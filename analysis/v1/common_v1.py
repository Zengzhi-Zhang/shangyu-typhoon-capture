# -*- coding: utf-8 -*-
"""Frozen formal-v1 definitions. Internal coordinates and pseudonyms are not publication data."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[2]), str(_ReleasePath(__file__).resolve().parents[0])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from pathlib import Path
import json, os, time, hashlib, hmac
from datetime import datetime, timezone, timedelta
import numpy as np
import pandas as pd

ROOT = Path(_release_path('project_root'))
REF = Path(_release_path('path_005'))
SOURCE = Path(_release_path('path_006'))
SEED = 20261005
np.random.seed(SEED)
def dates(a,b): return pd.date_range(a,b).strftime('%Y-%m-%d').tolist()
D_ALL = ['2021-06-17'] + dates('2021-06-28','2021-08-02')
D_PARTIAL = ['2021-07-'+d for d in ['08','10','22','23','24','25']]
B1 = [d for d in dates('2021-07-05','2021-07-21') if d not in D_PARTIAL]
B2 = dates('2021-07-12','2021-07-21')
B3 = ['2021-06-17'] + dates('2021-06-28','2021-07-04')
B_TAXI = dates('2021-07-06','2021-07-21')
BASELINES = dict(B1=B1,B2=B2,B3=B3)
W_T = dates('2021-07-12','2021-07-21'); E_T = dates('2021-07-25','2021-08-02')
W_P = dates('2021-06-28','2021-07-07'); E_P = dates('2021-07-11','2021-07-19')
COLORS = ['#2a78d6','#eb6834','#1baf7a','#eda100']
TZ = timezone(timedelta(hours=8))
def now(): return datetime.now(TZ).isoformat(timespec='seconds')
def key(): return (_ReleasePath(_release_key_file())).read_bytes()
def pseudonym(value,prefix=''): return prefix+hmac.new(key(),str(value).encode('utf-8'),hashlib.sha256).hexdigest()[:16]
def refs(date,baseline='B1'):
    days=BASELINES[baseline] if isinstance(baseline,str) else baseline
    return [d for d in days if pd.Timestamp(d).dayofweek==pd.Timestamp(date).dayofweek]
def write_json(path,obj):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    def fix(x):
        if isinstance(x,dict):return {str(k):fix(v) for k,v in x.items()}
        if isinstance(x,(list,tuple)):return [fix(v) for v in x]
        if isinstance(x,Path):return str(x)
        if isinstance(x,np.generic):return fix(x.item())
        if isinstance(x,float) and not np.isfinite(x):return None
        return x
    path.write_text(json.dumps(fix(obj),ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def save_csv(df,path,**kwargs):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    export=df.copy()
    if '01_panels' in path.parts:
        for c in ['lon','lat']:
            if c in export:export[c]=export[c].map(lambda v:format(float(v),'.12f') if pd.notna(v) else '')
    export.to_csv(path,index=False,encoding='utf-8-sig',float_format='%.4f',**kwargs)
def setup_plot():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Microsoft YaHei','SimHei','DejaVu Sans'],
      'text.color':'#333333','axes.labelcolor':'#333333','xtick.color':'#333333','ytick.color':'#333333',
      'axes.prop_cycle':matplotlib.cycler(color=COLORS),'lines.linewidth':2,'lines.markersize':8,
      'grid.linewidth':0.4,'grid.alpha':0.3,'axes.unicode_minus':False,'figure.dpi':170,'savefig.dpi':170})
    return plt
def load_panels():
    dh=pd.read_csv(ROOT/'01_panels/device_hour.csv',encoding='utf-8-sig')
    attr=pd.read_csv(ROOT/'01_panels/device_attributes.csv',encoding='utf-8-sig').set_index('dev',drop=False)
    dd=dh.pivot_table(index='dev',columns='date',values='n',aggfunc='sum',fill_value=0).reindex(index=attr.index,columns=D_ALL,fill_value=0)
    return dh,attr,dd
def device_vectors(date,baseline='B1',hour_matched=True,dh=None,dd=None):
    if dh is None or dd is None: dh,_,dd=load_panels()
    if date=='2021-07-25' and hour_matched:
        mat=dh[dh.hour.between(11,23)].pivot_table(index='dev',columns='date',values='n',aggfunc='sum',fill_value=0).reindex(index=dd.index,columns=D_ALL,fill_value=0)
    else:mat=dd
    return mat[date],mat[refs(date,baseline)].mean(axis=1)
def failure_vectors(date,dh,dd,baseline='B1',hour_matched=False):
    n,b=device_vectors(date,baseline,hour_matched,dh,dd)
    prev=(pd.Timestamp(date)-pd.Timedelta(days=7)).strftime('%Y-%m-%d')
    if prev in D_ALL and prev not in D_PARTIAL:
        if hour_matched and date=='2021-07-25':
            den=dh[(dh.date==prev)&dh.hour.between(11,23)].groupby('dev').n.sum().reindex(dd.index,fill_value=0)
        else:den=dd[prev]
        kind='previous_week'
    else:den=b;kind='dow_baseline_fallback'
    return n,den,b,kind
def boot_ratio(n,b,B=500,seed=SEED):
    n=np.asarray(n,float);b=np.asarray(b,float)
    if not len(n) or b.sum()<=0:return np.nan,np.nan
    rng=np.random.default_rng(seed)
    ix=rng.integers(0,len(n),size=(B,len(n)))
    den=b[ix].sum(axis=1)
    r=np.divide(n[ix].sum(axis=1),den,out=np.full(B,np.nan),where=den>0)
    return tuple(np.nanquantile(r,[.025,.975]))
def stage_record(stage,start,outputs,details=None):
    write_json(ROOT/f'00_env/{stage}_execution.json',dict(stage=stage,start=start,end=now(),command=f'{_release_path("path_007")}{stage}_v1.py',outputs=outputs,details=details or {}))
def metadata(paths):
    out=[]
    for p in paths:
        p=Path(p);s=p.stat();out.append(dict(path=str(p),size=s.st_size,mtime=datetime.fromtimestamp(s.st_mtime,TZ).isoformat(),mtime_ns=s.st_mtime_ns))
    return out
