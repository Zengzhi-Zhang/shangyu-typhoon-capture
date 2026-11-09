# -*- coding: utf-8 -*-
"""Independent W1/W3 audit. Reads frozen local inputs; writes only own audit JSON."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[3]), str(_ReleasePath(__file__).resolve().parents[1])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, time
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from pyproj import Transformer
import statsmodels.formula.api as smf

R=Path(_release_path('v8_root')); V=R.parent; SEED=20261005
checks={}; hashes={}
def read(p):
    p=Path(p); hashes[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
    return pd.read_parquet(p) if p.suffix=='.parquet' else pd.read_csv(p,encoding='utf-8-sig')
def check(k,v): checks[k]=bool(v)
def near(k,a,b,tol=1e-10): check(k,np.allclose(a,b,rtol=tol,atol=tol,equal_nan=True))
def div(a,b): return np.divide(a,b,out=np.full(np.broadcast_shapes(np.shape(a),np.shape(b)),np.nan),where=np.asarray(b)>0)
def weight(mask):
    n=int(mask.sum()); x=np.zeros((500,len(mask)),np.int64)
    x[:,mask]=np.random.default_rng(SEED).multinomial(n,np.repeat(1/n,n),500); return x
def medians(r,online,U,coord,xy):
    # Independent transcription of original v6 neighbour_median finite-ratio eligibility.
    donors=np.flatnonzero(online&np.isfinite(r)); valid=donors[coord[donors]]
    tree=cKDTree(xy[valid]) if len(valid) else None
    out=np.full(len(r),np.nan); count=np.zeros(len(r),int); fallback=np.zeros(len(r),bool)
    for i in np.flatnonzero(U):
        ix=donors[donors!=i]
        if not len(ix): continue
        if coord[i] and tree is not None:
            z=np.atleast_1d(tree.query(xy[i],k=min(8,len(valid)))[1]); ix2=valid[z]; ix2=ix2[ix2!=i][:6]
            if len(ix2): out[i]=np.median(r[ix2]);count[i]=len(ix2);continue
        out[i]=np.median(r[ix]);count[i]=len(ix);fallback[i]=True
    return out,count,fallback

start=datetime.now(timezone.utc).isoformat(); tick=time.monotonic()
a=read(V/'01_panels/device_attributes.csv').sort_values('dev').reset_index(drop=True)
ids=np.arange(1,len(a)+1); A100=a.in_A100.eq(1).to_numpy(); A200=a.in_A200.eq(1).to_numpy(); star=a.in_Sstar.eq(1).to_numpy()
q=read(V/'formal_v7/01_internal/device_state_internal_v7.csv').set_index(['date','dev_public'])
dd=read(V/'01_panels/device_day.csv').pivot_table(index='dev',columns='date',values='n',aggfunc='sum',fill_value=0).reindex(a.dev,fill_value=0)
hh=read(V/'01_panels/device_hour.csv'); hh=hh[hh.hour.between(11,23)].pivot_table(index='dev',columns='date',values='n',aggfunc='sum',fill_value=0).reindex(a.dev,fill_value=0)
old=read(V/'formal_v6/01_internal/T31_device_scenarios_internal_v6.parquet')
fam=read(V/'formal_v7/07_consequences/T37_estimator_family_v7.csv')
out=read(R/'03_baseline/W1_device_estimators_v8.csv').set_index(['baseline','estimator'])
dev=read(R/'01_internal/health_baseline_device_0728_v8.csv').set_index('dev_public').reindex(ids)
boot=read(R/'01_internal/health_baseline_bootstrap_v8.parquet')
bd=read(R/'01_internal/health_pc_bootstrap_v8.parquet')
daily=read(R/'03_baseline/W3_health_pc_daily_v8.csv').set_index('date')
rings=read(R/'03_baseline/W3_health_pc_rings_0726_v8.csv').set_index('distance_ring')
model=read(R/'03_baseline/W3_health_pc_ols_0726_v8.csv').set_index('term')
state_all=read(R/'03_baseline/W3_state_ratio_medians_A200_0726_v8.csv')
state_sel=read(R/'03_baseline/W3_state_ratio_medians_selected_0726_v8.csv')
versions=read(R/'03_baseline/W3_state_ratio_medians_version_provenance_0726_v8.csv')
cap=read(V/'formal_v7/01_internal/capture_camera_internal_v7.csv')
w100=weight(A100); w200=weight(A200)
B1=[d for d in pd.date_range('2021-07-05','2021-07-21').strftime('%Y-%m-%d') if d not in ['2021-07-08','2021-07-10']]
def vec(d,pool=B1):
    m=hh if d=='2021-07-25' else dd; refs=[x for x in pool if pd.Timestamp(x).dayofweek==pd.Timestamp(d).dayofweek]
    return m[d].to_numpy(float),m[refs].mean(axis=1).to_numpy(float),refs
d='2021-07-28'; n,b,_=vec(d); bw=dd['2021-07-14'].to_numpy(float); st=q.loc[d].reindex(ids)
o=old[old.date.eq(d)].set_index('dev_public').reindex(ids)
U=o.U.fillna(False).to_numpy(bool); online=o.in_online.fillna(False).to_numpy(bool); low=U&o.state.eq('low_all_channels').to_numpy()
near('W1_observed_records',dev.observed_records,n);near('W1_baseline_B1',dev.baseline_B1,b);near('W1_baseline_B1w',dev.baseline_B1w,bw)
check('W1_U_exact_frozen',np.array_equal(dev.U,U)); check('W1_Son_exact_frozen',np.array_equal(dev.in_online,online))
coord=a.lon.notna().to_numpy()&a.lat.notna().to_numpy()&a.lon.ne(0).to_numpy()&a.lat.ne(0).to_numpy()
xy=np.full((len(a),2),np.nan); tr=Transformer.from_crs(4326,32651,always_xy=True)
xy[coord]=np.column_stack(tr.transform(a.loc[coord,'lon'],a.loc[coord,'lat']))
up={}
for base,den in [('B1',b),('B1w',bw)]:
    r=div(n,den); med,cnt,fb=medians(r,online,U,coord,xy)
    near('W1_'+base+'_donor_median',dev['neighbor_median_'+base],med)
    check('W1_'+base+'_donor_count',np.array_equal(dev['n_donors' if base=='B1' else 'n_donors_B1w'],cnt))
    check('W1_'+base+'_global_fallback',np.array_equal(dev['global_fallback' if base=='B1' else 'global_fallback_B1w'],fb))
    upper=n.copy(); upper[U]=den[U]*np.minimum(1.1,med[U]);upper[low]=den[low]*np.minimum(1.1,.5*med[low]);up[base]=upper
    near('W1_'+base+'_upper_device',dev['records_upper_'+base],upper,2e-10)
    check('W1_'+base+'_all_U_medians_defined',np.isfinite(med[U]).all())
sample={'R_naive':A100,'R_online':online,'R_stable':star,'R_upper':A100,
        'R_health':A200&st.in_health.fillna(0).eq(1).to_numpy(),
        'R_health_strict':A200&st.in_health_strict.fillna(0).eq(1).to_numpy(),
        'R_spre_health':A200&st.in_Spre_health.fillna(0).eq(1).to_numpy()}
for (base,est),row in out.iterrows():
    use=sample[est]; den=b if base=='B1' else bw; val=up[base] if est=='R_upper' else n
    w=w200 if est in ['R_health','R_health_strict','R_spre_health'] else w100
    draws=div(w[:,use]@val[use],w[:,use]@den[use]); saved=boot[boot.baseline.eq(base)&boot.estimator.eq(est)].sort_values('rep')
    near('W1_'+base+'_'+est+'_500_draws',saved.estimate.to_numpy(),draws)
    check('W1_'+base+'_'+est+'_n',int(row.n_devices)==int(use.sum()))
    if base=='B1':
        v=fam[fam.date.eq(d)&fam.estimator.eq(est)].iloc[0]
        near('W1_B1_'+est+'_published_copy',row[['value','ci_lo','ci_hi']].to_numpy(float),v[['R','ci_lo','ci_hi']].to_numpy(float))
    else:
        near('W1_B1w_'+est+'_point',row.value,val[use].sum()/den[use].sum())
        near('W1_B1w_'+est+'_CI',row[['ci_lo','ci_hi']].to_numpy(float),np.quantile(draws,[.025,.975]))

ring=pd.cut(a.dist_baiguan_km,[0,2,4,7,12,np.inf],labels=['0-2','2-4','4-7','7-12','12+'],right=False,include_lowest=True).astype(object).fillna('missing').to_numpy()
for d,row in daily.iterrows():
    st=q.loc[d].reindex(ids);use=A200&~st.state.isin(['zero','offline','partial_day']).to_numpy();n,b,refs=vec(d)
    check('W3_'+d+'_membership_count',use.sum()==row.n_devices)
    check('W3_'+d+'_only_partial_channel_added',np.array_equal(use&~st.in_health.fillna(0).eq(1).to_numpy(),A200&st.state.eq('partial_channel').to_numpy()))
    check('W3_'+d+'_target_frozen',np.array_equal(n[A100],st.loc[A100,'n_day']))
    near('W3_'+d+'_baseline_frozen',b[A100],st.loc[A100,'baseline_B1'])
    near('W3_'+d+'_point',row.value,n[use].sum()/b[use].sum())
    draw=div(w200[:,use]@n[use],w200[:,use]@b[use]); saved=bd[bd.date.eq(d)].sort_values('rep')
    near('W3_'+d+'_shared_500_draws',draw,saved.estimate.to_numpy());near('W3_'+d+'_CI',row[['ci_lo','ci_hi']].to_numpy(float),np.quantile(draw,[.025,.975]))
    near('W3_'+d+'_missing_baseline_share',row.baseline_share_missing_distance,b[use&(ring=='missing')].sum()/b[use].sum())
    check('W3_'+d+'_missing_count',row.n_missing_distance==(use&(ring=='missing')).sum())
d='2021-07-26';st=q.loc[d].reindex(ids);n,b,_=vec(d);use=A200&~st.state.isin(['zero','offline','partial_day']).to_numpy();r=div(n,b);rng=np.random.default_rng(SEED)
for rn,row in rings.iterrows():
    ix=np.flatnonzero(use&(ring==rn));ind=rng.integers(0,len(ix),size=(500,len(ix)));draw=div(n[ix][ind].sum(1),b[ix][ind].sum(1))
    near('W3_ring_'+rn+'_point_CI',row[['value','ci_lo','ci_hi']].to_numpy(float),np.r_[n[ix].sum()/b[ix].sum(),np.quantile(draw,[.025,.975])])
    check('W3_ring_'+rn+'_n',row.n_devices==len(ix))
eligible=cap[cap.variant.eq('main_R60_cap03')&cap.date.eq(d)&cap.selected.eq(True)&cap.expected.ge(10)]
check('W3_selected_camera_unique',eligible.dev.nunique()==len(eligible))
selected=A200&np.isin(ids,eligible.dev)
for frame,mask,label in [(state_all,A200,'all_A200'),(state_sel,selected,'selected')]:
    check('W3_'+label+'_state_count_closure',frame.n_devices.sum()==mask.sum())
    for _,row in frame.iterrows():
        take=mask&st.state.eq(row.state).to_numpy();check('W3_'+label+'_'+row.state+'_n',take.sum()==row.n_devices)
        rr=r[take]; ar=st.ratio_A1.to_numpy(float)[take]
        near('W3_'+label+'_'+row.state+'_B1_median',row.ratio_B1_median,np.nanmedian(rr) if np.isfinite(rr).any() else np.nan)
        near('W3_'+label+'_'+row.state+'_A1_median',row.ratio_A1_median,np.nanmedian(ar) if np.isfinite(ar).any() else np.nan)
for _,row in versions.iterrows():
    mask=A200 if row.scope=='all_A200' else selected
    mask=mask&st['state_v6' if row.state_version=='frozen_v6' else 'state'].eq(row.state).to_numpy()
    check('W3_version_'+row.scope+row.state_version+row.state+'_n',mask.sum()==row.n_devices)
    near('W3_version_'+row.scope+row.state_version+row.state+'_median',row.ratio_B1_median,np.nanmedian(r[mask]))
x=a.loc[use&coord].copy();x['log_base']=np.log(x.base_B1.where(x.base_B1.gt(0)));x['response']=np.log(np.clip(r[x.index],.05,3))
x=x.replace([np.inf,-np.inf],np.nan).dropna(subset=['response','dist_baiguan_km','log_base','elev_m','relief_300m','road_level','org','gateway'])
fit=smf.ols('response ~ np.log1p(dist_baiguan_km) + log_base + elev_m + relief_300m + C(road_level) + C(org) + gateway',x).fit(cov_type='HC1')
near('W3_OLS_all_coefficients',model.coef.reindex(fit.params.index),fit.params);near('W3_OLS_all_HC1_SE',model.se_HC1.reindex(fit.params.index),fit.bse)
near('W3_OLS_all_p',model.p.reindex(fit.params.index),fit.pvalues);check('W3_OLS_n',model.n.eq(len(x)).all())
check('all_audited_inputs_unchanged',all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in hashes.items()))
source=(V/'formal_v6/scripts/bounds_v6.py').read_text(encoding='utf-8')
check('original_T31_finite_ratio_rule_in_source','donors=np.flatnonzero(online&np.isfinite(r))' in source)
report={'status':'passed' if all(checks.values()) else 'failed','created_at_utc':datetime.now(timezone.utc).isoformat(),'start_utc':start,'seconds':time.monotonic()-tick,'n_checks':len(checks),'checks':checks,'audited_sha256':hashes,
 'interpretation':{'donor_rule':'Baseline-specific finite ratios before6NN exactly follows originalT31; fixedS_on/U/state, fixedneighbours insideeachbaseline bootstrap. Initialover-frozen-neighbour implementationwascorrectedandarchived.',
 'CI':'500A100sharedweights fornaive/online/stable/upper;500A200sharedweights forhealthfamilies andW3; observedsetsandimputationvaluesfixed. Conditionalintervals,notselectionorclassificationuncertainty.',
 'state_medians':'v6/v7labelsandA200/selected-eventexpected>=10denominatorsareseparate. B1/A1ratiosnotinterchangeable;selectedsubsetneednotcontainall329cameras.'},
 'source_reads':False,'key_reads':False,'science_outputs_modified':False}
(R/'00_env/recovery_spatial_independent_audit_v8.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
print(json.dumps({'n_checks':len(checks),'passed':all(checks.values()),'failed':[k for k,v in checks.items() if not v],'seconds':report['seconds']}))
assert all(checks.values())
