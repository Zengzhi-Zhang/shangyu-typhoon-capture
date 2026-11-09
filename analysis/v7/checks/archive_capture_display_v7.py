# -*- coding: utf-8 -*-
"""Archive pre-correction display cells without recalculating any effect."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[3]), str(_ReleasePath(__file__).resolve().parents[1])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from pathlib import Path
from datetime import datetime, timezone, timedelta
import hashlib
import json
import time
import pandas as pd

R = Path(_release_path('v7_root'))


def now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def main():
    started, tick = now(), time.monotonic()
    truth = pd.read_csv(R/'01_internal/capture_summary_internal_v7.csv', encoding='utf-8-sig').set_index(['variant', 'date']).spearman_p
    archive = R/'00_env/capture_display_before'
    archive.mkdir(exist_ok=True)
    changes = []
    for relative in ['03_taxi_probe/T35_capture_wellmatched_v6.csv', '08_figures/fig_capture_relative_v7_data.csv']:
        path = R/relative
        current = pd.read_csv(path, encoding='utf-8-sig', dtype=str, keep_default_na=False)
        previous = current.copy()
        previous['spearman_p'] = [format(float(truth.loc[(v, d)]), '.4f') for v, d in zip(current.variant, current.date)]
        expected_current = [format(float(truth.loc[(v, d)]), '.6g') for v, d in zip(current.variant, current.date)]
        assert current.spearman_p.tolist() == expected_current
        assert current.drop(columns='spearman_p').equals(previous.drop(columns='spearman_p'))
        archived = archive/path.name
        previous.to_csv(archived, index=False, encoding='utf-8-sig')
        changes.append(dict(path=relative, archive=str(archived.relative_to(R)), rows=len(current),
                            unchanged_other_cells=True,
                            before_p_values=previous.spearman_p.tolist(),
                            after_p_values=current.spearman_p.tolist(),
                            current_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                            archive_sha256=hashlib.sha256(archived.read_bytes()).hexdigest()))
    checks = json.loads((R/'00_env/capture_independent_checks_v7.json').read_text(encoding='utf-8'))
    assert checks['all_passed'] and len(checks['checks']) == 19
    report = dict(start=started, end=now(), seconds=time.monotonic()-tick, complete=True,
                  command=_release_path('path_031'),
                  original_pre_correction_bytes_preserved=False,
                  archive_method='Pre-correction CSV cell values reconstructed from unchanged current cells and unchanged internal p values using original four-decimal formatting. This archive is not claimed to preserve original file bytes.',
                  public_scientific_values_other_than_p_display_unchanged=True,
                  internal_and_JSON_values_unchanged=True, effects_recomputed=False,
                  source_reads=False, key_reads=False,
                  final_independent_check_after_display=True, final_independent_checks=19,
                  final_independent_exit_code=0, repairs=changes)
    (R/'00_env/capture_display_repair_v7.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    print(json.dumps(dict(complete=True, archived_tables=len(changes), final_independent_checks=19), ensure_ascii=False))


if __name__ == '__main__':
    main()
