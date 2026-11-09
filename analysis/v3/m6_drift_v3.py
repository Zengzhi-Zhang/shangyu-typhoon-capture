# -*- coding: utf-8 -*-
"""T22: prespecified B3 drift diagnostics from immutable device panels."""
from common_v3 import *
def main():
    start=now();dh,a,dd=load_panels();keep=a.in_Sstar.eq(1);n=dd.loc[keep,B1].to_numpy(float)
    b=np.column_stack([dd.loc[keep,refs(d,'B3')].mean(axis=1).to_numpy(float) for d in B1])
    rng=np.random.default_rng(SEED);ix=rng.integers(0,keep.sum(),size=(500,keep.sum()))
    sampled=n[ix].sum(axis=1)/b[ix].sum(axis=1);point=n.sum(axis=0)/b.sum(axis=0)
    phiboot=sampled.mean(axis=1);phi=float(point.mean());plo,phi_hi=np.quantile(phiboot,[.025,.975])
    rows=[dict(date=d,R_stable_B3=float(point[j]),ci_lo=np.quantile(sampled[:,j],.025),ci_hi=np.quantile(sampled[:,j],.975),n_devices=int(keep.sum()),n_reference_days=len(refs(d,'B3')),source='v3_recomputed_from_v1_panels') for j,d in enumerate(B1)]
    save_csv(pd.DataFrame(rows),ROOT/'07_m6_robustness/m6_b3_drift_v3.csv')
    write_json(ROOT/'07_m6_robustness/m6_b3_drift_v3.json',dict(phi=[phi,plo,phi_hi],definition='arithmetic mean of the 15 B1 daily R_stable ratios using B3 same-weekday denominators',bootstrap='500 paired device-cluster resamples across all B1 dates',n_dates=len(B1),expectation=[.8,.95],expectation_met=.8<=phi<=.95,by_date={r['date']:r for r in rows},correction_scope='Single Sstar traffic drift factor, supplementary only; does not imply category-specific drift or taxi B3 comparability.'))
    m2=pd.read_csv(V1/'03_m2_two_sources/m2_daily_ratios_B3.csv',encoding='utf-8-sig');out=[]
    for row in m2[m2.date.isin(dates('2021-07-26','2021-07-28'))].to_dict('records'):
        for metric in ['R_naive','R_online','R_stable','R_taxi_km']:
            value=row[metric]
            out.append(dict(date=row['date'],metric=metric,R_B3=value,phi=phi,R_B3_adj=value/phi if pd.notna(value) else np.nan,ci_lo_conditional_phi=row[metric+'_ci_lo']/phi if pd.notna(value) else np.nan,ci_hi_conditional_phi=row[metric+'_ci_hi']/phi if pd.notna(value) else np.nan,interval_scope='Original B3 interval divided by fixed estimated phi; phi uncertainty not included.',status='not_applicable_no_taxi_B3' if pd.isna(value) else 'supplementary'))
    save_csv(pd.DataFrame(out),ROOT/'07_m6_robustness/m6_b3_adjusted_ratios_v3.csv')
    m3=pd.read_csv(V1/'04_m3_vehicles/m3_daily_by_group_B3.csv',encoding='utf-8-sig');out=[]
    for r in m3[m3.date.isin(['2021-07-26','2021-07-28'])].to_dict('records'):
        for metric in ['rP','rm','rN']:
            out.append(dict(date=r['date'],grp=r['grp'],metric=metric,ratio_B3=r[metric],phi=phi,ratio_B3_adj=r[metric]/phi,ci_lo_conditional_phi=r['ci_'+metric+'_lo']/phi,ci_hi_conditional_phi=r['ci_'+metric+'_hi']/phi,interval_scope='Conditional on estimated phi; applies common traffic drift to each margin only as the requested supplementary diagnostic.'))
    save_csv(pd.DataFrame(out),ROOT/'07_m6_robustness/m6_b3_adjusted_margins_v3.csv')
    stage_record('m6_drift',start,['07_m6_robustness/m6_b3_drift_v3.csv','07_m6_robustness/m6_b3_drift_v3.json','07_m6_robustness/m6_b3_adjusted_ratios_v3.csv','07_m6_robustness/m6_b3_adjusted_margins_v3.csv'],dict(phi=phi,raw_source_io=False))
    print('B3 phi',phi,'CI',plo,phi_hi,flush=True)
if __name__=='__main__':main()
