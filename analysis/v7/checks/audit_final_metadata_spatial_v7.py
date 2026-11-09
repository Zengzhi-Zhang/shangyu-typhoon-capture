# -*- coding: utf-8 -*-
"""Final root-assembly audit supplement; writes only its own00_env report."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[3]), str(_ReleasePath(__file__).resolve().parents[1])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from pathlib import Path
import json,hashlib
from datetime import datetime,timezone
import pandas as pd

R=Path(_release_path('v7_root'))
def load(p):return json.loads((R/p).read_text(encoding='utf-8-sig'))
def read(p,**kw):return pd.read_csv(R/p,encoding='utf-8-sig',**kw)
def main():
    results=load('results_v7.json');ce=load('00_env/capture_execution_v7.json');he=load('00_env/health_screen_execution_v7.json');pe=load('00_env/probe_bounds_execution_v7.json')
    acceptance=pd.DataFrame(results['acceptance']);main=acceptance[acceptance.task.eq('I3′')]
    keys={'Sstar_relative_median_in_090_105':'S*相对cap中位∈[0.90,1.05]','failed_pooled_cap_le002':'事件暴露合格失效组captured/expected≤0.02','Spearman_ge06':'Spearman≥0.6'}
    compare=[]
    for item in ce['acceptance']:
        if item['variant']!='main_R60_cap03':continue
        for field,label in keys.items():
            expected='达到' if item[field] is True else '未达到' if item[field] is False else '不可评估'
            row=main[main.date.eq(item['date'])&main.criterion.eq(label)]
            compare.append(len(row)==1 and row.iloc[0].status==expected)
    unmet=acceptance[acceptance.status.ne('达到')]
    checks=dict(root24acceptance_rows=len(acceptance)==24,
        root21I3_rows_7days_3criteria=len(main)==21 and main.groupby('date').size().eq(3).all(),
        root_all_I3_statuses_exact_frozen_numerics=all(compare),root_exactly2_unmet=len(unmet)==2,
        root_two_unmet_dates_criteria_exact=set(zip(unmet.date,unmet.criterion))=={('2021-07-25','S*相对cap中位∈[0.90,1.05]'),('2021-07-30','Spearman≥0.6')})
    for criterion,item in he['details']['acceptance'].items():
        row=acceptance[acceptance.task.eq('I6′')&acceptance.criterion.eq(criterion)]
        checks['root_I6_'+criterion+'_numeric_status']=len(row)==1 and row.iloc[0].status==('达到' if item['met'] else '未达到')
    row=acceptance[acceptance.task.eq('I5′')]
    checks['root_I5_numeric_status_exact']=len(row)==1 and row.iloc[0].status==('达到' if pe['acceptance']['R_probe_0726_in_056_063'] else '未达到')
    family=read('07_consequences/T37_estimator_family_v7.csv')
    health=read('06_s_pre/T36_health_screened_v6.csv').set_index('date')
    bounds=read('05_bounds/T31_recovery_bounds_v7.csv').set_index('date')
    oldsets=family[family.estimator.isin(['R_naive','R_online','R_stable'])]
    checks['T37_copied_old_CI_scope_not_mislabelled_scenario']=oldsets.interval_scope.str.contains('Copied frozen v6/v3 device-cluster interval; fixed observed network membership').all()
    scenarios=family[family.estimator.isin(['R_lower','R_upper','R_mid'])]
    checks['T37_scenario_CI_fixed_A100_states_U_neighbours_ring_scope']=scenarios.interval_scope.str.contains('500 paired A100 device clusters; states/U/neighbours/ring proxy fixed').all()
    checks['T37_health_A200_shared500_scope_exact']=all(row.interval_scope==health.loc[row.date,'CI_scope'] for row in family[family.estimator.isin(['R_health','R_health_strict','R_spre_health'])].itertuples())
    checks['T37_Spre_scope_fixed_A100500']=family[family.estimator.eq('R_pre')].interval_scope.eq('Copied v6 fixed S_pre, paired A100 device500 cluster percentile interval').all()
    checks['T37_probe_product_scope_exact']=all(row.interval_scope==bounds.loc[row.date,'R_probe_interval_scope'] for row in family[family.estimator.eq('R_probe')].itertuples())
    deviations=(R/'DEVIATIONS_v7.md').read_text(encoding='utf-8')
    checks['root100000products_not_independent_reps_disclosed']='100000组合不是100000独立重复' in deviations
    verification=load('00_env/input_verification_v7.json')
    checks['protected2350_inputs_unchanged']=verification['unchanged'] and verification['n_files']==2350
    internal=read('01_internal/capture_summary_internal_v7.csv').set_index(['variant','date'])
    for file in ['03_taxi_probe/T35_capture_wellmatched_v6.csv','08_figures/fig_capture_relative_v7_data.csv']:
        public=read(file,dtype=str,keep_default_na=False)
        checks['p_scientific_6significant_exact_'+Path(file).name]=all(row.spearman_p==format(internal.loc[(row.variant,row.date),'spearman_p'],'.6g') for row in public.itertuples())
    prior=load('00_env/public_independent_audit_v7.json')
    checks['prior178check_public_audit_passed']=prior['all_passed'] and prior['n_checks']==178 and prior['privacy_total_hits']==0
    checks['all33_public_files_still_match_final_audit_SHA']=all(hashlib.sha256((R/f['path']).read_bytes()).hexdigest()==f['sha256'] for f in prior['files'])
    report=dict(checked_at_utc=datetime.now(timezone.utc).isoformat(),all_passed=all(checks.values()),n_checks=len(checks),checks={k:bool(v) for k,v in checks.items()},
        main_unmet=unmet.to_dict('records'),control_only_selection_counts=prior['control_only_selection_counts'],scientific_outputs_modified=False,
        public_scan_scope_note='33 files includes09_manifest/privacy_check_v7.json; root scan32 excludes its own report',source_reads=False,key_reads=False)
    (R/'00_env/final_metadata_spatial_audit_v7.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(all_passed=report['all_passed'],n_checks=len(checks),failed=[k for k,v in checks.items() if not v])))
    if not report['all_passed']:raise AssertionError('Final metadata supplement failed')

if __name__=='__main__':main()
