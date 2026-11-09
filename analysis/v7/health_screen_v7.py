# -*- coding: utf-8 -*-
"""I1'/I6': new states and health sensitivity, frozen local inputs only."""
import argparse,json,time
import numpy as np
import pandas as pd
from health_helpers_v7 import (ROOT,V1,V3,V6,SEED,N_BOOT,EVENT,D_STATE,FIVE,
    Panels,now,sha,write_json,save_csv,require_protocol,ratio,ci,ring,fit_ols)

INTERPRET=ROOT/'00_env/interpretation_health_v7.json'
STATE_INPUT=V6/'01_internal/device_state_internal_v6.csv'
PRE_INPUT=V6/'01_internal/s_pre_devices_v6.csv'
STATE_OUTPUT=ROOT/'01_internal/device_state_internal_v7.csv'
ORDER=['zero','offline','partial_day','partial_channel','recognition_degraded','low_all_channels','degraded_other','normal']
BAD=['zero','offline','partial_day','partial_channel']
STRICT_BAD=BAD+['degraded_other','low_all_channels']
FAMILIES=[('health','in_health','R_health'),('health_strict','in_health_strict','R_health_strict'),('spre_health','in_Spre_health','R_spre_health')]


def partial_day_candidate(recording,stop,zero_run):
    recording=np.asarray(recording,float);stop=np.asarray(stop,float);zero_run=np.asarray(zero_run,float)
    return (recording>=5)&(recording<=11)&(np.isfinite(stop)|(zero_run>=6))


def make_states():
    q=pd.read_csv(STATE_INPUT,encoding='utf-8-sig')
    pre=pd.read_csv(PRE_INPUT,encoding='utf-8-sig')
    assert not q.duplicated(['dev','date']).any()
    assert set(EVENT)<=set(q.date)
    q=q.rename(columns={'state':'state_v6','public_D_STATE':'public_D_STATE_v6',
        'normal_catchall_low_or_missing_ratio':'normal_catchall_low_or_missing_ratio_v6'})
    selected=set(pre.loc[pre.in_Spre.eq(1),'dev'])
    q['in_Spre']=q.dev.isin(selected).astype(int)
    q['partial_day_stop_present']=np.isfinite(pd.to_numeric(q.stop_hour,errors='coerce')).astype(int)
    candidate=partial_day_candidate(q.hours_recording,pd.to_numeric(q.stop_hour,errors='coerce'),q.longest_zero_run)
    q['partial_day_candidate']=candidate.astype(int)
    q['state']=q.state_v6.copy()
    use=q.in_A200.eq(1)&~q.state_v6.isin(['zero','offline'])&candidate
    q.loc[use,'state']='partial_day'
    q['normal_catchall_low_or_missing_ratio']=((q.state=='normal')&((q.ratio_A1<.05)|~np.isfinite(q.ratio_A1))).astype(int)
    q['public_D_STATE_v7']=1
    q['in_health']=(q.in_A200.eq(1)&~q.state.isin(BAD)).astype(int)
    q['in_health_strict']=(q.in_A200.eq(1)&~q.state.isin(STRICT_BAD)).astype(int)
    q['in_Spre_health']=(q.in_Spre.eq(1)&q.in_health.eq(1)).astype(int)
    q['state_version']='v7_partial_day_after_offline'
    q['partial_day_rule']='raw5..11recording_hours AND (finite_stop_hour OR longest_zero_run>=6)'
    attrs=pd.read_csv(V1/'01_panels/device_attributes.csv',encoding='utf-8-sig').sort_values('dev')
    public_map=pd.Series(np.arange(1,len(attrs)+1),index=attrs.dev)
    checks=dict(unique_device_date=not q.duplicated(['dev','date']).any(),
        public_mapping_frozen=q.dev.map(public_map).eq(q.dev_public).all(),
        A200_only_classification=q.loc[q.in_A200.ne(1),'state'].eq('not_classified_outside_A200').all(),
        zero_offline_unchanged=q.loc[q.state_v6.isin(['zero','offline']),'state'].eq(q.loc[q.state_v6.isin(['zero','offline']),'state_v6']).all(),
        only_new_partial_day_changed=q.loc[q.state.ne(q.state_v6),'state'].eq('partial_day').all(),
        all12_existing_dates=len(q.date.unique())==12,
        all9_event_dates_present=set(EVENT)<=set(q.date),
        healthy_subsets_A200=not q.loc[q.in_health.eq(1)|q.in_health_strict.eq(1)|q.in_Spre_health.eq(1),'in_A200'].ne(1).any())
    outside=int((pre.in_Spre.eq(1)&pre.in_A200.ne(1)).sum())
    return q,checks,outside


