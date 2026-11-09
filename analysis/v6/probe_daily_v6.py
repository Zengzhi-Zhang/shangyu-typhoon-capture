# -*- coding: utf-8 -*-
"""Vehicle-paired taxi probe, shared 200-draw bootstrap; only aggregates public."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[2]), str(_ReleasePath(__file__).resolve().parents[0])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from pathlib import Path
from datetime import datetime,timezone,timedelta
import json,time,sys
import numpy as np,pandas as pd
R=Path(_release_path('project_root'));O=R/'formal_v6';I=O/'01_internal';P=O/'03_taxi_probe';SEED=20261005
RINGS=['0-2','2-4','4-7','7-12','12+']
DATES=pd.date_range('2021-07-06','2021-08-02').strftime('%Y-%m-%d').tolist()
B=[d for d in pd.date_range('2021-07-06','2021-07-21').strftime('%Y-%m-%d') if d not in ['2021-07-08','2021-07-10']]
def safe(n,d):
    n,d=np.asarray(n,float),np.asarray(d,float)
    return np.divide(n,d,out=np.full(np.broadcast(n,d).shape,np.nan),where=d>0)
def interval(a):
    a=np.asarray(a);a=a[np.isfinite(a)]
    return np.quantile(a,[.025,.975]) if len(a) else [np.nan,np.nan]
def main():
    start=time.perf_counter();stamp=datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
    h=json.loads((O/'00_env/hash_check_v6.json').read_text(encoding='utf-8'))
    if h['S1_triggered']:raise RuntimeError('S1 prevents probe ratios')
    ph=(I/'taxi_probe_ph_v6.txt').read_text(encoding='utf-8').splitlines();n=len(ph)
    gps=pd.read_csv(I/'taxi_vehicle_day_v6.csv',dtype={'vehicle_ph':str,'date':str})
    gps=gps.rename(columns={'vehicle_ph':'ph'});plate=pd.read_parquet(I/'taxi_plate_day_v6.parquet')
    assert len(ph)==290 and len(set(ph))==290,'Probe dimension mismatch'
    assert not gps.duplicated(['ph','date']).any(),'Duplicate GPS vehicle-day'
    assert not plate.duplicated(['ph','date']).any(),'Duplicate AVI vehicle-day'
    assert set(gps.ph).issubset(set(ph)) and set(plate.ph).issubset(set(ph)),'Identifier-set mismatch'
    closures={}
    for label,prefix,total in [('total_ring','km_total_ring_','dist_km'),('moving_ring','km_ring_','dist_moving_km'),('moving_h11_ring','km_moving_ring_h11_','km_moving_from_11h')]:
        diff=gps[[prefix+r for r in RINGS]].sum(axis=1)-gps[total]
        closures[label]=float(diff.abs().max())
        assert closures[label]<.0001,'GPS ring kilometre closure mismatch'
    avi=pd.read_parquet(I/'taxi_avi_records_v6.parquet');attrs=pd.read_csv(R/'01_panels/device_attributes.csv').set_index('dev')
    stable=set(attrs.index[attrs.in_Sstar.eq(1)]);avi['stable']=avi.dev.isin(stable).astype(int)
    a11=avi[avi.sec_of_day.ge(39600)&avi.sec_of_day.lt(86400)].groupby(['ph','date']).agg(rec_all_h11=('ph','size'),rec_stable_h11=('stable','sum')).reset_index()
    joined=pd.MultiIndex.from_product([ph,DATES],names=['ph','date']).to_frame(index=False).merge(gps,on=['ph','date'],how='left').merge(plate[['ph','date','n','n_stable','n_gw']],on=['ph','date'],how='left').merge(a11,on=['ph','date'],how='left')
    for c in ['n','n_stable','n_gw','rec_all_h11','rec_stable_h11']:joined[c]=joined[c].fillna(0)
    joined.to_parquet(I/'taxi_probe_joined_v6.parquet',index=False)
    weights=np.random.default_rng(SEED).multinomial(n,np.full(n,1/n),size=200)
    gps_dates=set(gps.date)
    def mat(col):return joined.pivot(index='ph',columns='date',values=col).reindex(index=ph,columns=DATES).fillna(0).to_numpy(float)
    km=mat('dist_km');km11=mat('km_from_11h');allrec=mat('n');stable_rec=mat('n_stable');rec11=mat('rec_all_h11');st11=mat('rec_stable_h11')
    allGPS=set(gps.loc[gps.dist_km.notna(),'date'])
    lookup={d:i for i,d in enumerate(DATES)}
    frozen=pd.read_csv(R/'03_m2_two_sources/m2_daily_ratios.csv').set_index('date')
    daily=[];dist=[]
    def norm(rec,kms,d):
        ix=lookup[d];refs=[lookup[x] for x in B if pd.Timestamp(x).dayofweek==pd.Timestamp(d).dayofweek]
        cp=safe(rec.sum(axis=0),kms.sum(axis=0));cpb=safe(weights@rec,weights@kms)
        denom=np.mean(cp[refs]);drawden=np.mean(cpb[:,refs],axis=1)
        c=float(safe(cp[ix],denom));draws=safe(cpb[:,ix],drawden);lo,hi=interval(draws)
        status='complete' if np.isfinite(c) else 'NA_zero_or_missing_target_or_baseline_km'
        return dict(c=c,lo=lo,hi=hi,cpk=float(cp[ix]),base_cpk=float(denom),baseline_dates=';'.join(DATES[i] for i in refs),bootstrap_valid=int(np.isfinite(draws).sum()),denominator_status=status)
    for d in DATES:
        ix=lookup[d];hm=d=='2021-07-25';aa=rec11 if hm else allrec;ss=st11 if hm else stable_rec;kk=km11 if hm else km
        row=dict(date=d,hour_matched=int(hm),n_taxi_seen=int((allrec[:,ix]>0).sum()),rec_all_full_day=int(allrec[:,ix].sum()),rec_stable_full_day=int(stable_rec[:,ix].sum()),n_probe=290,GPS_available=int(d in allGPS),baseline='B_PROBE',R_taxi_km_scope='frozen full-day B_TAXI')
        if d in allGPS:
            a=norm(aa,kk,d);s=norm(ss,kk,d)
            no_km=(kk[:,ix]<=0)&(aa[:,ix]>0)
            row.update(km=float(kk[:,ix].sum()),rec_all=int(aa[:,ix].sum()),rec_stable=int(ss[:,ix].sum()),c_all=a['c'],c_all_lo=a['lo'],c_all_hi=a['hi'],c_stable=s['c'],c_stable_lo=s['lo'],c_stable_hi=s['hi'],cpk_all=a['cpk'],cpk_stable=s['cpk'],base_cpk_all=a['base_cpk'],base_cpk_stable=s['base_cpk'],baseline_dates=a['baseline_dates'],n_taxi_with_GPS_km=int((kk[:,ix]>0).sum()),n_seen_without_positive_GPS_km=int(no_km.sum()),rec_without_positive_GPS_km=int(aa[no_km,ix].sum()),rec_without_positive_GPS_km_share=float(safe(aa[no_km,ix].sum(),aa[:,ix].sum())),bootstrap_valid_all=a['bootstrap_valid'],bootstrap_valid_stable=s['bootstrap_valid'],status=a['denominator_status'])
            ratios=safe(ss[:,ix],kk[:,ix]);finite=ratios[np.isfinite(ratios)]
            q=np.quantile(finite,[0,.1,.25,.5,.75,.9,1]) if len(finite) else np.full(7,np.nan)
            dist.append(dict(date=d,n_vehicle_days=len(finite),cpk_stable_min=q[0],cpk_stable_p10=q[1],cpk_stable_p25=q[2],cpk_stable_p50=q[3],cpk_stable_p75=q[4],cpk_stable_p90=q[5],cpk_stable_max=q[6],cpk_stable_IQR=q[4]-q[2],hour_matched=int(hm)))
        else:row.update(status='NA_no_GPS',km=np.nan,rec_all=int(aa[:,ix].sum()),rec_stable=int(ss[:,ix].sum()),c_all=np.nan,c_stable=np.nan)
        if d in frozen.index:
            for c in ['R_naive','R_online','R_stable','R_taxi_km']:row[c]=frozen.loc[d,c]
            row['R_naive_over_R_taxi_km']=float(safe(row['R_naive'],row['R_taxi_km']));row['R_stable_over_R_taxi_km']=float(safe(row['R_stable'],row['R_taxi_km']))
        daily.append(row)
    out=pd.DataFrame(daily)
    out.to_csv(I/'T28_probe_daily_internal_v6.csv',index=False,encoding='utf-8-sig',float_format='%.12g')
    public=out.copy()
    for field in ['n_taxi_seen','n_taxi_with_GPS_km','n_seen_without_positive_GPS_km']:
        public[field]=public[field].map(lambda v:'NA' if pd.isna(v) else '<10' if v<10 else str(int(v)))
    public.to_csv(P/'T28_probe_daily_v6.csv',index=False,encoding='utf-8-sig',float_format='%.4f')
    distribution=pd.DataFrame(dist)
    distribution['n_vehicle_days']=distribution['n_vehicle_days'].map(lambda v:'<10' if v<10 else v)
    distribution.to_csv(P/'T28_probe_vehicle_distribution_v6.csv',index=False,encoding='utf-8-sig',float_format='%.4f')
    # Ring AVI assignment uses geolocated camera ring. GPS distance uses segment
    # start-point ring; capture matching success does not determine record count.
    record_path=I/'taxi_ring_records_v6.csv';exact=record_path.exists();ringrows=[]
    rr=pd.read_csv(record_path,dtype={'ph':str}) if exact else None
    if exact:assert not rr.duplicated(['ph','date','ring']).any(),'Duplicate ring record key'
    if exact:
        closure=[]
        for d in DATES:
            hm=d=='2021-07-25';ix=lookup[d];field='rec_stable_h11' if hm else 'rec_stable';q=rr[rr.date.eq(d)]
            known=float(q.loc[q.ring.isin(RINGS),field].sum());unknown=float(q.loc[~q.ring.isin(RINGS),field].sum());network=float((st11 if hm else stable_rec)[:,ix].sum())
            assert abs(known+unknown-network)<.01,'Ring record closure mismatch'
            closure.append(dict(date=d,rec_stable_network=int(network),rec_stable_known_ring=int(known),rec_stable_unknown_ring=int(unknown),known_ring_share=float(safe(known,network)),closure_difference=int(known+unknown-network),hour_matched=int(hm),scope='approx0 means exact assignment where ring known; unknown ring retained in network total'))
        pd.DataFrame(closure).to_csv(P/'T28_ring_coverage_v6.csv',index=False,encoding='utf-8-sig',float_format='%.4f')
    for ring in RINGS:
        totalcol='km_total_ring_'+ring;hcol='km_ring_h11_'+ring
        movingcol='km_ring_'+ring;movinghcol='km_moving_ring_h11_'+ring
        if any(col not in joined for col in [totalcol,hcol,movingcol,movinghcol]):raise RuntimeError('Missing total or moving ring distance schema')
        kr=mat(movingcol);kr11=mat(movinghcol);krtotal=mat(totalcol);krtotal11=mat(hcol)
        if exact:
            q=rr[rr.ring.eq(ring)]
            def rm(col):return q.pivot_table(index='ph',columns='date',values=col,aggfunc='sum',fill_value=0).reindex(index=ph,columns=DATES,fill_value=0).fillna(0).to_numpy(float)
            sr=rm('rec_stable');sr11=rm('rec_stable_h11')
        else:
            moving_total=mat('dist_moving_km');moving_total11=sum(mat('km_moving_ring_h11_'+ringname) for ringname in RINGS)
            sr=stable_rec*safe(kr,moving_total);sr11=st11*safe(kr11,moving_total11)
            sr=np.nan_to_num(sr);sr11=np.nan_to_num(sr11)
        for d in DATES:
            ix=lookup[d];hm=d=='2021-07-25';k=kr11 if hm else kr;kt=krtotal11 if hm else krtotal;r=sr11 if hm else sr
            row=dict(date=d,ring=ring,approx=int(not exact),hour_matched=int(hm),km_ring_moving=float(k[:,ix].sum()) if d in allGPS else np.nan,km_ring_total=float(kt[:,ix].sum()) if d in allGPS else np.nan,rec_stable_ring=int(r[:,ix].sum()) if exact else float(r[:,ix].sum()),capture_proxy='normalised taxi records per moving GPS kilometre as task km_ring; not probability')
            if d in allGPS:
                a=norm(r,k,d);row.update(cpk_stable_ring=a['cpk'],c_stable_ring=a['c'],c_stable_ring_lo=a['lo'],c_stable_ring_hi=a['hi'],baseline_dates=a['baseline_dates'],bootstrap_valid=a['bootstrap_valid'],status=a['denominator_status'] if exact else 'approximate_distance_share_allocation')
                alt=norm(r,kt,d);row.update(c_stable_ring_total_km_supplement=alt['c'],c_stable_ring_total_km_supplement_lo=alt['lo'],c_stable_ring_total_km_supplement_hi=alt['hi'],cpk_stable_ring_total_km_supplement=alt['cpk'])
            else:row.update(cpk_stable_ring=np.nan,c_stable_ring=np.nan,status='NA_no_GPS')
            ringrows.append(row)
    pd.DataFrame(ringrows).to_csv(I/'T28_probe_by_ring_internal_v6.csv',index=False,encoding='utf-8-sig',float_format='%.12g')
    pd.DataFrame(ringrows).to_csv(P/'T28_probe_by_ring_v6.csv',index=False,encoding='utf-8-sig',float_format='%.4f')
    d26=out.set_index('date').loc['2021-07-26'];refgap=-pd.read_csv(R/'formal_v3/06_m5_bias_correction/m5_visible_bias_v3.csv').set_index('date').loc['2021-07-26','delta_naive']
    checks=dict(hash_ge250=h['acceptance_ge250'],c_stable_0726_0728_in_range={d:bool(.85<=out.set_index('date').loc[d,'c_stable']<=1.1) for d in ['2021-07-26','2021-07-27','2021-07-28']},c_all_upper_below1=bool(d26.c_all_hi<1),capture_deficit_to_visible_gap=float((1-d26.c_all)/refgap),same_order_half_to_twice=bool(.5<=(1-d26.c_all)/refgap<=2))
    report=dict(start=stamp,elapsed_seconds=time.perf_counter()-start,rows=len(out),ring_rows=len(ringrows),bootstrap=200,shared_vehicle_weights=True,ring_approx=int(not exact),GPS_ring_km_max_closure_errors=closures,acceptance=checks,august1_2='NA_no_GPS',I2_estimator_scope='per-km capture intensity may vary with taxi routing and GPS coverage; network denominator total km, ring denominator moving km as specified; this is not an unconfounded all-traffic detection probability')
    (O/'00_env/probe_daily_execution_v6.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(c_all_0726=d26.c_all,c_stable_0726=d26.c_stable,acceptance=checks,seconds=report['elapsed_seconds'])),flush=True)
if __name__=='__main__':main()
