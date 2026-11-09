# -*- coding: utf-8 -*-
"""Safe local aggregate parser diagnostics. No source workbooks or keys."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[3]), str(_ReleasePath(__file__).resolve().parents[1])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from pathlib import Path
import json
import pandas as pd
R=Path(_release_path('project_root'));V=R/'formal_v6';I=V/'01_internal'
def main():
    cp=[json.loads(p.read_text(encoding='utf-8')) for p in (I/'taxi_parse_checkpoints').glob('*.json')]
    totals={k:sum(c['counters'].get(k,0) for c in cp) for k in ['rows','source_rows','sheets_seen','bad_time','date_sheet_mismatch','sst_entries','sst_decoded']}
    old=pd.read_csv(R/'01_panels/taxi_vehicle_day.csv');old=old[old.batch.eq('GPS0706-0731')].copy();old['date']=pd.to_datetime(old.sheet_date.astype(str).str.replace('-','',regex=False),format='%Y%m%d').dt.strftime('%Y-%m-%d')
    new=pd.read_csv(I/'taxi_vehicle_day_v6.csv',encoding='utf-8-sig');fields=['n_rows','n_parsed_time','n_valid_xy','n_moving','n_occupied','hours_active','dist_km','dist_moving_km','n_jump_segments']
    a=old.groupby('date')[fields].sum().add_prefix('old_').join(new.groupby('date')[fields].sum().add_prefix('new_')).reset_index()
    a.to_csv(V/'00_env/taxi_parse_aggregate_diagnostic_v6.csv',index=False,encoding='utf-8-sig',float_format='%.6f')
    print(json.dumps(dict(counters=totals,all_old_vehicle_days=len(old),new_vehicle_days=len(new),nonzero_timestamp_sheet_mismatch_workbooks=sum(c['counters']['date_sheet_mismatch']>0 for c in cp)),ensure_ascii=False))
    print(a[a.date.isin(['2021-07-06','2021-07-19','2021-07-31'])].to_json(orient='records'))
if __name__=='__main__':main()
