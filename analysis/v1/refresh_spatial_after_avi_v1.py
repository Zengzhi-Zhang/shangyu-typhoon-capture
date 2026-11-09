# -*- coding: utf-8 -*-
"""Coordinator-approved post-AVI source spatial refresh and set-invariance audit.

Never run this while the AVI reader is active. The coordinator must first
confirm successful completion and its shared-attribute hash verification.
"""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[2]), str(_ReleasePath(__file__).resolve().parents[0])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
import json
import subprocess
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(_release_path('project_root'))
PYTHON = _release_path('python_executable')
SEED = 20261005


def canonical_online():
    x = pd.read_csv(ROOT / '01_panels/online_sets.csv', dtype=str)
    return x.sort_values(['date', 'dev']).reset_index(drop=True)


def main():
    if '--avi-complete-hash-verified' not in sys.argv:
        raise RuntimeError('Run only after the coordinator confirms AVI completion and successful shared-attribute hash verification')
    before = pd.read_csv(ROOT / '01_panels/device_attributes.csv').set_index('dev')
    online_before = canonical_online()
    subprocess.run([PYTHON, str(ROOT / 'scripts/spatial_attributes_v1.py'), '--refresh-source'], check=True)
    subprocess.run([PYTHON, str(ROOT / 'scripts/panels_v1.py')], check=True)
    after = pd.read_csv(ROOT / '01_panels/device_attributes.csv').set_index('dev')
    online_after = canonical_online()
    same_devices = set(before.index) == set(after.index)
    checks = {}
    for col in ['in_A100', 'in_A200', 'in_Sstar']:
        same = same_devices and before[col].sort_index().equals(after[col].sort_index())
        checks[col] = {'unchanged': same, 'before': int(before[col].sum()), 'after': int(after[col].sum()),
                       'changed_anonymous_device_ids': before.index[before[col].ne(after[col].reindex(before.index))].tolist()}
    checks['online_sets'] = {'unchanged': online_before.equals(online_after),
                             'before_rows': len(online_before), 'after_rows': len(online_after),
                             'n_online_by_date_before': online_before.groupby('date').size().to_dict(),
                             'n_online_by_date_after': online_after.groupby('date').size().to_dict()}
    sets_unchanged = same_devices and all(x['unchanged'] for x in checks.values())
    report = {'seed': SEED, 'authorization_gate': 'Coordinator confirmed AVI completion and successful shared-attribute hash verification',
              'device_index_unchanged': same_devices, 'checks': checks,
              'all_observation_sets_unchanged': sets_unchanged,
              'coordinate_counts_before': int(before['lon'].notna().sum()), 'coordinate_counts_after': int(after['lon'].notna().sum()),
              'coordinate_refresh_changes_vehicle_aggregation': not sets_unchanged}
    (ROOT / '00_env/spatial_refresh_set_invariance.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'spatial_source_refresh': 'complete', 'sets_unchanged': report['all_observation_sets_unchanged'],
                      'coordinates_before': report['coordinate_counts_before'], 'coordinates_after': report['coordinate_counts_after']}, ensure_ascii=False))
    if not report['all_observation_sets_unchanged']:
        raise RuntimeError('Observation sets changed; completed vehicle aggregations require coordinator review and recomputation')
    subprocess.run([PYTHON, str(ROOT / 'scripts/audit_spatial_source_equivalence_v1.py')], check=True)


if __name__ == '__main__':
    main()
