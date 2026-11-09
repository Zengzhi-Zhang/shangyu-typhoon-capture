# -*- coding: utf-8 -*-
"""Frozen-panel utilities for new v7 health sensitivity quantities.

No source, secret, pre-v6 output mutation or H1-H4 verdict recomputation.
"""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[2]), str(_ReleasePath(__file__).resolve().parents[0])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from pathlib import Path
from datetime import datetime, timezone, timedelta
import hashlib, json
import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy.spatial import cKDTree

V1=Path(_release_path('project_root')); V3=V1/'formal_v3'; V6=V1/'formal_v6'; ROOT=V1/'formal_v7'
PANELS=V1/'01_panels'; SEED=20261005; N_BOOT=500
def days(a,b): return pd.date_range(a,b).strftime('%Y-%m-%d').tolist()
D_ALL=['2021-06-17']+days('2021-06-28','2021-08-02')
D_PARTIAL=['2021-07-'+d for d in ['08','10','22','23','24','25']]
B1=[d for d in days('2021-07-05','2021-07-21') if d not in D_PARTIAL]
B3=['2021-06-17']+days('2021-06-28','2021-07-04')
EVENT=days('2021-07-25','2021-08-02')
D_STATE=['2021-07-19','2021-07-25','2021-07-26','2021-07-27','2021-07-28','2021-07-29','2021-07-30','2021-08-02','2021-07-08','2021-07-10']
STATE_ORDER=['zero','offline','partial_channel','recognition_degraded','low_all_channels','degraded_other','normal']
D_INELIG=set(D_PARTIAL+days('2021-07-26','2021-08-02'))
RINGS=['0-2','2-4','4-7','7-12','12-20','20+']; FIVE=['0-2','2-4','4-7','7-12','12+']
EDGES=[0,2,4,7,12,20,np.inf]
TRANS=Transformer.from_crs(4326,32651,always_xy=True)
INVERSE=Transformer.from_crs(32651,4326,always_xy=True)

def now(): return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def clean(x):
    if isinstance(x,dict): return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)): return [clean(v) for v in x]
    if isinstance(x,np.ndarray): return clean(x.tolist())
    if isinstance(x,np.generic): return clean(x.item())
    if isinstance(x,float) and not np.isfinite(x): return None
    if isinstance(x,Path): return str(x)
    return x
