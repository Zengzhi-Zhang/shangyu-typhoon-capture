# -*- coding: utf-8 -*-
"""Independent local-input audit of I1'/I6'; writes only v7 audit JSON."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[3]), str(_ReleasePath(__file__).resolve().parents[1])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from pathlib import Path
from decimal import Decimal
from datetime import datetime, timezone, timedelta
import json,re
import numpy as np
import pandas as pd

ROOT=Path(_release_path('v7_root'))
V1=ROOT.parent;V6=V1/'formal_v6'
EVENT=pd.date_range('2021-07-25','2021-08-02').strftime('%Y-%m-%d').tolist()
PARTIAL={'2021-07-08','2021-07-10','2021-07-22','2021-07-23','2021-07-24','2021-07-25'}
B1=[d for d in pd.date_range('2021-07-05','2021-07-21').strftime('%Y-%m-%d') if d not in PARTIAL]
FIVE=['0-2','2-4','4-7','7-12','12+']
PUBLIC=[
 '02_device_state/device_state_v7.csv',
 '02_device_state/T27_state_summary_v7.csv',
 '02_device_state/T27_failed_breakdown_v7.csv',
 '02_device_state/T27_state_changes_v7.csv',
 '06_s_pre/T36_health_screened_v6.csv',
 '06_s_pre/T36_rings_v6.csv',
 '06_s_pre/T36_rings_v6_orig.csv',
 '06_s_pre/T36_ols_v6.csv',
 '08_figures/fig_state_map_v7_data.csv',
 '08_figures/fig_health_screened_v7_data.csv']

def read(p,**kw):return pd.read_csv(p,encoding='utf-8-sig',**kw)
def close(a,b):return bool(np.allclose(a,b,rtol=5e-11,atol=2e-7,equal_nan=True))

def main():
    checks={};privacy=[]
    q=read(ROOT/'01_internal/device_state_internal_v7.csv').sort_values(['date','dev']).reset_index(drop=True)
    old=read(V6/'01_internal/device_state_internal_v6.csv').sort_values(['date','dev']).reset_index(drop=True)
    checks['internal_same_rows_and_order_as_v6']=q[['dev','date']].equals(old[['dev','date']])
    renamed={'state':'state_v6','public_D_STATE':'public_D_STATE_v6','normal_catchall_low_or_missing_ratio':'normal_catchall_low_or_missing_ratio_v6'}
    preserved=[]
    for c in old:
        dest=renamed.get(c,c)
        if pd.api.types.is_numeric_dtype(old[c]):ok=close(pd.to_numeric(q[dest]),pd.to_numeric(old[c]))
        else:ok=q[dest].fillna('<NA>').astype(str).equals(old[c].fillna('<NA>').astype(str))
        if not ok:preserved.append(c)
    checks['all_v6_intermediate_values_preserved']=not preserved
    raw=pd.to_numeric(q.hours_recording,errors='coerce').between(5,11)
    tail=pd.to_numeric(q.stop_hour,errors='coerce').notna()|pd.to_numeric(q.longest_zero_run,errors='coerce').ge(6)
    should=q.in_A200.eq(1)&~q.state_v6.isin(['zero','offline'])&raw&tail
    expected=q.state_v6.copy();expected.loc[should]='partial_day'
    checks['state_priority_and_literal_raw_hours']=q.state.equals(expected)
    checks['outside_A200_not_classified']=q.loc[q.in_A200.ne(1),'state'].eq('not_classified_outside_A200').all()
    broad=q.in_A200.eq(1)&~q.state.isin(['zero','offline','partial_day','partial_channel'])
    strict=broad&~q.state.isin(['degraded_other','low_all_channels'])
    checks['broad_membership_exact']=q.in_health.eq(1).equals(broad)
    checks['strict_membership_exact']=q.in_health_strict.eq(1).equals(strict)
    pre=read(V6/'01_internal/s_pre_devices_v6.csv');spre=set(pre.loc[pre.in_Spre.eq(1),'dev'])
    checks['spre_health_intersection_exact']=q.in_Spre_health.eq(1).equals(broad&q.dev.isin(spre))
    pub=read(ROOT/PUBLIC[0]).sort_values(['date','dev']).reset_index(drop=True)
    i=q[q.in_A200.eq(1)].sort_values(['date','dev_public']).reset_index(drop=True)
    checks['public_A200_state_matches_internal']=pub[['dev','date','state']].equals(i[['dev_public','date','state']].rename(columns={'dev_public':'dev'}))
    checks['public12dates_A200_complete']=len(pub)==12*int(i[i.date.eq(EVENT[0])].shape[0]) and pub.date.nunique()==12
    checks['original_date_flags_preserved']=pub.public_D_STATE_v6.eq(pub.date.isin(set(old.loc[old.public_D_STATE.eq(1),'date'])).astype(int)).all()
    summary=read(ROOT/PUBLIC[1]);failed=read(ROOT/PUBLIC[2])
    checks['state_summary96rows']=len(summary)==96
    checks['state_count_closure']=summary.groupby('date').n_devices.sum().eq(pub.groupby('date').size()).all()
    checks['failed_state_closure']=failed.groupby('date').n_failed_state.sum().eq(pub.groupby('date').A1_failed.sum()).all()
    attr=read(V1/'01_panels/device_attributes.csv').sort_values('dev').set_index('dev')
    devs=attr.index;na=int(attr.in_A200.sum())
    day=read(V1/'01_panels/device_day.csv',usecols=['dev','date','n'])
    mat=day.pivot_table(index='dev',columns='date',values='n',aggfunc='sum',fill_value=0).reindex(index=devs,fill_value=0)
    h=read(V1/'01_panels/device_hour.csv',usecols=['dev','date','hour','n'])
    afternoon=h[h.hour.between(11,23)].pivot_table(index='dev',columns='date',values='n',aggfunc='sum',fill_value=0).reindex(index=devs,fill_value=0)
    daily=read(ROOT/PUBLIC[4]).set_index('date')
    checks['T36nine_dates']=daily.index.tolist()==EVENT
    rng=np.random.default_rng(20261005);weights=np.zeros((500,len(attr)),np.int64)
    weights[:,attr.in_A200.eq(1).to_numpy()]=rng.multinomial(na,np.full(na,1/na),size=500)
    original=read(ROOT/PUBLIC[6]);models=read(ROOT/PUBLIC[7]);draws=read(ROOT/'01_internal/health_bootstrap_draws_v7.csv')
    checks['OLS3dates_HC1']=set(models.date)==set(EVENT[1:4]) and models.covariance.eq('HC1').all()
    checks['original5rings_all9days']=len(original)==45 and set(original.distance_ring)==set(FIVE)
    for date in EVENT:
        xx=q[q.date.eq(date)].set_index('dev').reindex(devs)
        dm=afternoon if date==EVENT[0] else mat
        refs=[d for d in B1 if pd.Timestamp(d).dayofweek==pd.Timestamp(date).dayofweek]
        n=dm[date].to_numpy(float);b=dm[refs].mean(axis=1).to_numpy(float)
        for flag,col,label in [('in_health','R_health','health'),('in_health_strict','R_health_strict','health_strict'),('in_Spre_health','R_spre_health','spre_health')]:
            use=xx[flag].fillna(0).eq(1).to_numpy();den=b[use].sum()
            point=n[use].sum()/den if den else np.nan
            bootden=weights[:,use]@b[use]
            boot=np.divide(weights[:,use]@n[use],bootden,out=np.full(500,np.nan),where=bootden>0)
            finite=boot[np.isfinite(boot)];ci=np.quantile(finite,[.025,.975]) if len(finite) else [np.nan,np.nan]
            checks[f'{date}_{label}_ratio_count_CI']=close([point,use.sum(),*ci],[daily.loc[date,col],daily.loc[date,'n_'+label],daily.loc[date,col+'_ci_lo'],daily.loc[date,col+'_ci_hi']])
            checks[f'{date}_{label}_shared500draws']=close(draws[draws.date.eq(date)].sort_values('draw')[col+'_draw'].to_numpy(),boot)
        city=int(daily.loc[date,'n_health']);missing=int(daily.loc[date,'n_missing_distance_health'])
        rings=original[original.date.eq(date)]
        checks[date+'_city_ring_missing_count_closure']=int(rings.n_devices.sum())==city-missing
        checks[date+'_city_ring_baseline_share_closure']=close([rings.baseline_records.sum()/daily.loc[date,'baseline_health']+daily.loc[date,'baseline_share_missing_distance_health']],[1.])
    for rel in PUBLIC:
        path=ROOT/rel;txt=path.read_text(encoding='utf-8-sig')
        if 'cam_' in txt:privacy.append(dict(file=rel,type='restricted_camera_alias'))
        for m in re.finditer(r'(?<![A-Za-z0-9])[0-9a-f]{16}(?![A-Za-z0-9])',txt):
            token=m.group();decimal_tail=token.isdigit() and m.start()>=2 and txt[m.start()-1]=='.' and txt[m.start()-2].isdigit()
            if not decimal_tail:privacy.append(dict(file=rel,type='independent16hex_token',offset=m.start()))
        p=read(path,dtype=str)
        forbidden=set(p.columns)&{'lon','lat','longitude','latitude','dev_name','device_id','dev_public'}
        if forbidden:privacy.append(dict(file=rel,type='forbidden_public_columns',columns=sorted(forbidden)))
        for c in ['plot_lon','plot_lat']:
            if c in p:
                bad=sum(Decimal(v).as_tuple().exponent < -2 for v in p[c].dropna())
                if bad:privacy.append(dict(file=rel,type='coordinate_decimal_precision',column=c,n=bad))
    checks['owned_public_privacy_zero_hits']=not privacy
    data=dict(ended=datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
        scope='Owned I1/I6 scientific public CSVs only; existing versions and source data readonly',
        checks={k:bool(v) for k,v in checks.items()},n_checks=len(checks),all_passed=all(checks.values()),
        privacy_total_hits=len(privacy),privacy_hits=privacy,public_files=len(PUBLIC),v6_fields_not_preserved=preserved)
    out=ROOT/'00_env/health_independent_audit_v7.json';out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(all_passed=data['all_passed'],n_checks=len(checks),privacy_total_hits=len(privacy),failed=[k for k,v in checks.items() if not v])))
    if not data['all_passed']:raise AssertionError('Independent health audit failed')

if __name__=='__main__':main()
