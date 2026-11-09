# -*- coding: utf-8 -*-
"""Strict privacy audit of the publication package, never reads secret keys."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[3]), str(_ReleasePath(__file__).resolve().parents[1]), str(_ReleasePath(__file__).resolve().parent)]
import csv, json, re
from pathlib import Path
from decimal import Decimal, InvalidOperation
from common_v3 import ROOT, write_json, now
HMAC=re.compile(r'(?<![A-Za-z0-9.])[a-fA-F0-9]{16}(?![A-Za-z0-9])')
PLATE=re.compile(r'[京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼使领][A-Z][A-Z0-9]{5,6}')
COORD={'lon','lat','longitude','latitude','plot_lon','plot_lat','jittered_lon','jittered_lat'}
def vehicle_count_column(c):
    c=c.lower()
    return ('plates' in c or 'vehicles' in c or c in {'n_regular','n_frequent','n_occasional','n_earlier_only','n_unseen','n_nonwindow','n_vehicles'}) and not any(x in c for x in ['ratio','share','ci_','semantics','scope','status','ph_count_semantics'])
def small(v):
    if v in ('','<10','NA','null'):return False
    try:return Decimal(v).is_finite() and 0<=Decimal(v)<10
    except InvalidOperation:return False
def check(root=None,write=True):
    folder=Path(root or ROOT/'pub_package'); rules={n:{'scanned_files':0,'hits':0,'files':[]} for n in ['hmac16','raw_plate','coordinates_more_than_2_decimals','vehicle_count_below_10','forbidden_directories']}
    for p in sorted(folder.rglob('*')):
        if not p.is_file() or p.name=='PRIVACY_CHECK.json':continue
        if any(c in {'01_panels','00_env'} for c in p.relative_to(folder).parts):
            rules['forbidden_directories']['hits']+=1;rules['forbidden_directories']['files'].append(p.relative_to(folder).as_posix())
        if p.suffix.lower() not in {'.csv','.json','.md'}:continue
        content=p.read_text(encoding='utf-8-sig');rel=p.relative_to(folder).as_posix()
        for name,rx in [('hmac16',HMAC),('raw_plate',PLATE)]:
            rules[name]['scanned_files']+=1;n=len(rx.findall(content))
            if n:rules[name]['hits']+=n;rules[name]['files'].append(rel)
        if p.suffix.lower()=='.csv':
            rules['coordinates_more_than_2_decimals']['scanned_files']+=1;rules['vehicle_count_below_10']['scanned_files']+=1
            with p.open(encoding='utf-8-sig',newline='') as f:
                for row in csv.DictReader(f):
                    for c,v in row.items():
                        if c.lower() in COORD and v and re.fullmatch(r'[+-]?\d+\.\d{3,}',v):
                            rules['coordinates_more_than_2_decimals']['hits']+=1
                            if rel not in rules['coordinates_more_than_2_decimals']['files']:rules['coordinates_more_than_2_decimals']['files'].append(rel)
                        if vehicle_count_column(c) and small(v):
                            rules['vehicle_count_below_10']['hits']+=1
                            if rel not in rules['vehicle_count_below_10']['files']:rules['vehicle_count_below_10']['files'].append(rel)
        elif p.suffix.lower()=='.json':
            rules['vehicle_count_below_10']['scanned_files']+=1
            def visit(x):
                if isinstance(x,dict):
                    for c,v in x.items():
                        if vehicle_count_column(c) and isinstance(v,(float,int)) and 0<=v<10:
                            rules['vehicle_count_below_10']['hits']+=1
                            if rel not in rules['vehicle_count_below_10']['files']:rules['vehicle_count_below_10']['files'].append(rel)
                        visit(v)
                elif isinstance(x,list):
                    for v in x:visit(v)
            visit(json.loads(content))
    report=dict(generated_at=now(),rules=rules,passed=all(r['hits']==0 for r in rules.values()),scope='All package CSV/JSON/MD; scripts contain no input panels or keys. HMAC16 matches standalone identifier tokens, not fractional digits of JSON numbers. Vehicle counts include zero under the protocol literal <10 rule; device/grid counts are different units.')
    if write:write_json(folder/'PRIVACY_CHECK.json',report)
    return report
if __name__=='__main__':
    r=check();print('Privacy passed',r['passed'],{k:v['hits'] for k,v in r['rules'].items()},flush=True)
    if not r['passed']:raise SystemExit(1)
