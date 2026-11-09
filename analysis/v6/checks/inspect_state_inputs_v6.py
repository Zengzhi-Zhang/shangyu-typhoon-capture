# -*- coding: utf-8 -*-
"""Structure-only inspection. No source, key, device identity or event statistic output."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[3]), str(_ReleasePath(__file__).resolve().parents[1])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from pathlib import Path
from datetime import datetime, timezone, timedelta
import json
import pandas as pd

V1 = Path(_release_path('project_root'))
ROOT = V1 / 'formal_v6'
PATHS = [
    V1/'01_panels/device_attributes.csv', V1/'01_panels/device_hour.csv',
    V1/'01_panels/device_day.csv', V1/'01_panels/device_dir_lane_day.csv',
    V1/'formal_v3/06_m5_bias_correction/m5_failure_counts_v3.csv',
    V1/'formal_v3/06_m5_bias_correction/m5_failure_persistence_calendar_v3.csv',
    V1/'formal_v3/06_m5_bias_correction/m5_failure_profile_v3.csv',
    V1/'formal_v3/05_m4_spatial/m4_ols_v3.csv',
    V1/'formal_v3/06_m5_bias_correction/m5_visible_bias_v3.csv',
]

def main():
    rows=[]
    for p in PATHS:
        st=p.stat()
        cols=pd.read_csv(p,encoding='utf-8-sig',nrows=0).columns.tolist()
        rows.append(dict(path=str(p),size=st.st_size,mtime_ns=st.st_mtime_ns,columns=cols))
    report=dict(stage='structure_only_before_protocol_freeze',generated_at=datetime.now(timezone(timedelta(hours=8))).isoformat(),
                numerical_analysis_run=False,raw_source_accessed=False,key_accessed=False,files=rows,
                note='Headers and local file metadata only; no row contents or restricted identifiers printed.')
    out=ROOT/'00_env/spatial_input_structure_v6.json';out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':main()
