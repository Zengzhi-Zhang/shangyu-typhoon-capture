# -*- coding: utf-8 -*-
"""Metadata and allowed-input join schema only, before effect computation."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[3]), str(_ReleasePath(__file__).resolve().parents[1])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from pathlib import Path
from datetime import datetime,timezone,timedelta
import zipfile,json
import numpy as np,pandas as pd

B=Path(_release_path('project_root'));R=_ReleasePath(_release_path('v9_output_root'))


def npz_schema(path):
    result={}
    with zipfile.ZipFile(path) as z:
        for key in z.namelist():
            with z.open(key) as f:
                version=np.lib.format.read_magic(f)
                shape,fortran,dtype=(np.lib.format.read_array_header_1_0(f) if version==(1,0) else np.lib.format.read_array_header_2_0(f))
                result[key[:-4]]=dict(shape=list(shape),dtype=str(dtype),fortran=fortran)
    return result


def main():
    capture=B/'formal_v7/01_internal';pub=B/'formal_v7/03_taxi_probe'
    names=['capture_camera_internal_v7.csv','capture_selection_internal_v7.csv','capture_vehicle_counts_v7.npz','capture_bootstrap_v7.npz']
    schemas={n:npz_schema(capture/n) if n.endswith('.npz') else pd.read_csv(capture/n,nrows=0).columns.tolist() for n in names}
    state=pd.read_csv(B/'formal_v7/02_device_state/device_state_v7.csv',usecols=['dev','date','in_A100','in_A200','in_health','baseline_B1','n_day','hour_matched'])
    camera=pd.read_csv(capture/names[0],usecols=['variant','dev','date','selected'])
    selection=pd.read_csv(capture/names[1],usecols=['variant','dev','selected'])
    public=pd.read_csv(pub/'T35_capture_camera_v7.csv',usecols=['variant','dev','date'])
    ids=np.load(capture/names[2],allow_pickle=False)['camera_ids']
    main=selection[selection.variant.eq('main_R60_cap03')]
    sel=main.selected.astype(str).str.lower().isin(['true','1'])
    flag=lambda v:v.astype(str).str.lower().isin(['true','1'])
    days=state.groupby('date').agg(n_rows=('dev','size'),n_unique_dev=('dev','nunique')).reset_index().to_dict('records')
    report=dict(at=datetime.now(timezone(timedelta(hours=8))).isoformat(),effects_computed=False,source_reads=False,key_reads=False,
        schemas=schemas,state_schema=pd.read_csv(B/'formal_v7/02_device_state/device_state_v7.csv',nrows=0).columns.tolist(),
        state_dates=days,unique_state_devices=int(state.dev.nunique()),A100_devices=int(state.loc[flag(state.in_A100),'dev'].nunique()),
        A200_devices=int(state.loc[flag(state.in_A200),'dev'].nunique()),selected_main_devices=int(sel.sum()),
        camera_ids_count=len(ids),bootstrap_weights_present=any('weight' in x for x in schemas[names[3]]),
        anonymous_join_checks=dict(all_capture_IDs_in_public_state=bool(set(ids).issubset(set(state.dev))),
                                  exact_public_private_camera_key_order=camera[['variant','date','dev']].equals(public[['variant','date','dev']]),
                                  all_main_selection_IDs_equal_cube_IDs=set(main.dev)==set(ids)),
        join_method='Join integer camera_ids/capture.dev/public state.dev directly; no attribute table or ID mapping read.',
        pending_root_release=True)
    (R/'00_env').mkdir(parents=True,exist_ok=True)
    (R/'00_env/capture_schema_v9.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:report[k] for k in ['unique_state_devices','A100_devices','A200_devices','selected_main_devices','camera_ids_count','bootstrap_weights_present','anonymous_join_checks']},ensure_ascii=False))
    print(json.dumps(schemas[names[2]],ensure_ascii=False))
    print(json.dumps(dict(bootstrap_key_count=len(schemas[names[3]]),example=list(schemas[names[3]].items())[:3]),ensure_ascii=False))


if __name__=='__main__':main()
