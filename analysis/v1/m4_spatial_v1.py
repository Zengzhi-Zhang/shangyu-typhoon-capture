# -*- coding: utf-8 -*-
"""M4: spatial recovery with frozen definitions and a reproducible seed.

Only 01_panels retains precise device coordinates. All published device tables
round lon/lat to 0.01 degrees; plotting coordinates use independent uniform
UTM offsets in [-200, 200] m on each axis. Source files are never written.
"""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[2]), str(_ReleasePath(__file__).resolve().parents[0])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
import json
import argparse
import time
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy.spatial import cKDTree
from scipy.stats import spearmanr
from spatial_stats_v1 import joincount_knn6
import statsmodels.formula.api as smf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize

ROOT = Path(_release_path('project_root'))
OUT = ROOT / '05_m4_spatial'
FIG = ROOT / '08_figures'
SEED = 20261005
B = 500
N_PERM = 999
KNN = 6
D_PARTIAL = pd.to_datetime(['2021-07-08', '2021-07-10', '2021-07-22',
                            '2021-07-23', '2021-07-24', '2021-07-25'])
B1 = pd.date_range('2021-07-05', '2021-07-21').difference(D_PARTIAL)
B_TAXI = pd.date_range('2021-07-06', '2021-07-21')
RINGS = ['0-2', '2-4', '4-7', '7-12', '12-20', '20+']
ROAD_LEVELS = ['motorway/trunk', 'primary', 'secondary', 'tertiary',
               'residential/service', 'unclassified/other', 'no_road_within_80m']
DATE_LABELS = [('0726', '2021-07-26'), ('0727', '2021-07-27'),
               ('0728', '2021-07-28'), ('0802', '2021-08-02')]
TRANS = Transformer.from_crs(4326, 32651, always_xy=True)
INVERSE = Transformer.from_crs(32651, 4326, always_xy=True)


def write_json(path, value):
    def convert(x):
        if isinstance(x, (np.integer,)): return int(x)
        if isinstance(x, (np.floating,)): return None if not np.isfinite(x) else float(x)
        if isinstance(x, np.bool_): return bool(x)
        raise TypeError(type(x).__name__)
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2,
                                    default=convert, allow_nan=False), encoding='utf-8')


def save_csv(frame, path, published=False):
    frame = frame.copy()
    if published:
        for c in ['lon', 'lat']:
            if c in frame: frame[c] = frame[c].round(2)
    # Preserve small p values and regression precision; only ratios have the
    # delivery convention of four decimal places.
    for c in ['p', 'p_perm', 'coef', 'se_HC1', 'r_squared']:
        if c in frame:
            frame[c] = frame[c].map(lambda v: '' if pd.isna(v) else format(float(v), '.10g'))
    frame.to_csv(path, index=False, encoding='utf-8-sig', float_format='%.4f')


def load_data():
    dh = pd.read_csv(ROOT / '01_panels/device_hour.csv', encoding='utf-8-sig')
    dh['date'] = pd.to_datetime(dh['date'].astype(str).str.replace('"', '', regex=False))
    attr = pd.read_csv(ROOT / '01_panels/device_attributes.csv', encoding='utf-8-sig').set_index('dev')
    dd = dh.groupby(['dev', 'date'])['n'].sum().unstack(fill_value=0).reindex(attr.index, fill_value=0)
    return dh, attr, dd


def vectors(dh, dd, day, refs=B1, hour_matched=True):
    day = pd.Timestamp(day)
    baseline = [d for d in refs if d.dayofweek == day.dayofweek]
    if hour_matched and day == pd.Timestamp('2021-07-25'):
        partial = dh.loc[dh['hour'].between(11, 23)]
        mat = partial.groupby(['dev', 'date'])['n'].sum().unstack(fill_value=0).reindex(dd.index, fill_value=0)
        return mat.reindex(columns=[day], fill_value=0)[day], mat.reindex(columns=baseline, fill_value=0).mean(axis=1)
    return dd.reindex(columns=[day], fill_value=0)[day], dd.reindex(columns=baseline, fill_value=0).mean(axis=1)


def failure_vectors(dh, dd, day):
    day = pd.Timestamp(day)
    n, b = vectors(dh, dd, day)
    prev = day - pd.Timedelta(days=7)
    if prev not in D_PARTIAL and prev in dd.columns:
        den = dd[prev]
        source = 'previous_same_weekday'
    else:
        den = b
        source = 'B1_same_weekday_fallback'
    return n.lt(.05 * den), n.lt(.05 * b), den, source


def bootstrap_ratio(n, b, rng):
    n, b = np.asarray(n, dtype=float), np.asarray(b, dtype=float)
    if not len(n) or b.sum() <= 0: return np.nan, np.nan
    indices = rng.integers(0, len(n), size=(B, len(n)))
    num, den = n[indices].sum(axis=1), b[indices].sum(axis=1)
    ratio = np.divide(num, den, out=np.full(B, np.nan), where=den > 0)
    return tuple(np.nanquantile(ratio, [.025, .975]))


def bootstrap_median(vals, rng):
    vals = np.asarray(vals, float)
    vals = vals[np.isfinite(vals)]
    if not len(vals): return np.nan, np.nan
    idx = rng.integers(0, len(vals), size=(B, len(vals)))
    return tuple(np.quantile(np.median(vals[idx], axis=1), [.025, .975]))


def knn_indices(xy):
    if len(xy) < 2: return np.empty((len(xy), 0), dtype=int)
    # Duplicate locations require explicit exclusion of the own index.
    k = min(KNN, len(xy) - 1)
    # Match the candidate count and self-exclusion used by M5's shared helper,
    # including deterministic handling of duplicate coordinates.
    _, nb = cKDTree(xy).query(xy, k=min(k + 2, len(xy)))
    return np.array([row[row != i][:k] for i, row in enumerate(np.atleast_2d(nb))], dtype=int)


