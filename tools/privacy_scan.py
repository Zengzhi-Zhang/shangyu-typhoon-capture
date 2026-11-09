"""Generic release checks. Match counts are reported; matched values are never printed."""
from pathlib import Path
import csv,io,json,re,sys,math

def token_hits(s):
    numeric=[m.span() for m in re.finditer(r'(?<![\w.])[-+]?(?:\d+\.\d+|\.\d+)(?:[Ee][-+]?\d+)?(?![\w.])',s)]
    return sum(not any(a<=m.start() and m.end()<=b for a,b in numeric)
               for m in re.finditer(r'(?<![A-Za-z0-9])[0-9a-fA-F]{16}(?![A-Za-z0-9])',s))

def physical_count(column):
    c=column.lower()
    if any(k in c for k in ('ratio','share','rate','fraction','threshold','bootstrap','valid','corr','coef','ci_scope','median_cap')): return False
    return bool(re.search(r'(^|_)(captured|expected|vehicles|passages|plates|n_taxi|rec_all|rec_stable|actual_records)(_|$)',c) or c in ('e','c','n_vehicles','n_passages'))

def scan_raw(root):
    counts={k:0 for k in ['absolute_path','hex16','device_alias_pattern','plate_pattern','email','coordinate_precision','small_physical_count','binary_requires_review']}
    registry=root/'public_layers/coordinates_manifest.json'
    public_geo=set()
    n_files=0;binary_review_files=[]
    for p in sorted(root.rglob('*')):
        if not p.is_file() or any(k in p.parts for k in ['.git','__pycache__','outputs']): continue
        n_files+=1;rel=p.relative_to(root).as_posix();raw=p.read_bytes()
        try: s=raw.decode('utf-8-sig')
        except UnicodeDecodeError:
            # Published geographical files are separately declared and field-audited.
            if rel not in public_geo:
                counts['binary_requires_review']+=1;binary_review_files.append(rel)
            continue
        counts['absolute_path']+=len(re.findall(r'(?i)(?<![A-Za-z])(?:[A-Z]:[/\\]|[/\\]Users[/\\]|[/\\]home[/\\]|[/\\]tmp[/\\])',s))
        counts['hex16']+=token_hits(s)
        counts['device_alias_pattern']+=len(re.findall(r'(?<!\w)'+'cam'+'_[0-9a-fA-F]{8,32}(?!\w)',s))
        counts['plate_pattern']+=len(re.findall(r'[京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼][A-ZＡ-Ｚ][A-Z0-9Ａ-Ｚ０-９·.]{5,7}',s))
        counts['email']+=len(re.findall(r'(?<![\w.-])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?![\w.-])',s))
        if p.suffix.lower()=='.csv':
            reader=csv.DictReader(io.StringIO(s));fields=reader.fieldnames or []
            for row in reader:
                for col,v in row.items():
                    if not col or v in (None,'','NA','NaN','nan','<10'): continue
                    if rel not in public_geo and re.search(r'(^|_)(lon|lat|longitude|latitude)($|_)',col,re.I):
                        try:
                            f=float(v)
                            if math.isfinite(f) and abs(f-round(f,2))>1e-9:counts['coordinate_precision']+=1
                        except ValueError: pass
                    if physical_count(col):
                        try:
                            f=float(v)
                            if math.isfinite(f) and 0<=f<10:counts['small_physical_count']+=1
                        except ValueError: pass
        elif rel not in public_geo:
            counts['coordinate_precision']+=len(re.findall(r'(?:\b(?:longitude|latitude|lon|lat)\b|经度|纬度)[\s\x22\x27]*[:=][\s\x22\x27]*[-+]?\d+\.\d{3,}',s,re.I))
    return dict(files_scanned=n_files,pass_zero_hits=not any(counts.values()),counts=counts,binary_review_files=binary_review_files,
                scope='Distribution files; generated outputs, bytecode and version-control internals excluded. Registry-listed public geographic layers are checked for provenance separately; other coordinates follow the generic precision rule.')


# -*- coding: utf-8 -*-
"""Hash-bound provenance checks; original raw scanner counts remain visible."""
import ast,tokenize,io,hashlib,json,re,csv,math
from pathlib import Path

