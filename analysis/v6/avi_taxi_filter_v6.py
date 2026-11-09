# -*- coding: utf-8 -*-
"""Stream only the three authorised CSVs; serialise only selected taxi rows."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[2]), str(_ReleasePath(__file__).resolve().parents[0])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from pathlib import Path
from datetime import datetime,timezone,timedelta
import json,time,sys,hashlib
import pandas as pd,numpy as np,pyarrow as pa,pyarrow.parquet as pq
from taxi_probe_hash_v6 import hasher
R=Path(_release_path('project_root'));O=R/'formal_v6';S=Path(_release_path('path_004'))
FILES=['AVI_20210627.csv','AVI_20210628_0704.csv','AVI_0705-0803.csv'];CHUNK=3_000_000
def stamp():return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
def main():
    start=time.perf_counter();beg=stamp();checks=json.loads((O/'00_env/hash_check_v6.json').read_text(encoding='utf-8'))
    if checks['S1_triggered']:raise RuntimeError('S1 blocks AVI stage')
    target=set((O/'01_internal/taxi_probe_ph_v6.txt').read_text(encoding='utf-8').splitlines());hsh=hasher()
    mapping=pd.read_csv(R/'01_panels/device_id_map.csv',dtype=str,encoding='utf-8-sig');name_map=dict(zip(mapping.dev_name,mapping.dev))
    cache={};unknown=set();rows=total=missing=0;counts={};writer=None;progress=[]
    dest=O/'01_internal/taxi_avi_records_v6.parquet';tmp=O/'01_internal/taxi_avi_records_v6.partial.parquet'
    before={f:dict(size=(S/f).stat().st_size,mtime_ns=(S/f).stat().st_mtime_ns) for f in FILES}
    log=O/'00_env/avi_filter_progress_v6.log'
    def note(s):
        with log.open('a',encoding='utf-8') as out:out.write(stamp()+' '+s+'\n')
        print(stamp(),s,flush=True)
    try:
        for fi,f in enumerate(FILES,1):
            note(f'AVI_SOURCE_{fi:02d} begin')
            reader=pd.read_csv(S/f,usecols=[0,1,2,3,4],names=['plate','dev','dir','lane','ts'],header=0,dtype=str,encoding='utf-8-sig',keep_default_na=False,quotechar='"',chunksize=CHUNK)
            for ci,df in enumerate(reader):
                pl=df.plate.str.strip('"');uniq=pl.unique()
                for plate in uniq:
                    if plate not in cache:
                        ph=hsh(plate);cache[plate]=ph if ph in target else None
                lookup={p:cache[p] for p in uniq};selected=pl.map(lookup);q=df.loc[selected.notna()].copy();q['ph']=selected.loc[q.index]
                if len(q):
                    rawdev=q.dev.str.strip('"')
                    for name in rawdev.unique():
                        if name not in name_map:unknown.add(hashlib.sha256(name.encode('utf-8')).hexdigest());name_map[name]='unknown_'+hashlib.sha256(name.encode('utf-8')).hexdigest()[:16]
                    sp=q.ts.str.strip('"').str.split(' ',n=1,expand=True)
                    dates={v:datetime.strptime(v.strip(),'%Y/%m/%d').strftime('%Y-%m-%d') for v in sp[0].unique()}
                    tm=sp[1].str.split(':',expand=True) if sp.shape[1]>1 else pd.DataFrame(index=q.index)
                    sec=pd.Series(-1,index=q.index,dtype='int32')
                    if tm.shape[1]>=3:
                        seconds=pd.to_numeric(tm[0],errors='coerce')*3600+pd.to_numeric(tm[1],errors='coerce')*60+pd.to_numeric(tm[2],errors='coerce')
                        sec=seconds.fillna(-1).astype('int32')
                    out=pd.DataFrame(dict(ph=q.ph.astype(str),dev=rawdev.map(name_map).astype(str),date=sp[0].map(dates),sec_of_day=sec,dir=q['dir'].str.strip('"'),lane=q.lane.str.strip('"')))
                    table=pa.Table.from_pandas(out,preserve_index=False)
                    if writer is None:writer=pq.ParquetWriter(tmp,table.schema,compression='snappy')
                    writer.write_table(table);rows+=len(out);missing+=int((sec<0).sum())
                    for d,n in out.groupby('date').size().items():counts[d]=counts.get(d,0)+int(n)
                total+=len(df);rec=dict(file_id=f'AVI_SOURCE_{fi:02d}',chunk=ci+1,source_rows=total,taxi_rows=rows,seconds=time.perf_counter()-start);progress.append(rec)
                note(f'AVI_SOURCE_{fi:02d} chunk={ci+1} source_rows={total} selected_rows={rows} elapsed_min={(time.perf_counter()-start)/60:.2f}')
                del df,pl,q,selected,lookup
        if writer:writer.close();writer=None
        after={f:dict(size=(S/f).stat().st_size,mtime_ns=(S/f).stat().st_mtime_ns) for f in FILES}
        assert before==after,'Source metadata changed'
        check=pd.read_csv(O/'03_taxi_probe/hash_daily_check_v6.csv').set_index('date');mismatches=[]
        for d,r in check.iterrows():
            if int(r.rec_all)!=counts.get(d,0):mismatches.append(dict(date=d,panel=int(r.rec_all),scanned=counts.get(d,0)))
        report=dict(start=beg,end=stamp(),elapsed_seconds=time.perf_counter()-start,source_rows=total,taxi_rows=rows,missing_sec_of_day=missing,unknown_device_count=len(unknown),all_daily_counts_match=not mismatches,mismatches=mismatches,source_metadata_unchanged=True,source_files=[dict(file_id=f'AVI_SOURCE_{i+1:02d}',**before[f]) for i,f in enumerate(FILES)],progress=progress)
        (O/'00_env/avi_filter_execution_v6.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        if mismatches:raise RuntimeError('Taxi AVI counts differ from plate-day panel; dependent calculations stopped')
        tmp.replace(dest)
        note(f'DONE rows={rows} all37days_equal=True unknown_devices={len(unknown)} seconds={report["elapsed_seconds"]:.2f}')
    finally:
        if writer:writer.close()
if __name__=='__main__':
    try:main()
    except Exception as e:print('AVI-stage failure type='+type(e).__name__,flush=True);raise SystemExit(1)
