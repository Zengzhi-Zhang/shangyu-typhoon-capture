# -*- coding: utf-8 -*-
"""Pure in-memory arithmetic/edge-case checks; never opens scientific inputs."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[3]), str(_ReleasePath(__file__).resolve().parents[1]), str(_ReleasePath(__file__).resolve().parent)]
from types import SimpleNamespace
import numpy as np
from bias_common_v6 import ROOT,SEED,Panels,write_json,now
from leaveout_structured_v6 import weighted_mask,evaluate,graph_masks,spatial_mask
from bounds_v6 import neighbor_median
from consequences_v6 import recovery

def main():
    checks={};rng=np.random.default_rng(SEED)
    picked,fb=weighted_mask(np.arange(5),[1,0,0,0,0],3,rng)
    checks['weighted_sparse_fallback_preserves_count']=bool(fb and len(set(picked))==3 and 0 in picked)
    d=['2021-07-26','2021-07-27','2021-07-28','2021-07-29']
    checks['recovery_uses_final_tail_not_first_crossing']=recovery([.7,.91,.88,.95],d,.9)['recovery_date']==d[3]
    checks['recovery_missing_tail_not_zero_or_recovered']=recovery([.95,.96,.97,np.nan],d,.9)['status']=='unavailable_tail_missing'
    checks['recovery_observed_below_tail_right_censored']=recovery([.95,.96,.97,.89],d,.9)['status']=='right_censored_no_sustained_recovery'
    p=SimpleNamespace(xy=np.array([[0,0],[1,0],[2,0],[3,0.]],float),coord=np.ones(4,bool),strata=np.array(['a']*4))
    p.predict=lambda r,donor,target:Panels.predict(p,r,donor,target)
    n=np.array([.5,3,1,4.]);b=np.array([1,3,2,4.]);r=n/b;p.vectors=lambda date:(n,b,r)
    target=np.array([False,False,True,False]);uni=np.ones(4,bool)
    rows=evaluate(p,'2021-07-26',uni,target,'synthetic',0,'test',{})
    estimates={row['method']:row['estimate'] for row in rows}
    checks['hand_calculated_city_estimators']=all(np.isclose(estimates[m],v) for m,v in dict(naive_zero=.75,drop=.9375,knn6=.95,stratum=.95).items())
    checks['drop_no_device_prediction_separate_proxy']=np.isnan(rows[1]['device_level_mae']) and np.isfinite(rows[1]['device_proxy_mae'])
    n0=np.array([5.,3.,1.,4.]);b0=np.array([0.,3.,2.,4.]);p.vectors=lambda date:(n0,b0,np.array([np.nan,1.,.5,1.]))
    zero_rows=evaluate(p,'2021-07-26',uni,target,'synthetic_zero_base',0,'test',{})
    z={row['method']:row for row in zero_rows}
    checks['zero_base_prediction_zero_preserves_observed_donor_numerator']=bool(
        np.isclose(z['naive_zero']['truth'],13/9) and np.isclose(z['naive_zero']['estimate'],12/9)
        and np.isclose(z['drop']['estimate'],12/7) and np.isclose(z['knn6']['estimate'],14/9)
        and z['knn6']['n_zero_base']==1 and z['knn6']['n_donor_zero_base']==1)
    p2=SimpleNamespace(xy=np.array([[0,0],[1,0],[2,0.]],float),coord=np.ones(3,bool))
    med,fb,nn=neighbor_median(p2,np.array([10.,1.,1.]),np.ones(3,bool),np.array([True,False,False]))
    checks['bounds_neighbor_self_excluded']=bool(med[0]==1 and nn[0]==2)
    p3=SimpleNamespace(xy=np.column_stack([np.arange(20),np.zeros(20)]),coord=np.ones(20,bool))
    valid,adj=graph_masks(p3,np.arange(20));mask,seed,bridges=spatial_mask(p3,valid,adj,4,rng)
    checks['spatial_mask_unique_target_size']=len(mask)==len(set(mask))==4 and seed in mask and bridges==0
    write_json(ROOT/'00_env/bias_synthetic_checks_v6.json',dict(status='passed' if all(checks.values()) else 'failed',created_at=now(),seed=SEED,scientific_inputs_read=False,synthetic_scientific_data_exported=False,checks=checks))
    print('Pure in-memory checks',checks)
    if not all(checks.values()):raise AssertionError('Synthetic edge check failed')
if __name__=='__main__':main()
