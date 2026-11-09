# -*- coding: utf-8 -*-
"""Read-only revalidation of the three explicitly reusable frozen panels."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[3]), str(_ReleasePath(__file__).resolve().parents[1]), str(_ReleasePath(__file__).resolve().parent)]
import hashlib
from common_v1 import *
START=now()
def fingerprints(paths):
    out=metadata(paths)
    for path,row in zip(paths,out):
        with path.open('rb') as f:
            first=f.read(1024**2);f.seek(max(0,path.stat().st_size-1024**2));last=f.read(1024**2)
        row.update(sha256_head1MB=hashlib.sha256(first).hexdigest(),sha256_tail1MB=hashlib.sha256(last).hexdigest())
    return out
def equivalent(a,b):
    if a.shape!=b.shape or list(a.columns)!=list(b.columns):return False
    for c in a:
        x=pd.to_numeric(a[c],errors='coerce');y=pd.to_numeric(b[c],errors='coerce')
        # Preserve strings and missingness; allow only the declared four-place serialization loss.
        if x.notna().sum()==a[c].notna().sum() and y.notna().sum()==b[c].notna().sum():
            if not np.allclose(x,y,atol=.00005001,rtol=0,equal_nan=True):return False
        elif not a[c].fillna('').astype(str).equals(b[c].fillna('').astype(str)):return False
    return True
def main():
    names=['device_hour.csv','device_dir_lane_day.csv','taxi_vehicle_day_all.csv']
    paths=[REF/'results'/n for n in names];before=fingerprints(paths)
    mapping=pd.read_csv(ROOT/'01_panels/device_id_map.csv').set_index('dev_name').dev.to_dict()
    checks={}
    for old,new in zip(names,['device_hour.csv','device_dir_lane_day.csv','taxi_vehicle_day.csv']):
        a=pd.read_csv(REF/'results'/old,encoding='utf-8-sig');b=pd.read_csv(ROOT/'01_panels'/new,encoding='utf-8-sig')
        if 'dev' in a:
            a.dev=a.dev.map(mapping)
            a.date=pd.to_datetime(a.date.astype(str).str.replace('"','',regex=False)).dt.strftime('%Y-%m-%d')
        if 'sheet_date' in a:a.sheet_date=pd.to_datetime(a.sheet_date.astype(str),format='%Y%m%d').dt.strftime('%Y-%m-%d')
        checks[new]=dict(rows=len(b),matches_frozen_reference=equivalent(a,b),numeric_serialization_tolerance=.00005001)
    after=fingerprints(paths)
    passed=before==after and all(x['matches_frozen_reference'] for x in checks.values())
    report=dict(started=START,ended=now(),passed=passed,checks=checks,before=before,after=after,scope='Reference panels revalidation before/after fingerprints; original protocol source initial/final manifest remains separate. No historical initial reference fingerprint is inferred.')
    write_json(ROOT/'00_env/reference_revalidation.json',report)
    stage_record('reference_revalidation',START,['00_env/reference_revalidation.json'],report)
    print('Frozen-reference panel revalidation',passed,flush=True)
    if not passed:raise RuntimeError('Reference revalidation failed; inspect protected local report.')
if __name__=='__main__':main()
