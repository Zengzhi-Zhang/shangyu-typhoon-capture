# -*- coding: utf-8 -*-
"""Correct source-sheet row metadata after auxiliary reconciliation only."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[2]), str(_ReleasePath(__file__).resolve().parents[0])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from pathlib import Path
import hashlib,json,time
import pandas as pd
from taxi_parse_v6 import INTERNAL,OUT,NOW,SafeParseError


def GPS_digest():
    digest=hashlib.sha256();files=sorted((INTERNAL/'taxi_gps_points').glob('*.parquet'))
    if len(files)!=290:raise SafeParseError('row_metadata_requires290_GPS_files')
    for path in files:
        digest.update(path.name.encode());digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def frame_digest(frame):
    return hashlib.sha256(frame.to_csv(index=False,float_format='%.6f',na_rep='NA').encode()).hexdigest()


def main():
    start=NOW();tick=time.monotonic();env=OUT/'00_env';report=json.loads((env/'taxi_legacy_sheet_reconciliation_v6.json').read_text(encoding='utf-8'))
    if not (report['complete'] and report['legacy_sheet_daily_distance_within_1pct'] and report['source_metadata_unchanged']):raise SafeParseError('row_metadata_requires_successful_auxiliary')
    path=INTERNAL/'taxi_vehicle_day_v6.csv';before=pd.read_csv(path,encoding='utf-8-sig');aux=pd.read_csv(INTERNAL/'taxi_legacy_sheet_vehicle_day_v6.csv',encoding='utf-8-sig')
    if aux.duplicated(['vehicle_ph','date']).any():raise SafeParseError('duplicate_auxiliary_source_sheet')
    backup=INTERNAL/'taxi_vehicle_day_before_nrows_fix_v6.csv'
    if backup.exists():raise SafeParseError('row_metadata_fix_already_has_backup')
    backup.write_bytes(path.read_bytes());GPS_before=GPS_digest()
    other=[c for c in before if c!='n_rows'];nonmetadata_before=frame_digest(before[other])
    source=aux.set_index(['vehicle_ph','date']).n_rows
    index=pd.MultiIndex.from_frame(before[['vehicle_ph','date']]);new=before.copy()
    new['n_rows']=source.reindex(index).fillna(0).to_numpy(dtype='int64')
    new['n_source_sheet_rows']=new.n_rows;new['n_actual_timestamp_rows']=new.n_parsed_time.astype('int64')
    if not before[other].equals(new[other]):raise SafeParseError('row_metadata_changed_other_field')
    temp=path.with_suffix('.metadata.partial.csv');new.to_csv(temp,index=False,encoding='utf-8-sig',float_format='%.6f');temp.replace(path)
    after=pd.read_csv(path,encoding='utf-8-sig');GPS_after=GPS_digest();nonmetadata_after=frame_digest(after[other])
    checks=dict(nonmetadata_columns_identical=nonmetadata_before==nonmetadata_after,GPS_content_SHA_unchanged=GPS_before==GPS_after,source_sheet_alias_exact=bool(after.n_rows.eq(after.n_source_sheet_rows).all()),actual_timestamp_alias_exact=bool(after.n_parsed_time.eq(after.n_actual_timestamp_rows).all()),missing_sheet_n_rows_zero=bool(after.loc[~index.isin(source.index),'n_rows'].eq(0).all()),actual_dates_unchanged=bool(before.date.equals(after.date)))
    a=before.groupby('date').agg(before_n_rows=('n_rows','sum'),before_actual_rows=('n_parsed_time','sum'),before_km=('dist_km','sum'))
    b=after.groupby('date').agg(after_n_source_sheet_rows=('n_source_sheet_rows','sum'),after_n_actual_timestamp_rows=('n_actual_timestamp_rows','sum'),after_km=('dist_km','sum'))
    a.join(b).reset_index().to_csv(env/'taxi_row_metadata_before_after_v6.csv',index=False,encoding='utf-8-sig',float_format='%.6f')
    output=dict(start=start,end=NOW(),seconds=time.monotonic()-tick,complete=True,command=_release_path('path_022'),source_reads=False,key_reads=False,checks=checks,all_passed=all(checks.values()),changed_n_rows_entries=int(before.n_rows.ne(after.n_rows).sum()),old_n_rows_total=int(before.n_rows.sum()),n_source_sheet_rows_total=int(after.n_source_sheet_rows.sum()),n_actual_timestamp_rows_total=int(after.n_actual_timestamp_rows.sum()),all_source_rows=17211405,actual_timestamp_outside_analysis_domain=2006,source_sheet_outside_analysis_domain_rows=1999,GPS_content_sha256_before=GPS_before,GPS_content_sha256_after=GPS_after,nonmetadata_columns_sha256_before=nonmetadata_before,nonmetadata_columns_sha256_after=nonmetadata_after,meaning='n_rows=n_source_sheet_rows counts original sheet calendar label,zero when no such sheet. n_actual_timestamp_rows=n_parsed_time counts actual timestamp date. These have different date assignments and n_rows is not actual-date exposure.',original_actual_legacy_1pct_passed=False)
    (env/'taxi_row_metadata_fix_execution_v6.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in output.items() if 'sha256' not in k}))
    if not output['all_passed']:raise SafeParseError('row_metadata_fix_integrity_failed')

if __name__=='__main__':main()
