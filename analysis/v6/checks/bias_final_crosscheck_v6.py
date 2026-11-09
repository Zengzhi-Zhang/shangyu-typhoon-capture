# -*- coding: utf-8 -*-
"""Independent local-output cross-checks only; no raw source or secret access."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[3]), str(_ReleasePath(__file__).resolve().parents[1])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
import numpy as np,pandas as pd
R=Path(_release_path('project_root'));O=R/'formal_v6'
def main():
    inputs={}
    def read(rel,parquet=False):
        p=O/rel;s=p.stat();inputs[str(p)]=(s.st_size,s.st_mtime_ns)
        return pd.read_parquet(p) if parquet else pd.read_csv(p,encoding='utf-8-sig')
    b=read('01_internal/T31_recovery_bounds_internal_v6.csv').set_index('date')
    dev=read('01_internal/T31_device_scenarios_internal_v6.parquet',True)
    boot=read('01_internal/T31_bootstrap_internal_v6.parquet',True)
    rec=read('07_consequences/T33_recovery_date_by_estimator_v6.csv')
    ring=read('07_consequences/T33_ring_daily_ratios_v6.csv')
    pre=read('06_s_pre/T32_s_pre_v6.csv').set_index('date')
    oldp=R/'formal_v3/06_m5_bias_correction/m5_visible_bias_v3.csv';s=oldp.stat();inputs[str(oldp)]=(s.st_size,s.st_mtime_ns)
    old=pd.read_csv(oldp,encoding='utf-8-sig').set_index('date');checks={};coverage=[]
    checks['mid_all9_NA_not_partial_aggregate']=bool(b.R_mid.isna().all()&~b.mid_available.any())
    checks['S2_S3_and_raw_failure_context_all9']=bool(b.mid_proxy_calibration_S2.all()&b.mid_proxy_calibration_S3.all()&b.mid_proxy_coordinate_method.eq('raw_WGS84').all()&b.mid_proxy_calibration_status.eq('failed_preserve_raw').all())
    for date,g in dev.groupby('date'):
        row=b.loc[date];den=g.baseline_B1.sum()
        checks['lower_full_observed_numerator:'+date]=abs(g.observed_records.sum()/den-row.R_lower)<1e-10
        checks['upper_all_device_scenario_aggregate:'+date]=abs(g.records_upper_scenario.sum()/den-row.R_upper)<1e-10
        u=g.U;missing=int((u&~g.cap_ring_proxy_available).sum())
        checks['missing_proxy_counts:'+date]=missing==row.n_U_cap_proxy_missing and missing>0
        for estimator,col in [('R_online','in_online'),('R_stable','in_Sstar')]:
            q=g[g[col]];ratio=q.observed_records.sum()/q.baseline_B1.sum()
            checks['whole_city_comparator:'+estimator+':'+date]=abs(ratio-old.loc[date,estimator])<=.000051
            z=q[q.ring.eq('missing')];share=z.baseline_B1.sum()/q.baseline_B1.sum()
            shown=ring[ring.date.eq(date)&ring.estimator.eq(estimator)]
            checks['missing_distance_baseline_share:'+estimator+':'+date]=bool((shown.baseline_share_missing_distance-share).abs().le(.000051).all())
            coverage.append(dict(date=date,estimator=estimator,n_missing_distance=len(z),baseline_share_missing_distance=share,missing_distance_ratio=z.observed_records.sum()/z.baseline_B1.sum()))
        for scenario in ['R_lower','R_upper','R_mid']:
            v=boot[boot.date.eq(date)&boot.scenario.eq(scenario)].estimate.to_numpy()
            checks['500_bootstrap:'+date+':'+scenario]=len(v)==500
            if scenario=='R_mid':checks['missing_mid_bootstrap_NA:'+date]=bool(np.isnan(v).all())
            else:
                lo,hi=np.quantile(v,[.025,.975]);checks['percentile_interval:'+date+':'+scenario]=abs(lo-row[scenario+'_ci_lo'])<1e-10 and abs(hi-row[scenario+'_ci_hi'])<1e-10
    dates=sorted(b.index);series={e:old[e].reindex(dates).to_numpy(float) for e in ['R_naive','R_online','R_stable','R_taxi_km']}
    series['R_pre']=pre.R_pre.reindex(dates).to_numpy(float)
    for e in ['R_lower','R_upper']:series[e]=b[e].reindex(dates).to_numpy(float)
    for i,row in rec.iterrows():
        horizon=dates[:7] if row.estimator=='R_taxi_km' else dates;v=series[row.estimator][:len(horizon)]
        candidates=[k for k in range(len(v)) if np.isfinite(v[k:]).all() and (v[k:]>=row.theta).all()]
        expected=horizon[candidates[0]] if candidates else None
        checks['first_sustained_tail:'+str(i)]=(pd.isna(row.recovery_date) if expected is None else row.recovery_date==expected)
        checks['right_horizon:'+str(i)]=row.horizon==horizon[-1]
    p=O/'00_env/bias_metadata_refresh_v6.json';refresh=json.loads(p.read_text(encoding='utf-8'))
    numeric=b.reset_index()[refresh['bounds_numeric_columns']]
    refresh['bounds_numeric_after_sha256']=hashlib.sha256(numeric.to_csv(index=False).encode()).hexdigest()
    refresh['recovery_dates_after_sha256']=hashlib.sha256(rec.to_csv(index=False).encode()).hexdigest()
    checks['metadata_refresh_bounds_points_and_CI_unchanged']=refresh['bounds_numeric_before_sha256']==refresh['bounds_numeric_after_sha256']
    checks['metadata_refresh_recovery_dates_unchanged']=refresh['recovery_dates_before_sha256']==refresh['recovery_dates_after_sha256']
    refresh['numeric_outputs_unchanged']=bool(checks['metadata_refresh_bounds_points_and_CI_unchanged'] and checks['metadata_refresh_recovery_dates_unchanged'])
    refresh['ended_at_utc']=datetime.now(timezone.utc).isoformat();p.write_text(json.dumps(refresh,ensure_ascii=False,indent=2),encoding='utf-8')
    for pth,before in inputs.items():
        s=Path(pth).stat();checks['readonly_unchanged:'+Path(pth).name]=before==(s.st_size,s.st_mtime_ns)
    checks={k:bool(v) for k,v in checks.items()};failed=[k for k,v in checks.items() if not v]
    result=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),status='complete' if not failed else 'failed',raw_source_read=False,key_read=False,checks=checks,failed=failed,ring_missing_distance_coverage=coverage)
    (O/'00_env/bias_final_crosscheck_v6.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps(dict(status=result['status'],n_checks=len(checks),failed=failed,metadata_numeric_outputs_unchanged=refresh['numeric_outputs_unchanged'],coverage_august2=[x for x in coverage if x['date']=='2021-08-02']),ensure_ascii=False))
    if failed:raise AssertionError('Independent output checks failed')
if __name__=='__main__':main()
