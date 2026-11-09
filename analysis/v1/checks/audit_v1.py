# -*- coding: utf-8 -*-
"""Read-only semantic/privacy audit; output contains identifiers of files only."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[3]), str(_ReleasePath(__file__).resolve().parents[1])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
import re,sys,csv,hashlib,ast
from common_v1 import *
from deliverable_spec_v1 import missing_deliverables,FIGURE_ALIASES

MAIN_GROUPS=['local_zheD_ICE','local_zheD_NEV','zhejiang_other_ICE','zhejiang_other_NEV',
             'other_province_ICE','other_province_NEV','unreadable','all','local_zheD',
             'zhejiang_other','other_province','all_ICE']
CURVE_GROUPS=['all','local_zheD','zhejiang_other','other_province']+MAIN_GROUPS[:6]
CLASSES=['regular','frequent','occasional','earlier_only','unseen']
E_T=dates('2021-07-25','2021-08-02');E_P=dates('2021-07-11','2021-07-19')

def read(rel):return pd.read_csv(ROOT/rel,encoding='utf-8-sig')
def jread(rel):return json.loads((ROOT/rel).read_text(encoding='utf-8'))
def exact_grid(frame,keys,levels):
    if frame.duplicated(keys).any():return False
    actual=set(map(tuple,frame[keys].itertuples(index=False,name=None)))
    from itertools import product
    return actual==set(product(*levels))
def check_probability_table(check,label,frame,columns,valid=None):
    valid=np.ones(len(frame),bool) if valid is None else np.asarray(valid,bool)
    for col in columns:
        x=pd.to_numeric(frame[col],errors='coerce')
        check(label+'_'+col+'_range',bool(x.dropna().between(-.000051,1.000051).all()))
        check(label+'_'+col+'_defined_when_count_known',bool(x[valid].notna().all()))
        lo=pd.to_numeric(frame[col+'_lo'],errors='coerce');hi=pd.to_numeric(frame[col+'_hi'],errors='coerce')
        known=lo.notna()&hi.notna()
        check(label+'_'+col+'_CI_order',bool((lo[known]<=hi[known]+.000001).all()))
        check(label+'_'+col+'_CI_range',bool(lo.dropna().between(-.000051,1.000051).all()) and bool(hi.dropna().between(-.000051,1.000051).all()))
        check(label+'_'+col+'_CI_defined_when_count_known',bool(lo[valid].notna().all()) and bool(hi[valid].notna().all()))

def source_checks(check):
    required=['00_env/input_manifest.json','00_env/input_manifest_final.json','00_env/source_comparison_final.json','00_env/environment.json']
    if not all((ROOT/p).is_file() for p in required):
        check('source_final_fingerprints_exist',False);return False
    first=jread(required[0]);last=jread(required[1]);comparison=jread(required[2]);env=jread(required[3])
    before={r['path']:r for r in first};after={r['path']:r for r in last}
    fields=['size','mtime_ns','sha256_head1MB','sha256_tail1MB']
    complete=all(all(k in r for k in fields+['path','mtime']) for r in first+last)
    identical=set(before)==set(after) and all(all(before[p].get(k)==after[p].get(k) for k in fields) for p in before)
    check('source_final_fields_complete',complete)
    check('source_manifest_paths_unique',len(before)==len(first) and len(after)==len(last))
    check('source_final_fingerprints_equal',identical)
    check('source_final_comparison_verified',comparison.get('unchanged') is True and not comparison.get('changed') and comparison.get('n_files')==len(last))
    check('source_final_comparison_includes_hashes',set(fields+['path']).issubset(comparison.get('fields',[])))
    hashes=all(re.fullmatch('[0-9a-f]{64}',str(r.get(k,''))) for r in first+last for k in fields[2:])
    check('source_sha256_format',hashes)
    xls=[r['path'] for r in first if str(r['path']).lower().endswith('.xls')]
    check('all_481_xls_fingerprinted',len(xls)==481,len(xls))
    check('taxi_batch_workbook_inventory',sum('GPS0601-0705' in p for p in xls)==191 and sum('GPS0706-0731' in p for p in xls)==290)
    check('source_xls_paths_pseudonymised',all(re.fullmatch('vehicle_[0-9a-f]{16}\.xls',p.replace('\\','/').rsplit('/',1)[-1]) for p in xls))
    basenames={p.replace('\\','/').rsplit('/',1)[-1] for p in before}
    check('source_required_AVI_and_sensor_fingerprints',set(['AVI_20210627.csv','AVI_20210628_0704.csv','AVI_0705-0803.csv','sensor_location.csv','sensor_classification.csv','(corrected)sensor_allroad_matched.csv']).issubset(basenames))
    check('source_fixed_56_terrain_tiles_fingerprinted',sum(str(p).lower().endswith('.tif') for p in before)==56)
    check('required_python_environment',str(env.get('python','')).replace('\\','/').lower()==_release_path('path_003'))
    check('environment_seed_frozen',env.get('seed')==20261005)
    comparisons=list((ROOT/'00_env').glob('source_comparison_*.json'))
    check('all_recorded_source_comparisons_unchanged',all(json.loads(p.read_text(encoding='utf-8')).get('unchanged') is True for p in comparisons))
    return bool(complete and identical and comparison.get('unchanged') is True and hashes)

def script_seed_checks(check):
    names=['common_v1.py','m1_m2_v1.py','m3_vehicles_v1.py','m4_spatial_v1.py',
           'm5_bias_v1.py','m6_consolidate_v1.py','spatial_stats_v1.py','taxi_grid_v1.py',
           'taxi_grid_resume_v1.py','avi_panel_v1.py']
    for name in names:
        source=(ROOT/'scripts'/name).read_text(encoding='utf-8-sig');tree=ast.parse(source)
        seeds=[]
        for node in ast.walk(tree):
            if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='SEED' for t in node.targets):
                seeds.append(node.value.value if isinstance(node.value,ast.Constant) else None)
        inherited=any(isinstance(node,ast.ImportFrom) and node.module=='common_v1' and
                      any(alias.name in ['*','SEED'] for alias in node.names) for node in ast.walk(tree))
        check('script_seed_'+name,(bool(seeds) and all(v==20261005 for v in seeds)) or (not seeds and inherited))

def vehicle_checks(check,dh,attr,dd):
    import pyarrow.parquet as pq
    master=pq.ParquetFile(ROOT/'01_panels/plate_master.parquet')
    check('plate_master_schema',set(['ph','cat','nev','plate_len']).issubset(master.schema_arrow.names))
    pm=pd.read_parquet(ROOT/'01_panels/plate_master.parquet',columns=['ph','cat','nev','plate_len'])
    check('plate_master_unique_HMAC',bool(pm.ph.astype(str).str.fullmatch('[0-9a-f]{16}').all()) and not pm.ph.duplicated().any())
    check('plate_master_category_domain',set(pm.cat)=={'local_zheD','zhejiang_other','other_province','unreadable'})
    check('plate_master_nev_binary',bool(pm.nev.isin([0,1]).all()))
    summary=read('01_panels/plate_day_summary.csv').set_index('date')
    check('plate_summary_all_37_dates',set(summary.index)==set(D_ALL) and not summary.index.duplicated().any())
    coverage=read('02_m1_observation/m1_daily_coverage.csv').set_index('date')
    check('formal_coverage_not_pilot_stable_plates',bool(coverage.plate_panel_status.eq('formal_rebuilt').all()))
    check('coverage_plates_match_formal_summary',bool((coverage.plates_all.astype(int)==summary.reindex(coverage.index).plates.astype(int)).all()) and bool((coverage.plates_Sstar.astype(int)==summary.reindex(coverage.index).plates_Sstar.astype(int)).all()))
    check('plate_summary_records_equal_hour_panel',bool((summary.records.reindex(D_ALL).values==dd.sum().reindex(D_ALL).values).all()))
    stable_ids=attr.index[attr.in_Sstar==1]
    check('plate_summary_stable_records_equal_hour_panel',bool((summary.records_Sstar.reindex(D_ALL).values==dd.loc[stable_ids].sum().reindex(D_ALL).values).all()))
    afternoon=dh[dh.dev.isin(stable_ids)&dh.hour.between(11,23)].groupby('date').n.sum().reindex(D_ALL,fill_value=0)
    check('plate_summary_stable_h11_records_equal_hour_panel',bool((summary.records_Sstar_h11.reindex(D_ALL).values==afternoon.values).all()))
    for d in D_ALL:
        panel=pq.ParquetFile(ROOT/'01_panels/plate_day'/f'{d}.parquet')
        check('plate_day_'+d+'_schema_rows',set(['ph','n','n_stable','n_gw','h_min','h_max']).issubset(panel.schema_arrow.names) and panel.metadata.num_rows==int(summary.loc[d,'plates']))
    panels=jread('00_env/vehicle_avi_execution.json')['checks']
    for field in ['daily_records_equal_device_hour','source_metadata_unchanged','shared_definitions_unchanged','hmac_unique']:
        check('AVI_parser_'+field,panels.get(field) is True)
    check('AVI_parser_all_dates',panels.get('dates')==37)
    check('AVI_parser_no_unknown_device',panels.get('unknown_device_count')==0)
    v=jread('04_m3_vehicles/m3_h1_h2_verdict.json')
    check('M3_seed_and_vehicle_bootstrap',v.get('seed')==20261005 and v.get('vehicle_cluster_bootstrap')==200)
    check('H1_H2_actual_verdicts',all(v.get(h,{}).get('status') in ['pass','fail','mixed','degraded'] for h in ['H1','H2']))
    baseline_tables={}
    for bname in ['B1','B2','B3']:
        rel='04_m3_vehicles/m3_daily_by_group'+('' if bname=='B1' else '_'+bname)+'.csv'
        x=read(rel);baseline_tables[bname]=x
        check('M3_'+bname+'_37_dates_12_groups',exact_grid(x,['date','grp'],[D_ALL,MAIN_GROUPS]))
        check('M3_'+bname+'_baseline_tag',bool(x.baseline.eq(bname).all()))
        check('M3_'+bname+'_0725_flag',bool(x.hour_matched.eq(x.date.eq('2021-07-25').astype(int)).all()))
        for metric in ['rP','rN','rm','rP_idcorr']:
            a=pd.to_numeric(x[metric],errors='coerce');lo=pd.to_numeric(x['ci_'+metric+'_lo'],errors='coerce');hi=pd.to_numeric(x['ci_'+metric+'_hi'],errors='coerce')
            good=lo.notna()&hi.notna()
            check('M3_'+bname+'_'+metric+'_nonnegative',bool(a.dropna().ge(0).all()))
            check('M3_'+bname+'_'+metric+'_CI_order',bool((lo[good]<=hi[good]+.000001).all()) and bool(lo.dropna().ge(0).all()))
            known=x.grp.ne('unreadable') & pd.to_numeric(x.plates,errors='coerce').ge(10) & a.notna()
            check('M3_'+bname+'_'+metric+'_CI_when_observed',bool(lo[known].notna().all()) and bool(hi[known].notna().all()))
        # Group record totals are not suppressed vehicle counts and can be
        # checked on all 37 dates, including the prescribed afternoon on 7/25.
        z=x.set_index(['date','grp'])
        for d in D_ALL:
            n,_=device_vectors(d,bname,True,dh,dd)
            expected=n.reindex(stable_ids).sum()
            actual=float(z.loc[(d,'all'),'records'])+float(z.loc[(d,'unreadable'),'records'])
            check('M3_'+bname+'_'+d+'_records_match_Sstar',abs(actual-expected)<.1)
        record_ratio=x.records/pd.to_numeric(x.baseline_records,errors='coerce')
        good=np.isfinite(record_ratio)&np.isfinite(x.rN)
        check('M3_'+bname+'_rN_definition',np.allclose(record_ratio[good],x.loc[good,'rN'],atol=.000051,rtol=0))
        p=pd.to_numeric(x.plates,errors='coerce');bp=pd.to_numeric(x.baseline_plates,errors='coerce')
        good=p.notna()&bp.notna()&bp.gt(0)&np.isfinite(x.rP)
        bound=.000051+(p[good]*.000051)/(bp[good]*(bp[good]-.000051))
        check('M3_'+bname+'_rP_definition_known_counts',bool((abs(p[good]/bp[good]-x.loc[good,'rP'])<=bound).all()))
        pp=pd.to_numeric(x.passes_per_plate,errors='coerce');bm=pd.to_numeric(x.baseline_mean_passes,errors='coerce')
        good=pp.notna()&bm.gt(.000051)&np.isfinite(x.rm)
        bound=.000051+.000051/(bm[good]-.000051)+abs(pp[good])*.000051/(bm[good]*(bm[good]-.000051))
        check('M3_'+bname+'_rm_frozen_mean_daily_operator',bool((abs(pp[good]/bm[good]-x.loc[good,'rm'])<=bound).all()))
        for metric,reported in [('rP','log_decomp_rP'),('rm','log_decomp_rm')]:
            good=x[metric].gt(.000051)&x[reported].notna()
            bound=.000051+np.log1p(.000051/(x.loc[good,metric]-.000051))
            check('M3_'+bname+'_'+reported+'_serialization_consistent',bool((abs(np.log(x.loc[good,metric])-x.loc[good,reported])<=bound).all()))
        # The frozen mean(N/P) does not generally make the log identity exact.
        # Verify its disclosed residual, and the labelled aggregate diagnostic.
        for rmcol,reported in [('rm','log_identity_residual'),('rm_ratio_of_aggregate_sensitivity',None)]:
            good=x.rN.gt(.000051)&x.rP.gt(.000051)&x[rmcol].gt(.000051)
            residual=np.log(x.loc[good,'rN'])-np.log(x.loc[good,'rP'])-np.log(x.loc[good,rmcol])
            target=x.loc[good,reported] if reported else np.zeros(int(good.sum()))
            bound=.000051+sum(np.log1p(.000051/(x.loc[good,m]-.000051)) for m in ['rN','rP',rmcol])
            check('M3_'+bname+'_'+rmcol+'_log_semantics',bool((abs(residual-target)<=bound).all()))
    margins=read('04_m3_vehicles/m3_two_margins_table.csv')
    check('M3_two_margins_all_arms',exact_grid(margins,['date','baseline','grp'],[E_T[:6],['B1','B2','B3'],MAIN_GROUPS]))
    exact=v['H1']['2021-07-26_local_minus_other']
    stop=any(np.sign(exact[b][m])!=np.sign(exact['B1'][m]) for b in ['B2','B3'] for m in ['rP','rm'])
    check('H1_frozen_stop_rule',bool(v['H1']['stop_condition_triggered'])==bool(stop))
    curve=read('04_m3_vehicles/m3_return_curve.csv')
    check('return_all_540_arms',exact_grid(curve,['window','thr','k','grp'],[['typhoon','placebo'],[6,8,9],list(range(1,10)),CURVE_GROUPS]))
    check('return_lag_weekday_dates',all(row.date==(E_T if row.window=='typhoon' else E_P)[int(row.k)-1] for row in curve.itertuples()))
    count=pd.to_numeric(curve.n_regular,errors='coerce')
    check_probability_table(check,'return',curve,['present','cum'],count.ge(10))
    monotone=all(np.all(np.diff(g.sort_values('k').cum.dropna().values)>=-.000001) for _,g in curve.groupby(['window','thr','grp']))
    check('return_cumulative_monotone',monotone)
    check('return_same_regular_count_over_k',bool(curve.groupby(['window','thr','grp']).n_regular.nunique(dropna=False).eq(1).all()))
    gap=read('04_m3_vehicles/m3_return_gap.csv')
    check('return_gap_all_270_arms',exact_grid(gap,['thr','k','grp'],[[6,8,9],list(range(1,10)),CURVE_GROUPS]))
    check('return_gap_signed_identity',np.allclose(gap.gap,gap.present_typhoon-gap.present_placebo,atol=.000151,rtol=0,equal_nan=True) and np.allclose(gap.deficit,-gap.gap,atol=.000051,rtol=0,equal_nan=True))
    for thr in [6,8,9]:
        for group in CURVE_GROUPS:
            z=gap[(gap.thr==thr)&(gap.grp==group)].sort_values('k')
            declared=v['H2']['first_k_gap_le_005'][str(thr)][group]
            possible=z[z.deficit<=.050051];definite=z[z.deficit<=.049949]
            lower=int(possible.k.iloc[0]) if len(possible) else None
            upper=int(definite.k.iloc[0]) if len(definite) else None
            valid=(declared is None and upper is None) or (declared is not None and lower is not None and declared>=lower and (upper is None or declared<=upper))
            check('return_first_gap_'+str(thr)+'_'+group,valid)
    comp=read('04_m3_vehicles/m3_composition.csv')
    check('composition_all_54_arms',len(comp)==54 and not comp.duplicated(['window','thr','date']).any() and
          all(set(g.date)==set(E_T if window=='typhoon' else E_P) for (window,thr),g in comp.groupby(['window','thr'])) and
          set(comp.thr)=={6,8,9} and set(comp.window)=={'typhoon','placebo'})
    check('composition_shares_sum_one',np.allclose(comp[['share_'+c for c in CLASSES]].sum(axis=1),1,atol=.000251,rtol=0))
    check_probability_table(check,'composition',comp,['share_'+c for c in CLASSES],pd.to_numeric(comp.plates,errors='coerce').ge(10))
    paired=read('04_m3_vehicles/m3_h2_composition_placebo.csv')
    check('composition_paired_all_135_arms',exact_grid(paired,['thr','k','class'],[[6,8,9],list(range(1,10)),CLASSES]))
    check_probability_table(check,'composition_paired',paired,['share_typhoon','share_placebo'],
          pd.to_numeric(paired.plates_visible_typhoon,errors='coerce').ge(10)&pd.to_numeric(paired.plates_visible_placebo,errors='coerce').ge(10))
    check('composition_paired_gap_identity',np.allclose(paired.gap,paired.share_typhoon-paired.share_placebo,atol=.000151,rtol=0,equal_nan=True))
    trends=read('04_m3_vehicles/m3_h2_composition_trends.csv')
    check('composition_trends_all_30_arms',exact_grid(trends,['thr','class','k_start'],[[6,8,9],CLASSES,[1,2]]) and trends.k_end.eq(9).all())
    for metric in ['gap']:
        lo=paired[metric+'_lo'];hi=paired[metric+'_hi'];known=lo.notna()&hi.notna()
        check('composition_paired_'+metric+'_CI_order',bool((lo[known]<=hi[known]+.000001).all()))
    for prefix in ['typhoon','placebo','typhoon_minus_placebo']:
        for metric in ['change','slope_per_day']:
            col=prefix+'_'+metric;lo=trends[col+'_lo'];hi=trends[col+'_hi']
            check('composition_trend_'+col+'_actual_CI',bool(trends[col].notna().all()) and bool(lo.notna().all()) and bool(hi.notna().all()) and bool((lo<=hi+.000001).all()))
    for metric in ['change','slope_per_day']:
        check('composition_trend_'+metric+'_difference_identity',np.allclose(trends['typhoon_minus_placebo_'+metric],trends['typhoon_'+metric]-trends['placebo_'+metric],atol=.000151,rtol=0,equal_nan=True))
    first=read('04_m3_vehicles/m3_first_hour.csv')
    check('first_hour_all_37_dates',set(first.date)==set(D_ALL) and not first.date.duplicated().any())
    check('first_hour_quantile_order',bool((first[['p10','p25','p50','p75','p90']].diff(axis=1).iloc[:,1:]>=-.000001).all().all()))

def m6_checks(check):
    baseline=read('07_m6_robustness/m6_baseline_sensitivity.csv')
    check('M6_baseline_uniform_long_schema',baseline.columns.tolist()==['module','date','baseline','grp','metric','value'])
    m2=baseline[baseline.module.eq('M2')];m3=baseline[baseline.module.eq('M3')]
    check('M6_baseline_all_33_actual_values',len(baseline)==33 and baseline.value.notna().all() and exact_grid(m2,['date','baseline','metric'],[dates('2021-07-26','2021-07-28'),['B1','B2','B3'],['R_stable']]) and exact_grid(m3,['date','baseline','grp','metric'],[['2021-07-26'],['B1','B2','B3'],['all','local_zheD','zhejiang_other','other_province'],['rP','rm']]))
    actual=[]
    for row in baseline.itertuples():
        stem='03_m2_two_sources/m2_daily_ratios' if row.module=='M2' else '04_m3_vehicles/m3_daily_by_group'
        source=read(stem+('' if row.baseline=='B1' else '_'+row.baseline)+'.csv')
        selected=source[source.date.eq(row.date)]
        if row.module=='M3':selected=selected[selected.grp.eq(row.grp)]
        actual.append(len(selected)==1 and abs(float(selected.iloc[0][row.metric])-row.value)<=.000001)
    check('M6_baseline_values_equal_main_results',all(actual))
    th=read('07_m6_robustness/m6_threshold_sensitivity.csv')
    check('M6_threshold_contains_curves_and_composition',set(th.row_type)=={'return_curve','composition'} and len(th[th.row_type=='return_curve'])==540 and len(th[th.row_type=='composition'])==54)
    online=read('07_m6_robustness/m6_online_set_variant.csv');raw=read('07_m6_robustness/m6_online_set_variant_vehicles.csv')
    check('M6_online_both_modules',set(online.module)=={'M2','M3'} and len(online[online.module=='M2'])==111 and len(online[online.module=='M3'])==len(raw)==324)
    check('M6_online_vehicle_all_arms',exact_grid(online[online.module=='M3'],['date','baseline','grp'],[E_T,['B1','B2','B3'],MAIN_GROUPS]))
    check('M6_online_vehicles_full_numbers_preserved',same_rows(online[online.module=='M3'],raw,['date','baseline','grp'],list(raw.columns)))
    for b in ['B1','B2','B3']:
        x=online[(online.module=='M2')&(online.baseline==b)].set_index('date')
        source=read('03_m2_two_sources/m2_daily_ratios'+('' if b=='B1' else '_'+b)+'.csv').set_index('date')
        check('M6_online_M2_'+b+'_all_days_actual',set(x.index)==set(D_ALL) and np.allclose(x.R_online.reindex(D_ALL),source.R_online.reindex(D_ALL),equal_nan=True,atol=.000001,rtol=0) and np.allclose(x.R_stable_reference.reindex(D_ALL),source.R_stable.reindex(D_ALL),equal_nan=True,atol=.000001,rtol=0))
    for row_type,rel,keys in [('return_curve','04_m3_vehicles/m3_return_curve.csv',['window','thr','k','grp']),('composition','04_m3_vehicles/m3_composition.csv',['window','thr','date'])]:
        source=read(rel)
        check('M6_threshold_'+row_type+'_actual_values_preserved',same_rows(th[th.row_type.eq(row_type)],source,keys,list(source.columns)))
    ice=read('07_m6_robustness/m6_exclude_nev.csv')
    check('M6_exclude_NEV_all_days_four_groups',exact_grid(ice,['date','grp'],[D_ALL,['all_ICE','local_zheD_ICE','zhejiang_other_ICE','other_province_ICE']]))
    ident=read('07_m6_robustness/m6_identification_correction.csv')
    check('M6_identification_all_4_days_all_groups',exact_grid(ident,['date','grp'],[E_T[:4],MAIN_GROUPS]) and {'rP','rP_idcorr'}.issubset(ident.columns))
    matrix=read('07_m6_robustness/m6_robustness_matrix.csv')
    check('M6_matrix_no_pending_labels',not matrix.status.astype(str).str.contains('pending|待|未完成',case=False).any())
    for hypothesis in ['H1','H2','H3','H4','M6_gateway']:
        check('M6_matrix_'+hypothesis+'_present',matrix.hypothesis.eq(hypothesis).any())
    h1=matrix[matrix.hypothesis.eq('H1')]
    check('M6_H1_all_variant_families',all(h1.variant.astype(str).str.contains(term,regex=False).any() for term in ['B2','B3','exclude_nev','S_on','identification_correction','lag_matched_placebo']))
    check('M6_H1_real_numeric_effects',h1[['reference_effect','effect']].notna().all().all())
    check('M6_H2_all_thresholds',set(matrix[matrix.hypothesis=='H2'].thr.dropna().astype(int))=={6,8,9})
    ordinary=matrix.status.isin(['稳定','方向一致但幅度变','翻转'])
    known=ordinary & matrix.reference_effect.notna() & matrix.effect.notna()
    # Censored ordering rows use bounds and separately stored signs.
    known &= matrix.metric.ne('first_k_local_minus_nonlocal')
    expected=[]
    for _,r in matrix[known].iterrows():
        if np.sign(r.reference_sign)!=np.sign(r.effect_sign):expected.append('翻转')
        elif round(r.reference_effect,4)==round(r.effect,4):expected.append('稳定')
        else:expected.append('方向一致但幅度变')
    check('M6_status_labels_follow_numeric_effects',matrix.loc[known,'status'].tolist()==expected)
    check('M6_status_sign_columns_match_numbers',all(bool(((matrix.loc[known,number].abs()<=.000051) |
          (np.sign(matrix.loc[known,number])==matrix.loc[known,sign])).all()) for number,sign in
          [('reference_effect','reference_sign'),('effect','effect_sign')]))
    na=matrix.loc[matrix.effect.isna()|matrix.reference_effect.isna()]
    check('M6_NA_effects_explicit',bool((na.status.str.contains('NA|右删失|描述性')|na.metric.eq('first_k_local_minus_nonlocal')).all()))
    sync=jread('07_m6_robustness/m6_gateway_sync.json')
    check('M6_gateway_all_four_correlations',set(sync)=={'flow_between_sets','outside_plates_between_sets','gateway_flow_vs_outside_plates','nongateway_flow_vs_outside_plates'} and all(finite_rho(v) for v in sync.values()))
    consolidation=jread('00_env/m6_consolidate_execution.json')
    check('M6_consolidation_completed',consolidation.get('status')=='complete' and all(consolidation.get('checks',{}).values()))

def same_rows(left,right,keys,columns):
    left=left.set_index(keys).sort_index();right=right.set_index(keys).sort_index()
    if not left.index.equals(right.index):return False
    for col in [c for c in columns if c not in keys]:
        a=left[col];b=right[col]
        if pd.api.types.is_numeric_dtype(b):
            if not np.allclose(pd.to_numeric(a,errors='coerce'),b,atol=.000001,rtol=0,equal_nan=True):return False
        elif not a.fillna('').astype(str).equals(b.fillna('').astype(str)):return False
    return True

def finite_rho(value):
    rho=value.get('spearman',value.get('rho'))
    p=value.get('p')
    finite=lambda v:v is not None and np.isfinite(float(v))
    valid_pair=(finite(rho) and finite(p) and -1<=float(rho)<=1 and 0<=float(p)<=1) or (not finite(rho) and not finite(p))
    return bool(valid_pair and value.get('n_days')==9)

def complete_stage_checks(check):
    taxi=jread('00_env/taxi_grid_checks.json')
    check('taxi_source_all_290_workbooks',taxi.get('workbooks')==290 and taxi.get('verified_workbooks')==290 and taxi.get('verified_complete') is True)
    for k in ['source_metadata_unchanged','valid_point_sums_equal','moving_points_no_greater_than_points']:
        check('taxi_'+k,taxi.get(k) is True)
    check('taxi_all_sheets_accounted',taxi.get('sheets_seen')==taxi.get('sheets_parsed',0)+taxi.get('sheets_empty',0))
    check('taxi_frozen_projection_filter',taxi.get('crs')=='EPSG:32651' and taxi.get('grid_metres')==1000 and taxi.get('bbox')==[120.3,121.4,29.5,30.5])
    check('taxi_actual_second_batch_period',taxi.get('date_min')=='2021-07-06' and taxi.get('date_max')=='2021-07-31')
    for rel,col in [('01_panels/taxi_grid_day.csv','n_vehicles'),('01_panels/taxi_hour_valid.csv','taxi_vehicles_moving')]:
        value=pd.to_numeric(read(rel)[col],errors='coerce')
        check(rel+'_small_vehicle_counts_suppressed',not bool((value.notna()&value.lt(10)).any()))
    execution=jread('00_env/bias_execution.json')
    check('M5_final_complete_and_frozen_seed',execution.get('status')=='complete' and execution.get('seed')==20261005 and execution.get('local_inputs_unchanged') is True)
    for row in execution.get('input_files_after',[]):
        path=Path(row['path'])
        # Final public formatting can legitimately rewrite module CSVs; exact
        # local input panels must still be those used by the final M5 run.
        if '01_panels' in path.parts:
            stat=path.stat()
            check('M5_current_input_'+path.name,row['size']==stat.st_size and row['mtime_ns']==stat.st_mtime_ns)
    cross=jread('00_env/m5_crosschecks.json')
    check('M5_all_cross_artifact_checks_pass',cross.get('status')=='pass' and len(cross.get('checks',[]))>=43 and all(r.get('passed') is True for r in cross.get('checks',[])))
    h4=jread('06_m5_bias_correction/m5_h4_verdict.json')
    check('H4_final_actual_verdict',h4.get('H4') in ['pass','fail','degraded','mixed'])
    tests=read('06_m5_bias_correction/m5_failure_nonrandomness.csv').set_index(['date','test'])
    dual=(tests.loc[('2021-07-26','joincount_knn6'),'p_perm']>.05 and tests.loc[('2021-07-26','mean_log_base_diff'),'p_perm']>.05)
    check('H4_frozen_dual_p_stop',bool(h4.get('stop_condition_triggered'))==bool(dual))
    ref=jread('00_env/reference_revalidation.json')
    # The exact check schema is set by the source-independent reference reader;
    # forbid incomplete/false checks while retaining its detailed comparisons.
    refchecks=ref.get('checks',{})
    check('reference_revalidation_actual_checks',ref.get('passed') is True and bool(refchecks) and
          all(v.get('matches_frozen_reference') is True for v in refchecks.values()) and ref.get('before')==ref.get('after'))
    invariant=jread('00_env/spatial_refresh_set_invariance.json')
    check('coordinate_refresh_frozen_sets_unchanged',invariant.get('device_index_unchanged') is True and
          invariant.get('all_observation_sets_unchanged') is True and invariant.get('coordinate_refresh_changes_vehicle_aggregation') is False and
          all(invariant.get('checks',{}).get(k,{}).get('unchanged') is True for k in ['in_A100','in_A200','in_Sstar','online_sets']))
    results=jread('results.json')
    check('overall_actual_status_not_pending',results.get('status')=='complete')
    count_fields=['devices','devices_any','records','plates','plates_all','plates_Sstar','taxi_vehicles','taxi_vehicles_reporting']
    check('machine_coverage_count_types_int_or_null',all(
        value is None or type(value) is int or value=='<10'
        for row in results.get('coverage',{}).values()
        for value in [row.get(name) for name in count_fields]))

def main():
    checks={};failures=[]
    def check(name,passed,detail=None):
        checks[name]=dict(passed=bool(passed),detail=detail)
        if not passed:failures.append(name)
    extra=['01_panels/device_id_map.csv','01_panels/record_count_checks.csv','01_panels/plate_day_summary.csv',
           '04_m3_vehicles/m3_h2_composition_placebo.csv','04_m3_vehicles/m3_h2_composition_trends.csv',
           '06_m5_bias_correction/m5_leaveout_replicates.csv','06_m5_bias_correction/m5_leaveout_by_flow_quantile_replicates.csv',
           '06_m5_bias_correction/m5_leaveout_by_flow_quantile_flowweighted.csv',
           '07_m6_robustness/m6_online_set_variant_vehicles.csv','07_m6_robustness/m6_gateway_sync.json',
           '00_env/vehicle_avi_execution.json','00_env/taxi_grid_checks.json','00_env/bias_execution.json',
           '00_env/m5_crosschecks.json','00_env/m6_consolidate_execution.json','00_env/reference_revalidation.json',
           '00_env/spatial_refresh_set_invariance.json',
           'README.md','EXECUTION_LOG.md','DEVIATIONS.md','RESULTS_SUMMARY.md','results.json']
    missing=missing_deliverables()+[r for r in extra if not (ROOT/r).is_file() or not (ROOT/r).stat().st_size]
    check('all_protocol_deliverables_present',not missing,sorted(set(missing)))
    if missing:
        report=dict(generated_at=now(),seed=SEED,checks=checks,passed=False,failed_checks=failures,source_integrity='not evaluated: required products missing')
        if '--verify-manifest-only' not in sys.argv:write_json(ROOT/'00_env/final_audit.json',report)
        print('Audit missing deliverables',len(missing),flush=True);raise SystemExit(1)
    check('frozen_calendar_and_baselines',D_ALL==['2021-06-17']+dates('2021-06-28','2021-08-02') and
          D_PARTIAL==['2021-07-'+d for d in ['08','10','22','23','24','25']] and
          B1==[d for d in dates('2021-07-05','2021-07-21') if d not in D_PARTIAL] and
          B2==dates('2021-07-12','2021-07-21') and B3==['2021-06-17']+dates('2021-06-28','2021-07-04') and
          B_TAXI==dates('2021-07-06','2021-07-21') and SEED==20261005)
    verified=source_checks(check)
    script_seed_checks(check)
    dh,attr,dd=load_panels()
    check('dates_and_D1',len(dd.columns)==37 and bool((pd.read_csv(ROOT/'01_panels/record_count_checks.csv').difference==0).all()))
    bmean=dd[B1].mean(axis=1)
    check('frozen_A100_A200_exact',bool((bmean.ge(100).astype(int)==attr.in_A100).all()) and bool((bmean.ge(200).astype(int)==attr.in_A200).all()))
    check('B1_device_mean_serialization',np.allclose(bmean,attr.base_B1,atol=.000051,rtol=0))
    stable=attr.in_A100==1
    for d in dates('2021-07-26','2021-07-30'):
        r=dd[d]/dd[refs(d)].mean(axis=1).replace(0,np.nan)
        stable &= r>=.2
        if d in ['2021-07-29','2021-07-30']:stable &= r>=.5
    check('frozen_Sstar_exact',bool((stable.astype(int)==attr.in_Sstar).all()),int(stable.sum()))
    for bname in BASELINES:
        rows=pd.read_csv(ROOT/('03_m2_two_sources/m2_daily_ratios'+('' if bname=='B1' else '_'+bname)+'.csv')).set_index('date')
        check('M2_'+bname+'_all_37_dates',set(rows.index)==set(D_ALL) and not rows.index.duplicated().any())
        for d in D_ALL:
            n,b=device_vectors(d,bname,True,dh,dd)
            on=attr.index[(attr.in_A100==1)&((dd[d]/dd[refs(d)].mean(axis=1).replace(0,np.nan))>=.2)]
            for label,ids in [('R_naive',attr.index[attr.in_A100==1]),('R_online',on),('R_stable',attr.index[attr.in_Sstar==1])]:
                denominator=b.reindex(ids).sum()
                value=n.reindex(ids).sum()/denominator if denominator>0 else np.nan
                check(f'{bname}_{d}_{label}',np.isclose(value,rows.loc[d,label],atol=.000051,rtol=0,equal_nan=True))
    ratios=pd.read_csv(ROOT/'03_m2_two_sources/m2_daily_ratios.csv')
    fig1=pd.read_csv(ROOT/'08_figures/fig1_data.csv')
    merged=ratios.merge(fig1,on='date',suffixes=('_table','_fig'))
    check('fig1_data_matches_ratios',all(np.allclose(merged[c+'_table'],merged[c+'_fig'],equal_nan=True) for c in ['R_naive','R_online','R_stable','R_taxi_km']))
    tx=pd.read_csv(ROOT/'01_panels/taxi_vehicle_day.csv',dtype={'vehicle_hash':str})
    check('taxi_HMAC_only',bool(tx.vehicle_hash.str.fullmatch('[0-9a-f]{16}').all()))
    for label,section in [('vehicle_semantics',lambda:vehicle_checks(check,dh,attr,dd)),
                          ('M6_semantics',lambda:m6_checks(check)),('stage_completion',lambda:complete_stage_checks(check))]:
        try:section()
        except Exception as exc:check(label+'_schema_or_semantic_exception',False,type(exc).__name__)
    vehicle_cols={'taxi_vehicles_moving','taxi_vehicles_reporting','taxi_vehicles_active','n_vehicles','plates','baseline_plates','plates_all','plates_Sstar','n_regular','n_other_plates','n_local_plates'}
    small=[];plate_hits=[];coord_hits=[];raw_dev_hits=[]
    plate_re=re.compile(r'[京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼港澳使领][A-Z][A-Z0-9]{5,6}')
    raw_names=pd.read_csv(ROOT/'01_panels/device_id_map.csv').dev_name.dropna().astype(str).tolist()
    for dirname in ['02_m1_observation','03_m2_two_sources','04_m3_vehicles','05_m4_spatial','06_m5_bias_correction','07_m6_robustness','08_figures']:
        for p in (ROOT/dirname).glob('*'):
            if not p.is_file() or p.suffix not in ['.csv','.json','.md','.log']:continue
            s=p.read_text(encoding='utf-8-sig')
            if plate_re.search(s):plate_hits.append(str(p.relative_to(ROOT)))
            if p.suffix=='.csv':
                df=pd.read_csv(p)
                # OSM road names may coincide with a short camera name. They are a
                # prescribed road covariate, not a leaked device identifier.
                unsafe_cols=[c for c in df if c not in ['osm_road_name','road_level','near_town','org','dev_type']]
                if any(df[c].astype(str).isin(raw_names).any() for c in unsafe_cols):raw_dev_hits.append(str(p.relative_to(ROOT)))
                for c in df:
                    if c in vehicle_cols or (c.startswith('plates_') and not any(t in c for t in ['ratio','share','log','ci_'])):
                        vals=pd.to_numeric(df[c],errors='coerce');bad=vals.notna()&(vals<10)
                        if bad.any():small.append(dict(file=str(p.relative_to(ROOT)),column=c,n_cells=int(bad.sum())))
                for c in ['lon','lat','plot_lon','plot_lat']:
                    if c in df:
                        vals=pd.to_numeric(df[c],errors='coerce').dropna()
                        if not np.allclose(vals*100,np.round(vals*100),atol=.00001,rtol=0):coord_hits.append(str(p.relative_to(ROOT)))
                check(str(p.relative_to(ROOT))+'_no_vehicle_identifiers',not any(c in df.columns for c in ['ph','vehicle_hash','HPHM','司机','营运证号','终端']))
                for c in [c for c in df if c=='date' or c.startswith('date_') or c.endswith('_date')]:
                    x=df[c].dropna().astype(str)
                    check(str(p.relative_to(ROOT))+'_'+c+'_ISO_dates_or_declared_censor',bool(x.str.fullmatch(r'\d{4}-\d{2}-\d{2}|not_by_0802').all()))
            elif any(name in s for name in raw_names if len(name)>=8):raw_dev_hits.append(str(p.relative_to(ROOT)))
    check('no_raw_plate_in_public_outputs',not plate_hits,plate_hits)
    check('no_raw_device_in_public_outputs',not raw_dev_hits,raw_dev_hits)
    check('public_coordinates_001',not coord_hits,coord_hits)
    check('vehicle_counts_lt10_suppressed',not small,small)
    env_plate_hits=[]
    for p in (ROOT/'00_env').glob('*'):
        if p.is_file() and p.suffix in ['.csv','.json','.md','.log'] and plate_re.search(p.read_text(encoding='utf-8-sig',errors='replace')):
            env_plate_hits.append(str(p.relative_to(ROOT)))
    check('no_raw_plate_in_environment_records',not env_plate_hits,env_plate_hits)
    from PIL import Image
    for stem,alias in FIGURE_ALIASES.items():
        left=ROOT/'08_figures'/(stem+'_data.csv');right=ROOT/'08_figures'/(alias+'.csv')
        check(stem+'_underlying_data_alias_identical',left.read_bytes()==right.read_bytes())
        with Image.open(ROOT/'08_figures'/(stem+'.png')) as im:
            dpi=im.info.get('dpi',(0,0));check(stem+'_at_least_160dpi',min(dpi)>=159.99,list(dpi))
    for rel in ['06_m5_bias_correction/m5_leaveout_validation.csv','06_m5_bias_correction/m5_leaveout_validation_flowweighted.csv']:
        x=pd.read_csv(ROOT/rel);check(rel+'_20_rows_200_reps',len(x)==20 and bool((x.n_reps==200).all()))
        if 'device_level_mae' in x:check(rel+'_drop_device_MAE_NA',bool(x.loc[x.method=='drop','device_level_mae'].isna().all()))
    n=pd.read_csv(ROOT/'06_m5_bias_correction/m5_failure_nonrandomness.csv');check('18_failure_tests',len(n)==18)
    check('M4_M5_joincount_identical',all(abs(n[(n.date==d)&(n.test=='joincount_knn6')].observed.iloc[0]-json.loads((ROOT/'05_m4_spatial/m4_moran.json').read_text(encoding='utf-8'))['joincount'][d]['observed'])<1e-9 for d in ['2021-07-26','2021-07-28','2021-08-02']))
    if '--skip-manifest' not in sys.argv:
        man=json.loads((ROOT/'09_manifest/manifest.json').read_text(encoding='utf-8'))
        errors=[]
        for r in man['files']:
            p=ROOT/r['path'];h=hashlib.sha256(p.read_bytes()).hexdigest()
            if h!=r['sha256'] or p.stat().st_size!=r['size']:errors.append(r['path'])
        check('delivery_sha256_current',not errors,errors)
        check('key_not_in_manifest',not any('.hmac_key' in r['path'] for r in man['files']))
    report=dict(generated_at=now(),seed=SEED,checks=checks,passed=not failures,failed_checks=failures,
                source_integrity='verified equal source size, mtime_ns and head/tail SHA256 fingerprints' if verified else 'source fingerprint verification failed or incomplete',
                source_scope='Original NAS and frozen reference fingerprints recorded by the environment stage; this audit does not rescan source files.')
    if '--verify-manifest-only' not in sys.argv:write_json(ROOT/'00_env/final_audit.json',report)
    print('Audit checks',len(checks),'passed',not failures,'failures',json.dumps(failures),flush=True)
    if failures:raise SystemExit(1)
if __name__=='__main__':main()
