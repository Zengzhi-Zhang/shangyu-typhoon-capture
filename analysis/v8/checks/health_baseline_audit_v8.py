# -*- coding: utf-8 -*-
"""Independent W1/W3 output/source audit; no prior-version or science writes."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[3]), str(_ReleasePath(__file__).resolve().parents[1])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from pathlib import Path
from datetime import datetime,timezone
import json,re,hashlib
import numpy as np
import pandas as pd
R=Path(_release_path('v8_root'));V1=R.parent;V7=V1/'formal_v7';V6=V1/'formal_v6'
EVENT=pd.date_range('2021-07-25','2021-08-02').strftime('%Y-%m-%d').tolist()
B1=[d for d in pd.date_range('2021-07-05','2021-07-21').strftime('%Y-%m-%d') if d not in ['2021-07-08','2021-07-10']]
def read(p,**kw):return pd.read_csv(p,encoding='utf-8-sig',**kw)
def close(a,b):return bool(np.allclose(a,b,rtol=5e-10,atol=2e-7,equal_nan=True))
def div(n,b):return np.divide(n,b,out=np.full(np.broadcast_shapes(np.shape(n),np.shape(b)),np.nan),where=np.asarray(b)>0)
def ci(v):return np.quantile(np.asarray(v)[np.isfinite(v)],[.025,.975])
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def weights(mask):
    w=np.zeros((500,len(mask)),int);k=mask.sum();w[:,mask]=np.random.default_rng(20261005).multinomial(k,np.full(k,1/k),500);return w
def main():
    checks={};a=read(V1/'01_panels/device_attributes.csv').sort_values('dev').reset_index(drop=True)
    ids=np.arange(1,len(a)+1);a100=a.in_A100.eq(1).to_numpy();a200=a.in_A200.eq(1).to_numpy();star=a.in_Sstar.eq(1).to_numpy();w100=weights(a100);w200=weights(a200)
    q=read(V7/'01_internal/device_state_internal_v7.csv').set_index(['date','dev_public'])
    old=read(V7/'07_consequences/T37_estimator_family_v7.csv');day=read(V1/'01_panels/device_day.csv')
    mat=day.pivot_table(index='dev',columns='date',values='n',aggfunc='sum',fill_value=0).reindex(index=a.dev,fill_value=0)
    h=read(V1/'01_panels/device_hour.csv',usecols=['dev','date','hour','n'])
    afternoon=h[h.hour.between(11,23)].pivot_table(index='dev',columns='date',values='n',aggfunc='sum',fill_value=0).reindex(index=a.dev,fill_value=0)
    pc=read(R/'03_baseline/W3_health_pc_daily_v8.csv').set_index('date');drawpc=pd.read_parquet(R/'01_internal/health_pc_bootstrap_v8.parquet')
    checks['W3_all9dates']=pc.index.tolist()==EVENT
    for date in EVENT:
        state=q.loc[date].reindex(ids);use=a200&~state.state.isin(['zero','offline','partial_day']).to_numpy();dm=afternoon if date==EVENT[0] else mat
        refs=[d for d in B1 if pd.Timestamp(d).dayofweek==pd.Timestamp(date).dayofweek]
        n=dm[date].to_numpy(float);b=dm[refs].mean(axis=1).to_numpy(float);boot=div(w200[:,use]@n[use],w200[:,use]@b[use])
        checks[date+'_pc_pointNCI_from_frozen_states_and_panel']=close([n[use].sum()/b[use].sum(),use.sum(),*ci(boot)],[pc.loc[date,'value'],pc.loc[date,'n_devices'],pc.loc[date,'ci_lo'],pc.loc[date,'ci_hi']])
        checks[date+'_pc_all500_draws_source_reproduced']=close(boot,drawpc[drawpc.date.eq(date)].sort_values('rep').estimate)
        checks[date+'_only_partial_channel_added']=pc.loc[date,'n_retained_partial_channel']==int((a200&state.state.eq('partial_channel').to_numpy()).sum())
    device=read(R/'01_internal/health_baseline_device_0728_v8.csv').set_index('dev_public').reindex(ids)
    sources=pd.read_parquet(V6/'01_internal/T31_device_scenarios_internal_v6.parquet');source=sources[sources.date.eq('2021-07-28')].set_index('dev_public').reindex(ids)
    checks['W1_U_Son_states_exact_original_T31']=np.array_equal(device.U,source.U.fillna(False)) and np.array_equal(device.in_online,source.in_online.fillna(False)) and device.state_T31_v6.fillna('NA').equals(source.state.fillna('NA'))
    checks['W1_B1w_denominator_exact_July14']=close(device.baseline_B1w,mat['2021-07-14'])
    checks['W1_B1_denominator_exact_3Wednesday_mean']=close(device.baseline_B1,mat[['2021-07-07','2021-07-14','2021-07-21']].mean(axis=1))
    checks['W1_observed_n_unchanged']=close(device.observed_records,mat['2021-07-28'])
    links=read(R/'01_internal/health_baseline_neighbor_links_v8.csv');U=device.U.to_numpy(bool);online=device.in_online.to_numpy(bool)
    for baseline in ['B1','B1w']:
        rr=div(device.observed_records.to_numpy(float),device['baseline_'+baseline].to_numpy(float));ld=links[links.baseline.eq(baseline)]
        checks[baseline+'_donors_always_fixed_Son_and_finite']=all(online[int(i)-1] and np.isfinite(rr[int(i)-1]) for i in ld.donor_dev_public)
        checks[baseline+'_neighbors_exclude_self']=ld.target_dev_public.ne(ld.donor_dev_public).all()
        med=np.full(len(ids),np.nan)
        for target,g in ld.groupby('target_dev_public'):med[int(target)-1]=np.median(rr[g.donor_dev_public.to_numpy(int)-1])
        checks[baseline+'_donor_link_medians_reproduce']=close(med[U],device.loc[U,'neighbor_median_'+baseline])
        values=device.observed_records.to_numpy(float).copy();upper=np.minimum(1.1,med);low=U&source.state.eq('low_all_channels').to_numpy();upper[low]=np.minimum(1.1,.5*med[low]);values[U]=device.loc[U,'baseline_'+baseline].to_numpy(float)*upper[U]
        checks[baseline+'_literal_upper_formula_from_donors']=close(values,device['records_upper_'+baseline])
    rows=read(R/'03_baseline/W1_device_estimators_v8.csv');draws=pd.read_parquet(R/'01_internal/health_baseline_bootstrap_v8.parquet')
    checks['W1_all14rows_available_500valid']=len(rows)==14 and rows.available.all() and rows.bootstrap_valid.eq(500).all()
    state=q.loc['2021-07-28'].reindex(ids)
    masks={'R_naive':a100,'R_online':online,'R_stable':star,'R_upper':a100,'R_health':a200&state.in_health.fillna(0).eq(1).to_numpy(),'R_health_strict':a200&state.in_health_strict.fillna(0).eq(1).to_numpy(),'R_spre_health':a200&state.in_Spre_health.fillna(0).eq(1).to_numpy()}
    for row in rows.itertuples():
        use=masks[row.estimator];w=w200 if row.estimator in ['R_health','R_health_strict','R_spre_health'] else w100
        b=device['baseline_'+row.baseline].to_numpy(float);n=device['records_upper_'+row.baseline].to_numpy(float) if row.estimator=='R_upper' else device.observed_records.to_numpy(float)
        boot=div(w[:,use]@n[use],w[:,use]@b[use])
        checks[row.baseline+'_'+row.estimator+'_500draws_and_N']=close(boot,draws[draws.baseline.eq(row.baseline)&draws.estimator.eq(row.estimator)].sort_values('rep').estimate) and row.n_devices==use.sum()
        if row.baseline=='B1':
            original=old[old.date.eq(row.date)&old.estimator.eq(row.estimator)].iloc[0]
            checks[row.baseline+'_'+row.estimator+'_frozen_pointCI_copied_exact']=close([row.value,row.ci_lo,row.ci_hi],[original.R,original.ci_lo,original.ci_hi])
        else:checks[row.baseline+'_'+row.estimator+'_point_and_CI_source_reproduced']=close([row.value,row.ci_lo,row.ci_hi],[n[use].sum()/b[use].sum(),*ci(boot)])
    initial=read(R/'01_internal/health_baseline_initial_W1_device_estimators_v8.csv')
    checks['initial20NA_diagnostic_preserved_and_superseded']=initial[initial.baseline.eq('B1w')&initial.estimator.eq('R_upper')].value.isna().all() and rows[rows.baseline.eq('B1w')&rows.estimator.eq('R_upper')].value.notna().all()
    rings=read(R/'03_baseline/W3_health_pc_rings_0726_v8.csv');row=pc.loc['2021-07-26']
    checks['W3_original5rings_city_missing_count_closure']=len(rings)==5 and rings.n_devices.sum()==row.n_devices-row.n_missing_distance
    checks['W3_original5rings_city_missing_baseline_closure']=close([rings.baseline_records.sum()/row.baseline_records+row.baseline_share_missing_distance],[1.])
    for file,scope in [('W3_state_ratio_medians_A200_0726_v8.csv','all_A200'),('W3_state_ratio_medians_selected_0726_v8.csv','main329_selected_event_expected_ge10')]:
        stats=read(R/'03_baseline'/file);scopeids=ids[a200]
        if scope!='all_A200':
            c=read(V7/'01_internal/capture_camera_internal_v7.csv');scopeids=c.loc[c.variant.eq('main_R60_cap03')&c.date.eq('2021-07-26')&c.selected.eq(True)&c.expected.ge(10),'dev'].to_numpy()
        ss=q.loc['2021-07-26'].reindex(scopeids);ratio=mat['2021-07-26']/mat[['2021-07-05','2021-07-12','2021-07-19']].mean(axis=1)
        ratio_map=pd.Series(ratio.reindex(a.dev).to_numpy(float),index=ids)
        checks[scope+'_state_median_denominator_count_closure']=stats.n_devices.sum()==len(scopeids)
        checks[scope+'_all_B1_A1_medians_reproduced']=all(close([z.ratio_B1_median,z.ratio_A1_median],[ratio_map.reindex(ss[ss.state.eq(z.state)].index).median(),ss.loc[ss.state.eq(z.state),'ratio_A1'].median()]) for z in stats.itertuples())
    # Independent refit of the new W3 model, without touching any old model.
    import statsmodels.formula.api as smf
    ss=q.loc['2021-07-26'].reindex(ids);use=a200&~ss.state.isin(['zero','offline','partial_day']).to_numpy();n=mat['2021-07-26'].to_numpy(float);b=mat[['2021-07-05','2021-07-12','2021-07-19']].mean(axis=1).to_numpy(float)
    x=a.loc[use&a.lon.notna().to_numpy()&a.lat.notna().to_numpy()].copy();x['log_base']=np.log(x.base_B1);x['response']=np.log(pd.Series(div(n,b),index=a.index).reindex(x.index).clip(.05,3))
    x=x.replace([np.inf,-np.inf],np.nan).dropna(subset=['response','dist_baiguan_km','log_base','elev_m','relief_300m','road_level','org','gateway'])
    model=smf.ols('response ~ np.log1p(dist_baiguan_km) + log_base + elev_m + relief_300m + C(road_level) + C(org) + gateway',data=x).fit(cov_type='HC1')
    stored=read(R/'03_baseline/W3_health_pc_ols_0726_v8.csv').set_index('term').reindex(model.params.index)
    checks['W3_original_OLS_formula_HC1_all_terms_reproduced']=close(stored.coef,model.params) and close(stored.se_HC1,model.bse) and close(stored.p,model.pvalues) and stored.n.eq(model.nobs).all()
    paths=sorted((R/'03_baseline').glob('W1_device*'))+sorted((R/'03_baseline').glob('W3*'));hits=0
    pattern=re.compile(r'(?<![A-Za-z0-9])[0-9a-fA-F]{16}(?![A-Za-z0-9])');number=re.compile(r'(?<![A-Za-z0-9_.])[-+]?(?:\d+\.\d*|\.\d+)(?:[eE][-+]?\d+)?(?![A-Za-z0-9_.])')
    names=set(read(V1/'01_panels/device_id_map.csv',usecols=['dev_name']).dev_name.dropna().astype(str));names.discard('')
    for p in paths:
        text=p.read_text(encoding='utf-8-sig');spans=[(m.start(),m.end()) for m in number.finditer(text)]
        hits+=text.count('cam_')+sum(text.count(name) for name in names if name in text)
        hits+=sum(not any(a<=m.start() and m.end()<=b for a,b in spans) for m in pattern.finditer(text))
        checks['no_private_columns_'+p.name]=not set(read(p,nrows=0).columns)&{'dev','dev_public','lon','lat','dev_name','ph'}
    checks['owned_public_privacy_zero_hits']=hits==0
    execution=json.loads((R/'00_env/health_baseline_execution_v8.json').read_text(encoding='utf-8'))
    checks['all_old_input_SHA_still_unchanged']=all(sha(p)==h for p,h in execution['inputs_sha256'].items())
    checks={k:bool(v) for k,v in checks.items()};report=dict(ended=datetime.now(timezone.utc).isoformat(),all_passed=all(checks.values()),n_checks=len(checks),checks=checks,privacy_total_hits=hits,public_files=len(paths),files=[dict(path=str(p.relative_to(R)),sha256=sha(p)) for p in paths],source_reads=False,key_reads=False,old_versions_modified=False)
    (R/'00_env/health_baseline_independent_audit_v8.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(all_passed=report['all_passed'],n_checks=len(checks),privacy_total_hits=hits,failed=[k for k,v in checks.items() if not v])))
    if not report['all_passed']:raise AssertionError('Independent health/baseline audit failed')

if __name__=='__main__':main()
