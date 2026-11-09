# -*- coding: utf-8 -*-
"""V4 manuscript figures/tables, consuming frozen aggregate results only."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[2]), str(_ReleasePath(__file__).resolve().parents[0])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from pathlib import Path
import argparse, hashlib, json, re, time, sys
from datetime import datetime, timezone, timedelta
import numpy as np
import pandas as pd

V1=Path(_release_path('project_root'));V3=V1/'formal_v3';ROOT=V1/'formal_v4';M=ROOT/'20_manuscript'
SEED=20261005
def now():return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
INPUTS={};OUTPUTS=[];PROV=[];CHECKS={}
def register(path):
    path=Path(path);st=path.stat();INPUTS[str(path)]=(st.st_size,st.st_mtime_ns);return path
def read(path):return pd.read_csv(register(path),encoding='utf-8-sig')
def readjson(path):return json.loads(register(path).read_text(encoding='utf-8'))
def provenance(value,file,key,usage,display=None):
    if isinstance(value,(bool,np.bool_)) or value is None:return
    if isinstance(value,(float,np.floating)) and not np.isfinite(value):return
    PROV.append(dict(value=value,display_value=value if display is None else display,source_file=str(file),source_row_or_key=str(key),usage=usage))
def frame_provenance(frame,path,usage,columns=None):
    for i,row in frame.iterrows():
        for c in columns or frame.columns:
            if c not in frame:continue
            v=row[c]
            if isinstance(v,(int,float,np.number)) and not pd.isna(v):provenance(v,path,f'CSV row {i+2}; column {c}',usage)
def flatten_numeric(obj,path,usage,key='$'):
    if isinstance(obj,dict):
        for k,v in obj.items():flatten_numeric(v,path,usage,key+'.'+str(k))
    elif isinstance(obj,list):
        for i,v in enumerate(obj):flatten_numeric(v,path,usage,f'{key}[{i}]')
    elif isinstance(obj,(int,float,np.number)):provenance(obj,path,key,usage)
def safe_frame(frame):
    d=frame.copy()
    for c in d:
        if c in ['lon','lat','plot_lon','plot_lat','longitude','latitude']:
            d[c]=pd.to_numeric(d[c],errors='coerce').round(2)
        if c in ['plates','n_regular','baseline_plates','taxi_vehicles_reporting','taxi_vehicles_active'] or c.startswith('plates_') or c.startswith('plates_baseline_'):
            v=pd.to_numeric(d[c],errors='coerce');d[c]=d[c].astype(object);d.loc[v.notna()&(v<10),c]='<10'
        if d[c].dtype==object:
            # No mapping is released. These outputs normally contain no IDs.
            mask=d[c].astype(str).str.fullmatch(r'(?:cam_)?[a-fA-F0-9]{16}')
            if mask.any():
                aliases={v:f'device_{j+1:04d}' for j,v in enumerate(sorted(d.loc[mask,c].astype(str).unique()))}
                d.loc[mask,c]=d.loc[mask,c].map(aliases)
    return d
def save(frame,path,strings=False):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    safe_frame(frame).to_csv(path,index=False,encoding='utf-8-sig',float_format=None if strings else '%.10g')
    OUTPUTS.append(dict(file=str(path.relative_to(ROOT)).replace('\\','/'),rows=len(frame)))
def textout(path,text):
    Path(path).parent.mkdir(parents=True,exist_ok=True);Path(path).write_text(text,encoding='utf-8');OUTPUTS.append(dict(file=str(Path(path).relative_to(ROOT)).replace('\\','/'),rows=None))
def jsonout(path,obj):
    textout(path,json.dumps(obj,ensure_ascii=False,indent=2,default=lambda x:x.item() if isinstance(x,np.generic) else str(x)))
def md(frame):
    d=frame.fillna('');escape=lambda x:str(x).replace('|','/').replace('\n',' ')
    return '| '+' | '.join(d.columns)+' |\n| '+' | '.join(['---']*len(d.columns))+' |\n'+''.join('| '+' | '.join(escape(v) for v in row)+' |\n' for row in d.values)
def setup_plot():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    matplotlib.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Arial','DejaVu Sans'],'font.size':7,'axes.titlesize':8,'axes.labelsize':7,'xtick.labelsize':6.5,'ytick.labelsize':6.5,'legend.fontsize':6.5,'lines.linewidth':1.0,'lines.markersize':3,'axes.linewidth':.6,'grid.linewidth':.3,'pdf.fonttype':42,'ps.fonttype':42,'savefig.dpi':300,'axes.unicode_minus':False})
    return plt
COLORS=['#2878b5','#eb7134','#20a486','#dba419'];EVENT=pd.date_range('2021-07-25','2021-08-02').strftime('%Y-%m-%d').tolist()
def finish_figure(fig,name):
    for ext in ['png','pdf']:
        p=M/'figures'/f'{name}.{ext}';p.parent.mkdir(parents=True,exist_ok=True);fig.savefig(p,dpi=300)
        OUTPUTS.append(dict(file=str(p.relative_to(ROOT)).replace('\\','/'),rows=None))
def fig4():
    paths={k:V3/'06_m5_bias_correction'/v for k,v in {'visible':'m5_visible_bias_v3.csv','decomp':'m5_bias_decomposition_v3.csv','km':'m5_failure_persistence_curve_v3.csv','leave':'m5_leaveout_replicates.csv'}.items()}
    paths['signature']=V3/'07_m6_robustness/m6_signature_comparison_v3.csv'
    data={k:read(p) for k,p in paths.items()};source=[]
    for key,panel in [('visible','a'),('decomp','b'),('km','c'),('leave','d')]:
        d=data[key].copy();d['panel']=panel;d['source_file']=str(paths[key]);d['source_row']=[i+2 for i in range(len(d))];source.append(d)
    sg=data['signature'][data['signature'].date.isin(['2021-07-26','2021-07-08','2021-07-10'])].copy();sg['panel']='e';sg['source_file']=str(paths['signature']);sg['source_row']=sg.index+2;source.append(sg)
    save(pd.concat(source,ignore_index=True,sort=False),M/'source_data/fig4_v4_source_data.csv')
    frame_provenance(data['visible'],paths['visible'],'Fig4a', ['delta_naive','delta_naive_ci_lo','delta_naive_ci_hi','delta_online','delta_online_ci_lo','delta_online_ci_hi','delta_taxi','delta_taxi_ci_lo','delta_taxi_ci_hi'])
    frame_provenance(data['decomp'],paths['decomp'],'Fig4b',['w_g','r_g','contribution','n_devices'])
    frame_provenance(data['km'],paths['km'],'Fig4c')
    frame_provenance(data['leave'],paths['leave'],'Fig4d',['rep','error','n_masked'])
    metrics=[('mean_log_base_diff','Baseline flow difference','Log counts'),('mean_dist_baiguan_diff','Distance difference','km'),('Q4_share_diff','Q4 fraction difference','Fraction'),('org_max_share','Largest organisation share','Fraction')]
    frame_provenance(sg,paths['signature'],'Fig4e',[m[0] for m in metrics]+['n_failed','n_online'])
    plt=setup_plot();fig=plt.figure(figsize=(180/25.4,187/25.4));grid=fig.add_gridspec(3,2,height_ratios=[1,1.05,.68],hspace=.65,wspace=.36)
    a=fig.add_subplot(grid[0,0]);b=fig.add_subplot(grid[0,1]);c=fig.add_subplot(grid[1,0]);d=fig.add_subplot(grid[1,1]);es=grid[2,:].subgridspec(1,4,wspace=.58);eax=[fig.add_subplot(es[0,i]) for i in range(4)]
    x=np.arange(9);v=data['visible']
    for lab,col in [('naive',COLORS[0]),('online',COLORS[2]),('taxi',COLORS[1])]:
        f='delta_'+lab;a.plot(x,v[f],label=lab,color=col,marker='o');a.fill_between(x,v[f+'_ci_lo'],v[f+'_ci_hi'],color=col,alpha=.16,linewidth=0)
    a.axhline(0,color='#777',linewidth=.5);a.set_xticks(x,[pd.Timestamp(t).strftime('%b %d') for t in EVENT],rotation=45,ha='right');a.set_ylabel('Ratio difference from S*');a.set_title('a  Visible recovery differences',loc='left');a.legend(ncol=3,loc='upper right',frameon=False,columnspacing=.8,handlelength=1.2)
    groups=['failed_lt005_nonSstar','degraded_005_050_nonSstar','online_nonSstar','Sstar'];positive=np.zeros(9);negative=np.zeros(9)
    labs=['<5%, outside S*','5–50%, outside S*','Other outside S*','S*']
    for g,color,label in zip(groups,COLORS,labs):
        s=data['decomp'][data['decomp'].group.eq(g)].set_index('date').reindex(EVENT);y=s.contribution.to_numpy();bottom=np.where(y>=0,positive,negative);b.bar(x,y,bottom=bottom,width=.7,color=color,label=label);positive+=np.maximum(y,0);negative+=np.minimum(y,0)
    b.axhline(0,color='#777',linewidth=.5);b.set_xticks(x,[pd.Timestamp(t).strftime('%b %d') for t in EVENT],rotation=45,ha='right');b.set_ylabel('Contribution to naive − S*');b.set_title('b  Exclusive device-group decomposition',loc='left');b.legend(frameon=False,fontsize=5.8,loc='lower left',handlelength=1.0,labelspacing=.25)
    km=data['km'];c.step(km.days_since_first_failure,km.survival_not_first_recovered,where='post',color=COLORS[0]);c.set_ylim(0,1.02);c.set_xlabel('Days since first A1 failure');c.set_ylabel('Not yet first recovered');c.set_title('c  Persistence to first recovery',loc='left');c.text(.98,.94,'77 / 1,221 A200 devices\nnot first recovered by Aug 2',transform=c.transAxes,ha='right',va='top',fontsize=6.5)
    box=[];leave=data['leave'];methods=['naive_zero','drop','knn','stratum']
    for mask in ['random','flowweighted']:
        for method in methods:box.append(leave.loc[(leave.masking==mask)&(leave.method==method),'error'].to_numpy())
    art=d.boxplot(box,positions=np.arange(8),widths=.60,showfliers=False,patch_artist=True,medianprops={'color':'#222','linewidth':.8},whiskerprops={'linewidth':.6},capprops={'linewidth':.6},boxprops={'linewidth':.6})
    for patch,color in zip(art['boxes'],COLORS*2):patch.set_facecolor(color);patch.set_alpha(.5)
    d.axhline(0,color='#777',linewidth=.5);d.axvline(3.5,color='#aaa',linewidth=.4);d.set_xticks(np.arange(8),['zero','drop','kNN','strata']*2,rotation=45,ha='right');d.set_ylabel('Signed leaveout error');d.set_title('d  Leaveout errors (1,000 per box)',loc='left');d.text(.24,-.31,'Random masking',transform=d.transAxes,ha='center',fontsize=6.4);d.text(.76,-.31,'Flow-weighted masking',transform=d.transAxes,ha='center',fontsize=6.4)
    sig=sg.set_index('date').reindex(['2021-07-26','2021-07-08','2021-07-10']);sigcols=[COLORS[0],'#9b9b9b','#c5c5c5']
    for i,(metric,title,ylabel) in enumerate(metrics):
        ax=eax[i];ax.bar(np.arange(3),sig[metric],color=sigcols,width=.65);ax.axhline(0,color='#777',linewidth=.5);ax.set_xticks(np.arange(3),['Jul 26','Jul 8','Jul 10'],rotation=45,ha='right');ax.set_ylabel(ylabel);ax.set_title(('e  ' if i==0 else '')+title,loc='left',fontsize=7)
    for ax in [a,b,c,d]+eax:ax.spines[['top','right']].set_visible(False);ax.grid(axis='y',alpha=.13);ax.set_axisbelow(True)
    fig.subplots_adjust(left=.08,right=.98,bottom=.10,top=.96)
    finish_figure(fig,'fig4_v4');plt.close(fig)
    CHECKS['fig4_leaveout_8_groups_1000_each']=all(len(z)==1000 for z in box)
    CHECKS['fig4_signature_3_dates_4_metrics']=sig.shape[0]==3 and all(sig[m[0]].notna().all() for m in metrics)
    CHECKS['fig4_decomposition_closes_at_serialization_precision']=bool(np.allclose(data['decomp'].groupby('date').contribution.sum(),v.set_index('date').delta_naive.reindex(sorted(EVENT)),atol=.0002,rtol=0))
    return data
def ed8():
    base=V3/'07_m6_robustness';paths={'drift':base/'m6_b3_drift_v3.csv','ratios':base/'m6_b3_adjusted_ratios_v3.csv','margins':base/'m6_b3_adjusted_margins_v3.csv'}
    data={k:read(p) for k,p in paths.items()};j=readjson(base/'m6_b3_drift_v3.json');phi=j['phi'];src=[]
    # The saved adjusted margins contain26/28. Display27 by a deterministic
    # transformation of existing B3 estimates, without re-estimation/resampling.
    rawpath=V1/'04_m3_vehicles/m3_daily_by_group_B3.csv';raw=read(rawpath);add=[]
    for ri,row in raw[raw.date.eq('2021-07-27')&raw.grp.isin(['local_zheD','zhejiang_other','other_province'])].iterrows():
        for metric in ['rP','rm']:
            add.append(dict(date=row.date,grp=row.grp,metric=metric,ratio_B3=row[metric],phi=phi[0],ratio_B3_adj=row[metric]/phi[0],ci_lo_conditional_phi=row['ci_'+metric+'_lo']/phi[0],ci_hi_conditional_phi=row['ci_'+metric+'_hi']/phi[0],interval_scope='Plot-only deterministic division of frozen B3 estimate and interval by frozen phi; no re-estimation.',source_file=str(rawpath),source_row=ri+2,source_key=f'{metric};ci_{metric}_lo/hi divided by m6_b3_drift_v3.json phi[0]'))
    data['margins']=pd.concat([data['margins'],pd.DataFrame(add)],ignore_index=True,sort=False)
    for k,panel in [('drift','a'),('ratios','b'),('margins','c')]:
        f=data[k].copy();f['panel']=panel
        if 'source_file' in f:
            f['source_file']=f.source_file.fillna(str(paths[k]));f['source_row']=f.source_row.fillna(pd.Series(f.index+2,index=f.index))
        else:f['source_file']=str(paths[k]);f['source_row']=f.index+2
        src.append(f)
        if k!='margins':frame_provenance(f,paths[k],'ED8'+panel)
    for i,v in enumerate(phi):provenance(v,base/'m6_b3_drift_v3.json',f'$.phi[{i}]','ED8a')
    src.append(pd.DataFrame([dict(panel='a',date='mean',metric='phi',value=phi[0],ci_lo=phi[1],ci_hi=phi[2],source_file=str(base/'m6_b3_drift_v3.json'),source_key='$.phi')]))
    edsrc=pd.concat(src,ignore_index=True,sort=False);save(edsrc,M/'source_data/ed8_v4_source_data.csv')
    frame_provenance(edsrc,M/'source_data/ed8_v4_source_data.csv','ED8 all plotted values')
    plt=setup_plot();fig=plt.figure(figsize=(180/25.4,190/25.4));grid=fig.add_gridspec(3,2,height_ratios=[.8,1,1],hspace=.65,wspace=.38)
    a=fig.add_subplot(grid[0,:]);b=fig.add_subplot(grid[1,:]);cs=[fig.add_subplot(grid[2,i]) for i in range(2)]
    drift=data['drift'];x=np.arange(len(drift));a.errorbar(x,drift.R_stable_B3,yerr=np.array([drift.R_stable_B3-drift.ci_lo,drift.ci_hi-drift.R_stable_B3]),fmt='o',color=COLORS[0],capsize=1.5);a.axhline(1,color='#777',linewidth=.5);a.axhline(phi[0],color=COLORS[1],label='Mean drift factor');a.axhspan(phi[1],phi[2],color=COLORS[1],alpha=.12);a.set_xticks(x,[pd.Timestamp(t).strftime('%b %d') for t in drift.date],rotation=45,ha='right');a.set_ylabel('S* ratio using B3');a.set_title('a  Seasonal drift in the 15 B1 reference days',loc='left');a.text(.98,.93,f'φ = {phi[0]:.4f} [{phi[1]:.4f}, {phi[2]:.4f}]',transform=a.transAxes,ha='right',va='top')
    r=data['ratios'];datecodes={d:i for i,d in enumerate(['2021-07-26','2021-07-27','2021-07-28'])}
    for mi,metric in enumerate(['R_naive','R_online','R_stable']):
        z=r[r.metric.eq(metric)].copy();xx=np.array([datecodes[d]*4+mi for d in z.date]);b.scatter(xx-.08,z.R_B3,marker='o',facecolors='white',edgecolors=COLORS[mi],s=16,zorder=3);b.errorbar(xx+.08,z.R_B3_adj,yerr=np.array([z.R_B3_adj-z.ci_lo_conditional_phi,z.ci_hi_conditional_phi-z.R_B3_adj]),fmt='o',color=COLORS[mi],capsize=1.5,label=metric[2:])
    b.axhline(1,color='#777',linewidth=.5);b.set_xticks([1,5,9],['Jul 26','Jul 27','Jul 28']);b.set_ylabel('Recovery ratio');b.set_title('b  Four observation ratios: B3 and B3 / φ',loc='left');b.legend(frameon=False,ncol=3,loc='upper left');b.text(.98,.06,'Open: B3; filled: B3 / φ\nTaxi: NA (no B3 observations)',transform=b.transAxes,ha='right',va='bottom',fontsize=6.5)
    margin=data['margins'];geos=['local_zheD','zhejiang_other','other_province'];labels=['Local','Other Zhejiang','Other provinces']
    for ax,metric in zip(cs,['rP','rm']):
        for gi,g in enumerate(geos):
            z=margin[(margin.grp==g)&(margin.metric==metric)];xx=np.array([datecodes[d]*4+gi for d in z.date]);ax.scatter(xx-.08,z.ratio_B3,facecolors='white',edgecolors=COLORS[gi],s=16,zorder=3);ax.errorbar(xx+.08,z.ratio_B3_adj,yerr=np.array([z.ratio_B3_adj-z.ci_lo_conditional_phi,z.ci_hi_conditional_phi-z.ratio_B3_adj]),fmt='o',color=COLORS[gi],capsize=1.4,label=labels[gi])
        ax.axhline(1,color='#777',linewidth=.5);ax.set_xticks([1,5,9],['Jul 26','Jul 27','Jul 28']);ax.set_ylabel(metric+' ratio');ax.set_title(('c  ' if metric=='rP' else '')+'Vehicle margin: '+metric,loc='left');ax.legend(frameon=False,fontsize=5.7,loc='lower right')
    for ax in [a,b]+cs:ax.spines[['top','right']].set_visible(False);ax.grid(axis='y',alpha=.13);ax.set_axisbelow(True)
    fig.subplots_adjust(left=.09,right=.98,bottom=.08,top=.96);finish_figure(fig,'ed8_v4');plt.close(fig)
    CHECKS['ed8_taxi_B3_retained_NA']=r.loc[r.metric.eq('R_taxi_km'),'R_B3_adj'].isna().all()
    CHECKS['ed8_3_geographic_groups_two_margins']=len(margin[margin.grp.isin(geos)&margin.metric.isin(['rP','rm'])])==18
    return j

SOURCE_MAP={
1:[('v1','02_m1_observation/m1_daily_coverage.csv')],
2:[],3:[('v1','03_m2_two_sources/m2_daily_ratios.csv')],4:[('v1','03_m2_two_sources/m2_daypart_summary.csv'),('v1','03_m2_two_sources/m2_hourly_ratios_0722_0728.csv')],
5:[('v3','06_m5_bias_correction/m5_failure_counts_v3.csv')],6:[('v3','06_m5_bias_correction/m5_failure_nonrandomness_v3.csv')],7:[('v3','06_m5_bias_correction/m5_visible_bias_v3.csv')],
8:[('v3','06_m5_bias_correction/m5_leaveout_validation.csv'),('v3','06_m5_bias_correction/m5_leaveout_validation_flowweighted.csv'),('v3','06_m5_bias_correction/m5_leaveout_by_flow_quantile.csv'),('v3','06_m5_bias_correction/m5_leaveout_by_flow_quantile_flowweighted.csv')],
9:[('v1','04_m3_vehicles/m3_two_margins_table.csv')],10:[('v1','04_m3_vehicles/m3_return_curve.csv'),('v1','04_m3_vehicles/m3_return_gap.csv')],11:[('v3','04_m3_vehicles/m3_composition_v3.csv')],
12:[('v3','05_m4_spatial/m4_ols_v3.csv'),('v3','05_m4_spatial/m4_by_distance_ring_v3.csv')],13:[('v3','05_m4_spatial/m4_taxi_camera_gradient_v3.csv')],14:[('v3','07_m6_robustness/m6_negative_control_v3.csv')],15:[('v3','07_m6_robustness/m6_robustness_matrix_v3.csv')],
16:[('v3','05_m4_spatial/m4_taxi_redistribution_v3.csv'),('v3','03_m2_two_sources/m2_taxi_camera_correlations_v3.csv'),('v3','05_m4_spatial/m4_taxi_grid_threshold_sensitivity_v3.csv')],
17:[('v3','06_m5_bias_correction/m5_failure_persistence_v3.csv'),('v3','06_m5_bias_correction/m5_failure_persistence_profile_v3.csv'),('v3','06_m5_bias_correction/m5_bias_decomposition_v3.csv'),('v3','06_m5_bias_correction/m5_visible_bias_v3.csv'),('v3','06_m5_bias_correction/m5_failure_persistence_curve_v3.csv')],
18:[('v3','06_m5_bias_correction/m5_ordinary_floor_v3.csv')],19:[('v3','04_m3_vehicles/m3_h1_placebo_margins_v3.csv'),('v3','04_m3_vehicles/m3_placebo_by_group_v3.csv')],20:[('v3','04_m3_vehicles/m3_h2_composition_placebo_v3.csv'),('v3','04_m3_vehicles/m3_composition_convergence_v3.csv')],
21:[('v3','05_m4_spatial/m4_ols_v3.csv'),('v3','05_m4_spatial/m4_five_ring_criterion_v3.csv'),('v3','05_m4_spatial/m4_negative_control_ols_v3.csv'),('v3','05_m4_spatial/m4_ols_floor_accounting_v3.csv')],
22:[('v3','07_m6_robustness/m6_b3_drift_v3.csv'),('v3','07_m6_robustness/m6_b3_adjusted_ratios_v3.csv'),('v3','07_m6_robustness/m6_b3_adjusted_margins_v3.csv')],23:[('v3','07_m6_robustness/m6_signature_comparison_v3.csv')]}
def supplementary():
    path=register(V3/'RESULTS_SUMMARY_v3.md');lines=path.read_text(encoding='utf-8').splitlines();index=[];parsed={};table=None;section=None;title='';firstline=None;block=[];counts={}
    def flush():
        nonlocal block,firstline
        if len(block)<2:block=[];return
        cells=[[s.strip() for s in line.strip().strip('|').split('|')] for line in block]
        header=cells[0];body=cells[2:]
        if any(len(row)!=len(header) for row in body):raise AssertionError(f'Markdown table malformed T{section} line{firstline}')
        df=pd.DataFrame(body,columns=header);part=counts.get(section,0)+1;counts[section]=part;name=f'T{section:02d}_md_{part:02d}.csv';save(df,M/'supplementary_tables'/name,strings=True)
        index.append(dict(table=f'T{section}',title=title,part=part,kind='markdown_conversion',file=name,source_file=str(path),source_row_or_key=f'lines {firstline}-{firstline+len(block)-1}',rows=len(df),status='complete',note='忠实转换v3汇总表格；对应原始结果数据另列。'))
        parsed.setdefault(section,[]).append(df);block=[]
    for li,line in enumerate(lines,1):
        heading=re.match(r'^## T(\d+) (.+)',line)
        if heading:
            flush();section=int(heading.group(1));title=heading.group(2)
        elif line.startswith('## ') and not line.startswith('## T'):flush();section=None
        if section is not None and line.strip().startswith('|'):
            if not block:firstline=li
            block.append(line)
        elif block:flush()
    flush()
    for n,files in SOURCE_MAP.items():
        for part,(version,rel) in enumerate(files,1):
            src=(V1 if version=='v1' else V3)/rel;d=pd.read_csv(register(src),encoding='utf-8-sig',dtype=str,keep_default_na=False);name=f'T{n:02d}_source_{part:02d}.csv';safe=safe_frame(d);save(safe,M/'supplementary_tables'/name,strings=True)
            index.append(dict(table=f'T{n}',title='',part=part,kind='original_result_data',file=name,source_file=str(src),source_row_or_key='All CSV data rows; original columns preserved',rows=len(d),status='complete',note='原冻结结果；仅公开小车辆计数掩蔽、坐标两位及安全设备别名格式化。'))
    # T2 has no original standalone CSV: its source is the frozen results JSON.
    r=readjson(V1/'results.json');df=pd.DataFrame([dict(set=k,n=r['sets'][key],source_key='$.sets.'+key) for k,key in [('A100','A100'),('A200','A200'),('S*','S_star')]])
    save(df,M/'supplementary_tables/T02_source_01.csv');index.append(dict(table='T2',title='集合规模',part=1,kind='original_result_data',file='T02_source_01.csv',source_file=str(V1/'results.json'),source_row_or_key='$.sets.A100 / A200 / S_star',rows=3,status='complete',note='原JSON标量无重算；同星期基线规模见T02_md_02.csv。'))
    blocked=pd.DataFrame([dict(analysis='T16 hourly distance-ring taxi ratio',status='BLOCKED',reason='现有结果与面板缺少网格×小时联合数据；全市小时边际不能恢复分环小时分布',source_file=str(path),source_key=_release_private('private_value_004'),raw_source_read=False,fabricated_values=False)])
    save(blocked,M/'supplementary_tables/T16_hourly_BLOCKED.csv');index.append(dict(table='T16',title='分环小时子分析',part='hourly',kind='transparent_blocked_entry',file='T16_hourly_BLOCKED.csv',source_file=str(path),source_row_or_key='T16 BLOCKED',rows=1,status='BLOCKED',note='未回源，未用全市小时数据冒充分环数据。'))
    idx=pd.DataFrame(index);save(idx,M/'supplementary_tables/supplementary_tables_index_v4.csv',strings=True)
    CHECKS['supplement_all_23_md_sections']=set(parsed)==set(range(1,24))
    CHECKS['supplement_all_23_original_data_sections']=set(idx.loc[idx.kind.eq('original_result_data'),'table'])=={f'T{i}' for i in range(1,24)}
    textout(M/'supplementary_tables/README_supplementary_tables_v4.md',_release_private('private_value_003'))
    return parsed,idx
def inventory():
    for root,files in [(V1,['results.json','02_m1_observation/m1_daily_coverage.csv','03_m2_two_sources/m2_daily_ratios.csv','03_m2_two_sources/m2_daypart_summary.csv','04_m3_vehicles/m3_two_margins_table.csv']),
      (V3,['results_v3.json','07_m6_robustness/m6_b3_adjusted_margins_v3.csv','03_m2_two_sources/m2_taxi_camera_correlations_v3.csv','05_m4_spatial/m4_taxi_redistribution_v3.csv','05_m4_spatial/m4_taxi_grid_threshold_sensitivity_v3.csv'])]:
        for f in files:
            p=root/f
            if p.suffix=='.json':
                j=json.loads(p.read_text(encoding='utf-8'));print(f,'KEYS',list(j))
                for k in ['metadata','data','data_totals','date_sets','baselines','definitions','audit','summary','platform_outage','sets']:
                    if k in j:print(k,str(j[k])[:2500])
            else:
                d=pd.read_csv(p,encoding='utf-8-sig');print(f,'ROWS',len(d),'COLS',list(d));print(d.head(2).to_string(index=False))
if __name__=='__main__':
    start=now();clock=time.perf_counter()
    for d in ['figures','source_data','tables','supplementary_tables']:(M/d).mkdir(parents=True,exist_ok=True)
    fig4();drift=ed8();supplementary()
    original=readjson(V1/'results.json');coverage=read(V1/'02_m1_observation/m1_daily_coverage.csv')
    table1=pd.DataFrame([
        dict(item='过车记录',value=int(coverage.records.sum()),unit='重复记录',definition='37个观测日期的全网记录数之和',source_file=str(V1/'02_m1_observation/m1_daily_coverage.csv'),source_row_or_key='sum records over all date rows'),
        dict(item='假名车牌主表',value=3857792,unit='ph',definition='包含不可读占位；可读车辆队列另行排除',source_file=str(V1/'results.json'),source_row_or_key='deviations_from_pilot metric=plate_master_total formal'),
        *[dict(item=k,value=original['sets'][key],unit='设备',definition=definition,source_file=str(V1/'results.json'),source_row_or_key='$.sets.'+key) for k,key,definition in [('A100','A100','B1日均记录≥100'),('A200','A200','B1日均记录≥200'),('S*','S_star','A100内7/26–30逐日比≥.20且7/29–30≥.50')]],
        dict(item='观测日期D_ALL',value=37,unit='日期',definition='2021-06-17及2021-06-28…08-02',source_file=str(V1/'研究方案_上虞台风_v2_执行版.md'),source_row_or_key='§3.1'),
        dict(item='事件批次出租车',value=290,unit='车辆',definition='第二批样本，与第一批不是相同车辆集合',source_file=str(V3/'00_env/m5_method_interpretations_v3.json'),source_row_or_key='$.notes[1].n_second_batch_vehicles'),
        *[dict(item=k,value=n,unit='基线日期',definition=ds,source_file=str(V1/'研究方案_上虞台风_v2_执行版.md') if k!='B_P' else str(V3/'00_env/protocol_frozen.json'),source_row_or_key='§3.1' if k!='B_P' else 'A2 explicit dates') for k,n,ds in [('B1',15,'7/5–21排除7/8、7/10'),('B2',10,'7/12–21'),('B3',8,'6/17及6/28–7/4'),('B_P',12,'6/17及6/28–7/9排除7/8')]],
        dict(item='D_PARTIAL',value='7/8,7/10,7/22,7/23,7/24,7/25',unit='日期集合',definition='平台中断/半天，7/25卡口11–23小时匹配',source_file=str(V1/'研究方案_上虞台风_v2_执行版.md'),source_row_or_key='§3.1–3.2'),
        dict(item='W_T/E_T',value='7/12–21 / 7/25–8/2',unit='规律窗口/评价窗口',definition='S*可读队列，主阈值≥8天',source_file=str(V1/'研究方案_上虞台风_v2_执行版.md'),source_row_or_key='§3.5'),
        dict(item='W_P/E_P',value='6/28–7/7 / 7/11–19',unit='安慰剂窗口/评价窗口',definition='同星期、同滞后',source_file=str(V1/'研究方案_上虞台风_v2_执行版.md'),source_row_or_key='§3.5')])
    save(table1,M/'tables/table1_data_sets_v4.csv');textout(M/'tables/table1_data_sets_v4.md','# 表1 数据与冻结集合\n\n'+md(table1[['item','value','unit','definition']])+'\n\n星期覆盖见ED2及T2。ph计数为假名面板标识，包含不可读占位，不能直接视为真实车辆或居民。\n')
    for _,r in table1.iterrows():
        if isinstance(r.value,(int,float,np.number)):provenance(r.value,r.source_file,r.source_row_or_key,'Table1')
    maps=[('H1','04_m3_vehicles/m3_h1_verdict_v3.json'),('H2','04_m3_vehicles/m3_h2_verdict_v3.json'),('H3','05_m4_spatial/m4_h3_verdict_v3.json'),('H4','06_m5_bias_correction/m5_h4_verdict_v3.json')];full=[];compact=[]
    for hyp,rel in maps:
        p=V3/rel;j=readjson(p);flatten_numeric(j,p,'Table2 '+hyp)
        for i,crit in enumerate(j['criteria']):
            obs=crit.get('observed');obsj=json.dumps(obs,ensure_ascii=False,separators=(',',':'))
            full.append(dict(hypothesis=hyp,status=j['status'],criterion_id=crit.get('id',i+1),criterion=crit.get('criterion',''),threshold=crit.get('threshold',''),observed=obsj,met=crit.get('met'),required_for_supported=crit.get('required_for_supported',True),source_file=str(p),source_row_or_key=f'$.criteria[{i}]'))
            if hyp=='H4' and crit.get('id')==4:
                cells=obs['per_date_masking'];bad=[x for x in cells if not x['drop_abs_bias_lt002'] or not x['zero_abs_bias_gt5x_drop']];brief='逐日两种掩蔽；未通过：'+json.dumps(bad,ensure_ascii=False)
            else:brief=obsj if len(obsj)<350 else obsj[:350]+'…（完整值见CSV）'
            compact.append(dict(假设=hyp,定稿判定=j['status'],判据=crit.get('id',i+1),界限=crit.get('threshold',''),观测值=brief,满足=crit.get('met')))
    save(pd.DataFrame(full),M/'tables/table2_hypotheses_v4.csv');textout(M/'tables/table2_hypotheses_v4.md','# 表2 定稿判据及观测值\n\n'+md(pd.DataFrame(compact))+'\n\n此表由四个冻结verdict JSON逐条导出，没有重判定。H4的7/29 flowweighted drop bias=0.0217不通过0.02界限，保持partial；方法比较项只描述。完整嵌套值、来源路径与JSON键保留在CSV。\n')
    captions_zh='''# 图4与ED8图注\n\n## Fig. 4 | 设备失效、可见恢复差与校正边界\n\n(a) naive、online、taxi相对S*的比值差及95%区间。卡口比值差来自500次共享设备簇抽样，出租车差独立组合200次车辆抽样与500次设备抽样。(b) A100内四个互斥设备组按基线流量权重分解差值，S*贡献为零。(c) 事件期曾A1失效设备的首次恢复KM曲线，n=227台，未首次恢复77台占全部1221台A200的6.31%；末日未恢复作右删失，不同于末日仍失效57台。(d) 四方法×两掩蔽方式的八组误差；每箱合并5日期×200重复=1000误差。箱为25%–75%，线为中位数，须为1.5IQR范围内最远点，异常点隐藏。7/29流量加权drop平均偏差0.0217超出0.02，保留partial。(e) 风暴日与两平台阴性日的四项签名，显示原单位效应。机构集中度为失效设备内最大机构份额；Q4差为最高基线流量四分位失效减在线份额。各日期设备n与P值见T23。所有差值相对观测集合，不作为全市真实交通误差。\n\n## Extended Data Fig. 8 | B3夏季漂移及条件校正\n\n(a) 15个B1日以B3为分母的S*比值与设备簇95%区间。共同漂移因子φ=0.9001 [0.8794,0.9215]，来自500次设备簇抽样。(b) 三个卡口观测口径在三日的B3原值与除以φ后值；第四口径出租车B3为缺失，标NA。(c) 三个车辆类别的rP、rm原值与校正值，原车辆簇区间来自200次抽样。空心点为原值，实心点与区间为条件于φ的校正值，区间未包含φ估计的不确定性。共同φ来自卡口流量，不表示类别特定季节漂移。\n'''
    captions_en='''# Bias figure legends\n\n## Fig. 4 | Device failure and visible recovery differences\n\na, Differences from S* with percentile confidence intervals from 500 device resamples and 200 taxi-vehicle resamples. Taxi differences combined independent empirical resampling distributions. b, Baseline-flow weights decomposed differences across four exclusive A100 groups. c, First-recovery survival for 227 ever-failed devices; 77 had not first recovered by 2 August. These devices represented 6.31% of the 1,221 A200 devices. d, Four correction methods under two masking schemes. Each box pooled 200 repeats across five dates, yielding 1,000 errors. Boxes show quartiles and medians; whiskers extend to 1.5 interquartile ranges. Outliers are hidden. The 29 July flow-weighted drop bias was 0.0217, exceeding 0.02. e, Storm and platform-control signatures retain their original units. Organisation concentration is the largest organisation share among failed devices. Counts and permutation P values are reported in Supplementary Table T23.\n\n## Extended Data Fig. 8 | B3 drift and conditional adjustment\n\na, Stable-camera B3 ratios across 15 B1 dates. The shared drift factor was 0.9001, with a 95% interval of 0.8794–0.9215 from 500 device-cluster resamples. b, Original and adjusted B3 ratios across three dates. Taxi values remain missing because B3 observations were unavailable. c, Original and adjusted vehicle margins across three geographic groups. Vehicle intervals used 200 resamples. Open symbols show original values; filled symbols show values divided by the shared drift factor. Adjusted intervals condition on the estimated factor and exclude its estimation uncertainty. The shared factor describes camera-flow drift, not group-specific seasonal changes.\n'''
    textout(M/'figures/bias_captions_zh_v4.md',captions_zh);textout(M/'figures/bias_captions_en_v4.md',captions_en)
    save(pd.DataFrame(PROV),M/'source_data/bias_number_provenance_v4.csv')
    CHECKS['inputs_size_mtime_unchanged']=all((Path(p).stat().st_size,Path(p).stat().st_mtime_ns)==v for p,v in INPUTS.items())
    jsonout(ROOT/'00_env/bias_figures_tables_execution_v4.json',dict(start=start,end=now(),elapsed_seconds=time.perf_counter()-clock,command=[sys.executable]+sys.argv,inputs=list(INPUTS),outputs=OUTPUTS,checks=CHECKS))
    print('Bias material complete',json.dumps(CHECKS,default=lambda x:bool(x) if isinstance(x,np.bool_) else str(x)),flush=True)
    if not all(CHECKS.values()):raise SystemExit(1)
