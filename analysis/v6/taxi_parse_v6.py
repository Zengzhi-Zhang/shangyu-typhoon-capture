# -*- coding: utf-8 -*-
"""Seven-column BIFF projection, isolated parsing, and reusable internal GPS points.

No workbook data is read on import. Raw CFB bytes are unavoidable file transport;
unselected cell values and SST strings are never decoded or materialised.
"""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[2]), str(_ReleasePath(__file__).resolve().parents[0])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from pathlib import Path
from datetime import datetime, timezone, timedelta
import argparse, io, json, math, os, struct, subprocess, sys, time
import numpy as np
import pandas as pd
from pyproj import Transformer

ROOT=Path(_release_path('project_root')); OUT=ROOT/'formal_v6'; INTERNAL=OUT/'01_internal'
SEED=20261005; PYTHON=_release_path('python_executable')
COLS={0:'时间',1:'速度',2:'方向',3:'车辆状态',7:'传送标识',8:'经度',9:'纬度'}
HEADERS=list(COLS.values()); RINGS=['0-2','2-4','4-7','7-12','12+']
PROJECT=Transformer.from_crs(4326,32651,always_xy=True)
NOW=lambda:datetime.now(timezone(timedelta(hours=8))).isoformat()

class SafeParseError(Exception): pass

def records(data,start=0):
    p=start
    while p+4<=len(data):
        rc,n=struct.unpack_from('<HH',data,p);p+=4
        if p+n>len(data): raise SafeParseError('truncated_BIFF')
        yield rc,memoryview(data)[p:p+n]
        p+=n
        if rc==0x000a: break

