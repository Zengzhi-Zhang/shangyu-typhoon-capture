# -*- coding: utf-8 -*-
"""Observation status and two-source recovery, preserving every day and frozen denominator."""
from common_v1 import *
from scipy.stats import spearmanr
START=now()
def main():
    inputpaths=[ROOT/'01_panels'/f for f in ['device_hour.csv','device_attributes.csv','taxi_vehicle_day.csv']]
    inputpaths.append(ROOT/'01_panels/plate_day_summary.csv' if (ROOT/'01_panels/plate_day_summary.csv').exists() else REF/'results/plate_day_summary.csv')
    inputs_before=metadata(inputpaths)
    dh,attr,dd=load_panels()
    tx=pd.read_csv(ROOT/'01_panels/taxi_vehicle_day.csv',dtype={'sheet_date':str,'vehicle_hash':str})
    tx['date']=tx.sheet_date
    tx=tx[tx.n_parsed_time>0].copy()
    # Workbooks can contain sparse out-of-period sheets. Select the specified batch for each calendar period.
    tx=tx[((tx.batch=='GPS0601-0705')&(tx.date<='2021-07-05'))|((tx.batch=='GPS0706-0731')&(tx.date>='2021-07-06')&(tx.date<='2021-07-31'))].copy()
    tx['active']=((tx.n_valid_xy>=50)&(tx.dist_moving_km>=5)).astype(int)
    second=tx[tx.batch=='GPS0706-0731'].copy()
    taxiday=tx.groupby('date').agg(taxi_vehicles_reporting=('vehicle_hash','nunique'),taxi_vehicles_active=('active','sum'),taxi_km=('dist_moving_km','sum'),taxi_pts=('n_parsed_time','sum'),occupied=('n_occupied','sum'),taxi_batch=('batch','first'))
    taxiday['taxi_occ_share']=taxiday.occupied/taxiday.taxi_pts
    taximat={c:second.pivot_table(index='vehicle_hash',columns='date',values=c,aggfunc='sum',fill_value=0) for c in ['dist_moving_km','dist_km','active','n_parsed_time','n_occupied']}
    rng=np.random.default_rng(SEED)
    wt=rng.multinomial(len(taximat['active']),np.full(len(taximat['active']),1/len(taximat['active'])),size=200).astype(np.int16)
    nvalid=dh[dh.hour>=0]
    ah=nvalid.groupby(['date','hour']).agg(avi_all=('n','sum'),devices_reporting=('dev','nunique')).reindex(pd.MultiIndex.from_product([D_ALL,range(24)],names=['date','hour']),fill_value=0)
    stids=attr.index[attr.in_Sstar==1]
    ah['avi_Sstar']=nvalid[nvalid.dev.isin(stids)].groupby(['date','hour']).n.sum().reindex(ah.index,fill_value=0)
    for h in range(24):
        for c,tc in [('taxi_points',f'pts_h{h:02d}'),('taxi_moving_points',f'mov_h{h:02d}')]:
            ah.loc[(slice(None),h),c]=tx.groupby('date')[tc].sum().reindex(D_ALL).values
        ah.loc[(slice(None),h),'taxi_vehicles_moving']=tx[tx[f'mov_h{h:02d}']>0].groupby('date').vehicle_hash.nunique().reindex(D_ALL,fill_value=0).values
    hr=ah.reset_index()
    # Historical hourly totals come from the specified copied vehicle-day table, whose point counts are parsed-time counts.
    rows=[]
    for bname in BASELINES:
        rows=[]
        for di,d in enumerate(D_ALL):
            n,base=device_vectors(d,bname,True,dh,dd)
            ndaily=dd[d];bdaily=dd[refs(d,'B1')].mean(axis=1)
            on=attr.index[(attr.in_A100==1)&((ndaily/bdaily.replace(0,np.nan))>=.2)]
            row=dict(date=d,hour_matched=int(d=='2021-07-25'),n_A100=int(attr.in_A100.sum()),n_online=len(on),n_Sstar=len(stids),observation_partial=int(d in D_PARTIAL))
            for name,ix in [('R_naive',attr.index[attr.in_A100==1]),('R_online',on),('R_stable',stids)]:
                nn=n.reindex(ix);bb=base.reindex(ix);row[name]=nn.sum()/bb.sum() if bb.sum()>0 else np.nan
                lo,hi=boot_ratio(nn,bb,B=500,seed=SEED+di)
                row[name+'_ci_lo']=lo;row[name+'_ci_hi']=hi
            for name,col in [('R_taxi_km','dist_moving_km'),('R_taxi_active','active'),('R_taxi_pts','n_parsed_time'),('R_taxi_total_km_sensitivity','dist_km')]:
                val=lo=hi=np.nan
                if bname!='B3' and d in taximat[col].columns:
                    a=taximat[col][d].values.astype(float);bd=taximat[col][refs(d,B_TAXI)].mean(axis=1).values
                    if bd.sum()>0:
                        val=a.sum()/bd.sum();draw=(wt@a)/(wt@bd);lo,hi=np.quantile(draw,[.025,.975])
                row[name]=val;row[name+'_ci_lo']=lo;row[name+'_ci_hi']=hi
            if bname!='B3' and d in taxiday.index:
                row['taxi_occ_share']=taxiday.loc[d,'taxi_occ_share']
                td=taxiday.reindex(refs(d,B_TAXI));row['taxi_occ_share_ratio']=row['taxi_occ_share']/td.taxi_occ_share.mean() if taxiday.loc[d,'taxi_batch']=='GPS0706-0731' else np.nan
            else:row['taxi_occ_share']=row['taxi_occ_share_ratio']=np.nan
            rows.append(row)
        daily=pd.DataFrame(rows)
        suffix='' if bname=='B1' else '_'+bname
        save_csv(daily,ROOT/f'03_m2_two_sources/m2_daily_ratios{suffix}.csv')
    daily=pd.read_csv(ROOT/'03_m2_two_sources/m2_daily_ratios.csv')
    # Hourly baselines retain platform-interrupted hours as observation-status data; no behavioural interpretation.
    for i,r in hr.iterrows():
        b=hr[(hr.date.isin(refs(r.date,'B1')))&(hr.hour==r.hour)]
        bt=hr[(hr.date.isin(refs(r.date,B_TAXI)))&(hr.hour==r.hour)]
        hr.loc[i,'r_avi_Sstar']=r.avi_Sstar/b.avi_Sstar.mean() if b.avi_Sstar.mean()>0 else np.nan
        hr.loc[i,'r_taxi_moving']=r.taxi_moving_points/bt.taxi_moving_points.mean() if bt.taxi_moving_points.mean()>0 else np.nan
    hr['delta']=hr.r_taxi_moving-hr.r_avi_Sstar
    hr['avi_hour_available']=~((hr.date.isin(['2021-07-22','2021-07-23','2021-07-24']))|((hr.date=='2021-07-25')&(hr.hour<11)))
    cols=['date','hour','r_avi_Sstar','r_taxi_moving','delta','avi_hour_available']
    save_csv(hr[hr.date.isin(dates('2021-07-22','2021-07-28'))][cols],ROOT/'03_m2_two_sources/m2_hourly_ratios_0722_0728.csv')
    parts={'early':range(6,10),'daytime':range(10,16),'evening':range(16,20),'night':range(20,24)}
    partrows=[]
    for d in dates('2021-07-24','2021-07-28'):
        for part,hs in parts.items():
            # These hourly observation summaries deliberately show the blackout as recorded; daily 7/25 ratios are separately hour matched.
            rr=hr[(hr.date==d)&hr.hour.isin(hs)]
            b=hr[hr.date.isin(refs(d,'B1'))&hr.hour.isin(hs)]
            bt=hr[hr.date.isin(refs(d,B_TAXI))&hr.hour.isin(hs)]
            ba=b.groupby('date').avi_Sstar.sum().mean();bb=bt.groupby('date').taxi_moving_points.sum().mean()
            ra=rr.avi_Sstar.sum()/ba if ba>0 else np.nan;rt=rr.taxi_moving_points.sum()/bb if bb>0 else np.nan
            partrows.append(dict(date=d,daypart=part,r_avi=ra,r_taxi=rt,delta=rt-ra,avi_observed_hours=int(rr.avi_hour_available.sum()),n_hours=len(rr)))
    partsdf=pd.DataFrame(partrows);save_csv(partsdf,ROOT/'03_m2_two_sources/m2_daypart_summary.csv')
    hourly=hr[hr.date.isin(dates('2021-07-18','2021-07-28'))][['date','hour','avi_all','avi_Sstar','devices_reporting','taxi_points','taxi_moving_points','taxi_vehicles_moving']].copy()
    for c in ['taxi_points','taxi_moving_points']:hourly[c]=hourly[c].astype('Int64')
    for c in ['taxi_vehicles_moving']:hourly[c]=hourly[c].map(lambda v:'<10' if pd.notna(v) and float(v)<10 else str(int(v)) if pd.notna(v) else '')
    save_csv(hourly,ROOT/'02_m1_observation/m1_hourly_0718_0728.csv')
    if (ROOT/'01_panels/plate_day_summary.csv').exists():
        ps=pd.read_csv(ROOT/'01_panels/plate_day_summary.csv').set_index('date')
        plate_status='formal_rebuilt'
    elif '--allow-incomplete-plates' in __import__('sys').argv:
        ps=pd.read_csv(REF/'results/plate_day_summary.csv').set_index('date')
        ps['plates_on_stable']=np.nan
        plate_status='plates_all_reference; plates_Sstar_pending_raw_AVI'
    else:raise RuntimeError('Formal plate panel required; no pilot stable-plate substitution permitted.')
    coverage=[]
    for d in D_ALL:
        r=dict(date=d,dow=pd.Timestamp(d).dayofweek,devices_any=int((dd[d]>0).sum()),devices_ge1000=int((dd[d]>=1000).sum()),records=int(dd[d].sum()),unread_share=dh.loc[dh.date==d,'n_unread'].sum()/dd[d].sum(),plates_all=int(ps.loc[d,'plates']),plates_Sstar=int(ps.loc[d,'plates_on_stable']) if pd.notna(ps.loc[d,'plates_on_stable']) else np.nan,plate_panel_status=plate_status,hour_matched=int(d=='2021-07-25'),observation_partial=int(d in D_PARTIAL))
        for c in ['taxi_vehicles_reporting','taxi_vehicles_active','taxi_km','taxi_batch']:r[c]=taxiday.loc[d,c] if d in taxiday.index else None
        coverage.append(r)
    cov=pd.DataFrame(coverage)
    for c in ['plates_Sstar','taxi_vehicles_reporting','taxi_vehicles_active']:cov[c]=cov[c].astype('Int64')
    save_csv(cov,ROOT/'02_m1_observation/m1_daily_coverage.csv')
    dl=pd.read_csv(ROOT/'01_panels/device_dir_lane_day.csv')
    surv=dl[dl.date.isin(dates('2021-07-22','2021-07-24'))].dev.unique()
    # Zero-fill directions/lanes at surviving devices to disclose selective direction loss.
    keys=dl[dl.dev.isin(surv)][['dev','dir','lane']].drop_duplicates()
    survrows=[]
    for d in dates('2021-07-22','2021-07-24'):
        n=dl[dl.date==d].set_index(['dev','dir','lane']).n
        base=dl[dl.date.isin(refs(d))].groupby(['dev','dir','lane']).n.sum()/len(refs(d))
        for _,r in keys.iterrows():
            k=(r.dev,r['dir'],r.lane);bv=base.get(k,0);nv=n.get(k,0)
            survrows.append(dict(date=d,dev=r.dev,dir=r['dir'],lane=r.lane,n=int(nv),baseline=bv,ratio=nv/bv if bv>0 else np.nan,org=attr.loc[r.dev,'org']))
    save_csv(pd.DataFrame(survrows),ROOT/'02_m1_observation/m1_blackout_survivors.csv')
    city=hr.copy()
    for i,r in city.iterrows():
        b=city[(city.date.isin(refs(r.date)))&(city.hour==r.hour)].avi_all.mean()
        city.loc[i,'ratio_all']=r.avi_all/b if b>0 else np.nan
    candidates=city[(city.date>='2021-07-18')&(city.ratio_all<.01)]
    first=candidates.sort_values(['date','hour']).iloc[0]
    t0=pd.Timestamp(first.date)+pd.Timedelta(hours=int(first.hour))
    city['ts']=pd.to_datetime(city.date)+pd.to_timedelta(city.hour,unit='h')
    rec=city[(city.ts>t0)&(city.ratio_all>=.2)].sort_values('ts').iloc[0]
    outage=dict(start=t0.isoformat(),recovery=rec.ts.isoformat(),frozen_timeline_start='2021-07-21T23:00:00',frozen_timeline_recovery='2021-07-25T11:00:00',survivor_devices=len(surv),org_distribution=attr.loc[surv].org.value_counts(dropna=False).to_dict(),devices_reporting_at_recovery=int(rec.devices_reporting),devices_reporting_at_frozen_recovery=int(city[(city.date=='2021-07-25')&(city.hour==11)].devices_reporting.iloc[0]),threshold_start=.01,threshold_recovery=.2)
    write_json(ROOT/'02_m1_observation/m1_platform_outage_summary.json',outage)
    # Figures and the exact plotting data.
    plt=setup_plot()
    fdata=daily[daily.date>='2021-07-05'].copy()
    counts=pd.read_csv(ROOT/'06_m5_bias_correction/m5_failure_counts.csv') if (ROOT/'06_m5_bias_correction/m5_failure_counts.csv').exists() else None
    for i,r in fdata.iterrows():
        n,den,b,kind=failure_vectors(r.date,dh,dd)
        fdata.loc[i,'n_failed']=int(((n<.05*den)&(attr.in_A200==1)).sum())
    save_csv(fdata,ROOT/'08_figures/fig1_data.csv')
    fig,ax=plt.subplots(2,1,figsize=(12,7),sharex=True)
    xx=pd.to_datetime(fdata.date)
    for c,label,color in [('R_naive','全部有效设备',COLORS[2]),('R_stable','稳定设备',COLORS[0]),('R_taxi_km','出租车行驶里程',COLORS[1])]:ax[0].plot(xx,fdata[c],marker='o',label=label,color=color)
    for a in ax:
        a.axvspan(pd.Timestamp('2021-07-21 23:00'),pd.Timestamp('2021-07-25 11:00'),color='#aaaaaa',alpha=.18,label='AVI平台中断' if a is ax[0] else None)
        for ti,tt in enumerate(['2021-07-25 12:30','2021-07-26 09:30']):a.axvline(pd.Timestamp(tt),color='#555555',ls=':',lw=1,label='两次登陆' if a is ax[0] and ti==0 else None)
        a.grid(True)
    ax[0].axhline(1,color='#777777',lw=.7);ax[0].set_ylabel('同星期恢复比');ax[0].legend(ncol=2)
    ax[1].plot(xx,fdata.n_online,label='逐日在线 A100');ax[1].plot(xx,fdata.n_failed,label='失效 A200');ax[1].set_ylabel('设备数');ax[1].legend()
    fig.autofmt_xdate();fig.tight_layout();fig.savefig(ROOT/'08_figures/fig1_daily_series.png');plt.close(fig)
    data2=pd.concat([fdata.assign(panel='daily'),hr[hr.date=='2021-07-26'].assign(panel='hourly')],ignore_index=True)
    save_csv(data2,ROOT/'08_figures/fig2_data.csv')
    fig,axs=plt.subplots(3,1,figsize=(11,10))
    for c,label,color in [('R_stable','稳定卡口',COLORS[0]),('R_taxi_km','出租车里程',COLORS[1])]:
        axs[0].plot(xx,fdata[c],marker='o',label=label,color=color);axs[0].fill_between(xx,fdata[c+'_ci_lo'].astype(float),fdata[c+'_ci_hi'].astype(float),alpha=.15,color=color)
    sub=hr[hr.date=='2021-07-26']
    axs[1].plot(sub.hour,sub.r_avi_Sstar,marker='o',label='稳定卡口',color=COLORS[0]);axs[1].plot(sub.hour,sub.r_taxi_moving,marker='o',label='出租车移动点',color=COLORS[1])
    axs[2].bar(sub.hour,sub.delta,color=COLORS[2],label='出租车－卡口');axs[2].axhline(0,color='#555555',lw=.8)
    for a in axs:a.grid(True);a.legend();a.set_ylabel('恢复比' if a is not axs[2] else '比值差')
    axs[1].set_title('2021-07-26 同星期小时基线');axs[2].set_xlabel('小时');fig.autofmt_xdate();fig.tight_layout();fig.savefig(ROOT/'08_figures/fig2_two_sources.png');plt.close(fig)
    sens=[]
    for bname in BASELINES:
        suf='' if bname=='B1' else '_'+bname
        x=pd.read_csv(ROOT/f'03_m2_two_sources/m2_daily_ratios{suf}.csv')
        for _,r in x[x.date.isin(dates('2021-07-26','2021-07-28'))].iterrows():sens.append(dict(module='M2',baseline=bname,date=r.date,grp='all',metric='R_stable',value=r.R_stable))
    save_csv(pd.DataFrame(sens),ROOT/'07_m6_robustness/m6_baseline_sensitivity_m2.csv')
    checks=dict(outage=outage,km_definition='dist_moving_km; total dist_km retained as sensitivity',taxi_baseline=B_TAXI,taxi_B2_remains_frozen_B_TAXI=True,taxi_B3_not_applicable=True,bootstrap=dict(camera=500,taxi_vehicle=200),acceptance=dict(taxi_0722_0724={d:float(daily.set_index('date').loc[d,'R_taxi_km']) for d in dates('2021-07-22','2021-07-24')},R_stable_0726=float(daily.set_index('date').loc['2021-07-26','R_stable']),R_taxi_km_0726=float(daily.set_index('date').loc['2021-07-26','R_taxi_km']),daytime_delta_0726=float(partsdf[(partsdf.date=='2021-07-26')&(partsdf.daypart=='daytime')].delta.iloc[0])))
    write_json(ROOT/'00_env/m1_m2_checks.json',checks)
    inputs_after=metadata(inputpaths)
    if inputs_before!=inputs_after:raise RuntimeError('M1/M2 input metadata changed during execution.')
    checks.update(inputs_before=inputs_before,inputs_after=inputs_after,inputs_unchanged=True)
    stage_record('m1_m2',START,[str(x.relative_to(ROOT)) for dn in ['02_m1_observation','03_m2_two_sources'] for x in (ROOT/dn).glob('*')],checks)
    print('M1/M2 completed',json.dumps(checks['acceptance']),flush=True)
if __name__=='__main__':main()
