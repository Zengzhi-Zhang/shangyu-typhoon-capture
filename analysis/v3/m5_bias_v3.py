# -*- coding: utf-8 -*-
"""Amendment A1 / M5 v3. Formal-v1 inputs are strictly read-only.

No source CSV/workbook scan, no key access, no panel copy. The interpretation
file is frozen before any numerical panel load and checked at run start.
"""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[2]), str(_ReleasePath(__file__).resolve().parents[0])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
import argparse
import hashlib
import json
import shutil
import time
from datetime import datetime,timezone,timedelta
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from pyproj import Transformer
from statsmodels.stats.multitest import multipletests

SEED=20261005
ROOT=Path(_release_path('v3_root'))
INPUTROOT=Path(_release_path('project_root'))
N_BOOT=500;N_TAXI_BOOT=200;N_PERM=999
def days(a,b):return pd.date_range(a,b).strftime('%Y-%m-%d').tolist()
D_PARTIAL=['2021-07-'+d for d in ['08','10','22','23','24','25']]
B1=[d for d in days('2021-07-05','2021-07-21') if d not in D_PARTIAL]
B3=['2021-06-17']+days('2021-06-28','2021-07-04')
B_TAXI=days('2021-07-06','2021-07-21')
EVENT=days('2021-07-25','2021-08-02')
PLATFORM=['2021-07-08','2021-07-10']
SIGNATURE_DATES=['2021-07-25','2021-07-26','2021-07-27','2021-07-28','2021-08-02']+PLATFORM
D_INELIG=set(D_PARTIAL+days('2021-07-26','2021-08-02'))
RINGS=['0-2','2-4','4-7','7-12','12-20','20+']
RULES={
 'amendment':'A1; reviewer-authorised post hoc correction',
 'seed':SEED,'device_bootstrap':500,'taxi_vehicle_bootstrap':200,'permutations':999,
 'A1':'Compute target-day LOO same-weekday B1 mean first; if no days, use B1 union B3 excluding target. If previous day is absent or ineligible, use LOO baseline. Otherwise use previous counts only where previous >=0.5*LOO baseline; July25 uses 11..23 for numerator and all denominator dates.',
 'online_comparator':'A200 intersect frozen full-day S_on(t), excluding A1 failed; intermediate devices omitted and sample sizes reported. Join-count uses all geolocated A200.',
 'Holm_family':'All 6 tests on all 7 prespecified signature dates, 42 raw p values; Holm is supplemental. Frozen criteria use raw p.',
 'signature_unique':'Each storm feature must be present on July26 and absent on BOTH July8 and July10. Feature1: mean_log_base_diff >0 AND raw p<0.05. Feature2: mean_dist_baiguan_diff <0 (no additional p threshold). Feature3: failed Q4 share minus online Q4 share >=0.15. At least two storm-unique features.',
 'persistence':'A200 with first A1 failure at any event date July25..August2. Recovery means first later event date with n>=0.5*A1 denominator, positive denominator. July25 has afternoon coverage. Not_recovered counts no first recovery by August2; current failure on August2 is reported separately for recurrence.',
 'decomposition':'Universe A100. Groups exclusive: Sstar first, then A1 ratio<.05, then .05<=A1 ratio<.5, then remaining non-Sstar. Last group is named online_nonSstar operationally >=.5 of A1 denominator; frozen S_on eligibility is a distinct full-day B1 quantity. Official F_A1 counts remain A200. Weights are matched B1 flow, not A1 flow; decomposition must exactly reproduce R_naive-R_stable.',
 'paired_CI':'Naive/online/stable use identical A100 device-cluster weights, 500 draws. Target-day S_on held fixed. Taxi second-batch vehicle-cluster draws=200 and independent stable draws=500; all 200x500 empirical product differences define the independent difference interval without extra bootstrap draws.',
 'leaveout_criterion4':'ALL 2 maskings x5 event dates must each have |drop bias|<0.02 AND |naive_zero bias|>5*|drop bias|. This strict interpretation is frozen before panel reads; averages reported descriptively only.',
 'H4_verdict':'supported iff criteria1,2,3,4 all met; partial iff1,3 met and2 or4 fails; otherwise not_supported. Section3.10 stop evaluated on v3 A1 tests; original v2 stop result retained separately. Criteria5 reports imputation comparison and does not gate verdict.',
 'A6':'Device distance layers merge any <10-device outer ring inward for the specific table population; original ring counts are preserved in separate _orig output.',
 'unchanged_correction_copy':'Copy correction_methods and all leaveout CSVs byte-for-byte from formal_v1. Correction_methods reflects frozen v2 imputation, not re-estimated A1 imputation. Leaveout independent of A1. Both labels disclosed.'}

def stamp():return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
def clean(x):
    if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [clean(v) for v in x]
    if isinstance(x,np.generic):return clean(x.item())
    if isinstance(x,float) and not np.isfinite(x):return None
    if isinstance(x,Path):return str(x)
    return x
