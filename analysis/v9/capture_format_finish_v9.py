# -*- coding: utf-8 -*-
"""Requested output formatting only, without effect/bootstrap recomputation."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[2]), str(_ReleasePath(__file__).resolve().parents[0])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from pathlib import Path
from datetime import datetime,timezone,timedelta
import json,hashlib,time
import pandas as pd
from capture_expected_v9 import save_public

R=Path(_release_path('v9_root'))


def main():
    start=datetime.now(timezone(timedelta(hours=8))).isoformat();tick=time.monotonic()
    path=R/'03_breakeven/T39_audit_coverage_v9.csv'
    old=pd.read_csv(path,dtype=str,keep_default_na=False,encoding='utf-8-sig');before=hashlib.sha256(path.read_bytes()).hexdigest()
    cover=pd.read_csv(R/'01_internal/capture_audit_coverage_internal_v9.csv',encoding='utf-8-sig')
    save_public(cover,path,['n_audited_cameras','event_expected','event_captured','control_expected','control_captured'])
    after=pd.read_csv(path,dtype=str,keep_default_na=False,encoding='utf-8-sig')
    untouched=[c for c in old if c!='n_audited_cameras']
    assert old[untouched].equals(after[untouched])
    numeric_before=pd.to_numeric(old.n_audited_cameras,errors='coerce');numeric_after=pd.to_numeric(after.n_audited_cameras,errors='coerce')
    assert numeric_before.equals(numeric_after)
    extra=R/'04_expected_capture/fig_expected_capture_source_v9.csv'
    removed=extra.exists()
    if removed:extra.unlink()
    record=dict(start=start,end=datetime.now(timezone(timedelta(hours=8))).isoformat(),seconds=time.monotonic()-tick,
        command=_release_path('path_043'),complete=True,
        effect_or_bootstrap_recomputed=False,coverage_numeric_values_unchanged=True,coverage_other_cells_exactly_unchanged=True,
        change='GPS-available n_audited_cameras serialized as integers;8/1 and8/2 NA retained',before_sha256=before,after_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        removed_only_this_new_extra_figure_source=removed,figure_note='Root centrally copies exact public T40 CSV to08_figures; no second copy in04_expected_capture',
        source_reads=False,key_reads=False)
    (R/'00_env/capture_format_finish_v9.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(complete=True,numeric_values_unchanged=True,extra_removed=removed)))


if __name__=='__main__':main()
