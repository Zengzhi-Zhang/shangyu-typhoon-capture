# -*- coding: utf-8 -*-
"""I6: pre-event-only device selection and new sensitivity estimates.

Frozen Sstar and H1-H4 results are read as comparators, never recomputed.
"""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[2]), str(_ReleasePath(__file__).resolve().parents[0])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
import argparse,time,json
import numpy as np
import pandas as pd
from spatial_helpers_v6 import (ROOT,V3,SEED,N_BOOT,B1,B3,EVENT,FIVE,Panels,now,sha,
    save_csv,write_json,require_protocol,refs,ratio,ci,ring,fit_ols)

INTERPRETATION=ROOT/'00_env/interpretation_spatial_v6.json'
PRE=sorted(set(B1+B3));DIST='np.log1p(dist_baiguan_km)'

def select_pre(p):
    failures_ratio=np.zeros(p.n_dev,int);failures_hours=np.zeros(p.n_dev,int)
    min_hours=np.full(p.n_dev,24,int);min_ratio=np.full(p.n_dev,np.inf)
    audit=[]
    for d in PRE:
        other=[v for v in refs(d,PRE) if v!=d]
        if not other:raise RuntimeError('S_pre same-weekday leave-one-out mean unavailable')
        n=p.daily[:,p.day_index[d]];b=p.daily[:,[p.day_index[v] for v in other]].mean(axis=1)
        hours=(p.hour[:,p.day_index[d],:]>0).sum(axis=1)
        # Task-book inequality is applied directly; a zero LOO mean is recorded,
        # not silently converted to an A1 previous-week denominator.
        badratio=n<.05*b;badhours=hours<20
        failures_ratio+=badratio;failures_hours+=badhours;min_hours=np.minimum(min_hours,hours)
        r=np.divide(n,b,out=np.full(p.n_dev,np.nan),where=b>0)
        min_ratio=np.minimum(min_ratio,np.where(np.isfinite(r),r,np.inf))
        audit.append(dict(date=d,leaveout_dates=';'.join(other),n_baseline_days=len(other),
            n_A100_ratio_fail=int((p.A100&badratio).sum()),n_A100_hour_fail=int((p.A100&badhours).sum()),
            n_A100_zero_LOO_denominator=int((p.A100&(b<=0)).sum())))
    spre=p.A100&(failures_ratio==0)&(failures_hours==0)
    internal=p.attr[['dev_public','in_A100','in_A200','in_Sstar']].reset_index().copy()
    internal['in_Spre']=spre.astype(int);internal['n_pre_days']=len(PRE)
    internal['n_ratio_failed_pre_days']=failures_ratio;internal['n_hours_failed_pre_days']=failures_hours
    internal['min_hours_recording_pre']=min_hours;internal['min_ratio_LOO_pre']=np.where(np.isfinite(min_ratio),min_ratio,np.nan)
    internal=internal.loc[p.A100].copy()
    return spre,internal,audit

def merge_five(counts):
    groups=[[r] for r in FIVE];changes=[]
    while len(groups)>1:
        sparse=[i for i,g in enumerate(groups) if sum(counts.get(r,0) for r in g)<10]
        if not sparse:break
        i=max(sparse);target=i-1 if i>0 else 1
        changes.append(dict(from_rings=groups[i].copy(),into_rings=groups[target].copy(),direction='inward' if i>0 else 'only_outward_neighbour'))
        groups[target]=sorted(groups[target]+groups[i],key=FIVE.index);groups.pop(i)
    mapping={};labels=[]
    for g in groups:
        if len(g)==1:label=g[0]
        elif g[-1]=='12+':label=g[0].split('-')[0]+'+'
        else:label=g[0].split('-')[0]+'-'+g[-1].split('-')[-1]
        labels.append(label)
        for r in g:mapping[r]=label
    return mapping,labels,changes

def ring_table(p,spre,mapping,labels,rng,n,b,variant):
    orig=ring(p.attr.dist_baiguan_km,five=True);mapped=orig.map(mapping)
    rows=[]
    for label in labels:
        select=spre&mapped.eq(label).to_numpy();ids=np.flatnonzero(select)
        if len(ids):
            # Copy v3 sims_ratio: fixed-size device resampling within each ring.
            ix=rng.integers(0,len(ids),size=(N_BOOT,len(ids)))
            num=n[ids][ix].sum(axis=1);den=b[ids][ix].sum(axis=1)
            draw=np.divide(num,den,out=np.full(N_BOOT,np.nan),where=den>0)
        else:draw=np.full(N_BOOT,np.nan)
        lo,hi=ci(draw)
        rows.append(dict(date='2021-07-26',sample='S_pre',distance_ring=label,n_devices=len(ids),
            r_camera=ratio(n[select],b[select]),r_camera_ci_lo=lo,r_camera_ci_hi=hi,
            observed_records=int(n[select].sum()),baseline_records=float(b[select].sum()),
            variant=variant,device_bootstrap=N_BOOT,hour_matched=0))
    return pd.DataFrame(rows)

