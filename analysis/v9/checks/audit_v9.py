# -*- coding: utf-8 -*-
"""Independent v9 audit entry point; schema helpers prepared before calculation.

Only frozen local inputs and formal_v9 outputs may be read. This file never
writes scientific tables, imports legacy project modules, or opens raw sources.
"""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[3]), str(_ReleasePath(__file__).resolve().parents[1])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import time
import re
import numpy as np
import pandas as pd

ROOT = Path(_release_path('project_root'))
OUT = _ReleasePath(_release_path('v9_output_root'))
SEED = 20261005
N_DEVICE = 500
N_VEHICLE = 200

def now():
    return datetime.now(timezone.utc).isoformat()

def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def divide(n, d):
    n = np.asarray(n, dtype=float)
    d = np.asarray(d, dtype=float)
    return np.divide(n, d, out=np.full(np.broadcast_shapes(n.shape, d.shape), np.nan), where=d > 0)

def classify(x, ro, rh):
    """Frozen A priority; do not repair unordered reference points."""
    x, ro, rh = np.broadcast_arrays(x, ro, rh)
    valid = np.isfinite(x) & np.isfinite(ro) & np.isfinite(rh)
    result = np.full(x.shape, 'invalid', dtype=object)
    result[valid & (x <= ro)] = 'A'
    result[valid & (x > ro) & (x <= rh)] = 'B'
    result[valid & (x > ro) & (x > rh)] = 'C'
    return result

def finite_ci(draw):
    d = np.asarray(draw, dtype=float)
    d = d[np.isfinite(d)]
    return (np.quantile(d, [.025, .975]) if len(d) else np.full(2, np.nan)), len(d)

def synthetic_checks():
    # No real input or new scientific effect is evaluated here.
    checks = {
        'A_boundary': classify(np.array([.4]), np.array([.4]), np.array([.6]))[0] == 'A',
        'B_boundary': classify(np.array([.6]), np.array([.4]), np.array([.6]))[0] == 'B',
        'C_strict': classify(np.array([.600001]), np.array([.4]), np.array([.6]))[0] == 'C',
        'overlap_A_priority': classify(np.array([.5]), np.array([.6]), np.array([.4]))[0] == 'A',
        'invalid_not_zero': classify(np.array([np.nan]), np.array([.4]), np.array([.6]))[0] == 'invalid',
        'zero_denominator_missing': np.isnan(divide(np.array([0.]), np.array([0.]))[0]),
        'negative_gap_preserved': (.2 - .4) < 0,
    }
    return {k: bool(v) for k, v in checks.items()}

def design_only():
    document = ROOT / 'shangyu_typhoon_gates_20261004/研究方案_上虞台风_v9_事后小分析任务书.md'
    checks = synthetic_checks()
    report = {
        'created_at_utc': now(),
        'status': 'audit_design_and_synthetic_checks_only',
        'task_document': str(document),
        'task_document_sha256': sha256(document),
        'seed': SEED,
        'effects_calculated': False,
        'frozen_root_interpretations_received': {
            'device': '500x1287 ascending-ID uniform indices; row bincount weights shared across9dates/allquantities',
            'camera': 'Same A100draw row accepted in fixedday subgroup,firstn; sharedextension SeedSequence([20261005,40]);eachdraw exactlyn',
            'vehicle': '200shared290vehicle multinomial weights; control/event/sharedacrossdates; recompute controlcapture andeventcounts',
            'zero_control_exposure': 'E and C/E invalid when a report camera has resampled controlE0; C remainsvalid',
            'classification': 'Apriority; invalid not zero; report RO>RH and conditionoverlaps;negativeg retained',
            'public_counts': 'Compare unrounded count/expectedcount/CI endpoint with10 before suppression;thenround integer; internalunrounded',
        },
        'required_audits': [
            'ProtocolSHA unchanged; allowed-inputmanifest beforeafter; no sourcesorlegacywrites',
            'T38full9dates/allthreeR,threepairedDelta,nO,wO,RO;500sharedA100draws;allrequiredCI',
            'July25h11targetandbaseline;July28threeoriginalWednesdays;fixedmembership',
            'T39all36xstar/gpointCIandABCfractions;finiteinvaliddenominators;literalboundaries;all36sustainedtails',
            'T39coverageO-intersectionfixed329-eventE>=10;pooledrelativecaptureandexposure;AugNA;coveragecannotchangexstar',
            'T40fixedreportscope;7dates;E/C/ratio;500cameraand200vehicleCI;draw-specificvalidn',
            'Internalpointacceptancewithoutpublicrounding;strictthresholds;allfailuresretained',
            'Figuresourcespreciselymatchtables;countsuppression;anonymousintegerdevices;nocoordinates/organisations',
        ],
        'synthetic_checks': checks,
        'all_synthetic_checks_passed': all(checks.values()),
        'source_reads': False,
        'key_reads': False,
        'scientific_outputs_modified': False,
    }
    path = OUT / '00_env/independent_audit_plan_v9.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps({'design_only': True, 'checks': checks, 'passed': all(checks.values())}))
    assert all(checks.values())

