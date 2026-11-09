# -*- coding: utf-8 -*-
"""I4 structured/MNAR masks. New quantities only, no H1-H4 re-evaluation."""
import argparse
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from bias_common_v6 import ROOT,V3,SEED,N_REP,Stage,Panels,days,ratio,write_json

METHODS=['naive_zero','drop','knn6','stratum']
def weighted_mask(ids,weights,k,rng):
    weights=np.asarray(weights,float);weights=np.where(np.isfinite(weights)&(weights>0),weights,0)
    positive=weights>0;fallback=False
    if positive.sum()>=k:return rng.choice(ids,k,replace=False,p=weights/weights.sum()),fallback
    chosen=list(ids[positive]);rest=ids[~positive];chosen.extend(rng.choice(rest,k-len(chosen),replace=False));return np.asarray(chosen,int),True
def graph_masks(p,ids):
    valid=ids[p.coord[ids]];adj={int(i):set() for i in valid}
    k=min(6,len(valid)-1)
    if k>0:
        near=np.asarray(cKDTree(p.xy[valid]).query(p.xy[valid],k=min(len(valid),k+2))[1]).reshape(len(valid),-1)
        for j,candidates in enumerate(near):
            for jj in [int(v) for v in candidates if int(v)!=j][:k]:adj[int(valid[j])].add(int(valid[jj]));adj[int(valid[jj])].add(int(valid[j]))
    return valid,adj
def spatial_mask(p,valid,adj,k,rng):
    if len(valid)<k:raise ValueError('Too few geolocated Sstar for spatial mask target')
    seed=int(rng.choice(valid));visited=[];frontier=[seed];queued={seed};bridges=0
    while len(visited)<k:
        if not frontier:
            remain=[v for v in valid if int(v) not in queued]
            nxt=min(remain,key=lambda v:(np.linalg.norm(p.xy[v]-p.xy[seed]),int(v)));frontier=[int(nxt)];queued.add(int(nxt));bridges+=1
        current=sorted(frontier,key=lambda v:(np.linalg.norm(p.xy[v]-p.xy[seed]),v));frontier=[]
        for node in current:
            if len(visited)>=k:break
            visited.append(node)
            for nxt in adj[node]:
                if nxt not in queued:queued.add(nxt);frontier.append(nxt)
    return np.asarray(visited,int),seed,bridges
def evaluate(p,date,universe,target,scheme,rep,kind,meta):
    n,b,_=p.vectors(date)
    # Frozen v1 prediction convention for an undefined device ratio; the city
    # numerator still contains every observed record. Separately counted below.
    r=np.divide(n,b,out=np.zeros(len(n)),where=b>0)
    donor=universe&~target;truth=ratio(n[universe],b[universe]);drop=ratio(n[donor],b[donor]);knn,stratum,fallback=p.predict(r,donor,target)
    estimates={'naive_zero':ratio(n[donor],b[universe]),'drop':drop,'knn6':(n[donor].sum()+(b[target]*knn[target]).sum())/b[universe].sum(),'stratum':(n[donor].sum()+(b[target]*stratum[target]).sum())/b[universe].sum()}
    preds={'naive_zero':np.zeros(len(n)),'drop':np.full(len(n),drop),'knn6':knn,'stratum':stratum};rows=[]
    for method,est in estimates.items():
        err=est-truth;dm=float(np.mean(np.abs(preds[method][target]-r[target])))
        rows.append(dict(scheme=scheme,date=date,rep=rep,rep_kind=kind,method=method,truth=truth,estimate=est,error=err,abs_error=abs(err),
            device_level_mae=np.nan if method=='drop' else dm,device_proxy_mae=dm if method=='drop' else np.nan,
            n_universe=int(universe.sum()),n_masked=int(target.sum()),n_zero_base=int((universe&(b<=0)).sum()),n_masked_zero_base=int((target&(b<=0)).sum()),n_donor_zero_base=int((donor&(b<=0)).sum()),masked_base_share=float(b[target].sum()/b[universe].sum()),**fallback,**meta))
    return rows