def state_tables(q):
    public=q[q.in_A200.eq(1)].drop(columns=['dev','lon','lat']).rename(columns={'dev_public':'dev'}).sort_values(['date','dev'])
    save_csv(public,ROOT/'02_device_state/device_state_v7.csv')
    rows=[];failed=[]
    for date,x in public.groupby('date',sort=True):
        nt=len(x);nf=int(x.A1_failed.sum());total=float(x.base_B1.sum())
        for state in ORDER:
            g=x[x.state.eq(state)];ng=len(g);nfs=int(g.A1_failed.sum());org=g.org.fillna('missing').value_counts()
            rows.append(dict(date=date,state=state,n_devices=ng,n_A200=nt,share_A200=ng/nt,
                n_A1_failed_in_state=nfs,n_A1_failed=nf,share_A1_failed=nfs/nf if nf else np.nan,
                baseline_flow=float(g.base_B1.sum()),baseline_flow_share=float(g.base_B1.sum()/total) if total else np.nan,
                dist_baiguan_median_km=float(g.dist_baiguan_km.median()) if g.dist_baiguan_km.notna().any() else np.nan,
                n_devices_with_distance=int(g.dist_baiguan_km.notna().sum()),org_max_share=float(org.iloc[0]/ng) if ng else np.nan,
                org_max_category=str(org.index[0]) if ng else '',public_D_STATE_v6=int(date in D_STATE),
                weight_definition='base_B1 / all A200 base_B1'))
            failed.append(dict(date=date,state=state,n_failed_state=nfs,n_failed_A1=nf,share_failed=nfs/nf if nf else np.nan,
                public_D_STATE_v6=int(date in D_STATE)))
    summary=pd.DataFrame(rows);breakdown=pd.DataFrame(failed)
    save_csv(summary,ROOT/'02_device_state/T27_state_summary_v7.csv')
    save_csv(breakdown,ROOT/'02_device_state/T27_failed_breakdown_v7.csv')
    change=public.groupby(['date','state_v6','state']).size().rename('n_devices').reset_index()
    save_csv(change,ROOT/'02_device_state/T27_state_changes_v7.csv')
    mp=pd.read_csv(V6/'08_figures/fig_state_map_v6_data.csv',encoding='utf-8-sig',dtype={'plot_lon':str,'plot_lat':str})
    updated=public[public.date.eq('2021-07-26')][['dev','state','state_v6','partial_day_candidate']]
    mp=mp.drop(columns='state').merge(updated,on='dev',how='left',validate='one_to_one')
    assert mp.state.notna().all()
    save_csv(mp,ROOT/'08_figures/fig_state_map_v7_data.csv')
    return summary,breakdown


