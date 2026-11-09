# -*- coding: utf-8 -*-
"""T40 and T39 audit coverage from the explicitly allowed frozen tables."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[2]), str(_ReleasePath(__file__).resolve().parents[0])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from pathlib import Path
from datetime import datetime,timezone,timedelta
import hashlib,json,time
import os
import numpy as np,pandas as pd
SYNTHETIC_MODE = os.environ.get('SHANGYU_SYNTHETIC', '') == '1'

B=Path(_release_path('project_root'));R=_ReleasePath(_release_path('v9_output_root'));I=R/'01_internal';E=R/'00_env';SEED=20261005
V7=B/'formal_v7/01_internal';MAIN='main_R60_cap03'
TARGET=[f'2021-07-{d:02d}' for d in range(25,32)]
DATES=TARGET+['2021-08-01','2021-08-02']
CONTROL=[f'2021-07-{d:02d}' for d in range(12,20)]


def now():return datetime.now(timezone(timedelta(hours=8))).isoformat()


def clean(v):
    if isinstance(v,dict):return {str(k):clean(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)):return [clean(x) for x in v]
    if isinstance(v,np.ndarray):return clean(v.tolist())
    if isinstance(v,np.generic):return clean(v.item())
    if isinstance(v,float) and not np.isfinite(v):return None
    return v


def put(path,v):path.write_text(json.dumps(clean(v),ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def flag(s):return s.astype(str).str.lower().isin(['true','1'])


def div(n,d):return np.divide(n,d,out=np.full(np.broadcast_shapes(np.shape(n),np.shape(d)),np.nan),where=np.asarray(d)>0)


def limits(values):
    a=np.asarray(values,float);a=a[np.isfinite(a)]
    return dict(lo=float(np.quantile(a,.025)) if len(a) else np.nan,hi=float(np.quantile(a,.975)) if len(a) else np.nan,valid=len(a))


def count_text(value):
    if pd.isna(value):return 'NA'
    return '<10' if float(value)<10 else str(int(np.floor(float(value)+.5)))


def save_public(frame,path,count_columns):
    f=frame.copy()
    for col in count_columns:
        if col in f:f[col]=f[col].map(count_text)
    f.to_csv(path,index=False,encoding='utf-8-sig',float_format='%.4f',na_rep='NA')


def accepted_bootstrap(groups,master,base_indices):
    """Exact fixed-n subgroup multinomial from common ordered A100 streams."""
    assert base_indices.shape==(500,len(master))
    lookup={int(v):i for i,v in enumerate(master)}
    memberships={};accepted={};filled={}
    for date,ids in groups.items():
        mask=np.zeros(len(master),bool);mask[[lookup[int(i)] for i in ids]]=True
        memberships[date]=mask;accepted[date]=np.empty((500,len(ids)),np.int32);filled[date]=np.zeros(500,int)
    def apply(block):
        for date in groups:
            n=accepted[date].shape[1]
            for rep in range(500):
                need=n-filled[date][rep]
                if need<=0:continue
                candidates=block[rep][memberships[date][block[rep]]][:need]
                accepted[date][rep,filled[date][rep]:filled[date][rep]+len(candidates)]=candidates
                filled[date][rep]+=len(candidates)
    apply(base_indices)
    rng=np.random.default_rng(np.random.SeedSequence([SEED,40]));extensions=[]
    while any(np.any(filled[d]<accepted[d].shape[1]) for d in groups):
        if len(extensions)>=100:raise RuntimeError('unbounded_rejection_sampling_guard')
        block=rng.integers(0,len(master),size=(500,len(master)),dtype=np.int32)
        extensions.append(block);apply(block)
    return {d:master[v] for d,v in accepted.items()},np.asarray(extensions,np.int32)


def run():
    start=now();tick=time.monotonic()
    for p in [I,E,R/'04_expected_capture',R/'03_breakeven']:p.mkdir(parents=True,exist_ok=True)
    protocol=E/'protocol_frozen_v9.json';manifest=E/'input_manifest_v9.json'
    assert protocol.exists() and manifest.exists(),'root_protocol_or_input_manifest_not_frozen'
    protocol_sha=hashlib.sha256(protocol.read_bytes()).hexdigest()
    put(E/'capture_execution_v9.json',dict(start=start,status='running',complete=False,protocol_sha256=protocol_sha))
    columns=['variant','dev','date','selected','A1_failed','hour_matched','expected','captured','expected_ctrl_matched','captured_ctrl_matched','cap_ctrl_matched']
    camera=pd.read_csv(V7/'capture_camera_internal_v7.csv',usecols=columns)
    camera=camera[camera.variant.eq(MAIN)].copy();camera.dev=camera.dev.astype(int)
    selection=pd.read_csv(V7/'capture_selection_internal_v7.csv',usecols=['variant','dev','selected'])
    selected=selection[selection.variant.eq(MAIN)&flag(selection.selected)].dev.astype(int).to_numpy()
    if not SYNTHETIC_MODE: assert len(selected)==329
    public=pd.read_csv(B/'formal_v7/03_taxi_probe/T35_capture_camera_v7.csv',usecols=columns,dtype=str,keep_default_na=False)
    public=public[public.variant.eq(MAIN)]
    state=pd.read_csv(B/'formal_v7/02_device_state/device_state_v7.csv',usecols=['dev','date','in_A200','in_health','hour_matched','baseline_B1'])
    device=pd.read_parquet(I/'decomp_device_day_v9.parquet',columns=['dev','date','baseline_B1','in_A100','in_A200','in_health','O','hour_matched'])
    device.dev=device.dev.astype(int)
    weights_input=np.load(I/'decomp_device_weights_v9.npz',allow_pickle=False)
    master=weights_input['device_ids'].astype(int);base_indices=weights_input['draw_indices'];root_weights=weights_input['weights']
    if not SYNTHETIC_MODE: assert len(master)==1287 and len(set(master))==1287
    assert np.array_equal(np.vstack([np.bincount(row,minlength=len(master)) for row in base_indices]),root_weights)
    data=np.load(V7/'capture_vehicle_counts_v7.npz',allow_pickle=False)
    ids=data['camera_ids'].astype(int);dates=list(data['dates']);radius=list(data['radii']).index(60)
    daily=data['all_day'][radius].astype(np.int64);h11=data['h11'][radius].astype(np.int64)
    assert daily.shape==(290,15,1075,2) and set(CONTROL).issubset(dates)
    previous=np.load(V7/'capture_bootstrap_v7.npz',allow_pickle=False)
    rng=np.random.default_rng(SEED);vehicle_weights=rng.multinomial(290,np.full(290,1/290),size=200)
    index_by_dev={int(d):i for i,d in enumerate(ids)}
    groups={};checks={};captured_columns={}
    for date in TARGET:
        f=camera[camera.date.eq(date)].set_index('dev').reindex(ids)
        good=flag(f.selected).to_numpy()&flag(f.A1_failed).to_numpy()&f.expected.ge(10).to_numpy()
        groups[date]=ids[good]
        checks['same329selection_'+date]=set(f.index[flag(f.selected)])==set(selected)
    accepted,extensions=accepted_bootstrap(groups,master,base_indices)
    np.savez_compressed(I/'capture_resampling_v9.npz',device_ids=master,base_draw_indices=base_indices,
        extension_blocks=extensions,vehicle_weights=vehicle_weights,seed=np.asarray(SEED),
        **{'accepted_device_ids__'+d:accepted[d] for d in TARGET},**{'subgroup_device_ids__'+d:groups[d] for d in TARGET})
    bootstrap_rows=[];result=[];coverage=[];subgroup_rows=[]
    for date in TARGET:
        hm=date=='2021-07-25';cube=h11 if hm else daily
        event_v=cube[:,dates.index(date)];control_v=cube[:,[dates.index(d) for d in CONTROL]].sum(axis=1)
        ev=event_v.sum(axis=0);ctrl=control_v.sum(axis=0);ctrl_cap=div(ctrl[:,1],ctrl[:,0])
        source=camera[camera.date.eq(date)].set_index('dev').reindex(ids)
        checks['point_event_counts_'+date]=np.array_equal(ev[:,0],source.expected.to_numpy()) and np.array_equal(ev[:,1],source.captured.to_numpy())
        checks['point_control_counts_'+date]=np.array_equal(ctrl[:,0],source.expected_ctrl_matched.to_numpy()) and np.array_equal(ctrl[:,1],source.captured_ctrl_matched.to_numpy())
        checks['point_control_cap_'+date]=np.allclose(ctrl_cap,source.cap_ctrl_matched.to_numpy(),equal_nan=True,atol=1e-11,rtol=1e-11)
        g=np.asarray([index_by_dev[int(d)] for d in groups[date]],int)
        expected_per_camera=ctrl_cap[g]*ev[g,0]
        pointE=float(expected_per_camera.sum());pointC=int(ev[g,1].sum());pointR=div(pointC,pointE).item()
        accepted_i=np.asarray([[index_by_dev[int(d)] for d in row] for row in accepted[date]],int)
        bE_camera=(ctrl_cap[accepted_i]*ev[accepted_i,0]).sum(axis=1)
        bC_camera=ev[accepted_i,1].sum(axis=1);bR_camera=div(bC_camera,bE_camera)
        be=(vehicle_weights@event_v.reshape(290,-1)).reshape(200,len(ids),2)
        bc=(vehicle_weights@control_v.reshape(290,-1)).reshape(200,len(ids),2)
        boot_cap=div(bc[:,:,1],bc[:,:,0]);invalid_control=(bc[:,g,0]==0).sum(axis=1)
        bE_vehicle=(boot_cap[:,g]*be[:,g,0]).sum(axis=1)
        bC_vehicle=be[:,g,1].sum(axis=1);bR_vehicle=div(bC_vehicle,bE_vehicle)
        checks['fixed_subgroup_invalid_control_'+date]=np.array_equal(np.isnan(bE_vehicle),invalid_control>0)
        original=previous[MAIN+'__'+date+'__failed_vehicle_cap']
        reproduced=div(be[:,g,1].sum(axis=1),be[:,g,0].sum(axis=1))
        checks['v7_200vehicle_weight_exact_reproduction_'+date]=np.allclose(reproduced,original,equal_nan=True,rtol=1e-13,atol=1e-13)
        checks['camera_each_draw_fixed_n_'+date]=accepted_i.shape==(500,len(g)) and np.isin(accepted[date],groups[date]).all()
        row=dict(date=date,hour_matched=int(hm),n_report_cameras=len(g),n_control_selected=329,E=pointE,C=pointC,C_over_E=pointR,
                 subgroup='fixed_v7_control_selected_A1_failed_event_expected_ge10',posthoc_revision=True)
        for kind,values in [('camera',dict(E=bE_camera,C=bC_camera,C_over_E=bR_camera)),('vehicle',dict(E=bE_vehicle,C=bC_vehicle,C_over_E=bR_vehicle))]:
            for metric,arr in values.items():
                bound=limits(arr)
                row[metric+'_'+kind+'_ci_lo']=bound['lo'];row[metric+'_'+kind+'_ci_hi']=bound['hi'];row[metric+'_'+kind+'_valid_draws']=bound['valid']
            bootstrap_rows.append(pd.DataFrame(dict(date=date,bootstrap=kind,replicate=np.arange(1,len(values['E'])+1),E=values['E'],C=values['C'],C_over_E=values['C_over_E'],
                invalid_control_camera_cells=np.zeros(500,int) if kind=='camera' else invalid_control)))
        result.append(row)
        for j,dev in enumerate(groups[date]):
            ci=g[j];subgroup_rows.append(dict(date=date,dev=int(dev),expected=int(ev[ci,0]),captured=int(ev[ci,1]),control_expected=int(ctrl[ci,0]),control_captured=int(ctrl[ci,1]),control_cap=ctrl_cap[ci],expected_capture=expected_per_camera[j]))
        subset=device[device.date.eq(date)].set_index('dev');O=subset[flag(subset.O)]
        O_ids=O.index.to_numpy(int);audit=np.asarray([i for i,d in enumerate(ids) if d in set(O_ids) and d in set(selected) and ev[i,0]>=10],int)
        audit_ids=ids[audit];baselineO=float(O.baseline_B1.sum());baseline_audit=float(O.reindex(audit_ids).baseline_B1.sum())
        e,c=ev[audit].sum(axis=0);ce,cc=ctrl[audit].sum(axis=0)
        coverage.append(dict(date=date,hour_matched=int(hm),GPS_available=True,n_O=len(O),n_audited_cameras=len(audit),
            O_baseline_flow_share_audited=div(baseline_audit,baselineO).item(),pooled_relative_capture=div(div(c,e),div(cc,ce)).item(),
            taxi_passage_frequency_ratio=div(e,ce/8).item(),event_expected=int(e),event_captured=int(c),control_expected=int(ce),control_captured=int(cc),
            control_days=8,scope='O_intersect_fixed329_intersect_event_expected_ge10',posthoc_revision=True))
        # Eligibility and baseline stay aligned to public A200 state, no A1 substitution.
        state_day=state[state.date.eq(date)].set_index('dev').reindex(O_ids)
        checks['coverage_O_equals_public_not_health_'+date]=not flag(state_day.in_health).any() and flag(state_day.in_A200).all()
        checks['matched_window_flags_'+date]=bool((pd.to_numeric(subset.hour_matched)==int(hm)).all() and (pd.to_numeric(source.hour_matched)==int(hm)).all())
    for date in DATES[7:]:
        O=device[device.date.eq(date)&flag(device.O)]
        coverage.append(dict(date=date,hour_matched=0,GPS_available=False,n_O=len(O),n_audited_cameras=np.nan,O_baseline_flow_share_audited=np.nan,pooled_relative_capture=np.nan,
            taxi_passage_frequency_ratio=np.nan,event_expected=np.nan,event_captured=np.nan,control_expected=np.nan,control_captured=np.nan,control_days=8,
            scope='GPS_unavailable_not_zero_coverage',posthoc_revision=True))
    frame=pd.DataFrame(result);cover=pd.DataFrame(coverage);draws=pd.concat(bootstrap_rows,ignore_index=True)
    frame.to_csv(I/'capture_expected_internal_v9.csv',index=False,encoding='utf-8-sig',float_format='%.15g',na_rep='NA')
    cover.to_csv(I/'capture_audit_coverage_internal_v9.csv',index=False,encoding='utf-8-sig',float_format='%.15g',na_rep='NA')
    pd.DataFrame(subgroup_rows).to_csv(I/'capture_report_subgroups_v9.csv',index=False,encoding='utf-8-sig',float_format='%.15g')
    draws.to_parquet(I/'capture_bootstrap_results_v9.parquet',index=False)
    count_columns=['E','C']+[f'{m}_{kind}_ci_{side}' for m in ['E','C'] for kind in ['camera','vehicle'] for side in ['lo','hi']]
    save_public(frame,R/'04_expected_capture/T40_expected_capture_v9.csv',count_columns)
    save_public(cover,R/'03_breakeven/T39_audit_coverage_v9.csv',['n_audited_cameras','event_expected','event_captured','control_expected','control_captured'])
    row=frame[frame.date.eq('2021-07-26')].iloc[0]
    acceptance=dict(T40_0726=dict(reached=bool(row.n_report_cameras==64 and row.C==55 and abs(row.E-8733)<15),n_report_cameras=int(row.n_report_cameras),E=row.E,C=int(row.C),absolute_difference_from_review_8733=abs(row.E-8733),tolerance_strict_less_than=15))
    checks['7_T40_and_9_coverage_rows']=len(frame)==7 and len(cover)==9
    checks['4900_retained_bootstrap_rows']=len(draws)==4900
    checks['protocol_unchanged']=hashlib.sha256(protocol.read_bytes()).hexdigest()==protocol_sha
    checks['public_private_keys_exact']=camera[['variant','date','dev']].astype(str).reset_index(drop=True).equals(public[['variant','date','dev']].astype(str).reset_index(drop=True))
    if not all(checks.values()):raise RuntimeError('capture_frozen_input_or_output_integrity_failed')
    put(E/'capture_execution_v9.json',dict(start=start,end=now(),seconds=time.monotonic()-tick,complete=True,status='complete',
        command=_release_path('path_041'),
        seed=SEED,protocol_sha256=protocol_sha,input_manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
        source_reads=False,key_reads=False,raw_point_or_AVI_reads=False,v8_reads=False,old_files_modified=False,
        camera_bootstrap='500 fixed-n subgroup multinomial via shared ordered A100 rejection sampling; same row/extension block across dates; E/C/ratio paired',
        vehicle_bootstrap='200 same original v7 multinomial290 weights across all control and event dates; exact archived failedcap reproduction',
        extension_seed=[SEED,40],extension_blocks=len(extensions),
        zero_denominators='Fixed report subgroup never shrunk. Any boot controlE0 invalidates entire E and C/E draw; C separately valid. controlC0/controlEpositive is a valid zero capture rate. Sum E0 makes ratio NA.',
        privacy='Count-valued point estimates and interval endpoints tested unrounded for<10 before suppression; other nonnegative counts rounded half-up integer; ratios4dp; source same public cells.',
        checks=checks,all_checks_passed=True,acceptance=acceptance,main_results=frame.to_dict('records'),audit_coverage=cover.to_dict('records')))
    put(R/'04_expected_capture/T40_checks_v9.json',acceptance)
    print(json.dumps(clean(dict(complete=True,seconds=time.monotonic()-tick,checks=len(checks),acceptance=acceptance,coverage_0726=cover[cover.date.eq('2021-07-26')].to_dict('records'))),ensure_ascii=False))


if __name__=='__main__':
    try:run()
    except BaseException as err:
        put(E/'capture_failure_v9.json',dict(at=now(),complete=False,error_type=type(err).__name__,source_reads=False,key_reads=False))
        print(json.dumps(dict(complete=False,error_type=type(err).__name__)))
        raise
