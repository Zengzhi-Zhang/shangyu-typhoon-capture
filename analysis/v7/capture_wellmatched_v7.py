# -*- coding: utf-8 -*-
"""Post-hoc v7 control-selected capture analysis; cached data only.

The pure geometry below is copied from v6, without importing any v6 module.
No source-workbook, raw-AVI or key-reading path exists in this script.
"""
from __future__ import annotations
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[2]), str(_ReleasePath(__file__).resolve().parents[0])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file

import argparse
from collections import defaultdict
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import time

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from pyproj import Transformer
from scipy.spatial import cKDTree
from scipy.stats import spearmanr


BASE = Path(_release_path('project_root'))
OUT = BASE / 'formal_v7'
OLD = BASE / 'formal_v6'
INTERNAL = OUT / '01_internal'
PUB = OUT / '03_taxi_probe'
ENV = OUT / '00_env'
FIG = OUT / '08_figures'
STATE_PATH = INTERNAL / 'device_state_internal_v7.csv'
SEED = 20261005
CONTROL = [f'2021-07-{d:02d}' for d in range(12, 20)]
TARGET = [f'2021-07-{d:02d}' for d in range(25, 32)]
DATES = CONTROL + TARGET
RADII = [60, 40]
VARIANTS = [('main_R60_cap03', 60, .3), ('sens_R60_cap02', 60, .2),
            ('sens_R60_cap04', 60, .4), ('sens_R40_cap03', 40, .3)]
PROJECT = Transformer.from_crs(4326, 32651, always_xy=True)


