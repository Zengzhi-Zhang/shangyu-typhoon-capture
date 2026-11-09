# -*- coding: utf-8 -*-
"""Read-only verification of T34 evidence paths/keys, not manuscript editing."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[3]), str(_ReleasePath(__file__).resolve().parents[1])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from pathlib import Path
from datetime import datetime,timezone
import json
import pandas as pd
R=Path(_release_path('project_root'));O=R/'formal_v6'
def main():
    tracked={}
    def read_csv(p,**kw):
        p=Path(p);s=p.stat();tracked[str(p)]=(s.st_size,s.st_mtime_ns)
        return pd.read_csv(p,encoding='utf-8-sig',**kw)
    def read_json(p):
        p=Path(p);s=p.stat();tracked[str(p)]=(s.st_size,s.st_mtime_ns)
        return json.loads(p.read_text(encoding='utf-8'))
    def pointer(j,path):
        for x in path.strip('/').split('/'):j=j[int(x)] if isinstance(j,list) else j[x]
        return j
    t=read_csv(O/'20_manuscript_fixes/T34_manuscript_fact_fixes_v6.csv')
    rows=[]
    for _,x in t.iterrows():
        p=Path(x.support_file);p=p if p.is_absolute() else R/p
        rows.append(dict(id=x.id,support_file=str(p),exists=p.exists(),current_support_key=x.support_key))
    v=read_json(R/'00_env/vehicle_execution.json');f5='/checks/frozen_mean_daily_log_residual_max'
    h=read_json(R/'formal_v3/06_m5_bias_correction/m5_h4_verdict_v3.json');f9='/criteria/3/observed/per_date_masking/8/drop_bias'
    f9row=pointer(h,'/criteria/3/observed/per_date_masking/8')
    sig=read_csv(R/'formal_v3/07_m6_robustness/m6_signature_comparison_v3.csv').set_index('date')
    f7=[]
    for d in ['2021-07-08','2021-07-26']:
        f7.append(dict(date=d,mean_dist_baiguan_diff=float(sig.loc[d,'mean_dist_baiguan_diff']),raw_p=float(sig.loc[d,'mean_dist_baiguan_diff_p']),holm_p=float(sig.loc[d,'mean_dist_baiguan_diff_p_holm'])))
    visible=read_csv(R/'formal_v3/06_m5_bias_correction/m5_visible_bias_v3.csv').set_index('date')
    f2={d:float(visible.loc[d,'delta_naive']) for d in ['2021-07-26','2021-08-02']}
    flow=read_csv(R/'formal_v3/06_m5_bias_correction/m5_leaveout_validation_flowweighted.csv')
    f6=flow[flow.date.isin(['2021-07-29','2021-07-30'])][['date','method','bias_mean','mae']].to_dict('records')
    dd=read_csv(R/'01_panels/device_day.csv',nrows=0);attr=read_csv(R/'01_panels/device_attributes.csv',nrows=0)
    checks=dict(all10_identifiers=set(t.id)=={f'F{i}' for i in range(1,11)},all_primary_support_paths_except_future_T31_exist=all(x['exists'] for x in rows if x['id']!='F8'),
        F1_dev_n_columns={'dev','n'}.issubset(dd.columns),F1_A200_column='in_A200' in attr,
        F5_exact_pointer_matches=float(pointer(v,f5))==0.02461177520300238,
        F7_both_dates_and_exact_distance_p_keys_exist=True,F9_pointer_value=float(pointer(h,f9))==.0217,
        F9_pointer_date_and_masking=f9row['date']=='2021-07-29' and f9row['masking']=='flowweighted')
    for p,before in tracked.items():
        s=Path(p).stat();checks['readonly_unchanged:'+Path(p).name]=before==(s.st_size,s.st_mtime_ns)
    t31_ready=(O/'05_bounds/T31_recovery_bounds_v6.csv').exists();keys=t.set_index('id').support_key
    recommendations=[]
    if f5 not in keys['F5']:recommendations.append('F5 support_key should use /checks/frozen_mean_daily_log_residual_max rather than a vague nested-key note.')
    if 'mean_dist_baiguan_diff_p_holm' not in keys['F7']:recommendations.append('F7 support_key should name mean_dist_baiguan_diff_p_holm explicitly. Both distance point estimates are negative, but neither Holm p is below .05.')
    if not all(x in keys['F6'] for x in ['bias_mean','mae']):recommendations.append('F6 numeric field names are bias_mean and mae (lowercase).')
    if not all(x in keys['F2'] for x in ['formal_v6/03_taxi_probe/','T28_probe_daily_v6.csv','T29_summary_v6.csv','formal_v6/05_bounds/T31_recovery_bounds_v6.csv']):recommendations.append('F2 supplementary labels should specify the exact formal_v6 source paths.')
    if not t31_ready:recommendations.append('F8 T31 is a pending dependency until I5 finishes.')
    status=('complete_references_verified' if not recommendations else 'complete_with_precise_key_recommendations' if t31_ready else 'pending_T31_support_and_key_recommendations') if all(checks.values()) else 'failed'
    report=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),status=status,T31_dependency_available=t31_ready,
        primary_supports=rows,checks=checks,F2_delta_naive=f2,F5=dict(exact_pointer=f5,value=pointer(v,f5),different_estimator_pointer='/checks/exact_ratio_of_aggregates_log_residual_max',different_estimator_value=pointer(v,'/checks/exact_ratio_of_aggregates_log_residual_max')),
        F6_flowweighted_MAE_rows=f6,F7_distance_rows=f7,F9=dict(exact_pointer=f9,value=pointer(h,f9),row=f9row),
        recommendations=recommendations,
        manuscript_or_other_scripts_modified=False)
    (O/'00_env/bias_t34_support_audit_v6.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps(dict(status=report['status'],checks=checks,F5=pointer(v,f5),F9=pointer(h,f9),T31_exists=(O/'05_bounds/T31_recovery_bounds_v6.csv').exists()),ensure_ascii=False))
if __name__=='__main__':main()
