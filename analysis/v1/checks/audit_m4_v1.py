# -*- coding: utf-8 -*-
"""Independent definition-based checks of final M4 delivery tables.

Reads local formal panels only. It does not inspect or modify source files,
and writes a compact audit report with no raw device or vehicle identifiers.
"""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[3]), str(_ReleasePath(__file__).resolve().parents[1])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
import json
from pathlib import Path
import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy.stats import spearmanr
import statsmodels.formula.api as smf
from jsonschema import Draft202012Validator

ROOT = Path(_release_path('project_root'))
SEED = 20261005
np.random.seed(SEED)
B1 = pd.date_range('2021-07-05', '2021-07-21').difference(pd.to_datetime(['2021-07-08', '2021-07-10']))
B_TAXI = pd.date_range('2021-07-06', '2021-07-21')
TARGETS = ['2021-07-26', '2021-07-27', '2021-07-28']
TRANS = Transformer.from_crs(4326, 32651, always_xy=True)


def main():
    checks = {}
    def check(name, passed, details=None):
        checks[name] = {'passed': bool(passed), 'details': details}
    h = pd.read_csv(ROOT / '01_panels/device_hour.csv')
    h['date'] = pd.to_datetime(h['date'].astype(str).str.replace('"', '', regex=False))
    attr = pd.read_csv(ROOT / '01_panels/device_attributes.csv').set_index('dev')
    d = h.groupby(['dev', 'date'])['n'].sum().unstack(fill_value=0).reindex(attr.index, fill_value=0)
    out = pd.read_csv(ROOT / '05_m4_spatial/m4_device_ratios.csv').set_index('dev')
    check('device_id_coverage', set(out.index) == set(attr.index) and out.index.is_unique)
    check('public_device_coordinates', all(np.allclose(out[c].dropna() * 100,
                                                    np.round(out[c].dropna() * 100)) for c in ['lon', 'lat']))
    check('anonymous_device_identifiers', out.index.to_series().str.startswith('cam_').all())
    baselines = {}
    for day in TARGETS + ['2021-08-02']:
        t = pd.Timestamp(day)
        b = d[[x for x in B1 if x.dayofweek == t.dayofweek]].mean(axis=1)
        baselines[day] = b
        expected = d[t] / b.replace(0, np.nan)
        got = out['r_' + t.strftime('%m%d')].reindex(attr.index)
        check('device_ratio_' + day, np.allclose(got, expected, atol=.000051, rtol=0, equal_nan=True))
        if day in ['2021-07-26', '2021-07-28', '2021-08-02']:
            failed = d[t].lt(.05 * d[t - pd.Timedelta(days=7)])
            act = attr.index[attr['in_A200'].eq(1)]
            check('previous_week_failure_' + day, np.array_equal(out.loc[act, 'off_' + t.strftime('%m%d')].to_numpy(), failed.loc[act].astype(int).to_numpy()))
    pm = h.loc[h['hour'].between(11, 23)].groupby(['dev', 'date'])['n'].sum().unstack(fill_value=0).reindex(attr.index, fill_value=0)
    b25 = pm[[x for x in B1 if x.dayofweek == 6]].mean(axis=1)
    expected25 = pm[pd.Timestamp('2021-07-25')] / b25.replace(0, np.nan)
    check('july25_hour_matched_ratio', np.allclose(out['r_0725h'].reindex(attr.index), expected25,
                                                 atol=.000051, rtol=0, equal_nan=True))
    # The published regression table must correspond to the frozen formula
    # on current complete-case source attributes, not old rounded attributes.
    ols = pd.read_csv(ROOT / '05_m4_spatial/m4_ols.csv')
    for day in TARGETS:
        t = pd.Timestamp(day)
        x = attr.loc[attr['in_Sstar'].eq(1) & attr['lon'].notna() & attr['lat'].notna()].copy()
        x['response'] = np.log((d[t] / baselines[day].replace(0, np.nan)).reindex(x.index).clip(.05, 3))
        x['log_base'] = np.log(x['base_B1'].where(x['base_B1'] > 0))
        x = x.replace([np.inf, -np.inf], np.nan).dropna(subset=['response', 'log_base', 'dist_baiguan_km', 'elev_m', 'relief_300m', 'road_level', 'org', 'gateway'])
        fit = smf.ols('response ~ np.log1p(dist_baiguan_km) + log_base + elev_m + relief_300m + C(road_level) + C(org) + gateway', data=x).fit(cov_type='HC1')
        got = ols.loc[ols['date'].eq(day)].set_index('term')
        check('OLS_HC1_' + day, got.index.equals(fit.params.index) and np.allclose(got['coef'], fit.params, atol=1e-9, rtol=1e-8)
              and np.allclose(got['se_HC1'], fit.bse, atol=1e-9, rtol=1e-8)
              and np.allclose(got['p'], fit.pvalues, atol=1e-9, rtol=1e-8)
              and got['n'].eq(int(fit.nobs)).all(), {'n': int(fit.nobs)})
    tg = pd.read_csv(ROOT / '01_panels/taxi_grid_day.csv')
    tg['date'] = pd.to_datetime(tg['date'])
    tp = tg.pivot_table(index=['gx', 'gy'], columns='date', values='n_points', aggfunc='sum', fill_value=0)
    mean = tp.reindex(columns=B_TAXI, fill_value=0).mean(axis=1)
    grid = pd.read_csv(ROOT / '05_m4_spatial/m4_taxi_grid_ratio.csv').set_index(['gx', 'gy'])
    check('grid_eligibility_B_TAXI_200', set(grid.index) == set(mean.index[mean.ge(200)]), {'eligible_grids': len(grid)})
    check('grid_baseline_fixed_16_days', np.allclose(grid['n_base_points'], mean.reindex(grid.index), atol=.000051, rtol=0))
    check('public_grid_coordinates', all(np.allclose(grid[c].dropna() * 100, np.round(grid[c].dropna() * 100)) for c in ['lon', 'lat']))
    cameras = attr.loc[attr['in_Sstar'].eq(1) & attr['lon'].notna() & attr['lat'].notna()].copy()
    e, n = TRANS.transform(cameras['lon'].values, cameras['lat'].values)
    cameras['gx'], cameras['gy'] = np.floor(e / 1000).astype(int), np.floor(n / 1000).astype(int)
    pair = pd.read_csv(ROOT / '05_m4_spatial/m4_taxi_vs_camera_grid.csv').set_index(['gx', 'gy'])
    expected_pair = set(grid.index).intersection(set(zip(cameras['gx'], cameras['gy'])))
    check('paired_grid_intersection', set(pair.index) == expected_pair, {'paired_grids': len(pair)})
    correlations = json.loads((ROOT / '05_m4_spatial/m4_taxi_camera_spearman.json').read_text(encoding='utf-8'))
    gradients = pd.read_csv(ROOT / '05_m4_spatial/m4_taxi_camera_gradient.csv')
    for day in TARGETS:
        t = pd.Timestamp(day); label = t.strftime('%m%d')
        b = tp.reindex(columns=[x for x in B_TAXI if x.dayofweek == t.dayofweek], fill_value=0).mean(axis=1)
        taxi_ratio = tp.reindex(columns=[t], fill_value=0)[t] / b.replace(0, np.nan)
        check('taxi_same_weekday_ratio_' + day, np.allclose(grid['r_taxi_pts_' + label], taxi_ratio.reindex(grid.index), atol=.000051, rtol=0, equal_nan=True))
        cameras['n'] = d[t].reindex(cameras.index); cameras['b'] = baselines[day].reindex(cameras.index)
        cg = cameras.groupby(['gx', 'gy'])[['n', 'b']].sum()
        camera_ratio = cg['n'] / cg['b'].replace(0, np.nan)
        check('paired_camera_ratio_' + day, np.allclose(pair['r_camera_' + label], camera_ratio.reindex(pair.index), atol=.000051, rtol=0, equal_nan=True))
        exact = pd.DataFrame({'taxi': taxi_ratio.reindex(pair.index), 'camera': camera_ratio.reindex(pair.index),
                              'distance': pair['dist_baiguan_km']}).dropna()
        # Use the exact grid-centre distance, as published CSV distances have
        # four decimal places which can introduce rank ties at a boundary.
        bg = pd.read_csv(ROOT / '01_panels/township_centroids_osm.csv').query("town == '百官'").iloc[0]
        centre = np.array(TRANS.transform(bg['lon'], bg['lat']))
        exact['distance'] = np.linalg.norm(np.column_stack([(exact.index.get_level_values('gx') + .5) * 1000,
                                                            (exact.index.get_level_values('gy') + .5) * 1000]) - centre, axis=1) / 1000
        for key, a, bval in [('spearman_taxi_camera', exact['taxi'], exact['camera']),
                             ('spearman_dist_taxi', exact['distance'], exact['taxi']),
                             ('spearman_dist_camera', exact['distance'], exact['camera'])]:
            rho, pval = spearmanr(a, bval); got = correlations[label][key]
            check(key + '_' + day, np.isclose(rho, got['rho'], atol=1e-12) and np.isclose(pval, got['p'], atol=1e-12))
        check('spearman_n_' + day, correlations[label]['n_grids'] == len(exact))
        rings = pd.cut(exact['distance'], [0, 2, 4, 7, 12, 20, np.inf],
                       labels=['0-2', '2-4', '4-7', '7-12', '12-20', '20+'], right=False, include_lowest=True)
        gd = gradients.loc[gradients['date'].eq(day)].set_index('distance_ring')
        points = tp.reindex(columns=[t], fill_value=0)[t]
        for ring in ['0-2', '2-4', '4-7', '7-12', '12-20', '20+']:
            ids = exact.index[rings.eq(ring)]
            tr = points.reindex(ids).sum() / b.reindex(ids).sum() if b.reindex(ids).sum() > 0 else np.nan
            cr = cg['n'].reindex(ids).sum() / cg['b'].reindex(ids).sum() if cg['b'].reindex(ids).sum() > 0 else np.nan
            check('paired_gradient_' + day + '_' + ring, gd.loc[ring, 'n_grids'] == len(ids)
                  and np.isclose(gd.loc[ring, 'r_taxi_pts'], tr, atol=.000051, rtol=0, equal_nan=True)
                  and np.isclose(gd.loc[ring, 'r_camera'], cr, atol=.000051, rtol=0, equal_nan=True))
    figdata = pd.read_csv(ROOT / '08_figures/fig5_data.csv')
    check('figure_data_no_device_ids', 'dev' not in figdata)
    check('figure_jitter_data_rounded', all(np.allclose(figdata[c].dropna() * 100, np.round(figdata[c].dropna() * 100)) for c in ['plot_lon', 'plot_lat']))
    check('figure_map_point_count', figdata['panel'].eq('map').sum() == 2 * int((attr['in_A100'].eq(1) & attr['lon'].notna() & attr['lat'].notna()).sum()))
    check('no_pending_note', not (ROOT / '05_m4_spatial/PENDING.md').exists())
    verdict = json.loads((ROOT / '05_m4_spatial/m4_h3_verdict.json').read_text(encoding='utf-8'))
    check('final_H3_status', verdict['status'] in ['pass', 'fail', 'degraded'])
    schema = json.loads((ROOT / 'scripts/m4_h3_schema_v1.json').read_text(encoding='utf-8'))
    schema_errors = [e.message for e in Draft202012Validator(schema).iter_errors(verdict)]
    check('H3_schema', not schema_errors, schema_errors)
    check('H3_no_invented_stop_rule', verdict['automatic_stop_condition'] is None)
    result = {'seed': SEED, 'source_io': 'None; local formal panels only',
              'passed': all(x['passed'] for x in checks.values()), 'checks': checks}
    (ROOT / '00_env/m4_independent_audit.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'M4_audit': result['passed'], 'n_checks': len(checks), 'failed': [k for k, v in checks.items() if not v['passed']]}, ensure_ascii=False))
    if not result['passed']: raise RuntimeError('M4 definition audit failed; inspect anonymous audit report')


if __name__ == '__main__':
    main()
