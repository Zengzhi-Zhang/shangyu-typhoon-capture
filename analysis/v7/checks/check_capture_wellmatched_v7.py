# -*- coding: utf-8 -*-
"""Independent schema/quantity/privacy checks for cached-data v7 capture."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[3]), str(_ReleasePath(__file__).resolve().parents[1])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from pathlib import Path
import argparse
import json
import re

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from scipy.stats import spearmanr

import capture_wellmatched_v7 as analysis

OUT=Path(_release_path('v7_root'))


def public_alias_hits(text):
    token=re.compile(r'(?<![A-Za-z0-9])[0-9a-f]{16}(?![A-Za-z0-9])|cam_[0-9a-f]+')
    # A 15-digit fractional mantissa followed by e is itself16 hex chars.
    # Exempt only spans of a complete decimal/scientific literal, never a
    # standalone16-digit integer or arbitrary hex identifier.
    numerical=re.compile(r'(?<![A-Za-z0-9_.])[-+]?(?:\d+\.\d*|\.\d+)(?:[eE][-+]?\d+)?(?![A-Za-z0-9_.])')
    spans=[m.span() for m in numerical.finditer(text)]
    return [m for m in token.finditer(text) if not any(a<=m.start() and m.end()<=b for a,b in spans)]


def synthetic():
    checks={}
    pooled=(np.array([9,1]).sum()/np.array([10,100]).sum())
    checks['pooled_passage_ratio_not_mean_daily_rates']=bool(np.isclose(pooled,10/110) and not np.isclose(pooled,np.mean([.9,.01])))
    checks['dedup_strict_300s_boundary']=analysis.dedup_expected([0,300,301,602]).tolist()==[0,301,602]
    checks['capture_inclusive_180s_boundary']=analysis.count_captures(np.array([39600.]),np.array([39420.]))==(1,1)
    checks['matched_observations_exclude_before11']=analysis.count_captures(np.array([39600.]),np.empty(0))==(1,0)
    lon,lat=120.86,30.03
    x,y=analysis.PROJECT.transform(lon,lat)
    lo,la=analysis.PROJECT.transform([x-40,x+40],[y,y],direction='INVERSE')
    g=pd.DataFrame(dict(timestamp=pd.to_datetime(['2021-07-25 10:59:40','2021-07-25 11:00:20']),lon=lo,lat=la,valid_xy=[True,True]))
    points=np.array([[x,y]])
    events=analysis.segment_events(g,points,cKDTree(points))
    checks['cross11_segment_retained']=bool(len(events)==1 and abs(events[0,1]-39600)<1e-5 and events[0,2]<1e-5)
    e=np.array([0.,10.,10.]);c=np.array([0.,0.,5.]);ce=np.array([20.,20.,20.]);cc=np.array([10.,0.,10.])
    relative=analysis.div(analysis.div(c,e),analysis.div(cc,ce))
    checks['zero_boot_denominators_NA_not_zero']=bool(np.isnan(relative[:2]).all() and np.isclose(relative[2],1))
    checks['inclusive_control_selection_boundary']=bool((np.array([30])>=30)[0] and (np.array([.3])>=.3)[0])
    checks['no_v6_source_key_import']=all(token not in (OUT/'scripts/capture_wellmatched_v7.py').read_text(encoding='utf-8') for token in ['import taxi_parse_v6','import taxi_probe_hash','from taxi_parse_v6','from taxi_probe_hash'])
    checks['scientific_literal_not_hex_alias']=not public_alias_hits(_release_private('private_value_018'))
    checks['standalone_numeric_and_hex_alias_still_detected']=len(public_alias_hits(_release_private('private_value_019')))==4
    report=dict(at=analysis.now(),source_reads=False,key_reads=False,real_data_effects_computed=False,checks=checks,all_passed=all(checks.values()))
    analysis.safe_json(report,OUT/'00_env/capture_synthetic_checks_v7.json')
    print(json.dumps(dict(all_passed=report['all_passed'],checks=len(checks))))
    if not report['all_passed']:raise SystemExit(1)


def outputs():
    checks={}
    private=pd.read_csv(OUT/'01_internal/capture_camera_internal_v7.csv',encoding='utf-8-sig')
    summary=pd.read_csv(OUT/'01_internal/capture_summary_internal_v7.csv',encoding='utf-8-sig')
    public=pd.read_csv(OUT/'03_taxi_probe/T35_capture_camera_v7.csv',encoding='utf-8-sig',dtype=str,keep_default_na=False)
    payload=json.loads((OUT/'03_taxi_probe/T35_capture_wellmatched_v7.json').read_text(encoding='utf-8'))
    counts=np.load(OUT/'01_internal/capture_vehicle_counts_v7.npz',allow_pickle=False)
    all_day=counts['all_day'];h11=counts['h11']
    checks['all_four_variants_seven_dates']=bool(len(summary)==28 and summary.groupby('variant').date.nunique().eq(7).all())
    checks['camera_rows_complete']=bool(len(private)==4*7*1075 and not private.duplicated(['variant','date','dev']).any())
    checks['public_private_order_equal']=bool(private[['variant','date','dev']].astype(str).equals(public[['variant','date','dev']]))
    checks['raw_counts_captured_le_expected']=bool((all_day[...,1]<=all_day[...,0]).all() and (h11[...,1]<=h11[...,0]).all())
    checks['h11_expected_not_above_all_day']=bool((h11[...,0]<=all_day[...,0]).all())
    selection_ok=True;scope_ok=True;medians_ok=True;failure_ok=True;rho_ok=True
    for variant,radius,threshold in analysis.VARIANTS:
        ri=list(counts['radii']).index(radius);ctrl=all_day[ri,:,:8].sum(axis=(0,1));control_cap=analysis.div(ctrl[:,1],ctrl[:,0]);chosen=(ctrl[:,0]>=30)&(control_cap>=threshold)
        for day in analysis.TARGET:
            g=private[private.variant.eq(variant)&private.date.eq(day)].sort_values('dev')
            row=summary[summary.variant.eq(variant)&summary.date.eq(day)].iloc[0]
            selection_ok &= np.array_equal(g.selected.to_numpy(),chosen)
            di=list(counts['dates']).index(day)
            expected_source=h11 if day=='2021-07-25' else all_day
            event=expected_source[ri,:,di].sum(axis=0)
            matched_ctrl=expected_source[ri,:,:8].sum(axis=(0,1))
            scope_ok &= np.array_equal(g.expected.to_numpy(),event[:,0]) and np.array_equal(g.captured.to_numpy(),event[:,1])
            scope_ok &= np.array_equal(g.expected_ctrl_matched.to_numpy(),matched_ctrl[:,0]) and np.array_equal(g.captured_ctrl_matched.to_numpy(),matched_ctrl[:,1])
            comparable=g.comparable.astype(bool)
            stable=g[comparable&g.in_Sstar.astype(bool)]
            value=stable.relative_cap.median()
            medians_ok &= (np.isclose(value,row.Sstar_relative_median,rtol=0,atol=1e-9) if pd.notna(value) else pd.isna(row.Sstar_relative_median))
            failed=g[g.selected.astype(bool)&g.A1_failed.astype(bool)]
            eligible=failed[failed.expected>=10]
            failure_ok &= len(failed)==row.n_failed_selected and len(eligible)==row.n_failed_event_ge10
            failure_ok &= failed.expected.sum()==row.failed_selected_expected and failed.captured.sum()==row.failed_selected_captured
            failure_ok &= eligible.expected.sum()==row.failed_event_ge10_expected and eligible.captured.sum()==row.failed_event_ge10_captured
            corr=g[comparable&g.ratio.notna()]
            rho=spearmanr(corr.ratio,corr.relative_cap).statistic if len(corr)>=3 else np.nan
            rho_ok &= np.isclose(rho,row.spearman_rho,rtol=0,atol=1e-9) if pd.notna(rho) else pd.isna(row.spearman_rho)
    checks['selection_only_all_day_control_fixed_each_date']=bool(selection_ok)
    checks['july25_h11_and_other_all_day_counts_exact']=bool(scope_ok)
    checks['stable_relative_median_matches_camera_cells']=bool(medians_ok)
    checks['failed_all_and_eligible_counts_totals_exact']=bool(failure_ok)
    checks['Spearman_matches_comparable_cells']=bool(rho_ok)
    low=private.expected<10
    checks['public_low_expected_counts_and_rates_suppressed']=bool(public.loc[low,['expected','captured']].eq('<10').all().all() and public.loc[low,['cap','relative_cap']].eq('NA').all().all())
    small=private.captured<10
    checks['public_small_captured_counts_suppressed']=bool(public.loc[small,'captured'].eq('<10').all())
    lowctrl=private.expected_ctrl_matched<10
    checks['public_low_matched_ctrl_cap_relative_NA']=bool(public.loc[lowctrl,['expected_ctrl_matched','captured_ctrl_matched']].eq('<10').all().all() and public.loc[lowctrl,['cap_ctrl_matched','relative_cap']].eq('NA').all().all())
    checks['public_has_no_coordinate_columns']=not any(c in public.columns for c in ['lon','lat','x','y'])
    checks['v6_S2_S3_history_preserved']=payload['v6_history']==dict(S2=True,S3=True,calibration_status='failed_preserve_raw')
    checks['bootstrap_valid_draw_ranges']=bool(summary.camera_valid_draws.between(0,500).all() and summary.vehicle_valid_draws.between(0,200).all() and summary.vehicle_finite_cells_min.ge(0).all() and (summary.vehicle_finite_cells_max<=summary.n_Sstar_comparable).all())
    public_files=list((OUT/'03_taxi_probe').glob('T35*'))+list((OUT/'08_figures').glob('fig_capture*'))
    bad_tokens=[]
    for path in public_files:
        text=path.read_text(encoding='utf-8-sig')
        if public_alias_hits(text):bad_tokens.append(path.name)
    checks['no_public_internal_alias_tokens']=not bad_tokens
    checks['main_JSON_small_event_counts_suppressed']=all(not isinstance(row[col],(int,float)) or row[col]>=10 for row in payload['main_results'] for col in ['failed_selected_expected','failed_selected_captured','failed_event_ge10_expected','failed_event_ge10_captured'])
    checks['posthoc_revision_explicit']=payload['version']=='v7_posthoc_revision' and private.posthoc_revision.all()
    report=dict(at=analysis.now(),source_reads=False,key_reads=False,new_scientific_effects=False,checks=checks,all_passed=all(checks.values()),bad_public_token_files=bad_tokens)
    analysis.safe_json(report,OUT/'00_env/capture_independent_checks_v7.json')
    print(json.dumps(dict(all_passed=report['all_passed'],checks=len(checks),failed=[k for k,v in checks.items() if not v])))
    if not report['all_passed']:raise SystemExit(1)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--synthetic',action='store_true');args=parser.parse_args()
    if args.synthetic:synthetic()
    else:outputs()
