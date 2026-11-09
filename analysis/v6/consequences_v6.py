# -*- coding: utf-8 -*-
"""I7 final sustained-threshold dates, explicit right censoring."""
import argparse
import numpy as np
import pandas as pd
from bias_common_v6 import ROOT,V3,EVENT,FIVE,Stage,Panels,ratio

THETAS=[.80,.85,.90,.95]
def recovery(values,dates,theta):
    values=np.asarray(values,float);lastbad=-1
    for i,v in enumerate(values):
        if not np.isfinite(v) or v<theta:lastbad=i
    if lastbad+1<len(values):
        return dict(recovery_date=dates[lastbad+1],status='observed_sustained_recovery',horizon=dates[-1],last_below_or_missing_date=dates[lastbad] if lastbad>=0 else '',n_missing=int((~np.isfinite(values)).sum()))
    return dict(recovery_date='',status='right_censored_no_sustained_recovery' if np.isfinite(values[-1]) else 'unavailable_tail_missing',horizon=dates[-1],last_below_or_missing_date=dates[-1],n_missing=int((~np.isfinite(values)).sum()))
def merge_map(p):
    groups=[[r] for r in FIVE];events=[]
    populations=[p.Sstar]+[p.online[d] for d in EVENT]
    while len(groups)>1:
        sparse=[i for i,g in enumerate(groups) if min(int((sel&np.isin(p.ring5,g)).sum()) for sel in populations)<10]
        if not sparse:break
        i=max(sparse);target=i-1 if i>0 else 1;events.append(dict(original=groups[i].copy(),into=groups[target].copy(),reason='Minimum device population across9dates and both estimators below10'))
        groups[target]=groups[i]+groups[target] if i<target else groups[target]+groups[i];groups.pop(i)
    mapping={};labels=[]
    for g in groups:
        g=sorted(g,key=FIVE.index);label=g[0] if len(g)==1 else g[0].split('-')[0]+'+' if g[-1]=='12+' else g[0].split('-')[0]+'-'+g[-1].split('-')[-1]
        labels.append(label)
        for r in g:mapping[r]=label
    return mapping,labels,events
