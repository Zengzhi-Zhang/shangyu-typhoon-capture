# -*- coding: utf-8 -*-
"""Reconcile frozen reference panels and compute formal device sets; never edit reference data."""
import sys,shutil
from common_v1 import *
START=now()
def main():
    dh=pd.read_csv(REF/'results/device_hour.csv',encoding='utf-8-sig')
    dh['date']=pd.to_datetime(dh.date.astype(str).str.replace('"','',regex=False)).dt.strftime('%Y-%m-%d')
    for c in ['hour','n','n_unread']:dh[c]=pd.to_numeric(dh[c],errors='raise').astype('int64')
    mapping=pd.DataFrame({'dev_name':sorted(dh.dev.unique())})
    mapping['dev']=mapping.dev_name.map(lambda x:pseudonym(x,'cam_'))
    save_csv(mapping,ROOT/'01_panels/device_id_map.csv')
    dm=mapping.set_index('dev_name').dev.to_dict()
    dh.dev=dh.dev.map(dm)
    save_csv(dh,ROOT/'01_panels/device_hour.csv')
    dl=pd.read_csv(REF/'results/device_dir_lane_day.csv',encoding='utf-8-sig')
    dl.date=pd.to_datetime(dl.date.astype(str).str.replace('"','',regex=False)).dt.strftime('%Y-%m-%d')
    dl.dev=dl.dev.map(dm); save_csv(dl,ROOT/'01_panels/device_dir_lane_day.csv')
    dd=dh.pivot_table(index='dev',columns='date',values='n',aggfunc='sum',fill_value=0).reindex(columns=D_ALL,fill_value=0)
    attr=pd.DataFrame(index=dd.index)
    avi=SOURCE/'10_上虞数据/AVI'
    if '--reference-attributes' in sys.argv:
        prior=pd.read_csv(REF/'results/device_panel.csv',encoding='utf-8-sig',dtype={'dev':str})
        loc=prior[['dev','lon','lat']].rename(columns={'dev':'dev_name'}).copy()
    else:
        loc=pd.read_csv(avi/'sensor_location.csv',encoding='utf-8-sig',dtype=str)
        loc.columns=['dev_name','lon','lat']
    loc['dev']=loc.dev_name.map(dm)
    for col in ['lon','lat']:loc[col]=pd.to_numeric(loc[col],errors='coerce')
    loc.loc[(loc.lon==0)|(loc.lat==0),['lon','lat']]=np.nan
    # §2.1 filters invalid coordinates before selecting one device location.
    # A zero-valued first row must not hide a later valid duplicate location.
    loc=loc.dropna(subset=['dev','lon','lat']).drop_duplicates('dev').set_index('dev')
    attr=attr.join(loc[['lon','lat']])
    if '--reference-attributes' in sys.argv:cls=prior[['dev','dev_type','org']].rename(columns={'dev':'dev_name'}).copy()
    else:
        cls=pd.read_csv(avi/'sensor_classification.csv',encoding='utf-8-sig',dtype=str)
        cls.columns=['dev_name','dev_type','org']
    cls['dev']=cls.dev_name.map(dm)
    attr=attr.join(cls.dropna(subset=['dev']).drop_duplicates('dev').set_index('dev')[['dev_type','org']])
    attr['gateway']=mapping.set_index('dev').dev_name.str.contains('高速|国道').astype(int)
    for b,days in BASELINES.items():attr['base_'+b]=dd[days].mean(axis=1)
    attr['in_A100']=(attr.base_B1>=100).astype(int);attr['in_A200']=(attr.base_B1>=200).astype(int)
    stable=attr.in_A100==1
    online=[]
    for d in D_ALL:
        den=dd[refs(d)].mean(axis=1); r=dd[d]/den.replace(0,np.nan)
        ids=attr.index[(attr.in_A100==1)&(r>=.2)]
        online.extend({'date':d,'dev':dev} for dev in ids)
        if d in dates('2021-07-26','2021-07-30'):stable &= r>=.2
        if d in ['2021-07-29','2021-07-30']:stable &= r>=.5
    attr['in_Sstar']=stable.astype(int)
    save_csv(pd.DataFrame(online),ROOT/'01_panels/online_sets.csv')
    attr.index.name='dev';save_csv(attr.reset_index(),ROOT/'01_panels/device_attributes_base.csv')
    if (ROOT/'01_panels/spatial_covariates.csv').exists():
        sp=pd.read_csv(ROOT/'01_panels/spatial_covariates.csv',encoding='utf-8-sig').set_index('dev')
        sp=sp.drop(columns=[c for c in ['lon','lat'] if c in sp])
        merged=attr.join(sp)
        merged['log_base']=np.log(merged.base_B1.replace(0,np.nan))
        save_csv(merged.reset_index(),ROOT/'01_panels/device_attributes.csv')
    save_csv(dd.reset_index().melt(id_vars='dev',var_name='date',value_name='n'),ROOT/'01_panels/device_day.csv')
    taxi=pd.read_csv(REF/'results/taxi_vehicle_day_all.csv',encoding='utf-8-sig',dtype={'sheet_date':str,'vehicle_hash':str})
    taxi['sheet_date']=pd.to_datetime(taxi.sheet_date,format='%Y%m%d').dt.strftime('%Y-%m-%d')
    save_csv(taxi,ROOT/'01_panels/taxi_vehicle_day.csv')
    frozen=[7176362,10266738,10555107,10633361,10216538,10040231,9939461,9354368,9643553,9797804,8612826,4997946,9050291,6221538,8929957,8965546,8813599,8819294,8782228,9115850,8929689,8490418,8829771,8332865,8000868,54895,61637,44040,1940937,4227789,6393473,8130855,7751421,7862672,7767792,7713611,7686984]
    actual=dd.sum().reindex(D_ALL)
    checks=pd.DataFrame({'date':D_ALL,'records':actual.values.astype(int),'pilot_records':frozen})
    checks['difference']=checks.records-checks.pilot_records
    save_csv(checks,ROOT/'01_panels/record_count_checks.csv')
    info=dict(device_hour_rows=len(dh),device_dir_lane_rows=len(dl),records=int(dh.n.sum()),date_only_records=int(dh.loc[dh.hour<0,'n'].sum()),taxi_rows=len(taxi),n_devices=len(attr),A100=int(attr.in_A100.sum()),A200=int(attr.in_A200.sum()),S_star=int(attr.in_Sstar.sum()),record_counts_all_match=bool((checks.difference==0).all()),attribute_source='frozen_reference' if '--reference-attributes' in sys.argv else 'raw_source',baseline_dow_counts={b:{str(k):sum(pd.Timestamp(d).dayofweek==k for d in ds) for k in range(7)} for b,ds in BASELINES.items()})
    write_json(ROOT/'00_env/panel_initial_checks.json',info)
    (ROOT/'01_panels/NOT_FOR_PUBLICATION.md').write_text('本目录含车辆HMAC、设备内部名称映射和设备精确坐标，仅供内部审阅复算，禁止随论文发布。00_env/.hmac_key不进入任何交付清单或发布包。\n',encoding='utf-8')
    stage_record('panels',START,[str(x.relative_to(ROOT)) for x in (ROOT/'01_panels').glob('*') if x.is_file()],info)
    print(json.dumps(info,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
