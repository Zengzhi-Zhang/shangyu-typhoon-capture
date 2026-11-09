# -*- coding: utf-8 -*-
"""Control-calibrated line-segment probe capture. Never reads source or key."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[2]), str(_ReleasePath(__file__).resolve().parents[0])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from pathlib import Path
from datetime import datetime,timezone,timedelta
from collections import defaultdict
import json,time,math
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from scipy.stats import spearmanr
from taxi_parse_v6 import corrected_xy,gcj_to_wgs,PROJECT,baiguan_xy,RINGS,SEED

ROOT=Path(_release_path('project_root'));OUT=ROOT/'formal_v6';INTERNAL=OUT/'01_internal';PUB=OUT/'03_taxi_probe';ENV=OUT/'00_env'
CONTROL=[f'2021-07-{d:02d}' for d in range(12,20)]
TARGET=['2021-07-19','2021-07-26','2021-07-27','2021-07-28','2021-08-02']
RADII=[40,60,100];WINDOWS=[120,180,300]
NOW=lambda:datetime.now(timezone(timedelta(hours=8))).isoformat()

def save(frame,path):
    frame=frame.copy()
    for col in ['expected','captured','captured_unexpected']:
        if col in frame:
            frame[col]=frame[col].map(lambda x:x if isinstance(x,str) or pd.isna(x) else str(int(x)))
    # Mixed context/numeric long-table values need explicit ratio formatting.
    if 'value' in frame:
        frame['value']=frame['value'].map(lambda x:f'{x:.4f}' if isinstance(x,(float,np.floating)) and np.isfinite(x) else x)
    frame.to_csv(path,index=False,encoding='utf-8-sig',float_format='%.4f',na_rep='NA')

def safe_json(obj,path):
    def clean(x):
        if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
        if isinstance(x,(list,tuple)):return [clean(v) for v in x]
        if isinstance(x,np.generic):return clean(x.item())
        if isinstance(x,float) and not np.isfinite(x):return None
        return x
    path.write_text(json.dumps(clean(obj),ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')

def stats(v):
    v=np.asarray(v,float);v=v[np.isfinite(v)]
    if not len(v):return dict(n=0,median=None,q25=None,q75=None,iqr=None)
    a,b,c=np.quantile(v,[.25,.5,.75]);return dict(n=len(v),median=float(b),q25=float(a),q75=float(c),iqr=float(c-a))

def nearest_indices(reference,query):
    if not len(reference):return np.zeros(len(query),int),np.full(len(query),np.inf)
    j=np.searchsorted(reference,query);a=np.clip(j-1,0,len(reference)-1);b=np.clip(j,0,len(reference)-1)
    choose=np.abs(reference[b]-query)<np.abs(reference[a]-query);idx=np.where(choose,b,a)
    return idx,np.abs(reference[idx]-query)

def median_calibration(dx,dy):
    d=np.hypot(dx,dy);result=stats(d);result.update(dx=stats(dx),dy=stats(dy));return result

def calibrate(avi,attrs,paths):
    mapping=attrs.set_index('dev')[['lon','lat']];deltas=[];gcjdeltas=[]
    control=avi[avi.date.isin(CONTROL)]
    for ph,g in control.groupby('ph',sort=True):
        p=paths.get(ph)
        if p is None:continue
        gps=pd.read_parquet(p,columns=['timestamp','date','lon','lat','valid_xy'])
        gps=gps[gps.valid_xy & gps.date.isin(CONTROL)]
        for day,a in g.groupby('date',sort=True):
            v=gps[gps.date.eq(day)].sort_values('timestamp',kind='stable')
            if v.empty:continue
            gt=(v.timestamp-pd.Timestamp(day)).dt.total_seconds().to_numpy();at=a.sec_of_day.to_numpy(float)
            idx,dt=nearest_indices(gt,at);xy=mapping.reindex(a.dev)
            ok=(dt<=30)&np.isfinite(xy.lon.to_numpy())&np.isfinite(xy.lat.to_numpy())
            if not ok.any():continue
            lon=v.lon.to_numpy()[idx[ok]];lat=v.lat.to_numpy()[idx[ok]];cx,cy=PROJECT.transform(xy.lon.to_numpy()[ok],xy.lat.to_numpy()[ok])
            gx,gy=PROJECT.transform(lon,lat);deltas.append(np.column_stack([cx-gx,cy-gy]))
            glon,glat=gcj_to_wgs(lon,lat);gx,gy=PROJECT.transform(glon,glat);gcjdeltas.append(np.column_stack([cx-gx,cy-gy]))
    if not deltas:
        return dict(selected_method='raw_WGS84',calibration_available=False,S2=True,S2_reason='no_control_AVI_GPS_pairs_within30s',raw=dict(n=0),control_dates=CONTROL)
    delta=np.vstack(deltas);gcj=np.vstack(gcjdeltas);dx,dy=delta.T
    raw=median_calibration(dx,dy);sx=float(np.median(dx));sy=float(np.median(dy))
    shifted=median_calibration(dx-sx,dy-sy);literal=median_calibration(dx+sx,dy+sy);gcjs=median_calibration(gcj[:,0],gcj[:,1])
    eligible=bool(30<raw['median']<=300 and raw['iqr']<=60)
    if raw['median']<=30:selected='raw_WGS84';chosen=raw
    else:
        # No correction is always a valid fallback. A failed calibration cannot
        # justify applying a transformation that increases control residuals.
        candidates=[('raw_WGS84',raw),('GCJ02_to_WGS84',gcjs)]
        if eligible:candidates.insert(1,('constant_UTM_shift',shifted))
        selected,chosen=min(candidates,key=lambda z:z[1]['median'])
    return dict(calibration_available=True,control_dates=CONTROL,match_seconds=30,raw=raw,constant_shift=shifted,constant_eligible=eligible,literal_negative_shift_diagnostic_only=literal,GCJ02_to_WGS84=gcjs,selected_method=selected,selected=chosen,applied_dx_m=sx if selected=='constant_UTM_shift' else 0.,applied_dy_m=sy if selected=='constant_UTM_shift' else 0.,delta_definition='camera-GPS; constant calibrated GPS=GPS+median(delta)',candidate_policy='post-data implementation bugfix: retain raw no-correction fallback; apply only eligible correction improving control median; ties retain raw',raw_fallback=bool(selected=='raw_WGS84' and raw['median']>30),correction_applied=selected!='raw_WGS84',S2=bool(chosen['median']>60),S2_reason='corrected_or_raw_fallback_control_median_distance_gt60m' if chosen['median']>60 else None)

def segment_events(g,camera_xy,tree,calibration):
    """Return candidate(camera index, interpolation second, distance) once."""
    g=g.sort_values('timestamp',kind='stable')
    if len(g)<2:return np.empty((0,3))
    valid=g.valid_xy.to_numpy(bool);ts=(g.timestamp-g.timestamp.dt.normalize()).dt.total_seconds().to_numpy()
    dt=np.diff(ts);lon=g.lon.to_numpy();lat=g.lat.to_numpy();x,y=corrected_xy(lon,lat,calibration)
    dx=np.diff(x);dy=np.diff(y);length=np.hypot(dx,dy)
    ok=valid[:-1]&valid[1:]&(dt>0)&(dt<=120)&(length>=30)&(length<=1500)&(length/(np.maximum(dt,1))*3.6<=150)
    starts=np.flatnonzero(ok);events=[]
    if not len(starts):return np.empty((0,3))
    mids=np.column_stack([(x[starts]+x[starts+1])/2,(y[starts]+y[starts+1])/2]);r=length[starts]/2+100
    groups=tree.query_ball_point(mids,r)
    for i,inds in zip(starts,groups):
        if not inds:continue
        inds=np.asarray(inds,int);v=camera_xy[inds]-[x[i],y[i]];f=np.clip((v[:,0]*dx[i]+v[:,1]*dy[i])/(length[i]**2),0,1)
        d=np.hypot(v[:,0]-f*dx[i],v[:,1]-f*dy[i]);inside=d<=100
        if inside.any():events.append(np.column_stack([inds[inside],ts[i]+f[inside]*dt[i],d[inside]]))
    return np.vstack(events) if events else np.empty((0,3))

def dedup_expected(times):
    times=np.sort(np.asarray(times,float));keep=[];last=-np.inf
    for t in times:
        if t-last>300:keep.append(t);last=t
    return np.asarray(keep,float)

def capture_counts(expected,observed,window):
    _,dist=nearest_indices(observed,expected);captured=(dist<=window)
    _,back=nearest_indices(expected,observed);unexpected=int((back>window).sum())
    return int(len(expected)),int(captured.sum()),unexpected

def ring_records(avi,attrs):
    info=attrs.set_index('dev');rings=pd.cut(info.dist_baiguan_km,[0,2,4,7,12,np.inf],labels=RINGS,right=False).astype(object).fillna('unknown')
    online=pd.read_csv(ROOT/'01_panels/online_sets.csv',encoding='utf-8-sig');keys=set(zip(online.date,online.dev))
    a=avi.copy();a['ring']=a.dev.map(rings).fillna('unknown');a['stable']=a.dev.map(info.in_Sstar).fillna(False).astype(str).str.lower().isin(['true','1'])
    a['online']=[(d,dev) in keys for d,dev in zip(a.date,a.dev)];h=a.sec_of_day.ge(39600)&a.sec_of_day.lt(86400)
    a['rec_all']=1;a['rec_stable']=a.stable.astype(int);a['rec_online']=a.online.astype(int)
    for col in ['rec_all','rec_stable','rec_online']:a[col+'_h11']=a[col]*h
    columns=['rec_all','rec_stable','rec_online','rec_all_h11','rec_stable_h11','rec_online_h11']
    f=a.groupby(['ph','date','ring'],sort=True)[columns].sum().reset_index();save(f,INTERNAL/'taxi_ring_records_v6.csv')
    sums=f.groupby('date').rec_all.sum();base=avi.groupby('date').size();assert sums.equals(base.rename('rec_all'))
    return dict(rows=len(f),all_AVI_record_count=int(f.rec_all.sum()),unknown_ring_records=int(f[f.ring=='unknown'].rec_all.sum()),approx=0)

def main():
    start=NOW();tick=time.monotonic();PUB.mkdir(parents=True,exist_ok=True);ENV.mkdir(parents=True,exist_ok=True);(OUT/'08_figures').mkdir(parents=True,exist_ok=True)
    safe_json(dict(start=start,complete=False,status='running',command=_release_path('path_018'),source_reads=False,key_reads=False),ENV/'capture_execution_v6.json')
    protocol=json.loads((ENV/'interpretation_capture_v6.json').read_text(encoding='utf-8'))
    attrs=pd.read_csv(ROOT/'01_panels/device_attributes.csv',encoding='utf-8-sig').sort_values('dev').reset_index(drop=True);attrs['dev_id']=np.arange(1,len(attrs)+1)
    for col in ['in_A200','in_Sstar']:attrs[col]=attrs[col].astype(str).str.lower().isin(['true','1'])
    attrs.loc[(attrs.lon==0)|(attrs.lat==0),['lon','lat']]=np.nan
    cameras=attrs[attrs.in_A200 & attrs.lon.notna() & attrs.lat.notna()].copy().reset_index(drop=True)
    cx,cy=PROJECT.transform(cameras.lon.to_numpy(),cameras.lat.to_numpy());xy=np.column_stack([cx,cy]);tree=cKDTree(xy)
    allavi=pd.read_parquet(INTERNAL/'taxi_avi_records_v6.parquet',columns=['ph','dev','date','sec_of_day'])
    allavi.date=allavi.date.astype(str);allavi.sec_of_day=pd.to_numeric(allavi.sec_of_day,errors='coerce')
    paths={p.stem:p for p in sorted((INTERNAL/'taxi_gps_points').glob('*.parquet'))}
    if len(paths)!=290:raise RuntimeError('requires290complete_GPS_files')
    ring_check=ring_records(allavi,attrs)
    invalid_time=int((allavi.sec_of_day.isna()|(allavi.sec_of_day<0)|(allavi.sec_of_day>=86400)).sum())
    allavi=allavi[allavi.sec_of_day.ge(0)&allavi.sec_of_day.lt(86400)].copy()
    calibration=calibrate(allavi,attrs,paths)
    calibration['calibration_status']=('failed_preserve_raw' if calibration['selected_method']=='raw_WGS84' else 'failed_corrected_residual') if calibration['S2'] else ('raw_no_correction' if calibration['selected_method']=='raw_WGS84' else 'corrected_control_residual_within60m')
    calibration['postdata_implementation_correction']=True
    initial_path=ENV/'calibration_initial_candidate_failure_v6.json'
    if initial_path.exists():
        initial=json.loads(initial_path.read_text(encoding='utf-8-sig'))
        calibration['initial_forced_candidate_method']=initial['selected_method'];calibration['initial_forced_candidate_median_m']=initial['selected']['median']
    calibration['AVI_rows_without_valid_second_excluded_from_temporal_matching']=invalid_time;safe_json(calibration,PUB/'T29_calibration_v6.json')
    # Ring recalculation reads internal seven-column-derived cache, never source.
    from taxi_ring_update_v6 import recompute_ring_metrics_v6
    # Always update once: raw coordinates also need moving-distance h11 columns.
    recompute_ring_metrics_v6(calibration)
    print(json.dumps(dict(stage='I2_exact_ring_inputs_ready',coordinate_variant=calibration['selected_method'],ring_record_rows=ring_check['rows'],S2=calibration['S2'])),flush=True)
    cameras['ring']=pd.cut(cameras.dist_baiguan_km,[0,2,4,7,12,np.inf],labels=RINGS,right=False).astype(object).fillna('unknown')
    dkeys=list(paths);vmap={v:i for i,v in enumerate(dkeys)};devmap={v:i for i,v in enumerate(cameras.dev)}
    dates=[d for d in TARGET if d!='2021-08-02'];dmap={d:i for i,d in enumerate(dates)}
    # vehicle x date x camera x (expected,captured,unexpected), for every grid.
    counts={(r,w):np.zeros((290,len(dates),len(cameras),3),dtype=np.int32) for r in RADII for w in WINDOWS}
    observed={(ph,day,dev):np.sort(g.sec_of_day.to_numpy(float)) for (ph,day,dev),g in allavi[allavi.date.isin(dates)].groupby(['ph','date','dev'],sort=False)}
    observed_cameras=defaultdict(set)
    for ph,day,dev in observed:
        if dev in devmap:observed_cameras[(ph,day)].add(devmap[dev])
    total_segments=0
    for vi,(ph,p) in enumerate(paths.items()):
        gps=pd.read_parquet(p);gps=gps[gps.date.isin(dates)]
        # A missing GPS day still has zero expected and may have unexpected AVI.
        # Traverse all four observed-domain dates, retaining those AVI diagnostics.
        for day in dates:
            g=gps[gps.date.eq(day)]
            di=dmap[day];events=segment_events(g,xy,tree,calibration);total_segments+=len(events)
            eventgroups={}
            if len(events):
                events=events[np.argsort(events[:,0],kind='stable')];ids,starts=np.unique(events[:,0].astype(int),return_index=True)
                eventgroups={int(ci):v for ci,v in zip(ids,np.split(events,starts[1:]))}
            for ci in set(eventgroups)|observed_cameras[(ph,day)]:
                v=eventgroups.get(ci,np.empty((0,3)));obs=observed.get((ph,day,cameras.iloc[ci].dev),np.empty(0))
                if not len(v) and not len(obs):continue
                for r in RADII:
                    e=dedup_expected(v[v[:,2]<=r,1])
                    for w in WINDOWS:counts[(r,w)][vi,di,ci,:]=capture_counts(e,obs,w)
        if (vi+1)%25==0:print(f'{NOW()} capture_vehicles_complete={vi+1}/290',flush=True)
    grid=[];control_i=dmap['2021-07-19']
    for (r,w),a in counts.items():
        s=a[:,control_i,:,:].sum(axis=0);ok=s[:,0]>=10;cap=np.divide(s[:,1],s[:,0],out=np.full(len(s),np.nan),where=s[:,0]>0)
        st=stats(cap[ok]);grid.append(dict(radius_m=r,window_seconds=w,n_eligible_cameras=int(ok.sum()),control_median_cap=st['median'],control_q25_cap=st['q25'],control_q75_cap=st['q75']))
    default=next(x for x in grid if (x['radius_m'],x['window_seconds'])==(60,180));selected=default
    if default['control_median_cap'] is None or default['control_median_cap']<.6:
        eligible=[x for x in grid if x['control_median_cap'] is not None and x['control_median_cap']>=.6]
        if eligible:selected=sorted(eligible,key=lambda x:(-x['control_median_cap'],x['radius_m'],x['window_seconds']))[0]
    finite=[x['control_median_cap'] for x in grid if x['control_median_cap'] is not None]
    s3=bool(len(finite)==9 and max(finite)<.4);unavailable=bool(len(finite)<9)
    mainkey=(selected['radius_m'],selected['window_seconds']);a=counts[mainkey];summed=a.sum(axis=0)
    calibration.update(parameter_grid=grid,selected_radius_m=mainkey[0],selected_window_seconds=mainkey[1],parameter_upgraded=mainkey!=(60,180),S3=s3,parameter_grid_some_unavailable=unavailable,camera_results_enter_judgement=not(calibration['S2'] or s3 or unavailable),control_day_median_cap=selected['control_median_cap'])
    safe_json(calibration,PUB/'T29_calibration_v6.json');save(pd.DataFrame(grid),PUB/'T29_parameter_grid_v6.csv')
    states=pd.read_csv(OUT/'02_device_state/device_state_v6.csv',encoding='utf-8-sig');state_dev='dev_id' if 'dev_id' in states else 'dev'
    states[state_dev]=pd.to_numeric(states[state_dev]);state_lookup=states.set_index([state_dev,'date'])
    rows=[]
    for day in TARGET:
        for ci,c in cameras.iterrows():
            e,cap,unexp=summed[dmap[day],ci,:] if day in dmap else (np.nan,np.nan,np.nan)
            key=(int(c.dev_id),day);st=state_lookup.loc[key] if key in state_lookup.index else None
            row=dict(dev=int(c.dev_id),date=day,expected=e,captured=cap,cap=cap/e if e>0 else np.nan,captured_unexpected=unexp,
                GPS_available=day in dmap,eligible_expected_ge10=bool(e>=10),state=st['state'] if st is not None else 'unavailable',A1_failed=st['A1_failed'] if st is not None else np.nan,in_Sstar=bool(c.in_Sstar),ring=c.ring,org=c.org,base_flow_quartile=st.get('base_flow_quartile',None) if st is not None else None,ratio=st['ratio'] if st is not None else np.nan,
                radius_m=mainkey[0],window_seconds=mainkey[1],report_only=not calibration['camera_results_enter_judgement'],calibration_status=calibration['calibration_status'],calibration_failed=calibration['S2'])
            rows.append(row)
    internal=pd.DataFrame(rows);save(internal,INTERNAL/'camera_capture_unmasked_v6.csv')
    public=internal.copy()
    for col in ['expected','captured','captured_unexpected']:
        z=public[col].notna()&(public[col]<10);public.loc[z,col]='<10'
    low_expected=internal.expected.notna()&internal.expected.lt(10)
    public.loc[low_expected,['expected','captured','captured_unexpected']]='<10'
    public.loc[~public.eligible_expected_ge10,'cap']=np.nan;save(public,PUB/'T29_camera_capture_v6.csv')
    july26=internal[internal.date=='2021-07-26'];july19=internal[internal.date=='2021-07-19'];paired=july26.merge(july19,on='dev',suffixes=('_26','_19'))
    available=paired.eligible_expected_ge10_26&paired.eligible_expected_ge10_19
    stable=paired[available&paired.in_Sstar_26].copy();stable['cap_change']=stable.cap_26-stable.cap_19
    # Eligibility observed once, paired camera and shared vehicle cluster intervals.
    rng=np.random.default_rng(SEED);bstat=stats(stable.cap_change)
    bstat['median_absolute_change']=float(np.median(np.abs(stable.cap_change))) if len(stable) else None
    ciids=np.array([devmap[cameras[cameras.dev_id==d].iloc[0].dev] for d in stable.dev],int)
    vehicle_boot=[];camera_boot=[]
    if len(ciids):
        for _ in range(200):
            w=rng.multinomial(290,np.full(290,1/290));z=np.einsum('v,vdce->dce',w,a[:,:,ciids,:]);cap=np.divide(z[:,:,1],z[:,:,0],out=np.full(z[:,:,0].shape,np.nan),where=z[:,:,0]>0)
            diff=cap[dmap['2021-07-26']]-cap[dmap['2021-07-19']];vehicle_boot.append(float(np.nanmedian(diff)))
        vals=stable.cap_change.to_numpy()
        for _ in range(500):camera_boot.append(float(np.median(rng.choice(vals,len(vals),replace=True))))
    for name,v in [('vehicle',vehicle_boot),('camera',camera_boot)]:
        finiteb=np.asarray(v)[np.isfinite(v)];bstat[name+'_ci_lo']=float(np.quantile(finiteb,.025)) if len(finiteb) else None;bstat[name+'_ci_hi']=float(np.quantile(finiteb,.975)) if len(finiteb) else None
    scatter=paired[available&(paired.cap_19>0)&paired.ratio_26.notna()].copy();scatter['cap_relative']=scatter.cap_26/scatter.cap_19
    rho,p=(spearmanr(scatter.ratio_26,scatter.cap_relative) if len(scatter)>=3 else (np.nan,np.nan))
    failed_all=states[(states.date=='2021-07-26') & states.A1_failed.astype(str).str.lower().isin(['true','1'])]
    failed=july26[july26.A1_failed.astype(str).str.lower().isin(['true','1'])];ef=failed[failed.expected>=10];low=ef[ef.cap<=.1]
    A=dict(n_A1_failed_all=len(failed_all),n_failed_geolocated=len(failed),expected_ge10=len(ef),share_expected_ge10_all_failed=len(ef)/len(failed_all) if len(failed_all) else None,cap_le01=len(low),share_cap_le01_among_expected_ge10=len(low)/len(ef) if len(ef) else None,expected_lt3=int((failed.expected<3).sum()),expected_lt3_context='geolocated failed devices with GPS coverage only; low probe exposure does not prove no traffic')
    D=[]
    for state,g in july26[july26.eligible_expected_ge10].groupby('state'):D.append(dict(state=state,**stats(g.cap)))
    result=dict(A=A,B=bstat,C=dict(n=len(scatter),spearman_rho=float(rho),p=float(p)),D=D,control=selected,stop_conditions=dict(S2=calibration['S2'],S3=s3,parameter_grid_unavailable=unavailable),calibration_status=calibration['calibration_status'],camera_results_report_only=not calibration['camera_results_enter_judgement'],interpretation='Probe observations and sensor capture conditional on line-segment matching. Not causal traffic or hardware diagnoses.',missing_august2='no_GPS_not_zero_expected')
    summary=[]
    for name,obj in [('A',A),('B',bstat),('C',result['C'])]:
        for metric,value in obj.items():summary.append(dict(table=name,date='2021-07-26',state='all',metric=metric,value=value))
    for obj in D:
        for metric,value in obj.items():
            if metric!='state':summary.append(dict(table='D',date='2021-07-26',state=obj['state'],metric=metric,value=value))
    save(pd.DataFrame(summary),PUB/'T29_summary_v6.csv');safe_json(result,PUB/'T29_summary_v6.json')
    fig=scatter[['dev','ratio_26','cap_relative','state_26','ring_26','report_only_26']].rename(columns={'ratio_26':'ratio','state_26':'state','ring_26':'ring','report_only_26':'report_only'});fig['date']='2021-07-26';save(fig,OUT/'08_figures/fig_capture_scatter_v6_data.csv')
    mapdata=public[public.date=='2021-07-26'].merge(cameras[['dev_id','lon','lat']],left_on='dev',right_on='dev_id').drop(columns='dev_id')
    rng=np.random.default_rng(SEED);mx,my=PROJECT.transform(mapdata.lon.to_numpy(),mapdata.lat.to_numpy());mx=mx+rng.uniform(-200,200,len(mapdata));my=my+rng.uniform(-200,200,len(mapdata));mlon,mlat=PROJECT.transform(mx,my,direction='INVERSE');mapdata.lon=np.round(mlon,2);mapdata.lat=np.round(mlat,2)
    for col in ['lon','lat']:mapdata[col]=mapdata[col].map(lambda x:f'{x:.2f}')
    save(mapdata,OUT/'08_figures/fig_capture_map_v6_data.csv')
    acceptance=dict(control_median_ge06=selected['control_median_cap'] is not None and selected['control_median_cap']>=.6,Sstar_median_absolute_paired_change_le01=bool(bstat['median_absolute_change'] is not None and bstat['median_absolute_change']<=.1),Sstar_signed_median_absolute_le01=bool(bstat['median'] is not None and abs(bstat['median'])<=.1))
    checks=dict(captured_never_exceeds_expected=bool((summed[:,:,1]<=summed[:,:,0]).all()),all_grid_combinations=9,vehicles=290,A200_geolocated=len(cameras),GPS_missing_august2_rows=int((~internal.GPS_available).sum()),public_low_expected_cap_all_NA=bool(public.loc[~public.eligible_expected_ge10,'cap'].isna().all()),ring_records=ring_check,bootstrap_vehicle_draws=len(vehicle_boot),bootstrap_camera_draws=len(camera_boot))
    if not checks['captured_never_exceeds_expected'] or not checks['public_low_expected_cap_all_NA']:raise RuntimeError('capture_integrity_failed')
    safe_json(dict(start=start,end=NOW(),seconds=time.monotonic()-tick,complete=True,checks=checks,acceptance=acceptance,summary=result,command=_release_path('path_018'),source_reads=False,key_reads=False),ENV/'capture_execution_v6.json')
    print(json.dumps(dict(complete=True,S2=calibration['S2'],S3=s3,main_grid=mainkey,control_cap=selected['control_median_cap'],failed=A,Sstar_change=bstat),ensure_ascii=False))

if __name__=='__main__':
    run_start=NOW();run_tick=time.monotonic()
    try:main()
    except BaseException as e:
        # Exception messages may contain internal point-cache filenames; omit.
        ENV.mkdir(parents=True,exist_ok=True)
        safe_json(dict(start=run_start,end=NOW(),seconds=time.monotonic()-run_tick,complete=False,error_type=type(e).__name__,command=_release_path('path_018'),source_reads=False,key_reads=False),ENV/'capture_execution_v6.json')
        print(json.dumps(dict(complete=False,error_type=type(e).__name__)),flush=True)
        raise SystemExit(1)