def moran(vals, xy, rng):
    vals = np.asarray(vals, float)
    nb = knn_indices(xy)
    z = vals - vals.mean()
    n, k = nb.shape
    if n < 3 or not k or np.dot(z, z) == 0:
        return {'I': None, 'p_perm': None, 'n': n, 'k': k}
    def calc(v): return float(np.sum(v[:, None] * v[nb]) / (k * np.dot(v, v)))
    obs = calc(z)
    perms = np.array([calc(rng.permutation(z)) for _ in range(N_PERM)])
    sd = perms.std(ddof=0)
    return {'I': obs, 'observed': obs, 'perm_mean': float(perms.mean()),
            'perm_sd': float(sd), 'z': float((obs - perms.mean()) / sd),
            'p_perm': float((1 + np.sum(perms >= obs)) / (N_PERM + 1)),
            'n': n, 'k': k, 'n_permutations': N_PERM,
            'weights': 'Directed 6 nearest neighbours, equal row-standardized weights',
            'alternative': 'Positive spatial autocorrelation'}


def create_device_table(dh, attr, dd):
    p = attr.copy()
    p['log_base'] = np.log(p['base_B1'].where(p['base_B1'] > 0))
    p['distance_ring'] = pd.cut(p['dist_baiguan_km'], [0, 2, 4, 7, 12, 20, np.inf],
                               labels=RINGS, include_lowest=True, right=False).astype(object)
    p['elev_group'] = pd.cut(p['elev_m'], [-np.inf, 5, 10, 20, 50, np.inf],
                            labels=['<5', '5-10', '10-20', '20-50', '50+'], right=False).astype(object)
    p['relief_group'] = pd.cut(p['relief_300m'], [-np.inf, 3, 10, 30, np.inf],
                              labels=['<3', '3-10', '10-30', '30+'], right=False).astype(object)
    n25, b25 = vectors(dh, dd, '2021-07-25')
    p['r_0725h'] = n25 / b25.replace(0, np.nan)
    p['hour_matched_0725'] = 1
    for label, day in DATE_LABELS:
        n, base = vectors(dh, dd, day)
        p['n_' + label] = n
        p['b_' + label] = base
        p['r_' + label] = n / base.replace(0, np.nan)
        if label in ['0726', '0728', '0802']:
            off, offbase, _, source = failure_vectors(dh, dd, day)
            p['off_' + label] = np.where(p['in_A200'].eq(1), off.astype(int), np.nan)
            p['off_' + label + '_baseline'] = np.where(p['in_A200'].eq(1), offbase.astype(int), np.nan)
            p['off_denominator_' + label] = source
    late = pd.date_range('2021-07-29', '2021-08-02')
    nlate = dd.reindex(columns=late, fill_value=0).sum(axis=1)
    blate = pd.concat([vectors(dh, dd, day)[1] for day in late], axis=1).sum(axis=1)
    p['r_0729_0802'] = nlate / blate.replace(0, np.nan)
    return p


def group_table(p, column, rng, values=None):
    rows = []
    values = values if values is not None else sorted(p[column].dropna().unique())
    for value in values:
        x = p.loc[p[column].eq(value) & p['in_A100'].eq(1)]
        if not len(x): continue
        fail = x.loc[x['in_A200'].eq(1)]
        st = x.loc[x['in_Sstar'].eq(1)]
        row = {'group': str(value), 'n_devices': len(x), 'n_A200': len(fail), 'n_stable': len(st)}
        for d in ['0726', '0728', '0802']:
            v = fail['off_' + d].values
            row['off_' + d] = float(np.mean(v)) if len(v) else np.nan
            if len(v):
                sims = v[rng.integers(0, len(v), size=(B, len(v)))].mean(axis=1)
                lo, hi = np.quantile(sims, [.025, .975])
            else: lo, hi = np.nan, np.nan
            row['off_' + d + '_ci_lo'], row['off_' + d + '_ci_hi'] = lo, hi
        for d, suffix in [('0726', 'online'), ('0727', 'online'), ('0728', 'stable')]:
            chosen = x.loc[x['r_' + d].ge(.20)] if suffix == 'online' else st
            metric = 'flow_r_' + d + '_' + suffix
            row['n_' + d + '_' + suffix] = len(chosen)
            row[metric] = chosen['n_' + d].sum() / chosen['b_' + d].sum() if chosen['b_' + d].sum() > 0 else np.nan
            row[metric + '_ci_lo'], row[metric + '_ci_hi'] = bootstrap_ratio(chosen['n_' + d], chosen['b_' + d], rng)
        row['median_r_0726_stable'] = st['r_0726'].median()
        row['median_r_0726_stable_ci_lo'], row['median_r_0726_stable_ci_hi'] = bootstrap_median(st['r_0726'], rng)
        rows.append(row)
    return pd.DataFrame(rows)


FORMULA = 'response ~ np.log1p(dist_baiguan_km) + log_base + elev_m + relief_300m + C(road_level) + C(org) + gateway'


def ols_rows(p, day, ratio, sample='Sstar'):
    x = p.loc[p['in_Sstar'].eq(1) & p['lon'].notna() & p['lat'].notna()].copy()
    x['response'] = np.log(ratio.reindex(x.index).clip(.05, 3))
    x = x.replace([np.inf, -np.inf], np.nan).dropna(subset=['response', 'dist_baiguan_km', 'log_base',
                                                           'elev_m', 'relief_300m', 'road_level', 'org', 'gateway'])
    fit = smf.ols(FORMULA, data=x).fit(cov_type='HC1')
    return pd.DataFrame([{'date': str(pd.Timestamp(day).date()), 'term': term, 'coef': float(coef),
                          'se_HC1': float(fit.bse[term]), 'p': float(fit.pvalues[term]),
                          'n': int(fit.nobs), 'r_squared': float(fit.rsquared),
                          'sample': sample, 'response': 'log(r.clip(0.05,3))'}
                         for term, coef in fit.params.items()])


