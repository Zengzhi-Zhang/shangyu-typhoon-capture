# -*- coding: utf-8 -*-
"""I5 assumption-conditional recovery scenarios; not truth estimation."""
import argparse,json
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from bias_common_v6 import ROOT,V3,SEED,N_BOOT,EVENT,Stage,Panels,ratio,ci

def neighbor_median(p,r,online,targets):
    donors=np.flatnonzero(online&np.isfinite(r));good=donors[p.coord[donors]];tree=cKDTree(p.xy[good]) if len(good) else None
    result=np.full(len(r),np.nan);nglobal=np.zeros(len(r),bool);ndonor=np.zeros(len(r),int)
    for target in np.flatnonzero(targets):
        others=donors[donors!=target]
        if not len(others):continue
        if tree is not None and p.coord[target]:
            candidates=np.atleast_1d(tree.query(p.xy[target],k=min(8,len(good)))[1]);selected=good[candidates];selected=selected[selected!=target][:6]
            if len(selected):result[target]=np.median(r[selected]);ndonor[target]=len(selected);continue
        result[target]=np.median(r[others]);nglobal[target]=True;ndonor[target]=len(others)
    return result,nglobal,ndonor
def load_capture(stage,path):
    if path is None:return None,'not_available'
    if path=='auto':
        internal=ROOT/'01_internal/T28_probe_by_ring_internal_v6.csv'
        path=internal if internal.exists() else ROOT/'03_taxi_probe/T28_probe_by_ring_v6.csv'
    if not __import__('pathlib').Path(path).exists():return None,'not_available'
    cap=stage.read(path)
    if 'c_stable_ring' not in cap:raise ValueError('I5 requires explicit c_stable_ring relative same-weekday baseline')
    ring='ring' if 'ring' in cap else 'distance_ring'
    if ring not in cap or 'approx' not in cap:raise ValueError('Capture interface requires ring/distance_ring and approx')
    cap=cap.rename(columns={ring:'ring'}).copy();cap['c_stable_ring']=pd.to_numeric(cap.c_stable_ring,errors='coerce')
    good=pd.to_numeric(cap.approx,errors='coerce').eq(0)&cap.c_stable_ring.gt(0)&np.isfinite(cap.c_stable_ring)
    if cap.duplicated(['date','ring']).any():raise ValueError('Capture ring interface not unique date/ring')
    cap['usable']=good
    return cap,'I2_exact_ring_moving_km_relative_weekday_baseline_proxy'
def capture_context(stage):
    path=ROOT/'03_taxi_probe/T29_calibration_v6.json'
    base=dict(mid_proxy_distance_scope='Stable-camera taxi records per moving ring kilometre, relative to matched same-weekday baseline; network I2 uses total kilometres',
        mid_proxy_claim_scope='Descriptive assumption-conditional sensitivity only; not a capture probability or validated I3 camera-cap estimate')
    if not path.exists():
        return {**base,'mid_proxy_calibration_S2':None,'mid_proxy_calibration_S3':None,'mid_proxy_calibration_status':'not_available','mid_proxy_coordinate_method':'not_available',
            'mid_proxy_spatial_limitation':'Coordinate calibration status unavailable; spatial ring alignment has not been validated'}
    stat=path.stat();stage.inputs[str(path)]=dict(size=stat.st_size,mtime_ns=stat.st_mtime_ns)
    context=json.loads(path.read_text(encoding='utf-8-sig'));s2=context.get('S2');s3=context.get('S3')
    warnings=[]
    if s2:warnings.append('S2 coordinate calibration failed: GPS-camera alignment and ring assignment remain uncertain')
    if s3:warnings.append('S3 control capture validation failed: I3 camera cap cannot enter judgement')
    limitation=('; '.join(warnings)+'; I3 cap is report-only and never enters this formula' if warnings else
        'Ring alignment remains conditional on the chosen coordinate method, GPS coverage and taxi routing; I3 cap never enters this formula')
    return {**base,'mid_proxy_calibration_S2':s2,'mid_proxy_calibration_S3':s3,'mid_proxy_calibration_status':context.get('calibration_status','not_available'),'mid_proxy_coordinate_method':context.get('selected_method','not_available'),
        'mid_proxy_spatial_limitation':limitation}
