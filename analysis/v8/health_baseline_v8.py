# -*- coding: utf-8 -*-
"""W1 device B1w sensitivity/W3 retained-channel health; frozen local inputs."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[2]), str(_ReleasePath(__file__).resolve().parents[0])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from pathlib import Path
from datetime import datetime,timezone,timedelta
import argparse,hashlib,json,time,sys
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from pyproj import Transformer

V1=Path(_release_path('project_root'));V6=V1/'formal_v6';V7=V1/'formal_v7';R=V1/'formal_v8'
SEED=20261005;BOOT=500;FIVE=['0-2','2-4','4-7','7-12','12+']
EVENT=pd.date_range('2021-07-25','2021-08-02').strftime('%Y-%m-%d').tolist()
B1=[d for d in pd.date_range('2021-07-05','2021-07-21').strftime('%Y-%m-%d') if d not in ['2021-07-08','2021-07-10']]
B1W=[d for d in B1 if d not in ['2021-07-07','2021-07-21']]
RULES=R/'00_env/interpretation_health_baseline_v8.json'
def now():return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(x):
    if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple,np.ndarray)):return [clean(v) for v in x]
    if isinstance(x,np.generic):return clean(x.item())
    if isinstance(x,float) and not np.isfinite(x):return None
    return x
def save(q,relative):
    p=R/relative;assert p.parent in [R/'01_internal',R/'03_baseline']
    assert p.name.startswith(('health','W1_device','W3'))
    p.parent.mkdir(parents=True,exist_ok=True)
    if p.suffix=='.parquet':q.to_parquet(p,index=False)
    else:q.to_csv(p,index=False,encoding='utf-8-sig',float_format='%.12g',na_rep='NA')
def write(relative,x):
    p=R/relative;assert p.parent==R/'00_env';p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def divide(n,b):return np.divide(n,b,out=np.full(np.broadcast_shapes(np.shape(n),np.shape(b)),np.nan),where=np.asarray(b)>0)
def ratio(n,b):return float(np.sum(n)/np.sum(b)) if np.sum(b)>0 else np.nan
def ci(x):
    x=np.asarray(x,float);x=x[np.isfinite(x)]
    return np.quantile(x,[.025,.975]) if len(x) else np.full(2,np.nan)
def weights(universe):
    n=int(universe.sum());w=np.zeros((BOOT,len(universe)),np.int64)
    w[:,universe]=np.random.default_rng(SEED).multinomial(n,np.full(n,1/n),BOOT)
    return w

class Inputs:
    def __init__(self):
        self.hashes={};self.checks={}
        self.attr=self.read(V1/'01_panels/device_attributes.csv').sort_values('dev').reset_index(drop=True)
        self.attr['dev_public']=np.arange(1,len(self.attr)+1);self.ids=self.attr.dev_public.to_numpy();self.devs=self.attr.dev.to_numpy()
        self.A100=self.attr.in_A100.eq(1).to_numpy();self.A200=self.attr.in_A200.eq(1).to_numpy();self.star=self.attr.in_Sstar.eq(1).to_numpy()
        dd=self.read(V1/'01_panels/device_day.csv')
        self.day=dd.pivot_table(index='dev',columns='date',values='n',aggfunc='sum',fill_value=0).reindex(index=self.devs,fill_value=0)
        h=self.read(V1/'01_panels/device_hour.csv',usecols=['dev','date','hour','n'])
        self.h11=h[h.hour.between(11,23)].pivot_table(index='dev',columns='date',values='n',aggfunc='sum',fill_value=0).reindex(index=self.devs,fill_value=0)
        self.q=self.read(V7/'01_internal/device_state_internal_v7.csv').set_index(['date','dev_public'])
        self.family=self.read(V7/'07_consequences/T37_estimator_family_v7.csv')
        self.health=self.read(V7/'06_s_pre/T36_health_screened_v6.csv').set_index('date')
        self.scenario=self.read(V6/'01_internal/T31_device_scenarios_internal_v6.parquet')
        self.cap=self.read(V7/'01_internal/capture_camera_internal_v7.csv')
        self.w100=weights(self.A100);self.w200=weights(self.A200)
        self.xy=np.full((len(self.attr),2),np.nan);ok=self.attr.lon.notna()&self.attr.lat.notna()&self.attr.lon.ne(0)&self.attr.lat.ne(0)
        tr=Transformer.from_crs(4326,32651,always_xy=True);self.xy[ok]=np.column_stack(tr.transform(self.attr.loc[ok,'lon'],self.attr.loc[ok,'lat']))
        self.coord=np.isfinite(self.xy).all(1)
        self.rings=pd.cut(self.attr.dist_baiguan_km,[0,2,4,7,12,np.inf],labels=FIVE,right=False,include_lowest=True).astype(object).fillna('missing').to_numpy()
    def read(self,p,**kw):
        self.hashes[str(p)]=sha(p)
        return pd.read_parquet(p,**kw) if Path(p).suffix=='.parquet' else pd.read_csv(p,encoding='utf-8-sig',**kw)
    def vectors(self,date,pool=B1):
        mat=self.h11 if date==EVENT[0] else self.day
        refs=[d for d in pool if pd.Timestamp(d).dayofweek==pd.Timestamp(date).dayofweek]
        if not refs:raise RuntimeError('No matched baseline day')
        return mat[date].to_numpy(float),mat[refs].mean(axis=1).to_numpy(float),refs
    def states(self,date):return self.q.loc[date].reindex(self.ids)
    def unchanged(self):return all(sha(p)==h for p,h in self.hashes.items())

def w3(p):
    daily=[];drawrows=[];members=[];masks={}
    for d in EVENT:
        q=p.states(d);n,b,refs=p.vectors(d)
        use=p.A200&~q.state.isin(['zero','offline','partial_day']).to_numpy();old=q.in_health.fillna(0).eq(1).to_numpy()
        masks[d]=use;draw=divide(p.w200[:,use]@n[use],p.w200[:,use]@b[use]);lo,hi=ci(draw)
        missing=use&(p.rings=='missing')
        daily.append(dict(date=d,estimator='R_health_pc',value=ratio(n[use],b[use]),ci_lo=lo,ci_hi=hi,n_devices=int(use.sum()),
            hour_matched=int(d==EVENT[0]),baseline='B1',baseline_dates=';'.join(refs),n_retained_partial_channel=int((use&q.state.eq('partial_channel').to_numpy()).sum()),
            observed_records=int(n[use].sum()),baseline_records=float(b[use].sum()),n_missing_distance=int(missing.sum()),baseline_share_missing_distance=ratio(b[missing],b[use]),
            R_health_frozen=float(p.health.loc[d,'R_health']),R_health_pc_minus_health=ratio(n[use],b[use])-float(p.health.loc[d,'R_health']),
            bootstrap_valid=int(np.isfinite(draw).sum()),interval_scope='500 shared A200 device-cluster weights; fixed state/membership and baseline days; conditional percentile95; no classification uncertainty',
            interpretation='Record-period and lane-coverage sensitivity; relative thresholds remain; not independent hardware telemetry'))
        drawrows.append(pd.DataFrame(dict(date=d,baseline='B1',estimator='R_health_pc',rep=np.arange(1,501),estimate=draw)))
        members.append(pd.DataFrame(dict(date=d,dev_public=p.ids,in_health_pc=use,in_health_v7=old,state=q.state.to_numpy())))
        p.checks['W3_only_partial_channel_added_'+d]=np.array_equal(use&~old,p.A200&q.state.eq('partial_channel').to_numpy()) and not (old&~use).any()
        p.checks['W3_target_records_frozen_'+d]=np.array_equal(q.loc[p.A100,'n_day'],n[p.A100])
        p.checks['W3_baseline_records_frozen_'+d]=np.allclose(q.loc[p.A100,'baseline_B1'],b[p.A100],rtol=2e-11,atol=1e-6)
    frame=pd.DataFrame(daily);save(frame,'03_baseline/W3_health_pc_daily_v8.csv');save(pd.concat(drawrows),'01_internal/health_pc_bootstrap_v8.parquet');save(pd.concat(members),'01_internal/health_pc_membership_v8.csv')
    d='2021-07-26';n,b,_=p.vectors(d);use=masks[d];rng=np.random.default_rng(SEED);rings=[]
    for r in FIVE:
        selected=use&(p.rings==r);ids=np.flatnonzero(selected)
        if len(ids):
            ix=rng.integers(0,len(ids),size=(BOOT,len(ids)));boot=divide(n[ids][ix].sum(1),b[ids][ix].sum(1))
        else:boot=np.full(BOOT,np.nan)
        lo,hi=ci(boot)
        rings.append(dict(date=d,distance_ring=r,estimator='R_health_pc',value=ratio(n[selected],b[selected]),ci_lo=lo,ci_hi=hi,n_devices=len(ids),observed_records=int(n[selected].sum()),baseline_records=float(b[selected].sum()),
            n_selected_city=int(use.sum()),n_missing_distance=int((use&(p.rings=='missing')).sum()),baseline_share_missing_distance=ratio(b[use&(p.rings=='missing')],b[use]),
            interval_scope='500fixed-size within-observed-ring device draws; membership fixed; conditional percentile95',denominator_scope='City includes missing-distance devices; original five rings exclude missing-distance'))
    save(pd.DataFrame(rings),'03_baseline/W3_health_pc_rings_0726_v8.csv')
    import statsmodels.formula.api as smf
    r=divide(n,b);x=p.attr.loc[use&p.attr.lon.notna().to_numpy()&p.attr.lat.notna().to_numpy()].copy()
    x['log_base']=np.log(x.base_B1.where(x.base_B1.gt(0)));x['response']=np.log(pd.Series(r,index=p.attr.index).reindex(x.index).clip(.05,3))
    x['treated_as_floor']=(pd.Series(r,index=p.attr.index).reindex(x.index)<.05).astype(int)
    x=x.replace([np.inf,-np.inf],np.nan).dropna(subset=['response','dist_baiguan_km','log_base','elev_m','relief_300m','road_level','org','gateway'])
    formula='response ~ np.log1p(dist_baiguan_km) + log_base + elev_m + relief_300m + C(road_level) + C(org) + gateway'
    fit=smf.ols(formula,data=x).fit(cov_type='HC1');conf=fit.conf_int(alpha=.05)
    model=pd.DataFrame([dict(date=d,sample='R_health_pc',term=t,coef=float(v),se_HC1=float(fit.bse[t]),p=float(fit.pvalues[t]),ci_lo=float(conf.loc[t,0]),ci_hi=float(conf.loc[t,1]),n=int(fit.nobs),n_selected_city=int(use.sum()),n_not_in_complete_cases=int(use.sum()-fit.nobs),r_squared=float(fit.rsquared),n_treated_as_floor=int(x.treated_as_floor.sum()),response='log(r.clip(0.05,3))',covariance='HC1',formula=formula) for t,v in fit.params.items()])
    save(model,'03_baseline/W3_health_pc_ols_0726_v8.csv')
    q=p.states(d);eligible=p.cap[p.cap.variant.eq('main_R60_cap03')&p.cap.date.eq(d)&p.cap.selected.eq(True)&p.cap.expected.ge(10)]
    scopes={'all_A200':p.A200,'main329_selected_event_expected_ge10':p.A200&np.isin(p.ids,eligible.dev)}
    records=[]
    for scope,scope_mask in scopes.items():
        for state in ['zero','offline','partial_day','partial_channel','recognition_degraded','low_all_channels','degraded_other','normal']:
            mask=scope_mask&q.state.eq(state).to_numpy();v=r[mask];a=pd.to_numeric(q.ratio_A1,errors='coerce').to_numpy()[mask]
            records.append(dict(date=d,scope=scope,state=state,n_devices=int(mask.sum()),n_finite_ratio_B1=int(np.isfinite(v).sum()),ratio_B1_median=float(np.median(v[np.isfinite(v)])) if np.isfinite(v).any() else np.nan,
                n_finite_ratio_A1=int(np.isfinite(a).sum()),ratio_A1_median=float(np.median(a[np.isfinite(a)])) if np.isfinite(a).any() else np.nan,
                baseline_flow=float(b[mask].sum()),ratio_B1_definition='Daily all-hour records / same-weekday B1 mean; primary',ratio_A1_definition='Frozen original A1 previous-week/fallback denominator; separate diagnostic'))
    stats=pd.DataFrame(records);save(stats[stats.scope.eq('all_A200')],'03_baseline/W3_state_ratio_medians_A200_0726_v8.csv');save(stats[stats.scope.ne('all_A200')],'03_baseline/W3_state_ratio_medians_selected_0726_v8.csv')
    p.checks['W3_original5rings_non_sparse']=all(z['n_devices']>=10 for z in rings)
    p.checks['W3_state_A200_denominator_closure']=stats[stats.scope.eq('all_A200')].n_devices.sum()==p.A200.sum()
    p.checks['W3_selected_state_denominator_closure']=stats[stats.scope.ne('all_A200')].n_devices.sum()==len(eligible)
    return dict(daily=frame.to_dict('records'),rings=rings,OLS_distance=model[model.term.eq('np.log1p(dist_baiguan_km)')].to_dict('records'),state_medians=stats.to_dict('records'))

def w1(p):
    d='2021-07-28';n,b1,refs=p.vectors(d);_,bw,wrefs=p.vectors(d,B1W)
    q=p.states(d);old=p.scenario[p.scenario.date.eq(d)].set_index('dev_public').reindex(p.ids)
    U=old.U.fillna(False).to_numpy(bool);online=old.in_online.fillna(False).to_numpy(bool);low=U&old.state.eq('low_all_channels').to_numpy()
    r1=divide(n,b1);rw=divide(n,bw);donors=np.flatnonzero(online&np.isfinite(r1));good=donors[p.coord[donors]];tree=cKDTree(p.xy[good]) if len(good) else None
    med1=np.full(len(n),np.nan);medw=med1.copy();globalfb=np.zeros(len(n),bool);ndonor=np.zeros(len(n),int);links=[]
    for target in np.flatnonzero(U):
        use=donors[donors!=target];globaltarget=True
        if tree is not None and p.coord[target]:
            candidate=np.atleast_1d(tree.query(p.xy[target],k=min(8,len(good)))[1]);chosen=good[candidate];chosen=chosen[chosen!=target][:6]
            if len(chosen):use=chosen;globaltarget=False
        if len(use):med1[target]=np.median(r1[use]);medw[target]=np.median(rw[use]);ndonor[target]=len(use);globalfb[target]=globaltarget
        links.extend(dict(baseline='B1',target_dev_public=int(p.ids[target]),donor_dev_public=int(p.ids[i]),rank=k+1,global_fallback=globaltarget) for k,i in enumerate(use))
    # Original T31 numerical eligibility: undefined ratios are not donors.
    # S_on and U remain frozen; neighbour values/eligibility reflect each baseline.
    medw[:]=np.nan;donorsw=np.flatnonzero(online&np.isfinite(rw));goodw=donorsw[p.coord[donorsw]]
    treew=cKDTree(p.xy[goodw]) if len(goodw) else None;ndonorw=np.zeros(len(n),int);globalfbw=np.zeros(len(n),bool)
    for target in np.flatnonzero(U):
        use=donorsw[donorsw!=target];globaltarget=True
        if treew is not None and p.coord[target]:
            candidate=np.atleast_1d(treew.query(p.xy[target],k=min(8,len(goodw)))[1]);chosen=goodw[candidate];chosen=chosen[chosen!=target][:6]
            if len(chosen):use=chosen;globaltarget=False
        if len(use):medw[target]=np.median(rw[use]);ndonorw[target]=len(use);globalfbw[target]=globaltarget
        links.extend(dict(baseline='B1w',target_dev_public=int(p.ids[target]),donor_dev_public=int(p.ids[i]),rank=k+1,global_fallback=globaltarget) for k,i in enumerate(use))
    upper1=n.copy();upperw=n.copy();ru1=np.minimum(1.1,med1);ruw=np.minimum(1.1,medw);ru1[low]=np.minimum(1.1,.5*med1[low]);ruw[low]=np.minimum(1.1,.5*medw[low]);upper1[U]=b1[U]*ru1[U];upperw[U]=bw[U]*ruw[U]
    p.checks['W1_original_T31_U_count']=int(U.sum())==int(old.loc[p.A100,'U'].sum())
    p.checks['W1_original_neighbor_medians_exact']=np.allclose(med1[U],old.loc[U,'neighbor_online_median'].to_numpy(float),rtol=5e-11,atol=5e-11,equal_nan=True)
    p.checks['W1_original_neighbor_counts_exact']=np.array_equal(ndonor[U],old.loc[U,'n_online_donors_used'].to_numpy(int))
    p.checks['W1_original_neighbor_global_fallback_exact']=np.array_equal(globalfb[U],old.loc[U,'neighbor_global_fallback'].to_numpy(bool))
    p.checks['W1_original_upper_records_exact']=np.allclose(upper1[p.A100],old.loc[p.A100,'records_upper_scenario'],rtol=5e-11,atol=1e-6,equal_nan=True)
    p.checks['W1_only_July14_Wednesday']=wrefs==['2021-07-14'] and refs==['2021-07-07','2021-07-14','2021-07-21']
    p.checks['W1_U_membership_frozen_not_reclassified']=np.array_equal(U,old.U.fillna(False).to_numpy(bool))
    save(pd.DataFrame(links),'01_internal/health_baseline_neighbor_links_v8.csv')
    device=pd.DataFrame(dict(dev_public=p.ids,in_A100=p.A100,in_A200=p.A200,in_Sstar=p.star,in_online=online,U=U,state_T31_v6=old.state,state_v7=q.state,
        observed_records=n,baseline_B1=b1,baseline_B1w=bw,ratio_B1=r1,ratio_B1w=rw,neighbor_median_B1=med1,neighbor_median_B1w=medw,n_donors=ndonor,global_fallback=globalfb,n_donors_B1w=ndonorw,global_fallback_B1w=globalfbw,records_upper_B1=upper1,records_upper_B1w=upperw))
    save(device,'01_internal/health_baseline_device_0728_v8.csv')
    samples={'R_naive':p.A100,'R_online':online,'R_health':p.A200&q.in_health.fillna(0).eq(1).to_numpy(),'R_health_strict':p.A200&q.in_health_strict.fillna(0).eq(1).to_numpy(),'R_spre_health':p.A200&q.in_Spre_health.fillna(0).eq(1).to_numpy(),'R_stable':p.star,'R_upper':p.A100}
    rows=[];boots=[];reproduction=[]
    frozen=p.family[p.family.date.eq(d)].set_index('estimator')
    for estimator,use in samples.items():
        w=p.w200 if estimator in ['R_health','R_health_strict','R_spre_health'] else p.w100
        for baseline,b,values in [('B1',b1,upper1 if estimator=='R_upper' else n),('B1w',bw,upperw if estimator=='R_upper' else n)]:
            raw=ratio(values[use],b[use]);draw=divide(w[:,use]@values[use],w[:,use]@b[use]);lo,hi=ci(draw)
            if baseline=='B1':
                source=frozen.loc[estimator];value=float(source.R);lo=float(source.ci_lo);hi=float(source.ci_hi);scope=str(source.interval_scope)
                reproduction.append(dict(estimator=estimator,raw_B1_value=raw,published_B1_value=value,difference=raw-value))
                p.checks['W1_B1_reproduces_frozen4dp_'+estimator]=abs(raw-value)<=.000051
            else:value=raw;scope='500 shared '+('A200' if w is p.w200 else 'A100')+' device-cluster weights; fixed sets/U; baseline-specific finite-ratio donors and neighbours fixed withinbootstrap; baseline days fixed; conditional percentile95; no selection/baseline-day uncertainty'
            rows.append(dict(date=d,baseline=baseline,estimator=estimator,value=value,ci_lo=lo,ci_hi=hi,available=bool(np.isfinite(value)),n_devices=int(use.sum()),interval_scope=scope,
                source='formal_v7/07_consequences/T37_estimator_family_v7.csv' if baseline=='B1' else '01_panels/device_day.csv + frozen v7 sets + frozen v6 T31 formula',source_value_column=estimator,
                baseline_dates=';'.join(refs if baseline=='B1' else wrefs),bootstrap_valid=int(np.isfinite(draw).sum()),n_U_frozen=int(U.sum()),n_U_undefined_donor_ratio=int((U&~np.isfinite(medw)).sum()) if estimator=='R_upper' else 0,
                point_precision='Copied published B1; B1w original panel precision',scenario_scope='R_upper is an imputation scenario endpoint, not a mathematical upper bound' if estimator=='R_upper' else 'Baseline sensitivity; frozen observed membership'))
            boots.append(pd.DataFrame(dict(date=d,baseline=baseline,estimator=estimator,rep=np.arange(1,501),estimate=draw)))
    frame=pd.DataFrame(rows).sort_values(['baseline','estimator']);save(frame,'03_baseline/W1_device_estimators_v8.csv');save(pd.concat(boots),'01_internal/health_baseline_bootstrap_v8.parquet');save(pd.DataFrame(reproduction),'01_internal/health_baseline_B1_reproduction_v8.csv')
    p.checks['W1_14rows_7estimators_2baselines']=len(frame)==14 and frame.estimator.nunique()==7 and frame.baseline.nunique()==2
    return dict(rows=frame.to_dict('records'),n_U_undefined_B1w=int((U&~np.isfinite(medw)).sum()),n_online_donors_nonfinite_B1w=int((online&~np.isfinite(rw)).sum()),baseline_reproduction=reproduction)

def main(protocol,stage):
    start=now();tick=time.monotonic();protocol=Path(protocol)
    if not protocol.is_file():raise RuntimeError('Frozen root protocol required')
    proto=json.loads(protocol.read_text(encoding='utf-8-sig'))
    if not proto.get('frozen_at'):raise RuntimeError('Protocol not frozen')
    ph=sha(protocol);rh=sha(RULES);rules=json.loads(RULES.read_text(encoding='utf-8-sig'));assert rules['status']=='frozen_before_new_effect_calculation'
    addendum=R/'00_env/implementation_addendum_health_baseline_v8.json';ah=sha(addendum) if addendum.exists() else None
    p=Inputs();details1=w1(p)
    details3=w3(p) if stage=='all' else json.loads((R/'00_env/health_baseline_execution_initial_frozen_neighbors_v8.json').read_text(encoding='utf-8'))['W3']
    p.checks['all_old_inputs_unchanged']=p.unchanged();p.checks['root_protocol_unchanged']=sha(protocol)==ph;p.checks['own_frozen_rules_unchanged']=sha(RULES)==rh
    if ah:p.checks['implementation_addendum_unchanged']=sha(addendum)==ah
    report=dict(status='complete' if all(p.checks.values()) else 'failed',stage=stage,start=start,end=now(),seconds=time.monotonic()-tick,command=[sys.executable]+sys.argv,seed=SEED,checks=p.checks,n_checks=len(p.checks),all_passed=all(p.checks.values()),inputs_sha256=p.hashes,protocol_sha256=ph,interpretation_sha256=rh,implementation_addendum_sha256=ah,W1=details1,W3=details3,source_reads=False,key_reads=False,old_versions_modified=False,H1_H4_recomputed=False)
    write('00_env/health_baseline_execution_v8.json',report)
    print(json.dumps(dict(all_passed=report['all_passed'],n_checks=len(p.checks),failed=[k for k,v in p.checks.items() if not v],seconds=report['seconds'],W1_B1w=details1['rows'][7:])))
    if not report['all_passed']:raise AssertionError('Health/baseline integrity failure')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--protocol',default=str(R/'00_env/protocol_frozen_v8.json'));parser.add_argument('--stage',choices=['all','w1'],default='all');args=parser.parse_args();main(args.protocol,args.stage)