def taxi_tables(p, dh, dd):
    tg = pd.read_csv(ROOT / '01_panels/taxi_grid_day.csv')
    if not len(tg) or tg['n_points'].sum() <= 0:
        raise ValueError('Taxi grid panel has no observed points; pending headers are not valid grid data')
    tg['date'] = pd.to_datetime(tg['date'])
    centres = pd.read_csv(ROOT / '01_panels/taxi_grid_centroids.csv')
    piv = tg.pivot_table(index=['gx', 'gy'], columns='date', values='n_points', aggfunc='sum', fill_value=0)
    base_mean = piv.reindex(columns=B_TAXI, fill_value=0).mean(axis=1)
    grid = centres.set_index(['gx', 'gy']).reindex(piv.index).copy()
    bg = pd.read_csv(ROOT / '01_panels/township_centroids_osm.csv')
    bg = bg.loc[bg['town'].eq('百官')].iloc[0]
    centre_xy = np.array(TRANS.transform(bg['lon'], bg['lat']))
    # Grid centres are exact 1 km UTM lattice centres, not device locations.
    grid['dist_baiguan_km'] = np.linalg.norm(np.column_stack([(grid.index.get_level_values('gx') + .5) * 1000,
                                                             (grid.index.get_level_values('gy') + .5) * 1000]) - centre_xy, axis=1) / 1000
    grid['n_base_points'] = base_mean
    for label, day in DATE_LABELS[:3]:
        target = pd.Timestamp(day)
        refs = [d for d in B_TAXI if d.dayofweek == target.dayofweek]
        bpts = piv.reindex(columns=refs, fill_value=0).mean(axis=1)
        npts = piv.reindex(columns=[target], fill_value=0)[target]
        grid['b_taxi_pts_' + label] = bpts
        grid['n_taxi_pts_' + label] = npts
        grid['r_taxi_pts_' + label] = npts / bpts.replace(0, np.nan)
    grid = grid.loc[base_mean.ge(200)].copy()
    grid['distance_ring'] = pd.cut(grid['dist_baiguan_km'], [0, 2, 4, 7, 12, 20, np.inf], labels=RINGS,
                                  include_lowest=True, right=False).astype(object)
    camera = p.loc[p['in_Sstar'].eq(1) & p['lon'].notna() & p['lat'].notna()].copy()
    e, north = TRANS.transform(camera['lon'].values, camera['lat'].values)
    camera['gx'], camera['gy'] = np.floor(e / 1000).astype(int), np.floor(north / 1000).astype(int)
    cam = camera.groupby(['gx', 'gy']).size().rename('n_Sstar_cameras').to_frame()
    for label, _ in DATE_LABELS[:3]:
        pair = camera.groupby(['gx', 'gy'])[['n_' + label, 'b_' + label]].sum()
        cam['n_camera_' + label], cam['b_camera_' + label] = pair['n_' + label], pair['b_' + label]
        cam['r_camera_' + label] = pair['n_' + label] / pair['b_' + label].replace(0, np.nan)
    paired = grid.join(cam, how='inner')
    stats, gradients = {}, []
    for label, day in DATE_LABELS[:3]:
        pair = paired.dropna(subset=['r_taxi_pts_' + label, 'r_camera_' + label])
        stats[label] = {'n_grids': len(pair)}
        for key, a, b in [('spearman_taxi_camera', pair['r_taxi_pts_' + label], pair['r_camera_' + label]),
                           ('spearman_dist_taxi', pair['dist_baiguan_km'], pair['r_taxi_pts_' + label]),
                           ('spearman_dist_camera', pair['dist_baiguan_km'], pair['r_camera_' + label])]:
            rho, pv = spearmanr(a, b)
            stats[label][key] = {'rho': float(rho) if np.isfinite(rho) else None,
                                 'p': float(pv) if np.isfinite(pv) else None}
        for ring in RINGS:
            x = pair.loc[pair['distance_ring'].eq(ring)]
            gradients.append({'date': str(pd.Timestamp(day).date()),
                              'distance_ring': ring, 'n_grids': len(x),
                              'n_Sstar_cameras': int(x['n_Sstar_cameras'].sum()),
                              'r_taxi_pts': x['n_taxi_pts_' + label].sum() / x['b_taxi_pts_' + label].sum() if x['b_taxi_pts_' + label].sum() else np.nan,
                              'r_camera': x['n_camera_' + label].sum() / x['b_camera_' + label].sum() if x['b_camera_' + label].sum() else np.nan})
    return grid.reset_index(), paired.reset_index(), stats, pd.DataFrame(gradients)