def merge_five(counts):
    groups=[[r] for r in FIVE];changes=[]
    while len(groups)>1:
        sparse=[i for i,g in enumerate(groups) if min(sum(counts[d].get(r,0) for r in g) for d in EVENT)<10]
        if not sparse:break
        i=max(sparse);target=i-1 if i>0 else 1
        changes.append(dict(from_rings=groups[i].copy(),into_rings=groups[target].copy(),direction='inward' if i else 'only_outward_neighbour'))
        groups[target]=sorted(groups[target]+groups[i],key=FIVE.index);groups.pop(i)
    mapping={};labels=[]
    for g in groups:
        label=g[0] if len(g)==1 else (g[0].split('-')[0]+'+' if g[-1]=='12+' else g[0].split('-')[0]+'-'+g[-1].split('-')[-1])
        labels.append(label)
        for r in g:mapping[r]=label
    return mapping,labels,changes


def ring_tables(p,masks,mapping,labels,variant):
    rng=np.random.default_rng(SEED);original=ring(p.attr.dist_baiguan_km,five=True);mapped=original.map(mapping)
    rows=[]
    for d in EVENT:
        n,b=p.vectors(d);selected=masks[d]['health']
        for label in labels:
            use=selected&mapped.eq(label).to_numpy();ids=np.flatnonzero(use)
            if len(ids):
                ix=rng.integers(0,len(ids),size=(N_BOOT,len(ids)))
                num=n[ids][ix].sum(1);den=b[ids][ix].sum(1)
                draws=np.divide(num,den,out=np.full(N_BOOT,np.nan),where=den>0)
            else:draws=np.full(N_BOOT,np.nan)
            lo,hi=ci(draws)
            rows.append(dict(date=d,estimator='R_health',distance_ring=label,n_devices=len(ids),
                R_health=ratio(n[use],b[use]),R_health_ci_lo=lo,R_health_ci_hi=hi,
                observed_records=int(n[use].sum()),baseline_records=float(b[use].sum()),
                n_selected_city=int(selected.sum()),n_missing_distance=int((selected&original.eq('missing').to_numpy()).sum()),
                baseline_share_missing_distance=float(b[selected&original.eq('missing').to_numpy()].sum()/b[selected].sum()) if b[selected].sum()>0 else np.nan,
                variant=variant,device_bootstrap=N_BOOT,bootstrap_valid=int(np.isfinite(draws).sum()),hour_matched=int(d=='2021-07-25'),
                denominator_scope='Selected health devices with distance in this ring; city includes missing-distance devices',
                CI_scope='500fixed-size within-selected-ring device draws; state/membership fixed; conditional percentile95'))
    return pd.DataFrame(rows)


