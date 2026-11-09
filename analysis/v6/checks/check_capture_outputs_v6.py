# -*- coding: utf-8 -*-
"""Aggregate and schema audit after capture; no raw source or key access."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[3]), str(_ReleasePath(__file__).resolve().parents[1])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from pathlib import Path
from datetime import datetime,timezone,timedelta
import json,re
import numpy as np,pandas as pd
R=Path(_release_path('v6_root'));I=R/'01_internal';P=R/'03_taxi_probe'

def main():
    internal=pd.read_csv(I/'camera_capture_unmasked_v6.csv',encoding='utf-8-sig')
    public=pd.read_csv(P/'T29_camera_capture_v6.csv',encoding='utf-8-sig',dtype=str,keep_default_na=False)
    gps=pd.read_csv(I/'taxi_vehicle_day_v6.csv',encoding='utf-8-sig')
    cal=json.loads((P/'T29_calibration_v6.json').read_text(encoding='utf-8'))
    execution=json.loads((R/'00_env/capture_execution_v6.json').read_text(encoding='utf-8'))
    same_keys=len(public)==len(internal) and np.array_equal(pd.to_numeric(public.dev).to_numpy(),internal.dev.to_numpy()) and np.array_equal(public.date.to_numpy(),internal.date.to_numpy())
    if not same_keys:raise RuntimeError('public_internal_camera_date_order_mismatch')
    mask=internal.expected.notna()&internal.expected.lt(10);nogps=internal.date.eq('2021-08-02')
    checks={'public_internal_camera_date_order_equal':same_keys}
    checks['captured_le_expected']=bool(internal.loc[~nogps,'captured'].le(internal.loc[~nogps,'expected']).all())
    checks['public_small_expected_all_counts_suppressed']=bool(public.loc[mask,['expected','captured','captured_unexpected']].eq('<10').all().all())
    checks['public_small_expected_cap_NA']=bool(public.loc[mask,'cap'].eq('NA').all())
    checks['august2_all_capture_counts_NA']=bool(public.loc[nogps,['expected','captured','captured_unexpected','cap']].eq('NA').all().all())
    values=public[['expected','captured','captured_unexpected']].to_numpy().ravel()
    checks['public_event_counts_integer_or_suppressed']=all(x in ('NA','<10') or re.fullmatch(r'\d+',x) for x in values)
    checks['parameter_grid_complete']=len(cal['parameter_grid'])==9
    checks['selected_calibration_not_worse_than_raw']=cal['selected']['median']<=cal['raw']['median']+1e-9
    checks['S2_matches_selected_or_raw_residual_threshold']=cal['S2']==(cal['selected']['median']>60)
    checks['camera_report_only_context_consistent']=bool(internal.report_only.eq(not cal['camera_results_enter_judgement']).all())
    for name in ['T29_summary_v6.csv','T29_parameter_grid_v6.csv']:
        f=pd.read_csv(P/name,encoding='utf-8-sig')
        checks[name+'_report_only_context']=bool(f.report_only.eq(not cal['camera_results_enter_judgement']).all() and f.calibration_status.eq(cal['calibration_status']).all())
    grid=cal['parameter_grid'];default=next(x for x in grid if x['radius_m']==60 and x['window_seconds']==180)
    chosen=(60,180)
    if default['control_median_cap'] is None or default['control_median_cap']<.6:
        eligible=[x for x in grid if x['control_median_cap'] is not None and x['control_median_cap']>=.6]
        if eligible:
            best=sorted(eligible,key=lambda x:(-x['control_median_cap'],x['radius_m'],x['window_seconds']))[0];chosen=(best['radius_m'],best['window_seconds'])
    checks['frozen_parameter_choice_reproduced']=chosen==(cal['selected_radius_m'],cal['selected_window_seconds'])
    checks['bootstrap_dimensions']=execution['checks']['bootstrap_vehicle_draws'] in (0,200) and execution['checks']['bootstrap_camera_draws'] in (0,500)
    pair=internal[internal.date.eq('2021-07-26')].merge(internal[internal.date.eq('2021-07-19')],on='dev',suffixes=('_26','_19'))
    stable=pair[pair.eligible_expected_ge10_26&pair.eligible_expected_ge10_19&pair.in_Sstar_26]
    actual=float(np.median(np.abs(stable.cap_26-stable.cap_19))) if len(stable) else None
    reported=execution['summary']['B']['median_absolute_change']
    checks['B_median_absolute_change_matches_paired_cells']=(actual is None and reported is None) or (actual is not None and reported is not None and abs(actual-reported)<.00015)
    rings=['0-2','2-4','4-7','7-12','12+']
    for prefix,total in [('km_total_ring_','dist_km'),('km_moving_ring_','dist_moving_km'),('km_ring_','dist_moving_km'),('km_ring_h11_','km_from_11h'),('km_moving_ring_h11_','km_moving_from_11h'),('pts_ring_','n_valid_xy')]:
        err=(gps[[prefix+x for x in rings]].sum(axis=1)-gps[total]).abs().max();checks[prefix+'conserves_'+total]=bool(err<.00004)
    checks['moving_h11_ring_le_total_h11_ring']=all(gps['km_moving_ring_h11_'+x].le(gps['km_ring_h11_'+x]+.000002).all() for x in rings)
    ring=pd.read_csv(I/'taxi_ring_records_v6.csv',encoding='utf-8-sig');hashdaily=pd.read_csv(P/'hash_daily_check_v6.csv',encoding='utf-8-sig').set_index('date')
    r=ring.groupby('date').sum(numeric_only=True).reindex(hashdaily.index,fill_value=0)
    checks['ring_records_all_equal_hash_panel']=bool(r.rec_all.eq(hashdaily.rec_all).all())
    checks['ring_records_stable_equal_hash_panel']=bool(r.rec_stable.eq(hashdaily.rec_stable).all())
    checks['ring_online_le_all']=bool(ring.rec_online.le(ring.rec_all).all())
    checks['ring_h11_le_all']=bool(ring.rec_all_h11.le(ring.rec_all).all())
    failures=[]
    for path in [P/'T29_camera_capture_v6.csv',P/'T29_summary_v6.csv',P/'T29_calibration_v6.json',R/'08_figures/fig_capture_map_v6_data.csv',R/'08_figures/fig_capture_scatter_v6_data.csv']:
        s=path.read_text(encoding='utf-8-sig')
        hits=[]
        for match in re.finditer(r'(?<![A-Za-z0-9])[0-9a-f]{16}(?![A-Za-z0-9])|cam_',s):
            # A legal numeric decimal fraction can have exactly sixteen digits.
            # Standalone sixteen-digit integers and any a-f token remain checked.
            if match.group().isdigit() and re.search(r'\d\.$',s[:match.start()]):continue
            hits.append(match.group())
        if hits:failures.append(path.name)
    checks['no_public_alias_tokens']=not failures
    coord=pd.read_csv(R/'08_figures/fig_capture_map_v6_data.csv',dtype=str,encoding='utf-8-sig')
    checks['public_coordinate_strings_two_decimals']=bool(coord.lon.str.fullmatch(r'-?\d+\.\d{2}').all() and coord.lat.str.fullmatch(r'-?\d+\.\d{2}').all())
    import pyarrow.parquet as pq
    expected={'timestamp','date','lon','lat','speed','heading','state','transmit','valid_xy','moving','occupied'}
    files=list((I/'taxi_gps_points').glob('*.parquet'));checks['GPS_cache_290_files']=len(files)==290
    checks['GPS_cache_permitted_schema_only']=all(set(pq.read_schema(p).names)==expected for p in files)
    result=dict(at=datetime.now(timezone(timedelta(hours=8))).isoformat(),source_reads=False,key_reads=False,checks=checks,all_passed=all(checks.values()),public_alias_failure_files=failures)
    (R/'00_env/capture_independent_checks_v6.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False))
    if not result['all_passed']:raise SystemExit(1)
if __name__=='__main__':main()