def make_figure(p, ringroad, gradients, rng, pending_taxi=False):
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'text.color': '#333333',
                         'axes.labelcolor': '#333333', 'xtick.color': '#333333', 'ytick.color': '#333333'})
    import matplotlib.font_manager as fm
    for font in ['Microsoft YaHei', 'SimHei', 'Noto Sans CJK SC']:
        if any(f.name == font for f in fm.fontManager.ttflist):
            plt.rcParams['font.family'] = font
            break
    x = p.loc[p['in_A100'].eq(1) & p['lon'].notna() & p['lat'].notna()].copy()
    e, north = TRANS.transform(x['lon'].values, x['lat'].values)
    x['plot_e_km'] = (e + rng.uniform(-200, 200, len(x))) / 1000
    x['plot_n_km'] = (north + rng.uniform(-200, 200, len(x))) / 1000
    lon_jitter, lat_jitter = INVERSE.transform(x['plot_e_km'].values * 1000, x['plot_n_km'].values * 1000)
    x['plot_lon'], x['plot_lat'] = lon_jitter, lat_jitter
    fig = plt.figure(figsize=(16, 11))
    gs = fig.add_gridspec(2, 2, height_ratios=[1.25, 1])
    norm = Normalize(0, 1.2)
    for i, label in enumerate(['0726', '0728']):
        ax = fig.add_subplot(gs[0, i])
        online = x['r_' + label].ge(.20)
        sizes = np.clip(np.sqrt(x['base_B1'].values) / 2, 12, 70)
        sc = ax.scatter(x.loc[online, 'plot_e_km'], x.loc[online, 'plot_n_km'],
                        c=x.loc[online, 'r_' + label], s=sizes[online], cmap='Blues', norm=norm, alpha=.8)
        failed = x['off_' + label].eq(1)
        ax.scatter(x.loc[failed, 'plot_e_km'], x.loc[failed, 'plot_n_km'], marker='x', s=36,
                   linewidths=1.5, color='#666666', label='Failed (<5%, A200)')
        other = ~(online | failed)
        ax.scatter(x.loc[other, 'plot_e_km'], x.loc[other, 'plot_n_km'], s=12, color='#bbbbbb',
                   alpha=.6, label='Other A100 device')
        ax.set_title('(a' + str(i + 1) + ') July ' + ('26' if label == '0726' else '28'))
        ax.set_xlabel('UTM 51N easting (km)'); ax.set_ylabel('UTM 51N northing (km)')
        ax.set_aspect('equal', adjustable='box'); ax.grid(color='#dddddd', linewidth=.4)
        ax.legend(frameon=False, fontsize=8)
        fig.colorbar(sc, ax=ax, label='Same-weekday flow ratio', fraction=.025, pad=.02)
    ax = fig.add_subplot(gs[1, 0])
    roads = ROAD_LEVELS
    width = .105
    xpos = np.arange(len(RINGS))
    for i, road in enumerate(roads):
        sub = ringroad.loc[ringroad['road_level'].eq(road)].set_index('distance_ring').reindex(RINGS)
        ax.bar(xpos + (i - 3) * width, sub['flow_r_0726_online'], width=width,
               color=plt.get_cmap('Blues')(.25 + .11 * i), label=road)
    ax.set_xticks(xpos); ax.set_xticklabels(RINGS)
    ax.set_title('(b) July 26: distance and road level')
    ax.set_xlabel('Distance to Baiguan (km)'); ax.set_ylabel('Online camera flow ratio')
    ax.grid(axis='y', color='#dddddd', linewidth=.4); ax.legend(frameon=False, fontsize=6, ncol=2, loc='upper right')
    ax = fig.add_subplot(gs[1, 1])
    if pending_taxi:
        ax.set_axis_off()
        ax.text(.5, .55, '(c) Taxi–camera paired grid analysis pending', ha='center', va='center', fontsize=13)
        ax.text(.5, .4, 'GPS source unavailable; no grid results have been substituted.', ha='center', va='center', fontsize=10, wrap=True)
    else:
        for i, day in enumerate(['2021-07-26', '2021-07-28']):
            sub = gradients.loc[gradients['date'].eq(day)].set_index('distance_ring').reindex(RINGS)
            for source, color in [('camera', '#2a78d6'), ('taxi_pts', '#eb6834')]:
                ax.plot(xpos, sub['r_' + source], color=color, linewidth=2, marker='o', markersize=8,
                        linestyle='-' if i == 0 else '--', label=('Camera' if source == 'camera' else 'Taxi points') + ' ' + day[5:])
        ax.set_xticks(xpos); ax.set_xticklabels(RINGS)
        ax.set_xlabel('Distance to Baiguan (km)'); ax.set_ylabel('Same-weekday ratio')
        ax.set_title('(c) Paired 1 km grids'); ax.legend(frameon=False, fontsize=8)
        ax.grid(color='#dddddd', linewidth=.4)
    fig.text(.5, .02, 'Device map points are independently jittered uniformly by ±200 m on each UTM axis; point size = baseline flow.\n'
             'Spatial labels refer to nearest town centres, not administrative boundaries. ' + ('Paired grid analysis remains pending.' if pending_taxi else 'Grid curves use paired S* camera and taxi grids.'),
             ha='center', fontsize=10)
    fig.subplots_adjust(left=.06, right=.95, bottom=.14, top=.95, hspace=.35, wspace=.25)
    fig.savefig(FIG / 'fig5_spatial.png', dpi=180)
    plt.close(fig)
    data = []
    for label in ['0726', '0728']:
        q = x[['plot_lon', 'plot_lat', 'base_B1', 'r_' + label, 'off_' + label]].copy()
        q[['plot_lon', 'plot_lat']] = q[['plot_lon', 'plot_lat']].round(2)
        q = q.rename(columns={'r_' + label: 'ratio', 'off_' + label: 'failed'})
        q['panel'] = 'map'; q['date'] = '2021-07-' + label[-2:]
        # No anonymous device ID is coupled to its jittered map position.
        data.append(q.reset_index(drop=True))
    bars = ringroad.copy(); bars['panel'] = 'ring_road'; data.append(bars)
    curves = gradients.copy(); curves['panel'] = 'paired_grid_gradient'; data.append(curves)
    if pending_taxi:
        data.append(pd.DataFrame([{'panel': 'paired_grid_gradient', 'status': 'pending: GPS source unavailable'}]))
    return pd.concat(data, ignore_index=True, sort=False)


