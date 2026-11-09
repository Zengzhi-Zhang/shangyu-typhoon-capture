# -*- coding: utf-8 -*-
"""Final read-only checksum, privacy freshness and deliverable completeness."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[3]), str(_ReleasePath(__file__).resolve().parents[1])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from pathlib import Path
import hashlib,json
R=Path(_release_path('v7_root'))
def read(p):return json.loads((R/p).read_text(encoding='utf-8-sig'))
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()
m=read('09_manifest/manifest_v7.json');internal=read('01_internal/manifest_internal_v7.json')['files'];rows=m['public_and_environment_files']+internal
for row in rows:
    p=R/row['path'];assert p.is_file() and p.stat().st_size==row['size'] and sha(p)==row['sha256'],'Manifest digest/size mismatch'
aliases={r['path_alias']:r for r in m['internal_files']}
for r in internal:
    a=aliases['internal_path_sha256_'+hashlib.sha256(r['path'].encode()).hexdigest()];assert a['sha256']==r['sha256'] and a['size']==r['size']
assert aliases['internal_manifest']['sha256']==sha(R/'01_internal/manifest_internal_v7.json')
actual={p.relative_to(R).as_posix() for p in R.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
assert actual=={r['path'] for r in rows}|set(m['exclusions']),'Manifest file coverage mismatch'
assert not any(Path(p).name in ['hmac_key','.hmac_key'] for p in actual),'Secret file in output tree'
privacy=read('09_manifest/privacy_check_v7.json');assert privacy['pass_zero_hits'] and all(v==0 for v in privacy['totals'].values())
assert all(sha(R/r['path'])==r['sha256'] for r in privacy['files']),'Privacy audit is stale'
required=['RESULTS_SUMMARY_v7.md','DEVIATIONS_v7.md','EXECUTION_LOG_v7.md','README_v7.md','results_v7.json','02_device_state/T27_state_summary_v7.csv','03_taxi_probe/T28_probe_daily_v7.csv','03_taxi_probe/T35_capture_wellmatched_v6.csv','03_taxi_probe/T35_by_state_v6.csv','03_taxi_probe/T35_camera_type_v6.csv','05_bounds/T31_recovery_bounds_v7.csv','06_s_pre/T36_health_screened_v6.csv','06_s_pre/T36_rings_v6.csv','06_s_pre/T36_ols_v6.csv','07_consequences/T37_network_comparison_v7.csv','07_consequences/T37_estimator_family_v7.csv']
assert all((R/p).is_file() and (R/p).stat().st_size>0 for p in required)
v=read('00_env/input_verification_v7.json');assert v['unchanged'] and v['n_files']==2350 and v['panels']==383 and v['formal_v6_files']==952
s=read('results_v7.json');assert len(s['acceptance'])==24 and sum(r['status']!='达到' for r in s['acceptance'])==2
assert s['v6_historical_stops']['S2'] and s['v6_historical_stops']['S3'] and s['posthoc_revision']
assert read('00_env/timing_summary_v7.json')['within_budget']
print(json.dumps(dict(all_passed=True,manifest_checksum_entries=len(rows)+1,output_files=len(actual),required_files=len(required),privacy_files=len(privacy['files']),privacy_zero=True,protected_files_unchanged=v['n_files'],source_reads=False,key_reads=False)))
