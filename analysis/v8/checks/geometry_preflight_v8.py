# -*- coding: utf-8 -*-
"""Cached metadata only; no geometry effects and no OSM access."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[3]), str(_ReleasePath(__file__).resolve().parents[1])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from pathlib import Path
import importlib.util
import json
import pandas as pd
import pyarrow.parquet as pq

R=Path(_release_path('project_root'))
def main():
    a=R/'formal_v6/01_internal/taxi_avi_records_v6.parquet'
    paths=sorted((R/'formal_v6/01_internal/taxi_gps_points').glob('*.parquet'))
    info=dict(AVI_schema=str(pq.ParquetFile(a).schema_arrow),GPS_schema=str(pq.ParquetFile(paths[0]).schema_arrow),
              GPS_files=len(paths),AVI_rows=pq.ParquetFile(a).metadata.num_rows,
              attrs_columns=pd.read_csv(R/'01_panels/device_attributes.csv',nrows=0).columns.tolist(),
              state_columns=pd.read_csv(R/'formal_v7/01_internal/device_state_internal_v7.csv',nrows=0).columns.tolist(),
              selection_columns=pd.read_csv(R/'formal_v7/01_internal/capture_selection_internal_v7.csv',nrows=0).columns.tolist(),
              libraries={x:bool(importlib.util.find_spec(x)) for x in ['geopandas','shapely','matplotlib','fiona','pyogrio']},
              direction_labels=pd.read_parquet(a,columns=['dir']).dir.value_counts(dropna=False).to_dict(),
              source_reads=False,key_reads=False,effects_computed=False,
              initial_shell_launch_exit_code=1,initial_shell_failure='PowerShell to Git Bash nested quotation; Python analysis did not start')
    (R/'formal_v8/00_env').mkdir(parents=True,exist_ok=True)
    (R/'formal_v8/00_env/geometry_preflight_v8.json').write_text(json.dumps(info,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf-8')
    print(json.dumps(info,ensure_ascii=False,default=str))

if __name__=='__main__':main()
