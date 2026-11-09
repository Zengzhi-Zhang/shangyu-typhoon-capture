# -*- coding: utf-8 -*-
"""I1: prespecified A200 states from frozen local panels only.

Run only after root freezes the whole protocol and verifies input fingerprints.
"""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[2]), str(_ReleasePath(__file__).resolve().parents[0])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from pathlib import Path
import argparse,time
import numpy as np
import pandas as pd
from spatial_helpers_v6 import (ROOT,V3,PANELS,SEED,B1,D_STATE,EVENT,STATE_ORDER,
    Panels,TRANS,INVERSE,now,sha,write_json,save_csv,require_protocol,refs)

INTERPRETATION=ROOT/'00_env/interpretation_spatial_v6.json'
INTERNAL_DATES=sorted(set(D_STATE+EVENT))
PUBLIC_ATTR=['dev_public','in_A100','in_A200','in_Sstar','base_B1','ring','org',
             'base_flow_quartile','gateway','road_level','dist_baiguan_km','elev_m','relief_300m']

def longest_run(zero):
    longest=run=0
    for value in zero:
        run=run+1 if value else 0;longest=max(longest,run)
    return longest

def stop_hour(hours,n,normal):
    for j,h in enumerate(hours):
        if h>=6 and j>0 and normal[:j].mean()>=.6 and np.all(n[j:]==0):return int(h)
    return np.nan

def load_channels(p):
    q=p.read(PANELS/'device_dir_lane_day.csv',usecols=['date','dev','dir','lane','n'],dtype={'dir':str,'lane':str})
    q[['dir','lane']]=q[['dir','lane']].fillna('missing')
    q=q[q.dev.isin(p.devs[p.A100])]
    return q.pivot_table(index=['dev','dir','lane'],columns='date',values='n',aggfunc='sum',fill_value=0).reindex(columns=list(p.day_index),fill_value=0)

def channel_signals(channels,date,devs):
    b=channels[refs(date)].mean(axis=1)
    eligible=b.ge(50);target=channels[date]
    cells=pd.DataFrame({'n_lanes':eligible.astype(int),'n_dead':(eligible&target.lt(.05*b)).astype(int),
                        'n_normal':(eligible&target.ge(.5*b)).astype(int)})
    out=cells.groupby(level='dev').sum().reindex(devs,fill_value=0).astype(int)
    out['mixed']=out.n_dead.ge(1)&out.n_normal.ge(1)
    return out

def classify_states(n,recording,mixed,ratios,spike,a200,date):
    """Ordered task-book first-match classification, including explicit NA handling."""
    mixed=np.asarray(mixed,bool)
    cond=[n==0,recording<=(2 if date=='2021-07-25' else 4),mixed,
          (spike==1)&(ratios>=.20),
          (ratios<.05)&(recording>=12)&~mixed&(spike==0),
          (ratios>=.05)&(ratios<.50)]
    state=np.select(cond,STATE_ORDER[:-1],default='normal').astype(object)
    state[~np.asarray(a200,bool)]='not_classified_outside_A200'
    return state

