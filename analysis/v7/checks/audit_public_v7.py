# -*- coding: utf-8 -*-
"""Final independent completeness/privacy audit; no science or source mutation.

Exact private-name matches are counted without serialising matched strings.
Coordinates are tested with Decimal lexical precision, including JSON numbers.
"""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[3]), str(_ReleasePath(__file__).resolve().parents[1])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from pathlib import Path
from decimal import Decimal,InvalidOperation
from datetime import datetime,timezone,timedelta
import argparse,csv,io,re,json,hashlib
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

R=Path(_release_path('v7_root'));V1=R.parent
EVENT=pd.date_range('2021-07-25','2021-08-02').strftime('%Y-%m-%d').tolist()
CONTROL=pd.date_range('2021-07-12','2021-07-19').strftime('%Y-%m-%d').tolist()
TARGET=EVENT[:7]
VARIANTS={'main_R60_cap03':(60,.3),'sens_R60_cap02':(60,.2),'sens_R60_cap04':(60,.4),'sens_R40_cap03':(40,.3)}
REQUIRED=[
 '02_device_state/device_state_v7.csv','02_device_state/T27_state_summary_v7.csv','02_device_state/T27_failed_breakdown_v7.csv',
 '03_taxi_probe/T28_probe_daily_v7.csv','03_taxi_probe/T28_wednesday_sensitivity_v7.csv',
 '03_taxi_probe/T35_capture_wellmatched_v6.csv','03_taxi_probe/T35_by_state_v6.csv','03_taxi_probe/T35_camera_type_v6.csv','03_taxi_probe/T35_capture_camera_v7.csv','03_taxi_probe/T35_capture_wellmatched_v7.json','03_taxi_probe/T35_METHODS_v7.md',
 '05_bounds/T31_recovery_bounds_v7.csv','06_s_pre/T36_health_screened_v6.csv','06_s_pre/T36_rings_v6.csv','06_s_pre/T36_rings_v6_orig.csv','06_s_pre/T36_ols_v6.csv',
 '07_consequences/T37_network_comparison_v7.csv','07_consequences/T37_estimator_family_v7.csv',
 '08_figures/fig_state_map_v7_data.csv','08_figures/fig_health_screened_v7_data.csv','08_figures/fig_probe_relative_intensity_v7_data.csv','08_figures/fig_probe_recovery_v7_data.csv','08_figures/fig_capture_relative_v7_data.csv','08_figures/fig_capture_failed_scatter_v7_data.csv','08_figures/fig_capture_type_v7_data.csv','08_figures/fig_estimator_family_v7_data.csv']
