# -*- coding: utf-8 -*-
"""Final local parsing audit. No workbook, filename mapping, or key access."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[3]), str(_ReleasePath(__file__).resolve().parents[1])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from pathlib import Path
from datetime import datetime,timezone,timedelta
import json
import pandas as pd
import pyarrow.parquet as pq

R=Path(_release_path('v6_root'));I=R/'01_internal';E=R/'00_env'


def main():
    files=list((I/'taxi_gps_points').glob('*.parquet'))
    checkpoints=[json.loads(p.read_text(encoding='utf-8')) for p in (I/'taxi_parse_checkpoints').glob('*.json')]
    execution=json.loads((E/'taxi_parse_execution_v6.json').read_text(encoding='utf-8'))
    daily=pd.read_csv(I/'taxi_vehicle_day_v6.csv',encoding='utf-8-sig')
    validation=pd.read_csv(E/'taxi_parse_daily_validation_v6.csv',encoding='utf-8-sig')
    independent=json.loads((E/'taxi_actualdate_point_validation_v6.json').read_text(encoding='utf-8'))
    auxiliary=json.loads((E/'taxi_legacy_sheet_reconciliation_v6.json').read_text(encoding='utf-8'))
    metadata=json.loads((E/'taxi_row_metadata_fix_execution_v6.json').read_text(encoding='utf-8'))
    allowed={'timestamp','date','lon','lat','speed','heading','state','transmit','valid_xy','moving','occupied'}
    rows=sum(pq.read_metadata(p).num_rows for p in files)
    counters={key:sum(x['counters'].get(key,0) for x in checkpoints) for key in ['rows','source_rows','sheets_seen','selected_cells','unselected_cells_skipped','sst_entries','sst_decoded','bad_time','date_sheet_mismatch']}
    dates={f'2021-07-{d:02d}' for d in range(6,32)}
    original_acceptance=bool(validation.rel_difference.notna().all() and validation.rel_difference.le(.01).all())
    checks=dict(workbooks_and_checkpoints_complete=len(files)==len(checkpoints)==290 and all(c['complete'] for c in checkpoints),no_partial_GPS_files=not list((I/'taxi_gps_points').glob('*.partial.parquet')),GPS_permitted_derived_columns_only=all(set(pq.read_schema(p).names)==allowed for p in files),GPS_row_totals_equal=rows==counters['rows']==int(daily.n_parsed_time.sum())==execution['GPS_rows'],analysis_date_domain_exact=set(daily.date)==dates,no_duplicate_vehicle_day=not daily.duplicated(['vehicle_ph','date']).any(),legacy_validation_26_dates=set(validation.date)==dates and len(validation)==26,original_legacy_acceptance_truthfully_preserved=original_acceptance==execution['legacy_daily_distance_within_1pct'],independent_actual_date_points_equal=bool(independent['all_26_actual_valid_point_counts_equal']),auxiliary_legacy_sheet_reproduced=bool(auxiliary['complete'] and auxiliary['legacy_sheet_daily_distance_within_1pct'] and auxiliary['source_metadata_unchanged']),row_metadata_correction_integrity=bool(metadata['all_passed']))
    count_differences=validation.loc[(validation.vehicle_day_count_difference!=0)|(validation.source_row_count_difference!=0),['date','vehicle_day_count_difference','source_row_count_difference']].to_dict('records')
    result=dict(at=datetime.now(timezone(timedelta(hours=8))).isoformat(),source_reads=False,key_reads=False,all_passed=all(checks.values()),checks=checks,acceptance=dict(original_actual_vs_legacy_daily_km_within_1pct=original_acceptance,auxiliary_sheet_vs_legacy_daily_km_within_1pct=auxiliary['legacy_sheet_daily_distance_within_1pct']),counters=counters,daily_rows=len(daily),GPS_rows=rows,domain_source_rows=int(daily.n_rows.sum()),max_daily_km_relative_difference=float(validation.rel_difference.max()),legacy_outside_analysis_dates=execution.get('legacy_outside_analysis_dates',[]),vehicle_day_or_source_row_differences=count_differences,worker_failures=execution.get('failures',[]),original_nonzero_exit_codes=[1,1])
    (E/'taxi_parse_final_checks_v6.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False))
    if not result['all_passed']:raise SystemExit(1)
if __name__=='__main__':main()