def build_day(p,channels,nbrs,date):
    s=p.a1(date);day=p.day_index[date];hours=np.arange(11,24) if date=='2021-07-25' else np.arange(24)
    bh=p.hour[:,[p.day_index[d] for d in refs(date)],:][:,:,hours].mean(axis=1)
    hn=p.hour[:,day,:][:,hours];un=p.unread[:,day,:][:,hours]
    normal=(hn>=.2*bh)&(bh>=5);recording=(hn>0).sum(axis=1)
    zero=(hn==0)&(bh>=5)
    n,b1=p.vectors(date);ratio_b1=np.divide(n,b1,out=np.full(p.n_dev,np.nan),where=b1>0)
    day_n=p.afternoon if date=='2021-07-25' else p.daily
    day_un=p.afternoon_unread if date=='2021-07-25' else p.daily_unread
    total_un=day_un[:,day];un_share=np.divide(total_un,n,out=np.full(p.n_dev,np.nan),where=n>=20)
    basen=day_n[:,[p.day_index[d] for d in refs(date)]]
    baseun=day_un[:,[p.day_index[d] for d in refs(date)]]
    bases=np.divide(baseun,basen,out=np.full(basen.shape,np.nan),where=basen>=20)
    valid=np.isfinite(bases);count=valid.sum(axis=1)
    unread_base=np.divide(np.nansum(bases,axis=1),count,out=np.full(p.n_dev,np.nan),where=count>0)
    un_valid=np.isfinite(un_share)&np.isfinite(unread_base)
    spike=np.full(p.n_dev,np.nan);spike[un_valid]=(un_share[un_valid]-unread_base[un_valid]>=.10).astype(int)
    lanes=channel_signals(channels,date,p.devs)
    neighbour=np.full(p.n_dev,np.nan);n_neighbour=np.zeros(p.n_dev,int)
    for i,js in nbrs.items():
        values=s['ratio'][js];values=values[np.isfinite(values)];n_neighbour[i]=len(values)
        if len(values):neighbour[i]=float(np.median(values))
    # Ordered first match. Missing recognition measurements do not prove normality.
    state=classify_states(n,recording,lanes.mixed.to_numpy(bool),s['ratio'],spike,p.A200,date)
    prefix=np.array([stop_hour(hours,hn[i],normal[i]) for i in range(p.n_dev)])
    row=p.attr[PUBLIC_ATTR+['lon','lat']].reset_index().copy()
    row['date']=date;row['n_day']=n.astype(int);row['ratio']=s['ratio'];row['ratio_A1']=s['ratio'];row['ratio_B1']=ratio_b1
    row['denominator_A1']=s['denom'];row['b_loo_A1']=s['b_loo'];row['baseline_B1']=b1
    row['A1_failed']=s['failed'].astype(int);row['state']=state
    row['normal_catchall_low_or_missing_ratio']=((state=='normal')&((s['ratio']<.05)|~np.isfinite(s['ratio']))).astype(int)
    row['n_unread']=total_un.astype(int);row['unread_share']=un_share;row['unread_base']=unread_base
    row['n_unassigned_hour_full_day']=p.unassigned_hour[:,day].astype(int)
    row['n_unread_unassigned_hour_full_day']=p.unassigned_unread[:,day].astype(int)
    row['unread_base_n_days']=count;row['unread_valid']=un_valid.astype(int);row['unread_spike']=spike
    row['normal_hours']=normal.sum(axis=1);row['hours_recording']=recording;row['hours_recording_24eq']=recording*24/len(hours)
    row['normal_hours_24eq']=normal.sum(axis=1)*24/len(hours);row['observed_hours']=len(hours)
    row['hours_baseline_ge5']=(bh>=5).sum(axis=1);row['longest_zero_run']=[longest_run(x) for x in zero];row['stop_hour']=prefix
    for c in ['n_lanes','n_dead','n_normal','mixed']:row[c]=lanes[c].to_numpy().astype(int)
    row['nbr_ratio_med']=neighbour;row['nbr_ratio_n']=n_neighbour
    row['hour_matched']=int(date=='2021-07-25');row['lane_hour_matched']=0;row['lane_baseline_scope']='full_day'
    row['A1_previous_date']=s['prev'];row['A1_baseline_pool']=s['baseline_pool'];row['A1_baseline_days']=';'.join(s['baseline_days'])
    row['A1_fallback_day']=int(s['daybad']);row['A1_fallback_device']=s['devicebad'].astype(int)
    row['denominator_source']=np.where(s['daybad'],'LOO_previous_ineligible',np.where(s['devicebad'],'LOO_previous_degraded','previous_week'))
    row['A1_source']='reconstructed_from_frozen_v3_A1_verified_counts'
    row['public_D_STATE']=int(date in D_STATE)
    return row.loc[p.A100].copy()

def summary_table(q):
    rows=[];failedrows=[]
    for date,x in q.groupby('date',sort=True):
        nt=len(x);nf=int(x.A1_failed.sum());weight=x.base_B1.sum()
        for state in STATE_ORDER:
            g=x[x.state.eq(state)];ng=len(g);nfs=int(g.A1_failed.sum())
            orgs=g.org.fillna('missing').value_counts()
            rows.append(dict(date=date,state=state,n_devices=ng,n_A200=nt,share_A200=ng/nt,
                n_A1_failed_in_state=nfs,n_A1_failed=nf,share_A1_failed=nfs/nf if nf else np.nan,
                baseline_flow=float(g.base_B1.sum()),baseline_flow_share=float(g.base_B1.sum()/weight) if weight else np.nan,
                dist_baiguan_median_km=float(g.dist_baiguan_km.median()) if g.dist_baiguan_km.notna().any() else np.nan,
                n_devices_with_distance=int(g.dist_baiguan_km.notna().sum()),org_max_share=float(orgs.iloc[0]/ng) if ng else np.nan,
                org_max_category=str(orgs.index[0]) if ng else '',weight_definition='base_B1 / all A200 base_B1'))
            failedrows.append(dict(date=date,state=state,n_failed_state=nfs,n_failed_A1=nf,share_failed=nfs/nf if nf else np.nan))
    return pd.DataFrame(rows),pd.DataFrame(failedrows)