def health_tables(q,outside):
    p=Panels();checks=dict(p.checks);indexed=q.set_index(['date','dev'])
    frozen=pd.read_csv(V3/'06_m5_bias_correction/m5_visible_bias_v3.csv',encoding='utf-8-sig').set_index('date')
    oldpre=pd.read_csv(V6/'06_s_pre/T32_s_pre_v6.csv',encoding='utf-8-sig').set_index('date')
    rng=np.random.default_rng(SEED);na=int(p.A200.sum());weights=np.zeros((N_BOOT,p.n_dev),dtype=np.int64)
    weights[:,p.A200]=rng.multinomial(na,np.full(na,1/na),size=N_BOOT)
    rows=[];drawrows=[];masks={};distance_missing=p.attr.dist_baiguan_km.isna().to_numpy()
    for d in EVENT:
        n,b=p.vectors(d);x=indexed.loc[d].reindex(p.devs)
        checks['n_matches_state_'+d]=np.array_equal(x.loc[p.A100,'n_day'].to_numpy(),n[p.A100])
        checks['B1_matches_state_'+d]=np.allclose(x.loc[p.A100,'baseline_B1'].to_numpy(),b[p.A100],rtol=2e-11,atol=1e-6)
        masks[d]={name:x[col].fillna(0).eq(1).to_numpy() for name,col,_ in FAMILIES}
        r=dict(date=d,hour_matched=int(d=='2021-07-25'),n_A200=na,n_Spre_total=int(q[q.date.eq(d)].in_Spre.sum()),n_Spre_outside_A200=outside,
            R_naive_frozen=float(frozen.loc[d,'R_naive']),R_online_frozen=float(frozen.loc[d,'R_online']),
            R_stable_frozen=float(frozen.loc[d,'R_stable']),R_pre_frozen=float(oldpre.loc[d,'R_pre']),
            device_bootstrap=N_BOOT,CI_scope='500paired A200 device-cluster weights shared across families/dates; observed memberships fixed; percentile95; excludes classification/selection uncertainty')
        draws=dict(date=d,draw=np.arange(N_BOOT))
        for name,_,col in FAMILIES:
            use=masks[d][name];num=weights[:,use]@n[use];den=weights[:,use]@b[use]
            boot=np.divide(num,den,out=np.full(N_BOOT,np.nan),where=den>0);lo,hi=ci(boot)
            r[col]=ratio(n[use],b[use]);r[col+'_ci_lo']=lo;r[col+'_ci_hi']=hi;r['n_'+name]=int(use.sum())
            r['observed_'+name]=int(n[use].sum());r['baseline_'+name]=float(b[use].sum());r['bootstrap_valid_'+name]=int(np.isfinite(boot).sum())
            r['n_missing_distance_'+name]=int((use&distance_missing).sum())
            r['baseline_share_missing_distance_'+name]=float(b[use&distance_missing].sum()/b[use].sum()) if b[use].sum()>0 else np.nan
            draws[col+'_draw']=boot
        rows.append(r);drawrows.append(pd.DataFrame(draws))
    daily=pd.DataFrame(rows);save_csv(daily,ROOT/'06_s_pre/T36_health_screened_v6.csv')
    save_csv(pd.concat(drawrows,ignore_index=True),ROOT/'01_internal/health_bootstrap_draws_v7.csv')
    original=ring(p.attr.dist_baiguan_km,five=True)
    counts={d:original[masks[d]['health']].value_counts().to_dict() for d in EVENT}
    mapping,labels,merges=merge_five(counts)
    orig=ring_tables(p,masks,dict(zip(FIVE,FIVE)),FIVE,'original_five')
    merged=ring_tables(p,masks,mapping,labels,'merged_if_population_lt10')
    save_csv(orig,ROOT/'06_s_pre/T36_rings_v6_orig.csv');save_csv(merged,ROOT/'06_s_pre/T36_rings_v6.csv')
    models=[]
    for d in ['2021-07-26','2021-07-27','2021-07-28']:
        n,b=p.vectors(d,matched=False);r=np.divide(n,b,out=np.full(p.n_dev,np.nan),where=b>0)
        model=fit_ols(p.attr,r,masks[d]['health'],d);model['sample']='R_health';model['n_selected_city']=int(masks[d]['health'].sum())
        model['n_not_in_OLS_complete_cases']=model.n_selected_city-model.n
        model['denominator_scope']='Health city subset; OLS additionally requires original coordinate/covariate complete cases'
        models.append(model)
    ols=pd.concat(models,ignore_index=True);save_csv(ols,ROOT/'06_s_pre/T36_ols_v6.csv')
    source=pd.concat([daily.assign(panel='daily'),orig.assign(panel='rings_original'),ols.assign(panel='OLS')],ignore_index=True,sort=False)
    source['interpretation']='Record-coverage/channel sensitivity; not fully independent hardware diagnosis or identified true traffic'
    save_csv(source,ROOT/'08_figures/fig_health_screened_v7_data.csv')
    v=orig[orig.date.eq('2021-07-26')].set_index('distance_ring').reindex(FIVE).R_health.to_numpy()
    rises=[FIVE[i]+' -> '+FIVE[i+1] for i in range(4) if np.isfinite(v[i:i+2]).all() and v[i+1]>v[i]]
    rho=float(daily.set_index('date').loc['2021-07-26','R_health'])
    acceptance=dict(R_health_0726=dict(value=rho,range=[.52,.60],met=bool(.52<=rho<=.60)),
        five_ring_gradient_0726=dict(ratios=v.tolist(),n_adjacent_increases=len(rises),adjacent_increases=rises,met=bool(len(rises)<=1) if np.isfinite(v).all() else None,scope='Original unmerged five health rings; point-estimate criterion'))
    checks.update(all9dates=daily.date.tolist()==EVENT,all3OLSdates=ols.date.nunique()==3,all500draws=N_BOOT==500,
        all_health_subsets_A200=all(not np.any(masks[d][name]&~p.A200) for d in EVENT for name,_,_ in FAMILIES),
        inputs_unchanged=p.unchanged())
    details=dict(acceptance=acceptance,ring_mapping=mapping,ring_merges=merges,Spre_outside_A200=outside,
        rows=dict(daily=len(daily),rings=len(merged),original_rings=len(orig),OLS=len(ols),figure_source=len(source)),input_sha256=p.input_hashes,
        cases_0726=daily[daily.date.eq('2021-07-26')].to_dict('records'),cases_0802=daily[daily.date.eq('2021-08-02')].to_dict('records'))
    return checks,details


