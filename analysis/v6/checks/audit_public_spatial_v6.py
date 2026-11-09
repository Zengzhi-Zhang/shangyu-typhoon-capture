# -*- coding: utf-8 -*-
"""Independent publication completeness/privacy audit, run after final tables exist.

Reads existing local files only. Writes its own00_env report; no table mutation.
Matched sensitive strings are counted but never printed or serialised.
"""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[3]), str(_ReleasePath(__file__).resolve().parents[1]), str(_ReleasePath(__file__).resolve().parent)]
from pathlib import Path
from decimal import Decimal,InvalidOperation
import argparse,csv,io,re,json,hashlib
import numpy as np
import pandas as pd
from spatial_helpers_v6 import ROOT,V1,D_STATE,EVENT,now,write_json

REQUIRED=[
 '02_device_state/device_state_v6.csv','02_device_state/T27_state_summary.csv','02_device_state/T27_failed_breakdown.csv',
 '03_taxi_probe/T28_probe_daily_v6.csv','03_taxi_probe/T28_probe_by_ring_v6.csv','03_taxi_probe/T28_probe_vehicle_distribution_v6.csv',
 '03_taxi_probe/T29_camera_capture_v6.csv','03_taxi_probe/T29_summary_v6.csv','03_taxi_probe/T29_calibration_v6.json',
 '04_leaveout/T30_leaveout_structured_v6.csv','04_leaveout/T30_applicability_matrix_v6.csv',
 '05_bounds/T31_recovery_bounds_v6.csv','06_s_pre/T32_s_pre_v6.csv','06_s_pre/T32_s_pre_ols_v6.csv','06_s_pre/T32_s_pre_rings_v6.csv',
 '07_consequences/T33_recovery_date_by_estimator_v6.csv','07_consequences/T33_lagging_rings_v6.csv',
 '20_manuscript_fixes/T34_manuscript_fact_fixes_v6.csv',
 '08_figures/fig_state_map_v6_data.csv','08_figures/fig_capture_scatter_v6_data.csv','08_figures/fig_capture_map_v6_data.csv',
 '08_figures/fig_applicability_matrix_v6_data.csv','08_figures/fig_recovery_bounds_v6_data.csv','08_figures/fig_s_pre_comparison_v6_data.csv']
HEX=re.compile(r'(?<![0-9a-zA-Z])[0-9a-fA-F]{16}(?![0-9a-zA-Z])')
PLATE=re.compile(r'[京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼][A-ZＡ-Ｚ][A-Z0-9Ａ-Ｚ０-９·.]{5,7}')
COORD=re.compile(r'(^|_)(lon|lat|longitude|latitude)($|_)',re.I)
ROOT_REPORTS=['README_v6.md','RESULTS_SUMMARY_v6.md','DEVIATIONS_v6.md','EXECUTION_LOG_v6.md','results_v6.json']

def read(rel):return pd.read_csv(ROOT/rel,encoding='utf-8-sig')
def identifier_tokens(text):
    """Exclude a digit-only fractional tail; retain independent16-digit tokens."""
    found=[]
    for m in HEX.finditer(text):
        value=m.group(0);start=m.start()
        decimal_tail=value.isdigit() and start>=2 and text[start-1]=='.' and text[start-2].isdigit()
        if not decimal_tail:found.append(value)
    return found
def excess_precision(value):
    s=str(value).strip()
    if not s or s.upper() in {'NA','NAN','NONE','NULL'}:return False
    try:return Decimal(s).is_finite() and Decimal(s).as_tuple().exponent < -2
    except InvalidOperation:return False
def json_coordinate_precision(text):
    """Preserve lexical decimal precision before testing coordinate fields."""
    def walk(x):
        if isinstance(x,dict):
            return sum(int(excess_precision(v)) if COORD.search(k) and not isinstance(v,(dict,list)) else walk(v) for k,v in x.items())
        if isinstance(x,list):return sum(walk(v) for v in x)
        return 0
    return walk(json.loads(text,parse_float=Decimal))

