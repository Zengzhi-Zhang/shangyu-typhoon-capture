# -*- coding: utf-8 -*-
"""Frozen v8 W1 vehicle baseline sensitivity; local caches only."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[2]), str(_ReleasePath(__file__).resolve().parents[0])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,time,argparse
import numpy as np,pandas as pd
from scipy import sparse

ROOT=Path(_release_path('v8_root')); OLD=ROOT.parent; SEED=20261005
GEO=['local_zheD','zhejiang_other','other_province']
DATES=['2021-07-07','2021-07-14','2021-07-21','2021-07-28']
METRICS=['rP','rm','rN']
PROTOCOL=ROOT/'00_env/recovery_component_protocol_v8.json'

def sig(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for x in iter(lambda:f.read(4*1024*1024),b''):h.update(x)
    s=p.stat();return dict(sha256=h.hexdigest(),bytes=s.st_size,mtime_ns=s.st_mtime_ns)
def clean(v):
    if isinstance(v,dict):return {str(k):clean(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)):return [clean(x) for x in v]
    if isinstance(v,np.generic):return clean(v.item())
    if isinstance(v,float) and not np.isfinite(v):return None
    return v
def put(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(clean(obj),ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def save(f,rel,internal=False):
    p=ROOT/rel;p.parent.mkdir(parents=True,exist_ok=True)
    if p.suffix=='.parquet':f.to_parquet(p,index=False)
    else:
        out=f.copy()
        if not internal:
            for c in out:
                if c.startswith('plates_'):
                    out[c]=out[c].map(lambda v:'<10' if pd.notna(v) and v<10 else v)
        out.to_csv(p,index=False,encoding='utf-8-sig',float_format='%.12g' if internal else '%.4f',na_rep='NA')
def div(a,b):return np.divide(a,b,out=np.full(np.broadcast_shapes(np.shape(a),np.shape(b)),np.nan),where=np.asarray(b)>0)
def ci(x):
    x=np.asarray(x);x=x[np.isfinite(x)]
    return np.quantile(x,[.025,.975]) if len(x) else [np.nan,np.nan]
def metrics(N,P,refs):
    n,p=N[3],P[3];bn,bp=N[refs].mean(axis=0),P[refs].mean(axis=0)
    bm=div(N[refs],P[refs]).mean(axis=0)
    return dict(rP=div(p,bp),rm=div(div(n,p),bm),rN=div(n,bn))

def main():
    start=datetime.now(timezone.utc).isoformat();tick=time.perf_counter()
    frozen=json.loads(PROTOCOL.read_text(encoding='utf-8'))
    assert frozen['seed']==SEED and (ROOT/'00_env/protocol_frozen_v8.json').exists()
    inputs=['01_panels/plate_master.parquet',*[f'01_panels/plate_day/{d}.parquet' for d in DATES],
        'formal_v3/04_m3_vehicles/m3_daily_by_group.csv',
        'formal_v7/03_taxi_probe/T28_wednesday_sensitivity_v7.csv',
        'formal_v7/01_internal/T28_wednesday_sensitivity_internal_v7.csv']
    before={rel:sig(OLD/rel) for rel in inputs};proto=sig(PROTOCOL);checks={}
    pm=pd.read_parquet(OLD/'01_panels/plate_master.parquet',columns=['ph','cat'])
    readable=pm.cat.ne('unreadable').to_numpy();master=pm.loc[readable].reset_index(drop=True)
    n=len(master);index=pd.Index(master.ph);codes=pd.Categorical(master.cat,categories=GEO).codes
    assert index.is_unique and (codes>=0).all()
    rr=[];cc=[];vv=[]
    for j,d in enumerate(DATES):
        day=pd.read_parquet(OLD/f'01_panels/plate_day/{d}.parquet',columns=['ph','n_stable'])
        assert day.ph.is_unique
        positions=index.get_indexer(day.ph);keep=(positions>=0)&day.n_stable.gt(0).to_numpy()
        idx=positions[keep];rr.append(j*3+codes[idx].astype('int32'));cc.append(idx.astype('int32'));vv.append(day.n_stable.to_numpy()[keep].astype(float))
        print('W1 vehicle local cache loaded',d,'rows',len(day),flush=True)
    N=sparse.csr_matrix((np.concatenate(vv),(np.concatenate(rr),np.concatenate(cc))),shape=(12,n))
    P=sparse.csr_matrix((np.ones(N.nnz,dtype='int8'),N.indices,N.indptr),shape=N.shape,copy=False)
    plainN=np.asarray(N.sum(axis=1)).reshape(4,3);plainP=np.asarray(P.sum(axis=1)).reshape(4,3)
    refs={'B1':[0,1,2],'B1w':[1]};point={k:metrics(plainN,plainP,v) for k,v in refs.items()}
    draws={k:{m:np.empty((200,3)) for m in METRICS} for k in refs}
    rng=np.random.default_rng(SEED);prob=np.full(n,1/n)
    for rep in range(200):
        w=rng.multinomial(n,prob);bn=N.dot(w).reshape(4,3);bp=P.dot(w).reshape(4,3)
        for baseline,ix in refs.items():
            out=metrics(bn,bp,ix)
            for m in METRICS:draws[baseline][m][rep]=out[m]
        if (rep+1)%25==0:print('W1 vehicle bootstrap',rep+1,'of200',flush=True)
    existing=pd.read_csv(OLD/'formal_v3/04_m3_vehicles/m3_daily_by_group.csv')
    existing=existing[existing.date.eq('2021-07-28')&existing.grp.isin(GEO)].set_index('grp')
    rows=[];boots=[];changes=[]
    for baseline,ix in refs.items():
        for m in METRICS:
            for g,group in enumerate(GEO+['local_minus_other_province']):
                value=point[baseline][m][g] if g<3 else point[baseline][m][0]-point[baseline][m][2]
                samples=draws[baseline][m][:,g] if g<3 else draws[baseline][m][:,0]-draws[baseline][m][:,2]
                lo,hi=ci(samples)
                row=dict(date='2021-07-28',baseline=baseline,group=group,metric=m,value=value,ci_lo=lo,ci_hi=hi,
                    bootstrap=200,bootstrap_valid=int(np.isfinite(samples).sum()),baseline_dates=';'.join(DATES[j] for j in ix),
                    interval_scope='200 readable-master vehicle clusters; same weights across dates, groups and baseline variants; frozen Sstar; percentile95; no set-selection/baseline-choice uncertainty',
                    source='01_panels/plate_master.parquet + four plate_day n_stable caches; frozen v3 margin definitions')
                if g<3:
                    row.update(plates_target=plainP[3,g],plates_baseline=float(plainP[ix,g].mean()),records_target=plainN[3,g],records_baseline=float(plainN[ix,g].mean()),mean_passes_baseline=float(div(plainN[ix,g],plainP[ix,g]).mean()))
                rows.append(row)
                boots.append(pd.DataFrame(dict(baseline=baseline,group=group,metric=m,rep=np.arange(1,201),estimate=samples)))
                if baseline=='B1' and g<3:
                    checks['B1point:'+group+':'+m]=bool(abs(value-existing.loc[group,m])<=.000051)
                    checks['B1CI:'+group+':'+m]=bool(np.allclose([lo,hi],existing.loc[group,['ci_'+m+'_lo','ci_'+m+'_hi']].to_numpy(float),atol=.000051,rtol=0))
            for g,group in enumerate(GEO+['local_minus_other_province']):
                change=(draws['B1w'][m][:,g]-draws['B1'][m][:,g] if g<3 else
                    (draws['B1w'][m][:,0]-draws['B1w'][m][:,2])-(draws['B1'][m][:,0]-draws['B1'][m][:,2]))
                value=(point['B1w'][m][g]-point['B1'][m][g] if g<3 else
                    (point['B1w'][m][0]-point['B1w'][m][2])-(point['B1'][m][0]-point['B1'][m][2]))
                lo,hi=ci(change)
                if baseline=='B1':changes.append(dict(date='2021-07-28',group=group,metric=m,B1w_minus_B1=value,ci_lo=lo,ci_hi=hi,bootstrap=200,scope='Paired descriptive baseline-change contrast; same200 vehicle weights, not difference of endpoint CIs'))
    frame=pd.DataFrame(rows);save(frame,'03_baseline/W1_vehicle_margins_v8.csv');save(frame,'01_internal/recovery_vehicle_points_v8.csv',True)
    save(pd.DataFrame(changes),'03_baseline/W1_vehicle_baseline_change_v8.csv');save(pd.concat(boots,ignore_index=True),'01_internal/recovery_vehicle_bootstrap_v8.parquet',True)
    probe=pd.read_csv(OLD/'formal_v7/01_internal/T28_wednesday_sensitivity_internal_v7.csv')
    probe['baseline']=probe.baseline_variant.map({'B_PROBE':'B1','B_PROBE_drop_0707_0721':'B1w'})
    probe['source']='formal_v7/01_internal/T28_wednesday_sensitivity_internal_v7.csv'
    probe['baseline_label_scope']='Device scenario labels; probe uses own existing B_PROBE sensitivity, not a redefinition of device baseline'
    save(probe,'03_baseline/W1_probe_v8.csv');save(probe,'01_internal/recovery_probe_reference_v8.csv',True)
    checks['24_vehicle_cells']=len(frame)==24
    checks['4800_vehicle_draw_rows']=sum(len(f) for f in boots)==4800
    checks['B1w_single_day_identity']=bool(np.allclose(draws['B1w']['rP']*draws['B1w']['rm'],draws['B1w']['rN'],atol=1e-12,rtol=1e-12))
    checks['probe_two_prespecified_rows']=len(probe)==2 and set(probe.baseline)=={'B1','B1w'}
    after={rel:sig(OLD/rel) for rel in inputs};checks['all_old_inputs_unchanged']=before==after;checks['component_protocol_unchanged']=sig(PROTOCOL)==proto
    report=dict(started_utc=start,finished_utc=datetime.now(timezone.utc).isoformat(),elapsed_seconds=time.perf_counter()-tick,status='complete' if all(checks.values()) else 'integrity_failed',seed=SEED,
        checks=checks,checks_passed=all(checks.values()),n_readable_master=n,n_unreadable_master=int((~readable).sum()),bootstrap=200,input_before=before,input_after=after,component_protocol=proto,
        source_reads=False,key_reads=False,vehicle_rows=24,retained_bootstrap_rows=4800,probe='Existing v7 reference only; no new draws',main_results=frame.to_dict('records'))
    put(ROOT/'00_env/recovery_vehicle_execution_v8.json',report)
    print(json.dumps(clean(dict(status=report['status'],seconds=report['elapsed_seconds'],n_readable_master=n,checks=checks)),ensure_ascii=False),flush=True)
    if not all(checks.values()):raise RuntimeError('W1 vehicle integrity checks failed')
if __name__=='__main__':main()
