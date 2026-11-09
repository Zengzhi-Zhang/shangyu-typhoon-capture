# -*- coding: utf-8 -*-
"""Independent aggregate-only T29 stop/degradation audit; no source/cache reads."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[3]), str(_ReleasePath(__file__).resolve().parents[1]), str(_ReleasePath(__file__).resolve().parent)]
import json
from itertools import product
import numpy as np
import pandas as pd
from spatial_helpers_v6 import ROOT, now, write_json


def main():
    def load(rel):
        return json.loads((ROOT/rel).read_text(encoding='utf-8-sig'))
    cal=load('03_taxi_probe/T29_calibration_v6.json')
    summary=load('03_taxi_probe/T29_summary_v6.json')
    execution=load('00_env/capture_execution_v6.json')
    grid=cal['parameter_grid'];keys=[(x['radius_m'],x['window_seconds']) for x in grid]
    med=np.array([x['control_median_cap'] for x in grid],dtype=float)
    default=next(x for x in grid if (x['radius_m'],x['window_seconds'])==(60,180))
    checks={
        'exact_nine_prespecified_parameter_cells': len(keys)==9 and set(keys)==set(product([40,60,100],[120,180,300])),
        'all_nine_control_medians_available': bool(np.isfinite(med).all()),
        'all_nine_control_medians_below_060': bool((med<.6).all()),
        'S3_matches_prespecified_control_rule': bool(cal['S3'])==bool(np.isfinite(med).all() and (med<.4).all()),
        'default_retained_when_no_eligible_upgrade': (cal['selected_radius_m'],cal['selected_window_seconds'])==(60,180) and not cal['parameter_upgraded'],
        'selected_control_median_matches_default_cell': abs(cal['control_day_median_cap']-default['control_median_cap'])<1e-12,
        'S2_matches_retained_coordinate_control_distance': bool(cal['S2'])==bool(cal['selected']['median']>60),
        'coordinate_failure_status_explicit': cal['calibration_status']=='failed_preserve_raw' and cal['raw_fallback'] and not cal['correction_applied'],
        'postdata_fallback_correction_explicit': bool(cal['postdata_implementation_correction']) and 'post-data' in cal['candidate_policy'],
        'raw_fallback_is_best_available_eligible_control_candidate': cal['selected_method']=='raw_WGS84' and not cal['constant_eligible'] and cal['raw']['median']<cal['GCJ02_to_WGS84']['median'],
        'camera_results_excluded_from_judgement': not cal['camera_results_enter_judgement'] and summary['camera_results_report_only'],
        'summary_stops_match_calibration': summary['stop_conditions']['S2']==cal['S2'] and summary['stop_conditions']['S3']==cal['S3'],
        'signed_and_absolute_change_separately_reported': 'median' in summary['B'] and 'median_absolute_change' in summary['B'],
        'low_probe_exposure_context_does_not_claim_no_traffic': 'does not prove no traffic' in summary['A']['expected_lt3_context'],
        'no_GPS_august2_explicit': summary['missing_august2']=='no_GPS_not_zero_expected',
        'execution_and_public_summary_match': execution['summary']==summary,
    }
    paths=['03_taxi_probe/T29_camera_capture_v6.csv','03_taxi_probe/T29_summary_v6.csv',
           '08_figures/fig_capture_map_v6_data.csv','08_figures/fig_capture_scatter_v6_data.csv']
    sizes={}
    for rel in paths:
        data=pd.read_csv(ROOT/rel,encoding='utf-8-sig',dtype=str,keep_default_na=False)
        sizes[rel]=len(data)
        checks[rel+'_all_report_only']=data.report_only.str.lower().eq('true').all()
        checks[rel+'_all_calibration_failed']=data.calibration_failed.str.lower().eq('true').all()
        checks[rel+'_failure_status_explicit']=data.calibration_status.eq(cal['calibration_status']).all()
    cap=pd.read_csv(ROOT/paths[0],encoding='utf-8-sig',dtype=str,keep_default_na=False)
    small=cap.expected.eq('<10');nogps=cap.date.eq('2021-08-02')
    checks['small_expected_all_three_counts_suppressed']=cap.loc[small,['expected','captured','captured_unexpected']].eq('<10').all().all()
    checks['small_expected_capture_NA']=cap.loc[small,'cap'].eq('NA').all()
    checks['august2_all_capture_fields_NA']=cap.loc[nogps,['expected','captured','captured_unexpected','cap']].eq('NA').all().all()
    failed=[k for k,v in checks.items() if not v]
    report=dict(ended=now(),all_passed=not failed,n_checks=len(checks),failed=failed,checks=checks,
        rows=sizes,control_default_median=cal['control_day_median_cap'],control_grid_min=float(med.min()),
        control_grid_max=float(med.max()),selected_coordinate_median_m=cal['selected']['median'],
        S2=cal['S2'],S3=cal['S3'],interpretation='All camera-level results are descriptive only; no hardware or true-traffic identification.',
        scope='Final local T29 publication tables/figure-source CSVs and aggregate JSON only; no source, key or GPS/AVI cache reads; no result mutation')
    write_json(ROOT/'00_env/capture_degradation_independent_spatial_audit_v6.json',report)
    print(json.dumps(dict(all_passed=not failed,n_checks=len(checks),failed=failed,control_default_median=cal['control_day_median_cap'],S2=cal['S2'],S3=cal['S3'])))
    if failed:raise AssertionError('Independent T29 degradation audit failed')


if __name__=='__main__':main()