def now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def safe_json(obj, path):
    def clean(v):
        if isinstance(v, dict): return {str(k): clean(x) for k, x in v.items()}
        if isinstance(v, (tuple, list)): return [clean(x) for x in v]
        if isinstance(v, np.ndarray): return clean(v.tolist())
        if isinstance(v, np.generic): return clean(v.item())
        if isinstance(v, float) and not np.isfinite(v): return None
        return v
    path.write_text(json.dumps(clean(obj), ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def save(frame, path, count_columns=()):
    f = frame.copy()
    if 'spearman_p' in f:
        f['spearman_p']=f['spearman_p'].map(lambda x: f'{float(x):.6g}' if pd.notna(x) and not isinstance(x,str) else x)
    for col in count_columns:
        if col in f:
            f[col] = f[col].map(lambda x: '<10' if pd.notna(x) and not isinstance(x, str) and x < 10 else (str(int(x)) if pd.notna(x) and not isinstance(x, str) else x))
    f.to_csv(path, index=False, encoding='utf-8-sig', float_format='%.4f', na_rep='NA')


def stats(v):
    a = np.asarray(v, float); a = a[np.isfinite(a)]
    if not len(a): return dict(n=0, median=np.nan, q25=np.nan, q75=np.nan, iqr=np.nan)
    q1, med, q3 = np.quantile(a, [.25, .5, .75])
    return dict(n=len(a), median=float(med), q25=float(q1), q75=float(q3), iqr=float(q3-q1))


def ci(v, prefix):
    a = np.asarray(v, float); good = a[np.isfinite(a)]
    return {prefix+'_ci_lo': float(np.quantile(good, .025)) if len(good) else np.nan,
            prefix+'_ci_hi': float(np.quantile(good, .975)) if len(good) else np.nan,
            prefix+'_valid_draws': len(good)}


def div(n, d):
    return np.divide(n, d, out=np.full(np.broadcast_shapes(np.shape(n), np.shape(d)), np.nan), where=np.asarray(d)>0)


def nearest_indices(reference, query):
    if not len(reference): return np.zeros(len(query), int), np.full(len(query), np.inf)
    j = np.searchsorted(reference, query)
    a = np.clip(j-1, 0, len(reference)-1); b = np.clip(j, 0, len(reference)-1)
    choose = np.abs(reference[b]-query) < np.abs(reference[a]-query)
    idx = np.where(choose, b, a)
    return idx, np.abs(reference[idx]-query)


def segment_events(g, camera_xy, tree):
    g = g.sort_values('timestamp', kind='stable')
    if len(g)<2: return np.empty((0, 3))
    valid = g.valid_xy.to_numpy(bool)
    ts = (g.timestamp-g.timestamp.dt.normalize()).dt.total_seconds().to_numpy()
    dt = np.diff(ts)
    x, y = PROJECT.transform(g.lon.to_numpy(), g.lat.to_numpy())
    dx = np.diff(x); dy = np.diff(y); length = np.hypot(dx, dy)
    ok = valid[:-1]&valid[1:]&(dt>0)&(dt<=120)&(length>=30)&(length<=1500)&(length/np.maximum(dt,1)*3.6<=150)
    starts = np.flatnonzero(ok); events = []
    if not len(starts): return np.empty((0, 3))
    mids = np.column_stack([(x[starts]+x[starts+1])/2, (y[starts]+y[starts+1])/2])
    groups = tree.query_ball_point(mids, length[starts]/2+100)
    for i, inds in zip(starts, groups):
        if not inds: continue
        inds = np.asarray(inds, int); v = camera_xy[inds]-[x[i], y[i]]
        fraction = np.clip((v[:,0]*dx[i]+v[:,1]*dy[i])/(length[i]**2), 0, 1)
        distance = np.hypot(v[:,0]-fraction*dx[i], v[:,1]-fraction*dy[i]); inside=distance<=100
        if inside.any(): events.append(np.column_stack([inds[inside], ts[i]+fraction[inside]*dt[i], distance[inside]]))
    return np.vstack(events) if events else np.empty((0,3))


def dedup_expected(times):
    keep=[]; last=-np.inf
    for t in np.sort(np.asarray(times,float)):
        if t-last>300: keep.append(t); last=t
    return np.asarray(keep,float)


def count_captures(expected, observed):
    _, distance = nearest_indices(observed, expected)
    return len(expected), int((distance<=180).sum())


def load_attrs():
    attrs=pd.read_csv(BASE/'01_panels/device_attributes.csv', encoding='utf-8-sig').sort_values('dev').reset_index(drop=True)
    attrs['dev_public']=np.arange(1,len(attrs)+1)
    for col in ['in_A200','in_Sstar']:
        attrs[col]=attrs[col].astype(str).str.lower().isin(['true','1'])
    attrs.loc[(attrs.lon==0)|(attrs.lat==0),['lon','lat']]=np.nan
    return attrs


def schema_only():
    ENV.mkdir(parents=True,exist_ok=True)
    paths=sorted((OLD/'01_internal/taxi_gps_points').glob('*.parquet'))
    required={'timestamp','date','lon','lat','valid_xy'}
    schemas=[set(pq.ParquetFile(p).schema_arrow.names) for p in paths]
    avi=pq.ParquetFile(OLD/'01_internal/taxi_avi_records_v6.parquet')
    attrs=load_attrs()
    report=dict(at=now(),source_reads=False,key_reads=False,effects_computed=False,
                GPS_files=len(paths),GPS_required_schema=all(required.issubset(x) for x in schemas),
                AVI_rows=avi.metadata.num_rows,AVI_required_schema={'ph','dev','date','sec_of_day'}.issubset(avi.schema_arrow.names),
                attrs_rows=len(attrs),A200_geolocated=int((attrs.in_A200&attrs.lon.notna()&attrs.lat.notna()).sum()),
                state_path=str(STATE_PATH.relative_to(OUT)),state_available=STATE_PATH.exists(),
                pure_helpers_copied_no_v6_import=True,
                planned_variants=VARIANTS,control_dates=CONTROL,target_dates=TARGET)
    report['passed']=report['GPS_files']==290 and report['GPS_required_schema'] and report['AVI_rows']==4440781 and report['AVI_required_schema']
    safe_json(report,ENV/'capture_schema_preflight_v7.json')
    print(json.dumps({k:report[k] for k in ['passed','GPS_files','AVI_rows','effects_computed','state_available']}))
    if not report['passed']: raise RuntimeError('cached_schema_preflight_failed')


def build_counts(cameras):
    cached=INTERNAL/'capture_vehicle_counts_v7.npz'
    if cached.exists():
        data=np.load(cached,allow_pickle=False)
        if list(data['dates'])!=DATES or list(data['radii'])!=RADII or list(data['camera_ids'])!=list(cameras.dev_public):
            raise RuntimeError('cached_count_schema_changed')
        return data['all_day'],data['h11'],dict(cache_reused=True)
    paths=sorted((OLD/'01_internal/taxi_gps_points').glob('*.parquet'))
    if len(paths)!=290: raise RuntimeError('requires290complete_cached_GPS')
    avi=pd.read_parquet(OLD/'01_internal/taxi_avi_records_v6.parquet',columns=['ph','dev','date','sec_of_day'])
    avi['date']=avi.date.astype(str); avi['sec_of_day']=pd.to_numeric(avi.sec_of_day,errors='coerce')
    bad=int((~avi.sec_of_day.ge(0)|~avi.sec_of_day.lt(86400)).sum())
    avi=avi[avi.date.isin(DATES)&avi.sec_of_day.ge(0)&avi.sec_of_day.lt(86400)]
    devmap={dev:i for i,dev in enumerate(cameras.dev)}
    observed={(ph,day,dev):np.sort(g.sec_of_day.to_numpy(float)) for (ph,day,dev),g in avi.groupby(['ph','date','dev'],sort=False) if dev in devmap}
    obs_ids=defaultdict(set)
    for ph,day,dev in observed: obs_ids[(ph,day)].add(devmap[dev])
    x,y=PROJECT.transform(cameras.lon.to_numpy(),cameras.lat.to_numpy()); xy=np.column_stack([x,y]); tree=cKDTree(xy)
    shape=(len(RADII),290,len(DATES),len(cameras),2)
    all_day=np.zeros(shape,dtype=np.int32);h11=np.zeros(shape,dtype=np.int32)
    candidate_rows=0
    for vi,path in enumerate(paths):
        ph=path.stem
        gps=pd.read_parquet(path,columns=['timestamp','date','lon','lat','valid_xy']);gps=gps[gps.date.isin(DATES)]
        for di,day in enumerate(DATES):
            g=gps[gps.date.eq(day)];events=segment_events(g,xy,tree);candidate_rows+=len(events)
            eventgroups={}
            if len(events):
                events=events[np.argsort(events[:,0],kind='stable')];ids,starts=np.unique(events[:,0].astype(int),return_index=True)
                eventgroups={int(i):v for i,v in zip(ids,np.split(events,starts[1:]))}
            for camera_i in set(eventgroups)|obs_ids[(ph,day)]:
                ev=eventgroups.get(camera_i,np.empty((0,3)))
                obs=observed.get((ph,day,cameras.iloc[camera_i].dev),np.empty(0))
                obs_h11=obs[(obs>=39600)&(obs<86400)]
                for ri,radius in enumerate(RADII):
                    ex=dedup_expected(ev[ev[:,2]<=radius,1])
                    all_day[ri,vi,di,camera_i]=count_captures(ex,obs)
                    # Dedup the full day first; then apply the same passage-time
                    # restriction on event and controls. No event-driven reselect.
                    ex_h11=ex[(ex>=39600)&(ex<86400)]
                    h11[ri,vi,di,camera_i]=count_captures(ex_h11,obs_h11)
        if (vi+1)%25==0:
            print(json.dumps(dict(at=now(),stage='cached_GPS_geometry',vehicles_complete=vi+1,vehicles_total=290)),flush=True)
    assert (all_day[...,1]<=all_day[...,0]).all() and (h11[...,1]<=h11[...,0]).all()
    assert (h11[...,0]<=all_day[...,0]).all()
    np.savez_compressed(cached,all_day=all_day,h11=h11,dates=np.asarray(DATES),radii=np.asarray(RADII),camera_ids=cameras.dev_public.to_numpy())
    return all_day,h11,dict(cache_reused=False,AVI_invalid_seconds=bad,candidate_rows=candidate_rows)


def median_boot(point, vehicle, mask, rng):
    vals=point[mask]; values=vehicle[:,mask]
    camera=[np.median(rng.choice(vals,len(vals),replace=True)) for _ in range(500)] if len(vals) else []
    finite=np.isfinite(values).sum(axis=1)
    with np.errstate(all='ignore'):
        med=np.array([np.median(row[np.isfinite(row)]) if np.isfinite(row).any() else np.nan for row in values])
    return dict(**stats(vals),**ci(camera,'camera'),**ci(med,'vehicle'),
                vehicle_finite_cells_min=int(finite.min()) if len(finite) else 0,
                vehicle_finite_cells_max=int(finite.max()) if len(finite) else 0),med


def main():
    start=now();tick=time.monotonic()
    for directory in [INTERNAL,PUB,ENV,FIG]:directory.mkdir(parents=True,exist_ok=True)
    if not (ENV/'protocol_frozen_v7.json').exists():raise RuntimeError('root_protocol_not_frozen')
    protocol_sha=hashlib.sha256((ENV/'protocol_frozen_v7.json').read_bytes()).hexdigest()
    safe_json(dict(start=start,status='running',complete=False,source_reads=False,key_reads=False),ENV/'capture_execution_v7.json')
    attrs=load_attrs();cameras=attrs[attrs.in_A200&attrs.lon.notna()&attrs.lat.notna()].copy().reset_index(drop=True)
    states=pd.read_csv(STATE_PATH,encoding='utf-8-sig')
    idcol='dev_public' if 'dev_public' in states else 'dev'
    states[idcol]=pd.to_numeric(states[idcol]);states['date']=states.date.astype(str)
    if states.duplicated([idcol,'date']).any():raise RuntimeError('duplicate_v7_state_cell')
    if not set(TARGET).issubset(set(states.date)):raise RuntimeError('v7_state_target_dates_incomplete')
    state_lookup=states.set_index([idcol,'date'])
    all_day,h11,build_info=build_counts(cameras)
    # Independent established v6 count concordance for unchanged geometry.
    old=pd.read_csv(OLD/'01_internal/camera_capture_unmasked_v6.csv',encoding='utf-8-sig')
    for day in ['2021-07-19','2021-07-26','2021-07-27','2021-07-28']:
        current=all_day[0,:,DATES.index(day)].sum(axis=0)
        previous=old[old.date.eq(day)].set_index('dev').reindex(cameras.dev_public)
        if not np.array_equal(current[:,0],previous.expected.to_numpy()) or not np.array_equal(current[:,1],previous.captured.to_numpy()):
            raise RuntimeError('v6_geometry_count_concordance_failed')
    rng=np.random.default_rng(SEED)
    weights=rng.multinomial(290,np.full(290,1/290),size=200).astype(np.float64)
    summary=[];state_rows=[];type_rows=[];details=[];selection_rows=[];acceptances=[];all_replicates={}
    internal_dates=[]
    for ri,radius in enumerate(RADII):
        sums=all_day[ri].sum(axis=0);matched=h11[ri].sum(axis=0)
        ctrl=sums[:8].sum(axis=0);ctrl_h11=matched[:8].sum(axis=0)
        cp=div(ctrl[:,1],ctrl[:,0]);cp_h11=div(ctrl_h11[:,1],ctrl_h11[:,0])
        vctrl=all_day[ri,:,:8].sum(axis=1);vctrl_h11=h11[ri,:,:8].sum(axis=1)
        bc=weights@vctrl.reshape(290,-1);bc=bc.reshape(200,len(cameras),2)
        bch=weights@vctrl_h11.reshape(290,-1);bch=bch.reshape(200,len(cameras),2)
        for name,rr,threshold in VARIANTS:
            if rr!=radius:continue
            selected=(ctrl[:,0]>=30)&(cp>=threshold)
            for camera_i,camera in cameras.iterrows():
                selection_rows.append(dict(variant=name,dev=int(camera.dev_public),radius_m=radius,cap_threshold=threshold,expected_ctrl=int(ctrl[camera_i,0]),captured_ctrl=int(ctrl[camera_i,1]),cap_ctrl=cp[camera_i],selected=bool(selected[camera_i])))
            # The type table uses control only and all geolocated A200 cameras.
            types=cameras[['dev_public','org','in_Sstar']].copy()
            first_state=states[states.date.eq('2021-07-26')].set_index(idcol)
            types['base_flow_quartile']=types.dev_public.map(first_state.base_flow_quartile)
            types['expected_ctrl']=ctrl[:,0];types['captured_ctrl']=ctrl[:,1];types['cap_ctrl']=cp;types['selected']=selected
            for group_column in ['org','base_flow_quartile']:
                for group,g in types.groupby(group_column,dropna=False,sort=True):
                    for minimum in [10,30]:
                        eligible=g[g.expected_ctrl>=minimum]
                        type_rows.append(dict(variant=name,radius_m=radius,cap_threshold=threshold,group_by=group_column,group=str(group),min_expected_ctrl=minimum,n_devices=len(g),n_ctrl_eligible=len(eligible),n_selected=int(g.selected.sum()),share_cap_ge03=float((eligible.cap_ctrl>=.3).mean()) if len(eligible) else np.nan,**{k:v for k,v in stats(eligible.cap_ctrl).items() if k!='n'}))
            for day in TARGET:
                di=DATES.index(day);hour_matched=day=='2021-07-25'
                event=matched[di] if hour_matched else sums[di]
                control=ctrl_h11 if hour_matched else ctrl
                control_cap=cp_h11 if hour_matched else cp
                ec=div(event[:,1],event[:,0]);relative=div(ec,control_cap)
                event_vehicle=h11[ri,:,di] if hour_matched else all_day[ri,:,di]
                be=(weights@event_vehicle.reshape(290,-1)).reshape(200,len(cameras),2)
                bcontrol=bch if hour_matched else bc
                br=div(div(be[:,:,1],be[:,:,0]),div(bcontrol[:,:,1],bcontrol[:,:,0]))
                comparable=selected&(event[:,0]>=10)&np.isfinite(relative)&(control_cap>0)
                st=state_lookup.reindex(pd.MultiIndex.from_arrays([cameras.dev_public,[day]*len(cameras)]))
                if st.state.isna().any():raise RuntimeError('v7_state_camera_day_incomplete')
                failed=st.A1_failed.astype(str).str.lower().isin(['true','1']).to_numpy()
                stable=comparable&cameras.in_Sstar.to_numpy()
                base=dict(variant=name,date=day,radius_m=radius,window_seconds=180,cap_threshold=threshold,hour_matched=int(hour_matched),posthoc_revision=True,v6_S2_historical=True,v6_S3_historical=True)
                bstat,bmed=median_boot(relative,br,stable,rng)
                fail_all=selected&failed;fail_eligible=fail_all&(event[:,0]>=10)
                total=event[fail_eligible].sum(axis=0)
                fail_boot=div(be[:,fail_eligible,1].sum(axis=1),be[:,fail_eligible,0].sum(axis=1))
                camera_fail=[]
                ids=np.flatnonzero(fail_eligible)
                if len(ids):
                    for _ in range(500):
                        sampled=rng.choice(ids,len(ids),replace=True);e,c=event[sampled].sum(axis=0);camera_fail.append(c/e if e else np.nan)
                ratio=pd.to_numeric(st.ratio,errors='coerce').to_numpy()
                corr=comparable&np.isfinite(ratio)
                rho,p=spearmanr(ratio[corr],relative[corr]) if corr.sum()>=3 else (np.nan,np.nan)
                row=dict(**base,n_selected=int(selected.sum()),n_comparable=int(comparable.sum()),n_selected_invalid_control=int((selected&(~np.isfinite(control_cap)|(control_cap<=0))).sum()),n_Sstar_comparable=int(stable.sum()),
                         Sstar_relative_median=bstat['median'],Sstar_relative_q25=bstat['q25'],Sstar_relative_q75=bstat['q75'],Sstar_relative_iqr=bstat['iqr'],
                         **{k:v for k,v in bstat.items() if k not in ['n','median','q25','q75','iqr']},
                         n_A1_failed_all=int(states[(states.date.eq(day))&states.in_A200.astype(str).str.lower().isin(['true','1'])&states.A1_failed.astype(str).str.lower().isin(['true','1'])].shape[0]),
                         n_failed_selected=int(fail_all.sum()),n_failed_event_ge10=int(fail_eligible.sum()),n_failed_event_lt3=int((fail_all&(event[:,0]<3)).sum()),n_failed_event_3to9=int((fail_all&(event[:,0]>=3)&(event[:,0]<10)).sum()),
                         failed_selected_expected=int(event[fail_all,0].sum()),failed_selected_captured=int(event[fail_all,1].sum()),
                         failed_event_ge10_expected=int(total[0]),failed_event_ge10_captured=int(total[1]),failed_event_ge10_cap=float(total[1]/total[0]) if total[0] else np.nan,
                         **ci(fail_boot,'failed_vehicle'),**ci(camera_fail,'failed_camera'),n_spearman=int(corr.sum()),spearman_rho=float(rho),spearman_p=float(p))
                summary.append(row)
                acceptance=dict(variant=name,date=day,Sstar_relative_median_in_090_105=bool(.9<=bstat['median']<=1.05) if np.isfinite(bstat['median']) else None,failed_pooled_cap_le002=bool(total[1]/total[0]<=.02) if total[0] else None,Spearman_ge06=bool(rho>=.6) if np.isfinite(rho) else None)
                acceptances.append(acceptance)
                all_replicates[name+'__'+day]=dict(Sstar_vehicle_median=bmed,failed_vehicle_cap=fail_boot,vehicle_finite_cells=np.isfinite(br[:,stable]).sum(axis=1))
                for label in sorted(set(st.state)):
                    mask=comparable&st.state.eq(label).to_numpy();ss,_=median_boot(relative,br,mask,rng)
                    state_rows.append(dict(**base,state=label,n_selected_state=int((selected&st.state.eq(label).to_numpy()).sum()),n_comparable_state=int(mask.sum()),**ss))
                for camera_i,camera in cameras.iterrows():
                    d=dict(**base,dev=int(camera.dev_public),selected=bool(selected[camera_i]),in_Sstar=bool(camera.in_Sstar),A1_failed=bool(failed[camera_i]),state=st.iloc[camera_i].state,ratio=ratio[camera_i],ring=st.iloc[camera_i].ring,org=camera.org,
                           expected_ctrl=int(ctrl[camera_i,0]),captured_ctrl=int(ctrl[camera_i,1]),cap_ctrl=cp[camera_i],
                           expected_ctrl_matched=int(control[camera_i,0]),captured_ctrl_matched=int(control[camera_i,1]),cap_ctrl_matched=control_cap[camera_i],
                           expected=int(event[camera_i,0]),captured=int(event[camera_i,1]),cap=ec[camera_i],relative_cap=relative[camera_i],event_expected_ge10=bool(event[camera_i,0]>=10),comparable=bool(comparable[camera_i]))
                    details.append(d)
    result=pd.DataFrame(summary);by_state=pd.DataFrame(state_rows);types=pd.DataFrame(type_rows);detail=pd.DataFrame(details);selections=pd.DataFrame(selection_rows)
    # Internal retained precision, public rate precision follows the reference.
    for name,frame in [('capture_summary_internal_v7.csv',result),('capture_state_internal_v7.csv',by_state),('capture_camera_internal_v7.csv',detail),('capture_selection_internal_v7.csv',selections)]:
        frame.to_csv(INTERNAL/name,index=False,encoding='utf-8-sig',float_format='%.12g',na_rep='NA')
    np.savez_compressed(INTERNAL/'capture_bootstrap_v7.npz',**{key+'__'+metric:val for key,vals in all_replicates.items() for metric,val in vals.items()})
    event_counts=['failed_selected_expected','failed_selected_captured','failed_event_ge10_expected','failed_event_ge10_captured']
    save(result,PUB/'T35_capture_wellmatched_v6.csv',event_counts)
    save(by_state,PUB/'T35_by_state_v6.csv');save(types,PUB/'T35_camera_type_v6.csv')
    public=detail.copy()
    low=public.expected<10
    public.loc[low,['cap','relative_cap']]=np.nan
    public.loc[public.expected_ctrl<10,'cap_ctrl']=np.nan
    for group in [('expected','captured'),('expected_ctrl_matched','captured_ctrl_matched')]:
        low_group=public[group[0]]<10
        public.loc[low_group,list(group)]='<10'
        if group[0]=='expected_ctrl_matched':public.loc[low_group,['cap_ctrl_matched','relative_cap']]=np.nan
    save(public,PUB/'T35_capture_camera_v7.csv',['expected','captured','expected_ctrl','captured_ctrl','expected_ctrl_matched','captured_ctrl_matched'])
    main=result[result.variant.eq('main_R60_cap03')]
    save(main,FIG/'fig_capture_relative_v7_data.csv',event_counts)
    failed_scatter=public[public.variant.eq('main_R60_cap03')&public.selected&public.A1_failed]
    save(failed_scatter,FIG/'fig_capture_failed_scatter_v7_data.csv',['expected','captured','expected_ctrl','captured_ctrl','expected_ctrl_matched','captured_ctrl_matched'])
    save(types[types.variant.eq('main_R60_cap03')],FIG/'fig_capture_type_v7_data.csv')
    v6_history=json.loads((OLD/'03_taxi_probe/T29_calibration_v6.json').read_text(encoding='utf-8-sig'))
    public_main=main.to_dict('records')
    for row in public_main:
        for column in event_counts:
            if row[column]<10:row[column]='<10'
    payload=dict(version='v7_posthoc_revision',control_dates=CONTROL,target_dates=TARGET,selection='control_only_pooled_8days',main_variant='main_R60_cap03',v6_history=dict(S2=v6_history['S2'],S3=v6_history['S3'],calibration_status=v6_history['calibration_status']),main_results=public_main,all_acceptance=acceptances,bootstrap_conditioning='Control selection and observed event-reporting eligibility fixed. Invalid bootstrap rate cells NA, never zero. No selection uncertainty included.',reviewer_numbers_not_prescribed=True)
    safe_json(payload,PUB/'T35_capture_wellmatched_v7.json')
    methods='''# 对照期可匹配卡口捕获率：v7方法\n\nv7是查看v6及审阅补算后提出的事后修订。对照期筛选只用于本次新增分析，不改v6的S2/S3、校准失败历史或H1–H4。原始坐标沿用v6最终raw；不从筛选后捕获率反推坐标校准成功。\n\n7月12–19日逐卡口合并捕获经过和应捕获经过，cap_ctrl为合计的比，不是逐日率平均。主集合要求全天expected_ctrl≥30且cap_ctrl≥0.3，只用对照期选卡。主60m/180秒；敏感性为cap阈值0.2、0.4及40m半径/0.3阈值，40m按自己的对照量重选。几何、300秒去重与180秒AVI匹配均复制v6纯函数，没有源或密钥读取路径。\n\n7月25日保留同一个全天对照选定集合，但应捕获插值时刻和AVI时刻均只取11–23时，并对八个对照日应用同一时段。先构造全部GPS线段、全天去重，再按经过时刻截取，跨11时线段不丢失。相对cap为事件cap/时段匹配对照池化cap。\n\n事件expected≥10只定义可比较报告子组，不参与选卡。失效表并列所有对照选定A1失效卡口合计和事件暴露合格子组合计，主≤0.02验收使用后者。另报expected<3和3–9台数。低探针暴露不能证明道路无人；捕获计数不能单独识别全车队真实交通或硬件故障。\n\nS*及各状态的相对cap使用等卡口中位数。500次卡口簇重抽固定合格卡口；200次车辆簇对290车取多项式权重，并在全部控制/事件日共享权重，重新计算两个cap后相除。控制选卡和观察事件合格集合均不重选，区间不包含选择或参数不确定性。重抽后任一单元控制/事件expected为0或控制cap为0时，相对量记NA；每个统计报告有效重复数和有限单元范围，不以0补。两套区间分别为2.5/97.5百分位。\n\n设备状态读取v7增补partial_day后的规则结果；A1失败、S*及比值定义不变。Spearman限定可比较、比值有效的已选卡口。机构和冻结流量四分位表只用对照期量，分别报告expected_ctrl≥10及≥30的设备组成与cap分布。所有七个事件日、四个变体和未达验收完整报告，审阅补算数字不是预定答案。公开设备使用整数序号；小于10的经过/捕获计数按v6屏蔽，低expected率为NA；没有车辆假名、内部设备ID或坐标。\n'''
    methods+='\nSpearman两侧均含AVI记录，因此该关联不构成完全独立的验证。GPS expected提供这批出租车在冻结几何条件下经过的证据；路线、设备类型及对照选卡仍限制其外推。公开p值用科学计数法，率与区间使用四位小数。\n'
    (PUB/'T35_METHODS_v7.md').write_text(methods,encoding='utf-8')
    checks=dict(captured_le_expected=bool((all_day[...,1]<=all_day[...,0]).all()),h11_captured_le_expected=bool((h11[...,1]<=h11[...,0]).all()),v6_geometry_exact_count_concordance=True,variants=len(result.variant.unique()),target_rows=len(main),all_variant_rows=len(result),GPS_vehicles=290,protocol_sha256=protocol_sha,source_reads=False,key_reads=False)
    safe_json(dict(start=start,end=now(),seconds=time.monotonic()-tick,complete=True,status='complete',command=_release_path('path_032'),source_reads=False,key_reads=False,build=build_info,checks=checks,main_results=main.to_dict('records'),acceptance=acceptances),ENV/'capture_execution_v7.json')
    print(json.dumps(dict(complete=True,seconds=time.monotonic()-tick,main_results=main[['date','n_selected','n_Sstar_comparable','Sstar_relative_median','camera_ci_lo','camera_ci_hi','vehicle_ci_lo','vehicle_ci_hi','n_failed_event_ge10','failed_event_ge10_expected','failed_event_ge10_captured','spearman_rho']].to_dict('records')),ensure_ascii=False),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--schema-only',action='store_true');args=parser.parse_args()
    if args.schema_only:schema_only()
    else:
        begun=now();timer=time.monotonic()
        try:main()
        except BaseException as exc:
            ENV.mkdir(parents=True,exist_ok=True)
            safe_json(dict(start=begun,end=now(),seconds=time.monotonic()-timer,complete=False,status='failed',error_type=type(exc).__name__,source_reads=False,key_reads=False),ENV/'capture_failure_v7.json')
            print(json.dumps(dict(complete=False,error_type=type(exc).__name__)),flush=True)
            raise SystemExit(1)
