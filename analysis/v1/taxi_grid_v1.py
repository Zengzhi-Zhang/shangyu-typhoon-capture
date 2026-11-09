# -*- coding: utf-8 -*-
"""Read-only, second-batch taxi GPS aggregation; no row, filename, or vehicle identifier is persisted."""
import xlrd,sys,time
from collections import defaultdict
from pyproj import Transformer
from common_v1 import *
START=now(); rng=np.random.default_rng(SEED)
def main():
    files=sorted((SOURCE/'10_上虞数据/GPS/GPS0706-0731').glob('*.xls'))
    grid=defaultdict(lambda:[0,0,0]); hourly=defaultdict(lambda:[0,0,0])
    failures=[]; counters=dict(workbooks=len(files),sheets=0,valid_points=0,invalid_xy=0,bad_time=0,date_mismatch=0,excluded_out_of_period=0)
    source_before={pseudonym(p.stem):{'size':p.stat().st_size,'mtime_ns':p.stat().st_mtime_ns} for p in files}
    proj=Transformer.from_crs(4326,32651,always_xy=True)
    began=time.time()
    for fi,p in enumerate(files):
        cells_seen=set(); moving_hours_seen=set()
        try:wb=xlrd.open_workbook(str(p),on_demand=True)
        except Exception as e:
            failures.append(dict(workbook_id=pseudonym(p.stem),error_type=type(e).__name__));continue
        for sn in wb.sheet_names():
            try:
                sh=wb.sheet_by_name(sn)
                if sh.nrows<3:continue
                hdr=[str(x).strip() for x in sh.row_values(1)]
                cols={k:hdr.index(k) for k in ['时间','速度','经度','纬度']}
                vals={k:sh.col_values(i,2) for k,i in cols.items()}
                tt=pd.Series(vals['时间'])
                isn=tt.map(lambda x:isinstance(x,(float,int)))
                stamp=pd.to_datetime(tt.where(~isn).astype(str).str.replace('/','-',regex=False),errors='coerce')
                if isn.any():stamp.loc[isn]=pd.to_datetime(pd.to_numeric(tt[isn]),unit='D',origin='1904-01-01' if wb.datemode else '1899-12-30',errors='coerce')
                xy=[pd.to_numeric(pd.Series(vals[k]),errors='coerce').to_numpy() for k in ['经度','纬度','速度']]
                lon,lat,spd=xy
                okxy=(lon>=120.3)&(lon<=121.4)&(lat>=29.5)&(lat<=30.5)
                ok=okxy&stamp.notna().to_numpy()
                counters['bad_time']+=int(stamp.isna().sum());counters['invalid_xy']+=int((~okxy).sum())
                inperiod=((stamp>=pd.Timestamp('2021-07-06'))&(stamp<pd.Timestamp('2021-08-01'))).to_numpy()
                counters['excluded_out_of_period']+=int((ok&~inperiod).sum());ok &= inperiod
                if not ok.any():continue
                datestr=stamp.loc[ok].dt.strftime('%Y-%m-%d').to_numpy(); hours=stamp.loc[ok].dt.hour.to_numpy()
                try:sd=pd.to_datetime(sn,format='%Y%m%d').strftime('%Y-%m-%d');counters['date_mismatch']+=int((datestr!=sd).sum())
                except Exception:pass
                e,n=proj.transform(lon[ok],lat[ok]);gx=np.floor(e/1000).astype(int);gy=np.floor(n/1000).astype(int)
                moving=np.isfinite(spd[ok])&(spd[ok]>0)
                df=pd.DataFrame(dict(date=datestr,gx=gx,gy=gy,moving=moving.astype(int),hour=hours))
                for (d,x,y),v in df.groupby(['date','gx','gy']).moving.agg(['size','sum']).iterrows():
                    cellkey=(d,int(x),int(y));a=grid[cellkey];a[0]+=int(v['size']);a[1]+=int(v['sum'])
                    if cellkey not in cells_seen:a[2]+=1;cells_seen.add(cellkey)
                for (d,h),v in df.groupby(['date','hour']).moving.agg(['size','sum']).iterrows():
                    hourkey=(d,int(h));a=hourly[hourkey];a[0]+=int(v['size']);a[1]+=int(v['sum'])
                    if v['sum']>0 and hourkey not in moving_hours_seen:a[2]+=1;moving_hours_seen.add(hourkey)
                counters['sheets']+=1;counters['valid_points']+=int(ok.sum())
            except Exception as e:
                try:sheet_alias=pd.to_datetime(sn,format='%Y%m%d').strftime('%Y-%m-%d') if len(str(sn))==8 else 'nondate'
                except Exception:sheet_alias='nondate'
                failures.append(dict(workbook_id=pseudonym(p.stem),sheet=sheet_alias,error_type=type(e).__name__))
            finally:wb.unload_sheet(sn)
        wb.release_resources()
        if (fi+1)%10==0:print('Taxi workbooks',fi+1,'/',len(files),'sheets',counters['sheets'],'minutes',round((time.time()-began)/60,1),flush=True)
    rows=[]
    for (d,x,y),(npnt,nmov,nv) in sorted(grid.items()):rows.append(dict(date=d,gx=x,gy=y,n_points=npnt,n_moving=nmov,n_vehicles=nv))
    out=pd.DataFrame(rows);out['n_vehicles']=out.n_vehicles.map(lambda n:'<10' if n<10 else str(n))
    save_csv(out,ROOT/'01_panels/taxi_grid_day.csv')
    centers=out[['gx','gy']].drop_duplicates().sort_values(['gx','gy'])
    inverse=Transformer.from_crs(32651,4326,always_xy=True)
    centers['lon'],centers['lat']=inverse.transform((centers.gx+.5)*1000,(centers.gy+.5)*1000)
    save_csv(centers,ROOT/'01_panels/taxi_grid_centroids.csv')
    hr=pd.DataFrame([dict(date=d,hour=h,taxi_points=a[0],taxi_moving_points=a[1],taxi_vehicles_moving=a[2]) for (d,h),a in sorted(hourly.items())])
    hr['taxi_vehicles_moving']=hr.taxi_vehicles_moving.map(lambda n:'<10' if n<10 else str(n))
    save_csv(hr,ROOT/'01_panels/taxi_hour_valid.csv')
    source_after={pseudonym(p.stem):{'size':p.stat().st_size,'mtime_ns':p.stat().st_mtime_ns} for p in files}
    counters.update(failures=failures,grid_rows=len(out),hour_rows=len(hr),elapsed_minutes=(time.time()-began)/60,source_before=source_before,source_after=source_after,source_unchanged=source_before==source_after,verified_complete=len(files)==290 and not failures and source_before==source_after and bool((out.n_moving<=out.n_points).all()))
    write_json(ROOT/'00_env/taxi_grid_checks.json',counters)
    stage_record('taxi_grid',START,['01_panels/taxi_grid_day.csv','01_panels/taxi_grid_centroids.csv','01_panels/taxi_hour_valid.csv'],counters)
    print('Taxi grids done',len(out),'failures',len(failures),flush=True)
    if not counters['verified_complete']:raise RuntimeError('Taxi-grid completeness verification failed; see anonymous checks.')
if __name__=='__main__':main()
