# -*- coding: utf-8 -*-
"""Bounded v8 geometry diagnostics. Cached GPS/AVI and authorized OSM only.

Pure passage geometry is copied from v7; no old module is imported or executed.
No secret or raw-workbook/raw-AVI reader exists in this module.
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
import geopandas as gpd
import shapely
from shapely.strtree import STRtree
from pyproj import Transformer, Geod
from scipy.spatial import cKDTree

BASE=Path(_release_path('project_root'))
OUT=BASE/'formal_v8'
ENV=OUT/'00_env'
PRIVATE=OUT/'01_internal'
PUBLIC=OUT/'02_geometry'
AUDIT=PRIVATE/'G5_audit'
ROAD=Path(_release_path('path_002'))
CONTROL=[f'2021-07-{d:02d}' for d in range(12,20)]
EVENT=[f'2021-07-{d:02d}' for d in range(25,29)]
DATES=CONTROL+EVENT
FILTERS=['main','G1','G2','G3']
PROJECT=Transformer.from_crs(4326,32651,always_xy=True)
GEOD=Geod(ellps='WGS84')
SEED=20261005
DIRECTION_LABELS=['北往南','南往北','西向东','东向西','其他']


def now():return datetime.now(timezone(timedelta(hours=8))).isoformat()


def clean(value):
    if isinstance(value,dict):return {str(k):clean(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [clean(v) for v in value]
    if isinstance(value,np.ndarray):return clean(value.tolist())
    if isinstance(value,np.generic):return clean(value.item())
    if isinstance(value,float) and not np.isfinite(value):return None
    return value


def write_json(obj,path):path.write_text(json.dumps(clean(obj),ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def public_csv(frame,path,count_cols=()):
    f=frame.copy()
    for col in count_cols:
        if col in f:f[col]=f[col].map(lambda x:'<10' if pd.notna(x) and x<10 else (str(int(x)) if pd.notna(x) else 'NA'))
    f.to_csv(path,index=False,encoding='utf-8-sig',float_format='%.4f',na_rep='NA')


def ratio(n,d):
    return np.divide(n,d,out=np.full(np.broadcast_shapes(np.shape(n),np.shape(d)),np.nan),where=np.asarray(d)>0)


def describe(a):
    x=np.asarray(a,float);x=x[np.isfinite(x)]
    if not len(x):return dict(n=0,median=np.nan,q25=np.nan,q75=np.nan,iqr=np.nan)
    q1,m,q3=np.quantile(x,[.25,.5,.75]);return dict(n=len(x),median=float(m),q25=float(q1),q75=float(q3),iqr=float(q3-q1))


def nearest(reference,query):
    if not len(reference):return np.zeros(len(query),int),np.full(len(query),np.inf)
    j=np.searchsorted(reference,query);a=np.clip(j-1,0,len(reference)-1);b=np.clip(j,0,len(reference)-1)
    idx=np.where(np.abs(reference[b]-query)<np.abs(reference[a]-query),b,a)
    return idx,np.abs(reference[idx]-query)


def direction_compatible(bearing,allowed):
    b=np.asarray(bearing,float);ok=np.zeros(len(b),bool)
    if '其他' in allowed:return np.ones(len(b),bool)
    if '北往南' in allowed:ok|=(b>=135)&(b<=225)
    if '南往北' in allowed:ok|=(b>=315)|(b<=45)
    if '西向东' in allowed:ok|=(b>=45)&(b<=135)
    if '东向西' in allowed:ok|=(b>=225)&(b<=315)
    return ok


def passage_events(g,xy,tree):
    """v7 accepted line segments, enriched without changing selection/dedup."""
    g=g.sort_values('timestamp',kind='stable')
    if len(g)<2:return pd.DataFrame()
    valid=g.valid_xy.to_numpy(bool)
    ts=(g.timestamp-g.timestamp.dt.normalize()).dt.total_seconds().to_numpy()
    dt=np.diff(ts);lon=g.lon.to_numpy();lat=g.lat.to_numpy()
    x,y=PROJECT.transform(lon,lat);dx=np.diff(x);dy=np.diff(y);length=np.hypot(dx,dy)
    ok=valid[:-1]&valid[1:]&(dt>0)&(dt<=120)&(length>=30)&(length<=1500)&(length/np.maximum(dt,1)*3.6<=150)
    starts=np.flatnonzero(ok)
    if not len(starts):return pd.DataFrame()
    bearing=(GEOD.inv(lon[:-1],lat[:-1],lon[1:],lat[1:])[0]+360)%360
    heading=g.heading.fillna('').astype(str).to_numpy();speed=pd.to_numeric(g.speed,errors='coerce').to_numpy()
    mids=np.column_stack([(x[starts]+x[starts+1])/2,(y[starts]+y[starts+1])/2])
    groups=tree.query_ball_point(mids,length[starts]/2+100)
    chunks=[]
    for i,inds in zip(starts,groups):
        if not inds:continue
        inds=np.asarray(inds,int);v=xy[inds]-[x[i],y[i]]
        fraction=np.clip((v[:,0]*dx[i]+v[:,1]*dy[i])/(length[i]**2),0,1)
        dist=np.hypot(v[:,0]-fraction*dx[i],v[:,1]-fraction*dy[i]);keep=dist<=60
        if not keep.any():continue
        ids=inds[keep];f=fraction[keep];endpoint=np.where(f<=.5,i,i+1)
        chunks.append(pd.DataFrame(dict(camera_i=ids,sec=ts[i]+f*dt[i],distance_m=dist[keep],
            x=x[i]+f*dx[i],y=y[i]+f*dy[i],bearing=bearing[i],segment_speed_kmh=length[i]/dt[i]*3.6,
            GPS_heading=heading[endpoint],GPS_speed=speed[endpoint])))
    if not chunks:return pd.DataFrame()
    candidates=pd.concat(chunks,ignore_index=True).sort_values(['camera_i','sec'],kind='stable')
    keep=[]
    for _,part in candidates.groupby('camera_i',sort=False):
        last=-np.inf
        for index,t in zip(part.index,part.sec):
            if t-last>300:keep.append(index);last=t
    return candidates.loc[keep].reset_index(drop=True)


def load_cameras():
    attrs=pd.read_csv(BASE/'01_panels/device_attributes.csv',encoding='utf-8-sig').sort_values('dev').reset_index(drop=True)
    attrs['dev_public']=np.arange(1,len(attrs)+1)
    attrs['in_Sstar']=attrs.in_Sstar.astype(str).str.lower().isin(['true','1'])
    selection=pd.read_csv(BASE/'formal_v7/01_internal/capture_selection_internal_v7.csv',encoding='utf-8-sig')
    selection=selection[selection.variant.eq('main_R60_cap03')]
    selected=selection[selection.selected.astype(str).str.lower().isin(['true','1'])].dev.astype(int)
    cameras=attrs[attrs.dev_public.isin(selected)].copy().sort_values('dev_public').reset_index(drop=True)
    assert len(cameras)==329 and cameras.lon.notna().all() and cameras.lat.notna().all()
    x,y=PROJECT.transform(cameras.lon.to_numpy(),cameras.lat.to_numpy());cameras['x']=x;cameras['y']=y
    return cameras


def load_roads(cameras):
    if not (ENV/'input_fingerprints_osm_begin_v8.json').exists():raise RuntimeError('OSM_begin_fingerprint_not_present')
    info=dict(available=False)
    try:
        raw=gpd.read_file(ROAD)
        if raw.crs is None:raise ValueError('OSM_CRS_missing')
        roads=raw[raw.geometry.notna()&~raw.geometry.is_empty].to_crs(32651).copy().reset_index(drop=True)
        if not len(roads):raise ValueError('OSM_empty')
        if 'name' not in roads or 'fclass' not in roads:raise ValueError('OSM_name_fclass_missing')
        roads['name_norm']=roads['name'].fillna('').astype(str).str.strip()
        roads['fclass_norm']=roads.fclass.fillna('').astype(str).str.strip()
        tree=STRtree(roads.geometry.to_numpy())
        choices=[];fallback=[];minimum=[]
        for row in cameras.itertuples():
            point=shapely.Point(row.x,row.y)
            inds=tree.query(point.buffer(30))
            inds=np.asarray([i for i in inds if roads.geometry.iloc[i].distance(point)<=30],int)
            if len(inds):
                choices.append(inds);fallback.append(False);minimum.append(float(min(roads.geometry.iloc[i].distance(point) for i in inds)))
            else:
                nearest_id=int(tree.nearest(point));distance=float(roads.geometry.iloc[nearest_id].distance(point))
                near=tree.query(point.buffer(min(distance+1e-7,80.0000001))) if distance<=80 else []
                tied=np.asarray([i for i in near if abs(roads.geometry.iloc[i].distance(point)-distance)<=1e-7],int)
                choices.append(np.sort(tied) if distance<=80 else np.array([],int));fallback.append(distance<=80);minimum.append(distance)
        roads.to_parquet(PRIVATE/'geometry_roads_projected_v8.parquet',index=False)
        info=dict(available=True,source_features=len(raw),projected_features=len(roads),source_crs=str(raw.crs),target_crs='EPSG:32651',
                  camera_road_within30=sum(len(x)>0 and not b for x,b in zip(choices,fallback)),
                  camera_road_fallback31to80=sum(fallback),camera_road_unavailable=sum(len(x)==0 for x in choices))
        return roads,tree,choices,np.asarray(fallback),np.asarray(minimum),info
    except Exception as error:
        info=dict(available=False,error_type=type(error).__name__,G2_G3_status='NA',no_silent_zero=True)
        return None,None,[np.array([],int) for _ in range(len(cameras))],np.zeros(len(cameras),bool),np.full(len(cameras),np.nan),info


def annotate_roads(points,roads,tree,choices):
    result=np.full(len(points),-1,np.int32);same=np.full(len(points),-1,np.int8)
    if roads is None:return result,same
    names=roads.name_norm.to_numpy();classes=roads.fclass_norm.to_numpy()
    allowed_names=[{(names[i],classes[i]) for i in ids if names[i]!=''} for ids in choices]
    allowed_ids=[set(ids) for ids in choices]
    for start in range(0,len(points),100000):
        part=points.iloc[start:start+100000]
        pairs=tree.query_nearest(shapely.points(part.x.to_numpy(),part.y.to_numpy()),all_matches=True)
        order=np.lexsort((pairs[1],pairs[0]));pairs=pairs[:,order]
        _,first=np.unique(pairs[0],return_index=True);pairs=pairs[:,first]
        result[start+pairs[0]]=pairs[1]
    for ci,part in points.groupby('camera_i',sort=False):
        if not len(choices[int(ci)]):continue
        indices=part.index.to_numpy();r=result[indices]
        same[indices]=[int(int(i) in allowed_ids[int(ci)] or (names[i]!='' and (names[i],classes[i]) in allowed_names[int(ci)])) for i in r]
    return result,same


def build_passages(cameras,roads,road_tree,choices):
    path=PRIVATE/'geometry_passages_v8.parquet'
    if path.exists():
        points=pd.read_parquet(path);dirs=json.loads((PRIVATE/'geometry_directions_v8.json').read_text(encoding='utf-8'))
        return points,{int(k):set(v) for k,v in dirs.items()},dict(cache_reused=True)
    avi=pd.read_parquet(BASE/'formal_v6/01_internal/taxi_avi_records_v6.parquet',columns=['ph','dev','date','sec_of_day','dir'])
    avi=avi[avi.date.isin(DATES)&avi.dev.isin(cameras.dev)&avi.sec_of_day.ge(0)&avi.sec_of_day.lt(86400)].copy()
    map_i={dev:i for i,dev in enumerate(cameras.dev)};avi['camera_i']=avi.dev.map(map_i)
    directions={};control=avi[avi.date.isin(CONTROL)]
    for i in range(len(cameras)):
        part=control[control.camera_i.eq(i)];shares=part.dir.value_counts()/len(part) if len(part) else pd.Series(dtype=float)
        directions[i]=set(shares[shares>=.05].index).intersection(DIRECTION_LABELS)
    write_json({str(i):sorted(v) for i,v in directions.items()},PRIVATE/'geometry_directions_v8.json')
    observed={(ph,day,int(ci)):np.sort(part.sec_of_day.to_numpy(float)) for (ph,day,ci),part in avi.groupby(['ph','date','camera_i'],sort=False)}
    del avi,control
    xy=cameras[['x','y']].to_numpy();tree=cKDTree(xy)
    paths=sorted((BASE/'formal_v6/01_internal/taxi_gps_points').glob('*.parquet'))
    assert len(paths)==290
    chunks=[];date_points={d:0 for d in DATES}
    for vi,path_in in enumerate(paths):
        ph=path_in.stem
        gps=pd.read_parquet(path_in,columns=['timestamp','date','lon','lat','valid_xy','speed','heading'])
        gps=gps[gps.date.isin(DATES)]
        for day,part in gps.groupby('date',sort=False):
            date_points[day]+=len(part);events=passage_events(part,xy,tree)
            if not len(events):continue
            captured=np.zeros(len(events),bool);captured_h11=np.zeros(len(events),bool);compatible=np.zeros(len(events),bool)
            for ci,g in events.groupby('camera_i',sort=False):
                obs=observed.get((ph,day,int(ci)),np.empty(0));_,delta=nearest(obs,g.sec.to_numpy())
                captured[g.index]=delta<=180
                obs11=obs[obs>=39600];_,delta11=nearest(obs11,g.sec.to_numpy())
                captured_h11[g.index]=(delta11<=180)&g.sec.ge(39600).to_numpy()
                compatible[g.index]=direction_compatible(g.bearing.to_numpy(),directions[int(ci)])
            events['vehicle_i']=vi;events['date']=day;events['captured']=captured;events['captured_h11']=captured_h11;events['G1']=compatible
            chunks.append(events)
        if (vi+1)%25==0:print(json.dumps(dict(at=now(),stage='cached_geometry',vehicles_complete=vi+1,total=290)),flush=True)
    points=pd.concat(chunks,ignore_index=True)
    points['road_i'],points['G2']=annotate_roads(points,roads,road_tree,choices)
    points['G3']=points.G1&(points.G2==1)
    points['camera_i']=points.camera_i.astype(np.int16);points['vehicle_i']=points.vehicle_i.astype(np.int16)
    points.to_parquet(path,index=False)
    return points,directions,dict(cache_reused=False,retained_main_passages=len(points),actual_GPS_points_by_date=date_points)


def counts(points,nc):
    out=np.zeros((4,len(DATES),nc,2),np.int64);h11=np.zeros_like(out)
    for di,day in enumerate(DATES):
        part=points[points.date.eq(day)]
        for fi,filter_name in enumerate(FILTERS):
            p=part if filter_name=='main' else part[part[filter_name]==1]
            ids=p.camera_i.to_numpy(int)
            np.add.at(out[fi,di,:,0],ids,1);np.add.at(out[fi,di,:,1],ids,p.captured.to_numpy(int))
            p=p[p.sec.ge(39600)];ids=p.camera_i.to_numpy(int)
            np.add.at(h11[fi,di,:,0],ids,1);np.add.at(h11[fi,di,:,1],ids,p.captured_h11.to_numpy(int))
    return out,h11


def bootstrap_median(values,rng):
    values=np.asarray(values,float);values=values[np.isfinite(values)]
    boot=np.median(rng.choice(values,(500,len(values)),replace=True),axis=1) if len(values) else np.full(500,np.nan)
    valid=boot[np.isfinite(boot)]
    return dict(camera_ci_lo=float(np.quantile(valid,.025)) if len(valid) else np.nan,
                camera_ci_hi=float(np.quantile(valid,.975)) if len(valid) else np.nan,
                camera_valid_draws=len(valid)),boot


def mask_public_camera(frame):
    f=frame.copy()
    low=f.expected_event<10;control_low=f.expected_control<10
    f.loc[low,['capture_rate','relative_capture']]=np.nan
    f.loc[control_low,['control_capture_rate','relative_capture']]=np.nan
    for mask,cols in [(low,['expected_event','captured_event']),(control_low,['expected_control','captured_control'])]:
        for col in cols:f[col]=f[col].astype(object);f.loc[mask,col]='<10'
    for col in ['expected_event','captured_event','expected_control','captured_control']:
        f[col]=f[col].map(lambda x:'<10' if not isinstance(x,str) and pd.notna(x) and x<10 else (str(int(x)) if not isinstance(x,str) and pd.notna(x) else x))
    return f


def summarise(cameras,points,full,h11,road_info,choices):
    states=pd.read_csv(BASE/'formal_v7/01_internal/device_state_internal_v7.csv',encoding='utf-8-sig').set_index(['dev_public','date'])
    network=pd.read_csv(BASE/'formal_v7/03_taxi_probe/T28_probe_daily_v7.csv',encoding='utf-8-sig').set_index('date')
    old=pd.read_csv(BASE/'formal_v7/01_internal/capture_camera_internal_v7.csv',encoding='utf-8-sig')
    old=old[old.variant.eq('main_R60_cap03')].set_index(['dev','date'])
    rng=np.random.default_rng(SEED)
    g0=[];summaries=[];shares=[];distance_rows=[];details=[];boots=[];camera_distance=[]
    ctrl_all=points[points.date.isin(CONTROL)];ctrl_11=ctrl_all[ctrl_all.sec.ge(39600)]
    controls=[ctrl_all,ctrl_11]
    group_masks={};g4_cache={};gold=[]
    for day in EVENT:
        di=DATES.index(day);hm=day=='2021-07-25';cube=h11 if hm else full
        control=cube[:,:8].sum(axis=1);event=cube[:,di]
        ctrl_points=controls[int(hm)];event_points=points[points.date.eq(day)&(points.sec.ge(39600) if hm else np.ones(len(points),bool))]
        state=states.reindex(pd.MultiIndex.from_arrays([cameras.dev_public,[day]*len(cameras)]))
        assert state.state.notna().all()
        failed=state.A1_failed.astype(str).str.lower().isin(['true','1']).to_numpy()
        stable=cameras.in_Sstar.to_numpy(bool)
        base_rel=ratio(ratio(event[0,:,1],event[0,:,0]),ratio(control[0,:,1],control[0,:,0]))
        fgroup=failed&(event[0,:,0]>=10)&(control[0,:,0]>0)
        sgroup=stable&(event[0,:,0]>=10)&np.isfinite(base_rel)&(control[0,:,1]>0)
        group_masks[day]={'A1_failed':fgroup,'Sstar':sgroup}
        previous=old.reindex(pd.MultiIndex.from_arrays([cameras.dev_public,[day]*len(cameras)]))
        gold.append(bool(np.array_equal(previous.expected.to_numpy(),event[0,:,0]) and np.array_equal(previous.captured.to_numpy(),event[0,:,1])))
        med_control=ctrl_points.groupby('camera_i').distance_m.median().reindex(range(len(cameras))).to_numpy()
        med_event=event_points.groupby('camera_i').distance_m.median().reindex(range(len(cameras))).to_numpy()
        delta=med_event-med_control;g4_cache[day]=delta
        tail_control=ctrl_points.assign(tail=ctrl_points.distance_m.between(40,60)).groupby('camera_i')['tail'].mean().reindex(range(len(cameras))).to_numpy()
        tail_event=event_points.assign(tail=event_points.distance_m.between(40,60)).groupby('camera_i')['tail'].mean().reindex(range(len(cameras))).to_numpy()
        for ci,c in cameras.iterrows():
            camera_distance.append(dict(dev=int(c.dev_public),date=day,A1_failed=bool(failed[ci]),in_Sstar=bool(stable[ci]),main_failed_comparable=bool(fgroup[ci]),main_Sstar_comparable=bool(sgroup[ci]),
                expected_event=int(event[0,ci,0]),captured_event=int(event[0,ci,1]),expected_control=int(control[0,ci,0]),captured_control=int(control[0,ci,1]),
                control_distance_median=med_control[ci],event_distance_median=med_event[ci],distance_median_shift=delta[ci],
                control_40_60_share=tail_control[ci],event_40_60_share=tail_event[ci],road_assigned=bool(len(choices[ci]))))
        for group,mask in group_masks[day].items():
            exposure=ratio(event[0,:,0],control[0,:,0]/8)
            vals=describe(exposure[mask]);pool=ratio(event[0,mask,0].sum(),control[0,mask,0].sum()/8).item()
            pooled_rel=ratio(ratio(event[0,mask,1].sum(),event[0,mask,0].sum()),ratio(control[0,mask,1].sum(),control[0,mask,0].sum())).item()
            g0.append(dict(date=day,group=group,hour_matched=int(hm),n_devices=int(mask.sum()),exposure_median=vals['median'],exposure_q25=vals['q25'],exposure_q75=vals['q75'],exposure_pooled=pool,
                event_expected=int(event[0,mask,0].sum()),event_captured=int(event[0,mask,1].sum()),control_expected=int(control[0,mask,0].sum()),control_captured=int(control[0,mask,1].sum()),
                pooled_relative_capture=pooled_rel,equal_camera_relative_median=describe(base_rel[mask])['median'],
                network_c_stable=float(network.loc[day,'c_stable']) if group=='Sstar' else np.nan))
            dc=ctrl_points[ctrl_points.camera_i.isin(np.flatnonzero(mask))];de=event_points[event_points.camera_i.isin(np.flatnonzero(mask))]
            ds=describe(delta[mask])
            distance_rows.append(dict(date=day,group=group,hour_matched=int(hm),n_devices=int(mask.sum()),n_valid_distance_shifts=ds['n'],
                shift_median_m=ds['median'],shift_q25_m=ds['q25'],shift_q75_m=ds['q75'],shift_iqr_m=ds['iqr'],
                control_40_60_share=float(dc.distance_m.between(40,60).mean()) if len(dc) else np.nan,
                event_40_60_share=float(de.distance_m.between(40,60).mean()) if len(de) else np.nan))
        for fi,filter_name in enumerate(FILTERS):
            available=filter_name in ['main','G1'] or road_info['available']
            e=event[fi];c=control[fi];control_cap=ratio(c[:,1],c[:,0]);evcap=ratio(e[:,1],e[:,0]);relative=ratio(evcap,control_cap)
            qualified_failed=failed&(e[:,0]>=10)
            comparable=stable&(e[:,0]>=10)&(c[:,0]>0)&(c[:,1]>0)&np.isfinite(relative)
            ds=describe(relative[comparable]);ci,boot=bootstrap_median(relative[comparable],rng)
            boots.append(pd.DataFrame(dict(filter=filter_name,date=day,replicate=np.arange(1,501),Sstar_relative_median=boot)))
            row=dict(filter=filter_name,date=day,hour_matched=int(hm),available=available,n_selected=329,n_failed_selected=int(failed.sum()),n_failed_event_ge10=int(qualified_failed.sum()),
                failed_all_expected=int(e[failed,0].sum()),failed_all_captured=int(e[failed,1].sum()),
                failed_ge10_expected=int(e[qualified_failed,0].sum()),failed_ge10_captured=int(e[qualified_failed,1].sum()),
                failed_ge10_cap=ratio(e[qualified_failed,1].sum(),e[qualified_failed,0].sum()).item(),
                n_Sstar_comparable=int(comparable.sum()),Sstar_relative_median=ds['median'],Sstar_relative_q25=ds['q25'],Sstar_relative_q75=ds['q75'],**ci,
                n_Sstar_event_ge10_zero_control_E=int((stable&(e[:,0]>=10)&(c[:,0]==0)).sum()),
                n_Sstar_event_ge10_zero_control_C=int((stable&(e[:,0]>=10)&(c[:,0]>0)&(c[:,1]==0)).sum()),
                n_camera_road_unavailable=int(sum(len(x)==0 for x in choices)) if filter_name in ['G2','G3'] else 0)
            if not available:
                for key in row:
                    if key.startswith('failed_') or key.startswith('Sstar_') or key in ['n_failed_event_ge10','n_Sstar_comparable','camera_ci_lo','camera_ci_hi','camera_valid_draws']:row[key]=np.nan
            summaries.append(row)
            for group,mask in group_masks[day].items():
                shares.append(dict(filter=filter_name,date=day,group=group,hour_matched=int(hm),n_devices=int(mask.sum()),available=available,
                    main_event_expected=int(event[0,mask,0].sum()),filtered_event_expected=int(e[mask,0].sum()) if available else np.nan,
                    event_retained_share=ratio(e[mask,0].sum(),event[0,mask,0].sum()).item() if available else np.nan,
                    main_control_expected=int(control[0,mask,0].sum()),filtered_control_expected=int(c[mask,0].sum()) if available else np.nan,
                    control_retained_share=ratio(c[mask,0].sum(),control[0,mask,0].sum()).item() if available else np.nan))
            for ci0,camera in cameras.iterrows():
                assigned=len(choices[ci0])>0;row_avail=available and (filter_name not in ['G2','G3'] or assigned)
                details.append(dict(dev=int(camera.dev_public),date=day,filter=filter_name,hour_matched=int(hm),available=row_avail,A1_failed=bool(failed[ci0]),in_Sstar=bool(stable[ci0]),
                    failed_event_ge10=bool(qualified_failed[ci0]),Sstar_comparable=bool(comparable[ci0]),
                    expected_event=int(e[ci0,0]) if row_avail else np.nan,captured_event=int(e[ci0,1]) if row_avail else np.nan,
                    expected_control=int(c[ci0,0]) if row_avail else np.nan,captured_control=int(c[ci0,1]) if row_avail else np.nan,
                    capture_rate=evcap[ci0] if row_avail else np.nan,control_capture_rate=control_cap[ci0] if row_avail else np.nan,
                    relative_capture=relative[ci0] if row_avail else np.nan,distance_median_shift=delta[ci0],
                    main_failed_comparable=bool(fgroup[ci0]),main_Sstar_comparable=bool(sgroup[ci0])))
    assert all(gold),'v7_main_count_concordance_failed'
    frames=dict(G0=pd.DataFrame(g0),G123=pd.DataFrame(summaries),shares=pd.DataFrame(shares),G4=pd.DataFrame(distance_rows),camera=pd.DataFrame(details),distance_camera=pd.DataFrame(camera_distance),bootstrap=pd.concat(boots,ignore_index=True))
    for key,frame in frames.items():frame.to_csv(PRIVATE/f'geometry_{key}_internal_v8.csv',index=False,encoding='utf-8-sig',float_format='%.12g',na_rep='NA')
    public_csv(frames['G0'],PUBLIC/'G0_exposure_v8.csv',['event_expected','event_captured','control_expected','control_captured'])
    public_csv(frames['G123'],PUBLIC/'G123_capture_v8.csv',['failed_all_expected','failed_all_captured','failed_ge10_expected','failed_ge10_captured'])
    public_csv(frames['shares'],PUBLIC/'G123_filter_shares_v8.csv',['main_event_expected','filtered_event_expected','main_control_expected','filtered_control_expected'])
    public_csv(frames['G4'],PUBLIC/'G4_distance_shift_v8.csv')
    public_csv(mask_public_camera(frames['camera']),PUBLIC/'G_camera_diagnostics_v8.csv')
    row=frames['G123'].query("filter=='G3' and date=='2021-07-26'").iloc[0]
    shifts=frames['G4'][frames['G4'].date.eq('2021-07-26')].set_index('group').shift_median_m
    accept=dict(A_G1=dict(reached=bool(row.available and row.n_failed_event_ge10>=40 and row.failed_ge10_cap<=.02),n_failed_event_ge10=row.n_failed_event_ge10,pooled_capture_rate=row.failed_ge10_cap,threshold_devices=40,threshold_rate=.02),
        A_G2=dict(reached=bool(row.available and .90<=row.Sstar_relative_median<=1.05),Sstar_relative_median=row.Sstar_relative_median,camera_ci_lo=row.camera_ci_lo,camera_ci_hi=row.camera_ci_hi,n_Sstar_comparable=row.n_Sstar_comparable,lower=.90,upper=1.05),
        A_G3=dict(reached=bool(shifts.A1_failed<=shifts.Sstar+10),failed_median_shift_m=shifts.A1_failed,Sstar_median_shift_m=shifts.Sstar,allowance_m=10),
        A_G4=dict(reached=None,status='pending_reviewer_visual_interpretation',n_figures_required=16,automatic_visual_verdict=False),
        posthoc_revision=True,main329_unchanged=True,v6_S2_S3_historical_unchanged=True,
        C1_rule='A-G1 or A-G3 not reached requires candidate-passage wording. All four reached requires reviewer A-G4; pending A-G4 is not a pass.')
    write_json(accept,PUBLIC/'G_acceptance_v8.json')
    return frames,accept,dict(v7_main_event_count_concordance=all(gold)),group_masks,g4_cache


def make_audit(cameras,points,directions,roads,choices,fallback,minimum,frames,group_masks,g4_cache):
    day='2021-07-26';camera=frames['distance_camera'];camera=camera[camera.date.eq(day)].set_index('dev')
    mainrows=frames['camera'].query("date=='2021-07-26' and filter=='main'").set_index('dev')
    failed=np.flatnonzero(group_masks[day]['A1_failed']);stable=np.flatnonzero(group_masks[day]['Sstar'])
    top8=sorted(failed,key=lambda i:(-camera.loc[int(cameras.iloc[i].dev_public),'expected_event'],int(cameras.iloc[i].dev_public)))[:8]
    shift4=sorted(set(failed)-set(top8),key=lambda i:(-g4_cache[day][i],int(cameras.iloc[i].dev_public)))[:4]
    stable4=sorted(stable,key=lambda i:(-camera.loc[int(cameras.iloc[i].dev_public),'expected_event'],int(cameras.iloc[i].dev_public)))[:4]
    selected=top8+shift4+stable4
    assert len(selected)==16 and len(set(selected))==16
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import LogNorm
    plt.rcParams['font.family']=['DejaVu Sans'];plt.rcParams['axes.unicode_minus']=False
    arrows={'北往南':(0,-1),'南往北':(0,1),'西向东':(1,0),'东向西':(-1,0)}
    attributes=[]
    for rank,ci in enumerate(selected,1):
        row=cameras.iloc[ci];pub=int(row.dev_public);x=float(row.x);y=float(row.y)
        control=points[points.camera_i.eq(ci)&points.date.isin(CONTROL)];event=points[points.camera_i.eq(ci)&points.date.eq(day)]
        fig,axes=plt.subplots(1,2,figsize=(12,6),sharex=True,sharey=True)
        if roads is not None:
            local=roads[roads.geometry.intersects(shapely.box(x-250,y-250,x+250,y+250))]
            for ax in axes:
                for geom in local.geometry:
                    parts=list(geom.geoms) if geom.geom_type=='MultiLineString' else [geom]
                    for part in parts:
                        xx,yy=part.xy;ax.plot(np.asarray(xx)-x,np.asarray(yy)-y,color='0.55',lw=.9,zorder=1)
        for ax in axes:
            ax.scatter([0],[0],marker='*',s=150,color='black',zorder=6)
            for label in sorted(directions[ci]):
                if label in arrows:
                    dx,dy=arrows[label];ax.annotate('',xy=(dx*100,dy*100),xytext=(0,0),arrowprops=dict(arrowstyle='->',color='#6a3d9a',lw=1.8),zorder=6)
            ax.set_xlim(-250,250);ax.set_ylim(-250,250);ax.set_aspect('equal');ax.set_xlabel('East from camera (m)');ax.grid(alpha=.15)
        axes[0].set_ylabel('North from camera (m)')
        if len(control):
            h=axes[0].hexbin(control.x-x,control.y-y,gridsize=45,extent=(-250,250,-250,250),mincnt=1,cmap='Greys',norm=LogNorm(),alpha=.8,zorder=3)
            fig.colorbar(h,ax=axes[0],fraction=.045,label='Control pooled passage density')
        for captured,color,marker,label in [(False,'#d95f02','o','Uncaptured'),(True,'#1f78b4','x','Captured')]:
            part=event[event.captured.eq(captured)]
            if len(part):axes[1].hexbin(part.x-x,part.y-y,gridsize=45,extent=(-250,250,-250,250),mincnt=1,cmap='Oranges' if not captured else 'Blues',alpha=.7 if not captured else .85,linewidths=.15,zorder=3 if not captured else 4)
            axes[1].scatter([],[],color=color,marker=marker,label=f'{label} passages: {len(part)}')
        axes[1].legend(loc='upper left',fontsize=8)
        axes[0].set_title('12–19 July controls (8-day pool)');axes[1].set_title('26 July (captured / uncaptured density)')
        reason='largest_failed_expected' if rank<=8 else ('largest_remaining_failed_shift' if rank<=12 else 'largest_Sstar_expected')
        wildcard='; direction wildcard' if '其他' in directions[ci] else ''
        fig.suptitle(f'Internal audit {rank:02d} | camera {pub} | {reason}{wildcard}\nGeometry only; visual interpretation pending',fontsize=11)
        fig.tight_layout();name=f'G5_{rank:02d}_camera_{pub}.png';fig.savefig(AUDIT/name,dpi=180);plt.close(fig)
        attr=dict(audit_id=rank,dev=pub,selection_reason=reason,figure=name,direction_labels='|'.join(sorted(directions[ci])),direction_wildcard='其他' in directions[ci],
            n_camera_road_features=len(choices[ci]),road_fallback=bool(fallback[ci]),nearest_road_distance_m=minimum[ci],lon=float(row.lon),lat=float(row.lat))
        attr.update(camera.loc[pub].to_dict())
        for filt in ['main','G1','G2','G3']:
            p=frames['camera'].query('date==@day and dev==@pub and filter==@filt').iloc[0]
            for field in ['expected_event','captured_event','expected_control','captured_control','relative_capture']:attr[filt+'_'+field]=p[field]
            attr[filt+'_event_retained_share']=ratio(p.expected_event,mainrows.loc[pub,'expected_event']).item()
            attr[filt+'_control_retained_share']=ratio(p.expected_control,mainrows.loc[pub,'expected_control']).item()
        attributes.append(attr)
    pd.DataFrame(attributes).to_csv(AUDIT/'G5_audit_attributes.csv',index=False,encoding='utf-8-sig',float_format='%.12g')
    (AUDIT/'README_internal.md').write_text('仅内部几何审查。16台按冻结规则选定；图中仅道路、卡口、方向箭头与候选经过密度，没有单车轨迹或车辆标识。所有视觉判读留给审阅者；A-G4目前未判定。左右密度分别为八日合计和单日，不能直接比较色深作为交通恢复。坐标以卡口为原点，显示±250m；精确位置不得移入公开目录。\n',encoding='utf-8')
    return dict(figures=16,attributes=16,no_visual_verdict=True,audit_camera_ids=[int(cameras.iloc[i].dev_public) for i in selected])


def run():
    start=now();tick=time.monotonic()
    for p in [ENV,PRIVATE,PUBLIC,AUDIT]:p.mkdir(parents=True,exist_ok=True)
    protocol=ENV/'geometry_protocol_v8.json'
    if not protocol.exists():raise RuntimeError('geometry_protocol_not_frozen')
    protocol_sha=hashlib.sha256(protocol.read_bytes()).hexdigest()
    write_json(dict(start=start,status='running',complete=False,protocol_sha256=protocol_sha),ENV/'geometry_execution_v8.json')
    cameras=load_cameras();roads,road_tree,choices,fallback,minimum,road_info=load_roads(cameras)
    print(json.dumps(dict(at=now(),stage='OSM_loaded',**road_info)),flush=True)
    points,directions,build_info=build_passages(cameras,roads,road_tree,choices)
    full,h11=counts(points,len(cameras));np.savez_compressed(PRIVATE/'geometry_counts_v8.npz',all_day=full,h11=h11,dates=np.asarray(DATES),filters=np.asarray(FILTERS),camera_ids=cameras.dev_public.to_numpy())
    frames,accept,concordance,group_masks,g4_cache=summarise(cameras,points,full,h11,road_info,choices)
    audit=make_audit(cameras,points,directions,roads,choices,fallback,minimum,frames,group_masks,g4_cache)
    methods='''# v8 几何敏感性

本轮为审阅后有界核查。主329台由v7八日对照选定，60m、180s及原线段/300s去重不变；G1–G3均是原保留expected候选的后置筛选，事件不重选卡口。每台方向集按八日AVI标签占比≥5%，其他为合格时的通配；方位角由两端WGS84点计算真北顺时针方向，边界同时属于两侧。GPS航向仅交叉核对。

同路使用冻结OSM：卡口30m内全部feature，空时80m内最近feature；经过投影点的最近feature须相同，或非空同名且同fclass。OSM无候选的卡口表示同路不可判定，不能读作零交通。G3为方向且同路。未改变坐标，也没有解除v6校准失败、S2/S3历史限制。

7/25同时对事件和八日对照的经过时刻、AVI时刻匹配11–23时；全日线段与去重在前。G0/G4两组保持主expected≥10的报告资格，S*相对比另须正control cap。各G另外列按其event expected≥10的失效子组及所有选定失效卡口合计，event资格是报告条件，不是329台选卡条件。S*各G相对捕获用相同筛选后的control池化率作分母；等卡口中位与经过池化比是不同加权统计量。网络c_stable按记录/公里和同星期基线计算，观察单位、分母与可匹配子网络又不同，不能互当验证。

500次卡口簇区间条件于固定329选集和各G观测到的资格集合；不在重抽中重选。control或event无expected以及control cap为0的相对比为NA，不补0。失效组池化捕获分母为该G下event expected≥10的设备expected合计，另有所有选定失败设备合计以展示暴露筛选。

G4每卡口为event距离中位减匹配control距离中位，再组内等卡口取中位；40–60m占比按组内所有经过池化。G5按冻结expected/偏移排名只出16张内部图，没有自动视觉判读，A-G4须由审阅者完成。图内八日灰密度与单日彩色密度不是同一曝光长度，不能直接比较色深。

全天零AVI记录时captured=0是机械结果；几何核查针对expected是否可能来自平行道路。即便数值验收达到，也不识别物理失效原因，不支持未覆盖设备或日期的外推。
'''
    (PUBLIC/'G_METHODS_v8.md').write_text(methods,encoding='utf-8')
    write_json(dict(start=start,end=now(),seconds=time.monotonic()-tick,complete=True,status='complete',
        command=_release_path('path_035'),
        seed=SEED,protocol_sha256=protocol_sha,source_OSM_only=True,key_reads=False,raw_AVI_reads=False,workbook_reads=False,old_outputs_modified=False,
        main_selected=329,road_info=road_info,build_info=build_info,concordance=concordance,audit=audit,
        rows={k:len(v) for k,v in frames.items()},acceptance=accept,
        initial_preflight_shell_exit=1,initial_preflight_shell_reason='nested shell quotation; no Python analysis started',
        visual_judgment_pending=True),ENV/'geometry_execution_v8.json')
    print(json.dumps(clean(dict(complete=True,seconds=time.monotonic()-tick,acceptance=accept)),ensure_ascii=False),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--synthetic',action='store_true');args=parser.parse_args()
    if args.synthetic:
        checks=dict(north=bool(direction_compatible([0,45,315],{'南往北'}).all()),south=bool(direction_compatible([135,180,225],{'北往南'}).all()),
            boundary_both=bool(direction_compatible([45],{'西向东'})[0] and direction_compatible([45],{'南往北'})[0]),
            wildcard=bool(direction_compatible([0,90,180,270],{'其他'}).all()),empty_set=bool(not direction_compatible([90],set())[0]),
            mismatch=bool(not direction_compatible([270],{'西向东'})[0]))
        ENV.mkdir(parents=True,exist_ok=True);write_json(dict(at=now(),checks=checks,all_passed=all(checks.values()),effects=False),ENV/'geometry_synthetic_v8.json')
        assert all(checks.values());print(json.dumps(checks))
    else:
        try:run()
        except Exception as error:
            existing=json.loads((ENV/'geometry_execution_v8.json').read_text(encoding='utf-8')) if (ENV/'geometry_execution_v8.json').exists() else {}
            existing.update(complete=False,status='failed',failed_at=now(),error_type=type(error).__name__,error_code=str(error) if str(error) in ['v7_main_count_concordance_failed','geometry_protocol_not_frozen','OSM_begin_fingerprint_not_present'] else 'internal_execution_failure')
            write_json(existing,ENV/'geometry_execution_v8.json')
            raise
