# -*- coding: utf-8 -*-
"""v4 text-only privacy checks. Images/PDFs are never decoded as text."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[3]), str(_ReleasePath(__file__).resolve().parents[1])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from pathlib import Path
import re,json,csv
from decimal import Decimal,InvalidOperation
ROOT=Path(_release_path('v4_root'))
EXT={'.csv','.json','.md','.txt'}
HEX=re.compile(r'(?<![A-Za-z0-9_.])[0-9a-fA-F]{16}(?![A-Za-z0-9_])')
PLATE=re.compile(r'[京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼使领][A-Z][A-Z0-9]{5,6}')
VEHICLE_COLS={'plates','n_regular','plates_all','plates_Sstar','singleton_plates','two_day_plates','regular_plates','taxi_vehicles_reporting','taxi_vehicles_active','n_vehicles','n_active_vehicles','active_vehicles','vehicles_reporting'}
def main():
    files=[p for p in ROOT.rglob('*') if p.is_file() and p.suffix.lower() in EXT and p.name not in ['PRIVACY_CHECK_v4.json']]
    rules={name:dict(scanned_files=0,hits=0,hit_files=[]) for name in ['raw_plates','hmac16_tokens','replacement_characters','coordinate_precision','small_vehicle_counts']}
    for p in files:
        s=p.read_text(encoding='utf-8-sig'); rel=p.relative_to(ROOT).as_posix()
        for name,regex in [('raw_plates',PLATE),('hmac16_tokens',HEX),('replacement_characters',re.compile('\ufffd'))]:
            rr=rules[name];rr['scanned_files']+=1;hits=len(regex.findall(s))
            if hits:rr['hits']+=hits;rr['hit_files'].append(dict(file=rel,hits=hits))
        if p.suffix.lower()=='.json':
            rr=rules['coordinate_precision'];rr['scanned_files']+=1;vv=rules['small_vehicle_counts'];vv['scanned_files']+=1
            def visit(value,key=''):
                ch=vh=0
                if isinstance(value,dict):
                    for k,v in value.items():
                        a,b=visit(v,str(k).lower());ch+=a;vh+=b
                elif isinstance(value,list):
                    for v in value:
                        a,b=visit(v,key);ch+=a;vh+=b
                elif isinstance(value,(int,float)) and not isinstance(value,bool):
                    if key in VEHICLE_COLS or key.startswith('plates_') or (key.startswith('n_') and key.endswith('_vehicles')):
                        if 0<=value<10:vh+=1
                    if key in {'lon','lat','longitude','latitude','plot_lon','plot_lat','jitter_lon','jitter_lat'}:
                        v=Decimal(str(value))
                        if v.is_finite() and v!=v.quantize(Decimal('.01')):ch+=1
                return ch,vh
            ch,vh=visit(json.loads(s))
            if ch:rr['hits']+=ch;rr['hit_files'].append(dict(file=rel,hits=ch))
            if vh:vv['hits']+=vh;vv['hit_files'].append(dict(file=rel,hits=vh))
        if p.suffix.lower()=='.csv':
            rr=rules['coordinate_precision'];rr['scanned_files']+=1;vv=rules['small_vehicle_counts'];vv['scanned_files']+=1
            ch=vh=0
            for row in csv.DictReader(s.splitlines()):
                for c,v in row.items():
                    if not v:continue
                    cn=str(c).lower()
                    if cn in {'lon','lat','longitude','latitude','plot_lon','plot_lat','jitter_lon','jitter_lat'}:
                        try:
                            value=Decimal(v)
                            if value.is_finite() and value!=value.quantize(Decimal('.01')):ch+=1
                        except InvalidOperation:pass
                    if cn in VEHICLE_COLS or cn.startswith('plates_') or (cn.startswith('n_') and cn.endswith('_vehicles')):
                        if v=='<10':continue
                        try:
                            val=float(v)
                            if 0<=val<10:vh+=1
                        except ValueError:pass
            if ch:rr['hits']+=ch;rr['hit_files'].append(dict(file=rel,hits=ch))
            if vh:vv['hits']+=vh;vv['hit_files'].append(dict(file=rel,hits=vh))
    # Only named vehicle-count fields, not device/grid/sample-size counts, are suppressed.
    result=dict(passed=all(r['hits']==0 for r in rules.values()),rules=rules,scope='All .csv/.json/.md/.txt in formal_v4; PNG/PDF excluded from textual scanning',text_files=len(files),small_count_scope='CSV/JSON named vehicle-unit fields; prose/table MD manually reviewed in manuscript audit',png_pdf_scanned_as_text=0)
    (ROOT/'00_env/PRIVACY_CHECK_v4.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False))
    if not result['passed']:raise SystemExit(1)
if __name__=='__main__':main()