def run(protocol):
    st=Stage('consequences',protocol);p=Panels(st);bounds=st.read(ROOT/'01_internal/T31_recovery_bounds_internal_v6.csv').set_index('date');pre=st.read(ROOT/'06_s_pre/T32_s_pre_v6.csv').set_index('date');old=st.read(V3/'06_m5_bias_correction/m5_visible_bias_v3.csv').set_index('date')
    estimators={e:old[e].reindex(EVENT).to_numpy(float) for e in ['R_naive','R_online','R_stable','R_taxi_km']}
    estimators['R_pre']=pre.R_pre.reindex(EVENT).to_numpy(float)
    for e in ['R_lower','R_upper']:estimators[e]=bounds[e].reindex(EVENT).to_numpy(float)
    rows=[]
    for theta in THETAS:
        for e,values in estimators.items():
            horizon=EVENT[:7] if e=='R_taxi_km' else EVENT
            rows.append(dict(theta=theta,estimator=e,scope='city',**recovery(values[:len(horizon)],horizon,theta),threshold_interpretation='Illustrative threshold, not a local rule'))
    mapping,labels,merges=merge_map(p);curves=[];original=[]
    for date in EVENT:
        n,b,r=p.vectors(date)
        for estimator,select in [('R_online',p.online[date]),('R_stable',p.Sstar)]:
            st.checks['whole_city_'+estimator+'_matches_frozen_4dp:'+date]=abs(ratio(n[select],b[select])-float(old.loc[date,estimator]))<=.000051
            missing=select&(p.ring5=='missing');missing_share=ratio(b[missing],b[select])
            for variant,labs,mp,collector in [('A6',labels,mapping,curves),('orig',FIVE,dict(zip(FIVE,FIVE)),original)]:
                for ring in labs:
                    group=select&np.isin(p.ring5,[rr for rr,new in mp.items() if new==ring]);collector.append(dict(date=date,estimator=estimator,ring=ring,n_devices=int(group.sum()),R=ratio(n[group],b[group]),observed_records=int(n[group].sum()),baseline_records=float(b[group].sum()),hour_matched=int(date=='2021-07-25'),ring_variant=variant,n_estimator_missing_distance=int(missing.sum()),baseline_share_missing_distance=missing_share))
    curve=pd.DataFrame(curves);original=pd.DataFrame(original);city=pd.DataFrame(rows);ringrows=[]
    for theta in THETAS:
        for (e,ring),g in curve.groupby(['estimator','ring']):
            g=g.set_index('date').reindex(EVENT);rr=recovery(g.R.to_numpy(float),EVENT,theta);ringrows.append(dict(theta=theta,estimator=e,scope='distance_ring',ring=ring,**rr,threshold_interpretation='Illustrative threshold, not a local rule'))
    ringdates=pd.DataFrame(ringrows);lags=[]
    for _,r in ringdates[ringdates.theta.eq(.90)].iterrows():
        c=city[city.theta.eq(.90)&city.estimator.eq(r.estimator)].iloc[0];lag=np.nan;lower=np.nan;flag=False
        if c.recovery_date:
            if r.recovery_date:lag=(pd.Timestamp(r.recovery_date)-pd.Timestamp(c.recovery_date)).days;flag=lag>=1;comparison='finite_dates'
            elif r.status=='right_censored_no_sustained_recovery':lower=(pd.Timestamp(r.horizon)+pd.Timedelta(days=1)-pd.Timestamp(c.recovery_date)).days;flag=lower>=1;comparison='ring_right_censored_lag_lower_bound'
            else:comparison='ring_tail_missing_unavailable'
        else:comparison='city_no_observed_recovery_comparison_unavailable'
        lags.append(dict(theta=.90,estimator=r.estimator,ring=r.ring,city_recovery_date=c.recovery_date,city_status=c.status,ring_recovery_date=r.recovery_date,ring_status=r.status,lag_days=lag,lag_days_lower_bound=lower,lagging=flag if comparison in ['finite_dates','ring_right_censored_lag_lower_bound'] else np.nan,comparison_status=comparison,horizon=r.horizon,threshold_interpretation='Illustrative threshold, not a local rule'))
    st.save(city,ROOT/'07_consequences/T33_recovery_date_by_estimator_v6.csv');st.save(pd.DataFrame(lags),ROOT/'07_consequences/T33_lagging_rings_v6.csv');st.save(ringdates,ROOT/'07_consequences/T33_recovery_date_by_ring_v6.csv');st.save(curve,ROOT/'07_consequences/T33_ring_daily_ratios_v6.csv');st.save(original,ROOT/'07_consequences/T33_ring_daily_ratios_v6_orig.csv')
    st.checks['28city_threshold_estimator_rows']=len(city)==28
    st.checks['no_taxi_dates_after_July31']=city.loc[city.estimator.eq('R_taxi_km'),'horizon'].eq('2021-07-31').all()
    st.checks['ring_city_comparisons_2estimators']=set(pd.DataFrame(lags).estimator)=={'R_online','R_stable'}
    st.finish(dict(ring_mapping=mapping,ring_merge_log=merges,ring_missing_distance_coverage=curve[['date','estimator','n_estimator_missing_distance','baseline_share_missing_distance']].drop_duplicates().to_dict('records'),theta_example=.90,threshold_is_local_rule=False,city_recovery_dates=city.to_dict('records'),
        precision='New T31 scenario thresholds use 12-significant-digit internal values; existing frozen v3 estimators retain their published precision without recomputation; S_pre retains v6 source precision'))
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--protocol',required=True);args=ap.parse_args();run(args.protocol)