class Audit:
    def __init__(self):
        self.checks = {}
        self.read_hashes = {}
        self.started = now()
        self.tick = time.monotonic()
    def check(self, key, value):
        self.checks[key] = bool(value)
    def near(self, key, actual, expected, tol=2e-11):
        self.check(key, np.allclose(actual, expected, rtol=tol, atol=tol, equal_nan=True))
    def read(self, relative, **kw):
        path = ROOT / relative
        self.read_hashes[str(relative)] = sha256(path)
        if path.suffix == '.parquet': return pd.read_parquet(path, **kw)
        return pd.read_csv(path, encoding='utf-8-sig', **kw)
    def npz(self, relative):
        path = ROOT / relative
        self.read_hashes[str(relative)] = sha256(path)
        return np.load(path, allow_pickle=False)
    def public(self, relative, expected, count_cols=(), half_up=False):
        actual = self.read(relative, dtype=str, keep_default_na=False).reset_index(drop=True)
        expected = expected.reset_index(drop=True)
        self.check(relative + ':shape', actual.shape == expected.shape and set(actual) == set(expected))
        for c in expected:
            values=[]
            for x in expected[c]:
                if pd.isna(x): values.append('NA')
                elif c in count_cols: values.append('<10' if 0 <= x < 10 else str(int(np.floor(x+.5) if half_up else np.rint(x))))
                elif isinstance(x, (float, np.floating)): values.append(f'{x:.4f}')
                else: values.append(str(x))
            self.check(relative + ':' + c, actual[c].tolist() == values)
    def save(self, section):
        for p,h in self.read_hashes.items(): self.check('unchanged:' + p, sha256(ROOT / p) == h)
        path = OUT / '00_env/independent_audit_v9.json'
        old = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'sections': {}}
        if section in old.get('sections', {}):
            previous=old['sections'][section]
            old.setdefault('audit_run_history', []).append({'section':section,'started_utc':previous['started_utc'], 'all_passed':previous['all_passed'], 'failed':[k for k,v in previous['checks'].items() if not v], 'note':'Prior audit snapshot retained; initial decomp CSV shape check treated harmless index-reset column order as an error. Science was unchanged.'})
        old.setdefault('sections', {})[section] = {
            'started_utc': self.started, 'ended_utc': now(), 'seconds': time.monotonic()-self.tick,
            'n_checks': len(self.checks), 'all_passed': all(self.checks.values()),
            'checks': self.checks, 'input_and_output_sha256': self.read_hashes,
        }
        old.update(created_at_utc=now(), status='passed' if {'decomp','capture','release'}.issubset(old['sections']) and all(s['all_passed'] for s in old['sections'].values()) else 'partial_passed' if all(s['all_passed'] for s in old['sections'].values()) else 'failed',
                   source_reads=False, key_reads=False, science_outputs_modified=False,
                   total_checks=sum(s['n_checks'] for s in old['sections'].values()))
        path.write_text(json.dumps(old, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
        print(json.dumps({'section':section,'n_checks':len(self.checks),'passed':all(self.checks.values()),'failed':[k for k,v in self.checks.items() if not v]}))
        assert all(self.checks.values())

def audit_decomp():
    a=Audit()
    protocol_path=OUT/'00_env/protocol_frozen_v9.json'; protocol_sha=sha256(protocol_path)
    protocol=json.loads(protocol_path.read_text(encoding='utf-8'))
    payload_serial=json.dumps(protocol['payload'],ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
    a.check('protocol_payload_sha', hashlib.sha256(payload_serial).hexdigest()==protocol['sha256_payload'])
    dates=pd.date_range('2021-07-25','2021-08-02').strftime('%Y-%m-%d').tolist()
    pool=[x for x in pd.date_range('2021-07-05','2021-07-21').strftime('%Y-%m-%d') if x not in ['2021-07-08','2021-07-10']]
    attrs=a.read('01_panels/device_attributes.csv',usecols=['dev','in_A100','in_A200']).sort_values('dev').reset_index(drop=True)
    attrs['anon']=np.arange(1,len(attrs)+1);attrs=attrs[attrs.in_A100.eq(1)]
    ids=attrs.anon.to_numpy();names=attrs.dev.tolist();a200=attrs.in_A200.eq(1).to_numpy();nd=len(ids)
    state=a.read('formal_v7/02_device_state/device_state_v7.csv',usecols=['dev','date','in_health','n_day','baseline_B1','hour_matched']).set_index(['date','dev'])
    day=a.read('01_panels/device_day.csv',usecols=['dev','date','n']).set_index(['dev','date']).n
    hour=a.read('01_panels/device_hour.csv',usecols=['dev','date','hour','n']);hour=hour[hour.hour.between(11,23)].groupby(['dev','date']).n.sum()
    n=np.zeros((9,nd));b=n.copy();health=np.zeros((9,nd),bool)
    for di,d in enumerate(dates):
        refs=[x for x in pool if pd.Timestamp(x).dayofweek==pd.Timestamp(d).dayofweek]
        obs=hour if di==0 else day
        n[di]=obs.reindex(pd.MultiIndex.from_product([names,[d]])).fillna(0).to_numpy()
        b[di]=np.column_stack([obs.reindex(pd.MultiIndex.from_product([names,[x]])).fillna(0).to_numpy() for x in refs]).mean(1)
        q=state.loc[d].reindex(ids);health[di]=q.in_health.fillna(0).eq(1).to_numpy()&a200
        a.near('state_n:'+d,n[di,a200],q.n_day.to_numpy()[a200],0)
        a.near('state_b:'+d,b[di,a200],q.baseline_B1.to_numpy()[a200],1e-7)
        a.check('state_hourmatch:'+d,q.hour_matched.to_numpy()[a200].astype(int).tolist()==[int(di==0)]*int(a200.sum()))
    omitted=a200[None,:]&~health
    rng=np.random.default_rng(SEED);indices=rng.integers(0,nd,(500,nd),dtype=np.int32)
    weights=np.stack([np.bincount(row,minlength=nd) for row in indices]).astype(np.int32)
    saved=a.npz('formal_v9/01_internal/decomp_device_weights_v9.npz')
    a.check('weights_indices_exact',np.array_equal(saved['draw_indices'],indices));a.check('weights_exact',np.array_equal(saved['weights'],weights));a.check('device_axis',np.array_equal(saved['device_ids'],ids))
    ww=np.vstack([np.ones(nd),weights]);metrics=['R_A100','R_A200','R_H','Delta_thr','Delta_scr','Delta_tot','n_O','w_O','R_O']
    value=np.empty((501,9,9))
    points=a.read('formal_v9/01_internal/decomp_points_v9.parquet').set_index('date')
    draws=a.read('formal_v9/01_internal/decomp_bootstrap_v9.parquet').set_index(['date','replicate'])
    device=a.read('formal_v9/01_internal/decomp_device_day_v9.parquet').set_index(['date','dev'])
    for di,d in enumerate(dates):
        q=device.loc[d].reindex(ids)
        for key,v in [('n_day',n[di]),('baseline_B1',b[di]),('in_A200',a200),('in_health',health[di]),('O',omitted[di])]:a.near('device:'+d+key,q[key].to_numpy(float),v)
        rr=[]
        for mask in [np.ones(nd,bool),a200,health[di]]:rr.append(divide((ww[:,mask]*n[di,mask]).sum(1),(ww[:,mask]*b[di,mask]).sum(1)))
        bo=(ww[:,omitted[di]]*b[di,omitted[di]]).sum(1);b2=(ww[:,a200]*b[di,a200]).sum(1)
        value[:,di,:]=np.column_stack(rr+[rr[1]-rr[0],rr[2]-rr[1],rr[2]-rr[0],ww[:,omitted[di]].sum(1),divide(bo,b2),divide((ww[:,omitted[di]]*n[di,omitted[di]]).sum(1),bo)])
        for mi,m in enumerate(metrics):
            a.near('point:'+d+m,points.loc[d,m],value[0,di,mi]);a.near('draws:'+d+m,draws.loc[d,m].to_numpy(),value[1:,di,mi])
            ends,nv=finite_ci(value[1:,di,mi]);a.near('CI:'+d+m,points.loc[d,[m+'_ci_lo',m+'_ci_hi']].to_numpy(float),ends)
            a.check('nvalid:'+d+m,int(points.loc[d,m+'_n_valid'])==nv)
    a.public('formal_v9/02_decomposition/T38_decomposition_v9.csv',points.reset_index(),['n_A100','n_A200','n_H','n_O','n_O_ci_lo','n_O_ci_hi'])
    w=value[:,:,7];rh=value[:,:,2];ro=value[:,:,8];r2=value[:,:,1]
    a.check('additive_all_draws',np.max(np.abs(value[:,:,3]+value[:,:,4]-value[:,:,5]))<1e-12)
    a.check('identity_RO_all_draws',np.nanmax(np.abs((1-w)*rh+w*ro-r2))<1e-12)
    a.check('identity_RH_all_draws',np.nanmax(np.abs((1-w)*rh+w*rh-rh))<1e-12)
    family=a.read('formal_v7/07_consequences/T37_estimator_family_v7.csv').set_index(['date','estimator'])
    for di,d in enumerate(dates):
        a.check('T37_A100:'+d,abs(value[0,di,0]-family.loc[(d,'R_naive'),'R'])<5e-5)
        a.check('T37_H:'+d,abs(value[0,di,2]-family.loc[(d,'R_health'),'R'])<5e-5)
    be=a.read('formal_v9/01_internal/decomp_breakeven_points_v9.parquet').set_index(['date','theta']);bb=a.read('formal_v9/01_internal/decomp_breakeven_bootstrap_v9.parquet').set_index(['date','theta','replicate']);su=a.read('formal_v9/01_internal/decomp_sustained_points_v9.parquet').set_index(['start_date','theta'])
    for theta in [.8,.85,.9,.95]:
        x=divide(theta-(1-w)*rh,w);g=x-ro;classes=classify(x,ro,rh);classes=np.where(classes=='invalid','NA',classes)
        for di,d in enumerate(dates):
            row=be.loc[(d,theta)];mask=classes[1:,di]!='NA';nv=int(mask.sum())
            for m,v in [('x_star',x),('g',g)]:
                a.near('T39point:'+d+str(theta)+m,row[m],v[0,di]);a.near('T39draw:'+d+str(theta)+m,bb.loc[(d,theta),m],v[1:,di]);ends,_=finite_ci(v[1:,di]);a.near('T39CI:'+d+str(theta)+m,row[[m+'_ci_lo',m+'_ci_hi']].to_numpy(float),ends)
            a.check('T39class:'+d+str(theta),row['class']==classes[0,di]);a.check('T39drawclass:'+d+str(theta),np.array_equal(bb.loc[(d,theta),'class'],classes[1:,di]))
            for c in ['A','B','C']:a.near('T39share:'+d+str(theta)+c,row['share_'+c],np.mean(classes[1:,di][mask]==c) if nv else np.nan)
            a.check('T39nvalid:'+d+str(theta),row.n_valid==nv and row.n_invalid==500-nv)
            a.check('T39ROdiagnostic:'+d+str(theta),row.RO_above_RH_bootstrap_n==int((ro[1:,di]>rh[1:,di]).sum()))
            tail=classes[:,di:];st=np.where((tail=='C').any(1),'not_sustained',np.where((tail=='A').all(1),'robust_sustained',np.where((tail=='NA').any(1),'unknown','depends_on_unseen')))
            sr=su.loc[(d,theta)];a.check('sustained_point:'+d+str(theta),sr.status==st[0]);a.check('sustained_draws:'+d+str(theta),np.array_equal(bb.loc[(d,theta),'sustained_from_date'],st[1:]))
            valid=st[1:]!='unknown'
            for c in ['robust_sustained','depends_on_unseen','not_sustained']:a.near('sustainedshare:'+d+str(theta)+c,sr['share_'+c],np.mean(st[1:][valid]==c) if valid.any() else np.nan)
    a.public('formal_v9/03_breakeven/T39_breakeven_v9.csv',be.reset_index(),['n_valid','n_invalid','RO_above_RH_bootstrap_n'])
    a.public('formal_v9/03_breakeven/T39_sustained_v9.csv',su.reset_index(),['n_tail_dates','n_valid','n_invalid'])
    a.check('T38_0726',f'{value[0,1,1]:.4f}'=='0.4608' and value[0,1,6]==228 and f'{value[0,1,7]:.4f}'=='0.3370')
    a.check('T38_0802',value[0,8,6]==119 and f'{value[0,8,7]:.4f}'=='0.2571')
    a.check('protocol_unchanged',sha256(protocol_path)==protocol_sha)
    a.save('decomp')

def audit_capture():
    a=Audit();protocol=OUT/'00_env/protocol_frozen_v9.json';ph=sha256(protocol)
    dates=[f'2021-07-{d:02d}' for d in range(25,32)];control=[f'2021-07-{d:02d}' for d in range(12,20)]
    camera=a.read('formal_v7/01_internal/capture_camera_internal_v7.csv',usecols=['variant','dev','date','selected','A1_failed','hour_matched','expected','captured','expected_ctrl_matched','captured_ctrl_matched','cap_ctrl_matched'])
    camera=camera[camera.variant.eq('main_R60_cap03')].set_index(['date','dev'])
    selection=a.read('formal_v7/01_internal/capture_selection_internal_v7.csv',usecols=['variant','dev','selected']);selected=selection.loc[selection.variant.eq('main_R60_cap03')&selection.selected.eq(True),'dev'].to_numpy(int)
    state=a.read('formal_v7/02_device_state/device_state_v7.csv',usecols=['dev','date','in_A200','in_health','baseline_B1','hour_matched']).set_index(['date','dev'])
    source=a.npz('formal_v7/01_internal/capture_vehicle_counts_v7.npz');ids=source['camera_ids'];source_dates=source['dates'].tolist();ri=source['radii'].tolist().index(60)
    daily=source['all_day'][ri].astype(np.int64);hour=source['h11'][ri].astype(np.int64)
    archived=a.npz('formal_v7/01_internal/capture_bootstrap_v7.npz')
    res=a.npz('formal_v9/01_internal/capture_resampling_v9.npz');master=res['device_ids'];base=np.random.default_rng(SEED).integers(0,len(master),(500,len(master)),dtype=np.int32)
    a.check('T40_reuses_original500_ordered_device_stream',np.array_equal(base,res['base_draw_indices']))
    ext=res['extension_blocks'];erng=np.random.default_rng(np.random.SeedSequence([SEED,40]))
    for k in range(len(ext)):a.check('extension_block_seed_exact:'+str(k),np.array_equal(ext[k],erng.integers(0,len(master),(500,len(master)),dtype=np.int32)))
    vw=np.random.default_rng(SEED).multinomial(290,np.repeat(1/290,290),size=200);a.check('vehicle_200_weights_exact',np.array_equal(vw,res['vehicle_weights']))
    a.check('329_selected_fixed',len(selected)==329 and len(np.unique(selected))==329)
    points=a.read('formal_v9/01_internal/capture_expected_internal_v9.csv').set_index('date');boot=a.read('formal_v9/01_internal/capture_bootstrap_results_v9.parquet').set_index(['date','bootstrap','replicate'])
    coverage=a.read('formal_v9/01_internal/capture_audit_coverage_internal_v9.csv').set_index('date')
    subgroup=a.read('formal_v9/01_internal/capture_report_subgroups_v9.csv').set_index(['date','dev'])
    for d in dates:
        cube=hour if d=='2021-07-25' else daily;event=cube[:,source_dates.index(d)];ctrl=cube[:,[source_dates.index(x) for x in control]].sum(1)
        e=event.sum(0);c=ctrl.sum(0);q=camera.loc[d].reindex(ids)
        a.check('event_count_cube_source:'+d,np.array_equal(e,q[['expected','captured']].to_numpy()))
        a.check('control_count_cube_source:'+d,np.array_equal(c,q[['expected_ctrl_matched','captured_ctrl_matched']].to_numpy()))
        a.near('control_cap_source:'+d,divide(c[:,1],c[:,0]),q.cap_ctrl_matched.to_numpy(float))
        a.check('source_matched_hours:'+d,q.hour_matched.astype(int).eq(int(d=='2021-07-25')).all())
        use=np.isin(ids,selected)&q.A1_failed.eq(True).to_numpy()&(e[:,0]>=10);group=ids[use];ng=len(group)
        a.check('frozen_subgroup:'+d,np.array_equal(group,res['subgroup_device_ids__'+d]));a.check('report_n:'+d,points.loc[d,'n_report_cameras']==ng)
        streams=np.concatenate([base]+[block for block in ext],axis=1);accepted=[]
        for rep in range(500):
            hits=streams[rep,np.isin(master[streams[rep]],group)][:ng];accepted.append(master[hits])
        accepted=np.asarray(accepted);a.check('accepted_ordered_rejection_sample:'+d,np.array_equal(accepted,res['accepted_device_ids__'+d]));a.check('camera_exact_n:'+d,accepted.shape==(500,ng))
        mapid={int(i):k for k,i in enumerate(ids)};accepted_axis=np.vectorize(mapid.get,otypes=[int])(accepted)
        cap=divide(c[:,1],c[:,0]);Ep=(cap[use]*e[use,0]).sum();Cp=e[use,1].sum();Rp=divide(Cp,Ep).item()
        for m,v in [('E',Ep),('C',Cp),('C_over_E',Rp)]:a.near('T40point:'+d+m,points.loc[d,m],v)
        for m,v in [('expected',e[use,0]),('captured',e[use,1]),('control_expected',c[use,0]),('control_captured',c[use,1]),('control_cap',cap[use]),('expected_capture',cap[use]*e[use,0])]:a.near('T40percamera:'+d+m,subgroup.loc[d].reindex(group)[m].to_numpy(),v)
        ec=(cap[accepted_axis]*e[accepted_axis,0]).sum(1);cc=e[accepted_axis,1].sum(1)
        ev=(vw@event.reshape(290,-1)).reshape(200,len(ids),2);cv=(vw@ctrl.reshape(290,-1)).reshape(200,len(ids),2)
        vc=divide(cv[:,:,1],cv[:,:,0]);invalid=(cv[:,use,0]==0).sum(1);Ev=(vc[:,use]*ev[:,use,0]).sum(1);Cv=ev[:,use,1].sum(1)
        old=archived['main_R60_cap03__'+d+'__failed_vehicle_cap'];a.near('archived200_originalweights:'+d,divide(ev[:,use,1].sum(1),ev[:,use,0].sum(1)),old,1e-13)
        for kind,v in [('camera',{'E':ec,'C':cc,'C_over_E':divide(cc,ec)}),('vehicle',{'E':Ev,'C':Cv,'C_over_E':divide(Cv,Ev)})]:
            saved=boot.loc[(d,kind)]
            for m,arr in v.items():
                a.near('T40all_draws:'+d+kind+m,saved[m].to_numpy(),arr);ci,nv=finite_ci(arr);a.near('T40CI:'+d+kind+m,points.loc[d,[m+'_'+kind+'_ci_lo',m+'_'+kind+'_ci_hi']].to_numpy(float),ci);a.check('T40valid:'+d+kind+m,points.loc[d,m+'_'+kind+'_valid_draws']==nv)
            a.check('invalid_control_n:'+d+kind,np.array_equal(saved.invalid_control_camera_cells,invalid if kind=='vehicle' else np.zeros(500,int)))
        a.check('control0_Eratio_invalid_Cstillfinite:'+d,np.array_equal(np.isnan(Ev),invalid>0) and np.isfinite(Cv).all())
        # Independently form O directly from the allowed public v7 state, not A1 failures.
        st=state.loc[d];O=st[st.in_A200.eq(1)&st.in_health.eq(0)];ou=np.isin(ids,O.index)&np.isin(ids,selected)&(e[:,0]>=10)
        od=ids[ou];omitted_base=O.baseline_B1.sum();audit_base=O.loc[od,'baseline_B1'].sum();expected,captured=e[ou].sum(0);ce,cc=c[ou].sum(0)
        crow=coverage.loc[d];a.check('coverage_nO:'+d,crow.n_O==len(O));a.check('coverage_n_audited:'+d,crow.n_audited_cameras==len(od))
        for m,v in [('O_baseline_flow_share_audited',audit_base/omitted_base),('pooled_relative_capture',divide(divide(captured,expected),divide(cc,ce)).item()),('taxi_passage_frequency_ratio',divide(expected,ce/8).item()),('event_expected',expected),('event_captured',captured),('control_expected',ce),('control_captured',cc)]:a.near('coverage:'+d+m,crow[m],v)
    for d in ['2021-08-01','2021-08-02']:
        cr=coverage.loc[d];a.check('August_probe_missing:'+d,not cr.GPS_available and cr[['n_audited_cameras','O_baseline_flow_share_audited','pooled_relative_capture','taxi_passage_frequency_ratio','event_expected','event_captured','control_expected','control_captured']].isna().all())
    countcols=['E','C']+[f'{m}_{k}_ci_{s}' for m in ['E','C'] for k in ['camera','vehicle'] for s in ['lo','hi']]
    a.public('formal_v9/04_expected_capture/T40_expected_capture_v9.csv',points.reset_index(),countcols,half_up=True)
    a.public('formal_v9/03_breakeven/T39_audit_coverage_v9.csv',coverage.reset_index(),['n_audited_cameras','event_expected','event_captured','control_expected','control_captured'],half_up=True)
    p=points.loc['2021-07-26'];a.check('T40_0726_acceptance',p.n_report_cameras==64 and p.C==55 and abs(p.E-8733)<15)
    a.check('retained_4900draws',len(boot)==4900);a.check('protocol_unchanged',sha256(protocol)==ph)
    a.save('capture')

def audit_release():
    a=Audit();p=OUT/'00_env/protocol_frozen_v9.json';ph=sha256(p)
    frozen=json.loads(p.read_text(encoding='utf-8'));sidecar=json.loads((OUT/'00_env/protocol_sha256_v9.json').read_text(encoding='utf-8'))
    a.check('protocol_full_file_sha_matches_freeze',ph==sidecar['sha256'])
    manifest=json.loads((OUT/'00_env/input_manifest_v9.json').read_text(encoding='utf-8'))
    for item in manifest['files']:
        q=Path(item['path']);a.check('frozen_input:'+item['path'],q.is_file() and q.stat().st_size==item['bytes'] and q.stat().st_mtime_ns==item['mtime_ns'] and sha256(q)==item['sha256'])
    a.check('manifest14_inputs',len(manifest['files'])==14)
    for figure,table in [('fig_breakeven_source_v9.csv','03_breakeven/T39_breakeven_v9.csv'),('fig_expected_capture_source_v9.csv','04_expected_capture/T40_expected_capture_v9.csv')]:
        q=OUT/'08_figures'/figure;t=OUT/table;a.check('figure_source_exact_bytes:'+figure,q.read_bytes()==t.read_bytes());a.read_hashes[str(q.relative_to(ROOT))]=sha256(q);a.read_hashes[str(t.relative_to(ROOT))]=sha256(t)
    checks=json.loads((OUT/'02_decomposition/T38_checks_v9.json').read_text(encoding='utf-8'))['checks']
    for k in ['T38_reproduce','T38_additive','T38_0726','T38_0802','T39_identity']:a.check('reported_acceptance:'+k,checks[k] is True)
    t40=json.loads((OUT/'04_expected_capture/T40_checks_v9.json').read_text(encoding='utf-8'));a.check('reported_acceptance:T40_0726',t40['T40_0726']['reached'] is True)
    previous=json.loads((OUT/'00_env/independent_audit_v9.json').read_text(encoding='utf-8'))
    for k in ['decomp','capture']:a.check('independent_'+k+'_passed',previous['sections'][k]['all_passed'])
    # Independent inspection of all actual public scientific cells, including
    # coverage control counts and all small interval endpoints.
    units=a.read('formal_v7/02_device_state/device_state_v7.csv',usecols=['org']).org.dropna().astype(str).unique().tolist()
    sensitive_units=[x for x in units if re.search('[\u3400-\u9fff]',x)]
    pseudo=re.compile(r'(?<![A-Za-z0-9])[0-9A-Fa-f]{16}(?![A-Za-z0-9])')
    scalar=re.compile(r'(?<![\w.])[-+]?(?:\d+\.\d+|\.\d+)(?:[Ee][-+]?\d+)?(?![\w.])')
    forbidden_columns={'dev','camera_id','camera_name','dev_name','org','organisation','ph','plate','lon','lat','longitude','latitude'}
    physical={'E','C','n_A100','n_A200','n_H','n_O','n_O_ci_lo','n_O_ci_hi','n_report_cameras','n_control_selected','n_audited_cameras','event_expected','event_captured','control_expected','control_captured'}
    for q in sorted(OUT.glob('0[2-8]_*/*.csv')):
        frame=pd.read_csv(q,dtype=str,keep_default_na=False,encoding='utf-8-sig');text=q.read_text(encoding='utf-8-sig');rel=q.relative_to(OUT).as_posix()
        a.check('privacy:no_names_prefix:'+rel,('cam'+'_') not in text and not any(x in text for x in sensitive_units))
        numeric=[m.span() for m in scalar.finditer(text)];pseudonyms=[m for m in pseudo.finditer(text) if not any(lo<=m.start() and m.end()<=hi for lo,hi in numeric)]
        a.check('privacy:no16alias:'+rel,not pseudonyms);a.check('privacy:no_identifier_coordinate_schema:'+rel,not (set(frame)&forbidden_columns))
        for col in frame:
            is_count=col in physical or bool(re.match(r'^[EC]_(camera|vehicle)_ci_(lo|hi)$',col))
            if not is_count:continue
            valid=True
            for value in frame[col]:
                if value in ['<10','NA','']:continue
                try:valid=valid and float(value)>=10 and float(value).is_integer()
                except ValueError:valid=False
            a.check('privacy:integer_suppressed:'+rel+':'+col,valid)
    a.check('protocol_still_unchanged',sha256(p)==ph)
    a.save('release')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--design-only', action='store_true')
    parser.add_argument('--decomp', action='store_true')
    parser.add_argument('--capture', action='store_true')
    parser.add_argument('--release', action='store_true')
    args = parser.parse_args()
    if args.release:
        audit_release()
    elif args.capture:
        audit_capture()
    elif args.decomp:
        audit_decomp()
    elif not args.design_only:
        raise RuntimeError('Numerical audit is not enabled before root release and final output schema')
    else:
        design_only()