def main(protocol,stage):
    start=now();tick=time.monotonic();gate=require_protocol(protocol);ih=sha(INTERPRET)
    hashes={str(p):sha(p) for p in [STATE_INPUT,PRE_INPUT,V1/'01_panels/device_attributes.csv',V6/'08_figures/fig_state_map_v6_data.csv']}
    q,checks,outside=make_states()
    if stage in ['state','all']:
        save_csv(q,STATE_OUTPUT);summary,failed=state_tables(q)
        checks['state_summary_closure']=summary.groupby('date').n_devices.sum().eq(q[q.in_A200.eq(1)].groupby('date').size()).all()
        checks['failed_breakdown_closure']=failed.groupby('date').n_failed_state.sum().eq(failed.groupby('date').n_failed_A1.first()).all()
        details=dict(rows=dict(internal=len(q),state_summary=len(summary),failed_breakdown=len(failed)),
            partial_day_by_date=q[q.in_A200.eq(1)].groupby('date').state.apply(lambda x:int(x.eq('partial_day').sum())).to_dict(),Spre_outside_A200=outside)
        write_json(ROOT/'00_env/device_state_execution_v7.json',dict(started=start,ended=now(),seconds=time.monotonic()-tick,status='complete' if all(checks.values()) else 'failed',checks=checks,details=details,protocol=gate,interpretation_sha256=ih,input_sha256=hashes,source_reads=False,key_reads=False))
    if stage in ['health','all']:
        hc,details=health_tables(q,outside);checks.update(hc)
        write_json(ROOT/'00_env/health_screen_execution_v7.json',dict(started=start,ended=now(),seconds=time.monotonic()-tick,status='complete' if all(checks.values()) else 'failed',checks=checks,details=details,protocol=gate,interpretation_sha256=ih,input_sha256=hashes,source_reads=False,key_reads=False,H1_H4_recomputed=False))
    checks['old_inputs_unchanged']=all(sha(p)==h for p,h in hashes.items())
    checks['protocol_unchanged']=gate['sha256']==sha(protocol);checks['interpretation_unchanged']=ih==sha(INTERPRET)
    write_json(ROOT/'00_env/health_integrity_v7.json',dict(ended=now(),all_passed=all(checks.values()),checks=checks,stage=stage))
    print(json.dumps(dict(stage=stage,all_passed=all(checks.values()),n_checks=len(checks),failed=[k for k,v in checks.items() if not v])))
    if not all(checks.values()):raise AssertionError('v7 health integrity failed')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--protocol',default=str(ROOT/'00_env/protocol_frozen_v7.json'));parser.add_argument('--stage',choices=['state','health','all'],default='all')
    args=parser.parse_args();main(args.protocol,args.stage)