def run(protocol,capture='auto'):
    st=Stage('bounds',protocol);p=Panels(st);states=st.read(ROOT/'01_internal/device_state_internal_v6.csv')
    key='dev_public' if 'dev_public' in states else 'dev';states[key]=states[key].astype(int)
    if states.duplicated(['date',key]).any():raise ValueError('Internal states must be unique date/device')
    state_lookup=states.set_index(['date',key]).state
    cap,capsource=load_capture(st,capture);proxycontext=capture_context(st);pre=st.read(ROOT/'06_s_pre/T32_s_pre_v6.csv').set_index('date')
    old=st.read(V3/'06_m5_bias_correction/m5_visible_bias_v3.csv').set_index('date')
    active=np.flatnonzero(p.A100);weights=np.random.default_rng(SEED).multinomial(len(active),np.full(len(active),1/len(active)),size=N_BOOT)
    records=[];deviceframes=[];bootframes=[]
    for date in EVENT:
        n,b,r=p.vectors(date);a1,den=p.a1(date);U=p.A100&~p.Sstar&(a1<.5);online=p.online[date]
        check_state=states[states.date.eq(date)].set_index(key).reindex(p.public[active])
        st.checks['I1_all_A100_rows_present:'+date]=bool(check_state.state.notna().all())
        ratio_col='ratio_A1' if 'ratio_A1' in check_state else 'ratio'
        st.checks['I1_A1_ratios_match:'+date]=bool(np.allclose(pd.to_numeric(check_state[ratio_col],errors='coerce'),a1[active],equal_nan=True,atol=1e-10,rtol=1e-10))
        st.checks['I1_observed_records_match:'+date]=bool(np.array_equal(check_state.n_day.to_numpy(float),n[active]))
        state=np.array([state_lookup.get((date,int(d)),'not_classified') for d in p.public],object)
        med,globalfb,ndonor=neighbor_median(p,r,online,U);lowall=U&(state=='low_all_channels');upper=r.copy();upper[U]=np.minimum(1.1,med[U]);upper[lowall]=np.minimum(1.1,.5*med[lowall])
        mid=r.copy();capvalue=np.full(len(r),np.nan);capvalid=np.zeros(len(r),bool)
        if cap is not None:
            rows=cap[cap.date.eq(date)].set_index('ring')
            for ring in np.unique(p.ring5[U]):
                target=U&(p.ring5==ring)
                if ring in rows.index and bool(rows.loc[ring,'usable']):
                    # July25 must use a matched I2 proxy, never an all-day substitute.
                    matched=(date!='2021-07-25') or ('hour_matched' in rows and pd.to_numeric(rows.loc[ring,'hour_matched'],errors='coerce')==1)
                    if matched:capvalue[target]=float(rows.loc[ring,'c_stable_ring']);capvalid[target]=True
        mid[U]=np.divide(r[U],capvalue[U],out=np.full(int(U.sum()),np.nan),where=capvalid[U])
        middone=bool((~U|capvalid).all());upperdone=bool(np.isfinite(upper[U]).all())
        uppern=n.copy();midn=n.copy();uppern[U]=b[U]*upper[U];midn[U]=b[U]*mid[U]
        row=dict(date=date,hour_matched=int(date=='2021-07-25'),n_A100=int(p.A100.sum()),n_U=int(U.sum()),n_U_low_all_channels=int(lowall.sum()),n_U_not_classified=int((U&np.char.startswith(state.astype(str),'not_classified')).sum()),
            n_U_no_neighbor=int((U&~np.isfinite(med)).sum()),n_U_global_neighbor_fallback=int((U&globalfb).sum()),n_U_cap_proxy_missing=int((U&~capvalid).sum()),
            cap_proxy_coverage=float(capvalid[U].mean()) if U.any() else 1.,R_lower=ratio(n[p.A100],b[p.A100]),R_upper=ratio(uppern[p.A100],b[p.A100]) if upperdone else np.nan,
            R_mid=ratio(midn[p.A100],b[p.A100]) if middone else np.nan,mid_available=middone,upper_available=upperdone,
            R_naive=float(old.loc[date,'R_naive']),R_online=float(old.loc[date,'R_online']),R_stable=float(old.loc[date,'R_stable']),R_pre=float(pre.loc[date,'R_pre']),
            mid_proxy_source=capsource,**proxycontext,interval_scope='500 paired A100 device clusters; states/U/neighbours/ring proxy fixed; taxi-proxy and set-selection uncertainty excluded',
            scenario_scope='Assumption-conditional scenarios; literal upper formula need not order every device or contain all comparison estimators')
        for estimator in ['R_naive','R_online','R_stable']:
            for end in ['lo','hi']:row[estimator+'_ci_'+end]=float(old.loc[date,estimator+'_ci_'+end])
        for end in ['lo','hi']:row['R_pre_ci_'+end]=float(pre.loc[date,'R_pre_ci_'+end])
        series={'R_lower':n,'R_upper':uppern if upperdone else np.full(len(r),np.nan),'R_mid':midn if middone else np.full(len(r),np.nan)}
        denboot=weights@b[active]
        for label,values in series.items():
            draw=(weights@values[active])/denboot;lo,hi=ci(draw);row[label+'_ci_lo']=lo;row[label+'_ci_hi']=hi
            bootframes.append(pd.DataFrame(dict(date=date,rep=np.arange(1,N_BOOT+1),scenario=label,estimate=draw)))
        row['bound_width']=row['R_upper']-row['R_lower'];row['lower_equals_naive_4dp']=abs(row['R_lower']-row['R_naive'])<=.000051
        row['upper_ge_lower']=bool(row['R_upper']>=row['R_lower']) if upperdone else False
        row['stable_inside_bounds']=bool(row['R_lower']<=row['R_stable']<=row['R_upper']) if upperdone else False
        row['n_U_upper_below_observed']=int((U&np.isfinite(upper)&(upper<r)).sum())
        records.append(row)
        deviceframes.append(pd.DataFrame(dict(date=date,dev_public=p.public[active],in_Sstar=p.Sstar[active],in_online=online[active],U=U[active],state=state[active],observed_records=n[active],baseline_B1=b[active],ratio_B1=r[active],denominator_A1=den[active],ratio_A1=a1[active],neighbor_online_median=med[active],n_online_donors_used=ndonor[active],neighbor_global_fallback=globalfb[active],ratio_upper=upper[active],ratio_mid=mid[active],records_upper_scenario=uppern[active],records_mid_scenario=midn[active],cap_ring_proxy=capvalue[active],cap_ring_proxy_available=capvalid[active],ring=p.ring5[active])))
        print('I5 completed',date,'mid_available',middone,flush=True)
    frame=pd.DataFrame(records);st.save(frame,ROOT/'05_bounds/T31_recovery_bounds_v6.csv');st.save(frame,ROOT/'08_figures/fig_recovery_bounds_v6_data.csv')
    st.save(frame,ROOT/'01_internal/T31_recovery_bounds_internal_v6.csv',internal=True)
    st.save(pd.concat(deviceframes,ignore_index=True),ROOT/'01_internal/T31_device_scenarios_internal_v6.parquet',internal=True)
    st.save(pd.concat(bootframes,ignore_index=True),ROOT/'01_internal/T31_bootstrap_internal_v6.parquet',internal=True)
    st.checks['9dates']=len(frame)==9;st.checks['lower_matches_naive_4dp']=frame.lower_equals_naive_4dp.all()
    st.checks['500resamples_per_date_scenario']=all(len(g)==500 for _,g in pd.concat(bootframes,ignore_index=True).groupby(['date','scenario']))
    st.finish(dict(mid_source=capsource,mid_proxy_context=proxycontext,mid_missing_dates=frame.loc[~frame.mid_available,'date'].tolist(),
        acceptance=dict(stable_inside_each_date=frame.set_index('date').stable_inside_bounds.to_dict(),width_0726_le020=bool(frame.set_index('date').loc['2021-07-26','bound_width']<=.20),width_0802_le010=bool(frame.set_index('date').loc['2021-08-02','bound_width']<=.10)),
        ordering_failures=frame.loc[~frame.upper_ge_lower,'date'].tolist(),note='Acceptance failures are scientific results and are not computation integrity failures'))
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--protocol',required=True);ap.add_argument('--capture',default='auto');args=ap.parse_args();run(args.protocol,args.capture)
