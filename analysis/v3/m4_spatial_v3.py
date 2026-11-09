# -*- coding: utf-8 -*-
"""A5/A6, T16/T21. Existing formal-v1 panels only; no source or key access."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[2]), str(_ReleasePath(__file__).resolve().parents[0])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from pathlib import Path
import hashlib, json, time
import numpy as np
import pandas as pd
from scipy.stats import spearmanr, kendalltau
from scipy.stats import norm
from pyproj import Transformer
import statsmodels.formula.api as smf
from common_v3 import ROOT, V1, PANELS, B1, B_TAXI, SEED, now, load_panels, device_vectors, save_csv, write_json, guarded, setup_plot

OUT=ROOT/'05_m4_spatial'; TWO=ROOT/'03_m2_two_sources'; FIG=ROOT/'08_figures'
DATES=['2021-07-25','2021-07-26','2021-07-27','2021-07-28']
RINGS=['0-2','2-4','4-7','7-12','12-20','20+']; EDGES=[0,2,4,7,12,20,np.inf]
FIVE=['0-2','2-4','4-7','7-12','12+']; B=500
FORMULA='response ~ np.log1p(dist_baiguan_km) + log_base + elev_m + relief_300m + C(road_level) + C(org) + gateway'
DIST='np.log1p(dist_baiguan_km)'
TRANS=Transformer.from_crs(4326,32651,always_xy=True)
INVERSE=Transformer.from_crs(32651,4326,always_xy=True)

def ring(vals):
    return pd.cut(vals,EDGES,labels=RINGS,include_lowest=True,right=False).astype(object)

def public_csv(df,path,precise=()):
    q=df.copy()
    for c in precise:
        if c in q:q[c]=q[c].map(lambda v:'' if pd.isna(v) else format(float(v),'.10g'))
    save_csv(q,path)

def sims_ratio(n,b,rng):
    n=np.asarray(n,float); b=np.asarray(b,float)
    if not len(n) or b.sum()<=0:return np.full(B,np.nan)
    ix=rng.integers(0,len(n),size=(B,len(n)))
    den=b[ix].sum(axis=1)
    return np.divide(n[ix].sum(axis=1),den,out=np.full(B,np.nan),where=den>0)

def ci(vals):
    vals=np.asarray(vals,float)
    return tuple(np.nanquantile(vals,[.025,.975])) if np.isfinite(vals).any() else (np.nan,np.nan)

def aggregate(n,b):
    return float(np.sum(n)/np.sum(b)) if np.sum(b)>0 else np.nan

def fit_model(attr,ratio,select,day,sample):
    x=attr.loc[select & attr.lon.notna() & attr.lat.notna()].copy()
    x['log_base']=np.log(x.base_B1.where(x.base_B1.gt(0)))
    x['response']=np.log(ratio.reindex(x.index).clip(.05,3))
    x['treated_as_floor']=(ratio.reindex(x.index)<.05).astype(int)
    x=x.replace([np.inf,-np.inf],np.nan).dropna(subset=['response','dist_baiguan_km','log_base','elev_m','relief_300m','road_level','org','gateway'])
    fit=smf.ols(FORMULA,data=x).fit(cov_type='HC1')
    intervals=fit.conf_int(alpha=.05)
    rows=[dict(date=day,term=term,coef=float(coef),se_HC1=float(fit.bse[term]),p=float(fit.pvalues[term]),
               n=int(fit.nobs),r_squared=float(fit.rsquared),sample=sample,response='log(r.clip(0.05,3))',
               ci_lo=float(intervals.loc[term,0]),ci_hi=float(intervals.loc[term,1]),
               n_treated_as_floor=int(x.treated_as_floor.sum()),source='v3_recomputed') for term,coef in fit.params.items()]
    return pd.DataFrame(rows)

def merge_map(counts,force_five=False):
    groups=[[i] for i in range(6)]
    if force_five:groups=[[0],[1],[2],[3],[4,5]]
    changes=[]
    # Outermost sparse cells are merged inward, repeating until all are >=10.
    while len(groups)>1:
        sparse=[i for i,g in enumerate(groups) if sum(counts.get(RINGS[j],0) for j in g)<10]
        if not sparse:break
        i=max(sparse); target=i-1 if i>0 else 1
        changes.append({'from':[RINGS[j] for j in groups[i]],'into':[RINGS[j] for j in groups[target]],
                        'reason':'n_units < 10','direction':'inward' if i>0 else 'only_outward_neighbour'})
        groups[target]=sorted(groups[target]+groups[i]);groups.pop(i)
    mapping={}; labels=[]
    for g in groups:
        if len(g)==1:label=RINGS[g[0]]
        elif g[-1]==5:label=str(EDGES[g[0]])+'+'
        else:label=str(EDGES[g[0]])+'-'+str(EDGES[g[-1]+1])
        labels.append(label)
        for i in g:mapping[RINGS[i]]=label
    return mapping,labels,changes

def camera_ring_table(attr,n,b,select,day,sample,mapping,labels,rng):
    x=attr.loc[select & attr.dist_baiguan_km.notna()].copy()
    x['distance_ring']=ring(x.dist_baiguan_km).map(mapping)
    rows=[]
    for label in labels:
        ids=x.index[x.distance_ring.eq(label)]
        ns=n.reindex(ids).to_numpy();bs=b.reindex(ids).to_numpy()
        lo,hi=ci(sims_ratio(ns,bs,rng))
        rows.append(dict(date=day,sample=sample,distance_ring=label,n_devices=len(ids),
                         r_camera=aggregate(ns,bs),r_camera_ci_lo=lo,r_camera_ci_hi=hi,
                         observed_records=int(ns.sum()),baseline_records=float(bs.sum()),
                         hour_matched=0,source='v3_recomputed'))
    return pd.DataFrame(rows)

def run_cameras(dh,attr,dd,checks,notes):
    copied=pd.read_csv(V1/'05_m4_spatial/m4_ols.csv')
    models=[]; curves=[]; originals=[]; fivecurves=[]; audit=[];merge_logs=[]
    rng=np.random.default_rng(SEED)
    for day in DATES[1:]:
        n,b=device_vectors(day,dh=dh,dd=dd,hour_matched=False);r=n/b.replace(0,np.nan)
        selects={'Sstar':attr.in_Sstar.eq(1),'S_on':attr.in_A100.eq(1)&r.ge(.2),'A100_floor':attr.in_A100.eq(1)}
        for sample,select in selects.items():
            m=fit_model(attr,r,select,day,sample)
            if sample=='Sstar':
                old=copied.loc[copied.date.eq(day)].set_index('term');new=m.set_index('term')
                for c in ['coef','se_HC1','p','r_squared']:
                    ok=old.index.equals(new.index) and np.array_equal(old[c].round(4).to_numpy(),new[c].round(4).to_numpy())
                    audit.append(dict(date=day,column=c,four_decimals_equal=ok,max_abs_difference=float((old[c]-new[c]).abs().max())))
                    if not ok:raise RuntimeError('Sstar OLS differs from v1 at four decimals: '+day+' '+c)
                if not np.array_equal(old.n.to_numpy(),new.n.to_numpy()):raise RuntimeError('Sstar OLS N differs from v1')
                old=copied.loc[copied.date.eq(day)].copy();old['source']='formal_v1'
                old['ci_lo']=old.coef-norm.ppf(.975)*old.se_HC1;old['ci_hi']=old.coef+norm.ppf(.975)*old.se_HC1
                old['n_treated_as_floor']=int(m.n_treated_as_floor.iloc[0]);m=old
            models.append(m)
            if sample=='A100_floor':continue
            counts=ring(attr.loc[select,'dist_baiguan_km']).value_counts().to_dict()
            mapping,labels,changes=merge_map(counts)
            merge_logs.append(dict(date=day,sample=sample,original_counts=counts,mapping=mapping,changes=changes))
            curves.append(camera_ring_table(attr,n,b,select,day,sample,mapping,labels,rng))
            originals.append(camera_ring_table(attr,n,b,select,day,sample,dict(zip(RINGS,RINGS)),RINGS,rng))
            fmap,flabels,fchanges=merge_map(counts,force_five=True)
            ftab=camera_ring_table(attr,n,b,select,day,sample,fmap,flabels,rng)
            ftab['ring_order']=np.arange(1,len(ftab)+1)
            ftab['ring_spearman']=spearmanr(ftab.ring_order,ftab.r_camera).statistic
            ftab['ring_spearman_p']=spearmanr(ftab.ring_order,ftab.r_camera).pvalue
            fivecurves.append(ftab)
    negative=pd.read_csv(V1/'07_m6_robustness/m6_spatial_negative_control_ols.csv')
    negative['source']='formal_v1';negative['ci_lo']=negative.coef-norm.ppf(.975)*negative.se_HC1
    negative['ci_hi']=negative.coef+norm.ppf(.975)*negative.se_HC1
    # Recompute negative controls for auditing, then preserve original values.
    for day,ref in [('2021-07-08','2021-07-01'),('2021-07-10','2021-07-03')]:
        m=fit_model(attr,dd[day]/dd[ref].replace(0,np.nan),attr.in_Sstar.eq(1),day,'Sstar')
        old=negative.loc[negative.date.eq(day)].set_index('term');new=m.set_index('term')
        ok=np.array_equal(old.coef.round(4).to_numpy(),new.coef.round(4).to_numpy())
        checks['negative_control_ols_'+day]=bool(ok)
        if not ok:raise RuntimeError('Negative control copy audit failed')
    ols=pd.concat(models,ignore_index=True)
    public_csv(ols,OUT/'m4_ols_v3.csv',['coef','se_HC1','p','r_squared','ci_lo','ci_hi'])
    accounting=[]
    for (day,sample),g in ols.groupby(['date','sample']):
        model=g.iloc[0];nf=int(model.n_treated_as_floor);nn=int(model.n)
        for treated,count in [(0,nn-nf),(1,nf)]:
            accounting.append(dict(date=day,sample=sample,treated_as_floor=treated,n_devices=count,
                                   model_complete_cases=nn,unit='device',floor_threshold=.05))
    save_csv(pd.DataFrame(accounting),OUT/'m4_ols_floor_accounting_v3.csv')
    public_csv(negative,OUT/'m4_negative_control_ols_v3.csv',['coef','se_HC1','p','r_squared','ci_lo','ci_hi'])
    save_csv(pd.concat(curves,ignore_index=True),OUT/'m4_by_distance_ring_v3.csv')
    save_csv(pd.concat(originals,ignore_index=True),OUT/'m4_by_distance_ring_v3_orig.csv')
    ft=pd.concat(fivecurves,ignore_index=True)
    save_csv(ft,OUT/'m4_five_ring_criterion_v3.csv')
    write_json(ROOT/'00_env/m4_ols_copy_audit_v3.json',{'checks':audit,'all_four_decimals_equal':all(a['four_decimals_equal'] for a in audit),'ring_merges':merge_logs})
    checks['Sstar_OLS_all_four_decimals_equal']=all(a['four_decimals_equal'] for a in audit)
    notes.append({'id':'A5_T21_floor_conflict','resolution':'T21 specific instruction takes precedence: A100-floor uses .05 lower bound, with model-level n_treated_as_floor. Earlier A5 parenthesis says missing.'})
    notes.append({'id':'A5_direction_text_conflict','resolution':'Numeric criteria unchanged. Negative distance coefficient means lower observed ratio farther from Baiguan. The core-slower parenthesis is inconsistent and is not used as interpretation; observed ratios do not identify true traffic.'})
    return ols,negative,ft,pd.concat(curves,ignore_index=True)

def build_grids(dh,attr,dd):
    tg=pd.read_csv(PANELS/'taxi_grid_day.csv'); tg['date']=tg.date.astype(str)
    piv={c:tg.pivot_table(index=['gx','gy'],columns='date',values=c,aggfunc='sum',fill_value=0) for c in ['n_points','n_moving']}
    grid=pd.DataFrame(index=piv['n_points'].index)
    grid['n_base_points']=piv['n_points'].reindex(columns=B_TAXI,fill_value=0).mean(axis=1)
    bg=pd.read_csv(PANELS/'township_centroids_osm.csv');bg=bg.loc[bg.town.eq('百官')].iloc[0]
    centre=np.array(TRANS.transform(bg.lon,bg.lat))
    xy=np.column_stack([(grid.index.get_level_values('gx')+.5)*1000,(grid.index.get_level_values('gy')+.5)*1000])
    grid['dist_baiguan_km']=np.linalg.norm(xy-centre,axis=1)/1000
    grid['distance_ring_orig']=ring(grid.dist_baiguan_km)
    camera=attr.loc[attr.in_Sstar.eq(1)&attr.lon.notna()&attr.lat.notna()].copy()
    e,north=TRANS.transform(camera.lon.to_numpy(),camera.lat.to_numpy())
    camera['gx']=np.floor(e/1000).astype(int);camera['gy']=np.floor(north/1000).astype(int)
    cam=camera.groupby(['gx','gy']).size().rename('n_Sstar_cameras').to_frame()
    for day in DATES:
        refs=[d for d in B_TAXI if pd.Timestamp(d).dayofweek==pd.Timestamp(day).dayofweek]
        for metric,col in [('taxi_pts','n_points'),('taxi_moving','n_moving')]:
            p=piv[col].reindex(grid.index)
            grid['n_'+metric+'_'+day]=p.reindex(columns=[day],fill_value=0)[day]
            grid['b_'+metric+'_'+day]=p.reindex(columns=refs,fill_value=0).mean(axis=1)
            grid['r_'+metric+'_'+day]=grid['n_'+metric+'_'+day]/grid['b_'+metric+'_'+day].replace(0,np.nan)
        n,b=device_vectors(day,dh=dh,dd=dd,hour_matched=True)
        temp=camera[['gx','gy']].copy();temp['n']=n.reindex(camera.index);temp['b']=b.reindex(camera.index)
        sums=temp.groupby(['gx','gy'])[['n','b']].sum()
        cam['n_camera_'+day]=sums.n;cam['b_camera_'+day]=sums.b
        cam['r_camera_'+day]=sums.n/sums.b.replace(0,np.nan)
    return grid,cam

def grid_correlations(pair,threshold):
    rows=[];nested={}
    for day in DATES:
        valid=pair.dropna(subset=['r_taxi_pts_'+day,'r_camera_'+day,'dist_baiguan_km'])
        metrics=[('dist_taxi',valid.dist_baiguan_km,valid['r_taxi_pts_'+day]),
                 ('dist_camera',valid.dist_baiguan_km,valid['r_camera_'+day]),
                 ('taxi_camera',valid['r_taxi_pts_'+day],valid['r_camera_'+day])]
        nested[day]={'n_grids':len(valid),'threshold':threshold,'camera_hour_matched':int(day==DATES[0]),'taxi_hour_matched':0}
        for label,x,y in metrics:
            sp=spearmanr(x,y);kt=kendalltau(x,y)
            rows.append(dict(date=day,threshold=threshold,metric=label,n_grids=len(valid),
                             spearman_rho=float(sp.statistic),spearman_p=float(sp.pvalue),
                             kendall_tau=float(kt.statistic),kendall_p=float(kt.pvalue),
                             source='v3_recomputed',taxi_hour_matched=0,camera_hour_matched=int(day==DATES[0])))
            nested[day][label]={'rho':float(sp.statistic),'p':float(sp.pvalue),'kendall_tau':float(kt.statistic),'kendall_p':float(kt.pvalue)}
    return pd.DataFrame(rows),nested

def share_boot(grid,mapping,labels,day,rng):
    n=grid['n_taxi_pts_'+day].to_numpy(float);b=grid['b_taxi_pts_'+day].to_numpy(float)
    ids=grid.distance_ring_orig.map(mapping).to_numpy()
    weights=rng.multinomial(len(grid),np.full(len(grid),1/len(grid)),size=B)
    tn=weights@n;tb=weights@b;out={}
    for label in labels:
        ix=ids==label
        sb=float(b[ix].sum()/b.sum());st=float(n[ix].sum()/n.sum()) if n.sum()>0 else np.nan
        shift=(weights[:,ix]@n[ix])/tn-(weights[:,ix]@b[ix])/tb
        out[label]=(sb,st,*ci(shift),int(ix.sum()),int(n[ix].sum()),float(b[ix].sum()))
    return out

def grid_curves(grid,pair,threshold,mapping,labels,rng):
    rows=[]
    for day in DATES:
        city_shares=share_boot(grid,mapping,labels,day,rng)
        pair_shares=share_boot(pair,mapping,labels,day,rng)
        for label in labels:
            x=pair.loc[pair.distance_ring_orig.map(mapping).eq(label)].copy()
            row=dict(date=day,threshold=threshold,distance_ring=label,n_grids=len(x),
                     n_Sstar_cameras=int(x.n_Sstar_cameras.sum()),taxi_hour_matched=0,camera_hour_matched=int(day==DATES[0]),
                     share_scope='all_threshold_eligible_taxi_grids',source='v3_recomputed')
            simulations={}
            for metric in ['taxi_pts','taxi_moving','camera']:
                ns=x['n_'+metric+'_'+day].to_numpy();bs=x['b_'+metric+'_'+day].to_numpy()
                sims=sims_ratio(ns,bs,rng);simulations[metric]=sims
                row['r_'+metric]=aggregate(ns,bs);row['r_'+metric+'_ci_lo'],row['r_'+metric+'_ci_hi']=ci(sims)
                row['n_'+metric]=int(ns.sum());row['b_'+metric]=float(bs.sum())
            # Independent grid weights for the two source sums, not identical paired weights.
            row['delta_ring']=row['r_taxi_pts']-row['r_camera']
            row['delta_ring_ci_lo'],row['delta_ring_ci_hi']=ci(simulations['taxi_pts']-simulations['camera'])
            sb,st,lo,hi,nc,npts,bpts=city_shares[label]
            row.update(share_base=sb,share_t=st,share_shift=st-sb,share_shift_ci_lo=lo,share_shift_ci_hi=hi,
                       n_taxi_city_grids=nc,n_taxi_city_pts=npts,b_taxi_city_pts=bpts,n_eligible_city_grids=len(grid))
            psb,pst,plo,phi,_,_,_=pair_shares[label]
            row.update(paired_share_base=psb,paired_share_t=pst,paired_share_shift=pst-psb,
                       paired_share_shift_ci_lo=plo,paired_share_shift_ci_hi=phi)
            rows.append(row)
    return pd.DataFrame(rows)

def run_taxi(dh,attr,dd,checks,notes):
    allgrid,cam=build_grids(dh,attr,dd);tables=[];corrs=[];merges=[];stats={};pairs={}
    for threshold in [100,200,400]:
        grid=allgrid.loc[allgrid.n_base_points.ge(threshold)].copy();pair=grid.join(cam,how='inner')
        mapping,labels,changes=merge_map(pair.distance_ring_orig.value_counts().to_dict())
        merges.append(dict(threshold=threshold,n_eligible_grids=len(grid),n_paired_grids=len(pair),mapping=mapping,changes=changes))
        rng=np.random.default_rng(SEED)
        table=grid_curves(grid,pair,threshold,mapping,labels,rng);tables.append(table)
        corr,stat=grid_correlations(pair,threshold);corrs.append(corr);stats[str(threshold)]=stat;pairs[threshold]=pair
        if threshold==200:
            save_csv(table,TWO/'m2_taxi_redistribution_v3.csv');save_csv(table,OUT/'m4_taxi_redistribution_v3.csv')
            save_csv(table,OUT/'m4_taxi_camera_gradient_v3.csv')
            orig=grid_curves(grid,pair,threshold,dict(zip(RINGS,RINGS)),RINGS,np.random.default_rng(SEED))
            save_csv(orig,TWO/'m2_taxi_redistribution_v3_orig.csv');save_csv(orig,OUT/'m4_taxi_camera_gradient_v3_orig.csv')
            # Existing three-day correlation values are copied only after equality audit.
            old=json.loads((V1/'05_m4_spatial/m4_taxi_camera_spearman.json').read_text(encoding='utf-8'))
            oldstat=old.get('by_date',old.get('correlations',old))
            if '0726' not in oldstat:
                # v1 wraps its values under the explicit field shown in its JSON.
                oldstat=next((v for v in old.values() if isinstance(v,dict) and '0726' in v),oldstat)
            for day in DATES[1:]:
                key=pd.Timestamp(day).strftime('%m%d')
                for metric,oldkey in [('dist_taxi','spearman_dist_taxi'),('dist_camera','spearman_dist_camera'),('taxi_camera','spearman_taxi_camera')]:
                    if key in oldstat:
                        previous=oldstat[key][oldkey]
                        checks['correlation_v1_'+day+'_'+metric]=bool(abs(stat[day][metric]['rho']-previous['rho'])<1e-10 and abs(stat[day][metric]['p']-previous['p'])<1e-10)
                        stat[day][metric]['source']='formal_v1_verified_and_copied'
            pairedlong=[]
            for day in DATES:
                q=pair.reset_index()[['gx','gy','dist_baiguan_km','distance_ring_orig','n_Sstar_cameras','r_taxi_pts_'+day,'r_camera_'+day]].copy()
                q=q.rename(columns={'r_taxi_pts_'+day:'r_taxi_pts','r_camera_'+day:'r_camera'});q['date']=day
                q['distance_ring']=q.distance_ring_orig.map(mapping);q['threshold']=threshold;pairedlong.append(q)
            save_csv(pd.concat(pairedlong,ignore_index=True),TWO/'m2_taxi_camera_paired_grids_v3.csv')
    sensitivity=pd.concat(tables,ignore_index=True);correlations=pd.concat(corrs,ignore_index=True)
    public_csv(correlations,TWO/'m2_taxi_camera_correlations_v3.csv',['spearman_rho','spearman_p','kendall_tau','kendall_p'])
    save_csv(sensitivity,TWO/'m2_taxi_grid_threshold_sensitivity_v3.csv');save_csv(sensitivity,OUT/'m4_taxi_grid_threshold_sensitivity_v3.csv')
    for threshold in [100,200,400]:
        v=correlations.loc[correlations.threshold.eq(threshold)&correlations.date.eq('2021-07-26')&correlations.metric.eq('dist_taxi')].iloc[0]
        checks['taxi_dist_positive_0726_threshold_'+str(threshold)]=bool(v.spearman_rho>0)
    main=stats['200']
    write_json(OUT/'m4_taxi_camera_spearman_v3.json',{'seed':SEED,'threshold':200,'dates':main,'threshold_variants':stats,'taxi_hourly_spatial_status':'BLOCKED_missing_existing_grid_hour_panel','bootstrap_B':B})
    write_json(ROOT/'00_env/m4_grid_merges_v3.json',merges)
    # Grid-day checkpoint products cannot recover the joint grid-hour margin.
    hour_path=PANELS/'taxi_grid_hour.csv';checkpoints=list((PANELS/'taxi_grid_checkpoints').glob('*.csv'))
    cache_schemas=[pd.read_csv(p,nrows=0).columns.tolist() for p in checkpoints[:2]]
    json_sample=next((PANELS/'taxi_grid_checkpoints').glob('*.json'),None)
    checkpoint_example=json.loads(json_sample.read_text(encoding='utf-8')) if json_sample else {}
    status={'status':'BLOCKED','missing_input':str(hour_path),'reason':'No existing grid-by-hour panel. City-hour and grid-day marginals cannot recover the joint distribution. Raw source re-read prohibited.',
            'city_hour_columns':pd.read_csv(PANELS/'taxi_hour_valid.csv',nrows=0).columns.tolist(),'checkpoint_csv_schema_sample':cache_schemas,
            'checkpoint_grid_schema':['date','gx','gy','n_points','n_moving'],
            'checkpoint_hourly_schema':['date','hour','n_points','n_moving'],
            'checkpoint_example_keys':list(checkpoint_example.keys()),
            'checkpoint_grid_tuple_length':len(checkpoint_example.get('grid',[[]])[0]),
            'checkpoint_hourly_tuple_length':len(checkpoint_example.get('hourly',[[]])[0]),'source_accessed':False}
    if hour_path.exists():raise RuntimeError('Unexpected hourly grid panel became available; implement its fixed definition rather than reporting BLOCKED.')
    write_json(ROOT/'00_env/m4_taxi_hourly_blocked_v3.json',status)
    save_csv(pd.DataFrame([dict(date='2021-07-26',status='BLOCKED',reason='taxi_grid_hour absent; grid-hour cannot be reconstructed from marginal totals',hour=np.nan,distance_ring='',r_taxi_pts=np.nan,n_grids=np.nan)]),TWO/'m2_taxi_redistribution_hourly_v3.csv')
    notes.append({'id':'T16_hourly_BLOCKED',**status})
    checks['paired_main_n_130']=len(pairs[200])==130;checks['eligible_main_n_204']=len(allgrid.loc[allgrid.n_base_points.ge(200)])==204
    return sensitivity.loc[sensitivity.threshold.eq(200)].copy(),correlations,pairs[200],stats

def h3_verdict(ols,negative,five):
    def row(day,sample='Sstar',term=DIST):return ols.loc[ols.date.eq(day)&ols['sample'].eq(sample)&ols.term.eq(term)].iloc[0]
    def observed(x):return {c:float(x[c]) for c in ['coef','se_HC1','p','ci_lo','ci_hi']}|{'n':int(x.n)}
    a=row('2021-07-26');b=row('2021-07-27');c=row('2021-07-28');on=row('2021-07-26','S_on')
    neg=negative.loc[negative.term.eq(DIST)]
    terrain=ols.loc[ols['sample'].eq('Sstar')&ols.date.isin(DATES[1:3])&ols.term.isin(['elev_m','relief_300m'])]
    rings=five.loc[five.date.eq('2021-07-26')&five['sample'].eq('Sstar')]
    rho=float(spearmanr(np.arange(1,len(rings)+1),rings.r_camera).statistic)
    proto=json.loads((ROOT/'00_env/m4_protocol_frozen_v3.json').read_text(encoding='utf-8'))
    obs=[{'2021-07-26':observed(a),'2021-07-27':observed(b)},observed(c),observed(on),
         {r.date:observed(r) for _,r in neg.iterrows()},
         [dict(date=r.date,term=r.term,p=float(r.p)) for _,r in terrain.iterrows()],
         {'n_rings':len(rings),'rho':rho,'ratios':rings[['distance_ring','r_camera']].to_dict('records')}]
    met=[a.coef<0 and a.p<.05 and b.coef<0 and b.p<.05,c.ci_lo<=0<=c.ci_hi,on.coef<0 and on.p<.05,
         not ((neg.coef<0)&(neg.p<.05)).any(),bool((terrain.p>=.05).all()),len(rings)==5 and rho<=-.6]
    criteria=[{**rule,'observed':value,'met':bool(ok)} for rule,value,ok in zip(proto['H3_criteria'],obs,met)]
    status='supported' if all(met) else ('partial' if met[0] and met[3] else 'not_supported')
    return {'hypothesis':'H3','status':status,'criteria':criteria,'automatic_stop_condition':None,
            'taxi_cross_source_direction_is_H3_criterion':False,'criterion_baseline':'B1',
            'interpretation':'Lower observed camera flow ratio farther from Baiguan on July 26-27; no evidence that this identifies true traffic or slower core recovery.',
            'terrain_qualification':'Nonsignificant elevation/relief terms meet a necessary condition; they do not establish terrain independence.',
            'Sstar_selection_qualification':'Selection at >=20% on July26-30 can remove low-ratio core devices and inflate their observed stable-set ratio; sensitivity models are descriptive.',
            'A100_floor_descriptive_only':ols.loc[ols['sample'].eq('A100_floor')&ols.term.eq(DIST)].to_dict('records')}

def figures(attr,dh,dd,five,ols,taxi,corr,pair):
    plt=setup_plot();colors=['#2a78d6','#eb6834','#1baf7a'];rng=np.random.default_rng(SEED)
    fig,axes=plt.subplots(1,3,figsize=(16,5.3));data=[]
    n,b=device_vectors('2021-07-26',dh=dh,dd=dd,hour_matched=False)
    x=attr.loc[attr.in_Sstar.eq(1)&attr.lon.notna()&attr.lat.notna()].copy();r=n/b.replace(0,np.nan)
    e,north=TRANS.transform(x.lon.to_numpy(),x.lat.to_numpy());je=e+rng.uniform(-200,200,len(x));jn=north+rng.uniform(-200,200,len(x))
    sc=axes[0].scatter(je/1000,jn/1000,c=r.reindex(x.index),s=np.clip(np.sqrt(x.base_B1)/2,10,55),cmap='Blues',vmin=0,vmax=1.2,alpha=.8)
    fig.colorbar(sc,ax=axes[0],fraction=.04,pad=.04,label='Observed ratio')
    axes[0].set(xlabel='UTM 51N easting (km)',ylabel='UTM 51N northing (km)',title='(a) July 26: stable cameras');axes[0].set_aspect('equal',adjustable='box')
    lon,lat=INVERSE.transform(je,jn)
    data.append(pd.DataFrame(dict(panel='map',date='2021-07-26',plot_lon=np.round(lon,2),plot_lat=np.round(lat,2),ratio=r.reindex(x.index).to_numpy(),base_B1=x.base_B1.to_numpy())))
    for i,day in enumerate(DATES[1:]):
        q=five.loc[five.date.eq(day)&five['sample'].eq('Sstar')].copy();xx=np.arange(len(q))
        axes[1].errorbar(xx,q.r_camera,yerr=[q.r_camera-q.r_camera_ci_lo,q.r_camera_ci_hi-q.r_camera],color=colors[i],marker='o',capsize=3,label=day[5:])
        q['panel']='five_ring_camera';data.append(q)
    axes[1].set(xticks=np.arange(5),xticklabels=FIVE,xlabel='Distance to Baiguan (km)',ylabel='Observed camera flow ratio',title='(b) Stable cameras: five rings');axes[1].legend(frameon=False)
    co=ols.loc[ols['sample'].eq('Sstar')&ols.term.eq(DIST)].copy();yy=np.arange(len(co))
    axes[2].errorbar(co.coef,yy,xerr=[co.coef-co.ci_lo,co.ci_hi-co.coef],fmt='o',color=colors[0],capsize=4)
    axes[2].axvline(0,color='#999999',ls='--',lw=1);axes[2].set(yticks=yy,yticklabels=co.date.str[5:],xlabel='log1p(distance) coefficient (HC1 95% CI)',title='(c) Adjusted distance gradient');axes[2].invert_yaxis()
    co['panel']='ols_distance';data.append(co)
    fig.text(.5,.015,'Map locations jittered independently by ±200 m on each UTM axis; point size represents baseline flow.\nFive-ring intervals: 500 device-cluster resamples. Negative coefficients mean lower observed ratios farther from Baiguan.',ha='center',fontsize=9)
    for ax in axes:ax.grid(alpha=.25)
    fig.tight_layout(rect=[0,.12,1,1]);fig.savefig(guarded(FIG/'fig5_spatial_v3.png'));plt.close(fig)
    save_csv(pd.concat(data,ignore_index=True,sort=False),FIG/'fig5_spatial_v3_data.csv')
    fig,axes=plt.subplots(2,2,figsize=(13,11));data=[]
    for ax,day,letter in zip(axes[0],['2021-07-26','2021-07-28'],['a','b']):
        xx=pair['r_camera_'+day];yy=pair['r_taxi_pts_'+day]
        sc=ax.scatter(xx,yy,c=pair.dist_baiguan_km,cmap='viridis',s=22,alpha=.75)
        fig.colorbar(sc,ax=ax,fraction=.035,pad=.025,label='Distance to Baiguan (km)')
        stat=corr.loc[corr.threshold.eq(200)&corr.date.eq(day)&corr.metric.eq('taxi_camera')].iloc[0]
        ax.set(xlabel='Observed camera ratio',ylabel='Taxi point ratio',title=f'({letter}) {day[5:]} paired grids: ρ={stat.spearman_rho:.2f}, p={stat.spearman_p:.3f}, n={int(stat.n_grids)}')
        q=pd.DataFrame({'panel':'scatter','date':day,'r_camera':xx.to_numpy(),'r_taxi_pts':yy.to_numpy(),'dist_baiguan_km':pair.dist_baiguan_km.to_numpy()});data.append(q)
    ax=axes[1,0]
    for i,day in enumerate(['2021-07-26','2021-07-28']):
        q=taxi.loc[taxi.date.eq(day)].copy();xx=np.arange(len(q))
        for metric,color in [('camera',colors[0]),('taxi_pts',colors[1])]:
            ax.errorbar(xx,q['r_'+metric],yerr=[q['r_'+metric]-q['r_'+metric+'_ci_lo'],q['r_'+metric+'_ci_hi']-q['r_'+metric]],
                        color=color,ls='-' if i==0 else '--',marker='o' if i==0 else '^',capsize=3,label=('Camera' if metric=='camera' else 'Taxi points')+' '+day[5:])
        q['panel']='paired_ring_curve';data.append(q)
    ax.set(xticks=np.arange(5),xticklabels=FIVE,xlabel='Distance to Baiguan (km)',ylabel='Same-weekday ratio',title='(c) Same paired grids, two sensors');ax.legend(frameon=False,fontsize=9,ncol=2)
    ax=axes[1,1];width=.34
    for i,day in enumerate(['2021-07-26','2021-07-28']):
        q=taxi.loc[taxi.date.eq(day)].copy();xx=np.arange(len(q))+(i-.5)*width
        ax.bar(xx,q.share_shift,width=width,color=colors[i],label=day[5:])
        ax.errorbar(xx,q.share_shift,yerr=[q.share_shift-q.share_shift_ci_lo,q.share_shift_ci_hi-q.share_shift],fmt='none',color='#555555',capsize=3)
        q['panel']='taxi_city_share_shift';data.append(q)
    ax.axhline(0,color='#999999',lw=1);ax.set(xticks=np.arange(5),xticklabels=FIVE,xlabel='Distance to Baiguan (km)',ylabel='Change in share of eligible-city taxi points',title='(d) Taxi point redistribution');ax.legend(frameon=False)
    for ax in axes.flat:ax.grid(alpha=.25)
    fig.text(.5,.015,'Taxi and camera ring ratios use 130 paired grids; city shares use all 204 eligible taxi grids.\nIntervals: 500 grid-cluster resamples; source differences use independent grid weights. Observed sensors do not identify true traffic.',ha='center',fontsize=9)
    fig.tight_layout(rect=[0,.07,1,1]);fig.savefig(guarded(FIG/'fig7_two_sensors_v3.png'));plt.close(fig)
    save_csv(pd.concat(data,ignore_index=True,sort=False),FIG/'fig7_two_sensors_v3_data.csv')

def main():
    started=now();t=time.time();protocol=ROOT/'00_env/m4_protocol_frozen_v3.json'
    if not protocol.exists():raise RuntimeError('Freeze H3 criteria before running numbers')
    for path in [OUT,TWO,FIG]:path.mkdir(parents=True,exist_ok=True)
    checks={};notes=[];dh,attr,dd=load_panels()
    ols,negative,five,curves=run_cameras(dh,attr,dd,checks,notes)
    taxi,corr,pair,stats=run_taxi(dh,attr,dd,checks,notes)
    verdict=h3_verdict(ols,negative,five);write_json(OUT/'m4_h3_verdict_v3.json',verdict)
    figures(attr,dh,dd,five,ols,taxi,corr,pair)
    methods='''# M4 v3 / T16 / T21 methods\n\nA5 and A6 are reviewer-authorised post hoc amendments; v1 remains unchanged.\n\nThe frozen formula uses HC1. Sstar coefficients are copied from v1 after independent equality checks at four decimals. S_on uses full-day A100/B1 >=20%, not the A1 failure denominator. T21 specifically requires A100-floor and supersedes A5's earlier missing-value parenthesis. Model counts show devices with ratios below .05.\n\nOriginal six-ring tables are retained. Cells with fewer than ten units merge inward, repeating if needed. Five-ring H3 criterion/figure tables additionally combine the outer two rings as 12+. The same mapping is used for both sources in a paired-grid table. The primary paired sample has 130 grids and the city-share denominator has 204 eligible taxi grids; paired shares are also reported separately. Eligibility averages all sixteen B_TAXI days with missing grid-days filled by zero; ratios use same-weekday B_TAXI. Taxi July25 uses all hours; cameras July25 use 11–23 and matching baseline hours.\n\nAll bootstrap intervals use 500 resamples and seed 20261005. Ring ratios resample grids within rings; taxi-minus-camera ratios use independent resampling weights. City share shifts jointly resample all eligible grids, preserving the total denominator and within-replicate baseline/current pairing.\n\nA negative distance coefficient means a lower observed ratio farther from Baiguan. This conflicts with A5's core-slower parenthesis: numeric H3 criteria are unchanged, while interpretation follows the mathematical direction. Nonsignificant terrain terms do not prove terrain independence. Sstar selection can exclude low-ratio core devices; all sensor ratios describe observations rather than identify true traffic.\n\nT16 hourly spatial analysis is BLOCKED: no existing taxi_grid_hour panel; grid-day and city-hour marginals cannot identify joint grid-hour counts. No source re-read or synthetic reconstruction was attempted.\n\nMap points use independent uniform ±200 m UTM jitter; exported figure coordinates have two decimal degrees and no device or vehicle identifiers.\n'''
    guarded(OUT/'M4_METHODS_v3.md').write_text(methods,encoding='utf-8')
    write_json(ROOT/'00_env/m4_deviations_v3.json',notes)
    outputs=[str(p.relative_to(ROOT)) for folder in [OUT,TWO,FIG] for p in folder.iterdir() if p.is_file() and ('v3' in p.name)]
    write_json(ROOT/'00_env/m4_execution_v3.json',dict(started=started,ended=now(),elapsed_seconds=time.time()-t,
        command=_release_path('path_013'),
        input_root=str(V1),source_accessed=False,key_accessed=False,protocol_sha256=hashlib.sha256(protocol.read_bytes()).hexdigest(),
        outputs=outputs,checks=checks,H3=verdict['status'],T16_hourly='BLOCKED'))
    print(json.dumps(dict(M4='complete_except_T16_hourly_BLOCKED',H3=verdict['status'],n_paired_grids=len(pair),checks=checks),ensure_ascii=False))

if __name__=='__main__':main()