class SSTCursor:
    def __init__(self,chunks):self.chunks=chunks;self.i=0;self.p=0
    def boundary(self):
        while self.i<len(self.chunks) and self.p==len(self.chunks[self.i]):self.i+=1;self.p=0
        if self.i>=len(self.chunks):raise SafeParseError('truncated_SST')
    def raw(self,n):
        buf=bytearray()
        while n:
            self.boundary();k=min(n,len(self.chunks[self.i])-self.p)
            buf.extend(self.chunks[self.i][self.p:self.p+k]);self.p+=k;n-=k
        return bytes(buf)
    def skip(self,n):
        while n:
            self.boundary();k=min(n,len(self.chunks[self.i])-self.p);self.p+=k;n-=k
    def chars(self,n,wide,decode):
        pieces=[]
        while n:
            if self.p==len(self.chunks[self.i]):
                self.boundary();wide=bool(self.raw(1)[0]&1)
            width=2 if wide else 1
            k=min(n,(len(self.chunks[self.i])-self.p)//width)
            if k==0:raise SafeParseError('invalid_SST_char_boundary')
            if decode:
                b=bytes(self.chunks[self.i][self.p:self.p+k*width]);pieces.append(b.decode('utf-16le' if wide else 'latin1'))
            self.p+=k*width;n-=k
        return ''.join(pieces) if decode else None

def selected_sst(chunks,wanted):
    if not chunks:
        if wanted:raise SafeParseError('missing_SST')
        return {},dict(sst_entries=0,sst_decoded=0)
    c=SSTCursor(chunks);_,unique=struct.unpack('<II',c.raw(8));values={}
    for i in range(unique):
        n=struct.unpack('<H',c.raw(2))[0];flags=c.raw(1)[0]
        rt=struct.unpack('<H',c.raw(2))[0] if flags&8 else 0
        ext=struct.unpack('<I',c.raw(4))[0] if flags&4 else 0
        s=c.chars(n,bool(flags&1),i in wanted)
        c.skip(rt*4+ext)
        if i in wanted:values[i]=s
    if set(values)!=wanted:raise SafeParseError('SST_index_out_of_range')
    return values,dict(sst_entries=int(unique),sst_decoded=len(values))

def rk_value(b):
    u=struct.unpack('<I',b)[0]
    v=(struct.unpack('<i',b)[0]>>2) if u&2 else struct.unpack('<d',b'\0\0\0\0'+struct.pack('<I',u&0xfffffffc))[0]
    return v/100 if u&1 else v

def projected_biff(data,_headers_verified=False):
    from xlrd.biffh import unpack_unicode
    sheets=[];sst=[];datemode=0;version=None;in_sst=False
    for rc,b in records(data):
        if rc==0x0809:version=struct.unpack_from('<H',b,0)[0]
        elif rc==0x0022:datemode=struct.unpack_from('<H',b,0)[0]
        elif rc==0x0085:
            offset=struct.unpack_from('<I',b,0)[0]
            if b[5]==0:
                nchars=int(b[6]);wide=bool(b[7]&1)
                sheet_name=bytes(b[8:8+nchars*(2 if wide else 1)]).decode('utf-16le' if wide else 'latin1')
                if not (len(sheet_name)==8 and sheet_name.isdigit()):raise SafeParseError('non_calendar_sheet_metadata')
                sheets.append((offset,sheet_name))
        elif rc==0x00fc:sst=[b];in_sst=True
        elif rc==0x003c and in_sst:sst.append(b)
        if rc not in (0x00fc,0x003c):in_sst=False
    if version!=0x0600:raise SafeParseError('requires_BIFF8')
    selected=[];wanted=set();counts=dict(sheets_seen=len(sheets),selected_cells=0,unselected_cells_skipped=0)
    for si,(offset,sheet_name) in enumerate(sheets):
        cells={};nrows=0;pending=None
        for rc,b in records(data,offset):
            if rc in (0x0203,0x00fd,0x0204,0x027e,0x0205,0x0006,0x0206,0x0406,0x00d6):
                if len(b)<6:raise SafeParseError('short_cell_record')
                row,col=struct.unpack_from('<HH',b,0);nrows=max(nrows,row+1)
                if row<1 or col not in COLS or (row>1 and not _headers_verified):
                    counts['unselected_cells_skipped']+=1;pending=None;continue
                key=(row,col);counts['selected_cells']+=1
                if rc==0x00fd:
                    idx=struct.unpack_from('<I',b,6)[0];cells[key]=('sst',idx);wanted.add(idx)
                elif rc==0x0203:cells[key]=('value',struct.unpack_from('<d',b,6)[0])
                elif rc==0x027e:cells[key]=('value',rk_value(b[6:10]))
                elif rc in (0x0204,0x00d6):cells[key]=('value',unpack_unicode(bytes(b),6,lenlen=2))
                elif rc==0x0205:cells[key]=('value',int(b[6]) if b[7]==0 else '')
                else:
                    if bytes(b[12:14])==b'\xff\xff':
                        typ=b[6]
                        if typ==0:pending=key
                        elif typ==1:cells[key]=('value',int(b[8]))
                        elif typ in (2,3):cells[key]=('value','')
                        else:raise SafeParseError('unsupported_formula_result')
                    else:cells[key]=('value',struct.unpack_from('<d',b,6)[0])
            elif rc==0x0207 and pending is not None:
                cells[pending]=('value',unpack_unicode(bytes(b),0,lenlen=2));pending=None
            elif rc==0x00bd:
                row,first=struct.unpack_from('<HH',b,0);last=struct.unpack_from('<H',b,len(b)-2)[0];nrows=max(nrows,row+1)
                for col in range(first,last+1):
                    if row>=1 and col in COLS and (_headers_verified or row==1):
                        p=4+(col-first)*6;cells[(row,col)]=('value',rk_value(b[p+2:p+6]));counts['selected_cells']+=1
                    else:counts['unselected_cells_skipped']+=1
        selected.append((si,sheet_name,nrows,cells))
    strings,scount=selected_sst(sst,wanted);counts.update(scount)
    frames=[]
    for si,sheet_name,nrows,cells in selected:
        resolve=lambda x:strings[x[1]] if x[0]=='sst' else x[1]
        if nrows>=2:
            hdr={col:str(resolve(cells.get((1,col),('value','')))).strip() for col in COLS}
            if hdr!=COLS:raise SafeParseError('seven_column_header_mismatch')
        if not _headers_verified:continue
        vals=[[resolve(cells.get((r,col),('value',''))) for col in COLS] for r in range(2,nrows)]
        f=pd.DataFrame(vals,columns=HEADERS);f.attrs['sheet_date']=pd.to_datetime(sheet_name,format='%Y%m%d').strftime('%Y-%m-%d');frames.append(f)
    if not _headers_verified:return projected_biff(data,_headers_verified=True)
    return frames,datemode,counts

def read_projected_workbook(path):
    from xlrd.compdoc import CompDoc
    raw=Path(path).read_bytes()
    if raw[:8]==b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1':
        doc=CompDoc(raw,logfile=io.StringIO());data=doc.get_named_stream('Workbook')
        if data is None:data=doc.get_named_stream('Book')
    else:data=raw
    if data is None:raise SafeParseError('missing_workbook_stream')
    return projected_biff(data)

def parse_times(s,datemode):
    numeric=s.map(lambda x:isinstance(x,(int,float,np.number)) and not isinstance(x,bool))
    times=pd.to_datetime(s.where(~numeric).astype(str).str.strip().str.replace('/','-',regex=False),errors='coerce')
    if numeric.any():
        origin='1904-01-01' if datemode else '1899-12-30'
        times.loc[numeric]=pd.to_datetime(pd.to_numeric(s[numeric],errors='coerce'),unit='D',origin=origin,errors='coerce')
    return times

def haversine(a,b,c,d):
    p1,p2=np.radians(b),np.radians(d);dl=np.radians(c-a);dp=p2-p1
    return 6371.*2*np.arcsin(np.sqrt(np.clip(np.sin(dp/2)**2+np.cos(p1)*np.cos(p2)*np.sin(dl/2)**2,0,1)))

def gcj_to_wgs(lon,lat):
    # Standard one-step inverse GCJ offset, deterministic; China-region inputs.
    x=lon-105.;y=lat-35.;pi=np.pi
    dlat=-100+2*x+3*y+.2*y*y+.1*x*y+.2*np.sqrt(np.abs(x))
    dlat+=(20*np.sin(6*x*pi)+20*np.sin(2*x*pi))*2/3
    dlat+=(20*np.sin(y*pi)+40*np.sin(y*pi/3))*2/3
    dlat+=(160*np.sin(y*pi/12)+320*np.sin(y*pi/30))*2/3
    dlon=300+x+2*y+.1*x*x+.1*x*y+.1*np.sqrt(np.abs(x))
    dlon+=(20*np.sin(6*x*pi)+20*np.sin(2*x*pi))*2/3
    dlon+=(20*np.sin(x*pi)+40*np.sin(x*pi/3))*2/3
    dlon+=(150*np.sin(x*pi/12)+300*np.sin(x*pi/30))*2/3
    rad=np.radians(lat);magic=1-.006693421622965943*np.sin(rad)**2;sqrt=np.sqrt(magic)
    dlat=dlat*180/((6378245.*(1-.006693421622965943))/(magic*sqrt)*pi)
    dlon=dlon*180/(6378245./sqrt*np.cos(rad)*pi)
    return lon-dlon,lat-dlat

def corrected_xy(lon,lat,calibration=None):
    c=calibration or {};method=c.get('selected_method','raw_WGS84')
    if method=='GCJ02_to_WGS84':lon,lat=gcj_to_wgs(lon,lat)
    x,y=PROJECT.transform(lon,lat)
    if method=='constant_UTM_shift':x=x+c['applied_dx_m'];y=y+c['applied_dy_m']
    return np.asarray(x),np.asarray(y)

def baiguan_xy():
    t=pd.read_csv(ROOT/'01_panels/township_centroids_osm.csv',encoding='utf-8-sig')
    r=t[t.town.eq('百官')].iloc[0];return PROJECT.transform(float(r.lon),float(r.lat))

def daily_metrics(points,ph,calibration=None):
    rows=[];bgx,bgy=baiguan_xy()
    for day,g in points.groupby('date',sort=True):
        g=g.sort_values('timestamp',kind='stable');valid=g.valid_xy.to_numpy(bool)
        t=g.timestamp.astype('int64').to_numpy()/1e9;lon=g.lon.to_numpy();lat=g.lat.to_numpy();mov=g.moving.to_numpy(bool)
        n=len(g);kmh=np.zeros(24);kmr=np.zeros(5);kmrm=np.zeros(5);kmrh11=np.zeros(5);ptsr=np.zeros(5,int)
        x,y=corrected_xy(lon[valid],lat[valid],calibration);ri=np.searchsorted([2,4,7,12],np.hypot(x-bgx,y-bgy)/1000,side='right')
        np.add.at(ptsr,ri,1)
        # Exact vectorisation of pilot's last valid coordinate carry-forward.
        lonff=pd.Series(lon).ffill().to_numpy();latff=pd.Series(lat).ffill().to_numpy()
        gap=np.diff(t);d=haversine(lonff[:-1],latff[:-1],lon[1:],lat[1:])
        eligible=valid[1:]&np.isfinite(lonff[:-1])&(gap>0)
        with np.errstate(divide='ignore',invalid='ignore'):speed_implied=d/(gap/3600)
        accept=eligible&(speed_implied<=150);jumps=int((eligible&(speed_implied>150)).sum())
        moving=mov[1:]|mov[:-1];hours=g.timestamp.dt.hour.to_numpy()[:-1]
        dist=float(d[accept].sum());distmov=float(d[accept&moving].sum());from11=float(d[accept&(hours>=11)].sum())
        px,py=corrected_xy(lonff[:-1][accept],latff[:-1][accept],calibration)
        ring=np.searchsorted([2,4,7,12],np.hypot(px-bgx,py-bgy)/1000,side='right')
        np.add.at(kmr,ring,d[accept]);np.add.at(kmrm,ring[moving[accept]],d[accept&moving]);np.add.at(kmh,hours[accept&moving],d[accept&moving])
        np.add.at(kmrh11,ring[hours[accept]>=11],d[accept&(hours>=11)])
        r=dict(vehicle_ph=ph,date=day,n_rows=n,n_parsed_time=n,n_valid_xy=int(valid.sum()),n_moving=int(mov.sum()),n_occupied=int(g.occupied.sum()),hours_active=int(g.timestamp.dt.hour.nunique()),dist_km=dist,dist_moving_km=distmov,km_from_11h=from11,n_jump_segments=jumps,coordinate_variant=(calibration or {}).get('selected_method','raw_WGS84'))
        r.update({f'km_h{h:02d}':float(kmh[h]) for h in range(24)})
        for i,ring in enumerate(RINGS):r.update({f'km_ring_{ring}':float(kmrm[i]),f'km_total_ring_{ring}':float(kmr[i]),f'km_moving_ring_{ring}':float(kmrm[i]),f'km_ring_h11_{ring}':float(kmrh11[i]),f'pts_ring_{ring}':int(ptsr[i])})
        rows.append(r)
    return rows

def worker(payload):
    ph=payload['ph'];path=Path(payload['path']);before=path.stat();frames,mode,counters=read_projected_workbook(path)
    gps=[];bad=0;sheet_row_counts={};mismatch=0
    for f in frames:
        sd=f.attrs['sheet_date'];sheet_row_counts[sd]=sheet_row_counts.get(sd,0)+len(f)
        if f.empty:continue
        ts=parse_times(f['时间'],mode);ok=ts.notna();bad+=int((~ok).sum());f=f.loc[ok];ts=ts.loc[ok]
        mismatch+=int(ts.dt.strftime('%Y-%m-%d').ne(sd).sum())
        lon=pd.to_numeric(f['经度'],errors='coerce');lat=pd.to_numeric(f['纬度'],errors='coerce');speed=pd.to_numeric(f['速度'],errors='coerce')
        v=(lon>=120.3)&(lon<=121.4)&(lat>=29.5)&(lat<=30.5)
        date=ts.dt.strftime('%Y-%m-%d');period=(ts>=pd.Timestamp('2021-07-06'))&(ts<pd.Timestamp('2021-08-01'))
        g=pd.DataFrame(dict(timestamp=ts,date=date,lon=lon.where(v),lat=lat.where(v),speed=speed,heading=f['方向'].astype(str),state=f['车辆状态'].astype(str),transmit=f['传送标识'].astype(str),valid_xy=v,moving=speed.gt(0),occupied=f['车辆状态'].astype(str).str.contains('载客',regex=False)))
        gps.append(g.loc[period])
    points=pd.concat(gps,ignore_index=True) if gps else pd.DataFrame(columns=['timestamp','date','lon','lat','speed','heading','state','transmit','valid_xy','moving','occupied'])
    points.sort_values(['date','timestamp'],kind='stable',inplace=True)
    target=INTERNAL/'taxi_gps_points';target.mkdir(parents=True,exist_ok=True)
    temp=target/(ph+'.partial.parquet');final=target/(ph+'.parquet');points.to_parquet(temp,index=False)
    rows=daily_metrics(points,ph)
    row_by_day={r['date']:r for r in rows}
    for day,nrows in sheet_row_counts.items():
        if not ('2021-07-06'<=day<'2021-08-01'):continue
        if day not in row_by_day:
            zero=dict(vehicle_ph=ph,date=day,n_rows=nrows,n_parsed_time=0,n_valid_xy=0,n_moving=0,n_occupied=0,hours_active=0,dist_km=0.,dist_moving_km=0.,km_from_11h=0.,n_jump_segments=0,coordinate_variant='raw_WGS84')
            zero.update({f'km_h{h:02d}':0. for h in range(24)})
            for ring in RINGS:
                for pre in ['km_ring_','km_total_ring_','km_moving_ring_','km_ring_h11_','pts_ring_']:zero[pre+ring]=0
            row_by_day[day]=zero
        row_by_day[day]['n_rows']=nrows
    rows=[row_by_day[d] for d in sorted(row_by_day)];after=path.stat()
    if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):temp.unlink(missing_ok=True);raise SafeParseError('source_changed')
    temp.replace(final);counters.update(rows=int(len(points)),source_rows=int(sum(sheet_row_counts.values())),bad_time=bad,date_sheet_mismatch=mismatch,datemode=int(mode),sheets_complete=True)
    return dict(ph=ph,complete=True,source=dict(size=before.st_size,mtime_ns=before.st_mtime_ns),counters=counters,rows=rows)

