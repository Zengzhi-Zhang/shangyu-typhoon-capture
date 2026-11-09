# -*- coding: utf-8 -*-
"""Shared v3 definitions. Reads existing formal_v1 panels, never a HMAC key.

All writes are guarded to formal_v3; raw source paths are not inputs here.
"""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[2]), str(_ReleasePath(__file__).resolve().parents[0])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from pathlib import Path
import json, os, sys, hashlib
from datetime import datetime, timezone, timedelta
import numpy as np
import pandas as pd

V1=INPUT=INPUT_ROOT=V1_ROOT=Path(_release_path('project_root'))
ROOT=OUT=OUTPUT_ROOT=V3_ROOT=V1/'formal_v3'
PANELS=V1/'01_panels'
SEED=20261005
TZ=timezone(timedelta(hours=8))
np.random.seed(SEED)
def now():return datetime.now(TZ).isoformat(timespec='seconds')
def dates(a,b):return pd.date_range(a,b).strftime('%Y-%m-%d').tolist()
D_ALL=['2021-06-17']+dates('2021-06-28','2021-08-02')
D_PARTIAL=['2021-07-'+d for d in ['08','10','22','23','24','25']]
B1=[d for d in dates('2021-07-05','2021-07-21') if d not in D_PARTIAL]
B2=dates('2021-07-12','2021-07-21')
B3=['2021-06-17']+dates('2021-06-28','2021-07-04')
B_TAXI=dates('2021-07-06','2021-07-21')
B_P=['2021-06-17']+[d for d in dates('2021-06-28','2021-07-09') if d!='2021-07-08']
BASELINES=dict(B1=B1,B2=B2,B3=B3,B_P=B_P)
W_T=dates('2021-07-12','2021-07-21');E_T=dates('2021-07-25','2021-08-02')
W_P=dates('2021-06-28','2021-07-07');E_P=dates('2021-07-11','2021-07-19')
SHOCK=dates('2021-07-25','2021-07-26');RECOV=dates('2021-07-27','2021-08-02')
D_INELIG=sorted(set(D_PARTIAL+SHOCK+RECOV))
COLORS=['#2a78d6','#eb6834','#1baf7a','#eda100']
def refs(date,baseline='B1'):
    ds=BASELINES[baseline] if isinstance(baseline,str) else baseline
    return [d for d in ds if pd.Timestamp(d).dayofweek==pd.Timestamp(date).dayofweek]
def guarded(path):
    path=Path(path).resolve()
    if ROOT.resolve() not in path.parents:raise RuntimeError('All v3 output must stay in formal_v3.')
    path.parent.mkdir(parents=True,exist_ok=True)
    return path
def clean(x):
    if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [clean(v) for v in x]
    if isinstance(x,Path):return str(x)
    if isinstance(x,np.generic):return clean(x.item())
    if isinstance(x,float) and not np.isfinite(x):return None
    return x
def write_json(path,obj):guarded(path).write_text(json.dumps(clean(obj),ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def save_csv(df,path,**kwargs):
    export=df.copy()
    for c in ['lon','lat','plot_lon','plot_lat']:
        if c in export:export[c]=pd.to_numeric(export[c],errors='coerce').round(2)
    export.to_csv(guarded(path),index=False,encoding='utf-8-sig',float_format='%.4f',**kwargs)
def load_panels():
    dh=pd.read_csv(PANELS/'device_hour.csv',encoding='utf-8-sig')
    attr=pd.read_csv(PANELS/'device_attributes.csv',encoding='utf-8-sig').set_index('dev',drop=False)
    dd=dh.pivot_table(index='dev',columns='date',values='n',aggfunc='sum',fill_value=0).reindex(index=attr.index,columns=D_ALL,fill_value=0)
    return dh,attr,dd
def device_vectors(date,baseline='B1',hour_matched=True,dh=None,dd=None):
    if dh is None or dd is None:dh,_,dd=load_panels()
    mat=dd
    if date=='2021-07-25' and hour_matched:
        mat=dh[dh.hour.between(11,23)].pivot_table(index='dev',columns='date',values='n',aggfunc='sum',fill_value=0).reindex(index=dd.index,columns=D_ALL,fill_value=0)
    return mat[date],mat[refs(date,baseline)].mean(axis=1)
def boot_ratio(n,b,B=500,seed=SEED):
    n=np.asarray(n,float);b=np.asarray(b,float)
    if not len(n) or b.sum()<=0:return np.nan,np.nan
    rng=np.random.default_rng(seed);ix=rng.integers(0,len(n),size=(B,len(n)))
    r=np.divide(n[ix].sum(axis=1),b[ix].sum(axis=1),out=np.full(B,np.nan),where=b[ix].sum(axis=1)>0)
    return tuple(np.nanquantile(r,[.025,.975]))
def stage_record(stage,start,outputs,details=None):
    record=dict(stage=stage,start=start,end=now(),command=[sys.executable]+sys.argv,outputs=outputs,details=details or {})
    history=ROOT/'00_env/execution_history_v3.json'
    if history.exists():events=json.loads(history.read_text(encoding='utf-8'))
    else:
        events=[]
        for p in sorted((ROOT/'00_env').glob('*execution*.json')):
            value=json.loads(p.read_text(encoding='utf-8-sig'))
            if isinstance(value,dict) and (value.get('start') or value.get('started')):
                events.append(dict(provenance='Previously retained stage record',record_file=p.name,**value))
    events.append(record);write_json(history,events)
    write_json(ROOT/f'00_env/{stage}_execution.json',record)
def setup_plot():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Microsoft YaHei','SimHei','DejaVu Sans'],'text.color':'#333333','axes.labelcolor':'#333333','xtick.color':'#333333','ytick.color':'#333333','axes.prop_cycle':matplotlib.cycler(color=COLORS),'lines.linewidth':2,'lines.markersize':8,'grid.linewidth':.4,'grid.alpha':.3,'axes.unicode_minus':False,'figure.dpi':170,'savefig.dpi':170})
    return plt
