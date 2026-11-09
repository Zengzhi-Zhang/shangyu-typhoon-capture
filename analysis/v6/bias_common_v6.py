# -*- coding: utf-8 -*-
"""Read-only local panel utilities for new I4/I5/I7 quantities only."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[2]), str(_ReleasePath(__file__).resolve().parents[0])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from pathlib import Path
from datetime import datetime, timezone, timedelta
import hashlib,json,sys,time
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from pyproj import Transformer

SEED=20261005;N_BOOT=500;N_REP=200
V1=Path(_release_path('project_root'));V3=V1/'formal_v3';ROOT=V1/'formal_v6'
def days(a,b):return pd.date_range(a,b).strftime('%Y-%m-%d').tolist()
D_PARTIAL=['2021-07-'+v for v in ['08','10','22','23','24','25']]
B1=[d for d in days('2021-07-05','2021-07-21') if d not in D_PARTIAL]
B3=['2021-06-17']+days('2021-06-28','2021-07-04')
EVENT=days('2021-07-25','2021-08-02');D_INELIG=set(D_PARTIAL+days('2021-07-26','2021-08-02'))
RINGS=['0-2','2-4','4-7','7-12','12-20','20+'];FIVE=['0-2','2-4','4-7','7-12','12+']
def now():return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
def clean(x):
    if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [clean(v) for v in x]
    if isinstance(x,np.generic):return clean(x.item())
    if isinstance(x,float) and not np.isfinite(x):return None
    if isinstance(x,Path):return str(x)
    return x
def guarded(path):
    p=Path(path).resolve()
    if ROOT.resolve() not in p.parents:raise RuntimeError('Output outside formal_v6 refused')
    p.parent.mkdir(parents=True,exist_ok=True);return p
def write_json(path,obj):guarded(path).write_text(json.dumps(clean(obj),ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def check_protocol(path):
    p=Path(path).resolve()
    if ROOT.resolve()/'00_env' not in p.parents:raise RuntimeError('Protocol must be in formal_v6/00_env')
    j=json.loads(p.read_text(encoding='utf-8'))
    if not (j.get('frozen_at') or j.get('status','').lower().startswith('frozen') or j.get('protocol_frozen')):raise RuntimeError('Protocol not frozen')
    return p,hashlib.sha256(p.read_bytes()).hexdigest()
def ratio(n,b):return float(np.sum(n)/np.sum(b)) if np.sum(b)>0 else np.nan
def ci(x):
    x=np.asarray(x,float);x=x[np.isfinite(x)];return tuple(np.quantile(x,[.025,.975])) if len(x) else (np.nan,np.nan)
def refs(date,pool=B1):return [d for d in pool if pd.Timestamp(d).dayofweek==pd.Timestamp(date).dayofweek]
class Stage:
    def __init__(self,name,protocol):
        self.name=name;self.started=now();self.clock=time.monotonic();self.protocol,self.protocol_hash=check_protocol(protocol)
        self.inputs={};self.outputs=[];self.checks={};self.notes=[]
        self.rules_path=ROOT/'00_env/interpretation_bias_v6.json';self.rules_hash=hashlib.sha256(self.rules_path.read_bytes()).hexdigest()
        self.addendum_path=ROOT/'00_env/implementation_addendum_bias_v6.json';self.addendum_hash=hashlib.sha256(self.addendum_path.read_bytes()).hexdigest()
    def read(self,path,**kwargs):
        path=Path(path);st=path.stat();self.inputs[str(path)]=dict(size=st.st_size,mtime_ns=st.st_mtime_ns)
        return pd.read_csv(path,encoding='utf-8-sig',**kwargs)
    def save(self,df,path,internal=False):
        path=guarded(path);d=df.copy()
        if not internal:
            for c in d:
                if c in ['lon','lat','longitude','latitude','plot_lon','plot_lat']:d[c]=pd.to_numeric(d[c],errors='coerce').round(2)
                if d[c].dtype==object and d[c].astype(str).str.contains(r'cam_|\b[0-9a-fA-F]{16}\b',regex=True).any():raise RuntimeError('Internal identifier in public output')
        if path.suffix=='.parquet':d.to_parquet(path,index=False)
        else:d.to_csv(path,index=False,encoding='utf-8-sig',float_format='%.12g' if internal else '%.4f')
        self.outputs.append(dict(file=path.relative_to(ROOT).as_posix(),rows=len(df),internal=internal));return df
    def finish(self,details=None):
        for p,before in self.inputs.items():
            st=Path(p).stat();self.checks['unchanged:'+Path(p).name]=before==dict(size=st.st_size,mtime_ns=st.st_mtime_ns)
        self.checks['protocol_unchanged']=self.protocol_hash==hashlib.sha256(self.protocol.read_bytes()).hexdigest()
        self.checks['rules_unchanged']=self.rules_hash==hashlib.sha256(self.rules_path.read_bytes()).hexdigest()
        self.checks['implementation_addendum_unchanged']=self.addendum_hash==hashlib.sha256(self.addendum_path.read_bytes()).hexdigest()
        failed=[k for k,v in self.checks.items() if isinstance(v,(bool,np.bool_)) and not v]
        record=dict(status='complete' if not failed else 'failed',started=self.started,ended=now(),seconds=time.monotonic()-self.clock,
            command=[sys.executable]+sys.argv,seed=SEED,inputs=self.inputs,outputs=self.outputs,checks=self.checks,details=details or {},notes=self.notes,protocol_file=str(self.protocol),protocol_sha256=self.protocol_hash,
            implementation_addendum_file=str(self.addendum_path),implementation_addendum_sha256=self.addendum_hash)
        write_json(ROOT/f'00_env/{self.name}_execution_v6.json',record)
        print(json.dumps(dict(stage=self.name,status=record['status'],seconds=round(record['seconds'],2),outputs=len(self.outputs),failed=failed)),flush=True)
        if failed:raise AssertionError('Local integrity checks failed')
class Panels:
    def __init__(self,stage):
        self.stage=stage;a=stage.read(V1/'01_panels/device_attributes.csv').sort_values('dev').reset_index(drop=True)
        self.attr=a;self.names=a.dev.astype(str).to_numpy();self.public=np.arange(1,len(a)+1)
        self.A100=a.in_A100.astype(int).to_numpy(bool);self.A200=a.in_A200.astype(int).to_numpy(bool);self.Sstar=a.in_Sstar.astype(int).to_numpy(bool)
        h=stage.read(V1/'01_panels/device_hour.csv',usecols=['date','dev','hour','n']);h.date=h.date.astype(str).str.replace('"','',regex=False)
        self.dates=sorted(h.date.unique());self.daily=h.pivot_table(index='dev',columns='date',values='n',aggfunc='sum',fill_value=0).reindex(index=self.names,columns=self.dates,fill_value=0)
        self.afternoon=h[h.hour.between(11,23)].pivot_table(index='dev',columns='date',values='n',aggfunc='sum',fill_value=0).reindex(index=self.names,columns=self.dates,fill_value=0)
        self.online={}
        for d,g in stage.read(V1/'01_panels/online_sets.csv').groupby('date'):self.online[d]=np.isin(self.names,g.dev.astype(str))&self.A100
        self.xy=np.full((len(a),2),np.nan);ok=a.lon.notna()&a.lat.notna()&a.lon.ne(0)&a.lat.ne(0);tr=Transformer.from_crs(4326,32651,always_xy=True)
        self.xy[ok]=np.column_stack(tr.transform(a.loc[ok,'lon'],a.loc[ok,'lat']));self.coord=np.isfinite(self.xy).all(axis=1)
        self.ring6=pd.cut(a.dist_baiguan_km,[-np.inf,2,4,7,12,20,np.inf],labels=RINGS,right=False).astype(object).fillna('missing').to_numpy()
        self.ring5=np.array([{'12-20':'12+','20+':'12+'}.get(v,v) for v in self.ring6],object)
        self.strata=(a.road_level.fillna('missing').astype(str)+'|'+pd.Series(self.ring6)).to_numpy();self.org=a.org.fillna('missing').astype(str).to_numpy()
    def vectors(self,date):
        mat=self.afternoon if date=='2021-07-25' else self.daily
        n=mat[date].to_numpy(float);b=mat[refs(date)].mean(axis=1).to_numpy(float)
        r=np.divide(n,b,out=np.full(len(b),np.nan),where=b>0);return n,b,r
    def a1(self,date):
        mat=self.afternoon if date=='2021-07-25' else self.daily;r=[d for d in refs(date) if d!=date]
        if not r:r=[d for d in refs(date,sorted(set(B1+B3))) if d!=date]
        b=mat[r].mean(axis=1).to_numpy(float);prev=(pd.Timestamp(date)-pd.Timedelta(days=7)).strftime('%Y-%m-%d');den=b.copy()
        if prev in mat and prev not in D_INELIG:
            old=mat[prev].to_numpy(float);den=np.where(old>=.5*b,old,b)
        n=mat[date].to_numpy(float);return np.divide(n,den,out=np.full(len(den),np.nan),where=den>0),den
    def predict(self,r,donor,target):
        ix=np.flatnonzero(donor&np.isfinite(r));targets=np.flatnonzero(target);knn=np.full(len(r),np.nan);stratum=knn.copy()
        if not len(ix):return knn,stratum,dict(n_knn_global_fallback=len(targets),n_stratum_knn_fallback=len(targets),n_no_donor=len(targets))
        knn[targets]=np.median(r[ix]);good=ix[self.coord[ix]];tgood=targets[self.coord[targets]]
        if len(good) and len(tgood):
            k=min(6,len(good));neighbors=np.asarray(cKDTree(self.xy[good]).query(self.xy[tgood],k=k)[1]).reshape(len(tgood),k);knn[tgood]=np.median(r[good[neighbors]],axis=1)
        stratum[targets]=knn[targets];fallback=len(targets)
        for layer in np.unique(self.strata[targets]):
            if layer.endswith('|missing') or layer.startswith('missing|'):continue
            ld=ix[self.strata[ix]==layer];lt=targets[self.strata[targets]==layer]
            if len(ld)>=5:stratum[lt]=np.median(r[ld]);fallback-=len(lt)
        return knn,stratum,dict(n_knn_global_fallback=int((target&~self.coord).sum()) if len(good) else len(targets),n_stratum_knn_fallback=fallback,n_no_donor=0)