def main(phase='final'):
    missing=[p for p in REQUIRED if not (ROOT/p).is_file()]
    if phase=='final':missing.extend(p for p in ROOT_REPORTS if not (ROOT/p).is_file())
    if missing:raise RuntimeError('Final audit requires all prescribed result files; missing '+str(len(missing)))
    checks={};details={};hits={k:0 for k in ['hex16','plate_pattern','internal_prefix','original_device_name','coordinate_precision','unreadable_binary']}
    private=pd.read_csv(V1/'01_panels/device_id_map.csv',encoding='utf-8-sig',usecols=['dev_name'])
    names={str(v) for v in private.dev_name.dropna() if str(v)}
    targets=[p for p in ROOT.iterdir() if p.is_file() and p.suffix.lower() in {'.md','.json','.txt','.csv'}]
    for p in ROOT.iterdir():
        if p.is_dir() and (re.match(r'^0[2-9]_',p.name) or p.name=='20_manuscript_fixes'):
            targets.extend(q for q in p.rglob('*') if q.is_file())
    file_stats=[]
    for p in sorted(targets):
        try:s=p.read_text(encoding='utf-8-sig')
        except UnicodeDecodeError:hits['unreadable_binary']+=1;continue
        local=dict(hex16=len(identifier_tokens(s)),plate_pattern=len(PLATE.findall(s)),internal_prefix=s.count('cam_'),
                   original_device_name=sum(s.count(n) for n in names if n in s),coordinate_precision=0)
        if p.suffix.lower()=='.csv':
            reader=csv.DictReader(io.StringIO(s));columns=[c for c in reader.fieldnames or [] if COORD.search(c)]
            for r in reader:
                local['coordinate_precision']+=sum(excess_precision(r.get(c,'')) for c in columns)
        elif p.suffix.lower()=='.json':
            local['coordinate_precision']+=json_coordinate_precision(s)
        else:
            labelled=re.findall(r'(?:longitude|latitude|\blon\b|\blat\b|经度|纬度)["\s]*[:=]\s*([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)',s,re.I)
            local['coordinate_precision']+=sum(excess_precision(v) for v in labelled)
        for k,v in local.items():hits[k]+=v
        file_stats.append(dict(path=p.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),hits=local))
    checks['all_prescribed_outputs_exist']=not missing
    if phase=='final':checks['all_final_root_reports_exist']=all((ROOT/p).is_file() for p in ROOT_REPORTS)
    checks['independent_public_privacy_zero_hits']=all(v==0 for v in hits.values())
    state=read('02_device_state/device_state_v6.csv');counts=read('02_device_state/T27_state_summary.csv')
    checks['T27_ten_dates_and_complete_states']=set(state.date)==set(D_STATE) and len(state)==12210 and len(counts)==70
    daily=read('03_taxi_probe/T28_probe_daily_v6.csv');rings=read('03_taxi_probe/T28_probe_by_ring_v6.csv')
    expected=pd.date_range('2021-07-06','2021-08-02').strftime('%Y-%m-%d').tolist()
    checks['T28_28_dates']=daily.date.tolist()==expected
    checks['T28_five_rings_all_dates']=len(rings)==140 and not rings.duplicated(['date','ring']).any()
    checks['T28_no_GPS_august1_2_NA']=daily.loc[daily.date.isin(['2021-08-01','2021-08-02']),['km','c_all','c_stable']].isna().all().all()
    checks['T28_July25_marked_matched']=daily.loc[daily.date.eq('2021-07-25'),'hour_matched'].eq(1).all()
    cap=read('03_taxi_probe/T29_camera_capture_v6.csv');cal=json.loads((ROOT/'03_taxi_probe/T29_calibration_v6.json').read_text(encoding='utf-8-sig'))
    checks['T29_five_dates']=set(cap.date)=={'2021-07-19','2021-07-26','2021-07-27','2021-07-28','2021-08-02'}
    checks['T29_August2_capture_unavailable']=cap.loc[cap.date.eq('2021-08-02'),'cap'].isna().all()
    checks['T29_finite_capture_in_unit_interval']=cap.cap.dropna().between(0,1).all()
    if cal.get('S2') or cal.get('S3'):
        checks['T29_stop_condition_report_only']=cap.report_only.astype(str).str.lower().isin(['true','1']).all()
    checks['T29_exact_nine_parameter_combinations']=len(cal['parameter_grid'])==9
    leave=read('04_leaveout/T30_leaveout_structured_v6.csv')
    checks['T30_prespecified_replicate_counts']=leave.loc[leave.variant.eq('all_200'),'n_reps'].eq(200).all() and leave.loc[leave.variant.eq('fixed_point'),'n_reps'].eq(1).all() and leave.loc[leave.variant.eq('perturbed_199'),'n_reps'].eq(199).all()
    checks['T30_all112_primary_cells']=int(leave.variant.eq('all_200').sum())==112
    bounds=read('05_bounds/T31_recovery_bounds_v6.csv');pre=read('06_s_pre/T32_s_pre_v6.csv')
    checks['T31_all9_event_dates']=set(bounds.date)==set(EVENT) and len(bounds)==9
    checks['T32_all9_event_dates']=set(pre.date)==set(EVENT) and len(pre)==9
    recovery=read('07_consequences/T33_recovery_date_by_estimator_v6.csv')
    checks['T33_4threshold_7estimator_cells']=len(recovery)==28
    fixes=read('20_manuscript_fixes/T34_manuscript_fact_fixes_v6.csv')
    checks['T34_ten_prespecified_claims']=len(fixes)==10
    old=json.loads((ROOT/'00_env/spatial_postrun_audit_v6.json').read_text(encoding='utf-8-sig'))
    checks['prior_I1_I6_35check_audit_passed']=old['all_passed'] and old['n_checks']==35
    failed=[str(k) for k,v in checks.items() if not v]
    result=dict(ended=now(),phase=phase,all_passed=not failed,n_checks=len(checks),failed=failed,checks=checks,public_privacy_hits=hits,
        publication_files=len(file_stats),files=file_stats,root_reports_present=[p for p in ROOT_REPORTS if (ROOT/p).is_file()],
        scope=('Scientific tables and figure-source snapshot before final root reports; final publication recheck required. ' if phase=='scientific' else 'Final existing publication surfaces including all root reports. ')+
        'No source/key reads; no result mutation; no private matches emitted')
    report='scientific_tables_independent_spatial_audit_v6.json' if phase=='scientific' else 'public_independent_spatial_audit_v6.json'
    write_json(ROOT/'00_env'/report,result)
    print(json.dumps(dict(all_passed=not failed,n_checks=len(checks),failed=failed,privacy_hits=hits,publication_files=len(file_stats))))
    if failed:raise AssertionError('Independent public completeness/privacy audit failed')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['scientific','final'],default='final')
    main(parser.parse_args().phase)
