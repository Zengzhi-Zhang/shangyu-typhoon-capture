# -*- coding: utf-8 -*-
"""Seven-column auxiliary reproduction by original sheet; main GPS unchanged."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[2]), str(_ReleasePath(__file__).resolve().parents[0])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from pathlib import Path
import argparse,json,os,subprocess,sys,time
import numpy as np,pandas as pd
import taxi_parse_v6 as p

E=p.OUT/'00_env';I=p.INTERNAL;CP=I/'taxi_legacy_sheet_checkpoints'


def worker(payload):
    path=Path(payload['path']);ph=payload['ph'];before=path.stat()
    frames,mode,counters=p.read_projected_workbook(path);rows=[];mismatch=bad=0;source_rows=0
    for f in frames:
        day=f.attrs['sheet_date'];source_rows+=len(f)
        ts=p.parse_times(f['时间'],mode);ok=ts.notna();bad+=int((~ok).sum());ts=ts.loc[ok];v=f.loc[ok]
        mismatch+=int(ts.dt.strftime('%Y-%m-%d').ne(day).sum())
        if len(v):
            lon=pd.to_numeric(v['经度'],errors='coerce');lat=pd.to_numeric(v['纬度'],errors='coerce');speed=pd.to_numeric(v['速度'],errors='coerce')
            valid=lon.between(120.3,121.4)&lat.between(29.5,30.5)
            # Keep original timestamps and all rows, but accumulate each sheet alone.
            points=pd.DataFrame(dict(timestamp=ts,date=day,lon=lon.where(valid),lat=lat.where(valid),valid_xy=valid,moving=speed.gt(0),occupied=v['车辆状态'].astype(str).str.contains('载客',regex=False)))
            row=p.daily_metrics(points,ph)[0]
        else:row=dict(vehicle_ph=ph,date=day,n_parsed_time=0,n_valid_xy=0,n_moving=0,n_occupied=0,hours_active=0,dist_km=0.,dist_moving_km=0.,n_jump_segments=0)
        row['n_rows']=len(f);row['dist_km_unrounded']=row['dist_km'];row['dist_moving_km_unrounded']=row['dist_moving_km']
        row['dist_km']=round(row['dist_km'],2);row['dist_moving_km']=round(row['dist_moving_km'],2)
        rows.append(row)
    after=path.stat();source=dict(size=before.st_size,mtime_ns=before.st_mtime_ns)
    if source!=dict(size=after.st_size,mtime_ns=after.st_mtime_ns):raise p.SafeParseError('auxiliary_source_changed')
    return dict(complete=True,source=source,rows=rows,counters=dict(source_rows=source_rows,sheets_seen=counters['sheets_seen'],bad_time=bad,date_sheet_mismatch=mismatch))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--worker',action='store_true');args=parser.parse_args()
    if args.worker:
        try:print(json.dumps(worker(json.loads(sys.stdin.read())),ensure_ascii=False,allow_nan=False))
        except BaseException as exc:print(json.dumps(dict(error_type=type(exc).__name__,error_code=str(exc) if isinstance(exc,p.SafeParseError) else None)));sys.exit(1)
        return
    start=p.NOW();tick=time.monotonic();CP.mkdir(parents=True,exist_ok=True)
    checkpoints={x.stem:json.loads(x.read_text(encoding='utf-8')) for x in (I/'taxi_parse_checkpoints').glob('*.json')}
    if len(checkpoints)!=290:raise p.SafeParseError('requires290_original_checkpoints')
    chosen={ph for ph,c in checkpoints.items() if c['counters']['date_sheet_mismatch']>0}
    if len(chosen)!=173:raise p.SafeParseError('mismatch_subset_cardinality_changed')
    from taxi_probe_hash_v6 import get_probe_files_hashed
    mapping=get_probe_files_hashed();mapping=dict((ph,Path(path)) for path,ph in (mapping.items() if isinstance(mapping,dict) else mapping))
    rows=[];failures=[];attempts=0;metadata_ok=True;reread=0
    for ph,c in checkpoints.items():
        if ph not in chosen:
            for row0 in c['rows']:
                row=dict(row0);row['dist_km_unrounded']=row['dist_km'];row['dist_moving_km_unrounded']=row['dist_moving_km'];row['dist_km']=round(row['dist_km'],2);row['dist_moving_km']=round(row['dist_moving_km'],2);row['auxiliary_source']='unchanged_date_cache';rows.append(row)
    for index,ph in enumerate(sorted(chosen),1):
        sourcepath=mapping[ph];st=sourcepath.stat();meta=dict(size=st.st_size,mtime_ns=st.st_mtime_ns)
        if meta!=checkpoints[ph]['source']:raise p.SafeParseError('source_metadata_differs_from_initial_parse')
        cache=CP/(ph+'.json');result=None
        if cache.exists():
            cached=json.loads(cache.read_text(encoding='utf-8'))
            if cached.get('complete') and cached['source']==meta:result=cached
        for attempt in range(1,4):
            if result is not None:break
            attempts+=1;proc=None
            try:
                proc=subprocess.run([p.PYTHON,str(Path(__file__)),'--worker'],input=json.dumps(dict(path=str(sourcepath),ph=ph),ensure_ascii=False).encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=420,env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1'))
                value=json.loads(proc.stdout.decode('utf-8'))
                if proc.returncode==0 and value.get('complete') and value.get('source')==meta:result=value;reread+=1
                else:failures.append(dict(workbook_index=index,attempt=attempt,exit_code=proc.returncode,error_type=value.get('error_type'),error_code=value.get('error_code')))
            except BaseException as exc:failures.append(dict(workbook_index=index,attempt=attempt,error_type=type(exc).__name__,exit_code=proc.returncode if proc is not None else None))
        if result is None:raise p.SafeParseError('auxiliary_workbook_failed_bounded_retries')
        current=sourcepath.stat();metadata_ok&=meta==dict(size=current.st_size,mtime_ns=current.st_mtime_ns)
        for key in ['source_rows','sheets_seen','bad_time','date_sheet_mismatch']:
            if result['counters'][key]!=checkpoints[ph]['counters'][key]:raise p.SafeParseError('auxiliary_projection_counter_disagreement')
        cache.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
        for row0 in result['rows']:
            row=dict(row0);row['auxiliary_source']='seven_column_source_reread';rows.append(row)
        print(f'{p.NOW()} auxiliary_workbooks_complete={index}/173',flush=True)
    frame=pd.DataFrame(rows);frame.to_csv(I/'taxi_legacy_sheet_vehicle_day_v6.csv',index=False,encoding='utf-8-sig',float_format='%.6f')
    domain=frame.date.ge('2021-07-06')&frame.date.lt('2021-08-01');aux=frame[domain]
    old=pd.read_csv(p.ROOT/'01_panels/taxi_vehicle_day.csv');old=old[old.batch.eq('GPS0706-0731')].copy();old['date']=pd.to_datetime(old.sheet_date.astype(str).str.replace('-','',regex=False),format='%Y%m%d').dt.strftime('%Y-%m-%d');old=old[old.date.ge('2021-07-06')&old.date.lt('2021-08-01')]
    daily=old.groupby('date').agg(legacy_km=('dist_km','sum'),legacy_source_rows=('n_rows','sum'),legacy_vehicle_days=('n_rows','size')).join(aux.groupby('date').agg(auxiliary_sheet_km=('dist_km','sum'),auxiliary_sheet_km_unrounded=('dist_km_unrounded','sum'),auxiliary_source_rows=('n_rows','sum'),auxiliary_vehicle_days=('n_rows','size')))
    actual=pd.read_csv(I/'taxi_vehicle_day_v6.csv',encoding='utf-8-sig')
    daily=daily.join(actual.groupby('date').agg(actual_km=('dist_km','sum'),actual_parsed_points=('n_parsed_time','sum'),actual_main_n_rows=('n_rows','sum'),actual_vehicle_days=('n_rows','size')))
    daily['relative_difference']=(daily.auxiliary_sheet_km-daily.legacy_km).abs()/daily.legacy_km
    daily['actual_minus_sheet_km']=daily.actual_km-daily.auxiliary_sheet_km
    daily['actual_minus_sheet_parsed_points']=daily.actual_parsed_points-daily.auxiliary_source_rows
    daily.reset_index().to_csv(E/'taxi_legacy_sheet_reconciliation_daily_v6.csv',index=False,encoding='utf-8-sig',float_format='%.6f')
    passed=bool(len(daily)==26 and daily.relative_difference.notna().all() and daily.relative_difference.le(.01).all())
    rowcounts=bool(daily.legacy_source_rows.eq(daily.auxiliary_source_rows).all() and daily.legacy_vehicle_days.eq(daily.auxiliary_vehicle_days).all())
    report=dict(start=start,end=p.NOW(),seconds=time.monotonic()-tick,command=_release_path('path_024'),complete=True,legacy_sheet_daily_distance_within_1pct=passed,max_relative_difference=float(daily.relative_difference.max()),n_source_workbooks_reread=reread,selected_source_workbooks=173,source_read_attempts=attempts,cache_reused_workbooks=117,source_metadata_unchanged=bool(metadata_ok),days=len(daily),source_rows_and_vehicle_days_equal=rowcounts,source_timestamp_sheet_date_mismatch_rows=353729,actual_day_legacy_1pct_passed=False,original_nonzero_exit_codes=[1,1],main_GPS_or_daily_modified=False,failures=failures,key_reader='taxi_probe_hash_v6.py only',extra_IO_reason='Investigate actual-date versus legacy sheet-date mileage validation failure without changing main calendar-date panel')
    (E/'taxi_legacy_sheet_reconciliation_v6.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=False))
    if not (passed and metadata_ok and rowcounts):raise p.SafeParseError('auxiliary_sheet_reconciliation_failed')

if __name__=='__main__':
    try:main()
    except Exception as exc:
        print(json.dumps(dict(complete=False,error_type=type(exc).__name__,error_code=str(exc) if isinstance(exc,p.SafeParseError) else None)),flush=True);sys.exit(1)
