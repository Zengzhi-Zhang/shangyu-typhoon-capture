# -*- coding: utf-8 -*-
"""Display-roundtrip check only; does not recompute any scientific result."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[3]), str(_ReleasePath(__file__).resolve().parents[1])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from pathlib import Path
from datetime import datetime,timezone,timedelta
import json,time,hashlib
import numpy as np,pandas as pd

B=Path(_release_path('project_root'));R=_ReleasePath(_release_path('v9_output_root'))


def main():
    start=datetime.now(timezone(timedelta(hours=8))).isoformat();tick=time.monotonic()
    path=B/'formal_v7/03_taxi_probe/T35_capture_camera_v7.csv'
    cols=['variant','date','selected','A1_failed','expected','cap_ctrl_matched']
    public=pd.read_csv(path,usecols=cols,encoding='utf-8-sig',dtype=str,keep_default_na=False)
    flag=lambda s:s.str.lower().isin(['true','1'])
    n=pd.to_numeric(public.expected,errors='coerce')
    subset=public[public.variant.eq('main_R60_cap03')&public.date.eq('2021-07-26')&flag(public.selected)&flag(public.A1_failed)&n.ge(10)].copy()
    expected=pd.to_numeric(subset.expected,errors='raise');cap=pd.to_numeric(subset.cap_ctrl_matched,errors='raise')
    rounded_E=float((expected*cap).sum())
    internal=pd.read_csv(R/'01_internal/capture_expected_internal_v9.csv',encoding='utf-8-sig').set_index('date')
    raw_E=float(internal.loc['2021-07-26','E']);difference=rounded_E-raw_E
    checks=dict(n64=len(subset)==64,all64_finite_caps=bool(np.isfinite(cap).all()),expected_total14335=int(expected.sum())==14335,
        difference_from_unrounded_within15=abs(difference)<15,
        frozen_protocol_unchanged=hashlib.sha256((R/'00_env/protocol_frozen_v9.json').read_bytes()).hexdigest()==json.loads((R/'00_env/capture_execution_v9.json').read_text(encoding='utf-8'))['protocol_sha256'])
    report=dict(start=start,end=datetime.now(timezone(timedelta(hours=8))).isoformat(),seconds=time.monotonic()-tick,
        command=_release_path('path_044'),
        source='formal_v7/03_taxi_probe/T35_capture_camera_v7.csv',date='2021-07-26',variant='main_R60_cap03',n_report_cameras=len(subset),
        event_expected_sum=int(expected.sum()),E_from_public_four_decimal_caps=rounded_E,E_from_existing_unrounded_internal=raw_E,
        public_minus_internal=difference,absolute_difference=abs(difference),
        scientific_results_modified=False,effects_or_bootstrap_recomputed=False,source_data_reads=False,key_reads=False,
        checks=checks,all_passed=all(checks.values()),
        note='Only a public-display roundtrip: cap_ctrl_matched is stored at four decimals. T40 result continues to use unchanged unrounded control counts. No retuning or substitution.')
    (R/'00_env/capture_public_roundtrip_v9.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(all_passed=report['all_passed'],n=len(subset),public_E=rounded_E,internal_E=raw_E,difference=difference)))
    if not report['all_passed']:raise RuntimeError('public_display_roundtrip_check_failed')


if __name__=='__main__':main()
