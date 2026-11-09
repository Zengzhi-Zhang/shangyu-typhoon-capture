# -*- coding: utf-8 -*-
"""Synthetic event-blindness and selection-boundary checks only."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[3]), str(_ReleasePath(__file__).resolve().parents[1]), str(_ReleasePath(__file__).resolve().parent)]
from types import SimpleNamespace
import numpy as np
import pandas as pd
from s_pre_v6 import select_pre,PRE
from spatial_helpers_v6 import D_ALL,EVENT,ROOT,write_json

p=SimpleNamespace(n_dev=5,day_index={d:i for i,d in enumerate(D_ALL)},
    daily=np.full((5,len(D_ALL)),100.),hour=np.ones((5,len(D_ALL),24)),
    A100=np.array([1,1,1,1,0],bool))
p.attr=pd.DataFrame(dict(dev_public=np.arange(1,6),in_A100=p.A100.astype(int),in_A200=[1,1,1,1,0],in_Sstar=[1,1,1,0,0]),
    index=pd.Index(['synthetic'+str(i) for i in range(5)],name='dev'))
p.daily[1,p.day_index[PRE[0]]]=0
p.hour[2,p.day_index[PRE[1]],:5]=0
for d in EVENT:
    p.daily[3,p.day_index[d]]=0;p.hour[3,p.day_index[d],:]=0
select,internal,audit=select_pre(p)
checks=dict(expected_selection=select.tolist()==[True,False,False,True,False],
    all23_pre_dates=len(audit)==23 and [r['date'] for r in audit]==PRE,
    LOO_excludes_each_target=all(r['date'] not in r['leaveout_dates'].split(';') for r in audit),
    hour19_rejected=int(internal.loc[internal.dev.eq('synthetic2'),'n_hours_failed_pre_days'].iloc[0])==1,
    zero_event_count_does_not_exclude=bool(select[3]))
for d in EVENT:p.daily[:,p.day_index[d]]=999999;p.hour[:,p.day_index[d],:]=0
after,_,_=select_pre(p)
checks['event_outcomes_do_not_change_membership']=bool(np.array_equal(select,after))
report=dict(stage='synthetic_only_before_observed_computation',all_passed=all(checks.values()),checks=checks,numerical_panel_analysis_run=False)
write_json(ROOT/'00_env/s_pre_synthetic_checks_v6.json',report)
print(__import__('json').dumps(report))
if not all(checks.values()):raise AssertionError('S_pre synthetic selection checks failed')
