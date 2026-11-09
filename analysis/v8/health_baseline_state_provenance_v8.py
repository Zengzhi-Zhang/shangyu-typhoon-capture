# -*- coding: utf-8 -*-
"""Resolve the reviewer's state-median denominator using frozen old labels."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[2]), str(_ReleasePath(__file__).resolve().parents[0])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from pathlib import Path
import pandas as pd,numpy as np,json
R=Path(_release_path('v8_root'));V=R.parent/'formal_v7';P=R.parent/'01_panels'
q=pd.read_csv(V/'01_internal/device_state_internal_v7.csv',encoding='utf-8-sig');q=q[q.date.eq('2021-07-26')&q.in_A200.eq(1)].copy()
d=pd.read_csv(P/'device_day.csv',encoding='utf-8-sig')
mat=d.pivot_table(index='dev',columns='date',values='n',aggfunc='sum',fill_value=0)
b=mat[['2021-07-05','2021-07-12','2021-07-19']].mean(axis=1);q['ratio_panel_B1']=q.dev.map(mat['2021-07-26']/b)
cap=pd.read_csv(V/'01_internal/capture_camera_internal_v7.csv',encoding='utf-8-sig')
selected=set(cap.loc[cap.variant.eq('main_R60_cap03')&cap.date.eq('2021-07-26')&cap.selected.eq(True)&cap.expected.ge(10),'dev'])
rows=[]
for scope,use in [('all_A200',q),('main329_selected_event_expected_ge10',q[q.dev_public.isin(selected)])]:
    for version,column in [('frozen_v6','state_v6'),('frozen_v7','state')]:
        for state,g in use.groupby(column,sort=True):
            rows.append(dict(date='2021-07-26',scope=scope,state_version=version,state=state,n_devices=len(g),ratio_B1_median=g.ratio_panel_B1.median(),ratio_A1_median=g.ratio_A1.median(),interpretation='Original labels only; no reclassification; B1/A1 denominators stated separately'))
out=pd.DataFrame(rows);out.to_csv(R/'03_baseline/W3_state_ratio_medians_version_provenance_0726_v8.csv',index=False,encoding='utf-8-sig',float_format='%.12g',na_rep='NA')
key=out[out.state.isin(['partial_channel','normal'])]
report=dict(scope='Review-source denominator and label-version diagnostic; primary W3 remains frozenv7 classification',state_medians=key.to_dict('records'),old_versions_modified=False,source_reads=False,key_reads=False)
(R/'00_env/health_baseline_state_provenance_v8.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(key.to_dict('records')))
