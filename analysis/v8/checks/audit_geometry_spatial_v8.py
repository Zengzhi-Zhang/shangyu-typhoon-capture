# -*- coding: utf-8 -*-
"""Independent cached-passage geometry aggregation. NoGPS/sourceOSM rereads.

No G5 image is opened and no human road/parallel-route verdict is assigned.
"""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[3]), str(_ReleasePath(__file__).resolve().parents[1])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,time
import numpy as np,pandas as pd
from pyproj import Transformer
import geopandas as gpd
import shapely
from shapely.strtree import STRtree

R=Path(_release_path('v8_root'));V1=R.parent;I=R/'01_internal';E=R/'00_env'
CONTROL=pd.date_range('2021-07-12','2021-07-19').strftime('%Y-%m-%d').tolist()
EVENT=pd.date_range('2021-07-25','2021-07-28').strftime('%Y-%m-%d').tolist();DATES=CONTROL+EVENT;FILTERS=['main','G1','G2','G3']
def read(p,**kw):return pd.read_csv(p,encoding='utf-8-sig',**kw)
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def close(a,b):return bool(np.allclose(a,b,atol=2e-7,rtol=5e-10,equal_nan=True))
def div(a,b):return np.divide(a,b,out=np.full(np.broadcast_shapes(np.shape(a),np.shape(b)),np.nan),where=np.asarray(b)>0)
def quantiles(x):
    x=np.asarray(x,float);x=x[np.isfinite(x)];return np.quantile(x,[.25,.5,.75]) if len(x) else np.full(3,np.nan)
def direction(b,labels):
    if '其他' in labels:return np.ones(len(b),bool)
    return (('北往南' in labels)&(b>=135)&(b<=225))|(('南往北' in labels)&((b<=45)|(b>=315)))|(('西向东' in labels)&(b>=45)&(b<=135))|(('东向西' in labels)&(b>=225)&(b<=315))
def cube(points,nc):
    out=np.zeros((4,12,nc,2),np.int64);h11=np.zeros_like(out)
    index=pd.MultiIndex.from_product([DATES,range(nc)],names=['date','camera_i'])
    for fi,filt in enumerate(FILTERS):
        p=points if filt=='main' else points[points[filt].eq(1)]
        g=p.groupby(['date','camera_i']).agg(E=('captured','size'),C=('captured','sum')).reindex(index,fill_value=0)
        out[fi]=g.to_numpy(np.int64).reshape(12,nc,2)
        g=p[p.sec.ge(39600)].groupby(['date','camera_i']).agg(E=('captured_h11','size'),C=('captured_h11','sum')).reindex(index,fill_value=0)
        h11[fi]=g.to_numpy(np.int64).reshape(12,nc,2)
    return out,h11