def main(protocol):
    start=now();t=time.monotonic();gate=require_protocol(protocol);interpret_hash=sha(INTERPRETATION)
    p=Panels();channels=load_channels(p);audit=p.a1_audit(INTERNAL_DATES)
    neighbours=p.neighbour_indices();q=pd.concat([build_day(p,channels,neighbours,d) for d in INTERNAL_DATES],ignore_index=True)
    save_csv(q,ROOT/'01_internal/device_state_internal_v6.csv')
    public=q[q.in_A200.eq(1)&q.public_D_STATE.eq(1)].drop(columns=['dev','lon','lat']).rename(columns={'dev_public':'dev'})
    public=public.sort_values(['date','dev']).reset_index(drop=True)
    save_csv(public,ROOT/'02_device_state/device_state_v6.csv')
    summary,failed=summary_table(public)
    save_csv(summary,ROOT/'02_device_state/T27_state_summary.csv');save_csv(failed,ROOT/'02_device_state/T27_failed_breakdown.csv')
    maprows=q[q.date.eq('2021-07-26')&q.in_A200.eq(1)&q.lon.notna()&q.lat.notna()].sort_values('dev_public')
    xy=np.column_stack(TRANS.transform(maprows.lon,maprows.lat));rng=np.random.default_rng(SEED)
    jitter=xy+rng.uniform(-200,200,size=xy.shape);lon,lat=INVERSE.transform(jitter[:,0],jitter[:,1])
    mp=maprows[['dev_public','date','state','A1_failed','in_Sstar','ring']].rename(columns={'dev_public':'dev'}).copy()
    mp['plot_lon']=np.round(lon,2);mp['plot_lat']=np.round(lat,2)
    mp['coordinate_note']='independent uniform +/-200m UTM jitter; rounded0.01degree'
    save_csv(mp,ROOT/'08_figures/fig_state_map_v6_data.csv',coords=True)
    storm=public[public.date.eq('2021-07-26')];ff=storm[storm.A1_failed.eq(1)]
    supported=ff.state.isin(['zero','offline','partial_channel']);share=float(supported.mean()) if len(ff) else np.nan
    low=storm.loc[storm.state.eq('low_all_channels'),'nbr_ratio_med'].dropna();off=storm.loc[storm.state.eq('offline'),'nbr_ratio_med'].dropna()
    comparable=bool(len(low) and len(off));neighbour_met=bool(low.median()<off.median()) if comparable else None
    acceptance=dict(failed_structural_fraction=dict(numerator=int(supported.sum()),denominator=len(ff),estimate=share,threshold=.60,met=share>=.60),
        neighbour_median_order=dict(low_n=len(low),offline_n=len(off),low_median=float(low.median()) if len(low) else np.nan,
            offline_median=float(off.median()) if len(off) else np.nan,met=neighbour_met,status='evaluated' if comparable else 'not_evaluable'))
    checks={**p.checks,'all_A1_counts_equal_v3':all(r['exact'] for r in audit),'public_exact_A200_by_10dates':len(public)==int(p.A200.sum())*len(D_STATE),
        'public_device_date_unique':not public.duplicated(['dev','date']).any(),'state_totals_equal_A200':summary.groupby('date').n_devices.sum().eq(p.A200.sum()).all(),
        'failed_totals_equal_A1':failed.groupby('date').n_failed_state.sum().eq(failed.groupby('date').n_failed_A1.first()).all(),
        'only_A200_classified':q.loc[q.in_A200.eq(0),'state'].eq('not_classified_outside_A200').all(),
        'published_coordinates_2dp':np.allclose(mp.plot_lon,mp.plot_lon.round(2)) and np.allclose(mp.plot_lat,mp.plot_lat.round(2)),
        'inputs_unchanged':p.unchanged(),'frozen_protocol_unchanged':gate['sha256']==sha(protocol),'interpretation_unchanged':interpret_hash==sha(INTERPRETATION)}
    write_json(ROOT/'00_env/device_state_A1_audit_v6.json',dict(rows=audit,all_equal=True))
    write_json(ROOT/'00_env/device_state_acceptance_v6.json',acceptance)
    record=dict(started=start,ended=now(),seconds=time.monotonic()-t,seed=SEED,status='complete' if all(checks.values()) else 'failed',
        command=_release_path('path_020')+str(protocol),
        protocol=gate,interpretation_sha256=interpret_hash,input_sha256=p.input_hashes,checks=checks,acceptance=acceptance,
        rows=dict(internal=len(q),public=len(public),state_summary=len(summary),failed_breakdown=len(failed),map=len(mp)),
        raw_source_accessed=False,key_accessed=False,H1_H4_recomputed=False,
        notes=['States use independent hourly/channel/recognition signals and explicit daily ratio thresholds; they do not establish true device health.',
               'July25 channel diagnostics are full-day because existing lane panel has no hour dimension.',
               'Only A200 classified; A100 outside A200 retained internally for downstream ratio/attribute joins.'])
    write_json(ROOT/'00_env/device_state_execution_v6.json',record)
    print(__import__('json').dumps(dict(status=record['status'],rows=record['rows'],acceptance=acceptance),ensure_ascii=False))
    if not all(checks.values()):raise AssertionError('Device-state integrity check failed')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--protocol',default=str(ROOT/'00_env/protocol_frozen_v6.json'))
    main(parser.parse_args().protocol)
