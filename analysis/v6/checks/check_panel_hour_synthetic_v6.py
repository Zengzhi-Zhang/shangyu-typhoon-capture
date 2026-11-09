# -*- coding: utf-8 -*-
"""Synthetic verification of assigned versus unassigned hour preservation."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[3]), str(_ReleasePath(__file__).resolve().parents[1]), str(_ReleasePath(__file__).resolve().parent)]
import numpy as np
import pandas as pd
from spatial_helpers_v6 import Panels,D_ALL,ROOT,write_json,clean

devs=['synthetic'+str(i) for i in range(4)]
idx=pd.MultiIndex.from_product([devs,D_ALL,range(24)],names=['dev','date','hour'])
hours=idx.to_frame(index=False);hours['n']=1;hours['n_unread']=0
hours=pd.concat([hours,pd.DataFrame([dict(dev=devs[0],date='2021-07-26',hour=-1,n=7,n_unread=2)])],ignore_index=True)
daily=hours.groupby(['dev','date'],as_index=False).n.sum()
attrs=pd.DataFrame(dict(dev=devs,lon=[120.8,120.81,120.82,120.83],lat=[30.,30.,30.,30.],
    base_B1=[24.,24.,24.,24.],in_A100=[1]*4,in_A200=[1]*4,in_Sstar=[1]*4,dist_baiguan_km=[0.,1.,2.,3.]))

class SyntheticPanels(Panels):
    def read(self,path,**kwargs):
        return {'device_attributes.csv':attrs,'device_hour.csv':hours,'device_day.csv':daily}[path.name].copy()

p=SyntheticPanels();i=p.day_index['2021-07-26'];n,b=p.vectors('2021-07-26')
checks=dict(full_day_includes_unknown_hour=p.daily[0,i]==31,known_clock_hours_remain24=p.hour[0,i].sum()==24,
    unread_full_day_includes_unknown_hour=p.daily_unread[0,i]==2,unknown_diagnostic_retained=p.unassigned_hour[0,i]==7,
    unknown_unread_diagnostic_retained=p.unassigned_unread[0,i]==2,ratio_numerator_not_truncated=n[0]==31,
    independent_day_hour_totals_match=p.checks['hour_day_panel_exact'])
report=dict(stage='synthetic_only_before_observed_computation',all_passed=all(checks.values()),checks=checks,numerical_panel_analysis_run=False)
write_json(ROOT/'00_env/panel_hour_synthetic_checks_v6.json',report)
print(__import__('json').dumps(clean(report)))
if not all(checks.values()):raise AssertionError('Synthetic unknown-hour preservation failed')
