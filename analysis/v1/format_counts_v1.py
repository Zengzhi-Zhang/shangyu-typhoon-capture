# -*- coding: utf-8 -*-
"""Keep all scientific values and ratio/p-value text, normalise integer count representation only."""
import csv,decimal
from common_v1 import *
START=now();changed=[]
count_names={'records','plates','plates_all','plates_Sstar','devices_any','devices_ge1000','devices_reporting','taxi_points','taxi_moving_points','taxi_vehicles_reporting','taxi_vehicles_active','taxi_vehicles_moving'}
for dn in ['02_m1_observation','03_m2_two_sources','04_m3_vehicles','05_m4_spatial','06_m5_bias_correction','07_m6_robustness','08_figures']:
    for p in (ROOT/dn).glob('*.csv'):
        with p.open('r',encoding='utf-8-sig',newline='') as f:
            reader=csv.DictReader(f);fields=reader.fieldnames;rows=list(reader)
        dirty=False
        for row in rows:
            for col in fields:
                if col not in count_names and not col.startswith('n_'):continue
                v=row[col]
                if not v or v=='<10':continue
                try:
                    number=decimal.Decimal(v)
                    if number.is_finite() and number==number.to_integral_value():
                        nv=str(int(number));dirty |= nv!=v;row[col]=nv
                except decimal.InvalidOperation:pass
        if dirty:
            with p.open('w',encoding='utf-8-sig',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)
            changed.append(str(p.relative_to(ROOT)))
stage_record('format_counts',START,changed,dict(scientific_values_changed=False,ratio_p_text_preserved=True))
print('Integer formatting',len(changed),'files; values unchanged',flush=True)