def write_json(path,obj):Path(path).write_text(json.dumps(clean(obj),ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def freeze():
    path=ROOT/'00_env/m5_A1_criteria_frozen_v3.json';path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        if json.loads(path.read_text(encoding='utf-8'))['rules']!=RULES:raise RuntimeError('Frozen M5 criteria differ; refuse silent change')
    else:write_json(path,dict(frozen_at=stamp(),stage='before numerical panel load',rules=RULES))
    return path

def refs(date,pool=B1):return [d for d in pool if pd.Timestamp(d).dayofweek==pd.Timestamp(date).dayofweek]
def ratio(n,b):
    den=np.asarray(b,float).sum();return float(np.asarray(n,float).sum()/den) if den>0 else np.nan
def ci(draw):
    x=np.asarray(draw,float);x=x[np.isfinite(x)]
    return tuple(np.quantile(x,[.025,.975])) if len(x) else (np.nan,np.nan)

def knn6_edges(xy):
    k=min(6,len(xy)-1)
    if k<1:return np.empty((0,2),int)
    candidates=np.asarray(cKDTree(xy).query(xy,k=min(len(xy),k+2))[1]).reshape(len(xy),-1)
    edges=set()
    for i,neighbors in enumerate(candidates):
        for j in [int(v) for v in neighbors if int(v)!=i][:k]:edges.add((min(i,j),max(i,j)))
    return np.asarray(sorted(edges),int).reshape(-1,2)
def joincount(xy,failed):
    edges=knn6_edges(xy);failed=np.asarray(failed,bool)
    observed=float((failed[edges[:,0]]&failed[edges[:,1]]).sum()) if len(edges) else 0.
    rng=np.random.default_rng(SEED);draw=[]
    for _ in range(N_PERM):
        mask=rng.permutation(failed);draw.append(float((mask[edges[:,0]]&mask[edges[:,1]]).sum()) if len(edges) else 0.)
    draw=np.asarray(draw);sd=float(draw.std(ddof=1))
    return dict(observed=observed,perm_mean=float(draw.mean()),perm_sd=sd,z=(observed-draw.mean())/sd if sd else np.nan,
                p_perm=float((1+np.sum(draw>=observed))/(N_PERM+1)),n_edges=len(edges),n_spatial=len(failed),n_failed_spatial=int(failed.sum()))
def permutation(values,failed,categorical=False):
    values=np.asarray(values);failed=np.asarray(failed,bool)
    if not failed.any() or failed.all():return dict(observed=np.nan,perm_mean=np.nan,perm_sd=np.nan,z=np.nan,p_perm=np.nan)
    if categorical:
        _,code=np.unique(values.astype(str),return_inverse=True);total=np.bincount(code).astype(float)
        ef=total*failed.mean();eo=total-ef
        def stat(mask):
            x=np.bincount(code[mask],minlength=len(total));y=total-x
            return float(np.divide((x-ef)**2,ef,out=np.zeros_like(ef),where=ef>0).sum()+np.divide((y-eo)**2,eo,out=np.zeros_like(eo),where=eo>0).sum())
    else:
        values=values.astype(float)
        def stat(mask):return float(values[mask].mean()-values[~mask].mean())
    observed=stat(failed);rng=np.random.default_rng(SEED)
    draw=np.array([stat(rng.permutation(failed)) for _ in range(N_PERM)]);sd=float(draw.std(ddof=1))
    p=(1+np.sum(draw>=observed if categorical else abs(draw)>=abs(observed)))/(N_PERM+1)
    return dict(observed=observed,perm_mean=float(draw.mean()),perm_sd=sd,z=(observed-draw.mean())/sd if sd else np.nan,p_perm=float(p))

class Run:
    def __init__(self):
        self.started=stamp();self.outputs=[];self.inputs={};self.checks={};self.notes=[]
        self.out=ROOT/'06_m5_bias_correction';self.rob=ROOT/'07_m6_robustness';self.fig=ROOT/'08_figures'
        for p in [self.out,self.rob,self.fig,ROOT/'00_env']:p.mkdir(parents=True,exist_ok=True)
    def register(self,rel):
        path=INPUTROOT/rel;stat=path.stat();self.inputs[rel]=dict(size=stat.st_size,mtime_ns=stat.st_mtime_ns);return path
    def read(self,rel,**kwargs):return pd.read_csv(self.register(rel),encoding='utf-8-sig',**kwargs)
    def save(self,df,folder,name):
        path=folder/name;df.to_csv(path,index=False,encoding='utf-8-sig',float_format='%.4f')
        self.outputs.append(dict(file=str(path.relative_to(ROOT)).replace('\\','/'),rows=len(df)));return df
    def load(self):
        a=self.read('01_panels/device_attributes.csv').set_index('dev').sort_index();self.attr=a
        for c in ['in_A100','in_A200','in_Sstar']:a[c]=a[c].astype(int)
        self.devs=a.index.to_numpy();self.A100=a.in_A100.to_numpy(bool);self.A200=a.in_A200.to_numpy(bool);self.Sstar=a.in_Sstar.to_numpy(bool)
        h=self.read('01_panels/device_hour.csv',usecols=['date','dev','hour','n']);self.h=h
        self.D=sorted(h.date.unique());self.daily=h.pivot_table(index='dev',columns='date',values='n',aggfunc='sum',fill_value=0).reindex(index=a.index,columns=self.D,fill_value=0)
        self.afternoon=h[h.hour.between(11,23)].pivot_table(index='dev',columns='date',values='n',aggfunc='sum',fill_value=0).reindex(index=a.index,columns=self.D,fill_value=0)
        self.base=a.base_B1.to_numpy(float)
        self.xy=np.full((len(a),2),np.nan);ok=a.lon.notna()&a.lat.notna()
        trans=Transformer.from_crs(4326,32651,always_xy=True)
        self.xy[ok]=np.column_stack(trans.transform(a.loc[ok,'lon'],a.loc[ok,'lat']));self.coord=np.isfinite(self.xy).all(axis=1)
        self.attr['distance_ring']=pd.cut(a.dist_baiguan_km,[-np.inf,2,4,7,12,20,np.inf],labels=RINGS,right=False).astype(object).fillna('missing')
        self.quartile=np.full(len(a),'missing',object)
        ranks=pd.Series(self.base[self.A200]).rank(method='first');self.quartile[self.A200]=pd.qcut(ranks,4,labels=['Q1','Q2','Q3','Q4']).astype(str).to_numpy()
        self.states={d:self.a1(d) for d in self.D};self.v2counts=self.read('06_m5_bias_correction/m5_failure_counts.csv').set_index('date')
        self.checks['frozen_sets_dimensions']=dict(A100=int(self.A100.sum()),A200=int(self.A200.sum()),Sstar=int(self.Sstar.sum()))
    def vectors(self,date,matched=False,pool=B1):
        mat=self.afternoon if matched else self.daily
        return mat[date].to_numpy(float),mat[refs(date,pool)].mean(axis=1).to_numpy(float)
    def a1(self,date):
        matched=date=='2021-07-25';mat=self.afternoon if matched else self.daily
        r=[d for d in refs(date) if d!=date];pool='B1'
        if not r:r=[d for d in refs(date,sorted(set(B1+B3))) if d!=date];pool='B1+B3'
        if not r:return None
        b=mat[r].mean(axis=1).to_numpy(float);n=mat[date].to_numpy(float)
        prev=(pd.Timestamp(date)-pd.Timedelta(days=7)).strftime('%Y-%m-%d')
        daybad=prev in D_INELIG or prev not in mat.columns
        denom=b.copy();degraded=np.zeros(len(b),bool)
        if not daybad:
            previous=mat[prev].to_numpy(float);degraded=previous<.5*b;denom=np.where(degraded,b,previous)
        online_daily,b_daily=self.vectors(date,False)
        online=self.A100 & np.divide(online_daily,b_daily,out=np.full(len(b),np.nan),where=b_daily>0).__ge__(.2)
        return dict(n=n,b_loo=b,denom=denom,failed=self.A200&(n<.05*denom),degraded=self.A200&(n<.5*denom),
                    online=online,daybad=daybad,devicebad=degraded,prev=prev,baseline_days=r,baseline_pool=pool,hour_matched=int(matched))
    def counts(self):
        rows=[]
        for d,s in self.states.items():
            if s is None:continue
            fulln,fullb=self.vectors(d)
            prev=s['prev'];v2den=self.daily[prev].to_numpy(float) if prev in self.D and prev not in D_PARTIAL else fullb
            row=dict(date=d,n_A200=int(self.A200.sum()),n_failed_A1=int(s['failed'].sum()),n_degraded_A1=int(s['degraded'].sum()),
                failed_prevweek_v2=int((self.A200&(fulln<.05*v2den)).sum()),degraded_prevweek_v2=int((self.A200&(fulln<.5*v2den)).sum()),
                failed_baseline=int((self.A200&(fulln<.05*fullb)).sum()),degraded_baseline=int((self.A200&(fulln<.5*fullb)).sum()),
                failed_baseline_loo_matched=int((self.A200&(s['n']<.05*s['b_loo'])).sum()),
                n_fallback_day_inelig=int(self.A200.sum()) if s['daybad'] else 0,
                n_fallback_device_degraded=int((self.A200&s['devicebad']).sum()),
                n_previous_day_ineligible=int(prev in D_INELIG),n_previous_day_absent=int(prev not in self.D),
                n_baseline_days_used=len(s['baseline_days']),baseline_pool=s['baseline_pool'],baseline_days=';'.join(s['baseline_days']),
                previous_date=prev,hour_matched=s['hour_matched'],n_zero_denominator=int((self.A200&(s['denom']<=0)).sum()),
                n_failed_A1_only_vs_loo=int((s['failed']&~(self.A200&(s['n']<.05*s['b_loo']))).sum()),
                n_failed_loo_only_vs_A1=int(((self.A200&(s['n']<.05*s['b_loo']))&~s['failed']).sum()),
                n_A200_A1_denominator_above_loo=int((self.A200&(s['denom']>s['b_loo'])).sum()))
            if d in self.v2counts.index:
                v=self.v2counts.loc[d]
                if row['failed_prevweek_v2']!=int(v.n_failed_prevweek) or row['failed_baseline']!=int(v.n_failed_baseline):
                    raise AssertionError('Original v2 failure count cannot be independently reproduced')
            rows.append(row)
        frame=self.save(pd.DataFrame(rows),self.out,'m5_failure_counts_v3.csv')
        self.checks['v2_counts_reproduced']=True
        self.checks['A1_fallback_counts_disjoint']=bool((frame.n_fallback_day_inelig+frame.n_fallback_device_degraded<=frame.n_A200).all())
        return frame
    def ordinary(self,counts):
        dates=sorted(set(days('2021-06-29','2021-07-04')+B1))
        frame=counts[counts.date.isin(dates)].copy();summary={}
        for name,col in [('failed','n_failed_A1'),('degraded','n_degraded_A1')]:
            values=frame[col].to_numpy(float);mx=int(values.max())
            summary[name]=dict(median=float(np.median(values)),p90=float(np.quantile(values,.9)),maximum=mx,
                               maximum_dates=frame.loc[frame[col].eq(mx),'date'].tolist(),n_days=len(frame))
        for field in ['median','p90','maximum']:frame['ordinary_'+field+'_failed']=summary['failed'][field];frame['ordinary_'+field+'_degraded']=summary['degraded'][field]
        frame['row_type']='ordinary_day';comparison=[]
        for d in ['2021-07-26','2021-07-27','2021-07-28','2021-08-02']:
            row=counts[counts.date.eq(d)].iloc[0].to_dict();row['row_type']='event_comparison'
            for metric,col in [('failed','n_failed_A1'),('degraded','n_degraded_A1')]:
                for base in ['median','maximum']:
                    den=summary[metric][base];row[metric+'_relative_to_ordinary_'+base]=row[col]/den if den>0 else np.nan
                    row['ordinary_'+base+'_'+metric]=den
            comparison.append(row)
        output=pd.concat([frame,pd.DataFrame(comparison)],ignore_index=True)
        self.save(output,self.out,'m5_ordinary_floor_v3.csv')
        report=dict(failed=summary['failed'],degraded=summary['degraded'],event_comparisons=comparison,
            expectation_checks=dict(july15_nonzero=int(counts.set_index('date').loc['2021-07-15','n_failed_A1'])>0,
                                    july17_nonzero=int(counts.set_index('date').loc['2021-07-17','n_failed_A1'])>0,
                                    maximum_failed_le45=summary['failed']['maximum']<=45),
            ordinary_dates=dates,quantile_method='numpy linear interpolation')
        write_json(self.out/'m5_ordinary_floor_summary_v3.json',report);self.ordinary_report=report
    @staticmethod
    def merge_rings(values):
        values=values.astype(str).copy();groups=[[r] for r in RINGS]
        # The merge is based on the table population, not status-specific cells.
        for i in range(len(groups)-1,0,-1):
            if len(groups[i]) and values.isin(groups[i]).sum()<10:
                groups[i-1]+=groups[i];groups[i]=[]
        mapping={}
        for group in groups:
            if not group:continue
            label=group[0] if len(group)==1 else group[0].split('-')[0]+'+'
            if group[0]=='0-2' and len(group)>1:label='0-'+group[-1].split('-')[-1]
            for r in group:mapping[r]=label
        return values.replace(mapping),mapping
    def tests(self):
        rows=[];profile=[];signature=[]
        attributes={c:self.attr[c].fillna('missing').astype(str).to_numpy() for c in ['road_level','org','distance_ring']}
        for d in SIGNATURE_DATES:
            s=self.states[d];failed=s['failed'];online=self.A200&s['online']&~failed;spatial=self.A200&self.coord
            common=dict(date=d,hour_matched=s['hour_matched'],n_failed=int(failed.sum()),n_online=int(online.sum()),
                        n_excluded_intermediate=int((self.A200&~failed&~online).sum()),denominator='A1',baseline_pool=s['baseline_pool'],n_baseline_days_used=len(s['baseline_days']))
            result=joincount(self.xy[spatial],failed[spatial])
            rows.append({**common,'test':'joincount_knn6',**result,'n_test':int(spatial.sum()),'n_failed_test':int(failed[spatial].sum()),'n_online_test':int((~failed[spatial]).sum())})
            inputs={'mean_log_base_diff':(np.log(np.maximum(self.base,1e-12)),False),
                'chisq_road_level':(attributes['road_level'],True),'chisq_org':(attributes['org'],True),
                'mean_dist_baiguan_diff':(self.attr.dist_baiguan_km.to_numpy(float),False),
                'share_gateway_diff':(self.attr.gateway.fillna(0).to_numpy(float),False)}
            for test,(value,cat) in inputs.items():
                valid=failed|online
                if not cat:valid &= np.isfinite(value)
                result=permutation(value[valid],failed[valid],cat)
                rows.append({**common,'test':test,**result,'n_test':int(valid.sum()),'n_failed_test':int(failed[valid].sum()),'n_online_test':int(online[valid].sum())})
            for attribute,value in list(attributes.items())+[('base_flow_quantile',self.quartile)]:
                for status,mask in [('failed',failed),('online',online)]:
                    for level in sorted(set(value[self.A200])):
                        count=int((mask&(value==level)).sum());total=int(mask.sum())
                        profile.append(dict(date=d,hour_matched=s['hour_matched'],attribute=attribute,category=level,status=status,n_devices=count,n_status=total,share=count/total if total else np.nan))
            orgs=pd.Series(attributes['org'][failed]).value_counts()
            qf=float(np.mean(self.quartile[failed]=='Q4')) if failed.any() else np.nan
            qo=float(np.mean(self.quartile[online]=='Q4')) if online.any() else np.nan
            signature.append({**common,'n_A200':int(self.A200.sum()),'Q4_share_failed':qf,'Q4_share_online':qo,'Q4_share_diff':qf-qo,
                'org_max_share':float(orgs.iloc[0]/failed.sum()) if len(orgs) else np.nan,'org_max_category':str(orgs.index[0]) if len(orgs) else ''})
        tests=pd.DataFrame(rows);valid=tests.p_perm.notna();tests['p_holm']=np.nan
        tests.loc[valid,'p_holm']=multipletests(tests.loc[valid,'p_perm'],method='holm')[1]
        tests['Holm_family']='6_tests_x7_dates_42';self.tests_frame=tests
        self.save(tests[tests.date.isin(SIGNATURE_DATES[:5])],self.out,'m5_failure_nonrandomness_v3.csv')
        control=tests[tests.date.isin(PLATFORM)].merge(self.counts_frame,on='date',suffixes=('','_counts'))
        self.save(control,self.rob,'m6_negative_control_v3.csv')
        self.save(tests,self.rob,'m6_signature_tests_long_v3.csv')
        self.save(pd.DataFrame(profile),self.out,'m5_failure_profile_v3.csv')
        sig=pd.DataFrame(signature).set_index('date')
        for test in tests.test.unique():
            data=tests[tests.test.eq(test)].set_index('date')
            for source,suffix in [('observed',''),('z','_z'),('p_perm','_p'),('p_holm','_p_holm')]:sig[test+suffix]=data[source]
        sig=sig.reset_index();self.signature=sig
        self.save(sig,self.rob,'m6_signature_comparison_v3.csv')
        self.checks['tests_42_arms']=len(tests)==42 and not tests.duplicated(['date','test']).any()
        self.checks['profiles_partition']=bool(pd.DataFrame(profile).groupby(['date','attribute','status']).n_devices.sum().eq(pd.DataFrame(profile).groupby(['date','attribute','status']).n_status.first()).all())
    def persistence(self):
        first=np.full(len(self.attr),'',object);recovery=np.full(len(self.attr),'',object)
        for d in EVENT:
            state=self.states[d]
            first[(first=='')&state['failed']]=d
            recovering=(first!='')&(recovery=='')&(first!=d)&(state['denom']>0)&(state['n']>=.5*state['denom'])
            recovery[recovering]=d
        cohort=first!='';unrecovered=cohort&(recovery=='')
        distribution=pd.DataFrame(dict(first_failure_date=first[cohort],recovery_date=recovery[cohort]))
        distribution.recovery_date=distribution.recovery_date.replace('','not_by_0802')
        distribution=distribution.groupby(['first_failure_date','recovery_date']).size().reset_index(name='n_devices')
        distribution['first_failure_period']=np.where(distribution.first_failure_date.eq('2021-07-25'),'11:00-23:59','full_day')
        distribution['cohort']='A200 any first A1 failure July25..August2'
        self.save(distribution,self.out,'m5_failure_persistence_v3.csv')
        # An additional timing alias preserves the required v2 schema.
        self.save(distribution,self.out,'m5_failure_timing_v3.csv')
        strata=[]
        ring,mapping=self.merge_rings(self.attr.loc[self.A200,'distance_ring'])
        ringfull=np.full(len(self.attr),'missing',object);ringfull[self.A200]=ring.to_numpy()
        for attribute,value in [('org',self.attr.org.fillna('missing').astype(str).to_numpy()),
                               ('distance_ring',ringfull),('base_flow_quantile',self.quartile)]:
            for cat in sorted(set(value[self.A200])):
                mask=self.A200&(value==cat);total=int(mask.sum());failedn=int((cohort&mask).sum());nr=int((unrecovered&mask).sum())
                strata.append(dict(attribute=attribute,category=cat,n_A200_group=total,n_first_failed_event=failedn,
                    n_not_recovered_by_0802=nr,share_group_A200=nr/total if total else np.nan,
                    share_failed_event=nr/failedn if failedn else np.nan,denominator='all A200 in stratum; event-cohort denominator separately reported',ring_variant='A6'))
        original=[]
        value=self.attr.distance_ring.astype(str).to_numpy()
        for cat in sorted(set(value[self.A200])):
            mask=self.A200&(value==cat);total=int(mask.sum());nr=int((unrecovered&mask).sum());cf=int((cohort&mask).sum())
            original.append(dict(attribute='distance_ring',category=cat,n_A200_group=total,n_first_failed_event=cf,n_not_recovered_by_0802=nr,share_group_A200=nr/total if total else np.nan,share_failed_event=nr/cf if cf else np.nan,ring_variant='orig'))
        self.save(pd.DataFrame(strata),self.out,'m5_failure_persistence_profile_v3.csv')
        self.save(pd.DataFrame(original),self.out,'m5_failure_persistence_profile_v3_orig.csv')
        durations=[];observed=[]
        for f,r in zip(first[cohort],recovery[cohort]):
            durations.append((pd.Timestamp(r if r else '2021-08-02')-pd.Timestamp(f)).days);observed.append(bool(r))
        durations=np.asarray(durations);observed=np.asarray(observed,bool);survival=1.;curve=[]
        for lag in range(9):
            risk=int((durations>=lag).sum());events=int(((durations==lag)&observed).sum());censored=int(((durations==lag)&~observed).sum())
            if risk:survival*=1-events/risk
            curve.append(dict(days_since_first_failure=lag,n_at_risk=risk,n_first_recoveries=events,n_right_censored=censored,
                              survival_not_first_recovered=survival,n_event_cohort=int(cohort.sum()),method='Kaplan-Meier; first-recovery duration; August2 right censoring'))
        self.survival=self.save(pd.DataFrame(curve),self.out,'m5_failure_persistence_curve_v3.csv')
        calendar=[]
        for d in EVENT:
            arrived=cohort&(first<=d);recovered=arrived&(recovery!='')&(recovery<=d)
            calendar.append(dict(date=d,n_first_failed_to_date=int(arrived.sum()),n_first_recovered_to_date=int(recovered.sum()),n_awaiting_first_recovery=int((arrived&~recovered).sum()),n_current_failed_A1=int(self.states[d]['failed'].sum()),n_current_degraded_A1=int(self.states[d]['degraded'].sum())))
        self.save(pd.DataFrame(calendar),self.out,'m5_failure_persistence_calendar_v3.csv')
        prior=(self.read('06_m5_bias_correction/m5_failure_timing.csv'))
        v2nr=int(prior.loc[prior.recovery_date.eq('not_by_0802'),'n_devices'].sum())
        report=dict(cohort_definition=RULES['persistence'],n_event_cohort=int(cohort.sum()),n_A200=int(self.A200.sum()),
            not_recovered_by_0802=int(unrecovered.sum()),share_A200=float(unrecovered.sum()/self.A200.sum()),
            current_failed_A1_0802=int(self.states['2021-08-02']['failed'].sum()),n_recovered_then_failed_0802=int((self.states['2021-08-02']['failed']&(recovery!='')).sum()),
            formal_v1_not_recovered_0726_cohort=v2nr,formal_v1_cohort_note='V1 only July26 failed cohort, first July25 or26; cohort and denominator differ from v3',
            ring_merge=mapping,by_attribute=pd.DataFrame(strata).to_dict('records'))
        self.persistence_report=report
        write_json(self.out/'m5_failure_persistence_summary_v3.json',report)
        self.checks['persistence_distribution_total']=int(distribution.n_devices.sum())==int(cohort.sum())
        self.checks['persistence_unrecovered_total']=int(distribution.loc[distribution.recovery_date.eq('not_by_0802'),'n_devices'].sum())==int(unrecovered.sum())
    def decomposition(self):
        rows=[]
        for d in EVENT:
            s=self.states[d];n,b=self.vectors(d,d=='2021-07-25');Rstable=ratio(n[self.Sstar],b[self.Sstar])
            residual=self.A100&~self.Sstar
            masks={'Sstar':self.Sstar,'failed_lt005_nonSstar':residual&(s['n']<.05*s['denom']),
                   'degraded_005_050_nonSstar':residual&(s['n']>=.05*s['denom'])&(s['n']<.5*s['denom'])}
            masks['online_nonSstar']=residual&~masks['failed_lt005_nonSstar']&~masks['degraded_005_050_nonSstar']
            den=b[self.A100].sum();count=np.zeros(len(self.attr),int)
            for group,mask in masks.items():
                count+=mask;weight=b[mask].sum()/den if den else np.nan;rg=ratio(n[mask],b[mask])
                contribution=(n[mask].sum()-Rstable*b[mask].sum())/den if den else np.nan
                rows.append(dict(date=d,group=group,n_devices=int(mask.sum()),baseline_flow=float(b[mask].sum()),observed_records=float(n[mask].sum()),
                    w_g=weight,r_g=rg,R_stable=Rstable,contribution=contribution,hour_matched=s['hour_matched'],
                    group_rule='Sstar priority, then A100 A1 threshold categories; official F_A1 remains A200',weight_baseline='B1 same weekday; July25 11..23 matched'))
            if not np.array_equal(count,self.A100.astype(int)):raise AssertionError('Bias decomposition groups overlap or miss A100')
        frame=pd.DataFrame(rows);checkrows=[]
        for d,g in frame.groupby('date'):
            n,b=self.vectors(d,d=='2021-07-25');expected=ratio(n[self.A100],b[self.A100])-ratio(n[self.Sstar],b[self.Sstar])
            error=float(g.contribution.sum()-expected)
            checkrows.append(dict(date=d,delta_naive=expected,sum_contributions=float(g.contribution.sum()),identity_residual=error,sum_weights=float(g.w_g.sum())))
            if abs(error)>1e-12 or abs(g.w_g.sum()-1)>1e-12:raise AssertionError('Bias decomposition identity failed')
        self.decomp=self.save(frame,self.out,'m5_bias_decomposition_v3.csv')
        self.save(pd.DataFrame(checkrows),self.out,'m5_bias_decomposition_checks_v3.csv')
        self.checks['decomposition_exact_before_rounding']=True
    def visible(self):
        tx=self.read('01_panels/taxi_vehicle_day.csv',dtype={'vehicle_hash':str,'sheet_date':str})
        tx=tx[(tx.batch=='GPS0706-0731')&tx.sheet_date.between('2021-07-06','2021-07-31')&(tx.n_parsed_time>0)]
        taxi=tx.pivot_table(index='vehicle_hash',columns='sheet_date',values='dist_moving_km',aggfunc='sum',fill_value=0)
        rng=np.random.default_rng(SEED);a=int(self.A100.sum())
        device_weights=rng.multinomial(a,np.full(a,1/a),size=N_BOOT)
        taxi_weights=rng.multinomial(len(taxi),np.full(len(taxi),1/len(taxi)),size=N_TAXI_BOOT)
        rows=[];online_counts=[]
        for d in EVENT:
            n,b=self.vectors(d,d=='2021-07-25');n=n[self.A100];b=b[self.A100]
            st=self.Sstar[self.A100];on=self.states[d]['online'][self.A100]
            masks={'R_naive':np.ones(a,bool),'R_online':on,'R_stable':st};draws={};row=dict(date=d,hour_matched=int(d=='2021-07-25'),n_A100=a,n_online=int(on.sum()),n_Sstar=int(st.sum()),device_bootstrap=N_BOOT,taxi_vehicle_bootstrap=N_TAXI_BOOT)
            for label,mask in masks.items():
                row[label]=ratio(n[mask],b[mask]);num=device_weights[:,mask]@n[mask];den=device_weights[:,mask]@b[mask]
                draws[label]=np.divide(num,den,out=np.full(N_BOOT,np.nan),where=den>0)
                row[label+'_ci_lo'],row[label+'_ci_hi']=ci(draws[label])
            for label,target in [('delta_naive','R_naive'),('delta_online','R_online')]:
                row[label]=row[target]-row['R_stable'];row[label+'_ci_lo'],row[label+'_ci_hi']=ci(draws[target]-draws['R_stable'])
            if d in taxi:
                tn=taxi[d].to_numpy(float);tb=taxi[refs(d,B_TAXI)].mean(axis=1).to_numpy(float)
                tdraw=(taxi_weights@tn)/(taxi_weights@tb)
                row['R_taxi_km']=ratio(tn,tb);row['R_taxi_km_ci_lo'],row['R_taxi_km_ci_hi']=ci(tdraw)
                row['delta_taxi']=row['R_taxi_km']-row['R_stable']
                diff=tdraw[:,None]-draws['R_stable'][None,:]
                row['delta_taxi_ci_lo'],row['delta_taxi_ci_hi']=ci(diff.ravel());row['independent_product_pairs']=N_BOOT*N_TAXI_BOOT
            else:
                for c in ['R_taxi_km','R_taxi_km_ci_lo','R_taxi_km_ci_hi','delta_taxi','delta_taxi_ci_lo','delta_taxi_ci_hi']:row[c]=np.nan
                row['independent_product_pairs']=0
            row['delta_CI_method']='paired A100 device cluster; taxi independent empirical product distribution'
            rows.append(row)
        self.visible_frame=self.save(pd.DataFrame(rows),self.out,'m5_visible_bias_v3.csv')
        original=self.read('06_m5_bias_correction/m5_visible_bias.csv').set_index('date');computed=self.visible_frame.set_index('date')
        for col in ['R_naive','R_online','R_stable','R_taxi_km','delta_naive','delta_online','delta_taxi']:
            tolerance=.000151 if col.startswith('delta_') else .000051
            if not np.allclose(computed[col],original[col].reindex(EVENT),atol=tolerance,rtol=0,equal_nan=True):raise AssertionError('Visible bias point estimates changed beyond four-decimal subtraction tolerance')
        self.checks['visible_point_estimates_same_as_v1']=True
        self.notes.append(dict(item='Delta computation precision',implementation='v3 differences are computed from unrounded panel ratios. V1 differences subtracted already four-decimal R values; up to .00015 comparison tolerance permits only serialization differences, and the last decimal may change.',definition_changed=False))
        self.checks['paired_CIs_9_dates']=len(rows)==9
        self.notes.append(dict(item='delta taxi independent interval',implementation=RULES['paired_CI'],n_second_batch_vehicles=len(taxi),n_pair_products=100000))
    def unchanged_copies(self):
        paths=sorted((INPUTROOT/'06_m5_bias_correction').glob('m5_leaveout*.csv'))
        paths.append(INPUTROOT/'06_m5_bias_correction/m5_correction_methods.csv')
        copied=[]
        for source in paths:
            self.register(str(source.relative_to(INPUTROOT)).replace('\\','/'))
            destination=self.out/source.name
            shutil.copyfile(source,destination)
            left=hashlib.sha256(source.read_bytes()).hexdigest();right=hashlib.sha256(destination.read_bytes()).hexdigest()
            if left!=right:raise AssertionError('Unchanged result copy differs')
            copied.append(dict(input=str(source.relative_to(INPUTROOT)).replace('\\','/'),output=str(destination.relative_to(ROOT)).replace('\\','/'),source='formal_v1',identical=True,sha256=right))
            self.outputs.append(dict(file=str(destination.relative_to(ROOT)).replace('\\','/'),rows=None,source='formal_v1 byte copy'))
        write_json(ROOT/'00_env/m5_unchanged_copies_v3.json',dict(copies=copied,disclosure=RULES['unchanged_correction_copy']))
        self.checks['unchanged_copies_byte_identical']=True
    def verdict(self):
        sig=self.signature.set_index('date');v=self.visible_frame.set_index('date');storm=sig.loc['2021-07-26']
        features={}
        for d in ['2021-07-26']+PLATFORM:
            s=sig.loc[d]
            features[d]=dict(high_flow_positive_significant=bool(s.mean_log_base_diff>0 and s.mean_log_base_diff_p<.05),
                core_distance_negative=bool(s.mean_dist_baiguan_diff<0),Q4_share_difference_ge015=bool(s.Q4_share_diff>=.15))
        unique={name:features['2021-07-26'][name] and all(not features[d][name] for d in PLATFORM) for name in features['2021-07-26']}
        c1=bool(storm.joincount_knn6_p<.05 and storm.mean_log_base_diff_p<.05)
        stop=bool(storm.joincount_knn6_p>.05 and storm.mean_log_base_diff_p>.05)
        c2=sum(unique.values())>=2
        nozero=lambda lo,hi:pd.notna(lo) and pd.notna(hi) and (lo>0 or hi<0)
        c3=bool(v.loc['2021-07-26','delta_naive']<=-.10 and nozero(v.loc['2021-07-26','delta_naive_ci_lo'],v.loc['2021-07-26','delta_naive_ci_hi']) and nozero(v.loc['2021-08-02','delta_naive_ci_lo'],v.loc['2021-08-02','delta_naive_ci_hi']))
        leaveout=[];averages=[]
        for masking,suffix in [('random',''),('flowweighted','_flowweighted')]:
            x=self.read('06_m5_bias_correction/m5_leaveout_validation'+suffix+'.csv').set_index(['date','method'])
            for d in days('2021-07-26','2021-07-30'):
                drop=float(x.loc[(d,'drop'),'bias_mean']);zero=float(x.loc[(d,'naive_zero'),'bias_mean'])
                leaveout.append(dict(masking=masking,date=d,drop_bias=drop,naive_zero_bias=zero,drop_abs_bias_lt002=abs(drop)<.02,
                    zero_abs_bias_gt5x_drop=abs(zero)>5*abs(drop),ratio_abs_zero_to_drop=abs(zero)/abs(drop) if drop else None))
            for method in ['drop','naive_zero','knn','stratum']:
                z=x.xs(method,level='method');averages.append(dict(masking=masking,method=method,bias_mean_over_dates=float(z.bias_mean.mean()),mae_mean_over_dates=float(z.mae.mean())))
        c4=all(r['drop_abs_bias_lt002'] and r['zero_abs_bias_gt5x_drop'] for r in leaveout)
        criteria=[dict(id=1,criterion='July26 A1 spatial clustering and high baseline flow',threshold='joincount p<.05 AND mean_log_base_diff p<.05',
            observed=dict(joincount_p=float(storm.joincount_knn6_p),mean_log_base_diff=float(storm.mean_log_base_diff),mean_log_base_diff_p=float(storm.mean_log_base_diff_p)),met=c1),
            dict(id=2,criterion='Storm-unique signature relative to BOTH platform dates',threshold='at least2 of3 features storm-present/control-absent',
                observed=dict(features_by_date=features,unique_features=unique,n_storm_unique=sum(unique.values()),signature_table='07_m6_robustness/m6_signature_comparison_v3.csv'),met=c2),
            dict(id=3,criterion='Paired naive-minus-stable difference',threshold='July26 delta<=-.10 and CI excludes0; August2 CI excludes0',
                observed={d:dict(estimate=float(v.loc[d,'delta_naive']),lo=float(v.loc[d,'delta_naive_ci_lo']),hi=float(v.loc[d,'delta_naive_ci_hi'])) for d in ['2021-07-26','2021-08-02']},met=c3),
            dict(id=4,criterion='Drop and zero leaveout bias at every prespecified date/masking',threshold='all10 cells |drop bias|<.02 AND |zero bias|>5*|drop bias|',
                observed=dict(per_date_masking=leaveout,all_dates_average_descriptive_only=averages),met=c4),
            dict(id=5,criterion='Report imputation comparison; does not affect verdict',threshold='not a verdict gate',observed=averages,met=True)]
        status='supported' if all([c1,c2,c3,c4]) else 'partial' if c1 and c3 else 'not_supported'
        if stop:status='not_supported'
        v2=json.loads(self.register('06_m5_bias_correction/m5_h4_verdict.json').read_text(encoding='utf-8'))
        report=dict(H4=status,status=status,seed=SEED,criteria=criteria,stop_condition_triggered=stop,
            v2_stop_condition_triggered=bool(v2['stop_condition_triggered']),
            stop_condition_rule='A1 July26 join-count raw p>.05 AND baseline-flow raw p>.05; v2 rule retained on amended A1 set',
            frozen_rules_file='00_env/m5_A1_criteria_frozen_v3.json',criterion4_interpretation=RULES['leaveout_criterion4'],
            signature_rule=RULES['signature_unique'],interpretation='Association and within-Sstar leaveout; stable-set reference is not unobserved citywide truth.',
            expectation_checks={d:dict(n_failed_A1=int(self.counts_frame.set_index('date').loc[d,'n_failed_A1']),expected_range=bound,
                met=bound[0]<=int(self.counts_frame.set_index('date').loc[d,'n_failed_A1'])<=bound[1]) for d,bound in [('2021-07-27',[57,87]),('2021-07-28',[43,79]),('2021-08-02',[17,57])]},
            formal_v1_H4=v2['H4'],copy_disclosure=RULES['unchanged_correction_copy'])
        self.verdict_report=report;write_json(self.out/'m5_h4_verdict_v3.json',report)
        self.save(pd.DataFrame(leaveout),self.out,'m5_leaveout_criterion4_v3.csv')
        self.notes.append(dict(item='H4 strict per-date leaveout interpretation',rule=RULES['leaveout_criterion4'],failed_cells=[r for r in leaveout if not (r['drop_abs_bias_lt002'] and r['zero_abs_bias_gt5x_drop'])]))
    def plot(self):
        from common_v3 import setup_plot
        plt=setup_plot();fig,axes=plt.subplots(2,2,figsize=(13,9));figdata=[]
        v=self.visible_frame;x=pd.to_datetime(v.date)
        for label,color in [('naive','#2a78d6'),('online','#1baf7a'),('taxi','#eb6834')]:
            field='delta_'+label;axes[0,0].plot(x,v[field],marker='o',label=label,color=color)
            axes[0,0].fill_between(x,v[field+'_ci_lo'],v[field+'_ci_hi'],color=color,alpha=.14)
        axes[0,0].axhline(0,color='#888',linewidth=.8);axes[0,0].set_ylabel('Difference from stable-device reference');axes[0,0].legend();axes[0,0].set_title('(a) Paired recovery differences')
        part=v.copy();part['panel']='a';figdata.append(part)
        groups=['failed_lt005_nonSstar','degraded_005_050_nonSstar','online_nonSstar','Sstar'];colors=['#2a78d6','#eb6834','#1baf7a','#eda100']
        dates=EVENT;pos=np.zeros(9);neg=np.zeros(9)
        for group,color in zip(groups,colors):
            z=self.decomp[self.decomp.group.eq(group)].set_index('date').reindex(dates);y=z.contribution.to_numpy()
            bottom=np.where(y>=0,pos,neg);axes[0,1].bar(np.arange(9),y,bottom=bottom,label={'failed_lt005_nonSstar':'<5% A1, outside S*','degraded_005_050_nonSstar':'5–50% A1, outside S*','online_nonSstar':'Other outside S*','Sstar':'S*'}[group],color=color)
            pos+=np.maximum(y,0);neg+=np.minimum(y,0)
        axes[0,1].set_xticks(np.arange(9),[d[5:] for d in dates],rotation=45);axes[0,1].axhline(0,color='#888',linewidth=.8);axes[0,1].set_ylabel('Contribution to naive minus stable');axes[0,1].set_title('(b) Exclusive baseline-flow decomposition');axes[0,1].legend(fontsize=8)
        part=self.decomp.copy();part['panel']='b';figdata.append(part)
        curve=self.survival
        axes[1,0].step(curve.days_since_first_failure,curve.survival_not_first_recovered,where='post',color='#2a78d6',label='First recovery ≥50% A1 denominator')
        axes[1,0].set_ylim(0,1.03);axes[1,0].set_xlabel('Days since first failure');axes[1,0].set_ylabel('Not yet first recovered');axes[1,0].set_title('(c) A1 failure persistence');axes[1,0].legend(loc='lower left',fontsize=8)
        axes[1,0].text(.97,.95,f"Not first recovered by Aug 2: {self.persistence_report['not_recovered_by_0802']}/{self.persistence_report['n_A200']} A200",transform=axes[1,0].transAxes,ha='right',va='top',fontsize=9)
        part=curve.copy();part['panel']='c';figdata.append(part)
        box=[];labels=[];allrows=[]
        for masking,suffix in [('random',''),('flowweighted','_flowweighted')]:
            z=self.read('06_m5_bias_correction/m5_leaveout_validation'+suffix+'.csv');z['masking']=masking;allrows.append(z)
            for method in ['naive_zero','drop','knn','stratum']:
                box.append(z.loc[z.method.eq(method),'bias_mean']);labels.append(('random' if masking=='random' else 'weighted')+'\n'+('zero' if method=='naive_zero' else method))
        bx=axes[1,1].boxplot(box,labels=labels,showfliers=True,patch_artist=True,medianprops={'color':'#333333'})
        for patch,color in zip(bx['boxes'],colors*2):patch.set_facecolor(color);patch.set_alpha(.4)
        axes[1,1].axhline(0,color='#888',linewidth=.8);axes[1,1].set_ylabel('Signed mean leaveout error');axes[1,1].set_title('(d) Leaveout bias: five date means per box');axes[1,1].tick_params(axis='x',labelsize=8)
        part=pd.concat(allrows,ignore_index=True);part['panel']='d';figdata.append(part)
        for ax in axes.ravel():ax.grid(axis='y',alpha=.25)
        axes[0,0].tick_params(axis='x',rotation=45)
        fig.text(.5,.008,'S* reference and leaveout are within the observed network. A1 groups use S* priority; original imputation and leaveout results are copied from formal_v1.',ha='center',fontsize=8)
        fig.tight_layout(rect=[0,.035,1,1]);fig.savefig(self.fig/'fig6_bias_correction_v3.png',dpi=180);plt.close(fig)
        self.outputs.append(dict(file='08_figures/fig6_bias_correction_v3.png',rows=None))
        self.save(pd.concat(figdata,ignore_index=True),self.fig,'fig6_bias_correction_v3_data.csv')
    def run(self):
        t=time.monotonic();frozen=freeze();ruleshash=hashlib.sha256(frozen.read_bytes()).hexdigest()
        self.load();self.counts_frame=self.counts();self.ordinary(self.counts_frame);self.tests();self.persistence();self.decomposition();self.visible();self.unchanged_copies();self.verdict();self.plot()
        for rel,before in self.inputs.items():
            stat=(INPUTROOT/rel).stat()
            self.checks['input_unchanged:'+rel]=before==dict(size=stat.st_size,mtime_ns=stat.st_mtime_ns)
        self.checks['frozen_rules_unchanged']=ruleshash==hashlib.sha256(frozen.read_bytes()).hexdigest()
        failures=[name for name,val in self.checks.items() if isinstance(val,(bool,np.bool_)) and not val]
        execution=dict(seed=SEED,script='scripts/m5_bias_v3.py',command=_release_path('path_015'),
            started=self.started,ended=stamp(),seconds=time.monotonic()-t,status='complete' if not failures else 'failed',outputs=self.outputs,
            input_source='formal_v1 existing local panels/results only; no raw sources/key/panel copies',inputs=self.inputs,checks=self.checks,
            H4=self.verdict_report['status'],criteria_frozen_before_run=True,criteria_sha256=ruleshash)
        write_json(ROOT/'00_env/m5_execution_v3.json',execution);write_json(ROOT/'00_env/m5_method_interpretations_v3.json',dict(rules=RULES,notes=self.notes))
        print(json.dumps(dict(M5_v3=execution['status'],H4=self.verdict_report['status'],n_outputs=len(self.outputs),seconds=round(execution['seconds'],2),failures=failures)),flush=True)
        if failures:raise AssertionError('M5 v3 integrity self-check failed')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--freeze-only',action='store_true');parser.add_argument('--plot-only',action='store_true');args=parser.parse_args()
    if args.freeze_only:print('Frozen M5 rules',freeze())
    elif args.plot_only:
        t=time.monotonic();started=stamp();freeze();r=Run();r.visible_frame=pd.read_csv(r.out/'m5_visible_bias_v3.csv');r.decomp=pd.read_csv(r.out/'m5_bias_decomposition_v3.csv');r.survival=pd.read_csv(r.out/'m5_failure_persistence_curve_v3.csv');r.persistence_report=json.loads((r.out/'m5_failure_persistence_summary_v3.json').read_text(encoding='utf-8'));r.plot()
        write_json(ROOT/'00_env/m5_plot_execution_v3.json',dict(status='complete',started=started,ended=stamp(),seconds=time.monotonic()-t,seed=SEED,
            command=_release_path('path_016'),
            inputs='Completed v3 aggregate tables and unchanged v1 leaveout validation tables only; no panel, source or key reads',
            numerical_recalculation=False,outputs=r.outputs))
        print('Figure6 v3 layout refreshed; numerical products unchanged')
    else:Run().run()
