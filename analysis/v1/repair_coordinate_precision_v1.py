from common_v1 import *
prior=pd.read_csv(REF/'results/device_panel.csv',encoding='utf-8-sig')
mapping=pd.read_csv(ROOT/'01_panels/device_id_map.csv',encoding='utf-8-sig').set_index('dev_name').dev
prior['dev']=prior.dev.map(mapping);prior=prior.set_index('dev')
for name in ['device_attributes_base.csv','device_attributes.csv']:
    df=pd.read_csv(ROOT/f'01_panels/{name}',encoding='utf-8-sig').set_index('dev')
    for c in ['lon','lat']:df[c]=prior[c].reindex(df.index)
    save_csv(df.reset_index(),ROOT/f'01_panels/{name}')
print('Internal coordinate precision restored',flush=True)
