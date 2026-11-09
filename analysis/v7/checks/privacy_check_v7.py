# -*- coding: utf-8 -*-
"""Audit only publication surfaces; report counts, never matched private values."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[3]), str(_ReleasePath(__file__).resolve().parents[1])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from pathlib import Path
import csv,io,json,re,time,hashlib
ROOT=Path(_release_path('v7_root'))
TOKEN=re.compile(r'(?<![0-9A-Za-z])[0-9a-fA-F]{16}(?![0-9A-Za-z])')
PLATE=re.compile(r'[京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼][A-ZＡ-Ｚ][A-Z0-9Ａ-Ｚ０-９·.]{5,7}')
COORD_NAME=re.compile(r'(^|_)(lon|lat|longitude|latitude)($|_)',re.I)
DECIMAL=re.compile(r'^[-+]?\d+\.(\d+)$')
def tokens(s):
    # Only an explicit decimal point disambiguates a numeric literal from an ID.
    # Scientific-notation decimal tails may include 'e', which is also hex.
    # A stand-alone16-character integer or hex containing'e' remains a hit.
    decimals=[m.span() for m in re.finditer(r'(?<![0-9A-Za-z_.])[-+]?(?:\d+\.\d+|\.\d+)(?:[eE][-+]?\d+)?(?![0-9A-Za-z_.])',s)]
    return [m for m in TOKEN.finditer(s) if not any(a<=m.start() and m.end()<=b for a,b in decimals)]
def targets():
    paths=[p for p in ROOT.iterdir() if p.is_file() and p.suffix.lower() in {'.md','.json','.txt','.csv'}]
    for p in ROOT.iterdir():
        if p.is_dir() and (re.match(r'^0[2-9]_',p.name) or p.name=='20_manuscript_fixes'):
            paths.extend(q for q in p.rglob('*') if q.is_file() and q.name!='privacy_check_v7.json')
    return sorted(paths)
def main():
    start=time.perf_counter()
    # Read names solely to perform an exact public-text exclusion check.
    with (ROOT.parent/'01_panels/device_id_map.csv').open(encoding='utf-8-sig',newline='') as f:
        names={r['dev_name'] for r in csv.DictReader(f) if r.get('dev_name') and re.search('[\u4e00-\u9fff]',r['dev_name'])}
    records=[]
    total={k:0 for k in ['hex16_token','plate_pattern','internal_device_prefix','device_chinese_name','coordinate_precision','binary_uninspected']}
    for p in targets():
        rel=p.relative_to(ROOT).as_posix();data=p.read_bytes()
        row=dict(path=rel,bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
        hit={k:0 for k in total}
        try: s=data.decode('utf-8-sig')
        except UnicodeDecodeError: hit['binary_uninspected']=1;s=''
        hit['hex16_token']=len(tokens(s));hit['plate_pattern']=len(PLATE.findall(s))
        hit['internal_device_prefix']=s.count('cam_')
        hit['device_chinese_name']=sum(s.count(n) for n in names if n in s)
        if p.suffix.lower()=='.csv' and s:
            reader=csv.DictReader(io.StringIO(s))
            fields=[k for k in (reader.fieldnames or []) if COORD_NAME.search(k)]
            for item in reader:
                for field in fields:
                    val=(item.get(field) or '').strip();m=DECIMAL.match(val)
                    if m and len(m.group(1))>2:hit['coordinate_precision']+=1
        else:
            # Text/JSON coordinate-labelled numeric pairs, not arbitrary scientific decimals.
            hit['coordinate_precision']+=len(re.findall(r'(?:longitude|latitude|\blon\b|\blat\b|经度|纬度)["\s]*[:=][\s]*[-+]?\d+\.\d{3,}',s,re.I))
        row.update(hit);records.append(row)
        for k in total:total[k]+=hit[k]
    result=dict(pass_zero_hits=all(v==0 for v in total.values()),totals=total,n_files=len(records),scope='root text, 02 through 09 and manuscript-fix register; internal and environment excluded; text only; private matches never printed',files=records,seconds=time.perf_counter()-start)
    out=ROOT/'09_manifest/privacy_check_v7.json';out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(pass_zero_hits=result['pass_zero_hits'],n_files=len(records),totals=total)))
    if not result['pass_zero_hits']:raise SystemExit(2)
if __name__=='__main__':main()