def main(cameras_only=False):
    started = time.time()
    OUT.mkdir(exist_ok=True); FIG.mkdir(exist_ok=True)
    rng = np.random.default_rng(SEED)
    dh, attr, dd = load_data()
    p = create_device_table(dh, attr, dd)
    save_csv(p.reset_index(), OUT / 'm4_device_ratios.csv', published=True)
    tables = {}
    for col, filename, values in [('distance_ring', 'm4_by_distance_ring.csv', RINGS),
                                  ('road_level', 'm4_by_road_level.csv', ROAD_LEVELS),
                                  ('near_town', 'm4_by_town.csv', None)]:
        table = group_table(p, col, rng, values)
        tables[col] = table
        save_csv(table, OUT / filename)
    elev = group_table(p, 'elev_group', rng, ['<5', '5-10', '10-20', '20-50', '50+'])
    elev.insert(0, 'group_by', 'elev_m')
    relief = group_table(p, 'relief_group', rng, ['<3', '3-10', '10-30', '30+'])
    relief.insert(0, 'group_by', 'relief_300m')
    save_csv(pd.concat([elev, relief], ignore_index=True), OUT / 'm4_by_elev.csv')
    crossed = []
    for ring in RINGS:
        sub = p.loc[p['distance_ring'].eq(ring)]
        tab = group_table(sub, 'road_level', rng, ROAD_LEVELS)
        tab = tab.rename(columns={'group': 'road_level'})
        tab.insert(0, 'distance_ring', ring)
        crossed.append(tab)
    ringroad = pd.concat(crossed, ignore_index=True)
    save_csv(ringroad, OUT / 'm4_distance_ring_by_road_level.csv')
    ols = pd.concat([ols_rows(p, day, p['r_' + label]) for label, day in DATE_LABELS[:3]], ignore_index=True)
    save_csv(ols, OUT / 'm4_ols.csv')
    spatial = {'seed': SEED, 'n_permutations': N_PERM, 'failure_denominator': 'Previous same weekday, B1 fallback on missing/partial date',
               'moran': {}, 'joincount': {}}
    for label, day in DATE_LABELS[:2]:
        on = p.loc[p['in_A100'].eq(1) & p['r_' + label].ge(.20) & p['lon'].notna() & p['lat'].notna()]
        xy = np.column_stack(TRANS.transform(on['lon'].values, on['lat'].values))
        spatial['moran'][day] = moran(np.log(on['r_' + label].clip(.05, 3)), xy, np.random.default_rng(SEED))
    act = p.loc[p['in_A200'].eq(1) & p['lon'].notna() & p['lat'].notna()]
    xy = np.column_stack(TRANS.transform(act['lon'].values, act['lat'].values))
    for label, day in [DATE_LABELS[0], DATE_LABELS[2], DATE_LABELS[3]]:
        spatial['joincount'][day] = joincount_knn6(xy, act['off_' + label].values,
                                                  seed=SEED, n_perm=N_PERM)
    write_json(OUT / 'm4_moran.json', spatial)
    # Prespecified platform negative controls; explicit previous-week references.
    negative_ols, negative_rings = [], []
    for target, reference in [('2021-07-08', '2021-07-01'), ('2021-07-10', '2021-07-03')]:
        n = dd[pd.Timestamp(target)]
        b = dd[pd.Timestamp(reference)]
        ratio = n / b.replace(0, np.nan)
        negative_ols.append(ols_rows(p, target, ratio))
        for ring in RINGS:
            on = p.loc[p['in_A100'].eq(1) & p['distance_ring'].eq(ring) & ratio.ge(.20)]
            negative_rings.append({'date': target, 'reference': reference, 'group': ring,
                                    'n_devices_online': len(on), 'flow_r_online': n.reindex(on.index).sum() / b.reindex(on.index).sum() if b.reindex(on.index).sum() else np.nan})
    negative_ols = pd.concat(negative_ols, ignore_index=True)
    save_csv(negative_ols, ROOT / '07_m6_robustness/m6_spatial_negative_control_ols.csv')
    save_csv(pd.DataFrame(negative_rings), ROOT / '07_m6_robustness/m6_spatial_negative_control_gradient.csv')
    if cameras_only:
        dist = ols.loc[ols['term'].eq('np.log1p(dist_baiguan_km)')]
        negdist = negative_ols.loc[negative_ols['term'].eq('np.log1p(dist_baiguan_km)')]
        terrain = ols.loc[ols['term'].isin(['elev_m', 'relief_300m'])]
        road = tables['road_level'].set_index('group')['flow_r_0726_online']
        verdict = {'hypothesis': 'H3', 'status': 'pending',
                   'pending': 'Taxi point-grid panel and paired gradient cannot be computed until GPS source is available',
                   'ols_distance': dist.to_dict('records'), 'negative_control_ols_distance': negdist.to_dict('records'),
                   'terrain_terms': terrain.to_dict('records'),
                   'road_comparison_0726': {'motorway_trunk': float(road.get('motorway/trunk')), 'residential_service': float(road.get('residential/service'))},
                   'interpretation': 'Adjusted distance gradients and road contrasts are computed, but H3 cross-source validation is unverified.'}
        write_json(OUT / 'm4_h3_verdict.json', verdict)
        pd.DataFrame(columns=['gx', 'gy', 'lon', 'lat', 'dist_baiguan_km', 'r_taxi_pts_0726',
                               'r_taxi_pts_0727', 'r_taxi_pts_0728', 'n_base_points']).to_csv(
            OUT / 'm4_taxi_grid_ratio.csv', index=False, encoding='utf-8-sig')
        pd.DataFrame(columns=['gx', 'gy', 'lon', 'lat', 'dist_baiguan_km', 'r_taxi_pts_0726',
                               'r_taxi_pts_0727', 'r_taxi_pts_0728', 'r_camera_0726', 'r_camera_0727',
                               'r_camera_0728', 'n_Sstar_cameras']).to_csv(
            OUT / 'm4_taxi_vs_camera_grid.csv', index=False, encoding='utf-8-sig')
        gradients = pd.DataFrame(columns=['date', 'distance_ring', 'n_grids', 'r_taxi_pts', 'r_camera'])
        save_csv(gradients, OUT / 'm4_taxi_camera_gradient.csv')
        write_json(OUT / 'm4_taxi_camera_spearman.json', {'status': 'pending', 'reason': 'GPS source unavailable; point-grid panel absent', 'spearman': None, 'n_grids': None})
        (OUT / 'PENDING.md').write_text('# Pending M4 cross-source checks\n\nThe GPS source is unavailable. Taxi grid tables contain headers only, not observed zero counts. Figure 5 panel (c) is explicitly pending. No substitute or synthetic result is reported. Run `m4_spatial_v1.py --stage finish` after real taxi grid panels are created.\n', encoding='utf-8')
        (OUT / 'M4_METHODS.md').write_text('''# M4 completed camera analysis and pending grid validation

Device coordinates are precise only in internal panels. Published device and
grid longitude/latitude are rounded to 0.01 degrees. `near_town` means nearest
OSM city/town centre, without administrative boundary attribution. Distances
use UTM 51N and the OSM Baiguan centre. Rings are left closed: [0,2), [2,4),
[4,7), [7,12), [12,20), [20,infinity) km.

Strata count A100 devices (`n_devices`); failure proportions use A200 with the
separately recorded `n_A200` denominator. Online ratios use S_on(t) and stable
ratios S*. Ratios divide sums of counts by sums of same-weekday B1 device
baselines. The July 25 column matches 11:00–23:59. Five hundred device-cluster
resamples give percentile 95% intervals. Main failures compare the previous
weekday, with B1 same-weekday fallback for a partial or missing reference.
Baseline-only flags are also saved.

OLS uses the exact frozen formula, complete-case S* with coordinates and HC1
standard errors. Platform control OLS uses July 1/3 as references for July 8/10.
Moran's I uses directed six-neighbour row-standardized weights on online A100.
Failure join-count uses the undirected union of six-neighbour edges on A200;
the helper is shared with M5. Both use 999 permutations, fixed seed 20261005,
and the upper-tail pseudo-p value (1 + permutations >= observed)/1000.

Map positions have independent uniform offsets between -200 and +200 metres
on each UTM axis; point size represents mean B1 flow. Figure data round the
jittered longitude/latitude to 0.01 degrees and omit device IDs.

Taxi grid output files currently contain headers only because the GPS source
is unavailable; these are pending results rather than observed zero counts.
Figure 5 panel (c) and H3 cross-source assessment are explicitly pending. All
completed camera results are reported, including the July 28 nonsignificant
distance coefficient. No causal interpretation or intercity extrapolation is
made; nonsignificant terrain coefficients cannot establish independence.
''', encoding='utf-8')
        figdata = make_figure(p, ringroad, gradients, np.random.default_rng(SEED), pending_taxi=True)
        save_csv(figdata, FIG / 'fig5_data.csv')
        write_json(ROOT / '00_env/spatial_deviations.json', {'definition_changes': [],
                   'pending': ['Taxi grid ratios, camera–taxi paired grids, H3 cross-source validation, Figure 5 panel (c)'],
                   'implementation_notes': ['Nearest-town identity and distance are reused from the frozen OSM pilot; town distance is rounded to 0.01 km in that intermediate.',
                                             'Baiguan UTM distance is recomputed at full precision; one device changes distance ring relative to rounded pilot distances.',
                                             'Terrain fields reuse the pilot 9x9-pixel approximately 300m-wide neighbourhood.',
                                             'Failure flags use prescribed previous-week denominators; pilot D3 spatial flags used same-weekday baseline instead.'],
                   'pilot_distance_ring_comparison': [{'group': ring, 'pilot': float(pilot), 'formal': float(tables['distance_ring'].set_index('group').loc[ring, 'flow_r_0726_online']),
                                                        'explanation': 'Formal B1 same-weekday and frozen A100 online set replace pilot B2/mean-baseline implementation.'}
                                                       for ring, pilot in zip(RINGS, [.709, .691, .603, .583, .507, .534])]})
        execution = {'seed': SEED, 'bootstrap_B': B, 'n_permutations': N_PERM, 'started_epoch': started,
                    'ended_epoch': time.time(), 'status': 'Camera analyses complete; taxi grid pairing and figure pending',
                    'n_devices': len(p), 'ols_n_by_date': ols.groupby('date')['n'].first().to_dict(),
                    'outputs': [str(f.relative_to(ROOT)).replace('\\', '/') for f in sorted(OUT.glob('*'))] + ['08_figures/fig5_spatial.png', '08_figures/fig5_data.csv', '07_m6_robustness/m6_spatial_negative_control_ols.csv', '07_m6_robustness/m6_spatial_negative_control_gradient.csv']}
        write_json(ROOT / '00_env/spatial_camera_execution.json', execution)
        write_json(ROOT / '00_env/spatial_execution.json', execution)
        print(json.dumps({'M4_camera': 'complete', 'n_devices': len(p), 'OLS_n': int(ols['n'].iloc[0])}))
        return
    grid, paired, correlations, gradients = taxi_tables(p, dh, dd)
    save_csv(grid, OUT / 'm4_taxi_grid_ratio.csv', published=True)
    save_csv(paired, OUT / 'm4_taxi_vs_camera_grid.csv', published=True)
    save_csv(gradients, OUT / 'm4_taxi_camera_gradient.csv')
    write_json(OUT / 'm4_taxi_camera_spearman.json', correlations)
    dist = ols.loc[ols['term'].eq('np.log1p(dist_baiguan_km)')]
    negdist = negative_ols.loc[negative_ols['term'].eq('np.log1p(dist_baiguan_km)')]
    camera_rho = correlations['0726']['spearman_dist_camera']['rho']
    taxi_rho = correlations['0726']['spearman_dist_taxi']['rho']
    reversed_dates = [day for label, day in DATE_LABELS[:3]
                      if correlations[label]['spearman_dist_camera']['rho'] is not None
                      and correlations[label]['spearman_dist_taxi']['rho'] is not None
                      and correlations[label]['spearman_dist_camera']['rho'] * correlations[label]['spearman_dist_taxi']['rho'] < 0]
    flags = {'adjusted_distance_gradient_0726_0727_negative_significant': bool(((dist.loc[dist['date'].isin(['2021-07-26', '2021-07-27']), 'coef'] < 0) & (dist.loc[dist['date'].isin(['2021-07-26', '2021-07-27']), 'p'] < .05)).all()),
             'taxi_gradient_reversed': camera_rho is not None and taxi_rho is not None and camera_rho * taxi_rho < 0,
             'same_negative_significant_gradient_in_platform_controls': bool(((negdist['coef'] < 0) & (negdist['p'] < .05)).any())}
    terrain = ols.loc[ols['term'].isin(['elev_m', 'relief_300m'])]
    flags['terrain_terms_all_p_ge_005'] = bool((terrain['p'] >= .05).all())
    road_ratios = tables['road_level'].set_index('group')['flow_r_0726_online']
    trunk, residential = road_ratios.get('motorway/trunk', np.nan), road_ratios.get('residential/service', np.nan)
    flags['trunk_ratio_lower_than_residential_0726'] = bool(trunk < residential)
    flags['taxi_gradient_assessable'] = camera_rho is not None and taxi_rho is not None and correlations['0726']['n_grids'] >= 3
    flags['recovery_day_gradient_reversal_present'] = any(day != '2021-07-26' for day in reversed_dates)
    fail_reasons = []
    if not flags['adjusted_distance_gradient_0726_0727_negative_significant']:
        fail_reasons.append('Adjusted distance association is not negative with p < 0.05 on both July 26 and July 27')
    if flags['taxi_gradient_reversed']:
        fail_reasons.append('Distance gradients have opposite signs in the paired taxi and camera grids')
    if flags['same_negative_significant_gradient_in_platform_controls']:
        fail_reasons.append('The same negative significant adjusted distance association occurs in a platform negative control')
    if not flags['terrain_terms_all_p_ge_005']:
        fail_reasons.append('At least one prespecified terrain term is statistically significant')
    if not flags['trunk_ratio_lower_than_residential_0726']:
        fail_reasons.append('The July 26 trunk ratio is not lower than the residential/service ratio')
    status = 'fail' if fail_reasons else ('pass' if flags['taxi_gradient_assessable'] else 'degraded')
    qualifications = []
    recovery_reversed = [day for day in reversed_dates if day != '2021-07-26']
    if recovery_reversed:
        qualifications.append('Recovery-date paired gradients have opposite signs on ' + ', '.join(recovery_reversed)
                              + ('; the primary shock-date gradients also have opposite signs, so the data do not support a consistent cross-source spatial gradient.'
                                 if flags['taxi_gradient_reversed'] else '; primary shock-date agreement cannot be described as stable across the recovery period.'))
    for _, row in dist.iterrows():
        if row['coef'] >= 0 or row['p'] >= .05:
            qualifications.append('Adjusted distance association on ' + row['date'] + ' is not negative with p < 0.05; all date-specific coefficients are reported.')
    verdict = {'hypothesis': 'H3', 'status': status,
               'checks': flags, 'ols_distance': dist.to_dict('records'),
               'fail_reasons': fail_reasons,
               'primary_cross_source_assessment_date': '2021-07-26',
               'reversed_gradient_dates': reversed_dates,
               'contextual_qualification': qualifications,
               'automatic_stop_condition': None,
               'assessment_scope': 'Primary shock-date cross-source direction plus all prespecified date-specific associations; H3 has no automatic stop rule in section 3.10.',
               'unverified_checks': [] if flags['taxi_gradient_assessable'] else ['Insufficient or constant paired-grid ratios prevent assessment of the taxi gradient'],
               'terrain_terms': terrain.to_dict('records'),
               'road_comparison_0726': {'motorway_trunk': float(trunk), 'residential_service': float(residential)},
               'negative_control_ols_distance': negdist.to_dict('records'),
               'taxi_camera_correlations': correlations,
               'interpretation': 'Descriptive spatial association; no causal or intercity extrapolation. Nonsignificant terrain terms do not establish terrain independence.',
               'gradient_direction_statistic': 'Spearman association of distance and flow ratio in the same paired 1 km grids'}
    write_json(OUT / 'm4_h3_verdict.json', verdict)
    h3_text = ['# H3 空间验收\n',
               '本节描述本市本次事件的空间关联，不作因果解释或跨城市外推。H3 不属于 §3.10 的自动停止条件。',
               '\n主跨源方向验收日固定为 2021-07-26。7/26–7/28 的出租车和卡口距离梯度、相互相关及 p 值全部并列报告；恢复日反向属于结论的时间范围限定，不追加方案未规定的自动停止规则。',
               '\n| 日期 | 调整后的 log1p(距百官) 系数 | HC1 标准误 | p | OLS n |',
               '|---|---:|---:|---:|---:|']
    for _, row in dist.iterrows():
        h3_text.append('| ' + row['date'] + ' | ' + format(row['coef'], '.6g') + ' | ' + format(row['se_HC1'], '.6g')
                       + ' | ' + format(row['p'], '.6g') + ' | ' + str(int(row['n'])) + ' |')
    h3_text.extend(['\n| 日期 | 配对网格数 | 距离–出租车 rho (p) | 距离–卡口 rho (p) | 出租车–卡口 rho (p) | 梯度方向反向 |',
                   '|---|---:|---:|---:|---:|---|'])
    for label, day in DATE_LABELS[:3]:
        s = correlations[label]
        values = []
        for name in ['spearman_dist_taxi', 'spearman_dist_camera', 'spearman_taxi_camera']:
            rho, pv = s[name]['rho'], s[name]['p']
            values.append(('未能估计' if rho is None else format(rho, '.6g')) + ' (' + ('未能估计' if pv is None else format(pv, '.6g')) + ')')
        h3_text.append('| ' + day + ' | ' + str(s['n_grids']) + ' | ' + ' | '.join(values) + ' | ' + ('是' if day in reversed_dates else '否') + ' |')
    h3_text.append('\n7/26 在线主干道路比值为 ' + format(trunk, '.4f') + '，residential/service 比值为 ' + format(residential, '.4f') + '。')
    h3_text.append('\n空间阴性对照使用 7/8 对 7/1、7/10 对 7/3 的固定同星期参照：\n')
    for _, row in negdist.iterrows():
        h3_text.append('- ' + row['date'] + '：距离系数 ' + format(row['coef'], '.6g') + '，p=' + format(row['p'], '.6g') + '。')
    h3_text.append('\n地形项逐日效应量与 p 值见 m4_ols.csv；不显著不能证明地形独立。')
    h3_text.append('\n描述性判定状态：`' + status + '`。')
    if fail_reasons: h3_text.extend(['\n未通过的预设方向/关联检查：\n'] + ['- ' + x for x in fail_reasons])
    if qualifications: h3_text.extend(['\n时间与适用范围限定：\n'] + ['- ' + x for x in qualifications])
    (OUT / 'm4_h3_acceptance.md').write_text('\n'.join(h3_text) + '\n', encoding='utf-8')
    figdata = make_figure(p, ringroad, gradients, np.random.default_rng(SEED))
    save_csv(figdata, FIG / 'fig5_data.csv')
    methods = '''# M4 spatial analysis conventions

All device identifiers are anonymous. Exact device coordinates are internal
inputs in `01_panels`; longitude and latitude in M4 output tables are rounded
to 0.01 degrees. No administrative township boundary is available: `near_town`
means the nearest OSM city/town centre. Distances use EPSG:32651 metres and the
OSM Baiguan centre. Distance rings are [0,2), [2,4), [4,7), [7,12), [12,20),
and [20,infinity) km. The elevation and local-relief strata are descriptive
extensions; their boundaries are fixed in the script before module execution.

In stratified tables `n_devices` counts A100 devices. Failure proportions use
A200 within that group; `n_A200` identifies their denominator. Main failure
flags compare the previous same weekday, falling back to the B1 same-weekday
mean if that day was partial or absent. The baseline-only flag is also saved.
Online flow ratios use S_on(t); stable ratios and medians use S*. Group ratios
divide sums of observed counts by sums of device-specific same-weekday
baseline counts. July 25 is matched to 11:00–23:59. Five hundred device-cluster
bootstrap resamples supply percentile 95% intervals for flow, median and
failure-proportion estimates; these intervals condition on the frozen set.

OLS uses the prespecified clipped log response, all frozen covariates,
complete-case S* with coordinates, and HC1 standard errors. The same model is
reported for the two platform negative-control dates, using July 1/3 as
reference counts. Moran's I uses the six nearest online A100 devices with
equal directed row-standardized weights. Join-count uses the undirected union
of six nearest neighbours among A200 devices with coordinates. Both spatial
tests use 999 label permutations, seed 20261005, with an upper-tail pseudo-p
value of (1 + permutations at least as large as observed)/1000. Join-count
calls the same helper as M5.

Taxi grid eligibility is a mean of at least 200 daily points over B_TAXI,
including zero-count dates. The daily denominator is the mean for matching
weekdays. Camera grid counts include S* devices only. Paired correlations and
distance curves retain the same common 1 km grids for the two sources; curves
divide within-ring sums rather than averaging ratios. Spearman coefficients
and their p values are reported for all three dates. Grid centroids are
locations of area aggregates rather than locations of individual taxis.

The H3 assessment reports each check separately. The adjusted distance check
requires negative coefficients with p < 0.05 on both July 26 and 27; the taxi
direction check uses the sign of the distance-ratio Spearman coefficient on
paired grids. A negative significant distance coefficient in either platform
control date triggers the corresponding counterexample. Trunk-versus-local
road comparison and all terrain terms are also reported. Nonsignificant
terrain terms cannot prove terrain independence. No result is interpreted
causally or extrapolated beyond the observed city and dates.

Figure map positions are jittered independently by a uniform offset between
-200 and +200 metres on each UTM axis. Figure source data round the jittered
longitude/latitude to 0.01 degrees and omit device IDs; exact plotting offsets
are reproducible from the internal panel and seed. Point size represents B1
mean flow. Published figure source data therefore do not expose exact device
locations. Grey crosses are failures; blue points are online devices and
grey dots other A100 devices.
'''
    (OUT / 'M4_METHODS.md').write_text(methods, encoding='utf-8')
    pending_note = OUT / 'PENDING.md'
    if pending_note.exists(): pending_note.unlink()
    attr_execution = json.loads((ROOT / '00_env/spatial_attributes_execution.json').read_text(encoding='utf-8'))
    write_json(ROOT / '00_env/spatial_deviations.json', {'definition_changes': [], 'pending': [],
               'implementation_notes': [attr_execution['town_method'], attr_execution['terrain_method'],
                                         'Baiguan UTM distance recomputed at full precision; one device ring differs from rounded pilot distances.',
                                         'Failure flags use prescribed previous-week denominators; pilot D3 spatial flags used same-weekday baseline instead.',
                                         'Moran directed neighbour selection shares the six-neighbour candidate count and self-exclusion algorithm with the M5 undirected join-count helper; all spatial outputs rerun in the full stage.'],
               'pilot_distance_ring_comparison': [{'group': ring, 'pilot': float(pilot),
                                                    'formal': float(tables['distance_ring'].set_index('group').loc[ring, 'flow_r_0726_online']),
                                                    'explanation': 'Formal B1 same-weekday and frozen A100 online set replace pilot B2/mean-baseline implementation.'}
                                                   for ring, pilot in zip(RINGS, [.709, .691, .603, .583, .507, .534])]})
    write_json(ROOT / '00_env/spatial_camera_execution.json', {'seed': SEED, 'status': 'complete',
               'completed_in': 'Full M4 run', 'started_epoch': started, 'ended_epoch': time.time(),
               'n_devices': len(p), 'ols_n_by_date': ols.groupby('date')['n'].first().to_dict()})
    write_json(ROOT / '00_env/spatial_execution.json', {'seed': SEED, 'bootstrap_B': B,
               'n_permutations': N_PERM, 'started_epoch': started, 'ended_epoch': time.time(),
               'input_files': ['01_panels/device_hour.csv', '01_panels/device_attributes.csv',
                               '01_panels/taxi_grid_day.csv', '01_panels/taxi_grid_centroids.csv'],
               'n_devices': len(p), 'n_A100': int(p['in_A100'].sum()), 'n_A200': int(p['in_A200'].sum()),
               'n_Sstar': int(p['in_Sstar'].sum()), 'n_taxi_grids': len(grid), 'n_paired_grids': len(paired),
               'ols_n_by_date': ols.groupby('date')['n'].first().to_dict(),
               'table_conventions': {'n_devices': 'A100 in group', 'off': 'Failure proportion among A200 in group',
                                     'flow_online': 'S_on(t) in group', 'flow_stable': 'S* in group',
                                     'elev_bins_m': '[-inf,5,10,20,50,inf)', 'relief_bins_m': '[-inf,3,10,30,inf)',
                                     'taxi_grid_eligibility': 'Mean B_TAXI daily n_points >=200, zero-count days included'},
               'outputs': [str(f.relative_to(ROOT)).replace('\\', '/') for f in sorted(OUT.glob('*'))] + ['08_figures/fig5_spatial.png', '08_figures/fig5_data.csv', '07_m6_robustness/m6_spatial_negative_control_ols.csv', '07_m6_robustness/m6_spatial_negative_control_gradient.csv']})
    print(json.dumps({'M4': 'complete', 'n_devices': len(p), 'n_paired_grids': len(paired), 'H3': verdict['status']}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--cameras-only', action='store_true')
    parser.add_argument('--stage', choices=['core', 'finish', 'all'], default='all',
                        help='core writes the actual camera analyses and explicitly pending taxi outputs; finish/all rerun core and compute real taxi-grid pairing')
    args = parser.parse_args()
    main(args.cameras_only or args.stage == 'core')