def write_json(path,obj):
    p=Path(path); assert ROOT in p.parents
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(clean(obj),ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def save_csv(q,path,coords=False):
    p=Path(path); assert ROOT in p.parents
    p.parent.mkdir(parents=True,exist_ok=True)
    data=q.copy()
    if coords:
        for c in ['plot_lon','plot_lat']:
            if c in data:data[c]=data[c].map(lambda v:'' if pd.isna(v) else f'{v:.2f}')
    data.to_csv(p,index=False,encoding='utf-8-sig',float_format='%.12g')
def require_protocol(path):
    p=Path(path)
    if not p.is_file():raise RuntimeError('Protocol must be frozen by root before numerical execution')
    return dict(path=str(p),sha256=sha(p))
def refs(date,pool=B1):return [d for d in pool if pd.Timestamp(d).dayofweek==pd.Timestamp(date).dayofweek]
def ratio(n,b):
    n=np.asarray(n,float);b=np.asarray(b,float)
    return float(n.sum()/b.sum()) if b.sum()>0 else np.nan
def ci(x):
    x=np.asarray(x,float);x=x[np.isfinite(x)]
    return tuple(np.quantile(x,[.025,.975])) if len(x) else (np.nan,np.nan)
def ring(x,five=False):
    labels=FIVE if five else RINGS;edges=[0,2,4,7,12,np.inf] if five else EDGES
    return pd.cut(x,edges,labels=labels,right=False,include_lowest=True).astype(object).fillna('missing')

class Panels:
    def __init__(self):
        self.input_hashes={};self.checks={}
        self.attr=self.read(PANELS/'device_attributes.csv').set_index('dev').sort_index()
        self.attr['dev_public']=np.arange(1,len(self.attr)+1,dtype=int)
        self.devs=self.attr.index.to_numpy();self.n_dev=len(self.attr)
        h=self.read(PANELS/'device_hour.csv',usecols=['dev','date','hour','n','n_unread'])
        full=pd.MultiIndex.from_product([self.devs,D_ALL,range(24)],names=['dev','date','hour'])
        vals=h.groupby(['dev','date','hour'])[['n','n_unread']].sum().reindex(full,fill_value=0)
        self.hour=vals.n.to_numpy(float).reshape(self.n_dev,len(D_ALL),24)
        self.unread=vals.n_unread.to_numpy(float).reshape(self.n_dev,len(D_ALL),24)
        # Frozen v3 daily sums include unassigned hours (e.g. hour=-1).
        # Hourly diagnostics use only clock hours0-23; never drop unassigned
        # records from the all-day ratio or unread numerator.
        self.daily=h.pivot_table(index='dev',columns='date',values='n',aggfunc='sum',fill_value=0).reindex(index=self.devs,columns=D_ALL,fill_value=0).to_numpy(float)
        self.daily_unread=h.pivot_table(index='dev',columns='date',values='n_unread',aggfunc='sum',fill_value=0).reindex(index=self.devs,columns=D_ALL,fill_value=0).to_numpy(float)
        self.afternoon=self.hour[:,:,11:].sum(axis=2);self.afternoon_unread=self.unread[:,:,11:].sum(axis=2)
        self.unassigned_hour=self.daily-self.hour.sum(axis=2);self.unassigned_unread=self.daily_unread-self.unread.sum(axis=2)
        self.day_index={d:i for i,d in enumerate(D_ALL)}
        dd=self.read(PANELS/'device_day.csv',usecols=['dev','date','n'])
        day=dd.pivot_table(index='dev',columns='date',values='n',aggfunc='sum',fill_value=0).reindex(index=self.devs,columns=D_ALL,fill_value=0).to_numpy(float)
        self.checks['hour_day_panel_exact']=bool(np.array_equal(day,self.daily))
        if not self.checks['hour_day_panel_exact']:raise AssertionError('Frozen hour/day panel mismatch')
        for c in ['in_A100','in_A200','in_Sstar']:self.attr[c]=self.attr[c].astype(int)
        self.A100=self.attr.in_A100.to_numpy(bool);self.A200=self.attr.in_A200.to_numpy(bool);self.Sstar=self.attr.in_Sstar.to_numpy(bool)
        self.xy=np.full((self.n_dev,2),np.nan)
        valid=self.attr.lon.notna()&self.attr.lat.notna()&self.attr.lon.gt(0)&self.attr.lat.gt(0)
        self.xy[valid]=np.column_stack(TRANS.transform(self.attr.loc[valid,'lon'],self.attr.loc[valid,'lat']))
        self.coord=np.isfinite(self.xy).all(axis=1)
        self.attr['ring']=ring(self.attr.dist_baiguan_km)
        self.attr['base_flow_quartile']='missing'
        ranks=pd.Series(self.attr.loc[self.A200,'base_B1'].to_numpy()).rank(method='first')
        self.attr.loc[self.A200,'base_flow_quartile']=pd.qcut(ranks,4,labels=['Q1','Q2','Q3','Q4']).astype(str).to_numpy()
    def read(self,path,**kwargs):
        self.input_hashes[str(path)]=sha(path)
        return pd.read_csv(path,encoding='utf-8-sig',**kwargs)
    def vectors(self,date,matched=None,pool=B1):
        if matched is None:matched=date=='2021-07-25'
        mat=self.afternoon if matched else self.daily
        targets=refs(date,pool)
        if not targets:raise RuntimeError('Same-weekday baseline empty')
        return mat[:,self.day_index[date]],mat[:,[self.day_index[d] for d in targets]].mean(axis=1)
    def a1(self,date):
        """Exact denominator logic copied from v3 Run.a1; no verdict recomputation."""
        matched=date=='2021-07-25';mat=self.afternoon if matched else self.daily
        r=[d for d in refs(date) if d!=date];pool='B1'
        if not r:r=[d for d in refs(date,sorted(set(B1+B3))) if d!=date];pool='B1+B3'
        if not r:raise RuntimeError('A1 leave-one-out baseline empty')
        b=mat[:,[self.day_index[d] for d in r]].mean(axis=1);n=mat[:,self.day_index[date]]
        prev=(pd.Timestamp(date)-pd.Timedelta(days=7)).strftime('%Y-%m-%d')
        daybad=prev in D_INELIG or prev not in self.day_index
        denom=b.copy();devicebad=np.zeros(self.n_dev,bool)
        if not daybad:
            previous=mat[:,self.day_index[prev]];devicebad=previous<.5*b;denom=np.where(devicebad,b,previous)
        rr=np.divide(n,denom,out=np.full(self.n_dev,np.nan),where=denom>0)
        return dict(n=n,b_loo=b,denom=denom,ratio=rr,failed=self.A200&(n<.05*denom),
                    daybad=daybad,devicebad=devicebad,prev=prev,baseline_days=r,baseline_pool=pool,hour_matched=int(matched))
    def a1_audit(self,dates):
        old=self.read(V3/'06_m5_bias_correction/m5_failure_counts_v3.csv').set_index('date')
        rows=[]
        for d in dates:
            s=self.a1(d);observed=int(s['failed'].sum());expected=int(old.loc[d,'n_failed_A1'])
            rows.append(dict(date=d,n_failed_reconstructed=observed,n_failed_v3=expected,exact=observed==expected))
            if observed!=expected:raise AssertionError('A1 failed count mismatch on '+d)
        return rows
    def neighbour_indices(self,universe=None):
        """Directed six nearest neighbours, UTM51N; excludes self by row index."""
        use=self.A200 if universe is None else np.asarray(universe,bool)
        source=np.flatnonzero(use&self.coord);out={}
        if not len(source):return out
        tree=cKDTree(self.xy[source]);k=min(len(source),8)
        targets=np.flatnonzero(self.coord)
        positions=np.asarray(tree.query(self.xy[targets],k=k)[1]).reshape(len(targets),-1)
        for i,js in zip(targets,positions):out[int(i)]=np.array([int(source[j]) for j in js if int(source[j])!=int(i)][:6],int)
        return out
    def unchanged(self):return all(sha(p)==h for p,h in self.input_hashes.items())

def fit_ols(attr,r,select,date):
    """Same formula, covariate construction and complete cases as v3 fit_model."""
    import statsmodels.formula.api as smf
    formula='response ~ np.log1p(dist_baiguan_km) + log_base + elev_m + relief_300m + C(road_level) + C(org) + gateway'
    x=attr.loc[select & attr.lon.notna() & attr.lat.notna()].copy()
    x['log_base']=np.log(x.base_B1.where(x.base_B1.gt(0)))
    ratios=pd.Series(r,index=attr.index).reindex(x.index)
    x['response']=np.log(ratios.clip(.05,3));x['treated_as_floor']=(ratios<.05).astype(int)
    x=x.replace([np.inf,-np.inf],np.nan).dropna(subset=['response','dist_baiguan_km','log_base','elev_m','relief_300m','road_level','org','gateway'])
    if not len(x):raise RuntimeError('No S_pre OLS complete cases')
    fit=smf.ols(formula,data=x).fit(cov_type='HC1');conf=fit.conf_int(alpha=.05)
    return pd.DataFrame([dict(date=date,sample='S_pre',term=t,coef=float(v),se_HC1=float(fit.bse[t]),p=float(fit.pvalues[t]),
        n=int(fit.nobs),r_squared=float(fit.rsquared),ci_lo=float(conf.loc[t,0]),ci_hi=float(conf.loc[t,1]),
        n_treated_as_floor=int(x.treated_as_floor.sum()),response='log(r.clip(0.05,3))',covariance='HC1') for t,v in fit.params.items()])
