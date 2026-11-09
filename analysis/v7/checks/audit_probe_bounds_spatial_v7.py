# -*- coding: utf-8 -*-
"""Independent T28/T31 audit; only local frozen caches; only audit JSON writes."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[3]), str(_ReleasePath(__file__).resolve().parents[1])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from pathlib import Path
from datetime import datetime, timezone
import hashlib,json
import numpy as np
import pandas as pd

R=Path(_release_path('v7_root'));V6=R.parent/'formal_v6'
DATES=pd.date_range('2021-07-06','2021-08-02').strftime('%Y-%m-%d').tolist()
EVENT=pd.date_range('2021-07-25','2021-08-02').strftime('%Y-%m-%d').tolist()
B=[d for d in DATES if '2021-07-06'<=d<='2021-07-21' and d not in ['2021-07-08','2021-07-10']]
def read(p,**kw):return pd.read_csv(p,encoding='utf-8-sig',**kw)
def safe(n,b):
    n,b=np.broadcast_arrays(np.asarray(n,float),np.asarray(b,float))
    return np.divide(n,b,out=np.full(n.shape,np.nan),where=np.isfinite(b)&(b>0))
def close(a,b,atol=5e-10):return bool(np.allclose(a,b,rtol=5e-10,atol=atol,equal_nan=True))
def ci(v):
    x=np.asarray(v,float);x=x[np.isfinite(x)]
    return np.quantile(x,[.025,.975]) if len(x) else np.full(2,np.nan)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    checks={};paths=[V6/'01_internal/taxi_probe_joined_v6.parquet',V6/'01_internal/taxi_probe_ph_v6.txt',
        V6/'01_internal/T31_device_scenarios_internal_v6.parquet',V6/'01_internal/T31_bootstrap_internal_v6.parquet',
        V6/'03_taxi_probe/T28_probe_daily_v6.csv',V6/'05_bounds/T31_recovery_bounds_v6.csv',
        R/'03_taxi_probe/T28_probe_daily_v7.csv',R/'05_bounds/T31_recovery_bounds_v7.csv',
        R/'03_taxi_probe/T28_wednesday_sensitivity_v7.csv']
    before={str(p):sha(p) for p in paths}
    daily=read(R/'01_internal/T28_probe_daily_internal_v7.csv').set_index('date')
    bounds=read(R/'01_internal/T31_recovery_bounds_internal_v7.csv').set_index('date')
    pub=read(V6/'03_taxi_probe/T28_probe_daily_v6.csv').set_index('date')
    vehicle=pd.read_parquet(R/'01_internal/probe_vehicle_bootstrap_v7.parquet')
    device=pd.read_parquet(R/'01_internal/probe_device_bootstrap_v7.parquet')
    product=pd.read_parquet(R/'01_internal/probe_product_bootstrap_v7.parquet')
    joined=pd.read_parquet(V6/'01_internal/taxi_probe_joined_v6.parquet')
    aliases=(V6/'01_internal/taxi_probe_ph_v6.txt').read_text(encoding='utf-8').splitlines()
    checks['290_fixed_vehicle_ids']=len(aliases)==290 and len(set(aliases))==290 and set(joined.ph)==set(aliases)
    checks['vehicle_date_full_product']=len(joined)==290*28 and not joined.duplicated(['ph','date']).any()
    vw=np.random.default_rng(20261005).multinomial(290,np.full(290,1/290),200)
    raw={c:joined.pivot(index='ph',columns='date',values=c).reindex(index=aliases,columns=DATES).fillna(0).to_numpy(float)
        for c in ['dist_km','km_from_11h','n','n_stable','rec_all_h11','rec_stable_h11']}
    index={d:i for i,d in enumerate(DATES)}
    def normalize(date,refs,matched):
        km=raw['km_from_11h' if matched else 'dist_km'];i=index[date];ref=[index[d] for d in refs]
        values=[];draws=[]
        for field in ['rec_all_h11','rec_stable_h11'] if matched else ['n','n_stable']:
            cp=safe(raw[field].sum(0),km.sum(0))
            values.append(float(safe(cp[i],cp[ref].mean())))
            bootcp=safe(vw@raw[field],vw@km)
            draws.append(safe(bootcp[:,i],bootcp[:,ref].mean(1)))
        return values,draws
    vehmarg={}
    for date in DATES[:26]:
        refs=[d for d in B if pd.Timestamp(d).dayofweek==pd.Timestamp(date).dayofweek]
        value,draw=normalize(date,refs,date=='2021-07-25');ba,bs=draw;qp=safe(ba,bs)
        v=vehicle[vehicle.date.eq(date)&vehicle.baseline_variant.eq('B_PROBE')].sort_values('vehicle_rep')
        checks[date+'_200_vehicle_marginals_source_reproduced']=len(v)==200 and close(v[['c_all','c_stable','q_probe']].to_numpy(),np.column_stack([ba,bs,qp]),atol=1e-12)
        checks[date+'_q_points_source_and_formula']=close([daily.loc[date,'c_all'],daily.loc[date,'c_stable'],daily.loc[date,'q_probe']],value+[value[0]/value[1]])
        checks[date+'_q_fleet_uses_inherited_comparators']=close([daily.loc[date,'q_fleet']],[pub.loc[date,'R_naive']/pub.loc[date,'R_stable']])
        vehmarg[date]=(ba,bs,qp)
    source=pd.read_parquet(V6/'01_internal/T31_device_scenarios_internal_v6.parquet')
    original_boot=pd.read_parquet(V6/'01_internal/T31_bootstrap_internal_v6.parquet')
    ids=np.sort(source.dev_public.unique());dw=np.random.default_rng(20261005).multinomial(len(ids),np.full(len(ids),1/len(ids)),500)
    checks['500_device_universe_A100_1287']=len(ids)==1287 and len(source)==1287*9
    devmarg={}
    for date in EVENT:
        x=source[source.date.eq(date)].set_index('dev_public').reindex(ids)
        n=x.observed_records.to_numpy(float);b=x.baseline_B1.to_numpy(float);st=x.in_Sstar.to_numpy(bool)
        rn=safe(dw@n,dw@b);rs=safe(dw@(n*st),dw@(b*st));qf=safe(rn,rs)
        dd=device[device.date.eq(date)].sort_values('device_rep')
        checks[date+'_500_device_marginals_source_reproduced']=len(dd)==500 and close(dd[['R_naive','R_stable','q_fleet']].to_numpy(),np.column_stack([rn,rs,qf]),atol=1e-12)
        ob=original_boot[original_boot.date.eq(date)&original_boot.scenario.eq('R_lower')].sort_values('rep')
        checks[date+'_500_naive_draws_exact_v6_source']=np.array_equal(rn,ob.estimate.to_numpy(float))
        devmarg[date]=(rn,rs,qf)
    for date in EVENT[:7]:
        rn,rs,qf=devmarg[date];ba,bs,qp=vehmarg[date]
        rp=(rn[:,None]*safe(bs,ba)[None,:]).ravel();difference=(qp[None,:]-qf[:,None]).ravel()
        p=product[product.date.eq(date)].sort_values(['device_rep','vehicle_rep'])
        checks[date+'_full_500x200_product_values']=len(p)==100000 and close(p.R_probe,rp,atol=1e-12) and close(p.q_probe_minus_q_fleet,difference,atol=1e-12)
        checks[date+'_full_500x200_product_indices']=np.array_equal(p.device_rep,np.repeat(np.arange(1,501),200)) and np.array_equal(p.vehicle_rep,np.tile(np.arange(1,201),500))
        checks[date+'_product_percentile_CIs']=close([*ci(rp),*ci(difference)],[bounds.loc[date,'R_probe_ci_lo'],bounds.loc[date,'R_probe_ci_hi'],daily.loc[date,'q_probe_minus_q_fleet_ci_lo'],daily.loc[date,'q_probe_minus_q_fleet_ci_hi']])
        checks[date+'_q_marginal_percentile_CIs']=close([*ci(qp),*ci(qf)],[daily.loc[date,'q_probe_ci_lo'],daily.loc[date,'q_probe_ci_hi'],daily.loc[date,'q_fleet_ci_lo'],daily.loc[date,'q_fleet_ci_hi']])
        point=pub.loc[date,'R_naive']*daily.loc[date,'c_stable']/daily.loc[date,'c_all']
        checks[date+'_Rprobe_point_precision_and_direction']=close([bounds.loc[date,'R_probe']],[point])
        checks[date+'_all100000products_finite']=np.isfinite(rp).sum()==100000 and np.isfinite(difference).sum()==100000
    sensitivity=read(R/'01_internal/T28_wednesday_sensitivity_internal_v7.csv')
    for label,refs in [('B_PROBE',['2021-07-07','2021-07-14','2021-07-21']),('B_PROBE_drop_0707_0721',['2021-07-14'])]:
        row=sensitivity[sensitivity.baseline_variant.eq(label)].iloc[0]
        value,draw=normalize('2021-07-28',refs,False);ba,bs=draw;rp=(devmarg['2021-07-28'][0][:,None]*safe(bs,ba)[None,:]).ravel()
        expected=[*value,value[0]/value[1],pub.loc['2021-07-28','R_naive']*value[1]/value[0]]
        checks[label+'_Wednesday_refs_exact']=row.baseline_dates==';'.join(refs) and row.n_baseline_dates==len(refs)
        checks[label+'_Wednesday_points_and_CIs']=close(row[['c_all','c_stable','q_probe','R_probe']].to_numpy(float),expected) and close(row[['c_all_ci_lo','c_all_ci_hi','c_stable_ci_lo','c_stable_ci_hi','q_probe_ci_lo','q_probe_ci_hi','R_probe_ci_lo','R_probe_ci_hi']].to_numpy(float),[*ci(ba),*ci(bs),*ci(safe(ba,bs)),*ci(rp)])
    for folder,file in [('03_taxi_probe','T28_probe_daily'),('05_bounds','T31_recovery_bounds')]:
        old=read(V6/folder/(file+'_v6.csv'),dtype=str,keep_default_na=False)
        new=read(R/folder/(file+'_v7.csv'),dtype=str,keep_default_na=False)
        checks[file+'_all_old_public_fields_exact']=new[old.columns].equals(old)
    for base in ['T28_probe_daily','T31_recovery_bounds']:
        old=read(V6/'01_internal'/(base+'_internal_v6.csv'),dtype=str,keep_default_na=False)
        new=read(R/'01_internal'/(base+'_internal_v7.csv'),dtype=str,keep_default_na=False)
        checks[base+'_all_old_internal_fields_exact']=new[old.columns].equals(old)
    checks['July25_hour_matched_flags']=daily.loc['2021-07-25','hour_matched']==1 and bounds.loc['2021-07-25','hour_matched']==1
    checks['Aug1_Aug2_no_probe_extrapolation']=bounds.loc[EVENT[-2:],['R_probe','R_probe_ci_lo','R_probe_ci_hi']].isna().all().all() and bounds.loc[EVENT[-2:],'R_probe_status'].eq('NA_no_GPS').all()
    checks['Aug1_Aug2_no_relative_probe']=daily.loc[EVENT[-2:],['q_probe','q_probe_ci_lo','q_probe_ci_hi']].isna().all().all()
    checks['old_mid_all9NA']=bounds.R_mid.isna().all()
    checks['shared_AVI_product_independence_limit_disclosed']=bounds.R_probe_shared_system_limitation.str.contains('independence').all()
    checks['all_audited_scientific_files_unchanged']=before=={str(p):sha(p) for p in paths}
    report=dict(checked_at_utc=datetime.now(timezone.utc).isoformat(),scope='Independent spatial-agent readonly scientific audit of I2-prime/I5-prime local caches and outputs',
        all_passed=all(checks.values()),n_checks=len(checks),checks={k:bool(v) for k,v in checks.items()},
        source_key_reads=False,old_versions_written=False,source_files_sha256=before,
        point_interval_precision_note='Points deliberately use inherited published four-decimal fleet ratios; intervals reuse unrounded original device draws. This is explicit in the output.',
        resampling_interpretation='The 500x200 empirical product imposes resampling independence. It does not establish scientific independence of shared AVI data.',
        Wednesday_sensitivity=sensitivity[['date','baseline_variant','baseline_dates','q_probe','R_probe','R_probe_ci_lo','R_probe_ci_hi']].to_dict('records'),
        key_Rprobe_0726=bounds.loc['2021-07-26',['R_probe','R_probe_ci_lo','R_probe_ci_hi']].to_dict())
    (R/'00_env/probe_bounds_spatial_independent_audit_v7.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(all_passed=report['all_passed'],n_checks=len(checks),failed=[k for k,v in checks.items() if not v])))
    if not report['all_passed']:raise AssertionError('Independent probe/bounds audit failed')

if __name__=='__main__':main()
