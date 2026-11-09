# -*- coding: utf-8 -*-
"""Assemble v7 T37 and reports from computed, auditable local outputs."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[2]), str(_ReleasePath(__file__).resolve().parents[0])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from pathlib import Path
from datetime import datetime,timezone,timedelta
import argparse,hashlib,json,math,sys
import pandas as pd
R=Path(_release_path('v7_root'));E=R/'00_env';V1=R.parent
EVENT=pd.date_range('2021-07-25','2021-08-02').strftime('%Y-%m-%d').tolist()
def now():return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
def clean(x):
    if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [clean(v) for v in x]
    if hasattr(x,'item'):return clean(x.item())
    if isinstance(x,float) and not math.isfinite(x):return None
    return x
def put(p,x):(R/p).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def read(p):return pd.read_csv(R/p,encoding='utf-8-sig')
def save(df,p):df.to_csv(R/p,index=False,encoding='utf-8-sig',float_format='%.12g',na_rep='NA')
def tables():
    start=now();probe=read('03_taxi_probe/T28_probe_daily_v7.csv');bounds=read('05_bounds/T31_recovery_bounds_v7.csv');health=read('06_s_pre/T36_health_screened_v6.csv')
    cols=['date','hour_matched','n_taxi_seen','c_all','c_all_lo','c_all_hi','c_stable','c_stable_lo','c_stable_hi','q_probe','q_probe_ci_lo','q_probe_ci_hi','q_fleet','q_fleet_ci_lo','q_fleet_ci_hi','q_probe_minus_q_fleet','q_probe_minus_q_fleet_ci_lo','q_probe_minus_q_fleet_ci_hi','relative_interval_scope']
    network=probe[probe.date.isin(EVENT[:7])][cols].copy();network['source']='03_taxi_probe/T28_probe_daily_v7.csv'
    save(network,'07_consequences/T37_network_comparison_v7.csv')
    attrs=pd.read_csv(V1/'01_panels/device_attributes.csv',encoding='utf-8-sig');online=pd.read_csv(V1/'01_panels/online_sets.csv',encoding='utf-8-sig')
    A100=set(attrs.loc[attrs.in_A100.eq(1),'dev']);Sstar=set(attrs.loc[attrs.in_Sstar.eq(1),'dev'])
    counts={d:len(set(g.dev)&A100) for d,g in online.groupby('date')}
    family=[]
    for day in EVENT:
        b=bounds.set_index('date').loc[day];h=health.set_index('date').loc[day]
        names=['R_naive','R_health','R_spre_health','R_online','R_stable','R_health_strict','R_pre','R_lower','R_upper','R_mid','R_probe']
        for name in names:
            ishealth=name in ['R_health','R_health_strict','R_spre_health'];src=h if ishealth else b
            n=(int(h[{'R_health':'n_health','R_health_strict':'n_health_strict','R_spre_health':'n_spre_health'}[name]]) if ishealth else counts[day] if name=='R_online' else len(Sstar) if name=='R_stable' else int(h.n_Spre_total) if name=='R_pre' else len(A100))
            val=src[name];lo=src.get(name+'_ci_lo');hi=src.get(name+'_ci_hi')
            source='06_s_pre/T36_health_screened_v6.csv' if ishealth else '05_bounds/T31_recovery_bounds_v7.csv'
            scope=h.CI_scope if ishealth else b.get('R_probe_interval_scope','Independent device500 by vehicle200 product; fixed sets') if name=='R_probe' else b.interval_scope
            # R_pre CIs were copied from the original fixed-S_pre bootstrap.
            if name=='R_pre':scope='Copied v6 fixed S_pre, paired A100 device500 cluster percentile interval'
            if name in ['R_naive','R_online','R_stable']:scope='Copied frozen v6/v3 device-cluster interval; fixed observed network membership; selection uncertainty excluded'
            family.append(dict(date=day,hour_matched=int(b.hour_matched),estimator=name,R=val,ci_lo=lo,ci_hi=hi,n_devices=n,n_probe=290 if name=='R_probe' and pd.notna(val) else None,available=pd.notna(val),interval_scope=scope,source=source,source_value_column=name))
    family=pd.DataFrame(family);save(family,'07_consequences/T37_estimator_family_v7.csv');save(family,'08_figures/fig_estimator_family_v7_data.csv')
    checks=dict(network_7days=network.date.tolist()==EVENT[:7],family_9days=family.date.nunique()==9,family_11estimators=family.estimator.nunique()==11,no_August_probe=family[family.estimator.eq('R_probe')&family.date.ge('2021-08-01')].R.isna().all(),all_original_mid_NA=family[family.estimator.eq('R_mid')].R.isna().all())
    assert all(checks.values()),'T37 completeness failed'
    put('00_env/t37_execution_v7.json',dict(status='complete',start=start,end=now(),checks=checks,rows=dict(network=len(network),family=len(family)),scope='Assembly only; no original effects or H1-H4 refit',source_reads=False,key_reads=False))
    print(json.dumps(dict(T37_complete=True,network_rows=len(network),family_rows=len(family))))
