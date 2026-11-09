# -*- coding: utf-8 -*-
"""Independent v3 arithmetic, frozen-input, verdict and publication audits."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[3]), str(_ReleasePath(__file__).resolve().parents[1])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
import re,hashlib,csv
from pathlib import Path
from PIL import Image
from common_v3 import *
from privacy_check_v3 import check as privacy_check
def read(rel):return pd.read_csv(ROOT/rel,encoding='utf-8-sig')
def jr(rel):return json.loads((ROOT/rel).read_text(encoding='utf-8-sig'))
def main():
    started=now();checks={}
    def check(name,ok,details=None):checks[name]=dict(passed=bool(ok),details=details)
    required=['README_v3.md','EXECUTION_LOG_v3.md','DEVIATIONS_v3.md','RESULTS_SUMMARY_v3.md','results_v3.json',
        '04_m3_vehicles/m3_h1_placebo_margins_v3.csv','04_m3_vehicles/m3_composition_v3.csv','04_m3_vehicles/m3_h2_composition_placebo_v3.csv','04_m3_vehicles/m3_h1_h2_verdict_v3.json',
        '05_m4_spatial/m4_ols_v3.csv','05_m4_spatial/m4_by_distance_ring_v3.csv','05_m4_spatial/m4_taxi_camera_gradient_v3.csv','05_m4_spatial/m4_taxi_redistribution_v3.csv','05_m4_spatial/m4_taxi_grid_threshold_sensitivity_v3.csv','05_m4_spatial/m4_taxi_camera_spearman_v3.json',
        '06_m5_bias_correction/m5_failure_counts_v3.csv','06_m5_bias_correction/m5_ordinary_floor_v3.csv','06_m5_bias_correction/m5_failure_nonrandomness_v3.csv','06_m5_bias_correction/m5_failure_profile_v3.csv','06_m5_bias_correction/m5_failure_persistence_v3.csv','06_m5_bias_correction/m5_bias_decomposition_v3.csv','06_m5_bias_correction/m5_visible_bias_v3.csv',
        '07_m6_robustness/m6_negative_control_v3.csv','07_m6_robustness/m6_signature_comparison_v3.csv','07_m6_robustness/m6_b3_drift_v3.csv','07_m6_robustness/m6_robustness_matrix_v3.csv',
        '08_figures/fig5_spatial_v3.png','08_figures/fig6_bias_correction_v3.png','08_figures/fig7_two_sensors_v3.png']
    missing=[p for p in required if not (ROOT/p).is_file() or not (ROOT/p).stat().st_size]
    check('required_v3_outputs_present',not missing,missing)
    if missing:write_json(ROOT/'00_env/audit_v3.json',dict(passed=False,checks=checks));raise SystemExit(1)
    check('correct_python',Path(sys.executable).resolve()==Path(_release_path('python_executable')).resolve())
    check('B_P12_no_evaluation_overlap',len(B_P)==12 and not set(B_P)&set(E_P))
    check('B_P_exact_weekday_counts',[len(refs(d,'B_P')) for d in E_P[:7]]==[1,2,2,2,2,2,1])
    check('no_copied_panels',all(p.suffix not in {'.csv','.parquet'} for p in (ROOT/'01_panels').rglob('*') if p.is_file()))
    begin=jr('00_env/input_manifest_v1panels_begin.json');end=jr('00_env/input_manifest_v1panels_end.json')
    check('input_full_SHA256_size_mtime_unchanged',begin['files']==end['files'] and end['unchanged'])
    check('frozen_v1_results_unchanged_except_hygiene',jr('00_env/frozen_v1_results_end.json')['unchanged_except_authorized_hygiene'])
    check('secret_removed_from_delivery_tree',not (_ReleasePath(_release_key_file())).exists() and not list(ROOT.rglob('.hmac_key')))
    frozen=ROOT/'00_env/PROTOCOL_v3_FROZEN.md';check('protocol_frozen_unchanged',frozen.read_text(encoding='utf-8')==Path(jr('00_env/protocol_frozen.json')['source']).read_text(encoding='utf-8-sig'))
    summary=(ROOT/'RESULTS_SUMMARY_v3.md').read_text(encoding='utf-8')
    check('all_23_tables',set(map(int,re.findall(r'^## T(\d+)\b',summary,re.M)))==set(range(1,24)))
    check('BLOCKED_explicit',bool(jr('results_v3.json')['blocked_subanalyses']) and 'BLOCKED' in summary and '网格×小时' in (ROOT/'DEVIATIONS_v3.md').read_text(encoding='utf-8'))
    dh,a,dd=load_panels();mat_h=dh[dh.hour.between(11,23)].pivot_table(index='dev',columns='date',values='n',aggfunc='sum',fill_value=0).reindex(index=dd.index,columns=D_ALL,fill_value=0)
    ct=read('06_m5_bias_correction/m5_failure_counts_v3.csv');A=a.in_A200.eq(1)
    for r in ct.to_dict('records'):
        date=r['date'];m=mat_h if date=='2021-07-25' else dd
        ds=[d for d in refs(date,'B1') if d!=date];pool='B1'
        if not ds:ds=sorted(set(refs(date,B1+B3))-{date});pool='B1+B3'
        b=m[ds].mean(axis=1);prev=(pd.Timestamp(date)-pd.Timedelta(days=7)).strftime('%Y-%m-%d')
        if prev not in D_ALL or prev in D_INELIG:den=b;fallback_day=int(A.sum());fallback_dev=0
        else:
            degraded=m[prev]<.5*b;den=m[prev].where(~degraded,b);fallback_day=0;fallback_dev=int((degraded&A).sum())
        f=((m[date]<.05*den)&A);g=((m[date]<.5*den)&A)
        check('A1_independent_'+date,int(f.sum())==r['n_failed_A1'] and int(g.sum())==r['n_degraded_A1'] and fallback_dev==r['n_fallback_device_degraded'],dict(expected_F=int(f.sum()),expected_G=int(g.sum())))
        check('LOO_pool_'+date,r['n_baseline_days_used']==len(ds) and r['baseline_pool']==pool)
    comp=read('04_m3_vehicles/m3_composition_v3.csv')
    check('four_class_complete_54_rows',len(comp)==54 and set(comp.thr)=={6,8,9} and set(comp.window)=={'typhoon','placebo'})
    check('four_class_shares_sum_one',np.allclose(comp[['share_'+c for c in ['regular','frequent','occasional','nonwindow']]].sum(axis=1),1,atol=.00021))
    check('A4_nonwindow_equals_two_5class',np.allclose(comp.share_nonwindow,comp.share_earlier_only_5class+comp.share_unseen_5class,atol=.00011))
    for f in ['m3_return_curve.csv','m3_return_gap.csv','m3_two_margins_table.csv']:
        check('unchanged_copy_'+f,(ROOT/'04_m3_vehicles'/f).read_bytes()==(V1/'04_m3_vehicles'/f).read_bytes())
    O=read('05_m4_spatial/m4_ols_v3.csv');old=pd.read_csv(V1/'05_m4_spatial/m4_ols.csv',encoding='utf-8-sig');s=O[O['sample'].eq('Sstar')]
    join=s.merge(old,on=['date','term'],suffixes=('_v3','_v1'))
    for field in ['coef','se_HC1','p','n','r_squared']:check('Sstar_OLS_'+field+'_4places',len(join)==len(old) and np.allclose(join[field+'_v3'].round(4),join[field+'_v1'].round(4),atol=1e-9))
    check('OLS_three_samples',set(O['sample'])=={'Sstar','S_on','A100_floor'})
    decomp=read('06_m5_bias_correction/m5_bias_decomposition_v3.csv');visible=read('06_m5_bias_correction/m5_visible_bias_v3.csv').set_index('date')
    for date,g in decomp.groupby('date'):
        check('decomposition_'+date,abs(g.w_g.sum()-1)<.00021 and abs(g.contribution.sum()-visible.loc[date,'delta_naive'])<.00026)
    for date,r in visible.iterrows():
        for name in ['naive','online','taxi']:
            values=[r['delta_'+name+'_ci_lo'],r['delta_'+name],r['delta_'+name+'_ci_hi']]
            missing=all(pd.isna(v) for v in values)
            check('delta_interval_'+date+'_'+name,(missing and name=='taxi' and date in ['2021-08-01','2021-08-02']) or (values[0]<=values[1]<=values[2]))
    redis=read('05_m4_spatial/m4_taxi_redistribution_v3.csv')
    check('A6_main_five_rings_4days',len(redis)==20 and set(redis.distance_ring)=={'0-2','2-4','4-7','7-12','12+'} and set(redis.date)==set(dates('2021-07-25','2021-07-28')))
    check('A6_all_main_cells_ge10',bool((redis.n_grids>=10).all()))
    for r in redis.to_dict('records'):
        check('taxi_camera_delta_'+r['date']+'_'+r['distance_ring'],abs(r['r_taxi_pts']-r['r_camera']-r['delta_ring'])<=.00011)
    for date,group in redis.groupby('date'):
        check('taxi_city_shares_close_'+date,abs(group.share_base.sum()-1)<.00021 and abs(group.share_t.sum()-1)<.00021 and abs(group.share_shift.sum())<.00026)
    R=jr('results_v3.json');verdictfiles={'H1':'04_m3_vehicles/m3_h1_verdict_v3.json','H2':'04_m3_vehicles/m3_h2_verdict_v3.json','H3':'05_m4_spatial/m4_h3_verdict_v3.json','H4':'06_m5_bias_correction/m5_h4_verdict_v3.json'}
    for h,path in verdictfiles.items():
        v=jr(path);check(h+'_status_provenance',R['verdicts_v3'][h]==v and v['status'] in {'supported','partial','not_supported'})
        c={x['id']:x for x in v['criteria']};check(h+'_criteria_numeric_disclosed',bool(c) and all('criterion' in x and 'threshold' in x and 'observed' in x and type(x['met']) is bool for x in c.values()))
        necessary=[x for x in v['criteria'] if x.get('required_for_supported',True)]
        if h=='H2':necessary=[c[i] for i in [1,2,3]]
        if h=='H4':necessary=[c[i] for i in [1,2,3,4]]
        if v['status']=='supported':check(h+'_supported_all_required',all(x['met'] for x in necessary))
    ordinary=read('06_m5_bias_correction/m5_ordinary_floor_v3.csv')
    phi=jr('07_m6_robustness/m6_b3_drift_v3.json');drift=read('07_m6_robustness/m6_b3_drift_v3.csv')
    check('T22_phi_mean_independent',len(drift)==15 and abs(drift.R_stable_B3.mean()-phi['phi'][0])<.000051)
    for stem in ['fig5_spatial_v3','fig6_bias_correction_v3','fig7_two_sensors_v3']:
        with Image.open(ROOT/'08_figures'/f'{stem}.png') as im:check(stem+'_dpi160',min(im.info.get('dpi',(0,0)))>=159.99)
        check(stem+'_data',bool((ROOT/'08_figures'/f'{stem}_data.csv').stat().st_size))
    check('privacy_checks_all_zero',privacy_check(write=False)['passed'])
    matrix=read('07_m6_robustness/m6_robustness_matrix_v3.csv');check('matrix_has_required_columns',{'effect','lo','hi','sign_preserved','ci_excludes_0'}.issubset(matrix.columns))
    if '--verify-manifest' in sys.argv:
        man=jr('09_manifest/manifest_v3.json');errors=[]
        for r in man['files']:
            p=ROOT/r['path']
            if not p.is_file() or p.stat().st_size!=r['size'] or hashlib.sha256(p.read_bytes()).hexdigest()!=r['sha256']:errors.append(r['path'])
        check('all_manifest_SHA256_current',not errors,errors)
        check('no_key_or_panels_in_package_manifest',not any(r['path'].startswith('pub_package/') and ('/00_env/' in r['path'] or '/01_panels/' in r['path'] or '.hmac_key' in r['path']) for r in man['files']))
    failures=[k for k,v in checks.items() if not v['passed']]
    report=dict(generated_at=now(),started=started,passed=not failures,checks=checks,failed_checks=failures,scope='Independent arithmetic and provenance checks; observed scientific non-support/expectation failures are not treated as execution errors.')
    if '--verify-manifest' not in sys.argv:
        write_json(ROOT/'00_env/audit_v3.json',report)
        stage_record('audit',started,['00_env/audit_v3.json'],dict(passed=not failures,checks=len(checks)))
    print('V3 audit',len(checks),'checks, passed',not failures,'failures',failures,flush=True)
    if failures:raise SystemExit(1)
if __name__=='__main__':main()
