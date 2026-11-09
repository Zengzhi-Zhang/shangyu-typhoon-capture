# -*- coding: utf-8 -*-
"""Read-only equivalence audit of reused spatial attributes on source coordinates."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[3]), str(_ReleasePath(__file__).resolve().parents[1])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
import json
from pathlib import Path
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point

ROOT = Path(_release_path('project_root'))
ROADS = Path(_release_path('path_002'))
SEED = 20261005
np.random.seed(SEED)
HIER = {'motorway': 'motorway/trunk', 'motorway_link': 'motorway/trunk',
        'trunk': 'motorway/trunk', 'trunk_link': 'motorway/trunk',
        'primary': 'primary', 'primary_link': 'primary',
        'secondary': 'secondary', 'secondary_link': 'secondary',
        'tertiary': 'tertiary', 'tertiary_link': 'tertiary',
        'residential': 'residential/service', 'service': 'residential/service',
        'living_street': 'residential/service', 'unclassified': 'unclassified/other'}


def source_stat(path):
    s = path.stat()
    return {'path': str(path), 'size': s.st_size, 'mtime_ns': s.st_mtime_ns}


def text_value(v):
    return '' if pd.isna(v) else str(v)


def main():
    source_files = [ROADS.with_suffix(s) for s in ['.shp', '.shx', '.dbf', '.prj', '.cpg'] if ROADS.with_suffix(s).exists()]
    before = [source_stat(p) for p in source_files]
    attr = pd.read_csv(ROOT / '01_panels/device_attributes.csv').set_index('dev')
    cov = pd.read_csv(ROOT / '01_panels/spatial_covariates.csv').set_index('dev').reindex(attr.index)
    equal_xy = np.isclose(attr[['lon', 'lat']], cov[['lon', 'lat']], atol=1e-12, rtol=0, equal_nan=True).all(axis=1)
    valid = attr['lon'].between(100, 140) & attr['lat'].between(20, 60)
    delta = np.abs(attr[['lon', 'lat']].to_numpy() - cov[['lon', 'lat']].to_numpy())
    max_delta = float(np.nanmax(delta)) if np.isfinite(delta).any() else None
    cams = gpd.GeoDataFrame(attr.loc[valid].copy(),
                            geometry=[Point(lo, la) for lo, la in zip(attr.loc[valid, 'lon'], attr.loc[valid, 'lat'])],
                            crs='EPSG:4326').to_crs(32651)
    roads = gpd.read_file(str(ROADS)).to_crs(32651)
    nearest = gpd.sjoin_nearest(cams[['geometry']], roads[['fclass', 'name', 'geometry']],
                                how='left', distance_col='source_road_dist_m', max_distance=80)
    road_mismatches = []
    max_rounding_diff = 0.
    tie_devices = 0
    for dev, matches in nearest.groupby(level=0):
        if len(matches) > 1: tie_devices += 1
        expected = cov.loc[dev]
        accepted = False
        for _, row in matches.iterrows():
            fclass = text_value(row['fclass']); name = text_value(row['name'])
            level = HIER.get(fclass, 'unclassified/other') if fclass else 'no_road_within_80m'
            rd = row['source_road_dist_m']; cached = expected['osm_road_dist_m']
            distance_ok = (pd.isna(rd) and pd.isna(cached)) or (pd.notna(rd) and pd.notna(cached) and abs(rd - cached) <= .050001)
            if pd.notna(rd) and pd.notna(cached): max_rounding_diff = max(max_rounding_diff, abs(float(rd - cached)))
            candidate_ok = (level == text_value(expected['road_level']) and fclass == text_value(expected['osm_fclass'])
                            and name == text_value(expected['osm_road_name']) and distance_ok)
            accepted |= candidate_ok
        if not accepted: road_mismatches.append(dev)
    after = [source_stat(p) for p in source_files]
    report = {'seed': SEED, 'passed': bool(equal_xy.all() and not road_mismatches and before == after),
              'coordinate_origin': 'Current device_attributes.csv is sourced from actual sensor_location.csv by the formal panels stage',
              'coordinate_comparison': {'n_devices': len(attr), 'n_coordinates': int(valid.sum()),
                                        'tolerance_degrees': 1e-12, 'n_mismatches': int((~equal_xy).sum()),
                                        'max_absolute_difference_degrees': max_delta,
                                        'mismatch_anonymous_device_ids': attr.index[~equal_xy].tolist()},
              'road_reconstruction': {'n_source_segments': len(roads), 'crs': 'EPSG:32651', 'max_nearest_distance_m': 80,
                                      'n_devices_compared': len(cams), 'n_exact_distance_ties': tie_devices,
                                      'n_mismatches': len(road_mismatches), 'mismatch_anonymous_device_ids': road_mismatches,
                                      'maximum_distance_difference_due_to_cached_0_1m_rounding': max_rounding_diff,
                                      'tie_rule': 'Cached fclass, name and hierarchy must match one of the equally nearest source road candidates',
                                      'no_coordinate_devices': 'Excluded from road reconstruction; spatial fields remain missing'},
              'source_before': before, 'source_after': after, 'source_unchanged': before == after,
              'shared_attribute_files_modified': False}
    (ROOT / '00_env/spatial_source_equivalence.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'equivalent': report['passed'], 'coordinate_mismatches': int((~equal_xy).sum()),
                      'road_mismatches': len(road_mismatches), 'segments': len(roads)}, ensure_ascii=False))
    if not report['passed']: raise RuntimeError('Source and cached spatial attributes differ; do not modify locked shared attributes while AVI runs')


if __name__ == '__main__':
    main()