REPORTS=['README_v7.md','RESULTS_SUMMARY_v7.md','DEVIATIONS_v7.md','EXECUTION_LOG_v7.md','results_v7.json']
HEX=re.compile(r'(?<![0-9A-Za-z])[0-9a-fA-F]{16}(?![0-9A-Za-z])')
# A complete legal number containing a decimal point is numerical evidence,
# including e/E exponent tails. Independent hex identifiers remain disallowed.
DECIMAL_LITERAL=re.compile(r'(?<![A-Za-z0-9_.])[-+]?(?:\d+\.\d*|\.\d+)(?:[eE][-+]?\d+)?(?![A-Za-z0-9_.])')
PLATE=re.compile(r'[京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼][A-ZＡ-Ｚ][A-Z0-9Ａ-Ｚ０-９·.]{5,7}')
COORD=re.compile(r'(^|_)(lon|lat|longitude|latitude)($|_)',re.I)
def now():return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
def read(rel,**kw):return pd.read_csv(R/rel,encoding='utf-8-sig',**kw)
def load(rel):return json.loads((R/rel).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def close(a,b,tol=5e-10):return bool(np.allclose(a,b,atol=tol,rtol=5e-10,equal_nan=True))
def divide(n,d):
    n,d=np.broadcast_arrays(np.asarray(n,float),np.asarray(d,float))
    return np.divide(n,d,out=np.full(n.shape,np.nan),where=d>0)
def tokens(text):
    numbers=[(m.start(),m.end()) for m in DECIMAL_LITERAL.finditer(text)]
    return [m.group() for m in HEX.finditer(text) if not any(a<=m.start() and m.end()<=b for a,b in numbers)]
def excessive(value):
    s=str(value).strip()
    if not s or s.upper() in {'NA','NAN','NONE','NULL'}:return False
    try:x=Decimal(s);return x.is_finite() and x.as_tuple().exponent < -2
    except InvalidOperation:return False
def json_precision(text):
    def leaves(x):
        if isinstance(x,dict):return sum(leaves(v) for v in x.values())
        if isinstance(x,list):return sum(leaves(v) for v in x)
        return int(excessive(x))
    def walk(x):
        if isinstance(x,dict):return sum(leaves(v) if COORD.search(k) else walk(v) for k,v in x.items())
        if isinstance(x,list):return sum(walk(v) for v in x)
        return 0
    return walk(json.loads(text,parse_float=Decimal))

def scan_public(phase):
    names=set(pd.read_csv(V1/'01_panels/device_id_map.csv',encoding='utf-8-sig',usecols=['dev_name']).dev_name.dropna().astype(str))
    names.discard('')
    paths=[p for p in R.iterdir() if p.is_file() and p.suffix.lower() in {'.md','.json','.txt','.csv'}]
    for folder in R.iterdir():
        if folder.is_dir() and (re.match(r'^0[2-9]_',folder.name) or folder.name.startswith('20_')):
            paths.extend(p for p in folder.rglob('*') if p.is_file())
    total=dict(hex16=0,plate_pattern=0,internal_prefix=0,original_device_name=0,coordinate_precision=0,unreadable_binary=0)
    details=[]
    for p in sorted(set(paths)):
        h={k:0 for k in total}
        try:text=p.read_text(encoding='utf-8-sig')
        except UnicodeDecodeError:h['unreadable_binary']=1;text=''
        h.update(hex16=len(tokens(text)),plate_pattern=len(PLATE.findall(text)),internal_prefix=text.count('cam_'),original_device_name=sum(text.count(n) for n in names if n in text))
        if p.suffix.lower()=='.csv' and text:
            reader=csv.DictReader(io.StringIO(text));coords=[c for c in reader.fieldnames or [] if COORD.search(c)]
            h['coordinate_precision']=sum(excessive(row.get(c,'')) for row in reader for c in coords)
        elif p.suffix.lower()=='.json' and text:h['coordinate_precision']=json_precision(text)
        elif text:
            labelled=re.findall(r'(?:longitude|latitude|\blon\b|\blat\b|经度|纬度)["\s]*[:=]\s*([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)',text,re.I)
            h['coordinate_precision']=sum(excessive(v) for v in labelled)
        total={k:total[k]+h[k] for k in total}
        details.append(dict(path=p.relative_to(R).as_posix(),sha256=sha(p),hits=h))
    return total,details

def check_capture(checks):
    arrays=np.load(R/'01_internal/capture_vehicle_counts_v7.npz',allow_pickle=False)
    allday=arrays['all_day'];h11=arrays['h11'];dates=arrays['dates'].tolist();radii=arrays['radii'].tolist();ids=arrays['camera_ids']
    checks['T35_exact8controls_7targets']=dates==CONTROL+TARGET
    checks['T35_fixed290vehicle_count_array']=allday.shape[1]==290 and h11.shape==allday.shape
    checks['T35_capture_cannot_exceed_expected']=bool((allday[...,1]<=allday[...,0]).all() and (h11[...,1]<=h11[...,0]).all())
    internal=read('01_internal/capture_camera_internal_v7.csv')
    summary=read('01_internal/capture_summary_internal_v7.csv')
    selection=read('01_internal/capture_selection_internal_v7.csv')
    public=read('03_taxi_probe/T35_capture_camera_v7.csv',dtype=str)
    state=read('01_internal/device_state_internal_v7.csv').set_index(['dev_public','date'])
    ce=load('00_env/capture_execution_v7.json')
    acceptance={(x['variant'],x['date']):x for x in ce['acceptance']}
    checks['T35_all4variants_7days']=len(summary)==28 and set(summary.variant)==set(VARIANTS) and set(summary.date)==set(TARGET)
    selection_counts={}
    for name,(radius,threshold) in VARIANTS.items():
        ri=radii.index(radius);ctrl=allday[ri,:,:8].sum(axis=(0,1));ctrlh=h11[ri,:,:8].sum(axis=(0,1))
        cp=divide(ctrl[:,1],ctrl[:,0]);selected=(ctrl[:,0]>=30)&(cp>=threshold)
        select=selection[selection.variant.eq(name)].set_index('dev').reindex(ids)
        checks[name+'_only8day_control_selection_exact']=np.array_equal(select.selected.to_numpy(bool),selected) and close(select[['expected_ctrl','captured_ctrl','cap_ctrl']].to_numpy(float),np.column_stack([ctrl,cp]))
        selection_counts[name]=int(selected.sum())
        for date in TARGET:
            di=dates.index(date);counts=(h11 if date==TARGET[0] else allday)[ri,:,di].sum(0)
            matchedctrl=ctrlh if date==TARGET[0] else ctrl
            matchcap=divide(matchedctrl[:,1],matchedctrl[:,0]);cap=divide(counts[:,1],counts[:,0]);relative=divide(cap,matchcap)
            data=internal[internal.variant.eq(name)&internal.date.eq(date)].set_index('dev').reindex(ids)
            row=summary[summary.variant.eq(name)&summary.date.eq(date)].iloc[0]
            checks[name+'_'+date+'_selection_eventcounts_and_matched_controls']=np.array_equal(data.selected.to_numpy(bool),selected) and close(data[['expected','captured']].to_numpy(float),counts) and close(data[['expected_ctrl_matched','captured_ctrl_matched','relative_cap']].to_numpy(float),np.column_stack([matchedctrl,relative]))
            st=state.reindex(pd.MultiIndex.from_arrays([ids,[date]*len(ids)]))
            checks[name+'_'+date+'_state_ratio_A1_failure_shared_exact']=data.state.to_list()==st.state.to_list() and np.array_equal(data.A1_failed,st.A1_failed) and close(data.ratio,st.ratio)
            fail=selected&st.A1_failed.to_numpy(bool);eligiblefail=fail&(counts[:,0]>=10)
            comparable=selected&(counts[:,0]>=10)&np.isfinite(relative)&(matchcap>0)
            stable=comparable&data.in_Sstar.to_numpy(bool)
            corr=comparable&np.isfinite(st.ratio.to_numpy(float))
            rho=spearmanr(st.ratio.to_numpy(float)[corr],relative[corr]).statistic if corr.sum()>=3 else np.nan
            total=counts[eligiblefail].sum(0);totalall=counts[fail].sum(0)
            med=float(np.median(relative[stable])) if stable.any() else np.nan
            checks[name+'_'+date+'_failed_exposure_denominator_closure']=close([row.n_selected,row.n_comparable,row.n_Sstar_comparable,row.n_failed_selected,row.n_failed_event_ge10,row.failed_selected_expected,row.failed_selected_captured,row.failed_event_ge10_expected,row.failed_event_ge10_captured,row.Sstar_relative_median,row.spearman_rho],[selected.sum(),comparable.sum(),stable.sum(),fail.sum(),eligiblefail.sum(),*totalall,*total,med,rho])
            checks[name+'_'+date+'_failed_exposure_partition']=row.n_failed_selected==row.n_failed_event_ge10+row.n_failed_event_lt3+row.n_failed_event_3to9
            ac=acceptance[name,date]
            expected=[bool(.9<=med<=1.05) if np.isfinite(med) else None,bool(total[1]/total[0]<=.02) if total[0] else None,bool(rho>=.6) if np.isfinite(rho) else None]
            checks[name+'_'+date+'_acceptance_not_event_selection']=expected==[ac['Sstar_relative_median_in_090_105'],ac['failed_pooled_cap_le002'],ac['Spearman_ge06']]
    checks['T35_public_integer_device_IDs']=pd.to_numeric(public.dev).mod(1).eq(0).all()
    low=public.expected.eq('<10')
    checks['T35_public_low_expected_rates_NA']=public.loc[low,['cap','relative_cap']].isna().all().all()
    lowcontrol=public.expected_ctrl_matched.eq('<10')
    checks['T35_public_low_matched_control_rates_NA']=public.loc[lowcontrol,['cap_ctrl_matched','relative_cap']].isna().all().all()
    for col in ['expected','captured','expected_ctrl','captured_ctrl','expected_ctrl_matched','captured_ctrl_matched']:
        values=pd.to_numeric(public[col],errors='coerce')
        checks['T35_public_'+col+'_small_count_masking']=not values.between(0,9).any()
    return selection_counts

def scientific_checks(checks,phase):
    state=read('02_device_state/device_state_v7.csv');summary=read('02_device_state/T27_state_summary_v7.csv');failed=read('02_device_state/T27_failed_breakdown_v7.csv')
    checks['T27_12dates_complete_A200']=state.date.nunique()==12 and len(state)==14652 and len(summary)==96
    checks['T27_state_denominator_closure']=summary.groupby('date').n_devices.sum().eq(state.groupby('date').size()).all()
    checks['T27_failed_denominator_closure']=failed.groupby('date').n_failed_state.sum().eq(state.groupby('date').A1_failed.sum()).all()
    health=read('06_s_pre/T36_health_screened_v6.csv').set_index('date');rings=read('06_s_pre/T36_rings_v6_orig.csv');ols=read('06_s_pre/T36_ols_v6.csv')
    checks['T36_all9dates_5originalrings_3models']=health.index.tolist()==EVENT and len(rings)==45 and set(ols.date)==set(EVENT[1:4])
    checks['T36_city_missing_distance_ring_count_closure']=all(int(g.n_devices.sum())==int(health.loc[d,'n_health']-health.loc[d,'n_missing_distance_health']) for d,g in rings.groupby('date'))
    checks['T36_city_missing_distance_ring_baseline_closure']=all(close([g.baseline_records.sum()/health.loc[d,'baseline_health']+health.loc[d,'baseline_share_missing_distance_health']],[1.]) for d,g in rings.groupby('date'))
    bounds=read('05_bounds/T31_recovery_bounds_v7.csv');probe=read('03_taxi_probe/T28_probe_daily_v7.csv')
    checks['T31_9dates_preserved_midNA_August_probeNA']=bounds.date.tolist()==EVENT and bounds.R_mid.isna().all() and bounds.loc[bounds.date.ge('2021-08-01'),['R_probe','R_probe_ci_lo','R_probe_ci_hi']].isna().all().all()
    checks['T28_28dates_7matched_eventdays']=len(probe)==28 and probe.loc[probe.date.eq('2021-07-25'),'hour_matched'].eq(1).all()
    family=read('07_consequences/T37_estimator_family_v7.csv');network=read('07_consequences/T37_network_comparison_v7.csv')
    checks['T37_family_9x11_and_network7']=len(family)==99 and family.date.nunique()==9 and family.estimator.nunique()==11 and network.date.tolist()==TARGET
    checks['T37_family_all_estimator_values_and_intervals_match_sources']=all(close([row.R,row.ci_lo,row.ci_hi],[(health.loc[row.date] if row.estimator in ['R_health','R_health_strict','R_spre_health'] else bounds.set_index('date').loc[row.date]).get(c,np.nan) for c in [row.estimator,row.estimator+'_ci_lo',row.estimator+'_ci_hi']]) for row in family.itertuples())
    checks['T37_August_probe_and_mid_unavailable']=family[family.estimator.eq('R_probe')&family.date.ge('2021-08-01')].R.isna().all() and family[family.estimator.eq('R_mid')].R.isna().all()
    for path in ['00_env/health_independent_audit_v7.json','00_env/probe_bounds_spatial_independent_audit_v7.json']:
        audit=load(path);checks['prior_independent_pass_'+Path(path).name]=audit['all_passed'] and all(audit['checks'].values())
    selection_counts=check_capture(checks)
    if phase=='final':
        results=load('results_v7.json')
        checks['root_posthoc_and_v6_stops_preserved']=results['posthoc_revision'] and results['v6_historical_stops']==dict(S1=False,S2=True,S3=True,unchanged=True)
        checks['root_I1_partial_day_counts_match_state']=results['partial_day_by_date']==state.groupby('date').state.apply(lambda s:int(s.eq('partial_day').sum())).to_dict()
        checks['root_all24_main_acceptance_rows']=len(results['acceptance'])==24
        checks['root_full9health_days_and_7network_days']=len(results['health'])==9 and len(results['relative_network_comparison'])==7
        text=(R/'RESULTS_SUMMARY_v7.md').read_text(encoding='utf-8')
        checks['root_health_scope_denominator_and_conditional_interval_disclosure']=all(t in text for t in ['全市估计包含无距离设备','严格健康口径','不是已识别的真实恢复','不是等效检验'])
    return selection_counts

def main(phase):
    missing=[p for p in REQUIRED+(REPORTS if phase=='final' else []) if not (R/p).is_file()]
    if missing:raise RuntimeError('Required final audit files missing: '+str(len(missing)))
    checks=dict(all6tasks_prescribed_files_complete=not missing)
    hits,files=scan_public(phase);checks['independent_public_privacy_zero_hits']=not any(hits.values())
    counts=scientific_checks(checks,phase)
    checks['scientific_public_files_unchanged_during_audit']=all(sha(R/f['path'])==f['sha256'] for f in files)
    checks={k:bool(v) for k,v in checks.items()};failed=[k for k,v in checks.items() if not v]
    result=dict(ended=now(),phase=phase,scope='Root reports plus all files recursively in 02-09 and 20 directories; 00_env/scripts/01_internal excluded from public scan',all_passed=not failed,n_checks=len(checks),checks=checks,failed=failed,publication_files=len(files),public_privacy_hits=hits,privacy_total_hits=sum(hits.values()),files=files,control_only_selection_counts=counts,source_reads=False,key_reads=False,scientific_outputs_modified=False)
    name='public_independent_audit_v7.json' if phase=='final' else 'scientific_public_independent_audit_v7.json'
    (R/'00_env'/name).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(all_passed=not failed,n_checks=len(checks),failed=failed,publication_files=len(files),privacy_total_hits=sum(hits.values()))))
    if failed:raise AssertionError('Public independent audit failed')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['scientific','final'],default='final');main(parser.parse_args().phase)
