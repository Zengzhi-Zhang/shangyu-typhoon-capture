# -*- coding: utf-8 -*-
"""Create the authorised publication copy; never mutates frozen v1 outputs."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[2]), str(_ReleasePath(__file__).resolve().parent), str(_ReleasePath(__file__).resolve().parent / 'checks')]
import csv,json,shutil
import re
from decimal import Decimal,InvalidOperation
from common_v3 import *
from privacy_check_v3 import vehicle_count_column, COORD, check
DEVICE=re.compile(r'cam_[a-fA-F0-9]{16}')
DEVICE_MAP={}
def public_ids(text):return DEVICE.sub(lambda m:DEVICE_MAP[m.group(0)],text)
def sanitise_json(x):
    if isinstance(x,dict):
        return {public_ids(k):('<10' if vehicle_count_column(k) and isinstance(v,(int,float)) and 0<=v<10 else sanitise_json(v)) for k,v in x.items()}
    if isinstance(x,list):return [sanitise_json(v) for v in x]
    if isinstance(x,str):return public_ids(x)
    return x
def transform(source,target):
    target=guarded(target)
    if source.suffix.lower()=='.csv':
        with source.open('r',encoding='utf-8-sig',newline='') as f:
            reader=csv.DictReader(f);cols=reader.fieldnames;rows=list(reader)
        changed=0
        for r in rows:
            for c,v in r.items():
                nv=public_ids(v);changed+=nv!=v;r[c]=v=nv
                if c.lower() in COORD and v:
                    try:
                        nv=format(float(v),'.2f');changed+=nv!=v;r[c]=nv
                    except ValueError:pass
                elif vehicle_count_column(c) and v and v!='<10':
                    try:
                        if Decimal(v).is_finite() and 0<=Decimal(v)<10:r[c]='<10';changed+=1
                    except InvalidOperation:pass
        with target.open('w',encoding='utf-8-sig',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=cols);writer.writeheader();writer.writerows(rows)
        return changed
    if source.suffix.lower()=='.json':
        ob=json.loads(source.read_text(encoding='utf-8-sig'));new=sanitise_json(ob)
        target.write_text(json.dumps(clean(new),ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
        return int(ob!=new)
    if source.suffix.lower()=='.md':
        original=source.read_text(encoding='utf-8-sig');new=public_ids(original);target.write_text(new,encoding='utf-8');return int(new!=original)
    shutil.copyfile(source,target);return 0
def main():
    start=now();package=ROOT/'pub_package';changes=[]
    ids=set()
    for base in [V1,ROOT]:
        for folder in [p for p in base.iterdir() if p.is_dir() and p.name[:2] in [f'{i:02d}' for i in range(2,9)]]:
            for p in folder.rglob('*'):
                if p.is_file() and p.suffix.lower() in {'.csv','.json','.md'}:ids.update(DEVICE.findall(p.read_text(encoding='utf-8-sig')))
    DEVICE_MAP.update({value:'device'+format(i+1,'06d') for i,value in enumerate(sorted(ids))})
    for base,label in [(V1,'formal_v1'),(ROOT,'formal_v3')]:
        for folder in [p for p in base.iterdir() if p.is_dir() and (p.name[:2] in [f'{i:02d}' for i in range(2,9)] or p.name=='scripts')]:
            for source in sorted(folder.rglob('*')):
                if not source.is_file() or '__pycache__' in source.parts or source.suffix=='.pyc':continue
                rel=source.relative_to(base)
                n=transform(source,package/label/rel)
                if n:changes.append(dict(path=(Path(label)/rel).as_posix(),cells_or_objects_transformed=n))
        for name in (['RESULTS_SUMMARY.md','DEVIATIONS.md','results.json','README.md'] if label=='formal_v1' else ['RESULTS_SUMMARY_v3.md','DEVIATIONS_v3.md','results_v3.json','README_v3.md']):
            transform(base/name,package/label/name)
    readme='上虞台风研究发布包\n\nformal_v1和formal_v3分别保存原冻结结果及授权修正结果。仅包含02–08、汇总、偏离说明、机器结果、README和脚本。01_panels与00_env均不包含。\n\n公开副本仅作隐私格式化：经纬度文本保留两位小数，车辆计数小于10（含0）写为<10；原设备HMAC别名替换为跨版本一致的device序号，映射不发布。原分析结果及全部比值不因发布而重算。脚本复算仍需要未公开内部面板；v3不需要密钥。原v1执行脚本仅供历史方法审阅，不应在冻结目录直接重跑。\n'
    (package/'README.md').write_text(readme,encoding='utf-8')
    write_json(ROOT/'00_env/publication_transformations.json',dict(generated_at=now(),changes=changes,source_outputs_modified=False,n_public_device_aliases=len(DEVICE_MAP),device_mapping_published=False))
    report=check(package)
    stage_record('publication',start,['pub_package','pub_package/PRIVACY_CHECK.json'],dict(privacy_passed=report['passed'],n_transformed_files=len(changes)))
    if not report['passed']:raise RuntimeError('Publication privacy audit failed; inspect report before delivery.')
    print('Publication package privacy pass',flush=True)
if __name__=='__main__':main()
