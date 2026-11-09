# -*- coding: utf-8 -*-
"""Read-only final delivery checksum/completeness verification, after privacy."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[3]), str(_ReleasePath(__file__).resolve().parents[1])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from pathlib import Path
import hashlib,json
R=Path(_release_path('v6_root'))
def read(p):return json.loads((R/p).read_text(encoding='utf-8'))
def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()
m=read('09_manifest/manifest_v6.json'); internal=read('01_internal/manifest_internal_v6.json')['files']
rows=m['public_and_environment_files']+internal
bad=[]
for row in rows:
    p=R/row['path']
    if not p.is_file() or p.stat().st_size!=row['size'] or digest(p)!=row['sha256']:bad.append(hashlib.sha256(row['path'].encode()).hexdigest())
aliases={row['path_alias']:row for row in m['internal_files']}
for row in internal:
    alias='internal_path_sha256_'+hashlib.sha256(row['path'].encode()).hexdigest()
    actual=aliases.get(alias,{})
    if actual.get('sha256')!=row['sha256'] or actual.get('size')!=row['size']:bad.append(alias)
ip=R/'01_internal/manifest_internal_v6.json'
assert aliases['internal_manifest']['sha256']==digest(ip)
inventory={p.relative_to(R).as_posix() for p in R.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
expected={r['path'] for r in rows}|set(m['exclusions'])
assert inventory==expected, 'Output file coverage differs from manifest'
assert not bad, 'Output digest or size mismatch'
privacy=read('09_manifest/privacy_check_v6.json'); assert privacy['pass_zero_hits']
assert all(digest(R/r['path'])==r['sha256'] for r in privacy['files'])
v=read('00_env/input_verification_v6.json'); assert v['unchanged'] and v['panel_files']==383 and v['source_files']==293
required=['RESULTS_SUMMARY_v6.md','DEVIATIONS_v6.md','results_v6.json','02_device_state/T27_state_summary.csv','03_taxi_probe/T28_probe_daily_v6.csv','03_taxi_probe/T29_summary_v6.csv','03_taxi_probe/T29_calibration_v6.json','04_leaveout/T30_applicability_matrix_v6.csv','05_bounds/T31_recovery_bounds_v6.csv','06_s_pre/T32_s_pre_v6.csv','07_consequences/T33_recovery_date_by_estimator_v6.csv','20_manuscript_fixes/T34_manuscript_fact_fixes_v6.csv']
assert all((R/p).is_file() and (R/p).stat().st_size>0 for p in required)
result=read('results_v6.json'); assert result['stop_conditions']['S1']['triggered'] is False
assert result['stop_conditions']['S2']['triggered'] and result['stop_conditions']['S3']['triggered'] and result['capture']['report_only']
assert all('不入判断' in result['acceptance'][key]['admissibility'] for key in ['I3_control','I3_stable_change'])
print(json.dumps(dict(pass_all=True,manifest_checksum_entries=len(rows)+1,output_files=len(inventory),required_review_files=len(required),privacy_zero=True,protected_files_unchanged=v['n_files'],panels=v['panel_files'],sources=v['source_files'])))