EMAIL_EXACT=re.compile(r'(?<![\w.-])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?![\w.-])')
COORD_EXACT=re.compile(r'(?:\b(?:longitude|latitude|lon|lat)\b|经度|纬度)[\s\x22\x27]*[:=][\s\x22\x27]*[-+]?\d+\.\d{3,}',re.I)
def file_sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def _layout(text):
    lines=text.splitlines(keepends=True);offset=[0]
    for line in lines:offset.append(offset[-1]+len(line))
    return lines,offset
def _span(node,text):
    lines,offset=_layout(text)
    def point(row,col):return offset[row-1]+len(lines[row-1].encode('utf-8')[:col].decode('utf-8'))
    return point(node.lineno,node.col_offset),point(node.end_lineno,node.end_col_offset)
def _inside(a,b,span):return span[0]<=a and b<=span[1]
def email_classifications(text,is_python):
    matches=list(EMAIL_EXACT.finditer(text));matrix=[];protected=[];operators=[]
    if is_python:
        try:
            tree=ast.parse(text);matrix=[_span(n,text) for n in ast.walk(tree) if isinstance(n,ast.BinOp) and isinstance(n.op,ast.MatMult)]
            lines,offset=_layout(text)
            for t in tokenize.generate_tokens(io.StringIO(text).readline):
                span=(offset[t.start[0]-1]+t.start[1],offset[t.end[0]-1]+t.end[1])
                if t.type in (tokenize.STRING,tokenize.COMMENT):protected.append(span)
                if t.type==tokenize.OP and t.string=='@':operators.append(span)
        except (SyntaxError,tokenize.TokenError,IndentationError):matrix=[];operators=[]
    result=[]
    for m in matches:
        a,b=m.span();confirmed=(any(_inside(a,b,s) for s in matrix)
            and any(a<=x and y<=b for x,y in operators)
            and not any(not(b<=x or a>=y) for x,y in protected))
        result.append({'start':a,'end':b,'line':text.count('\n',0,a)+1,'confirmed_MatMult_operator':bool(confirmed)})
    return result

def fixture_spans(text,relative_path,sha256,registry):
    entry=registry.get('synthetic_coordinate_fixtures',{}).get(relative_path)
    if not entry or sha256!=entry['sha256']:return []
    try:tree=ast.parse(text)
    except SyntaxError:return []
    expected=set(entry['test_names']);found={}
    for function in tree.body:
        if not isinstance(function,(ast.FunctionDef,ast.AsyncFunctionDef)) or function.name!='main':continue
        for statement in function.body:
            if not isinstance(statement,ast.Assign) or not any(isinstance(t,ast.Name) and t.id=='checks' for t in statement.targets) or not isinstance(statement.value,ast.Dict):continue
            for key,value in zip(statement.value.keys,statement.value.values):
                if not isinstance(key,ast.Constant) or key.value not in expected:continue
                if not(isinstance(value,ast.Compare) and len(value.ops)==1 and isinstance(value.ops[0],ast.Eq) and len(value.comparators)==1 and isinstance(value.comparators[0],ast.Constant) and value.comparators[0].value==1):continue
                call=value.left
                if not(isinstance(call,ast.Call) and isinstance(call.func,ast.Name) and call.func.id=='json_coordinate_precision' and len(call.args)==1 and isinstance(call.args[0],ast.Constant) and isinstance(call.args[0].value,str)):continue
                try:
                    data=json.loads(call.args[0].value)
                    if not isinstance(data,dict) or len(data)!=1 or next(iter(data)) not in {'lon','longitude'}:continue
                    if not isinstance(next(iter(data.values())),(int,float)):continue
                except (ValueError,TypeError):continue
                found[key.value]=_span(call.args[0],text)
    # A changed/missing assertion invalidates the entire fixture registration.
    return list(found.values()) if set(found)==expected else []

def public_coordinate_fields(relative_path,sha256,registry):
    item=registry.get('public_geographic_csv',{}).get(relative_path)
    if not item or item['sha256']!=sha256:return set()
    if item.get('source_type')!='public_storm_track_interpolation':return set()
    return set(item['coordinate_fields'])

