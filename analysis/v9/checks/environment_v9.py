import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[3]), str(_ReleasePath(__file__).resolve().parents[1])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from pathlib import Path
from datetime import datetime, timezone, timedelta
import hashlib, json, sys, os
import numpy as np, pandas as pd
R=Path(_release_path('project_root')); O=R/'formal_v9'; ENV=O/'00_env'; TZ=timezone(timedelta(hours=8))
SPEC='shangyu_typhoon_gates_20261004/研究方案_上虞台风_v9_事后小分析任务书.md'
TERMS='shangyu_typhoon_gates_20261004/对外主张与口径定稿_2026-10-09.md'
B1DOC='shangyu_typhoon_gates_20261004/研究方案_上虞台风_v2_执行版.md'
PASTE=Path(_release_path('path_046'))
DATA=['01_panels/device_attributes.csv','01_panels/device_day.csv','01_panels/device_hour.csv','formal_v7/02_device_state/device_state_v7.csv','formal_v7/07_consequences/T37_estimator_family_v7.csv','formal_v7/03_taxi_probe/T35_capture_camera_v7.csv']+['formal_v7/01_internal/'+n for n in ['capture_camera_internal_v7.csv','capture_selection_internal_v7.csv','capture_vehicle_counts_v7.npz','capture_bootstrap_v7.npz']]
def now():return datetime.now(TZ).isoformat(timespec='milliseconds')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def put(p,x,exclusive=False):
 with p.open('x' if exclusive else 'w',encoding='utf8',newline='\n') as f:json.dump(x,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def inventory():
 files=[]
 for p,role in [(R/i,'data') for i in DATA]+[(R/i,'definition') for i in [SPEC,TERMS,B1DOC]]+[(PASTE,'user_request')]:
  s=p.stat();digest=sha(p);a=p.stat();assert(s.st_size,s.st_mtime_ns)==(a.st_size,a.st_mtime_ns)
  files.append(dict(path=p.as_posix(),role=role,bytes=s.st_size,mtime_ns=s.st_mtime_ns,modified=datetime.fromtimestamp(s.st_mtime,TZ).isoformat(),sha256=digest))
 return files
def main(mode):
 for d in ['00_env','01_internal','02_decomposition','03_breakeven','04_expected_capture','08_figures','09_manifest','scripts']:(O/d).mkdir(exist_ok=True,parents=True)
 p=ENV/'protocol_frozen_v9.json'
 if mode=='begin':
  assert not p.exists() and not (ENV/'input_manifest_v9.json').exists()
  t=now();spec=(R/SPEC).read_text(encoding='utf-8-sig');assert sha(PASTE)==sha(R/SPEC)
  payload=dict(version='v9',post_review=True,spec_sha256=sha(R/SPEC),frozen_at=t,definition_and_acceptance_verbatim=spec[spec.index('## 3. 定义与计算'):spec.index('## 5. 输出目录')],seed=20261005,python=sys.executable,python_version=sys.version,numpy=np.__version__,pandas=pd.__version__,encoding=os.environ.get('PYTHONIOENCODING'),no_bytecode=os.environ.get('PYTHONDONTWRITEBYTECODE'),data_allowlist=DATA,baseline='B1 July05-21 excluding July08,10; arithmetic mean of same weekdays including structural zeros; July25 and baseline Sundays July11/18 use hours 11 through 23 inclusive. July28 uses July7,14,21.',interpretation={
  'scope':'Only three post-review analyses, old files unchanged. A200 baseline-record weighted network under K; not independently identified traffic of the whole district. No manuscript or external source access.',
  'T38':'A100 1287 / A200 1221 / H observed in_health / O=A200 minus H. Sum counts before division. Include all three ratios, three paired differences, n_O,w_O,R_O with percentile intervals. Deltas are dimensionless ratios; multiply by 100 for pp. n_O draws are weighted multiplicities, not unique sites.',
  'device_sampling':'Sorted anonymous integer A100 device axis. default_rng(20261005).integers(0,1287,(500,1287),dtype=int32); row bincount gives Multinomial(1287,uniform) weights shared over quantities and dates. Fixed membership. Percentiles at 2.5,97.5 linear, use unrounded data.',
  'T39':'x* and signed g not clipped at zero or unity. A if x*<=R_O, else B if x*<=R_H, else C. Count any overlap R_O>R_H and disclose. Undefined denominator/zero w_O -> x*,g and A/B/C NA; report valid/invalid. Shares per valid replicate, not posterior probabilities. Suffix to Aug2: any C not sustained, all A robust sustained, else conditional; unresolved missing -> unknown unless any C. Classification uses points; not lower-CI recovery. Under K, A is robust against the specified low-record reference (x>=R_O), not all conceivable x. In C, x>R_H can still attain.',
  'coverage':'O subset within control-only main329 plus event expected>=10. Denominator of baseline share = all O baseline flow; not all A200, not A1 failures. Pooled matched event C/E divided by pooled matched-control C/E, not median or average of rates. Exposure=event total/(eight-control-day total/8). August1/2 probe measures NA; no input to x*.',
  'T40':'Main329 AND daily A1 failed AND observed event expected>=10. E=sum_i((sum control C_i/sum control E_i)*event expected_i); C=sum captured; ratio=C/E. Reuse 7/25 matched11-23 control and event. E is expected GPS-inferred passages with an AVI match under unchanged per-site capture, not total traffic nor raw AVI record count.',
  'capture_camera_bootstrap':'500 fixed-n camera-cluster samples per observed date subgroup. Reuse ordered T38 A100 index draws per replicate; keep first n hits belonging to each date subgroup. If needed extend all dates with a common independent stream default_rng(SeedSequence([20261005,40])), uniform int32 in blocks (500,1287). This gives exact uniform subgroup multinomial while sharing underlying device draws. C,E,ratio use same subgroup weights.',
  'capture_vehicle_bootstrap':'200 multinomial draws for 290 vehicle clusters with seed20261005, same vector across controls/events/dates. Verify prior frozen vehicle draws when recoverable. Recompute both control cap and event E,C; fixed subgroup, no eligibility re-selection. Zero control E with positive weighted event expected -> replicate E and C/E NA, C still defined; zero control C with positive control E gives valid zero rate. If any control denominator zero, conservative complete-subgroup convention: E and ratio NA even with zero event exposure; count finite by statistic. Do not combine camera and vehicle intervals.',
  'privacy':'Public counts <10 (including count CI endpoints and zero) masked before integer display; point expected counts and count intervals rounded for display only. Ratios and their bounds printed to four decimals. Analytical constants are not disclosure cells. No device names, organisations, precise coordinates, plate aliases, raw plates or internal device prefixes. Newly generated weights/draws are internal.',
  'fingerprinting':'SHA256/size/mtime for all enumerated numerical inputs and reference instructions before/after; protocol payload hash embedded; full-file hash in separate JSON avoids self-reference.'
  })
  canonical=json.dumps(payload,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode('utf8');put(p,dict(sha256_payload=hashlib.sha256(canonical).hexdigest(),payload=payload),True)
  put(ENV/'protocol_sha256_v9.json',dict(file=p.name,sha256=sha(p),recorded_at=now()),True)
  files=inventory();put(ENV/'input_manifest_v9.json',dict(started=t,finished=now(),files=files),True)
  print(json.dumps(dict(frozen=True,files=len(files),data=len(DATA),ended=now())))
 elif mode=='verify':
  start=now();a=inventory();b=json.loads((ENV/'input_manifest_v9.json').read_text(encoding='utf8'))['files'];digest=json.loads((ENV/'protocol_sha256_v9.json').read_text(encoding='utf8'))['sha256'];ok=a==b and sha(p)==digest
  put(ENV/'input_verification_v9.json',dict(checked_at=now(),started=start,all_inputs_unchanged=a==b,protocol_unchanged=sha(p)==digest,approved_data_files=len(DATA),total_files=len(a),differences=[x['path'] for x,y in zip(a,b) if x!=y],files=a));assert ok
  print(json.dumps(dict(unchanged=ok,data=len(DATA),total=len(a))))
if __name__=='__main__':main(sys.argv[1])
