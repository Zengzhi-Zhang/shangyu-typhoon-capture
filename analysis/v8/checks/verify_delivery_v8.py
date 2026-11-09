import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[3]), str(_ReleasePath(__file__).resolve().parents[1])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from pathlib import Path
import json,hashlib,sys,pandas as pd
O=Path(_release_path('v8_root'))
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def js(p):return json.loads((O/p).read_text(encoding='utf8'))
def main():
 final='--read-only' in sys.argv;c={};m=js('09_manifest/manifest_v8.json')
 for i,r in enumerate(m['files']):
  p=O/r['path'];c['manifest_'+str(i)]=p.exists() and p.stat().st_size==r['size'] and sha(p)==r['sha256']
 need=['RESULTS_SUMMARY_v8.md','DEVIATIONS_v8.md','README_v8.md','EXECUTION_LOG_v8.md','results_v8.json','02_geometry/G0_exposure_v8.csv','02_geometry/G123_capture_v8.csv','02_geometry/G4_distance_shift_v8.csv','02_geometry/G_acceptance_v8.json','03_baseline/W1_device_estimators_v8.csv','03_baseline/W1_vehicle_margins_v8.csv','03_baseline/W1_probe_v8.csv','03_baseline/W2_recovery_dates_v8.csv','03_baseline/W3_health_pc_daily_v8.csv','03_baseline/W3_health_pc_rings_0726_v8.csv','03_baseline/W3_health_pc_ols_0726_v8.csv','04_ledger/claim_ledger_v8.csv','01_internal/G5_audit/G5_audit_attributes.csv']
 for n,p in enumerate(need):c['required_'+str(n)]=(O/p).is_file()
 c['sixteen_main_PNG']=len(list((O/'01_internal/G5_audit').glob('G5_[0-9][0-9]_*.png')))==16
 c['G5_attribute_count']=len(pd.read_csv(O/'01_internal/G5_audit/G5_audit_attributes.csv'))==16
 c['local_unchanged']=js('00_env/input_verification_v8.json')['unchanged']
 c['osm_unchanged']=js('00_env/input_verification_osm_v8.json')['unchanged']
 c['A_G4_not_automatically_judged']=js('02_geometry/G_acceptance_v8.json')['A_G4']['reached'] is None
 c['W2_216']=len(pd.read_csv(O/'03_baseline/W2_recovery_dates_v8.csv'))==216
 c['N_216']=len(pd.read_csv(O/'04_ledger/claim_ledger_v8.csv'))==216
 c['within_machine_budget']=js('results_v8.json')['timing']['measured_wall_seconds']<5400
 c['precision_wording_corrected']='公共表4位展示，验收' not in (O/'README_v8.md').read_text(encoding='utf8')
 if final:
  p=js('09_manifest/privacy_check_v8.json');c['privacy_zero_hits']=p['pass_zero_hits']
  for i,r in enumerate(p['files']):c['privacy_target_unchanged_'+str(i)]=sha(O/r['path'])==r['sha256']
 out=dict(pass_all=all(c.values()),n_checks=len(c),checks=c,mode='read_only_final' if final else 'pre_privacy_manifest')
 if not final:(O/'09_manifest/verification_v8.json').write_text(json.dumps(out,indent=2),encoding='utf8')
 print(json.dumps(dict(pass_all=out['pass_all'],n_checks=len(c),failed=[k for k,v in c.items() if not v])))
 assert out['pass_all']
if __name__=='__main__':main()