def recompute_ring_metrics(calibration):
    original=pd.read_csv(INTERNAL/'taxi_vehicle_day_v6.csv',encoding='utf-8-sig').set_index(['vehicle_ph','date'])
    paths=sorted((INTERNAL/'taxi_gps_points').glob('*.parquet'))
    if len(paths)!=290:raise SafeParseError('incomplete_GPS_cache')
    for p in paths:
        rows=daily_metrics(pd.read_parquet(p),p.stem,calibration)
        for r in rows:
            key=(p.stem,r['date'])
            if key not in original.index:raise SafeParseError('daily_GPS_cache_key_mismatch')
            for col,value in r.items():
                if col.startswith(('km_ring_','km_total_ring_','km_moving_ring_','pts_ring_')) or col=='coordinate_variant':original.loc[key,col]=value
    original.reset_index().to_csv(INTERNAL/'taxi_vehicle_day_v6.csv',index=False,encoding='utf-8-sig',float_format='%.6f')
    return len(original)

def validate_daily_distances(daily):
    old=pd.read_csv(ROOT/'01_panels/taxi_vehicle_day.csv');old=old[old.batch.eq('GPS0706-0731')].copy()
    old['sheet_date']=pd.to_datetime(old.sheet_date.astype(str).str.replace('-','',regex=False),format='%Y%m%d',errors='raise').dt.strftime('%Y-%m-%d')
    domain=old.sheet_date.ge('2021-07-06')&old.sheet_date.lt('2021-08-01')
    outside=old[~domain].groupby('sheet_date').agg(vehicle_days=('n_rows','size'),n_rows=('n_rows','sum'),dist_km=('dist_km','sum')).reset_index().to_dict('records')
    for r in outside:r.update(included_new_analysis_km=0.,analysis_exclusion_km_difference=-float(r['dist_km']))
    compare=old[domain].groupby('sheet_date').dist_km.sum().rename('old_km').to_frame().join(daily.groupby('date').dist_km.sum().rename('new_km'))
    compare=compare.join(old[domain].groupby('sheet_date').agg(old_vehicle_days=('n_rows','size'),old_source_rows=('n_rows','sum'))).join(daily.groupby('date').agg(new_vehicle_days=('n_rows','size'),new_source_rows=('n_rows','sum')))
    compare['vehicle_day_count_difference']=compare.new_vehicle_days-compare.old_vehicle_days;compare['source_row_count_difference']=compare.new_source_rows-compare.old_source_rows
    compare['rel_difference']=(compare.new_km-compare.old_km).abs()/compare.old_km
    compare.reset_index().rename(columns={'sheet_date':'date'}).to_csv(OUT/'00_env/taxi_parse_daily_validation_v6.csv',index=False,encoding='utf-8-sig',float_format='%.6f')
    passed=bool(len(compare)==26 and compare.rel_difference.notna().all() and compare.rel_difference.le(.01).all())
    return passed,float(compare.rel_difference.max()),outside

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--worker',action='store_true');parser.add_argument('--recompute-rings',action='store_true');parser.add_argument('--validate-only',action='store_true');args=parser.parse_args()
    if args.worker:
        try:result=worker(json.loads(sys.stdin.read()));print(json.dumps(result,ensure_ascii=False,allow_nan=False))
        except BaseException as e:print(json.dumps(dict(error_type=type(e).__name__,error_code=str(e) if isinstance(e,SafeParseError) else None)));sys.exit(1)
        return
    start=NOW();tick=time.monotonic();(OUT/'00_env').mkdir(parents=True,exist_ok=True)
    if args.validate_only:
        daily=pd.read_csv(INTERNAL/'taxi_vehicle_day_v6.csv',encoding='utf-8-sig');path=OUT/'00_env/taxi_parse_execution_v6.json'
        report=json.loads(path.read_text(encoding='utf-8'))
        if report.get('workbooks_complete')!=290 or len(list((INTERNAL/'taxi_gps_points').glob('*.parquet')))!=290:raise SafeParseError('cannot_validate_incomplete_workbook_stage')
        passed,maxdiff,outside=validate_daily_distances(daily)
        report.update(legacy_daily_distance_within_1pct=passed,max_relative_difference=maxdiff,legacy_outside_analysis_dates=outside,validation_repair=dict(start=start,end=NOW(),seconds=time.monotonic()-tick,source_reads=False,key_reads=False,reason='restrict legacy comparison to same GPS analysis domainJuly6..31; legacy includes oneJuly5sheet',command=_release_path('path_025')))
        path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(dict(validate_only=True,passed=passed,max_relative_difference=maxdiff,legacy_outside_analysis_dates=outside),ensure_ascii=False))
        if not passed:raise SafeParseError('legacy_daily_distance_validation_failed')
        return
    if args.recompute_rings:
        cal=json.loads((OUT/'03_taxi_probe/T29_calibration_v6.json').read_text(encoding='utf-8'))
        nrows=recompute_ring_metrics(cal)
        (OUT/'00_env/taxi_ring_recompute_execution_v6.json').write_text(json.dumps(dict(start=start,end=NOW(),seconds=time.monotonic()-tick,calibration_method=cal['selected_method'],rows=nrows),indent=2),encoding='utf-8');return
    from taxi_probe_hash_v6 import get_probe_files_hashed
    mapping=get_probe_files_hashed();items=list(mapping.items()) if isinstance(mapping,dict) else list(mapping)
    if len(items)!=290 or len({ph for _,ph in items})!=290:raise SafeParseError('expected_290_distinct_workbooks')
    cp=INTERNAL/'taxi_parse_checkpoints';cp.mkdir(parents=True,exist_ok=True);allrows=[];execution=[]
    for idx,(path,ph) in enumerate(sorted(items,key=lambda v:v[1]),1):
        path=Path(path);st=path.stat();meta=dict(size=st.st_size,mtime_ns=st.st_mtime_ns);cache=cp/(ph+'.json');result=None
        if cache.exists() and (INTERNAL/'taxi_gps_points'/f'{ph}.parquet').exists():
            c=json.loads(cache.read_text(encoding='utf-8'))
            if c.get('source')==meta and c.get('complete'):result=c
        for attempt in range(1,4):
            if result is not None:break
            env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1')
            proc=None
            try:
                proc=subprocess.run([PYTHON,str(Path(__file__)),'--worker'],input=json.dumps(dict(path=str(path),ph=ph),ensure_ascii=False).encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=420,env=env)
                safe=json.loads(proc.stdout.decode('utf-8'))
                if proc.returncode==0 and safe.get('complete') and safe.get('source')==meta:result=safe
                else:execution.append(dict(workbook_index=idx,attempt=attempt,error_type=safe.get('error_type','WorkerExit'),error_code=safe.get('error_code'),exit_code=proc.returncode))
            except BaseException as e:execution.append(dict(workbook_index=idx,attempt=attempt,error_type=type(e).__name__,exit_code=proc.returncode if proc is not None else None,stdout_bytes=len(proc.stdout) if proc is not None else None,stderr_bytes=len(proc.stderr) if proc is not None else None))
        if result is None:
            (OUT/'00_env/taxi_parse_execution_v6.json').write_text(json.dumps(dict(start=start,end=NOW(),complete=False,workbooks_complete=idx-1,failures=execution),indent=2),encoding='utf-8');raise SafeParseError('workbook_failed_bounded_retries')
        cache.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8');allrows.extend(result['rows'])
        print(f'{NOW()} workbooks_complete={idx}/290',flush=True)
    daily=pd.DataFrame(allrows);daily.to_csv(INTERNAL/'taxi_vehicle_day_v6.csv',index=False,encoding='utf-8-sig',float_format='%.6f')
    passed,maxdiff,outside=validate_daily_distances(daily)
    report=dict(start=start,end=NOW(),seconds=time.monotonic()-tick,workbooks_complete=290,complete=True,daily_rows=len(daily),GPS_rows=sum(json.loads(p.read_text(encoding='utf-8'))['counters']['rows'] for p in cp.glob('*.json')),legacy_daily_distance_within_1pct=passed,max_relative_difference=maxdiff,legacy_outside_analysis_dates=outside,failures=execution,projection_columns=COLS,method='BIFF row/column projection before SST selected-string decode; no xlrd.open_workbook or sheet materialisation')
    (OUT/'00_env/taxi_parse_execution_v6.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if not passed:raise SafeParseError('legacy_daily_distance_validation_failed')

if __name__=='__main__':
    try:main()
    except Exception as e:
        print(json.dumps(dict(error_type=type(e).__name__,error_code=str(e) if isinstance(e,SafeParseError) else None)),flush=True)
        sys.exit(1)
