# -*- coding: utf-8 -*-
"""Assemble robustness evidence from every completed prespecified variant."""
from common_v3 import *
def read(p):return pd.read_csv(p,encoding='utf-8-sig')
def main():
    start=now();rows=[]
    old=read(V1/'07_m6_robustness/m6_robustness_matrix.csv')
    for r in old.to_dict('records'):
        if r.get('conclusion','').find('构成')>=0 or r.get('variant','') in ['matched_placebo','placebo_B1']:continue
        effect=r.get('effect',np.nan);ref=r.get('reference_effect',np.nan)
        lo=next((r[k] for k in ['effect_lo','effect_lower'] if k in r and pd.notna(r[k])),np.nan)
        hi=next((r[k] for k in ['effect_hi','effect_upper'] if k in r and pd.notna(r[k])),np.nan)
        rows.append(dict(hypothesis=r['hypothesis'],conclusion=r.get('conclusion'),date=r.get('date'),grp=r.get('grp'),variant=r.get('variant'),metric=r.get('metric'),effect=effect,lo=lo,hi=hi,reference_effect=ref,sign_preserved=bool(np.sign(effect)==np.sign(ref)) if pd.notna(effect) and pd.notna(ref) else None,ci_excludes_0=bool(lo>0 or hi<0) if pd.notna(lo) and pd.notna(hi) else None,source='formal_v1 unchanged numerical variant',status_context='Original effect retained; v3 verdict uses frozen v3 rules.'))
    variants=ROOT/'07_m6_robustness/m6_h1_variants_v3.csv'
    if variants.exists():
        for r in read(variants).to_dict('records'):rows.append(dict(hypothesis='H1',source='v3 recalculated',**r))
    for file,hyp,metrics in [
        ('04_m3_vehicles/m3_h1_placebo_margins_v3.csv','H1',['typhoon_minus_placebo_delta_rP','typhoon_minus_placebo_delta_rm','placebo_delta_rP','placebo_delta_rm']),
        ('04_m3_vehicles/m3_h2_composition_placebo_v3.csv','H2',['gap']),
        ('05_m4_spatial/m4_ols_v3.csv','H3',['coef']),
        ('05_m4_spatial/m4_by_distance_ring_v3.csv','H3',['r_camera']),
        ('05_m4_spatial/m4_taxi_grid_threshold_sensitivity_v3.csv','H4',['rho']),
        ('03_m2_two_sources/m2_taxi_camera_correlations_v3.csv','H4',['spearman_rho','kendall_tau']),
        ('06_m5_bias_correction/m5_visible_bias_v3.csv','H4',['delta_naive','delta_online','delta_taxi']),
        ('07_m6_robustness/m6_b3_drift_v3.csv','H1',['R_stable_B3']),
    ]:
        p=ROOT/file
        if not p.exists():continue
        frame=read(p)
        for r in frame.to_dict('records'):
            for metric in metrics:
                if metric not in r:continue
                if metric=='coef' and 'log1p' not in str(r.get('term','')):continue
                value=r[metric];lo=r.get(metric+'_lo',r.get(metric+'_ci_lo',r.get('ci_lo',np.nan)));hi=r.get(metric+'_hi',r.get(metric+'_ci_hi',r.get('ci_hi',np.nan)))
                ref=r.get('typhoon_delta_'+metric.rsplit('_',1)[-1],np.nan) if metric.startswith('placebo_delta') else np.nan
                reference=frame
                if metric=='coef':reference=frame[(frame.date==r['date'])&(frame.term==r['term'])&frame['sample'].eq('Sstar')]
                elif metric=='gap':reference=frame[(frame.k==r['k'])&frame['class'].eq(r['class'])&frame.thr.eq(8)]
                elif metric=='r_camera':reference=frame[(frame.date==r['date'])&frame.distance_ring.eq(r['distance_ring'])&frame['sample'].eq('Sstar')]
                elif metric in ['spearman_rho','kendall_tau']:reference=frame[(frame.date==r['date'])&frame.metric.eq(r['metric'])&frame.threshold.eq(200)]
                else:reference=pd.DataFrame()
                if len(reference)==1:ref=reference.iloc[0][metric]
                label=str(r.get('metric'))+'/'+metric if metric in ['spearman_rho','kendall_tau'] else metric
                rows.append(dict(hypothesis=hyp,date=r.get('date',r.get('date_typhoon')),grp=r.get('grp',r.get('class')),k=r.get('k'),thr=r.get('thr'),variant=r.get('baseline_variant',r.get('sample',r.get('threshold',r.get('ring')))),metric=label,effect=value,lo=lo,hi=hi,reference_effect=ref,sign_preserved=bool(np.sign(value)==np.sign(ref)) if pd.notna(value) and pd.notna(ref) else None,ci_excludes_0=bool(lo>0 or hi<0) if pd.notna(lo) and pd.notna(hi) else None,p=r.get('p',r.get('spearman_p')),source=file,status_context='All rows retained; unavailable CI/sign reference remains null.'))
    save_csv(pd.DataFrame(rows),ROOT/'07_m6_robustness/m6_robustness_matrix_v3.csv')
    verdicts={}
    for hyp,file in [('H1','04_m3_vehicles/m3_h1_verdict_v3.json'),('H2','04_m3_vehicles/m3_h2_verdict_v3.json'),('H3','05_m4_spatial/m4_h3_verdict_v3.json'),('H4','06_m5_bias_correction/m5_h4_verdict_v3.json')]:
        verdicts[hyp]=json.loads((ROOT/file).read_text(encoding='utf-8'))
    drift=json.loads((ROOT/'07_m6_robustness/m6_b3_drift_v3.json').read_text(encoding='utf-8'))
    report='# M6 v3 稳健性与授权事后修正\n\n'
    for h,v in verdicts.items():report+=h+'：'+str(v.get('status',v.get(h)))+'。每个数值判据及原停止条件见相应verdict；所有变体效应、区间及未支持结果已列入矩阵。\n\n'
    report+=f"B3夏季漂移φ={drift['phi'][0]:.4f}，设备簇95%区间[{drift['phi'][1]:.4f}, {drift['phi'][2]:.4f}]，预设期望[0.80,0.95]符合={drift['expectation_met']}。校正只作敏感性，出租车无B3口径，保持NA。\n\n"
    report+='A1、B_P、四类构成与空间样本变体各自保留全部数字。T16分环小时曲线缺少网格×小时输入，BLOCKED，未回源或用边际汇总制造联合分布。五类构成仅描述，不用于判定。所有修正均属审阅后授权，不作为事前预注册。\n'
    (ROOT/'07_m6_robustness/m6_summary_v3.md').write_text(report,encoding='utf-8')
    stage_record('m6_consolidate',start,['07_m6_robustness/m6_robustness_matrix_v3.csv','07_m6_robustness/m6_summary_v3.md'],dict(rows=len(rows),source_data_scans=False))
    print('V3 robustness matrix',len(rows),'rows',flush=True)
if __name__=='__main__':main()
