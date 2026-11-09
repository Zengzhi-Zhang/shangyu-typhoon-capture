# -*- coding: utf-8 -*-
"""Read-only numerical checks of v8 outputs; no OSM/source re-read."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[3]), str(_ReleasePath(__file__).resolve().parents[1])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from pathlib import Path
from datetime import datetime, timezone, timedelta
import hashlib
import json
import re
import time
import numpy as np
import pandas as pd
from PIL import Image

BASE=Path(_release_path('project_root'));R=BASE/'formal_v8';I=R/'01_internal';P=R/'02_geometry';E=R/'00_env'


def alias_hits(text):
    numeric=[m.span() for m in re.finditer(r'(?<![\w.])[+-]?(?:\d+\.\d*|\.\d+)(?:[eE][+-]?\d+)?(?![\w.])',text)]
    hits=[]
    for m in re.finditer(r'cam_[0-9a-f]+|(?<![0-9a-f])[0-9a-f]{16}(?![0-9a-f])',text,re.I):
        if not any(a<=m.start() and m.end()<=b for a,b in numeric):hits.append(m.group())
    return hits


def main():
    started=datetime.now(timezone(timedelta(hours=8))).isoformat();tick=time.monotonic()
    checks={};cube=np.load(I/'geometry_counts_v8.npz',allow_pickle=False)
    full=cube['all_day'];h11=cube['h11'];dates=list(cube['dates']);ids=cube['camera_ids'];filters=list(cube['filters'])
    points=pd.read_parquet(I/'geometry_passages_v8.parquet')
    summary=pd.read_csv(I/'geometry_G123_internal_v8.csv');g0=pd.read_csv(I/'geometry_G0_internal_v8.csv')
    distances=pd.read_csv(I/'geometry_G4_internal_v8.csv');camera=pd.read_csv(I/'geometry_camera_internal_v8.csv')
    shifts=pd.read_csv(I/'geometry_distance_camera_internal_v8.csv')
    boots=pd.read_csv(I/'geometry_bootstrap_internal_v8.csv')
    public=pd.read_csv(P/'G_camera_diagnostics_v8.csv',dtype=str,keep_default_na=False)
    old=np.load(BASE/'formal_v7/01_internal/capture_vehicle_counts_v7.npz',allow_pickle=False)
    old_all=old['all_day'][0].sum(axis=0);old11=old['h11'][0].sum(axis=0)
    positions=np.array([list(old['camera_ids']).index(x) for x in ids])
    checks['329_frozen_main_cameras']=len(ids)==329 and len(set(ids))==329
    checks['all12_dates_v7_main_count_equality']=all(np.array_equal(full[0,di],old_all[list(old['dates']).index(day),positions]) for di,day in enumerate(dates))
    checks['all12_h11_v7_main_count_equality']=all(np.array_equal(h11[0,di],old11[list(old['dates']).index(day),positions]) for di,day in enumerate(dates))
    checks['captures_not_above_expected']=bool((full[...,1]<=full[...,0]).all() and (h11[...,1]<=h11[...,0]).all())
    checks['h11_not_above_full_expected']=bool((h11[...,0]<=full[...,0]).all())
    checks['postfilter_counts_subset_main']=bool((full[1:,:,:,0]<=full[0,:,:,0]).all() and (h11[1:,:,:,0]<=h11[0,:,:,0]).all())
    checks['G3_exact_conjunction']=bool(points.G3.eq(points.G1&(points.G2==1)).all())
    dirs=json.loads((I/'geometry_directions_v8.json').read_text(encoding='utf-8'))
    b=points.bearing.to_numpy();expected=np.zeros(len(points),bool)
    for ci,sub in points.groupby('camera_i',sort=False):
        d=set(dirs[str(ci)]);ix=sub.index.to_numpy();bear=b[ix];ok=np.zeros(len(ix),bool)
        if '其他' in d:ok[:]=True
        if '北往南' in d:ok|=(bear>=135)&(bear<=225)
        if '南往北' in d:ok|=(bear<=45)|(bear>=315)
        if '西向东' in d:ok|=(bear>=45)&(bear<=135)
        if '东向西' in d:ok|=(bear>=225)&(bear<=315)
        expected[ix]=ok
    checks['G1_independent_bearing_classification']=bool(np.array_equal(expected,points.G1.to_numpy()))
    checks['within_frozen60m']=bool(points.distance_m.between(0,60).all())
    checks['no_changed_time_or_speed_threshold']=bool(points.segment_speed_kmh.le(150).all() and points.sec.ge(0).all() and points.sec.lt(86400).all())
    checks['dedup_same_vehicle_camera_gt300']=bool(points.sort_values(['vehicle_i','date','camera_i','sec']).groupby(['vehicle_i','date','camera_i']).sec.diff().dropna().gt(300).all())
    checks['16_summary_rows_4filters4days']=len(summary)==16 and not summary.duplicated(['filter','date']).any()
    checks['8_G0_and_8_G4_rows']=len(g0)==8 and len(distances)==8
    checks['5264_camera_rows']=len(camera)==5264 and not camera.duplicated(['dev','date','filter']).any()
    checks['8000_camera_draw_rows']=len(boots)==8000
    stable_reconstructed=[];failed_reconstructed=[];boot_reconstructed=[]
    for row in summary.itertuples():
        f=camera[(camera['filter']==row.filter)&camera.date.eq(row.date)]
        st=f[f.Sstar_comparable.astype(bool)];fail=f[f.failed_event_ge10.astype(bool)]
        med=st.relative_capture.median();cap=fail.captured_event.sum()/fail.expected_event.sum() if fail.expected_event.sum()>0 else np.nan
        stable_reconstructed.append(np.isclose(med,row.Sstar_relative_median,atol=1e-10,rtol=1e-10,equal_nan=True) and len(st)==row.n_Sstar_comparable)
        failed_reconstructed.append(np.isclose(cap,row.failed_ge10_cap,atol=1e-10,rtol=1e-10,equal_nan=True) and len(fail)==row.n_failed_event_ge10 and np.isclose(fail.expected_event.sum(),row.failed_ge10_expected))
        draw=boots[(boots['filter']==row.filter)&boots.date.eq(row.date)].Sstar_relative_median.dropna()
        bound=draw.quantile([.025,.975]).to_numpy() if len(draw) else np.array([np.nan,np.nan])
        boot_reconstructed.append(np.allclose(bound,[row.camera_ci_lo,row.camera_ci_hi],atol=1e-10,rtol=1e-10,equal_nan=True) and len(draw)==row.camera_valid_draws)
    checks['Sstar_medians_from_camera_cells']=all(stable_reconstructed)
    checks['failed_GE10_pooled_denominators_from_cells']=all(failed_reconstructed)
    checks['all500_camera_intervals_from_retained_draws']=all(boot_reconstructed)
    checks['public_private_camera_row_order']=public[['dev','date','filter']].astype(str).equals(camera[['dev','date','filter']].astype(str))
    low=camera.expected_event.lt(10);lowctrl=camera.expected_control.lt(10)
    checks['low_event_E_both_counts_suppressed']=bool(public.loc[low,['expected_event','captured_event']].eq('<10').all().all())
    checks['low_event_rates_NA']=bool(public.loc[low,['capture_rate','relative_capture']].eq('NA').all().all())
    checks['low_control_E_both_counts_suppressed']=bool(public.loc[lowctrl,['expected_control','captured_control']].eq('<10').all().all())
    checks['low_control_relative_NA']=bool(public.loc[lowctrl,['control_capture_rate','relative_capture']].eq('NA').all().all())
    checks['no_public_coordinate_columns']=not any(c in ['lon','lat','x','y','longitude','latitude','GPS_heading','road_i','vehicle_i','camera_i'] for c in public.columns)
    files=sorted(p for p in P.rglob('*') if p.is_file())
    checks['public_alias_hits_zero']=not any(alias_hits(p.read_text(encoding='utf-8-sig')) for p in files if p.suffix in ['.csv','.json','.md'])
    checks['privacy_numeric_boundaries']=not alias_hits(_release_private('private_value_021')) and all(alias_hits(s) for s in [_release_private('private_value_022'),_release_private('private_value_007'),_release_private('private_value_023'),_release_private('private_value_024')])
    attrs=pd.read_csv(I/'G5_audit/G5_audit_attributes.csv');images=sorted(p for p in (I/'G5_audit').glob('G5_*.png') if p.name!='G5_contact_sheet.png')
    checks['G5_exactly16_unique_cameras']=len(attrs)==16 and attrs.dev.nunique()==16 and len(images)==16
    checks['G5_images_nonempty_and_same_dimensions']=all(Image.open(p).size==(2160,1080) and p.stat().st_size>10000 for p in images)
    dc=shifts[shifts.date.eq('2021-07-26')]
    a=dc[dc.main_failed_comparable.astype(bool)].sort_values(['expected_event','dev'],ascending=[False,True]).head(8).dev.tolist()
    b=dc[dc.main_failed_comparable.astype(bool)&~dc.dev.isin(a)].sort_values(['distance_median_shift','dev'],ascending=[False,True]).head(4).dev.tolist()
    c=dc[dc.main_Sstar_comparable.astype(bool)].sort_values(['expected_event','dev'],ascending=[False,True]).head(4).dev.tolist()
    checks['G5_frozen_selection_rankings']=attrs.dev.tolist()==a+b+c
    acceptance=json.loads((P/'G_acceptance_v8.json').read_text(encoding='utf-8'))
    row=summary[(summary['filter']=='G3')&summary.date.eq('2021-07-26')].iloc[0]
    checksg4=distances[distances.date.eq('2021-07-26')].set_index('group').shift_median_m
    checks['A_G1_threshold_unmodified']=acceptance['A_G1']['reached']==bool(row.n_failed_event_ge10>=40 and row.failed_ge10_cap<=.02)
    checks['A_G2_threshold_unmodified']=acceptance['A_G2']['reached']==bool(.90<=row.Sstar_relative_median<=1.05)
    checks['A_G3_median_of_camera_shifts']=acceptance['A_G3']['reached']==bool(checksg4.A1_failed<=checksg4.Sstar+10)
    checks['A_G4_pending_no_visual_verdict']=acceptance['A_G4']['reached'] is None and acceptance['A_G4']['automatic_visual_verdict'] is False
    checks['protocol_fingerprint_unchanged']=hashlib.sha256((E/'geometry_protocol_v8.json').read_bytes()).hexdigest()==json.loads((E/'geometry_execution_v8.json').read_text(encoding='utf-8'))['protocol_sha256']
    report=dict(start=started,end=datetime.now(timezone(timedelta(hours=8))).isoformat(),seconds=time.monotonic()-tick,
        command=_release_path('path_039'),
        checks={k:bool(v) for k,v in checks.items()},all_passed=all(checks.values()),source_reads=False,key_reads=False,
        scientific_outputs_modified=False,visual_road_interpretation_performed=False,
        public_SHA256={str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
    (E/'geometry_independent_checks_v8.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(all_passed=report['all_passed'],checks=len(checks),failed=[k for k,v in checks.items() if not v])))
    if not report['all_passed']:raise RuntimeError('geometry_independent_check_failure')


if __name__=='__main__':main()
