# -*- coding: utf-8 -*-
"""Synthetic boundary checks only; never opens observed panel rows."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[3]), str(_ReleasePath(__file__).resolve().parents[1]), str(_ReleasePath(__file__).resolve().parent)]
import numpy as np
import pandas as pd
from device_state_v6 import classify_states,longest_run,stop_hour,channel_signals
from s_pre_v6 import merge_five
from spatial_helpers_v6 import ROOT,write_json,FIVE,B1

checks={}
n=np.array([0,3,100,100,100,100,100,100,100],float)
hours=np.array([0,4,24,24,12,24,24,12,24])
mixed=np.array([1,1,1,0,0,0,0,0,0],bool)
r=np.array([0,.1,.7,.2,.049,.05,.5,.049,1.])
spike=np.array([1,1,0,1,0,0,0,np.nan,0])
a200=np.array([1,1,1,1,1,1,1,1,0],bool)
actual=classify_states(n,hours,mixed,r,spike,a200,'2021-07-26')
checks['ordered_first_match']=actual.tolist()==['zero','offline','partial_channel','recognition_degraded','low_all_channels','degraded_other','normal','normal','not_classified_outside_A200']
actual25=classify_states(np.ones(2),np.array([2,3]),np.zeros(2,bool),np.array([.1,.1]),np.zeros(2),np.ones(2,bool),'2021-07-25')
checks['July25_raw_2hour_threshold']=actual25.tolist()==['offline','degraded_other']
checks['longest_run_keeps_actual_hour_gaps']=longest_run([1,1,0,1])==2
checks['stop_hour_prefix_suffix']=stop_hour(np.arange(24),np.r_[np.ones(6),np.zeros(18)],np.r_[np.ones(6,dtype=bool),np.zeros(18,dtype=bool)])==6
checks['July25_prefix_starts_at11']=stop_hour(np.arange(11,24),np.r_[1,np.zeros(12)],np.r_[True,np.zeros(12,dtype=bool)])==12
idx=pd.MultiIndex.from_tuples([('synthetic','east','1'),('synthetic','west','1')],names=['dev','dir','lane'])
channels=pd.DataFrame(100,index=idx,columns=B1+['2021-07-26']);channels.loc[('synthetic','east','1'),'2021-07-26']=0
signals=channel_signals(channels,'2021-07-26',['synthetic'])
checks['direction_lane_pair_not_collapsed']=int(signals.n_lanes.iloc[0])==2 and bool(signals.mixed.iloc[0])
mapping,labels,_=merge_five(dict(zip(FIVE,[30,30,30,6,2])))
checks['outer_sparse_ring_merges_inward']=labels==['0-2','2-4','4+'] and mapping['12+']=='4+'
report=dict(stage='synthetic_only_before_observed_computation',all_passed=all(checks.values()),checks=checks,numerical_panel_analysis_run=False)
write_json(ROOT/'00_env/state_synthetic_checks_v6.json',report)
print(__import__('json').dumps(report))
if not all(checks.values()):raise AssertionError('Synthetic state boundary checks failed')
