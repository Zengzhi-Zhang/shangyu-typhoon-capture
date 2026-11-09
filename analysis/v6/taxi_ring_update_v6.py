# -*- coding: utf-8 -*-
"""One local GPS-cache traversal for calibrated rings and moving h11 distance."""
from pathlib import Path
import json
import time
import numpy as np
import pandas as pd
from taxi_parse_v6 import INTERNAL,OUT,RINGS,NOW,corrected_xy,baiguan_xy,haversine,SafeParseError


def calibrated_ring_rows(points,calibration):
    bgx,bgy=baiguan_xy();rows=[]
    for day,g in points.groupby('date',sort=True):
        g=g.sort_values('timestamp',kind='stable')
        valid=g.valid_xy.to_numpy(bool);lon=g.lon.to_numpy();lat=g.lat.to_numpy();mov=g.moving.to_numpy(bool)
        seconds=g.timestamp.to_numpy(dtype='datetime64[ns]').astype(np.int64)/1e9
        gap=np.diff(seconds);lonff=pd.Series(lon).ffill().to_numpy();latff=pd.Series(lat).ffill().to_numpy()
        d=haversine(lonff[:-1],latff[:-1],lon[1:],lat[1:])
        eligible=valid[1:]&np.isfinite(lonff[:-1])&(gap>0)
        with np.errstate(divide='ignore',invalid='ignore'):speed=d/(gap/3600)
        accept=eligible&(speed<=150);moving=mov[1:]|mov[:-1];hour=g.timestamp.dt.hour.to_numpy()[:-1]
        px,py=corrected_xy(lonff[:-1][accept],latff[:-1][accept],calibration)
        ring=np.searchsorted([2,4,7,12],np.hypot(px-bgx,py-bgy)/1000,side='right')
        total=np.zeros(5);move=np.zeros(5);h11=np.zeros(5);moveh11=np.zeros(5)
        distances=d[accept];is_move=moving[accept];after11=hour[accept]>=11
        np.add.at(total,ring,distances)
        np.add.at(move,ring[is_move],distances[is_move])
        np.add.at(h11,ring[after11],distances[after11])
        np.add.at(moveh11,ring[is_move&after11],distances[is_move&after11])
        vx,vy=corrected_xy(lon[valid],lat[valid],calibration)
        pr=np.searchsorted([2,4,7,12],np.hypot(vx-bgx,vy-bgy)/1000,side='right');pts=np.bincount(pr,minlength=5)
        row=dict(date=day,coordinate_variant=calibration.get('selected_method','raw_WGS84'),km_moving_from_11h=float(moveh11.sum()))
        for i,label in enumerate(RINGS):
            row.update({f'km_ring_{label}':float(move[i]),f'km_moving_ring_{label}':float(move[i]),f'km_total_ring_{label}':float(total[i]),f'km_ring_h11_{label}':float(h11[i]),f'km_moving_ring_h11_{label}':float(moveh11[i]),f'pts_ring_{label}':int(pts[i])})
        rows.append(row)
    return rows


def recompute_ring_metrics_v6(calibration):
    start=NOW();tick=time.monotonic();path=INTERNAL/'taxi_vehicle_day_v6.csv'
    original=pd.read_csv(path,encoding='utf-8-sig').set_index(['vehicle_ph','date'])
    original_nonring=original[['n_rows','dist_km','dist_moving_km','km_from_11h']].copy()
    files=sorted((INTERNAL/'taxi_gps_points').glob('*.parquet'))
    if len(files)!=290:raise SafeParseError('incomplete_GPS_cache')
    for label in RINGS:original['km_moving_ring_h11_'+label]=0.
    original['km_moving_from_11h']=0.
    original['coordinate_variant']=calibration.get('selected_method','raw_WGS84')
    for index,p in enumerate(files,1):
        for row in calibrated_ring_rows(pd.read_parquet(p),calibration):
            key=(p.stem,row.pop('date'))
            if key not in original.index:raise SafeParseError('daily_GPS_cache_key_mismatch')
            for col,value in row.items():original.loc[key,col]=value
        if index%50==0:print(f'{NOW()} calibrated_ring_vehicles_complete={index}/290',flush=True)
    if not original_nonring.equals(original[original_nonring.columns]):raise SafeParseError('ring_update_changed_nonring_fields')
    checks={}
    for prefix,field in [('km_total_ring_','dist_km'),('km_moving_ring_','dist_moving_km'),('km_ring_','dist_moving_km'),('km_ring_h11_','km_from_11h'),('km_moving_ring_h11_','km_moving_from_11h'),('pts_ring_','n_valid_xy')]:
        error=float((original[[prefix+label for label in RINGS]].sum(axis=1)-original[field]).abs().max())
        checks[prefix+'conservation_max_abs_error']=error
        if error>.00004:raise SafeParseError('ring_distance_conservation_failed')
    checks['moving_h11_le_total_h11']=bool(original.km_moving_from_11h.le(original.km_from_11h+.000001).all())
    if not checks['moving_h11_le_total_h11']:raise SafeParseError('moving_h11_exceeds_total_h11')
    temp=path.with_suffix('.partial.csv');original.reset_index().to_csv(temp,index=False,encoding='utf-8-sig',float_format='%.6f');temp.replace(path)
    report=dict(start=start,end=NOW(),seconds=time.monotonic()-tick,complete=True,rows=len(original),vehicles=290,calibration_method=calibration.get('selected_method','raw_WGS84'),source_reads=False,key_reads=False,nonring_fields_preserved=True,checks=checks,interface='km_ring=moving all day; km_moving_ring_h11=moving accepted segments starting>=11; total ring columns retained as sensitivity')
    (OUT/'00_env/taxi_ring_recompute_execution_v6.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return len(original)
