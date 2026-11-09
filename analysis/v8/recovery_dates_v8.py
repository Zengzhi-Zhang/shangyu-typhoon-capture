# -*- coding: utf-8 -*-
"""W2 retrospective recovery dates from frozen existing daily estimators."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[2]), str(_ReleasePath(__file__).resolve().parents[0])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,time
import numpy as np,pandas as pd

ROOT=Path(_release_path('v8_root'));OLD=ROOT.parent;SEED=20261005
EVENT=pd.date_range('2021-07-25','2021-08-02').strftime('%Y-%m-%d').tolist()
DEVICE=['R_naive','R_health','R_health_strict','R_spre_health','R_online','R_stable','R_upper']
ESTIMATORS=DEVICE+['R_probe','R_taxi_km']
THRESHOLDS=[.8,.85,.9,.95]

def sig(p):
    s=p.stat();return dict(sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=s.st_size,mtime_ns=s.st_mtime_ns)
def clean(v):
    if isinstance(v,dict):return {str(k):clean(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)):return [clean(x) for x in v]
    if isinstance(v,np.generic):return clean(v.item())
    if isinstance(v,float) and not np.isfinite(v):return None
    return v
def save(f,rel,internal=False):
    p=ROOT/rel;p.parent.mkdir(parents=True,exist_ok=True)
    f.to_csv(p,index=False,encoding='utf-8-sig',float_format='%.12g' if internal else '%.4f',na_rep='NA')
def put(p,obj):
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(clean(obj),ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')

def classify(dates,values,theta,rule):
    values=np.asarray(values,float);finite=np.isfinite(values);ge=finite&(values>=theta)
    result=dict(recovery_date=None,first_observed_qualifying_date=None,status=None,right_censored=False,
        tail_days=0,n_missing=int((~finite).sum()),n_finite=int(finite.sum()),earlier_missing=0,
        missing_dates=';'.join(d for d,good in zip(dates,finite) if not good))
    if rule=='first_ge':
        possible=np.flatnonzero(ge)
        if len(possible):
            j=int(possible[0]);result['first_observed_qualifying_date']=dates[j]
            if not finite[:j].all():result.update(status='not_evaluable_missing_values',earlier_missing=int((~finite[:j]).sum()))
            else:result.update(recovery_date=dates[j],status='qualified',tail_days=len(dates)-j)
        elif finite.all():result.update(status='right_censored',right_censored=True)
        else:result.update(status='not_evaluable_missing_values')
    else:
        eligible=[j for j in range(len(dates)) if ge[j:].all()]
        if eligible:
            j=eligible[0];result.update(recovery_date=dates[j],first_observed_qualifying_date=dates[j],status='qualified',tail_days=len(dates)-j,earlier_missing=int((~finite[:j]).sum()))
        elif finite[-1] and not ge[-1]:result.update(status='right_censored',right_censored=True)
        else:result.update(status='not_evaluable_missing_values')
    return result

def selftest():
    dates=['a','b','c']
    assert classify(dates,[1,.8,1],.9,'first_ge')['recovery_date']=='a'
    assert classify(dates,[1,.8,1],.9,'sustained_point')['recovery_date']=='c'
    assert classify(dates,[1,1,.8],.9,'sustained_point')['status']=='right_censored'
    assert classify(dates,[1,1,np.nan],.9,'sustained_lower_ci')['status']=='not_evaluable_missing_values'
    assert classify(dates,[np.nan,1,1],.9,'first_ge')['status']=='not_evaluable_missing_values'
    assert classify(dates,[np.nan,1,1],.9,'sustained_point')['recovery_date']=='b'
    assert classify(dates,[.9,.9,.9],.9,'sustained_point')['recovery_date']=='a'

def main():
    selftest();start=datetime.now(timezone.utc).isoformat();tick=time.perf_counter()
    protocol=ROOT/'00_env/recovery_component_protocol_v8.json';assert protocol.exists() and (ROOT/'00_env/protocol_frozen_v8.json').exists()
    inputs={
        'family':OLD/'formal_v7/07_consequences/T37_estimator_family_v7.csv',
        'taxi':OLD/'formal_v3/06_m5_bias_correction/m5_visible_bias_v3.csv',
        'deviceW1':ROOT/'03_baseline/W1_device_estimators_v8.csv',
        'probeW1':ROOT/'01_internal/recovery_probe_reference_v8.csv',
        'component_protocol':protocol}
    before={k:sig(p) for k,p in inputs.items()}
    fam=pd.read_csv(inputs['family']).set_index(['date','estimator']);taxi=pd.read_csv(inputs['taxi']).set_index('date')
    w1=pd.read_csv(inputs['deviceW1']).set_index(['baseline','estimator']);probe=pd.read_csv(inputs['probeW1']).set_index('baseline')
    daily=[];checks={}
    for baseline in ['B1','B1w']:
        for name in ESTIMATORS:
            dates=EVENT[:7] if name in ['R_probe','R_taxi_km'] else EVENT
            for date in dates:
                if name=='R_taxi_km':
                    s=taxi.loc[date];point,lo,hi=[s[c] for c in ['R_taxi_km','R_taxi_km_ci_lo','R_taxi_km_ci_hi']]
                    source='formal_v3/06_m5_bias_correction/m5_visible_bias_v3.csv';key='date='+date+';field=R_taxi_km'
                    scope='Copied frozen B_TAXI moving-km vehicle200 interval; fixed taxi fleet and baseline';sourcebase='B_TAXI_unchanged'
                else:
                    s=fam.loc[(date,name)];point,lo,hi=[s[c] for c in ['R','ci_lo','ci_hi']]
                    source='formal_v7/07_consequences/T37_estimator_family_v7.csv';key='date='+date+';estimator='+name
                    scope=s.interval_scope;sourcebase='B1_published' if name!='R_probe' else 'B1_times_B_PROBE_published'
                replaced=False
                if baseline=='B1w' and date=='2021-07-28':
                    if name in DEVICE:
                        s=w1.loc[('B1w',name)];point,lo,hi=[s[c] for c in ['value','ci_lo','ci_hi']]
                        source='formal_v8/03_baseline/W1_device_estimators_v8.csv';key='date='+date+';baseline=B1w;estimator='+name
                        scope=s.interval_scope;sourcebase='B1w';replaced=True
                    elif name=='R_probe':
                        s=probe.loc['B1w'];point,lo,hi=[s[c] for c in ['R_probe','R_probe_ci_lo','R_probe_ci_hi']]
                        source='formal_v7/01_internal/T28_wednesday_sensitivity_internal_v7.csv';key='date='+date+';baseline_variant=B_PROBE_drop_0707_0721;field=R_probe'
                        scope='Copied v7 vehicle200 by naive-device500 empirical product interval; fixed sets/baselines; not100000 independent draws';sourcebase='existing_B_PROBE_drop_0707_0721';replaced=True
                daily.append(dict(baseline=baseline,date=date,estimator=name,value=point,ci_lo=lo,ci_hi=hi,
                    source_baseline=sourcebase,replaced_0728=replaced,source=source,source_key=key,interval_scope=scope,
                    hour_matched=int(date=='2021-07-25' and name!='R_taxi_km'),
                    baseline_label_scope='B1/B1w refer to device scenario; taxi B_TAXI unchanged; probe cites own B_PROBE Wednesday variant'))
    daily=pd.DataFrame(daily);rows=[]
    for (baseline,name),g in daily.groupby(['baseline','estimator'],sort=False):
        g=g.sort_values('date');dates=g.date.tolist()
        for theta in THRESHOLDS:
            for rule in ['first_ge','sustained_point','sustained_lower_ci']:
                use=g.ci_lo.to_numpy(float) if rule=='sustained_lower_ci' else g.value.to_numpy(float)
                info=classify(dates,use,theta,rule)
                rows.append(dict(baseline=baseline,estimator=name,theta=theta,date_rule=rule,**info,
                    window_start=dates[0],window_end=dates[-1],n_observations=len(dates),
                    censor_date=dates[-1] if info['right_censored'] else None,
                    rule_scope='Earliest observed threshold crossing or earliest verified complete remaining tail; no minimum tail length; retrospective finite window',
                    threshold_precision='Compare numeric source values as stored without rounding/epsilon; original published precision retained',
                    source='03_baseline/W2_daily_inputs_v8.csv',interval_conditioning='Copied source conditional cluster intervals; lower-CI persistence is not simultaneous confidence coverage or a formal recovery-time CI',
                    baseline_note='Taxi remains frozen B_TAXI in both scenarios' if name=='R_taxi_km' else 'Only July28 denominator variant changes; memberships fixed'))
    out=pd.DataFrame(rows)
    # Keep source precision in the public calculation trace so rounding cannot
    # turn a value below a threshold into an apparent qualifying input.
    save(daily,'03_baseline/W2_daily_inputs_v8.csv',True);save(daily,'01_internal/recovery_daily_inputs_v8.csv',True)
    save(out,'03_baseline/W2_recovery_dates_v8.csv');save(out,'01_internal/recovery_dates_internal_v8.csv',True)
    checks['216_recovery_rows']=len(out)==216
    checks['154_daily_inputs']=len(daily)==154
    checks['all_72_triplets']=out.groupby(['baseline','estimator','theta']).size().eq(3).all()
    checks['GPS_horizon_July31']=out.loc[out.estimator.isin(['R_probe','R_taxi_km']),'window_end'].eq('2021-07-31').all()
    checks['devices_horizon_Aug2']=out.loc[out.estimator.isin(DEVICE),'window_end'].eq('2021-08-02').all()
    a=daily[daily.baseline.eq('B1')].set_index(['date','estimator']);b=daily[daily.baseline.eq('B1w')].set_index(['date','estimator'])
    unchanged=a.index.get_level_values('date')!='2021-07-28'
    checks['all_other_dates_exactly_unchanged']=a.loc[unchanged,['value','ci_lo','ci_hi']].equals(b.loc[unchanged,['value','ci_lo','ci_hi']])
    checks['taxi_all_dates_exactly_unchanged']=a.xs('R_taxi_km',level='estimator')[['value','ci_lo','ci_hi']].equals(b.xs('R_taxi_km',level='estimator')[['value','ci_lo','ci_hi']])
    checks['8_replaced_rows_only']=int(daily.replaced_0728.sum())==8
    checks['qualified_dates_inside_window']=all(row.window_start<=row.recovery_date<=row.window_end for row in out[out.status.eq('qualified')].itertuples())
    after={k:sig(p) for k,p in inputs.items()};checks['all_inputs_unchanged']=before==after
    checks={k:bool(v) for k,v in checks.items()}
    report=dict(status='complete' if all(checks.values()) else 'integrity_failed',started_utc=start,finished_utc=datetime.now(timezone.utc).isoformat(),elapsed_seconds=time.perf_counter()-tick,seed=SEED,
        checks=checks,checks_passed=all(checks.values()),inputs_before=before,inputs_after=after,
        source_reads=False,key_reads=False,synthetic_checks='7 edge cases passed, including missing terminal, unknown earlier first date and one-day terminal tail',
        theta090=out[out.theta.eq(.9)].to_dict('records'),status_counts=out.status.value_counts().to_dict(),
        caution='Pointwise lower-CI sustained rule is descriptive and conditional; it is not a joint probability statement or recovery-date confidence interval; horizon differs by estimator')
    put(ROOT/'00_env/recovery_dates_execution_v8.json',report)
    print(json.dumps(clean(dict(status=report['status'],checks=checks,seconds=report['elapsed_seconds'],theta090=report['theta090'])),ensure_ascii=False),flush=True)
    if not all(checks.values()):raise RuntimeError('W2 recovery checks failed')
if __name__=='__main__':main()
