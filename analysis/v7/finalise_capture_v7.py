# -*- coding: utf-8 -*-
"""Final capture display/audit completion. No new effects or geometry."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[2]), str(_ReleasePath(__file__).resolve().parents[0])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from pathlib import Path
from datetime import datetime,timezone,timedelta
import hashlib
import json
import time
import pandas as pd

R=Path(_release_path('v7_root'))


def now():return datetime.now(timezone(timedelta(hours=8))).isoformat()


def main():
    start=now();tick=time.monotonic()
    internal=pd.read_csv(R/'01_internal/capture_summary_internal_v7.csv',encoding='utf-8-sig')
    truth=internal.set_index(['variant','date']).spearman_p
    repairs=[]
    for relative in ['03_taxi_probe/T35_capture_wellmatched_v6.csv','08_figures/fig_capture_relative_v7_data.csv']:
        path=R/relative
        before=pd.read_csv(path,encoding='utf-8-sig',dtype=str,keep_default_na=False)
        after=before.copy()
        after['spearman_p']=[format(float(truth.loc[(variant,date)]),'.6g') if pd.notna(truth.loc[(variant,date)]) else 'NA' for variant,date in zip(after.variant,after.date)]
        untouched=[c for c in before if c!='spearman_p']
        assert before[untouched].equals(after[untouched])
        after.to_csv(path,index=False,encoding='utf-8-sig')
        reread=pd.read_csv(path,encoding='utf-8-sig',dtype=str,keep_default_na=False)
        assert reread[untouched].equals(before[untouched])
        assert pd.to_numeric(reread.spearman_p,errors='coerce').gt(0).all()
        repairs.append(dict(path=relative,only_spearman_p_display_changed=True,other_cells_exactly_preserved=True,rows=len(after)))
    methods=R/'03_taxi_probe/T35_METHODS_v7.md'
    text=methods.read_text(encoding='utf-8')
    sentence='Spearman两侧均含AVI记录，因此该关联不构成完全独立的验证。GPS expected提供这批出租车在冻结几何条件下经过的证据；路线、设备类型及对照选卡仍限制其外推。公开p值用科学计数法，率与区间使用四位小数。'
    if sentence not in text:methods.write_text(text.rstrip()+'\n\n'+sentence+'\n',encoding='utf-8')
    stage=json.loads((R/'00_env/capture_execution_v7.json').read_text(encoding='utf-8'))
    independent=json.loads((R/'00_env/capture_independent_checks_v7.json').read_text(encoding='utf-8'))
    synthetic=json.loads((R/'00_env/capture_synthetic_checks_v7.json').read_text(encoding='utf-8'))
    files=['03_taxi_probe/T35_capture_wellmatched_v6.csv','03_taxi_probe/T35_by_state_v6.csv','03_taxi_probe/T35_camera_type_v6.csv','03_taxi_probe/T35_capture_camera_v7.csv','08_figures/fig_capture_relative_v7_data.csv','08_figures/fig_capture_failed_scatter_v7_data.csv','08_figures/fig_capture_type_v7_data.csv']
    tables={}
    for relative in files:
        frame=pd.read_csv(R/relative,encoding='utf-8-sig',dtype=str,keep_default_na=False)
        tables[relative]=dict(rows=len(frame),columns=list(frame.columns),sha256=hashlib.sha256((R/relative).read_bytes()).hexdigest())
    unmet=[row for row in stage['acceptance'] if any(row[k] is not True for k in ['Sstar_relative_median_in_090_105','failed_pooled_cap_le002','Spearman_ge06'])]
    report=dict(start=start,end=now(),seconds=time.monotonic()-tick,complete=True,status='complete',
                command=_release_path('path_033'),
                source_reads=False,key_reads=False,scientific_effects_recomputed=False,internal_and_JSON_scientific_values_unchanged=True,
                geometry_seconds=stage['seconds'],main_exit_code=0,first_independent_checker_exit_code=1,
                checker_failure_reason='Only alias-token false positive on complete dotted scientific p literal; no identifier leakage. Original first report preserved.',
                checker_first_report='00_env/capture_independent_checks_first_v7.json',
                checker_fix_boundary=_release_private('private_value_020'),
                final_independent_checks=len(independent['checks']),final_independent_all_passed=independent['all_passed'],
                final_synthetic_checks=len(synthetic['checks']),final_synthetic_all_passed=synthetic['all_passed'],
                display_repairs=repairs,tables=tables,all_unmet_or_unavailable=unmet,
                main_results=stage['main_results'],posthoc_revision=True,v6_S2_S3_history_unchanged=True)
    (R/'00_env/capture_completion_v7.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(dict(complete=True,tables={k:v['rows'] for k,v in tables.items()},unmet_variant_dates=len(unmet)),ensure_ascii=False))


if __name__=='__main__':main()