def map_field_review(root,registry):
    from importlib.util import spec_from_file_location,module_from_spec
    helper=Path(root)/'tools/verify_public_layers.py'
    if not helper.is_file():
        assets=[p for p in (Path(root)/'public_layers').rglob('*') if p.is_file() and p.suffix.lower() in {'.geojson','.json','.tif','.tiff','.npz','.png','.jpg','.jpeg'}]
        return [dict(file=p.relative_to(root).as_posix(),valid=False,binary=False,reason='required_map_validator_missing') for p in assets],[]
    spec=spec_from_file_location('release_public_map_field_review',helper)
    module=module_from_spec(spec);spec.loader.exec_module(module)
    return module.verify(root,registry)

def semantic_review(root,raw_result,registry):
    root=Path(root);counts=dict(raw_result['counts']);items=[]
    for path in sorted(root.rglob('*')):
        if not path.is_file() or any(k in path.parts for k in ['.git','__pycache__','outputs']):continue
        rel=path.relative_to(root).as_posix()
        try:text=path.read_bytes().decode('utf-8-sig')
        except UnicodeDecodeError:continue
        digest=file_sha(path)
        for m in email_classifications(text,path.suffix.lower()=='.py'):
            if m['confirmed_MatMult_operator']:
                counts['email']-=1;items.append({'category':'email','file':rel,'line':m['line'],'classification':'lexically_and_AST_confirmed_MatMult_operator','raw_hit_retained_in_raw_result':True})
        if path.suffix.lower()=='.csv':
            fields=public_coordinate_fields(rel,digest,registry)
            if not fields:continue
            reader=csv.DictReader(io.StringIO(text))
            for row in reader:
                for col in fields:
                    try:value=float(row.get(col,''))
                    except (ValueError,TypeError):continue
                    if math.isfinite(value) and abs(value-round(value,2))>1e-9:
                        counts['coordinate_precision']-=1;items.append({'category':'coordinate_precision','file':rel,'line':reader.line_num,'field':col,'classification':'hash_verified_public_storm_track_coordinate','raw_hit_retained_in_raw_result':True})
        else:
            spans=fixture_spans(text,rel,digest,registry)
            for m in COORD_EXACT.finditer(text):
                if any(_inside(m.start(),m.end(),s) for s in spans):
                    counts['coordinate_precision']-=1;items.append({'category':'coordinate_precision','file':rel,'line':text.count('\n',0,m.start())+1,'classification':'hash_and_AST_verified_synthetic_precision_test','raw_hit_retained_in_raw_result':True})
    map_results,_=map_field_review(root,registry)
    counts['geographic_schema']=0
    for item in map_results:
        if not item['valid']:
            counts['geographic_schema']+=1
        elif item['binary'] and item['file'] in raw_result.get('binary_review_files',[]):
            counts['binary_requires_review']-=1
            items.append({'category':'binary_requires_review','file':item['file'],'classification':'hash_bound_public_RGB_payload_and_every_metadata_field_verified','raw_hit_retained_in_raw_result':True})
    if any(v<0 for v in counts.values()):raise AssertionError('Provenance classification exceeded original raw hits')
    return {'raw_result':raw_result,'classified_nonprivate_hits':items,'unresolved_counts':counts,'unresolved_hit_total':sum(counts.values()),'unresolved_zero':not any(counts.values()),'raw_acceptance_relabelled':False,
      'note':'Authorised exact provenance classifications are applied to unresolved counts. Raw detections remain reported separately; no directory or whole-file waiver is applied.'}


def scan(root):
    root=Path(root).resolve()
    registry_path=root/'tools/privacy_provenance.json'
    registry=json.loads(registry_path.read_text(encoding='utf8')) if registry_path.exists() else {}
    reviewed=semantic_review(root,scan_raw(root),registry)
    classes={}
    for item in reviewed['classified_nonprivate_hits']:
        key=item['classification'];classes[key]=classes.get(key,0)+1
    return dict(files_scanned=reviewed['raw_result']['files_scanned'],pass_zero_hits=reviewed['unresolved_zero'],counts=reviewed['unresolved_counts'],raw_counts=reviewed['raw_result']['counts'],classified_nonprivate_counts=classes,scope='All distribution files; exact hash plus AST/token/field provenance only. No whole-file or directory exemptions. Generated outputs and bytecode are not distributed. Raw detections remain reported.')

if __name__=='__main__':
    root=Path(__file__).resolve().parents[1]
    if len(sys.argv)>1:root=Path(sys.argv[1]).resolve()
    result=scan(root);print(json.dumps(result,indent=2))
    if not result['pass_zero_hits']:raise SystemExit(1)
