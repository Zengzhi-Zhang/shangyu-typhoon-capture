"""Verify release surfaces; never print matches or publish internal identifiers."""
from environment_v9 import O,R,ENV,sha,put,now,TZ
import csv,io,json,re,sys
from datetime import datetime
import pandas as pd
M=O/'09_manifest'
def j(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def manifest():
 rows=[]
 for p in sorted(O.rglob('*')):
  if not p.is_file() or '__pycache__' in p.parts:continue
  rel=p.relative_to(O).as_posix()
  if rel.startswith('09_manifest/'):continue
  rows.append(dict(path=rel,bytes=p.stat().st_size,sha256=sha(p),access='internal' if rel.startswith(('00_env/','01_internal/','scripts/')) else 'public_aggregate'))
 put(M/'manifest_v9.json',dict(version='v9',generated=now(),n_files=len(rows),exclude='09_manifest self-referential audit products; bytecode caches',files=rows))
def public():
 return [p for p in sorted(O.rglob('*')) if p.is_file() and (p.parent==O or re.match(r'^0[2-9]_',p.relative_to(O).parts[0]))]
def privacy():
 units=set(pd.read_csv(R/'formal_v7/02_device_state/device_state_v7.csv',usecols=['org']).org.dropna().astype(str));units={s for s in units if re.search(r'[\u3400-\u9fff]',s)}
 private_prefix='cam'+'_'
 hx=re.compile(r'(?<![A-Za-z0-9])[0-9a-fA-F]{16}(?![A-Za-z0-9])')
 dec=re.compile(r'(?<![\w.])[-+]?(?:\d+\.\d+|\.\d+)(?:[Ee][-+]?\d+)?(?![\w.])')
 plate=re.compile(r'[京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂贵粤青藏川宁琼蒙陕吉闽赣晋甘桂][A-ZＡ-Ｚ][A-Z0-9Ａ-Ｚ０-９·.]{5,7}')
 coord=re.compile(r'(?:\b(?:lat|lon|longitude|latitude)\b|经度|纬度)[\s"\x27]*[:=,][\s"\x27]*[-+]?\d+\.\d{3,}',re.I)
 geotuple=re.compile(r'(?<![\d.])(?:119|120|121|122)\.\d{3,}\s*[,，/]\s*(?:29|30|31)\.\d{3,}(?![\d.])')
 totals={k:0 for k in ['private_device_prefix','pseudonym16','plate','organisation_name','schema_device_identifier_or_location','coordinate_precision','unsuppressed_small_count','binary_uninspected']};records=[]
 for p in public():
  if p.name in ['privacy_scan_v9.json','verification_v9.json']:continue
  data=p.read_bytes();hit=totals.copy();hit={k:0 for k in hit}
  try:s=data.decode('utf-8-sig')
  except UnicodeDecodeError:hit['binary_uninspected']=1;s=''
  rel=p.relative_to(O).as_posix();scheck=rel+'\n'+s;numeric=[m.span() for m in dec.finditer(scheck)]
  hit['private_device_prefix']=scheck.count(private_prefix)
  hit['pseudonym16']=sum(not any(a<=m.start() and m.end()<=b for a,b in numeric) for m in hx.finditer(scheck))
  hit['plate']=len(plate.findall(scheck));hit['organisation_name']=sum(scheck.count(k) for k in units)
  hit['coordinate_precision']=len(coord.findall(scheck))+len(geotuple.findall(scheck))
  if p.suffix=='.csv':
   reader=csv.DictReader(io.StringIO(s));fields=reader.fieldnames or []
   hit['schema_device_identifier_or_location']=sum(bool(re.search(r'^(dev|dev_name|camera_id|camera_name|org|organisation|unit_name|lon|lat|longitude|latitude|ph|plate)$',col,re.I)) for col in fields)
   for row in reader:
    for col,raw in row.items():
     # All physical count columns (including CI endpoints) are explicitly typed here.
     # The metadata n_valid and planned replicate sizes are not measured site/vehicle counts.
     if not is_public_count(col):continue
     if raw in ('<10','NA',''):continue
     try:small=float(raw)<10;is_integer=float(raw).is_integer()
     except (ValueError,TypeError):small=True;is_integer=False
     hit['unsuppressed_small_count']+=int(small or not is_integer)
  for k,v in hit.items():totals[k]+=int(v)
  records.append(dict(path=rel,bytes=len(data),sha256=sha(p),hits=hit))
 out=dict(scan_time=now(),pass_zero_hits=not any(totals.values()),counts=totals,n_files=len(records),scope='Public root reports, 02 through 09, including the manifest. Scanner/verification outputs record counts only. All scientific CSV schemas checked: aggregates only, no per-device or free-text name/coordinate/organisation fields. Organisation denylist comes from permitted frozen state table. Private IDs, raw plates, coordinates and small count cells not echoed.',files=records)
 put(M/'privacy_scan_v9.json',out);print(json.dumps(dict(privacy=out['pass_zero_hits'],n_files=len(records),counts=totals)))
 assert out['pass_zero_hits'],[(r['path'],r['hits']) for r in records if any(r['hits'].values())]
def is_public_count(col):
 c=col.lower()
 if re.search(r'(ratio|relative|share|rate|freq|cap_ctrl|bootstrap|n_valid|n_invalid|_valid|_draw)',c):return False
 return (c in ('n_a100','n_a200','n_h','n_o','n_audit','n_cameras','n_devices','n_eligible','n_audited_cameras','n_report_cameras','n_control_selected','event_expected','event_captured','control_expected','control_captured','n_tail_dates') or c.startswith(('n_o_ci_','expected_passages','actual_passages','captured_passages','expected_records','actual_records'))) or bool(re.match(r'^(e|c)(?:$|_(?:camera|vehicle|ci|lo|hi|count))',c))
def final():
 checks={};rows=j(M/'manifest_v9.json')['files']
 for i,r in enumerate(rows):checks['file'+str(i)]=(O/r['path']).is_file() and (O/r['path']).stat().st_size==r['bytes'] and sha(O/r['path'])==r['sha256']
 required=['00_env/protocol_frozen_v9.json','00_env/input_manifest_v9.json','00_env/execution_v9.json','02_decomposition/T38_decomposition_v9.csv','02_decomposition/T38_checks_v9.json','03_breakeven/T39_breakeven_v9.csv','03_breakeven/T39_sustained_v9.csv','03_breakeven/T39_audit_coverage_v9.csv','04_expected_capture/T40_expected_capture_v9.csv','08_figures/fig_breakeven_source_v9.csv','08_figures/fig_expected_capture_source_v9.csv','README_v9.md','METHODS_v9.md','DEVIATIONS_v9.md','RESULTS_SUMMARY_v9.md','results_v9.json']
 for k in required:checks['required:'+k]=(O/k).is_file()
 checks['input_integrity']=j(ENV/'input_verification_v9.json')['all_inputs_unchanged']
 checks['protocol_sha256']=sha(ENV/'protocol_frozen_v9.json')==j(ENV/'protocol_sha256_v9.json')['sha256']
 checks['two_figure_sources_match_tables']=((O/'08_figures/fig_breakeven_source_v9.csv').read_bytes()==(O/'03_breakeven/T39_breakeven_v9.csv').read_bytes() and (O/'08_figures/fig_expected_capture_source_v9.csv').read_bytes()==(O/'04_expected_capture/T40_expected_capture_v9.csv').read_bytes())
 priv=j(M/'privacy_scan_v9.json');checks['privacy_zero_hits']=priv['pass_zero_hits']
 for i,r in enumerate(priv['files']):checks['publicationscan'+str(i)]=sha(O/r['path'])==r['sha256']
 checks['privacy_complete']={r['path'] for r in priv['files']}=={p.relative_to(O).as_posix() for p in public() if p.name not in ['privacy_scan_v9.json','verification_v9.json']}
 res=j(O/'results_v9.json');checks['all_six_acceptance_statuses_reported']=len(res['prespecified_acceptance'])==6
 end=datetime.now(TZ);start=datetime.fromisoformat(j(ENV/'execution_v9.json')['first_recorded_preflight'])
 put(M/'verification_v9.json',dict(finished_at=end.isoformat(),wall_seconds_from_first_recorded_preflight=(end-start).total_seconds(),n_checks=len(checks),all_passed=all(checks.values()),failed=[k for k,v in checks.items() if not v],output_files_excluding_this_report=sum(p.is_file() and p.name!='verification_v9.json' for p in O.rglob('*'))))
 print(json.dumps(j(M/'verification_v9.json')));assert all(checks.values())
if __name__=='__main__':{'manifest':manifest,'privacy':privacy,'final':final}[sys.argv[1]]()
