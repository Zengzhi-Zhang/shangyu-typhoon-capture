# -*- coding: utf-8 -*-
"""Independent spatial-agent audit of W1 vehicle/W2; local readonly caches."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[3]), str(_ReleasePath(__file__).resolve().parents[1])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,time
import numpy as np,pandas as pd
from scipy.sparse import csr_matrix
R=Path(_release_path('v8_root'));V=R.parent;G=['local_zheD','zhejiang_other','other_province'];D=['2021-07-07','2021-07-14','2021-07-21','2021-07-28']
def read(p,**kw):return pd.read_csv(p,encoding='utf-8-sig',**kw)
def close(a,b,tol=5e-10):return bool(np.allclose(a,b,atol=tol,rtol=5e-10,equal_nan=True))
def div(n,b):return np.divide(n,b,out=np.full(np.broadcast_shapes(np.shape(n),np.shape(b)),np.nan),where=np.asarray(b)>0)
def ci(v):return np.quantile(np.asarray(v)[np.isfinite(v)],[.025,.975])
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def norm(v):return None if pd.isna(v) else v
def main():
    started=time.monotonic();checks={}
    protected=[V/'01_panels/plate_master.parquet',*[V/('01_panels/plate_day/'+d+'.parquet') for d in D],R/'03_baseline/W1_vehicle_margins_v8.csv',R/'03_baseline/W1_vehicle_baseline_change_v8.csv',R/'03_baseline/W2_daily_inputs_v8.csv',R/'03_baseline/W2_recovery_dates_v8.csv']
    before={str(p):sha(p) for p in protected}
    master=pd.read_parquet(protected[0],columns=['ph','cat']);master=master[master.cat.ne('unreadable')].reset_index(drop=True)
    index=pd.Index(master.ph);codes=pd.Categorical(master.cat,categories=G).codes;checks['readable_master_unique_3geographies']=index.is_unique and (codes>=0).all()
    rr=[];cc=[];nn=[]
    for j,date in enumerate(D):
        p=pd.read_parquet(V/('01_panels/plate_day/'+date+'.parquet'),columns=['ph','n_stable'])
        pos=index.get_indexer(p.ph);keep=(pos>=0)&p.n_stable.gt(0).to_numpy()
        rr.extend((j*3+codes[pos[keep]]).tolist());cc.extend(pos[keep].tolist());nn.extend(p.loc[keep,'n_stable'].tolist())
    counts=csr_matrix((np.asarray(nn,float),(rr,cc)),shape=(12,len(index)))
    present=counts.copy();present.data[:]=1.
    N=np.asarray(counts.sum(1)).reshape(4,3);P=np.asarray(present.sum(1)).reshape(4,3)
    def metric(N,P,baseline):
        refs=[0,1,2] if baseline=='B1' else [1]
        return {'rP':div(P[3],P[refs].mean(0)),'rm':div(div(N[3],P[3]),div(N[refs],P[refs]).mean(0)),'rN':div(N[3],N[refs].mean(0))}
    points={b:metric(N,P,b) for b in ['B1','B1w']}
    store={(b,m):np.zeros((200,3)) for b in ['B1','B1w'] for m in ['rP','rm','rN']}
    rng=np.random.default_rng(20261005);prob=np.full(len(index),1/len(index))
    for rep in range(200):
        w=rng.multinomial(len(index),prob);nr=counts.dot(w).reshape(4,3);pr=present.dot(w).reshape(4,3)
        for b in ['B1','B1w']:
            for m,x in metric(nr,pr,b).items():store[b,m][rep]=x
    internal=read(R/'01_internal/recovery_vehicle_points_v8.csv');public=read(R/'03_baseline/W1_vehicle_margins_v8.csv');boots=pd.read_parquet(R/'01_internal/recovery_vehicle_bootstrap_v8.parquet');change=read(R/'03_baseline/W1_vehicle_baseline_change_v8.csv')
    checks['W1_24point_4800draw_12change_rows']=len(internal)==24 and len(public)==24 and len(boots)==4800 and len(change)==12
    for b in ['B1','B1w']:
        for m in ['rP','rm','rN']:
            for k,g in enumerate(G+['local_minus_other_province']):
                expected=store[b,m][:,k] if k<3 else store[b,m][:,0]-store[b,m][:,2]
                value=points[b][m][k] if k<3 else points[b][m][0]-points[b][m][2]
                rows=boots[boots.baseline.eq(b)&boots.metric.eq(m)&boots.group.eq(g)].sort_values('rep')
                s=internal[internal.baseline.eq(b)&internal.metric.eq(m)&internal.group.eq(g)].iloc[0]
                ps=public[public.baseline.eq(b)&public.metric.eq(m)&public.group.eq(g)].iloc[0]
                checks[b+'_'+m+'_'+g+'_all200_master_cluster_draws']=len(rows)==200 and close(rows.estimate,expected)
                checks[b+'_'+m+'_'+g+'_point_CI_reproduced']=close([s.value,s.ci_lo,s.ci_hi],[value,*ci(expected)]) and close([ps.value,ps.ci_lo,ps.ci_hi],[value,*ci(expected)],tol=.000051)
                if b=='B1':
                    delta=store['B1w',m]-store['B1',m];ds=delta[:,k] if k<3 else delta[:,0]-delta[:,2]
                    pt=points['B1w'][m]-points['B1'][m];pv=pt[k] if k<3 else pt[0]-pt[2]
                    z=change[change.metric.eq(m)&change.group.eq(g)].iloc[0]
                    checks[m+'_'+g+'_paired_baseline_change_CI']=close([z.B1w_minus_B1,z.ci_lo,z.ci_hi],[pv,*ci(ds)],tol=.000051)
    checks['B1_rm_mean_daily_m_not_pooled']=close([internal[(internal.baseline=='B1')&(internal.group==g)&(internal.metric=='rm')].iloc[0].mean_passes_baseline for g in G],div(N[:3],P[:3]).mean(0))
    reference=read(R/'01_internal/recovery_probe_reference_v8.csv');oldprobe=read(V/'formal_v7/01_internal/T28_wednesday_sensitivity_internal_v7.csv')
    fields=['c_all','c_stable','q_probe','R_probe','R_probe_ci_lo','R_probe_ci_hi']
    checks['W1_probe_exact_existing_v7_reference']=close(reference[fields],oldprobe[fields]) and reference.baseline.tolist()==['B1','B1w']
    daily=read(R/'03_baseline/W2_daily_inputs_v8.csv');out=read(R/'03_baseline/W2_recovery_dates_v8.csv');family=read(V/'formal_v7/07_consequences/T37_estimator_family_v7.csv').set_index(['date','estimator']);taxi=read(V/'formal_v3/06_m5_bias_correction/m5_visible_bias_v3.csv').set_index('date');device=read(R/'03_baseline/W1_device_estimators_v8.csv').set_index(['baseline','estimator']);probe=reference.set_index('baseline')
    checks['W2_exact216rows_154inputs']=len(out)==216 and len(daily)==154
    checks['W2_8replacement_rows_only']=daily.replaced_0728.sum()==8 and daily[daily.replaced_0728].date.eq('2021-07-28').all() and daily[daily.replaced_0728].baseline.eq('B1w').all()
    for row in daily.itertuples():
        if row.estimator=='R_taxi_km':s=taxi.loc[row.date];expected=s[['R_taxi_km','R_taxi_km_ci_lo','R_taxi_km_ci_hi']].to_numpy(float)
        elif row.baseline=='B1w' and row.date=='2021-07-28':
            if row.estimator=='R_probe':s=probe.loc['B1w'];expected=s[['R_probe','R_probe_ci_lo','R_probe_ci_hi']].to_numpy(float)
            else:s=device.loc[('B1w',row.estimator)];expected=s[['value','ci_lo','ci_hi']].to_numpy(float)
        else:s=family.loc[(row.date,row.estimator)];expected=s[['R','ci_lo','ci_hi']].to_numpy(float)
        checks[row.baseline+'_'+row.date+'_'+row.estimator+'_exact_source_replacement']=close([row.value,row.ci_lo,row.ci_hi],expected)
    for row in out.itertuples():
        g=daily[daily.baseline.eq(row.baseline)&daily.estimator.eq(row.estimator)].sort_values('date');dates=g.date.tolist();values=(g.ci_lo if row.date_rule=='sustained_lower_ci' else g.value).to_numpy(float);finite=np.isfinite(values);cross=finite&(values>=row.theta)
        qualified=None;first=None;earlier=0;right=False
        if row.date_rule=='first_ge':
            candidates=np.flatnonzero(cross)
            if len(candidates):
                j=candidates[0];first=dates[j];earlier=(~finite[:j]).sum()
                if earlier:status='not_evaluable_missing_values'
                else:status='qualified';qualified=dates[j]
            elif finite.all():status='right_censored';right=True
            else:status='not_evaluable_missing_values'
        else:
            candidates=[j for j in range(len(dates)) if all(finite[j:]) and all(values[j:]>=row.theta)]
            if candidates:j=candidates[0];qualified=dates[j];first=qualified;status='qualified';earlier=(~finite[:j]).sum()
            elif finite[-1] and values[-1]<row.theta:status='right_censored';right=True
            else:status='not_evaluable_missing_values'
        expected_end='2021-07-31' if row.estimator in ['R_probe','R_taxi_km'] else '2021-08-02'
        checks[row.baseline+'_'+row.estimator+'_'+str(row.theta)+'_'+row.date_rule+'_independent_date_rule']=norm(row.recovery_date)==qualified and norm(row.first_observed_qualifying_date)==first and row.status==status and row.right_censored==right and row.earlier_missing==earlier and row.window_end==expected_end and row.n_observations==len(dates) and norm(row.censor_date)==(dates[-1] if right else None)
    checks['all_protected_inputs_science_unchanged']=before=={str(p):sha(p) for p in protected}
    checks={k:bool(v) for k,v in checks.items()};report=dict(ended=datetime.now(timezone.utc).isoformat(),seconds=time.monotonic()-started,all_passed=all(checks.values()),n_checks=len(checks),checks=checks,source_reads=False,key_reads=False,scientific_outputs_modified=False,
        theta090=out[out.theta.eq(.9)].to_dict('records'),input_sha256=before)
    # Convert empty cells toJSON null, without emitting restricted identifiers.
    report['theta090']=json.loads(pd.DataFrame(report['theta090']).to_json(orient='records'))
    (R/'00_env/health_baseline_recovery_crossaudit_v8.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps(dict(all_passed=report['all_passed'],n_checks=len(checks),seconds=report['seconds'],failed=[k for k,v in checks.items() if not v])))
    if not report['all_passed']:raise AssertionError('W1vehicle/W2 independent crossaudit failed')

if __name__=='__main__':main()
