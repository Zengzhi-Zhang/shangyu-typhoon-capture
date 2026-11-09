# -*- coding: utf-8 -*-
"""Post-run integrity/privacy audit; prints only aggregate check results."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[3]), str(_ReleasePath(__file__).resolve().parents[1]), str(_ReleasePath(__file__).resolve().parent)]
from pathlib import Path
import json,re
import numpy as np
import pandas as pd
from spatial_helpers_v6 import ROOT,V3,STATE_ORDER,D_STATE,EVENT,B1,B3,now,sha,write_json

def read(rel):return pd.read_csv(ROOT/rel,encoding='utf-8-sig')

def main():
    checks={}
    state=read('02_device_state/device_state_v6.csv')
    internal=read('01_internal/device_state_internal_v6.csv')
    summary=read('02_device_state/T27_state_summary.csv')
    failed=read('02_device_state/T27_failed_breakdown.csv')
    mp=read('08_figures/fig_state_map_v6_data.csv')
    counts=pd.read_csv(V3/'06_m5_bias_correction/m5_failure_counts_v3.csv',encoding='utf-8-sig').set_index('date')
    n_A200=int(counts.n_A200.iloc[0])
    checks['public_A200_complete_10date_panel']=len(state)==n_A200*10 and set(state.date)==set(D_STATE) and not state.duplicated(['dev','date']).any()
    checks['public_all_dates_same_device_ids']=all(set(q.dev)==set(state[state.date.eq(D_STATE[0])].dev) for _,q in state.groupby('date'))
    checks['public_dev_integer']=bool(pd.to_numeric(state.dev).eq(pd.to_numeric(state.dev).astype(int)).all())
    checks['public_states_only_prespecified']=set(state.state).issubset(STATE_ORDER)
    checks['public_no_internal_id_or_coordinate_columns']=not any(c in state for c in ['dev_public','lon','lat','dev_name'])
    checks['failed_counts_match_frozen_v3']=all(int(q.A1_failed.sum())==int(counts.loc[d,'n_failed_A1']) for d,q in state.groupby('date'))
    checks['summary_counts_partition_A200']=bool(summary.groupby('date').n_devices.sum().eq(n_A200).all())
    checks['summary_weights_close_one']=bool(np.allclose(summary.groupby('date').baseline_flow_share.sum(),1,atol=1e-9))
    checks['failed_counts_partition_official_failed']=bool(failed.groupby('date').n_failed_state.sum().eq(failed.groupby('date').n_failed_A1.first()).all())
    checks['internal_has_all_event_dates']=set(EVENT).issubset(set(internal.date))
    checks['outside_A200_not_classified']=internal.loc[internal.in_A200.eq(0),'state'].eq('not_classified_outside_A200').all()
    checks['hourly_vs_day_nonnegative_unknown_counts']=internal.n_unassigned_hour_full_day.ge(0).all() and internal.n_unread_unassigned_hour_full_day.ge(0).all()
    july25=state[state.date.eq('2021-07-25')]
    checks['July25_raw13hour_signals']=july25.observed_hours.eq(13).all() and july25.hours_recording.le(13).all() and july25.hour_matched.eq(1).all()
    checks['July25_lane_unmatched_explicit']=july25.lane_hour_matched.eq(0).all() and july25.lane_baseline_scope.eq('full_day').all()
    checks['unknown_recognition_not_low_all_channels']=state.loc[state.state.eq('low_all_channels'),'unread_spike'].eq(0).all()
    checks['map_july26_A200_ids_only']=set(mp.date)=={'2021-07-26'} and set(mp.dev).issubset(set(state.dev))
    checks['map_coordinates_2decimals']=np.allclose(mp.plot_lon,mp.plot_lon.round(2)) and np.allclose(mp.plot_lat,mp.plot_lat.round(2))
    membership=read('01_internal/s_pre_devices_v6.csv');members=membership[membership.in_Spre.eq(1)]
    pre=read('06_s_pre/T32_s_pre_v6.csv');sel=read('06_s_pre/T32_s_pre_selection_audit_v6.csv')
    model=read('06_s_pre/T32_s_pre_ols_v6.csv');rings=read('06_s_pre/T32_s_pre_rings_v6.csv')
    checks['Spre_all_selected_rules_pass']=members.in_A100.eq(1).all() and members.n_ratio_failed_pre_days.eq(0).all() and members.n_hours_failed_pre_days.eq(0).all()
    checks['Spre_selected_min_hours20']=members.min_hours_recording_pre.ge(20).all()
    checks['Spre_count_matches_daily']=pre.n_Spre.eq(len(members)).all()
    overlap=int(members.in_Sstar.sum());star=int(membership.in_Sstar.sum());union=len(members)+star-overlap
    checks['Spre_overlap_and_jaccard_correct']=pre.n_overlap_Sstar.eq(overlap).all() and np.allclose(pre.jaccard,overlap/union,atol=1e-10)
    pool=set(B1+B3)
    checks['Spre_only23_pre_dates']=set(sel.date)==pool and len(sel)==23 and all(set(r.leaveout_dates.split(';')).issubset(pool) and r.date not in r.leaveout_dates.split(';') for _,r in sel.iterrows())
    checks['Spre_complete_9event_dates']=pre.date.tolist()==EVENT
    checks['Spre_delta_algebra']=np.allclose(pre.delta_naive_pre,pre.R_naive-pre.R_pre,atol=1e-10)
    checks['Spre_CIs_ordered']=pre.R_pre_ci_lo.le(pre.R_pre_ci_hi).all() and pre.delta_naive_pre_ci_lo.le(pre.delta_naive_pre_ci_hi).all()
    dist=model[model.term.eq('np.log1p(dist_baiguan_km)')]
    checks['Spre_three_distance_models']=set(dist.date)=={'2021-07-26','2021-07-27','2021-07-28'} and len(dist)==3 and dist['sample'].eq('S_pre').all()
    checks['Spre_HC1_completecase_N_valid']=model.covariance.eq('HC1').all() and model.n.le(len(members)).all() and model.n.gt(0).all()
    checks['Spre_ring_CIs_ordered']=rings.r_camera_ci_lo.le(rings.r_camera_ci_hi).all()
    checks['Spre_rings_no_sparse_cells_after_merge']=rings.n_devices.ge(10).all() or len(rings)==1
    public_paths=[ROOT/'02_device_state/device_state_v6.csv',ROOT/'02_device_state/T27_state_summary.csv',
        ROOT/'02_device_state/T27_failed_breakdown.csv',ROOT/'08_figures/fig_state_map_v6_data.csv']
    public_paths+=sorted((ROOT/'06_s_pre').glob('*.csv'))+[ROOT/'08_figures/fig_s_pre_comparison_v6_data.csv']
    token=re.compile(r'(?<![a-fA-F0-9])[a-fA-F0-9]{16}(?![a-fA-F0-9])')
    checks['owned_public_outputs_no_internal_prefix_or_token']=all('cam_' not in p.read_text(encoding='utf-8-sig') and token.search(p.read_text(encoding='utf-8-sig')) is None for p in public_paths)
    checks['owned_public_outputs_no_replacement_character']=all('\ufffd' not in p.read_text(encoding='utf-8-sig') for p in public_paths)
    for name in ['device_state_execution_v6.json','s_pre_execution_v6.json']:
        r=json.loads((ROOT/'00_env'/name).read_text(encoding='utf-8-sig'))
        checks[name+'_input_hashes_unchanged']=all(sha(p)==h for p,h in r['input_sha256'].items())
        checks[name+'_protocol_hash_unchanged']=sha(r['protocol']['path'])==r['protocol']['sha256']
    failures=[str(k) for k,v in checks.items() if not v]
    result=dict(ended=now(),all_passed=not failures,n_checks=len(checks),failed=failures,checks=checks,
        rows=dict(state=len(state),internal_state=len(internal),Spre=len(members),Spre_daily=len(pre),Spre_models=len(model),Spre_rings=len(rings)),
        observed_outputs_changed=False)
    write_json(ROOT/'00_env/spatial_postrun_audit_v6.json',result)
    print(json.dumps(dict(all_passed=not failures,n_checks=len(checks),failed=failures,rows=result['rows'])))
    if failures:raise AssertionError('Post-run I1/I6 audit failed')

if __name__=='__main__':main()
