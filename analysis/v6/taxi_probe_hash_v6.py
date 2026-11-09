# -*- coding: utf-8 -*-
"""The only script permitted to read the formal key. Never serialise raw plates."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[2]), str(_ReleasePath(__file__).resolve().parents[0])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from pathlib import Path
import hashlib,hmac,json,time,unicodedata,sys
import pandas as pd,numpy as np
R=Path(_release_path('project_root'));O=R/'formal_v6';GPS=Path(_release_path('path_026'))
KEY_PATH=Path(_release_path('path_027'))
_KEY=None
def hasher():
    global _KEY
    if _KEY is None:
        _KEY=KEY_PATH.read_bytes()
        if len(_KEY)!=32:raise RuntimeError('Formal key length invalid')
    key=_KEY
    def compute(plate):
        return hmac.new(key, plate.encode("utf-8"), hashlib.sha256).hexdigest()[:16]
    return compute
def normalise(plate,level):
    if level>=1:plate=plate.strip()
    if level>=2:plate=unicodedata.normalize('NFKC',plate)
    if level>=3:plate=plate.upper()
    if level>=4:plate=plate.replace('·','').replace('.','').replace(' ','')
    return plate
def get_probe_files_hashed():
    report=json.loads((O/'00_env/hash_check_v6.json').read_text(encoding='utf-8'))
    if report['S1_triggered']:raise RuntimeError('S1 prevents dependent source processing')
    f=hasher();return [(p,f(normalise(p.stem,report['selected_normalisation_level']))) for p in sorted(GPS.glob('*.xls'))]
def main():
    start=time.perf_counter();files=sorted(GPS.glob('*.xls'));assert len(files)==290,'Unexpected workbook count'
    f=hasher();control=pd.read_parquet(R/'01_panels/plate_day/2021-07-19.parquet',columns=['ph'])
    control_set=set(control.ph);attempts=[];level=0
    for level in range(5):
        ph=[f(normalise(p.stem,level)) for p in files];n=len(set(ph)&control_set)
        attempts.append(dict(level=level,method=['literal_filename_stem','strip_whitespace','then_NFKC','then_uppercase','then_remove_middle_dot_dot_space'][level],unique_hashes=len(set(ph)),n_seen_0719=n))
        if n>=100:break
    S1=all(x['n_seen_0719']<100 for x in attempts) and len(attempts)==5
    assert len(set(ph))==290,'Probe identifier collision or duplicate'
    old=pd.read_csv(R/'01_panels/taxi_vehicle_day.csv',usecols=['vehicle_hash','batch'])
    # All old-key aliases may include both batches; also report batch counts safely.
    oldover=len(set(ph)&set(old.vehicle_hash));internal=O/'01_internal';internal.mkdir(exist_ok=True)
    (internal/'taxi_probe_ph_v6.txt').write_text('\n'.join(ph)+'\n',encoding='utf-8')
    report=dict(selected_normalisation_level=level,attempts=attempts,n_probe=290,old_hash_overlap=oldover,S1_triggered=S1,S1_zero_only_condition=all(x['n_seen_0719']==0 for x in attempts),acceptance_ge250=n>=250,seconds=time.perf_counter()-start,raw_plate_or_mapping_written=False)
    (O/'00_env/hash_check_v6.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    dayrows=[];rows=[];target=set(ph)
    for p in sorted((R/'01_panels/plate_day').glob('*.parquet')):
        q=pd.read_parquet(p);q=q[q.ph.isin(target)].copy();q['date']=p.stem;rows.append(q)
        dayrows.append(dict(date=p.stem,n_taxi_seen=len(q),rec_all=int(q.n.sum()),rec_stable=int(q.n_stable.sum()),rec_gw=int(q.n_gw.sum())))
    pd.concat(rows,ignore_index=True).to_parquet(internal/'taxi_plate_day_v6.parquet',index=False)
    public=pd.DataFrame(dayrows)
    public['n_taxi_seen']=public['n_taxi_seen'].map(lambda v:'<10' if v<10 else v)
    public.to_csv(O/'03_taxi_probe/hash_daily_check_v6.csv',index=False,encoding='utf-8-sig')
    report['seconds']=time.perf_counter()-start
    (O/'00_env/hash_check_v6.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(n_probe=290,n_seen_0719=n,old_hash_overlap=oldover,S1=S1,seconds=report['seconds'])),flush=True)
if __name__=='__main__':
    try:main()
    except Exception as e:
        # Never expose exception text or locals, which can include workbook stems.
        print('Hash-stage failure type='+type(e).__name__,flush=True);raise SystemExit(1)
