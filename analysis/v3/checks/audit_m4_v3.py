# -*- coding: utf-8 -*-
"""Independent reconciliation against frozen panel counts, not original sources."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[3]), str(_ReleasePath(__file__).resolve().parents[1]), str(_ReleasePath(__file__).resolve().parent)]
import json,re
import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy.stats import spearmanr,kendalltau
import statsmodels.formula.api as smf
from common_v3 import ROOT,V1,PANELS,B1,B_TAXI,SEED,load_panels,write_json,now

def main():
    checks={}
    def check(name,value):checks[name]=bool(value)
    dh,attr,dd=load_panels();out=ROOT/'05_m4_spatial';two=ROOT/'03_m2_two_sources'
    ols=pd.read_csv(out/'m4_ols_v3.csv');old=pd.read_csv(V1/'05_m4_spatial/m4_ols.csv')
    for day in ['2021-07-26','2021-07-27','2021-07-28']:
        a=ols.loc[ols.date.eq(day)&ols['sample'].eq('Sstar')].set_index('term')
        b=old.loc[old.date.eq(day)].set_index('term')
        for c in ['coef','se_HC1','p','r_squared']:
            check('Sstar_copy_'+day+'_'+c,np.array_equal(a[c].round(4),b[c].round(4)))
        check('Sstar_copy_'+day+'_n',np.array_equal(a.n,b.n))
        refs=[d for d in B1 if pd.Timestamp(d).dayofweek==pd.Timestamp(day).dayofweek]
        ratio=dd[day]/dd[refs].mean(axis=1).replace(0,np.nan)
        for sample,sel in [('S_on',attr.in_A100.eq(1)&ratio.ge(.2)),('A100_floor',attr.in_A100.eq(1))]:
            x=attr.loc[sel&attr.lon.notna()&attr.lat.notna()].copy();x['log_base']=np.log(x.base_B1.where(x.base_B1>0))
            x['response']=np.log(ratio.reindex(x.index).clip(.05,3))
            x=x.replace([np.inf,-np.inf],np.nan).dropna(subset=['response','dist_baiguan_km','log_base','elev_m','relief_300m','road_level','org','gateway'])
            model=smf.ols('response ~ np.log1p(dist_baiguan_km) + log_base + elev_m + relief_300m + C(road_level) + C(org) + gateway',x).fit(cov_type='HC1')
            actual=ols.loc[ols.date.eq(day)&ols['sample'].eq(sample)].set_index('term')
            check(sample+'_'+day+'_complete_cases',len(x)==actual.n.iloc[0])
            check(sample+'_'+day+'_coefficients',np.allclose(model.params,actual.coef,atol=1e-9,rtol=0))
            check(sample+'_'+day+'_HC1_p',np.allclose(model.pvalues,actual.p,atol=1e-9,rtol=0))
            check(sample+'_'+day+'_floor_count',(ratio.reindex(x.index)<.05).sum()==actual.n_treated_as_floor.iloc[0])
    tg=pd.read_csv(PANELS/'taxi_grid_day.csv');piv=tg.pivot_table(index=['gx','gy'],columns='date',values='n_points',aggfunc='sum',fill_value=0)
    mov=tg.pivot_table(index=['gx','gy'],columns='date',values='n_moving',aggfunc='sum',fill_value=0)
    means=piv.reindex(columns=B_TAXI,fill_value=0).mean(axis=1)
    trans=Transformer.from_crs(4326,32651,always_xy=True)
    loc=attr.loc[attr.in_Sstar.eq(1)&attr.lon.notna()&attr.lat.notna()].copy()
    e,n=trans.transform(loc.lon.to_numpy(),loc.lat.to_numpy());loc['gx']=np.floor(e/1000).astype(int);loc['gy']=np.floor(n/1000).astype(int)
    camgrids=loc.groupby(['gx','gy']).size().index
    bg=pd.read_csv(PANELS/'township_centroids_osm.csv');bg=bg.loc[bg.town.eq('百官')].iloc[0];be,bn=trans.transform(bg.lon,bg.lat)
    correlations=pd.read_csv(two/'m2_taxi_camera_correlations_v3.csv')
    sensitivity=pd.read_csv(two/'m2_taxi_grid_threshold_sensitivity_v3.csv')
    merges=json.loads((ROOT/'00_env/m4_grid_merges_v3.json').read_text(encoding='utf-8'))
    for threshold in [100,200,400]:
        eligible=means.index[means.ge(threshold)];pairidx=eligible.intersection(camgrids)
        merge=next(m for m in merges if m['threshold']==threshold);mapping=merge['mapping']
        check('eligible_grid_'+str(threshold),len(eligible)==merge['n_eligible_grids'])
        check('paired_grid_'+str(threshold),len(pairidx)==merge['n_paired_grids'])
        dist=pd.Series(np.hypot((pairidx.get_level_values(0)+.5)*1000-be,(pairidx.get_level_values(1)+.5)*1000-bn)/1000,index=pairidx)
        citydist=pd.Series(np.hypot((eligible.get_level_values(0)+.5)*1000-be,(eligible.get_level_values(1)+.5)*1000-bn)/1000,index=eligible)
        labels=['0-2','2-4','4-7','7-12','12-20','20+'];edges=[0,2,4,7,12,20,np.inf]
        rings=pd.cut(dist,edges,labels=labels,right=False,include_lowest=True).astype(object).map(mapping)
        cityrings=pd.cut(citydist,edges,labels=labels,right=False,include_lowest=True).astype(object).map(mapping)
        for day in ['2021-07-25','2021-07-26','2021-07-27','2021-07-28']:
            refs=[d for d in B_TAXI if pd.Timestamp(d).dayofweek==pd.Timestamp(day).dayofweek]
            tn=piv.reindex(index=pairidx,columns=[day],fill_value=0)[day];tb=piv.reindex(index=pairidx,columns=refs,fill_value=0).mean(axis=1)
            mn=mov.reindex(index=pairidx,columns=[day],fill_value=0)[day];mb=mov.reindex(index=pairidx,columns=refs,fill_value=0).mean(axis=1)
            cmat=dd
            if day=='2021-07-25':
                cmat=dh.loc[dh.hour.between(11,23)].pivot_table(index='dev',columns='date',values='n',aggfunc='sum',fill_value=0).reindex(attr.index,fill_value=0)
            cr=[d for d in B1 if pd.Timestamp(d).dayofweek==pd.Timestamp(day).dayofweek]
            tmp=loc[['gx','gy']].copy();tmp['n']=cmat[day].reindex(tmp.index);tmp['b']=cmat[cr].mean(axis=1).reindex(tmp.index)
            cg=tmp.groupby(['gx','gy'])[['n','b']].sum().reindex(pairidx)
            tr=tn/tb.replace(0,np.nan);car=cg.n/cg.b.replace(0,np.nan)
            for metric,x,y in [('dist_taxi',dist,tr),('dist_camera',dist,car),('taxi_camera',tr,car)]:
                actual=correlations.loc[correlations.threshold.eq(threshold)&correlations.date.eq(day)&correlations.metric.eq(metric)].iloc[0]
                valid=x.notna()&y.notna();sp=spearmanr(x[valid],y[valid]);kt=kendalltau(x[valid],y[valid])
                check('correlation_'+str(threshold)+'_'+day+'_'+metric,len(x[valid])==actual.n_grids and abs(sp.statistic-actual.spearman_rho)<1e-9 and abs(kt.statistic-actual.kendall_tau)<1e-9 and abs(sp.pvalue-actual.spearman_p)<1e-9)
            cityn=piv.reindex(index=eligible,columns=[day],fill_value=0)[day];cityb=piv.reindex(index=eligible,columns=refs,fill_value=0).mean(axis=1)
            table=sensitivity.loc[sensitivity.threshold.eq(threshold)&sensitivity.date.eq(day)]
            check('same_A6_counts_'+str(threshold)+'_'+day,table.n_grids.sum()==len(pairidx) and table.n_grids.min()>=10)
            check('shares_close_'+str(threshold)+'_'+day,abs(table.share_base.sum()-1)<.0004 and abs(table.share_t.sum()-1)<.0004 and abs(table.paired_share_base.sum()-1)<.0004 and abs(table.paired_share_t.sum()-1)<.0004)
            for _,a in table.iterrows():
                ids=pairidx[rings.eq(a.distance_ring)];cityids=eligible[cityrings.eq(a.distance_ring)]
                expected=[tn.reindex(ids).sum()/tb.reindex(ids).sum(),mn.reindex(ids).sum()/mb.reindex(ids).sum(),cg.n.reindex(ids).sum()/cg.b.reindex(ids).sum()]
                check('ring_ratio_'+str(threshold)+'_'+day+'_'+a.distance_ring,np.allclose(expected,[a.r_taxi_pts,a.r_taxi_moving,a.r_camera],atol=.000051,rtol=0))
                sb=cityb.reindex(cityids).sum()/cityb.sum();st=cityn.reindex(cityids).sum()/cityn.sum()
                check('cityshare_'+str(threshold)+'_'+day+'_'+a.distance_ring,abs(sb-a.share_base)<.000051 and abs(st-a.share_t)<.000051 and abs(st-sb-a.share_shift)<.000051)
                check('delta_identity_'+str(threshold)+'_'+day+'_'+a.distance_ring,abs(expected[0]-expected[2]-a.delta_ring)<.000051)
                check('CI_valid_'+str(threshold)+'_'+day+'_'+a.distance_ring,all(a[c+'_ci_lo']<=a[c+'_ci_hi'] for c in ['r_taxi_pts','r_taxi_moving','r_camera','delta_ring','share_shift','paired_share_shift']))
    five=pd.read_csv(out/'m4_five_ring_criterion_v3.csv');s=five.loc[five.date.eq('2021-07-26')&five['sample'].eq('Sstar')]
    verdict=json.loads((out/'m4_h3_verdict_v3.json').read_text(encoding='utf-8'))
    rho=spearmanr(s.ring_order,s.r_camera).statistic
    check('H3_five_ring_criterion',len(s)==5 and abs(rho-verdict['criteria'][5]['observed']['rho'])<1e-10)
    check('H3_status_exact_rule',verdict['status']==('supported' if all(v['met'] for v in verdict['criteria']) else ('partial' if verdict['criteria'][0]['met'] and verdict['criteria'][3]['met'] else 'not_supported')))
    check('H3_no_taxi_veto_no_new_stop',verdict['taxi_cross_source_direction_is_H3_criterion'] is False and verdict['automatic_stop_condition'] is None)
    for f in ['fig5_spatial_v3_data.csv','fig7_two_sensors_v3_data.csv']:
        q=pd.read_csv(ROOT/'08_figures'/f)
        check(f+'_no_identifiers',not any(c in q for c in ['dev','ph','vehicle_id','plate']))
        text=(ROOT/'08_figures'/f).read_text(encoding='utf-8-sig')
        check(f+'_no_HMAC_tokens',re.search(r'(?<![0-9a-f])[0-9a-f]{16}(?![0-9a-f])',text) is None)
        for col in ['lon','lat','plot_lon','plot_lat']:
            if col in q:check(f+'_'+col+'_rounded',np.allclose(q[col].dropna(),q[col].dropna().round(2),atol=1e-12))
    hourly=json.loads((ROOT/'00_env/m4_taxi_hourly_blocked_v3.json').read_text(encoding='utf-8'))
    check('hourly_BLOCKED_truthful',not (PANELS/'taxi_grid_hour.csv').exists() and hourly['status']=='BLOCKED' and hourly['source_accessed'] is False)
    floor_account=pd.read_csv(out/'m4_ols_floor_accounting_v3.csv')
    for (day,sample),g in floor_account.groupby(['date','sample']):
        m=ols.loc[ols.date.eq(day)&ols['sample'].eq(sample)].iloc[0]
        check('floor_accounting_'+day+'_'+sample,int(g.n_devices.sum())==int(m.n) and int(g.loc[g.treated_as_floor.eq(1),'n_devices'].iloc[0])==int(m.n_treated_as_floor))
    failed=[k for k,v in checks.items() if not v]
    write_json(ROOT/'00_env/m4_independent_audit_v3.json',dict(ended=now(),seed=SEED,n_checks=len(checks),all_passed=not failed,failed=failed,checks=checks))
    print(json.dumps(dict(M4_audit=not failed,n_checks=len(checks),failed=failed)))
    if failed:raise RuntimeError('M4 independent reconciliation failed')
if __name__=='__main__':main()
