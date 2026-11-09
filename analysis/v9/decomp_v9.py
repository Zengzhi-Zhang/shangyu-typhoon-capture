# -*- coding: utf-8 -*-
"""Post-review T38/T39 only. Frozen local inputs; no raw source/key imports."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[2]), str(_ReleasePath(__file__).resolve().parents[0])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,time,sys
import numpy as np
import pandas as pd

ROOT=Path(_release_path('project_root'));OUT=_ReleasePath(_release_path('v9_output_root'));ENV=OUT/'00_env';INTERNAL=OUT/'01_internal'
SEED=20261005;NBOOT=500
EVENT=pd.date_range('2021-07-25','2021-08-02').strftime('%Y-%m-%d').tolist()
B1=[x for x in pd.date_range('2021-07-05','2021-07-21').strftime('%Y-%m-%d') if x not in ['2021-07-08','2021-07-10']]
THETA=[.80,.85,.90,.95]
METRICS=['R_A100','R_A200','R_H','Delta_thr','Delta_scr','Delta_tot','n_O','w_O','R_O']
INPUTS={
 'state':ROOT/'formal_v7/02_device_state/device_state_v7.csv',
 'family':ROOT/'formal_v7/07_consequences/T37_estimator_family_v7.csv',
 'day':ROOT/'01_panels/device_day.csv',
 'hour':ROOT/'01_panels/device_hour.csv',
 'attrs':ROOT/'01_panels/device_attributes.csv',
}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p,**kw):return pd.read_csv(p,encoding='utf-8-sig',**kw)
def write_json(p,x):
    Path(p).parent.mkdir(parents=True,exist_ok=True)
    Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def div(a,b):
    a,b=np.broadcast_arrays(np.asarray(a,dtype=float),np.asarray(b,dtype=float))
    return np.divide(a,b,out=np.full(a.shape,np.nan),where=np.isfinite(b)&(b>0))
def classify(x,ro,rh):
    x,ro,rh=np.broadcast_arrays(x,ro,rh)
    valid=np.isfinite(x)&np.isfinite(ro)&np.isfinite(rh)
    # A is evaluated first, exactly preserving the literal table order.
    return np.where(valid,np.where(x<=ro,'A',np.where(x<=rh,'B','C')),'NA')
def sustained(classes):
    classes=np.asarray(classes)
    return np.where((classes=='C').any(axis=-1),'not_sustained',
        np.where((classes=='A').all(axis=-1),'robust_sustained',
        np.where((classes=='NA').any(axis=-1),'unknown','depends_on_unseen')))
def ci(x):
    x=np.asarray(x,float);x=x[np.isfinite(x)]
    return np.quantile(x,[.025,.975]) if len(x) else np.array([np.nan,np.nan])
def public_csv(df,path,count_cols=()):
    q=df.copy()
    for col in q:
        if col in count_cols:
            q[col]=q[col].map(lambda x:'NA' if pd.isna(x) else '<10' if 0<=x<10 else str(int(np.rint(x))))
        elif pd.api.types.is_float_dtype(q[col]):q[col]=q[col].map(lambda x:'NA' if pd.isna(x) else f'{x:.4f}')
    Path(path).parent.mkdir(parents=True,exist_ok=True);q.to_csv(path,index=False,encoding='utf-8')
def load_data():
    attrs=read(INPUTS['attrs'],usecols=['dev','in_A100','in_A200']).sort_values('dev').reset_index(drop=True)
    attrs['device_id']=np.arange(1,len(attrs)+1)
    a=attrs[attrs.in_A100.eq(1)].copy();names=a.dev.tolist();ids=a.device_id.to_numpy(np.int64)
    flags=a.in_A200.to_numpy(bool);day=read(INPUTS['day']);hour=read(INPUTS['hour'],usecols=['dev','date','hour','n'])
    days=B1+EVENT
    full=day.pivot(index='dev',columns='date',values='n').reindex(index=names,columns=days,fill_value=0).fillna(0)
    dates_hm=[d for d in B1 if pd.Timestamp(d).weekday()==6]+[EVENT[0]]
    hour=hour[hour.date.isin(dates_hm)&hour.hour.between(11,23)]
    partial=hour.groupby(['dev','date']).n.sum().unstack().reindex(index=names,columns=dates_hm,fill_value=0).fillna(0)
    n=np.empty((9,len(a)));b=np.empty_like(n)
    for di,date in enumerate(EVENT):
        pool=[d for d in B1 if pd.Timestamp(d).weekday()==pd.Timestamp(date).weekday()]
        source=partial if di==0 else full
        n[di]=source[date].to_numpy();b[di]=source[pool].mean(axis=1).to_numpy()
    state=read(INPUTS['state'],usecols=['dev','date','n_day','baseline_B1','in_health','hour_matched','in_A100','in_A200'])
    index=pd.MultiIndex.from_product([EVENT,ids],names=['date','dev'])
    state=state.set_index(['date','dev']).reindex(index)
    h=state.in_health.fillna(0).to_numpy().reshape(9,-1).astype(bool)&flags[None,:]
    sd=state.n_day.to_numpy().reshape(9,-1);sb=state.baseline_B1.to_numpy().reshape(9,-1)
    checks={
       'A100_fixed_1287':len(ids)==1287,'A200_fixed_1221':int(flags.sum())==1221,
       'all_A200_event_state_present':bool(np.isfinite(sd[:,flags]).all()),
       'all_A100_only_66_outside_A200':int((~flags).sum())==66,
       'state_n_day_matches_exact_full_or_h11':bool(np.array_equal(sd[:,flags],n[:,flags])),
       'state_B1_sameweekday_matches_exact_panel_reconstruction':bool(np.allclose(sb[:,flags],b[:,flags],atol=1e-7,rtol=1e-11)),
       'health_subset_A200':bool((h<=flags[None,:]).all()),
    }
    diagnostics={'state_B1_max_absolute_difference':float(np.max(np.abs(sb[:,flags]-b[:,flags]))),'B1_dates':B1,
        'baseline_dates_by_event':{d:[v for v in B1 if pd.Timestamp(v).weekday()==pd.Timestamp(d).weekday()] for d in EVENT}}
    if not all(checks.values()):raise AssertionError('Input reconciliation failed: '+repr([k for k,v in checks.items() if not v]))
    return ids,flags,h,n,b,checks,diagnostics

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',action='store_true');args=ap.parse_args()
    if not args.run:raise SystemExit('Formal effects require explicit --run after root freeze/authorization')
    protocol=ENV/'protocol_frozen_v9.json'
    if not protocol.exists():raise RuntimeError('Root frozen protocol is required')
    frozen_sha=sha(protocol);tick=time.monotonic();started=datetime.now(timezone.utc).isoformat()
    for p in [INTERNAL,OUT/'02_decomposition',OUT/'03_breakeven']:p.mkdir(parents=True,exist_ok=True)
    before={k:{'path':str(p),'sha256':sha(p),'size':p.stat().st_size,'mtime_ns':p.stat().st_mtime_ns} for k,p in INPUTS.items()}
    ids,a200,h,n,b,checks,diagnostics=load_data();o=a200[None,:]&~h;nd=len(ids)
    rng=np.random.default_rng(SEED)
    draws=rng.integers(0,nd,size=(NBOOT,nd),dtype=np.int32)
    weights=np.stack([np.bincount(row,minlength=nd) for row in draws]).astype(np.int32)
    np.savez_compressed(INTERNAL/'decomp_device_weights_v9.npz',draw_indices=draws,device_ids=ids,weights=weights,dates=np.array(EVENT),seed=SEED)
    checks['weights_each_total_A100']=bool(np.all(weights.sum(axis=1)==1287))
    checks['ordered_public_device_axis']=bool(np.all(np.diff(ids)>0))
    device_frames=[]
    for di,date in enumerate(EVENT):
        device_frames.append(pd.DataFrame({'dev':ids,'date':date,'n_day':n[di].astype(np.int64),'baseline_B1':b[di],
          'in_A100':1,'in_A200':a200.astype(np.int8),'in_health':h[di].astype(np.int8),'O':o[di].astype(np.int8),'hour_matched':int(di==0)}))
    pd.concat(device_frames,ignore_index=True).to_parquet(INTERNAL/'decomp_device_day_v9.parquet',index=False)
    allw=np.vstack([np.ones(nd),weights]);values=np.empty((NBOOT+1,9,len(METRICS)))
    for di in range(9):
        wn=allw@n[di];wb=allw@b[di];n200=allw@(n[di]*a200);b200=allw@(b[di]*a200)
        nh=allw@(n[di]*h[di]);bh=allw@(b[di]*h[di]);no=allw@(n[di]*o[di]);bo=allw@(b[di]*o[di])
        ra100,ra200,rh=div(wn,wb),div(n200,b200),div(nh,bh)
        values[:,di,:]=np.column_stack([ra100,ra200,rh,ra200-ra100,rh-ra200,rh-ra100,allw@o[di],div(bo,b200),div(no,bo)])
    full=[];point=values[0];boot=values[1:];rows=[]
    for di,date in enumerate(EVENT):
        row={'date':date,'hour_matched':int(di==0),'n_A100':1287,'n_A200':1221,'n_H':int(h[di].sum()),'baseline_dates':';'.join(diagnostics['baseline_dates_by_event'][date])}
        for mi,m in enumerate(METRICS):
            low,high=ci(boot[:,di,mi]);row.update({m:point[di,mi],m+'_ci_lo':low,m+'_ci_hi':high,m+'_n_valid':int(np.isfinite(boot[:,di,mi]).sum())})
        rows.append(row)
        frame=pd.DataFrame(boot[:,di,:],columns=METRICS);frame.insert(0,'replicate',np.arange(1,NBOOT+1));frame.insert(0,'date',date);full.append(frame)
    pd.concat(full,ignore_index=True).to_parquet(INTERNAL/'decomp_bootstrap_v9.parquet',index=False)
    decomp=pd.DataFrame(rows);decomp.to_parquet(INTERNAL/'decomp_points_v9.parquet',index=False)
    public_csv(decomp,OUT/'02_decomposition/T38_decomposition_v9.csv',count_cols=['n_A100','n_A200','n_H','n_O','n_O_ci_lo','n_O_ci_hi'])
    family=read(INPUTS['family']).set_index(['date','estimator']);diffs={}
    for di,date in enumerate(EVENT):
        for m,e in [('R_A100','R_naive'),('R_H','R_health')]:diffs[date+'_'+m]=float(abs(point[di,METRICS.index(m)]-family.loc[(date,e),'R']))
    checks['T38_reproduce']=bool(all(x<5e-5 for x in diffs.values()))
    checks['T38_additive']=bool(np.max(np.abs(values[:,:,3]+values[:,:,4]-values[:,:,5]))<1e-12)
    checks['T38_0726']=bool(f'{point[1,1]:.4f}'=='0.4608' and point[1,6]==228 and f'{point[1,7]:.4f}'=='0.3370')
    checks['T38_0802']=bool(point[8,6]==119 and f'{point[8,7]:.4f}'=='0.2571')
    wh=values[:,:,7];rh=values[:,:,2];ro=values[:,:,8];ra200=values[:,:,1]
    checks['T39_identity']=bool(np.nanmax(np.abs((1-wh)*rh+wh*ro-ra200))<1e-12 and np.nanmax(np.abs((1-wh)*rh+wh*rh-rh))<1e-12)
    xt=np.empty((NBOOT+1,9,4));gg=np.empty_like(xt);classes=np.empty(xt.shape,dtype='<U2');breakeven=[];sustained_rows=[];bframes=[]
    for ti,theta in enumerate(THETA):
        xt[:,:,ti]=div(theta-(1-wh)*rh,wh);gg[:,:,ti]=xt[:,:,ti]-ro
        classes[:,:,ti]=classify(xt[:,:,ti],ro,rh)
        for di,date in enumerate(EVENT):
            valid=classes[1:,di,ti]!='NA';nv=int(valid.sum());xl,xu=ci(xt[1:,di,ti]);gl,gu=ci(gg[1:,di,ti])
            breakeven.append({'date':date,'theta':theta,'hour_matched':int(di==0),'R_A200':ra200[0,di],'R_O':ro[0,di],'R_H':rh[0,di],'w_O':wh[0,di],
              'x_star':xt[0,di,ti],'x_star_ci_lo':xl,'x_star_ci_hi':xu,'g':gg[0,di,ti],'g_ci_lo':gl,'g_ci_hi':gu,'class':classes[0,di,ti],
              'share_A':float(np.mean(classes[1:,di,ti][valid]=='A')) if nv else np.nan,
              'share_B':float(np.mean(classes[1:,di,ti][valid]=='B')) if nv else np.nan,
              'share_C':float(np.mean(classes[1:,di,ti][valid]=='C')) if nv else np.nan,
              'n_valid':nv,'n_invalid':NBOOT-nv,'RO_above_RH_point':bool(ro[0,di]>rh[0,di]),
              'RO_above_RH_bootstrap_n':int(np.sum(ro[1:,di]>rh[1:,di])),'interpretation':'conditional_on_K; post_review_analysis'})
            st=sustained(classes[:,di:,ti]);valids=st[1:]!='unknown';ns=int(valids.sum())
            sustained_rows.append({'start_date':date,'end_date':EVENT[-1],'theta':theta,'n_tail_dates':9-di,'status':st[0],
              'share_robust_sustained':float(np.mean(st[1:][valids]=='robust_sustained')) if ns else np.nan,
              'share_depends_on_unseen':float(np.mean(st[1:][valids]=='depends_on_unseen')) if ns else np.nan,
              'share_not_sustained':float(np.mean(st[1:][valids]=='not_sustained')) if ns else np.nan,'n_valid':ns,'n_invalid':NBOOT-ns})
            bframes.append(pd.DataFrame({'date':date,'theta':theta,'replicate':np.arange(1,NBOOT+1),'x_star':xt[1:,di,ti],'g':gg[1:,di,ti],'class':classes[1:,di,ti],'sustained_from_date':st[1:]}))
    pd.concat(bframes,ignore_index=True).to_parquet(INTERNAL/'decomp_breakeven_bootstrap_v9.parquet',index=False)
    be=pd.DataFrame(breakeven).sort_values(['date','theta']);su=pd.DataFrame(sustained_rows).sort_values(['start_date','theta'])
    be.to_parquet(INTERNAL/'decomp_breakeven_points_v9.parquet',index=False);su.to_parquet(INTERNAL/'decomp_sustained_points_v9.parquet',index=False)
    public_csv(be,OUT/'03_breakeven/T39_breakeven_v9.csv',count_cols=['n_invalid','RO_above_RH_bootstrap_n'])
    public_csv(su,OUT/'03_breakeven/T39_sustained_v9.csv',count_cols=['n_tail_dates','n_invalid'])
    checks['T39_all_36_breakeven_and_36_sustained']=len(be)==36 and len(su)==36
    checks['T39_ABC_fractions_close']=bool(np.allclose(be[['share_A','share_B','share_C']].sum(axis=1),1))
    checks['all_inputs_unchanged']=all(sha(p)==before[k]['sha256'] and p.stat().st_size==before[k]['size'] and p.stat().st_mtime_ns==before[k]['mtime_ns'] for k,p in INPUTS.items())
    checks['root_protocol_unchanged']=sha(protocol)==frozen_sha
    write_json(OUT/'02_decomposition/T38_checks_v9.json',{'checks':checks,'all_passed':all(checks.values()),'comparison_unrounded':'Full-precision recomputation compared with stored T37 points: R_naive is stored to four decimals; R_health retains higher precision. The strict 5e-5 tolerance is applied before v9 display rounding.','reproduce_abs_differences':diffs,
        'T38_additive_max_abs':float(np.max(np.abs(values[:,:,3]+values[:,:,4]-values[:,:,5]))),'T39_identity_max_abs_RO':float(np.nanmax(np.abs((1-wh)*rh+wh*ro-ra200))),
        'T39_identity_max_abs_RH':float(np.nanmax(np.abs((1-wh)*rh+wh*rh-rh)))})
    write_json(ENV/'decomp_execution_v9.json',{'started':started,'ended':datetime.now(timezone.utc).isoformat(),'seconds':time.monotonic()-tick,'command':_release_path('path_045'),
        'python':sys.executable,'seed':SEED,'n_bootstrap':NBOOT,'protocol_sha256':frozen_sha,'input_files':before,'checks':checks,'all_passed':all(checks.values()),'diagnostics':diagnostics,
        'notes':['All scientific calculations use unrounded values; public ratios 4dp, device-count CI displayed as nearest integers.','A-first literal classification; g is not truncated; invalid denominator gives NA.','Fixed observed memberships, shared A100 weights across all dates and metrics; interval excludes baseline-choice/membership uncertainty.']})
    print(json.dumps({'all_passed':all(checks.values()),'checks':checks,'seconds':time.monotonic()-tick,'T38_0726':rows[1],'T38_0802':rows[-1]},ensure_ascii=False,allow_nan=False))
    if not all(checks.values()):raise AssertionError('Prespecified checks not all reached; outputs retained unchanged')
if __name__=='__main__':main()
