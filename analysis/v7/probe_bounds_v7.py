# -*- coding: utf-8 -*-
"""I2-prime relative probe and I5-prime product-bootstrap recovery.

Read only existing local v6 caches; append to inherited tables without changing
their old cells. Execution requires the root's frozen protocol and release.
"""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[2]), str(_ReleasePath(__file__).resolve().parents[0])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import time
import numpy as np
import pandas as pd

ROOT = Path(_release_path('v7_root'))
V6 = ROOT.parent / 'formal_v6'
SEED = 20261005
DATES = pd.date_range('2021-07-06', '2021-08-02').strftime('%Y-%m-%d').tolist()
EVENT = pd.date_range('2021-07-25', '2021-08-02').strftime('%Y-%m-%d').tolist()
GPS_EVENT = EVENT[:7]
B = [d for d in pd.date_range('2021-07-06', '2021-07-21').strftime('%Y-%m-%d')
     if d not in ['2021-07-08', '2021-07-10']]
INPUTS = [
    '01_internal/T28_probe_daily_internal_v6.csv',
    '03_taxi_probe/T28_probe_daily_v6.csv',
    '01_internal/taxi_probe_joined_v6.parquet',
    '01_internal/taxi_probe_ph_v6.txt',
    '01_internal/T31_recovery_bounds_internal_v6.csv',
    '05_bounds/T31_recovery_bounds_v6.csv',
    '01_internal/T31_device_scenarios_internal_v6.parquet',
    '01_internal/T31_bootstrap_internal_v6.parquet',
    '00_env/hash_check_v6.json',
    '00_env/probe_daily_execution_v6.json',
]


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def signature(path):
    s = path.stat()
    return dict(bytes=s.st_size, mtime_ns=s.st_mtime_ns, sha256=sha(path))


def safe(n, d):
    n, d = np.broadcast_arrays(np.asarray(n, float), np.asarray(d, float))
    return np.divide(n, d, out=np.full(n.shape, np.nan), where=np.isfinite(d) & (d > 0))