def main(protocol):
    start=now();t=time.monotonic();gate=require_protocol(protocol);interpret_hash=sha(INTERPRETATION)
    p=Panels();spre,internal,selection_audit=select_pre(p)
    if not spre.any():raise RuntimeError('S_pre is empty; report limitation before any model fit')
    save_csv(internal,ROOT/'01_internal/s_pre_devices_v6.csv')
    save_csv(pd.DataFrame(selection_audit),ROOT/'06_s_pre/T32_s_pre_selection_audit_v6.csv')
    n_pre=int(spre.sum());overlap=int((spre&p.Sstar).sum());union=int((spre|p.Sstar).sum());jaccard=overlap/union if union else np.nan
    frozen=p.read(V3/'06_m5_bias_correction/m5_visible_bias_v3.csv').set_index('date')
    oldols=p.read(V3/'05_m4_spatial/m4_ols_v3.csv')
    rng=np.random.default_rng(SEED);a=int(p.A100.sum())
    weights=np.zeros((N_BOOT,p.n_dev),dtype=np.int64)
    weights[:,p.A100]=rng.multinomial(a,np.full(a,1/a),size=N_BOOT)
    rows=[];draw_records=[];checks=dict(p.checks);n26=b26=None
    for d in EVENT:
        n,b=p.vectors(d);rpre=ratio(n[spre],b[spre]);rawnaive=ratio(n[p.A100],b[p.A100])
        checks['R_naive_matches_frozen_'+d]=bool(np.isclose(round(rawnaive,4),float(frozen.loc[d,'R_naive']),atol=.0000001,rtol=0))
        checks['R_stable_matches_frozen_'+d]=bool(np.isclose(round(ratio(n[p.Sstar],b[p.Sstar]),4),float(frozen.loc[d,'R_stable']),atol=.0000001,rtol=0))
        num=weights[:,spre]@n[spre];den=weights[:,spre]@b[spre]
        pre_draw=np.divide(num,den,out=np.full(N_BOOT,np.nan),where=den>0)
        naive_den=weights[:,p.A100]@b[p.A100];naive_num=weights[:,p.A100]@n[p.A100]
        naive_draw=np.divide(naive_num,naive_den,out=np.full(N_BOOT,np.nan),where=naive_den>0)
        lo,hi=ci(pre_draw);dlo,dhi=ci(naive_draw-pre_draw)
        rows.append(dict(date=d,n_Spre=n_pre,n_Sstar=int(p.Sstar.sum()),n_overlap_Sstar=overlap,jaccard=jaccard,
            R_pre=rpre,R_pre_ci_lo=lo,R_pre_ci_hi=hi,R_naive=float(frozen.loc[d,'R_naive']),R_stable=float(frozen.loc[d,'R_stable']),
            delta_naive_pre=float(frozen.loc[d,'R_naive'])-rpre,delta_naive_pre_ci_lo=dlo,delta_naive_pre_ci_hi=dhi,
            delta_naive_pre_unrounded=rawnaive-rpre,abs_R_pre_minus_stable=abs(rpre-float(frozen.loc[d,'R_stable'])),
            observed_records=int(n[spre].sum()),baseline_records=float(b[spre].sum()),hour_matched=int(d=='2021-07-25'),
            device_bootstrap=N_BOOT,CI_method='paired A100 device-cluster; shared cross-date weights; fixed S_pre; percentile95',
            comparator_source='formal_v3 frozen published R_naive and R_stable; CI uses unrounded panel naive ratio'))
        # Restricted row-level bootstrap draws remain internal for downstream joins.
        draw_records.append(pd.DataFrame(dict(date=d,draw=np.arange(N_BOOT),R_pre_draw=pre_draw,R_naive_draw=naive_draw)))
        if d=='2021-07-26':n26,b26=n,b
    daily=pd.DataFrame(rows);save_csv(daily,ROOT/'06_s_pre/T32_s_pre_v6.csv')
    save_csv(pd.concat(draw_records,ignore_index=True),ROOT/'01_internal/s_pre_bootstrap_draws_v6.csv')
    original=ring(p.attr.dist_baiguan_km,five=True);counts=original[spre].value_counts().to_dict()
    mapping,labels,merges=merge_five(counts)
    ring_rng=np.random.default_rng(SEED)
    rings=ring_table(p,spre,mapping,labels,ring_rng,n26,b26,'merged_if_n_lt10')
    orig_rings=ring_table(p,spre,dict(zip(FIVE,FIVE)),FIVE,ring_rng,n26,b26,'original_five')
    save_csv(rings,ROOT/'06_s_pre/T32_s_pre_rings_v6.csv');save_csv(orig_rings,ROOT/'06_s_pre/T32_s_pre_rings_v6_orig.csv')
    models=[]
    for d in ['2021-07-26','2021-07-27','2021-07-28']:
        n,b=p.vectors(d,matched=False);r=np.divide(n,b,out=np.full(p.n_dev,np.nan),where=b>0)
        models.append(fit_ols(p.attr,r,spre,d))
    ols=pd.concat(models,ignore_index=True);save_csv(ols,ROOT/'06_s_pre/T32_s_pre_ols_v6.csv')
    dist=ols[ols.term.eq(DIST)].copy();dist['source']='new S_pre model; frozen v3 specification'
    star=oldols[oldols['sample'].eq('Sstar')&oldols.term.eq(DIST)].copy();star['source']='formal_v3 frozen Sstar coefficient read only'
    forest=pd.concat([dist,star],ignore_index=True)
    source=pd.concat([daily.assign(panel='a_daily'),forest.assign(panel='b_OLS'),rings.assign(panel='c_rings')],ignore_index=True,sort=False)
    source['selection_note']='event-preceding B1 union B3 only; per-day LOO and >=20 recording hours'
    save_csv(source,ROOT/'08_figures/fig_s_pre_comparison_v6_data.csv')
    rp=float(daily.set_index('date').loc['2021-07-26','R_pre']);rs=float(frozen.loc['2021-07-26','R_stable'])
    coef=float(dist.set_index('date').loc['2021-07-26','coef']);starcoef=float(star.set_index('date').loc['2021-07-26','coef'])
    acceptance=dict(ratio_agreement=dict(R_pre=rp,R_stable=rs,absolute_difference=abs(rp-rs),threshold=.05,met=abs(rp-rs)<=.05),
        distance_coefficient_sign=dict(S_pre=coef,Sstar_frozen=starcoef,met=bool(np.sign(coef)==np.sign(starcoef))))
    checks.update(dict(selection_only_pre_event=max(PRE)<'2021-07-25',selection_pool_23_dates=len(PRE)==23,
        S_pre_subset_A100=not np.any(spre&~p.A100),all_selected_pass_both_rules=bool(internal.loc[internal.in_Spre.eq(1),['n_ratio_failed_pre_days','n_hours_failed_pre_days']].eq(0).all().all()),
        internal_in_Spre_sum_equals_n=int(internal.in_Spre.sum())==n_pre,daily_all_9_event_dates=daily.date.tolist()==EVENT,
        OLS_all_3_dates=dist.date.tolist()==['2021-07-26','2021-07-27','2021-07-28'],
        OLS_response_and_covariance_frozen=True,inputs_unchanged=p.unchanged(),
        protocol_unchanged=gate['sha256']==sha(protocol),interpretation_unchanged=interpret_hash==sha(INTERPRETATION)))
    write_json(ROOT/'00_env/s_pre_acceptance_v6.json',acceptance)
    write_json(ROOT/'06_s_pre/T32_s_pre_membership_summary_v6.json',dict(n=n_pre,n_Sstar=int(p.Sstar.sum()),overlap=overlap,union=union,jaccard=jaccard,
        n_pre_days=len(PRE),pre_dates=PRE,ring_counts_orig=counts,ring_merge_mapping=mapping,ring_merges=merges,
        interpretation='The agreement tests assess sensitivity to event-based selection; neither comparator is an independent true-traffic measurement.'))
    record=dict(started=start,ended=now(),seconds=time.monotonic()-t,seed=SEED,status='complete' if all(checks.values()) else 'failed',
        command=_release_path('path_023')+str(protocol),
        protocol=gate,interpretation_sha256=interpret_hash,input_sha256=p.input_hashes,checks=checks,acceptance=acceptance,
        selection=dict(n=n_pre,overlap=overlap,jaccard=jaccard),rows=dict(internal_devices=len(internal),daily=len(daily),ols=len(ols),rings=len(rings),figure_source=len(source)),
        raw_source_accessed=False,key_accessed=False,H1_H4_recomputed=False,
        notes=['Only S_pre is estimated; frozen Sstar comparator coefficients are read without refitting.',
               'Published naive comparator point value is retained; paired interval uses unrounded panel naive ratio and retains unrounded delta separately.',
               'Membership is fixed for all500 device-cluster replicates; intervals do not include selection uncertainty.'])
    write_json(ROOT/'00_env/s_pre_execution_v6.json',record)
    print(json.dumps(dict(status=record['status'],selection=record['selection'],rows=record['rows'],acceptance=acceptance),ensure_ascii=False))
    if not all(checks.values()):raise AssertionError('S_pre integrity check failed')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--protocol',default=str(ROOT/'00_env/protocol_frozen_v6.json'))
    main(parser.parse_args().protocol)
