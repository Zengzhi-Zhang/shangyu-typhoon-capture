# -*- coding: utf-8 -*-
"""Propagate calibration context to standalone aggregate CSVs; no recalculation."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[2]), str(_ReleasePath(__file__).resolve().parents[0])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from pathlib import Path
import json,time
import pandas as pd
from taxi_parse_v6 import OUT,NOW
def main():
    start=NOW();tick=time.monotonic();pub=OUT/'03_taxi_probe';cal=json.loads((pub/'T29_calibration_v6.json').read_text(encoding='utf-8'))
    if 'parameter_grid' not in cal:raise RuntimeError('capture_grid_not_complete')
    names=[pub/'T29_summary_v6.csv',pub/'T29_parameter_grid_v6.csv',OUT/'08_figures/fig_capture_scatter_v6_data.csv']
    for path in names:
        f=pd.read_csv(path,encoding='utf-8-sig',dtype=str,keep_default_na=False)
        f['report_only']=not cal['camera_results_enter_judgement'];f['calibration_status']=cal['calibration_status'];f['calibration_failed']=cal['S2'];f['S3']=cal['S3'];f.to_csv(path,index=False,encoding='utf-8-sig')
    result=dict(start=start,end=NOW(),seconds=time.monotonic()-tick,complete=True,source_reads=False,key_reads=False,values_recalculated=False,report_only=not cal['camera_results_enter_judgement'],calibration_status=cal['calibration_status'],files=[p.name for p in names],command=_release_path('path_021'))
    (OUT/'00_env/capture_report_only_decoration_v6.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
if __name__=='__main__':main()
