# -*- coding: utf-8 -*-
"""Synthetic-only geometric and calibration checks, no source inputs."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[3]), str(_ReleasePath(__file__).resolve().parents[1])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from pathlib import Path
import json
import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy.spatial import cKDTree
import capture_rate_v6 as c

def main():
    assert c.dedup_expected([0,299,300,301,600,602]).tolist()==[0,301,602]
    e,k,u=c.capture_counts(np.array([1000.,2000.]),np.array([1001.,2100.,3000.]),120)
    assert (e,k,u)==(2,2,1)
    idx,d=c.nearest_indices(np.array([10.,20.]),np.array([9.,16.,24.]));assert idx.tolist()==[0,1,1] and d.tolist()==[1.,4.,4.]
    lon=np.array([120.9,_release_private('private_value_015')]);lat=np.array([30.,30.]);x,y=c.PROJECT.transform(lon,lat);cam=np.array([[(x[0]+x[1])/2,(y[0]+y[1])/2]])
    g=pd.DataFrame(dict(timestamp=pd.to_datetime(['2021-07-19 08:00:00','2021-07-19 08:01:00']),valid_xy=[True,True],lon=lon,lat=lat))
    events=c.segment_events(g,cam,cKDTree(cam),dict(selected_method='raw_WGS84'));assert len(events)==1 and abs(events[0,1]-(8*3600+30))<1e-5 and events[0,2]<1e-8
    empty_events=c.segment_events(g.iloc[:0],cam,cKDTree(cam),dict(selected_method='raw_WGS84'))
    assert empty_events.shape==(0,3)
    assert c.capture_counts(np.empty(0),np.array([1000.,1100.]),180)==(0,0,2)
    # Camera100m east; +median correction cancels, literalminus doubles residual.
    inv=Transformer.from_crs(32651,4326,always_xy=True);clon,clat=inv.transform(x[0]+100,y[0])
    a=pd.DataFrame(dict(ph=['synthetic']*2,dev=['camera']*2,date=['2021-07-19']*2,sec_of_day=[28800,28860]))
    gps=pd.DataFrame(dict(timestamp=pd.to_datetime(['2021-07-19 08:00:00','2021-07-19 08:01:00']),date=['2021-07-19']*2,lon=[120.9]*2,lat=[30.]*2,valid_xy=[True]*2))
    original=pd.read_parquet
    pd.read_parquet=lambda *a,**k:gps.copy()
    try:
        cal=c.calibrate(a,pd.DataFrame(dict(dev=['camera'],lon=[clon],lat=[clat])),{'synthetic':Path('not_read')})
        offsets=np.array([0.,0.,40.,40.,100.,100.,200.,200.]);flon,flat=inv.transform(x[0]+offsets,np.full(8,y[0]));dev=[f'synthetic{i}' for i in range(8)]
        fa=pd.DataFrame(dict(ph=['synthetic']*8,dev=dev,date=['2021-07-19']*8,sec_of_day=[28800]*8))
        fallback=c.calibrate(fa,pd.DataFrame(dict(dev=dev,lon=flon,lat=flat)),{'synthetic':Path('not_read')})
    finally:pd.read_parquet=original
    assert cal['selected_method']=='constant_UTM_shift' and abs(cal['applied_dx_m']-100)<1e-5
    assert cal['selected']['median']<1e-5 and cal['literal_negative_shift_diagnostic_only']['median']>199.99 and not cal['S2']
    assert not fallback['constant_eligible'] and fallback['GCJ02_to_WGS84']['median']>fallback['raw']['median']
    assert fallback['selected_method']=='raw_WGS84' and fallback['raw_fallback'] and fallback['S2']
    result=dict(all_passed=True,source_reads=0,key_reads=0,greedy_300s_dedup=True,capture_window_and_unexpected=True,line_segment_interpolation=True,empty_GPS_preserves_unexpected_AVI=True,constant_offset_sign=True,literal_negative_shift_not_selected=True,failed_correction_retains_raw_and_S2=True,august2_missing_explicit='2021-08-02' in c.TARGET)
    p=Path(_release_path('path_028'));p.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
if __name__=='__main__':main()