def run(protocol):
    st=Stage('leaveout_structured',protocol);p=Panels(st);state=st.read(ROOT/'01_internal/device_state_internal_v6.csv')
    state=state[state.date.eq('2021-07-26')&state.in_A200.astype(int).eq(1)]
    column='dev_public' if 'dev_public' in state else 'dev'
    fixed_public=state.loc[state.A1_failed.astype(int).eq(1),column].astype(int).to_numpy();fixed=np.flatnonzero(np.isin(p.public,fixed_public)&p.A100)
    independent_a1,_=p.a1('2021-07-26')
    st.checks['fixed_F_exact_matches_independent_A1']=np.array_equal(fixed,np.flatnonzero(p.A100&p.A200&(independent_a1<.05)))
    old=st.read(V3/'06_m5_bias_correction/m5_failure_counts_v3.csv').set_index('date');st.checks['fixed_F_count_matches_frozen_v3']=len(fixed)==int(old.loc['2021-07-26','n_failed_A1'])
    a=np.flatnonzero(p.A100);s=np.flatnonzero(p.Sstar);nmask=int(round(.2*len(s)));orgs=np.unique(p.org[s]);valid,adj=graph_masks(p,s)
    raw=[];maskframes=[];metadata=[]
    def add(scheme,date,rep,kind,masked,universe,meta):
        target=np.zeros(len(p.attr),bool);target[masked]=True
        if not np.all(universe[target]):raise AssertionError('Mask outside known-truth universe')
        raw.extend(evaluate(p,date,universe,target,scheme,rep,kind,meta))
        maskframes.append(pd.DataFrame(dict(scheme=scheme,date=date,rep=rep,rep_kind=kind,dev_public=p.public[masked])))
    rng=np.random.default_rng(np.random.SeedSequence([SEED,1]));replace_count=int(round(.1*len(fixed)));outside=np.setdiff1d(a,fixed)
    fixedmasks=[fixed]
    for rep in range(1,N_REP):
        remove=rng.choice(fixed,replace_count,replace=False);additions=rng.choice(outside,replace_count,replace=False);fixedmasks.append(np.sort(np.r_[np.setdiff1d(fixed,remove),additions]))
    for date in days('2021-07-12','2021-07-19'):
        for rep,masked in enumerate(fixedmasks):add('real_failure',date,rep,'fixed' if rep==0 else 'perturbed',masked,p.A100,dict(n_perturbed_replacements=0 if rep==0 else replace_count,universe='A100',probability_fallback=False,spatial_seed_dev_public=np.nan,spatial_component_bridges=0))
    for code,scheme in [(2,'organisation_block'),(3,'spatial_block'),(4,'mnar_low_recovery'),(5,'mnar_high_recovery')]:
        rng=np.random.default_rng(np.random.SeedSequence([SEED,code]))
        for date in days('2021-07-26','2021-07-30'):
            n,b,_=p.vectors(date);r=np.divide(n,b,out=np.zeros(len(n)),where=b>0)
            for rep in range(N_REP):
                meta=dict(n_perturbed_replacements=0,universe='Sstar',probability_fallback=False,spatial_seed_dev_public=np.nan,spatial_component_bridges=0)
                if scheme=='organisation_block':
                    org=str(rng.choice(orgs));masked=s[p.org[s]==org];cap=int(round(.3*len(s)))
                    if len(masked)>cap:masked=rng.choice(masked,cap,replace=False)
                    meta['organisation']=org
                elif scheme=='spatial_block':
                    masked,seed,bridges=spatial_mask(p,valid,adj,nmask,rng);meta.update(spatial_seed_dev_public=int(p.public[seed]),spatial_component_bridges=bridges)
                else:
                    weights=(1-r[s])**2 if scheme=='mnar_low_recovery' else r[s]**2;masked,fb=weighted_mask(s,weights,nmask,rng);meta['probability_fallback']=fb
                add(scheme,date,rep,'random',masked,p.Sstar,meta)
            print('I4 completed',scheme,date,flush=True)
    raw=pd.DataFrame(raw);masks=pd.concat(maskframes,ignore_index=True)
    st.save(raw,ROOT/'01_internal/T30_leaveout_replicates_internal_v6.parquet',internal=True);st.save(masks,ROOT/'01_internal/T30_masks_internal_v6.parquet',internal=True)
    st.save(raw[raw.rep_kind.eq('fixed')],ROOT/'01_internal/T30_real_failure_fixed_internal_v6.csv',internal=True)
    pieces=[]
    for variant,selected in [('all_200',raw),('fixed_point',raw[(raw.scheme=='real_failure')&raw.rep_kind.eq('fixed')]),('perturbed_199',raw[(raw.scheme=='real_failure')&raw.rep_kind.eq('perturbed')])]:
        if variant=='all_200':selected=selected.copy()
        summary=selected.groupby(['scheme','date','method'],sort=False).agg(bias=('error','mean'),sd=('error','std'),MAE=('abs_error','mean'),device_level_mae=('device_level_mae','mean'),device_proxy_mae=('device_proxy_mae','mean'),n_masked_mean=('n_masked','mean'),n_zero_base=('n_zero_base','max'),n_masked_zero_base_mean=('n_masked_zero_base','mean'),n_donor_zero_base_mean=('n_donor_zero_base','mean'),n_reps=('rep','count'),masked_base_share_mean=('masked_base_share','mean'),n_knn_global_fallback_mean=('n_knn_global_fallback','mean'),n_stratum_knn_fallback_mean=('n_stratum_knn_fallback','mean'),probability_fallback_reps=('probability_fallback','sum'),spatial_component_bridges_mean=('spatial_component_bridges','mean')).reset_index();summary['variant']=variant;pieces.append(summary)
    summary=pd.concat(pieces,ignore_index=True);summary['abs_bias_lt002']=summary.bias.abs()<.02;summary['error_unit']='recovery_ratio';summary['scope']='Known observed universe, not independent citywide traffic truth'
    st.save(summary,ROOT/'04_leaveout/T30_leaveout_structured_v6.csv');st.save(summary[summary.variant.eq('fixed_point')],ROOT/'04_leaveout/T30_real_failure_fixed_v6.csv')
    app=summary.groupby(['scheme','variant','method'],sort=False).agg(n_dates=('date','count'),dates_within_002=('abs_bias_lt002','sum'),fraction_dates_within_002=('abs_bias_lt002','mean'),max_abs_bias=('bias',lambda v:np.abs(v).max()),mean_abs_bias=('bias',lambda v:np.abs(v).mean()),mean_MAE=('MAE','mean')).reset_index();app['threshold']=.02;app['claim']='Applicability under this mask and observed universe only'
    st.save(app,ROOT/'04_leaveout/T30_applicability_matrix_v6.csv');st.save(app,ROOT/'08_figures/fig_applicability_matrix_v6_data.csv')
    st.checks['raw_22400_estimates']=len(raw)==22400
    st.checks['all_200_per_scheme_date_method']=bool(raw.groupby(['scheme','date','method']).size().eq(200).all())
    st.checks['fixed8days4methods_once']=int(raw.rep_kind.eq('fixed').sum())==32
    st.checks['real_masks_equal_size']=all(len(m)==len(fixed) for m in fixedmasks)
    st.checks['perturbation_equal_swaps']=all(len(np.setdiff1d(fixed,m))==replace_count for m in fixedmasks[1:])
    st.checks['drop_has_no_device_prediction']=raw.loc[raw.method.eq('drop'),'device_level_mae'].isna().all()
    st.checks['fixed_sd_NA']=summary.loc[summary.variant.eq('fixed_point'),'sd'].isna().all()
    st.finish(dict(n_A100=len(a),n_Sstar=len(s),n_real_mask=len(fixed),n_10percent_swaps=replace_count,n_spatial_mask_target=nmask,n_Sstar_missing_coords=int((p.Sstar&~p.coord).sum()),rng='SeedSequence([20261005, scheme_code1..5]); each date advances stream; real masks shared across8dates',fixed_point_separate=True))
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--protocol',required=True);args=ap.parse_args();run(args.protocol)