def ci(a):
    a = np.asarray(a, float)
    a = a[np.isfinite(a)]
    return np.quantile(a, [.025, .975]) if len(a) else (np.nan, np.nan)


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def json_safe(obj):
    if isinstance(obj, dict):
        return {str(k): json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [json_safe(v) for v in obj]
    if isinstance(obj, (np.bool_,)): return bool(obj)
    if isinstance(obj, (np.integer,)): return int(obj)
    if isinstance(obj, (float, np.floating)): return float(obj) if np.isfinite(obj) else None
    return obj


def save(frame, relative, internal=False):
    path = ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == '.parquet': frame.to_parquet(path, index=False)
    else: frame.to_csv(path, index=False, encoding='utf-8-sig', float_format='%.12g' if internal else '%.4f')


def append_public(source, new, relative):
    old = pd.read_csv(source, dtype=str, keep_default_na=False)
    new = new.set_index('date')
    assert old.date.is_unique and new.index.is_unique
    duplicate = set(old.columns) & set(new.columns)
    assert not duplicate, ('New columns overwrite old columns', duplicate)
    out = old.join(new, on='date')
    save(out, relative)
    reread = pd.read_csv(ROOT / relative, dtype=str, keep_default_na=False)
    assert reread[old.columns].equals(old), 'Inherited public cells changed'
    return out


def plots(daily, bounds):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family': 'sans-serif', 'font.size': 7,
                         'axes.titlesize': 8, 'pdf.fonttype': 42, 'ps.fonttype': 42,
                         'axes.spines.top': False, 'axes.spines.right': False})
    q = daily[daily.date.isin(GPS_EVENT)].copy()
    x = np.arange(len(q)); labels = [d[5:].replace('-', '/') for d in q.date]
    fig, axes = plt.subplots(2, 1, figsize=(7.0866, 4.3), sharex=True,
                             gridspec_kw={'height_ratios': [2, 1]}, constrained_layout=True)
    for c, label, color in [('q_probe', 'Fixed taxi probe', '#0072B2'), ('q_fleet', 'All-fleet naive / stable', '#D55E00')]:
        axes[0].plot(x, q[c], 'o-', label=label, color=color, ms=3, lw=1)
        axes[0].fill_between(x, q[c+'_ci_lo'], q[c+'_ci_hi'], color=color, alpha=.15, lw=0)
    axes[0].axhline(1, color='.6', lw=.6); axes[0].set_ylabel('Relative network ratio')
    axes[0].legend(frameon=False, loc='lower right'); axes[0].set_title('Relative probe intensity and all-fleet observation ratio')
    axes[1].plot(x, q.q_probe_minus_q_fleet, 'o-', ms=3, lw=1, color='#009E73')
    axes[1].vlines(x, q.q_probe_minus_q_fleet_ci_lo, q.q_probe_minus_q_fleet_ci_hi,
                   color='#009E73', lw=.8)
    axes[1].axhline(0, color='.6', lw=.6); axes[1].set_ylabel('Probe − all fleet')
    axes[1].set_xticks(x, labels); axes[1].set_xlabel('2021 date (July 25: matched 11–23 h)')
    for suffix in ['png', 'pdf']: fig.savefig(ROOT/'08_figures'/('fig_probe_relative_intensity_v7.'+suffix), dpi=300)
    plt.close(fig)
    z = bounds.copy(); xx = np.arange(len(z)); fig, ax = plt.subplots(figsize=(7.0866, 3.2), constrained_layout=True)
    colors = {'R_naive': '#D55E00', 'R_stable': '#0072B2', 'R_pre': '#CC79A7', 'R_probe': '#009E73'}
    for c, label in [('R_naive', 'Naive'), ('R_stable', 'Stable'), ('R_pre', 'Pre-event set'), ('R_probe', 'Probe-adjusted scenario')]:
        ax.plot(xx, z[c], 'o-', color=colors[c], label=label, ms=3, lw=1)
        if c == 'R_probe': ax.fill_between(xx, z.R_probe_ci_lo, z.R_probe_ci_hi, color=colors[c], alpha=.15, lw=0)
    ax.fill_between(xx, z.R_lower, z.R_upper, color='.5', alpha=.12, label='Copied lower–upper scenarios', lw=0)
    ax.axhline(.9, color='.6', lw=.6, ls='--'); ax.set_xticks(xx, [d[5:].replace('-', '/') for d in z.date])
    ax.set_ylabel('Baseline-normalised recovery'); ax.set_xlabel('2021 date (probe unavailable August 1–2)')
    ax.legend(frameon=False, ncol=3); ax.set_title('Recovery comparators and conditional probe correction')
    for suffix in ['png', 'pdf']: fig.savefig(ROOT/'08_figures'/('fig_probe_recovery_v7.'+suffix), dpi=300)
    plt.close(fig)