def main():
    tick=time.monotonic();checks={};execution=load(E/'geometry_execution_v8.json')
    if not execution.get('complete'):raise RuntimeError('Geometry outputs must be complete before audit')
    paths=[I/'geometry_passages_v8.parquet',I/'geometry_counts_v8.npz',E/'geometry_protocol_v8.json',
        *sorted((R/'02_geometry').glob('*')),*sorted(I.glob('geometry_*_internal_v8.csv'))]
    before={str(p):sha(p) for p in paths if p.is_file()}
    data=np.load(I/'geometry_counts_v8.npz',allow_pickle=False);ids=data['camera_ids'];nc=len(ids)
    points=pd.read_parquet(I/'geometry_passages_v8.parquet')
    checks['frozen329_unique_main']=nc==329 and len(set(ids))==329
    checks['exact8controls_4events_4filters']=data['dates'].tolist()==DATES and data['filters'].tolist()==FILTERS
    selected=read(V1/'formal_v7/01_internal/capture_selection_internal_v7.csv')
    expected_ids=np.sort(selected.loc[selected.variant.eq('main_R60_cap03')&selected.selected.eq(True),'dev'].to_numpy())
    checks['329_exact_v7_control_selected_IDs']=np.array_equal(ids,expected_ids)
    checks['candidate_radius_and_seconds_finite']=points.distance_m.between(0,60).all() and points.sec.ge(0).all() and points.sec.lt(86400).all() and np.isfinite(points.bearing).all()
    checks['already_deduped_before_all_filters']=points.sort_values(['vehicle_i','date','camera_i','sec']).groupby(['vehicle_i','date','camera_i']).sec.diff().dropna().gt(300).all()
    dirs=load(I/'geometry_directions_v8.json');g1=np.zeros(len(points),bool)
    for ci,p in points.groupby('camera_i'):g1[p.index]=direction(p.bearing.to_numpy(),set(dirs[str(ci)]))
    checks['G1_every_candidate_direction_predicate']=np.array_equal(g1,points.G1.to_numpy(bool))
    checks['direction_boundary_belongs_both_adjacent_sectors']=all(direction(np.array([b]),{x})[0] and direction(np.array([b]),{y})[0] for b,x,y in [(45,'南往北','西向东'),(135,'西向东','北往南'),(225,'北往南','东向西'),(315,'东向西','南往北')])
    checks['wildcard_and_empty_set']=direction(np.array([0,90,180,270]),{'其他'}).all() and not direction(np.array([90]),set()).any()
    checks['G3_exact_G1_AND_known_true_G2']=points.G3.eq(points.G1&points.G2.eq(1)).all()
    # All road checks use the newly created projected cache, never sourceOSM.
    if execution['road_info']['available']:
        roads=gpd.read_parquet(I/'geometry_roads_projected_v8.parquet');tree=STRtree(roads.geometry.to_numpy())
        attrs=read(V1/'01_panels/device_attributes.csv').sort_values('dev').reset_index(drop=True).iloc[ids.astype(int)-1]
        xy=np.column_stack(Transformer.from_crs(4326,32651,always_xy=True).transform(attrs.lon.to_numpy(),attrs.lat.to_numpy()))
        choices=[]
        for x,y in xy:
            point=shapely.Point(x,y);near=tree.query(point.buffer(30));near=np.array([int(j) for j in near if roads.geometry.iloc[j].distance(point)<=30],int)
            if not len(near):
                j=int(tree.nearest(point));distance=roads.geometry.iloc[j].distance(point)
                if distance<=80:
                    candidate=tree.query(point.buffer(min(distance+1e-7,80.0000001)));near=np.array([int(j) for j in candidate if abs(roads.geometry.iloc[j].distance(point)-distance)<=1e-7],int)
            choices.append(set(near))
        name=roads.name_norm.to_numpy();fclass=roads.fclass_norm.to_numpy();same=np.full(len(points),-1,np.int8)
        for ci,p in points.groupby('camera_i'):
            allowed=choices[int(ci)]
            if not allowed:continue
            pairs={(name[j],fclass[j]) for j in allowed if name[j]!=''}
            same[p.index]=[int(int(j) in allowed or (name[j]!='' and (name[j],fclass[j]) in pairs)) for j in p.road_i.to_numpy(int)]
        checks['G2_every_candidate_30m_or80m_samefeature_or_name_fclass']=np.array_equal(same,points.G2.to_numpy(np.int8))
        checks['G2_unavailable_cameras_marked_unknown']=all(points.loc[points.camera_i.eq(ci),'G2'].eq(-1).all() for ci,allowed in enumerate(choices) if not allowed)
    full,h11=cube(points,nc)
    checks['all_candidate_aggregates_exact_full_and_h11_cube']=np.array_equal(full,data['all_day']) and np.array_equal(h11,data['h11'])
    checks['filters_are_postdedup_subsets_not_new_passages']=(full[1:,:,:,0]<=full[0,:,:,0]).all() and (h11[1:,:,:,0]<=h11[0,:,:,0]).all()
    checks['captured_never_above_expected']=(full[...,1]<=full[...,0]).all() and (h11[...,1]<=h11[...,0]).all()
    states=read(V1/'formal_v7/01_internal/device_state_internal_v7.csv').set_index(['dev_public','date'])
    attrs=read(V1/'01_panels/device_attributes.csv').sort_values('dev').reset_index(drop=True).iloc[ids.astype(int)-1];stable=attrs.in_Sstar.eq(1).to_numpy()
    g0=read(I/'geometry_G0_internal_v8.csv').set_index(['date','group']);g4=read(I/'geometry_G4_internal_v8.csv').set_index(['date','group'])
    summary=read(I/'geometry_G123_internal_v8.csv').set_index(['date','filter']);shares=read(I/'geometry_shares_internal_v8.csv').set_index(['date','filter','group']);boots=read(I/'geometry_bootstrap_internal_v8.csv')
    rng=np.random.default_rng(20261005);computed={};shift_stats={}
    for date in EVENT:
        hm=date==EVENT[0];counts=h11 if hm else full;control=counts[:,:8].sum(1);event=counts[:,DATES.index(date)]
        q=states.reindex(pd.MultiIndex.from_arrays([ids,[date]*nc]));failed=q.A1_failed.to_numpy(bool)
        relative=div(div(event[0,:,1],event[0,:,0]),div(control[0,:,1],control[0,:,0]))
        groups={'A1_failed':failed&(event[0,:,0]>=10)&(control[0,:,0]>0),'Sstar':stable&(event[0,:,0]>=10)&np.isfinite(relative)&(control[0,:,1]>0)}
        cp=points[points.date.isin(CONTROL)&(points.sec.ge(39600) if hm else np.ones(len(points),bool))]
        ep=points[points.date.eq(date)&(points.sec.ge(39600) if hm else np.ones(len(points),bool))]
        cm=cp.groupby('camera_i').distance_m.median().reindex(range(nc)).to_numpy();em=ep.groupby('camera_i').distance_m.median().reindex(range(nc)).to_numpy();shift=em-cm
        for group,mask in groups.items():
            exposure=div(event[0,:,0],control[0,:,0]/8);q25,med,q75=quantiles(exposure[mask]);ev=event[0,mask].sum(0);ctrl=control[0,mask].sum(0)
            pool=div(ev[0],ctrl[0]/8).item();poolcap=div(div(ev[1],ev[0]),div(ctrl[1],ctrl[0])).item();equalmed=quantiles(relative[mask])[1]
            row=g0.loc[date,group]
            checks[date+'_'+group+'_G0_all_denominators_and_statistics']=close([row.n_devices,row.exposure_median,row.exposure_q25,row.exposure_q75,row.exposure_pooled,row.event_expected,row.event_captured,row.control_expected,row.control_captured,row.pooled_relative_capture,row.equal_camera_relative_median],[mask.sum(),med,q25,q75,pool,*ev,*ctrl,poolcap,equalmed])
            q25,med,q75=quantiles(shift[mask]);c=cp[cp.camera_i.isin(np.flatnonzero(mask))];e=ep[ep.camera_i.isin(np.flatnonzero(mask))]
            ct=c.distance_m.between(40,60).mean();et=e.distance_m.between(40,60).mean();row=g4.loc[date,group]
            checks[date+'_'+group+'_G4_median_camera_shift_and_pooled_40_60']=close([row.n_devices,row.n_valid_distance_shifts,row.shift_median_m,row.shift_q25_m,row.shift_q75_m,row.control_40_60_share,row.event_40_60_share],[mask.sum(),np.isfinite(shift[mask]).sum(),med,q25,q75,ct,et])
            shift_stats[date,group]=med
        for fi,filt in enumerate(FILTERS):
            e=event[fi];c=control[fi];rel=div(div(e[:,1],e[:,0]),div(c[:,1],c[:,0]));ff=failed&(e[:,0]>=10);ss=stable&(e[:,0]>=10)&(c[:,0]>0)&(c[:,1]>0)&np.isfinite(rel)
            failtotal=e[ff].sum(0);failall=e[failed].sum(0);q25,med,q75=quantiles(rel[ss]);row=summary.loc[date,filt]
            if row.available:
                checks[date+'_'+filt+'_G123_perG_eligible_and_pooled_denominators']=close([row.n_selected,row.n_failed_selected,row.n_failed_event_ge10,row.failed_all_expected,row.failed_all_captured,row.failed_ge10_expected,row.failed_ge10_captured,row.failed_ge10_cap,row.n_Sstar_comparable,row.Sstar_relative_median,row.Sstar_relative_q25,row.Sstar_relative_q75],[329,failed.sum(),ff.sum(),*failall,*failtotal,div(failtotal[1],failtotal[0]).item(),ss.sum(),med,q25,q75])
            values=rel[ss];draw=np.median(rng.choice(values,(500,len(values)),replace=True),axis=1) if len(values) else np.full(500,np.nan)
            source=boots[boots.date.eq(date)&boots['filter'].eq(filt)].sort_values('replicate').Sstar_relative_median.to_numpy()
            checks[date+'_'+filt+'_all500_conditional_camera_draws']=close(draw,source)
            if np.isfinite(draw).any():checks[date+'_'+filt+'_camera_percentileCI']=close([row.camera_ci_lo,row.camera_ci_hi],np.quantile(draw[np.isfinite(draw)],[.025,.975]))
            for group,mask in groups.items():
                sh=shares.loc[date,filt,group]
                if row.available:checks[date+'_'+filt+'_'+group+'_shares_use_fixed_main_group']=close([sh.main_event_expected,sh.filtered_event_expected,sh.event_retained_share,sh.main_control_expected,sh.filtered_control_expected,sh.control_retained_share],[event[0,mask,0].sum(),e[mask,0].sum(),div(e[mask,0].sum(),event[0,mask,0].sum()).item(),control[0,mask,0].sum(),c[mask,0].sum(),div(c[mask,0].sum(),control[0,mask,0].sum()).item()])
            computed[date,filt]=dict(available=bool(row.available),n_failed=int(ff.sum()),pooled_rate=div(failtotal[1],failtotal[0]).item(),Sstar_median=med,n_Sstar=int(ss.sum()))
    acc=load(R/'02_geometry/G_acceptance_v8.json');main=computed['2021-07-26','G3']
    checks['A_G1_independent_count_and_pooled_rate']=acc['A_G1']['reached']==bool(main['available'] and main['n_failed']>=40 and main['pooled_rate']<=.02) and close([acc['A_G1']['n_failed_event_ge10'],acc['A_G1']['pooled_capture_rate']],[main['n_failed'],main['pooled_rate']])
    checks['A_G2_independent_G3_Sstar_median']=acc['A_G2']['reached']==bool(main['available'] and .9<=main['Sstar_median']<=1.05) and close([acc['A_G2']['Sstar_relative_median']],[main['Sstar_median']])
    checks['A_G3_independent_median_of_camera_shifts']=acc['A_G3']['reached']==bool(shift_stats['2021-07-26','A1_failed']<=shift_stats['2021-07-26','Sstar']+10) and close([acc['A_G3']['failed_median_shift_m'],acc['A_G3']['Sstar_median_shift_m']],[shift_stats['2021-07-26','A1_failed'],shift_stats['2021-07-26','Sstar']])
    checks['A_G4_still_pending_no_visual_verdict']=acc['A_G4']['reached'] is None and not acc['A_G4']['automatic_visual_verdict']
    checks['no_audited_geometry_file_changed']=before=={p:sha(p) for p in before}
    checks={k:bool(v) for k,v in checks.items()}
    report=dict(ended=datetime.now(timezone.utc).isoformat(),seconds=time.monotonic()-tick,all_passed=all(checks.values()),n_checks=len(checks),checks=checks,
        A_G1_G2_G3=acc,G0_0726=g0.loc['2021-07-26'].reset_index().to_dict('records'),G4_0726=g4.loc['2021-07-26'].reset_index().to_dict('records'),
        source_GPS_OSM_reads=False,key_reads=False,scientific_outputs_modified=False,G5_images_opened=False,human_visual_verdict=False,
        scope='All-candidate reconstruction and cached-only road predicates; independent G0/G123/G4 aggregation and500draws; no raw/cacheGPS rescan and no sourceOSM read',input_sha256=before)
    # pandas conversion keeps NaN diagnostics as strictJSON null.
    for key in ['G0_0726','G4_0726']:report[key]=json.loads(pd.DataFrame(report[key]).to_json(orient='records'))
    (E/'geometry_spatial_independent_audit_v8.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps(dict(all_passed=report['all_passed'],n_checks=len(checks),seconds=report['seconds'],failed=[k for k,v in checks.items() if not v])))
    if not report['all_passed']:raise AssertionError('Independent spatial geometry audit failed')

if __name__=='__main__':main()
