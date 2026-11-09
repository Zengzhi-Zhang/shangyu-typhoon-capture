# -*- coding: utf-8 -*-
"""Full Appendix D comparison: point estimates remain independent of pilot targets."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[3]), str(_ReleasePath(__file__).resolve().parents[1])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from common_v1 import *
def append_comparisons(rows,read,jread):
    def add(metric,pilot,formal,date='',kind='ratio',reason=''):
        if formal is None or pd.isna(formal):return
        cutoff=.1*abs(pilot) if kind=='count' else .03
        rows.append(dict(metric=metric,date=date,pilot=pilot,formal=float(formal),difference=float(formal)-pilot,requires_explanation=abs(float(formal)-pilot)>cutoff,reason=reason))
    same='正式S*=855按冻结同星期阈值选取，先导车辆分析使用S*=932；所有原始记录日总和一致，集合与同星期基线不同可改变车辆比值和规律性分布。'
    m2=read('03_m2_two_sources/m2_daily_ratios.csv').set_index('date')
    for d,m,v in [('2021-07-25','R_taxi_km',.714),('2021-07-26','R_taxi_active',.897),('2021-07-26','taxi_occ_share',.416)]:
        add('D2_'+m,v,m2.loc[d,m],d,reason='冻结第二批B_TAXI同星期基线；原缓存里程口径dist_moving_km。')
    timing=read('06_m5_bias_correction/m5_failure_timing.csv')
    if not timing.empty:
        add('D3_failed_first_0725_afternoon',100,timing.loc[timing.first_failure_date=='2021-07-25','n_devices'].sum(),'2021-07-26',kind='count',reason='前周F(7/26)设备按冻结5%阈值，7/25仅11–23匹配时段检测首失效；先导阈值/集合不同。')
    # Appendix D3 percentages are P(F|group), never P(group|F).
    diag=read('07_m6_robustness/m6_pilot_conditioning_diagnostic.csv')
    if not diag.empty:
        for sample,cat,pilot in [('formal_corrected_full_A200','primary',.40),('formal_org_full_A200',_release_private('private_value_001'),.26)]:
            z=diag[(diag['sample']==sample)&(diag.category==cat)]
            if len(z):add('D3_conditional_failure_rate_'+sample+'_'+cat,pilot,z.iloc[0].P_failure_given_group,'2021-07-26',reason='同口径P(F|group)对照；先导primary=12/30，机构=90/344。正文OSM80m路类与corrected-road辅助分类分别报告，失效构成份额不与条件失效率混比。')
    moran=jread('05_m4_spatial/m4_moran.json',{})
    for d,v in [('2021-07-26',7.2),('2021-07-28',6.4),('2021-08-02',4.1)]:
        x=moran.get('joincount',{}).get(d,{})
        if x:add('D3_joincount_z',v,x.get('z'),d,reason=_release_private('private_value_002'))
    x=moran.get('moran',{}).get('2021-07-26',{})
    if x:add('D3_Moran_z',5.3,x.get('z'),'2021-07-26',reason='A100全天S_on、6最近邻在线log比，999置换；不替用先导在线集合。')
    av=jread('00_env/vehicle_avi_execution.json',{}).get('checks',{})
    if av:
        add('plate_master_total',3857792,av.get('master_rows'),kind='count',reason='本轮由全部三份CSV重新HMAC并独立聚合；类别不依赖S*。')
        for cat,n in [('other_province',1551681),('zhejiang_other',1384096),('local_zheD',920803),('unreadable',1212)]:
            add('plate_master_'+cat,n,av.get('category_counts',{}).get(cat),kind='count',reason='冻结号牌类别，按内容判断；不可读是占位字符串数，不解释为车辆数。')
        add('plate_master_NEV',110731,av.get('nev'),kind='count',reason='冻结8位且末位非特殊标记规则。')
    gr=read('04_m3_vehicles/m3_daily_by_group.csv')
    if not gr.empty:
        sel=gr[gr.date=='2021-07-26'].set_index('grp')
        for grp,values in [('all',{'rP':.661,'rN':.597}),('local_zheD_ICE',{'rP':.801,'rN':.618}),('other_province_ICE',{'rP':.451,'rN':.457}),('zhejiang_other_ICE',{'rP':.536,'rN':.449})]:
            if grp in sel.index:
                for m,v in values.items():add('D4_'+grp+'_'+m,v,sel.loc[grp,m],'2021-07-26',reason=same)
        for grp,m in [('local_zheD_ICE',18.7),('other_province_ICE',7.4)]:
            if grp in sel.index:add('D4_'+grp+'_passes_per_plate',m,sel.loc[grp,'passes_per_plate'],'2021-07-26',kind='count',reason=same)
    curve=read('04_m3_vehicles/m3_return_curve.csv')
    if not curve.empty:
        pilots={'all':{'typhoon':[.444,.704,.841,.872],'placebo':[.813,.886,.880,.876]},'other_province':{'typhoon':[.310,.474,.635,.705],'placebo':[.790,.808,.802,.789]}}
        for grp,windows in pilots.items():
            for window,vals in windows.items():
                s=curve[(curve.thr==8)&(curve.grp==grp)&(curve.window==window)].set_index('k')
                for k,v in enumerate(vals,1):add('D5_'+grp+'_'+window+'_present_k'+str(k),v,s.loc[k,'present'],s.loc[k,'date'],reason=same+' 台风k1按7/25小时可见范围；安慰剂主版本全天。')
        for window,v in [('typhoon',.740),('placebo',.785)]:
            s=curve[(curve.thr==8)&(curve.grp=='other_province')&(curve.window==window)&(curve.k==9)].iloc[0]
            add('D5_other_province_'+window+'_present_k9',v,s.present,s.date,reason=same)
    comp=read('04_m3_vehicles/m3_composition.csv')
    if not comp.empty:
        s=comp[(comp.thr==8)&(comp.window=='typhoon')].sort_values('date')
        for c,start,end in [('regular',.48,.39),('unseen',.20,.24)]:
            for label,v,r in [('first',start,s.iloc[0]),('last',end,s.iloc[-1])]:add('D6_'+c+'_'+label,v,r['share_'+c],r.date,reason=same)
        p=comp[(comp.thr==8)&(comp.window=='placebo')]
        for c,low,high in [('regular',.35,.37),('unseen',.25,.27)]:
            add('D6_placebo_'+c+'_min',low,p['share_'+c].min(),reason=same)
            add('D6_placebo_'+c+'_max',high,p['share_'+c].max(),reason=same)
    road=read('05_m4_spatial/m4_by_road_level.csv')
    if not road.empty:
        road=road.set_index('group')
        for level,v in [('motorway/trunk',.551),('primary',.554),('secondary',.655),('tertiary',.640),('residential/service',.678)]:
            if level in road.index:add('D7_road_'+level,v,road.loc[level,'flow_r_0726_online'],'2021-07-26',reason='正式A100与全天S_on、实际来源坐标和80m路段匹配；不混先导不同在线集合。')
    ols=read('05_m4_spatial/m4_ols.csv')
    if not ols.empty:
        for d,v in [('2021-07-26',-.0855),('2021-07-27',-.0529)]:
            z=ols[(ols.date==d)&(ols.term=='log1p_dist')]
            if z.empty:z=ols[(ols.date==d)&ols.term.str.contains('log1p')]
            if not z.empty:add('D7_OLS_distance',v,z.iloc[0].coef,d,reason='固定S*有坐标完整案例；实际source属性修复后重新计算HC1 OLS，样本量与先导763不同。')
    return rows