def run(protocol, release):
    start = time.perf_counter(); started = datetime.now(timezone.utc).isoformat()
    protocol = Path(protocol).resolve()
    assert release, 'Root release required after protocol freeze'
    assert protocol.is_file() and protocol.parent == (ROOT/'00_env').resolve(), 'Frozen protocol must exist in v7/00_env'
    frozen = json.loads(protocol.read_text(encoding='utf-8-sig'))
    protocol_signature = signature(protocol)
    interpretation = ROOT/'00_env/interpretation_probe_bounds_v7.json'
    interpretation_signature = signature(interpretation)
    assert frozen.get('frozen_at') and frozen.get('seed') == SEED
    assert frozen['interpretations'][interpretation.name] == json.loads(interpretation.read_text(encoding='utf-8-sig'))
    before = {rel: signature(V6/rel) for rel in INPUTS}
    h = json.loads((V6/'00_env/hash_check_v6.json').read_text(encoding='utf-8-sig'))
    assert h['n_probe'] == 290 and not h['S1_triggered']
    pub = pd.read_csv(V6/'03_taxi_probe/T28_probe_daily_v6.csv')
    old = pd.read_csv(V6/'01_internal/T28_probe_daily_internal_v6.csv')
    old_bounds = pd.read_csv(V6/'01_internal/T31_recovery_bounds_internal_v6.csv')
    bounds_pub = pd.read_csv(V6/'05_bounds/T31_recovery_bounds_v6.csv')
    joined = pd.read_parquet(V6/'01_internal/taxi_probe_joined_v6.parquet',
        columns=['ph', 'date', 'dist_km', 'km_from_11h', 'n', 'n_stable', 'rec_all_h11', 'rec_stable_h11'])
    aliases = (V6/'01_internal/taxi_probe_ph_v6.txt').read_text(encoding='utf-8').splitlines()
    assert len(aliases) == 290 and len(set(aliases)) == 290
    assert len(joined) == len(DATES)*290 and not joined.duplicated(['ph', 'date']).any()
    assert set(joined.ph) == set(aliases) and set(joined.date) == set(DATES)
    def mat(col):
        return joined.pivot(index='ph', columns='date', values=col).reindex(index=aliases, columns=DATES).fillna(0).to_numpy(float)
    matrices = {c: mat(c) for c in ['dist_km', 'km_from_11h', 'n', 'n_stable', 'rec_all_h11', 'rec_stable_h11']}
    vw = np.random.default_rng(SEED).multinomial(290, np.full(290, 1/290), size=200)
    ix = {d: i for i, d in enumerate(DATES)}
    old = old.set_index('date'); pub = pub.set_index('date')
    checks = {}; vehicle_rows = []; draws = {}; norms = {}

    def norm(rec, km, date, refs):
        i = ix[date]; rr = [ix[d] for d in refs]
        cp = safe(rec.sum(axis=0), km.sum(axis=0))
        cpb = safe(vw@rec, vw@km)
        return float(safe(cp[i], np.mean(cp[rr]))), safe(cpb[:, i], np.mean(cpb[:, rr], axis=1))

    for date in DATES:
        if int(old.loc[date, 'GPS_available']) != 1: continue
        hm = date == '2021-07-25'; km = matrices['km_from_11h' if hm else 'dist_km']
        refs = [d for d in B if pd.Timestamp(d).dayofweek == pd.Timestamp(date).dayofweek]
        ca, ba = norm(matrices['rec_all_h11' if hm else 'n'], km, date, refs)
        cs, bs = norm(matrices['rec_stable_h11' if hm else 'n_stable'], km, date, refs)
        q = safe(ba, bs); qpt = float(safe(ca, cs)); draws[date] = (ba, bs, q)
        norms[date] = dict(c_all=ca, c_stable=cs, q_probe=qpt)
        for field, val, boot in [('c_all', ca, ba), ('c_stable', cs, bs)]:
            lo, hi = ci(boot)
            checks['v6_point:'+date+':'+field] = bool(np.isclose(val, old.loc[date, field], atol=5e-10, rtol=5e-10))
            checks['v6_interval:'+date+':'+field] = bool(np.allclose([lo, hi], old.loc[date, [field+'_lo', field+'_hi']].to_numpy(float), atol=5e-10, rtol=5e-10))
        vehicle_rows.append(pd.DataFrame(dict(date=date, vehicle_rep=np.arange(1,201), baseline_variant='B_PROBE', c_all=ba, c_stable=bs, q_probe=q)))

    dev = pd.read_parquet(V6/'01_internal/T31_device_scenarios_internal_v6.parquet',
        columns=['date', 'dev_public', 'in_Sstar', 'observed_records', 'baseline_B1'])
    cached = pd.read_parquet(V6/'01_internal/T31_bootstrap_internal_v6.parquet')
    ids = np.sort(dev.dev_public.unique()); ndev = len(ids)
    assert ndev == 1287 and len(dev) == ndev*9 and not dev.duplicated(['date','dev_public']).any()
    dw = np.random.default_rng(SEED).multinomial(ndev, np.full(ndev, 1/ndev), size=500)
    device_rows = []; devdraw = {}; rounding = []
    for date in EVENT:
        z = dev[dev.date.eq(date)].set_index('dev_public').reindex(ids)
        assert z.in_Sstar.notna().all()
        n = z.observed_records.to_numpy(float); b = z.baseline_B1.to_numpy(float); st = z.in_Sstar.to_numpy(bool)
        naive = safe(dw@n, dw@b); stable = safe(dw@(n*st), dw@(b*st)); q = safe(naive, stable)
        cache = cached[cached.date.eq(date) & cached.scenario.eq('R_lower')].sort_values('rep')
        checks['cached_naive_500:'+date] = bool(len(cache)==500 and np.array_equal(naive, cache.estimate.to_numpy(float)))
        checks['cached_naive_close:'+date] = bool(len(cache)==500 and np.allclose(naive, cache.estimate.to_numpy(float), atol=1e-14, rtol=1e-14))
        devdraw[date] = (naive, stable, q)
        device_rows.append(pd.DataFrame(dict(date=date, device_rep=np.arange(1,501), R_naive=naive, R_stable=stable, q_fleet=q)))
        rounding.append(dict(date=date, R_naive_device_raw=float(safe(n.sum(), b.sum())),
            R_stable_device_raw=float(safe(n[st].sum(), b[st].sum())),
            R_naive_published=float(pub.loc[date,'R_naive']), R_stable_published=float(pub.loc[date,'R_stable'])))

    add_rows = []; products = []; badd = []; bnum = old_bounds.set_index('date')
    for date in DATES:
        gps = date in norms; event = date in GPS_EVENT
        row = dict(date=date, q_probe=np.nan, q_probe_ci_lo=np.nan, q_probe_ci_hi=np.nan,
                   q_fleet=np.nan, q_fleet_ci_lo=np.nan, q_fleet_ci_hi=np.nan,
                   q_probe_minus_q_fleet=np.nan, q_probe_minus_q_fleet_ci_lo=np.nan,
                   q_probe_minus_q_fleet_ci_hi=np.nan, q_probe_vehicle_valid=0,
                   q_fleet_device_valid=0, relative_difference_product_valid=0,
                   relative_inference_status='NA_no_GPS' if not gps else 'not_prespecified_outside_event_window',
                   relative_ratio_scope='Relative observation intensity; not capture probability or traffic-independent recovery',
                   relative_interval_scope='500 paired device by 200 paired vehicle Cartesian product; shared cross-day weights; fixed sets/baselines')
        if gps:
            qpt = float(safe(old.loc[date,'c_all'], old.loc[date,'c_stable']))
            qfleet = float(safe(pub.loc[date,'R_naive'], pub.loc[date,'R_stable']))
            row.update(q_probe=qpt, q_fleet=qfleet, q_probe_minus_q_fleet=qpt-qfleet,
                       q_probe_vehicle_valid=int(np.isfinite(draws[date][2]).sum()))
            row['q_probe_ci_lo'], row['q_probe_ci_hi'] = ci(draws[date][2])
        if event:
            naive, stable, qf = devdraw[date]; ca, cs, qp = draws[date]
            diff = (qp[None,:]-qf[:,None]).ravel()
            recovery = (naive[:,None]*safe(cs,ca)[None,:]).ravel()
            row['q_fleet_ci_lo'], row['q_fleet_ci_hi'] = ci(qf)
            row['q_probe_minus_q_fleet_ci_lo'], row['q_probe_minus_q_fleet_ci_hi'] = ci(diff)
            row.update(q_fleet_device_valid=int(np.isfinite(qf).sum()),
                       relative_difference_product_valid=int(np.isfinite(diff).sum()), relative_inference_status='complete')
            products.append(pd.DataFrame(dict(date=date, device_rep=np.repeat(np.arange(1,501),200),
                vehicle_rep=np.tile(np.arange(1,201),500), q_probe_minus_q_fleet=diff, R_probe=recovery)))
            probe = float(pub.loc[date,'R_naive']*safe(old.loc[date,'c_stable'],old.loc[date,'c_all']))
            lo, hi = ci(recovery)
        else: probe, lo, hi = np.nan, np.nan, np.nan
        add_rows.append(row)
        if date in EVENT:
            badd.append(dict(date=date, R_probe=probe, R_probe_ci_lo=lo, R_probe_ci_hi=hi,
                R_probe_available=bool(event), R_probe_product_valid=int(np.isfinite(recovery).sum()) if event else 0,
                R_probe_n_device_draws=500 if event else 0, R_probe_n_vehicle_draws=200 if event else 0,
                R_probe_status='complete' if event else 'NA_no_GPS',
                R_probe_scenario_scope='Conditional relative-probe correction; not an identified all-fleet truth',
                R_probe_point_scope='Inherited published R_naive precision times internal c_stable/c_all',
                R_probe_interval_scope='500 original naive-device draws x 200 paired vehicle draws, independent product, fixed sets/baselines; 95% percentile',
                R_probe_spatial_scope='Network ratio uses no camera/GPS ring assignment or I3 cap; routing/exposure/GPS selection remain',
                R_probe_shared_system_limitation='Resampling product imposes independence; taxis and full fleet share AVI system, so covariance not estimated'))

    new = pd.DataFrame(add_rows); bound_new = pd.DataFrame(badd)
    for comparator in ['R_naive','R_stable']:
        checks['inherited_T28_T31_'+comparator+'_agree'] = bool(np.array_equal(
            pub.reindex(EVENT)[comparator].to_numpy(float),
            bounds_pub.set_index('date').reindex(EVENT)[comparator].to_numpy(float)))
    public_daily = append_public(V6/'03_taxi_probe/T28_probe_daily_v6.csv', new, '03_taxi_probe/T28_probe_daily_v7.csv')
    public_bounds = append_public(V6/'05_bounds/T31_recovery_bounds_v6.csv', bound_new, '05_bounds/T31_recovery_bounds_v7.csv')
    daily_internal = old.reset_index().merge(new,on='date',validate='one_to_one')
    bounds_internal = old_bounds.merge(bound_new,on='date',validate='one_to_one')
    save(daily_internal, '01_internal/T28_probe_daily_internal_v7.csv', True)
    save(bounds_internal, '01_internal/T31_recovery_bounds_internal_v7.csv', True)
    save(pd.DataFrame(rounding), '01_internal/device_point_rounding_v7.csv', True)
    save(pd.concat(device_rows,ignore_index=True), '01_internal/probe_device_bootstrap_v7.parquet', True)
    save(pd.concat(products,ignore_index=True), '01_internal/probe_product_bootstrap_v7.parquet', True)

    sens = []; date='2021-07-28'; km=matrices['dist_km']
    for label, refs in [('B_PROBE', ['2021-07-07','2021-07-14','2021-07-21']), ('B_PROBE_drop_0707_0721',['2021-07-14'])]:
        ca, ba = norm(matrices['n'],km,date,refs); cs, bs=norm(matrices['n_stable'],km,date,refs); q=safe(ba,bs)
        nd=devdraw[date][0]; rp=(nd[:,None]*safe(bs,ba)[None,:]).ravel()
        rr=dict(date=date,baseline_variant=label,baseline_dates=';'.join(refs),n_baseline_dates=len(refs),
            c_all=ca,c_stable=cs,q_probe=float(safe(ca,cs)),R_probe=float(pub.loc[date,'R_naive']*safe(cs,ca)),
            n_vehicle_draws=200,n_device_draws=500,n_products=100000,
            interpretation='Single remaining Wednesday is retained without fallback; sensitivity does not replace primary B_PROBE')
        for field, draw in [('c_all',ba),('c_stable',bs),('q_probe',q),('R_probe',rp)]:
            rr[field+'_ci_lo'],rr[field+'_ci_hi']=ci(draw)
        sens.append(rr)
        if label != 'B_PROBE': vehicle_rows.append(pd.DataFrame(dict(date=date, vehicle_rep=np.arange(1,201), baseline_variant=label,c_all=ba,c_stable=bs,q_probe=q)))
    sens=pd.DataFrame(sens);save(sens,'03_taxi_probe/T28_wednesday_sensitivity_v7.csv')
    save(sens,'01_internal/T28_wednesday_sensitivity_internal_v7.csv',True)
    save(pd.concat(vehicle_rows,ignore_index=True),'01_internal/probe_vehicle_bootstrap_v7.parquet',True)
    save(new[new.date.isin(GPS_EVENT)], '08_figures/fig_probe_relative_intensity_v7_data.csv')
    save(bounds_internal, '08_figures/fig_probe_recovery_v7_data.csv')
    (ROOT/'08_figures').mkdir(exist_ok=True)
    # Frozen root protocol specifies figure-source CSVs only; do not render.
    checks['Wednesday_refs_main_3_sensitivity_1'] = bool(sens.n_baseline_dates.tolist()==[3,1])
    checks['GPS_event_7_rows'] = bool(new.relative_inference_status.eq('complete').sum()==7)
    checks['all_product_counts_100000'] = bool(bound_new.loc[bound_new.date.isin(GPS_EVENT),'R_probe_product_valid'].eq(100000).all())
    checks['Aug1_Aug2_NA_probe'] = bool(bound_new.loc[~bound_new.date.isin(GPS_EVENT),'R_probe'].isna().all())
    checks['July25_hour_matched'] = bool(old.loc['2021-07-25','hour_matched']==1 and bnum.loc['2021-07-25','hour_matched']==1)
    after = {rel: signature(V6/rel) for rel in INPUTS}
    checks['all_inputs_unchanged'] = before==after
    checks['protocol_unchanged'] = signature(protocol)==protocol_signature
    checks['interpretation_unchanged'] = signature(interpretation)==interpretation_signature
    result26=bound_new.set_index('date').loc['2021-07-26']
    eventtable=new[new.date.isin(GPS_EVENT)]
    report=dict(status='complete' if all(checks.values()) else 'integrity_check_failed',started_utc=started,
        finished_utc=datetime.now(timezone.utc).isoformat(),elapsed_seconds=time.perf_counter()-start,
        seed=SEED,protocol=str(protocol),protocol_signature=protocol_signature,interpretation_signature=interpretation_signature,
        input_before=before,input_after=after,checks=checks,checks_passed=bool(all(checks.values())),
        acceptance={'R_probe_0726_in_056_063':bool(.56<=result26.R_probe<=.63)},
        R_probe_0726={c:result26[c] for c in ['R_probe','R_probe_ci_lo','R_probe_ci_hi']},
        daily_relative_results=eventtable.to_dict('records'),wednesday_sensitivity=sens.to_dict('records'),
        n_probe=290,n_device=ndev,device_draws=500,vehicle_draws=200,products_per_day=100000,
        independence='Product empirical distribution imposed; not established independence of shared AVI data',
        point_rounding='Published4dp fleet comparators retained; original unrounded device draws reused for intervals',
        target_GPS_cancellation='Target-day km cancels in c_all/c_stable. Baseline weekday cpk means retain GPS weighting; route/exposure/selection confounding remains.',
        effect_interpretation='Relative observation-intensity consistency; no assertion that traffic activity is irrelevant or true all-fleet recovery is identified',
        old_scenarios='All inherited v6 T28/T31 public cells copied exactly; lower/upper/mid not recomputed',
        no_GPS_dates=EVENT[-2:],source_Z_access=False,key_access=False)
    write_json(ROOT/'00_env/probe_bounds_execution_v7.json',json_safe(report))
    print(json.dumps(json_safe({k:report[k] for k in ['status','checks_passed','acceptance','R_probe_0726','wednesday_sensitivity','elapsed_seconds']}),ensure_ascii=False),flush=True)
    if not all(checks.values()): raise RuntimeError('I2/I5 v7 integrity checks failed; see execution JSON')


if __name__ == '__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--protocol',required=True)
    ap.add_argument('--root-released',action='store_true');args=ap.parse_args()
    run(args.protocol,args.root_released)
