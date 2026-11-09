# -*- coding: utf-8 -*-
"""Frozen spatial covariates. Source and pilot files are strictly read only.

Device identifiers are joined in memory to the private anonymous-ID map. Only
anonymous IDs are saved. Exact device coordinates remain in 01_panels.
"""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[2]), str(_ReleasePath(__file__).resolve().parents[0])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
import json
import argparse
import shutil
import time
import math
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy.spatial import cKDTree

ROOT = Path(_release_path('project_root'))
PILOT = Path(_release_path('path_009'))
PLACES = Path(_release_path('path_010'))
LOCATIONS = Path(_release_path('path_011'))
ROADS = Path(_release_path('path_002'))
TERRAIN = PILOT / 'ref/terrain'
SEED = 20261005
HIER = {'motorway': 'motorway/trunk', 'motorway_link': 'motorway/trunk',
        'trunk': 'motorway/trunk', 'trunk_link': 'motorway/trunk',
        'primary': 'primary', 'primary_link': 'primary',
        'secondary': 'secondary', 'secondary_link': 'secondary',
        'tertiary': 'tertiary', 'tertiary_link': 'tertiary',
        'residential': 'residential/service', 'service': 'residential/service',
        'living_street': 'residential/service', 'unclassified': 'unclassified/other'}


def stat(path):
    s = Path(path).stat()
    return {'path': str(path), 'size': s.st_size, 'mtime_ns': s.st_mtime_ns}


def terrain_values(lonlat):
    """Exact frozen pilot 9x9-pixel elevation/relief extraction, read only."""
    import tifffile
    arrays = {}
    missing = 0
    def value(lon, lat):
        nonlocal missing
        n = 2 ** 12
        fx_tile = (lon + 180.) / 360. * n
        lr = math.radians(lat)
        fy_tile = (1. - math.log(math.tan(lr) + 1. / math.cos(lr)) / math.pi) / 2. * n
        x, y = int(fx_tile), int(fy_tile)
        fn = TERRAIN / ('z12_' + str(x) + '_' + str(y) + '.tif')
        if not fn.exists():
            missing += 1
            return np.nan, np.nan
        if (x, y) not in arrays: arrays[(x, y)] = tifffile.imread(str(fn)).astype(float)
        arr = arrays[(x, y)]; h, w = arr.shape
        i = int(min(max((fy_tile - y) * h, 0), h - 1))
        j = int(min(max((fx_tile - x) * w, 0), w - 1))
        sub = arr[max(0, i - 4):i + 5, max(0, j - 4):j + 5]
        return float(arr[i, j]), float(sub.max() - sub.min())
    ev = [value(float(lo), float(la)) for lo, la in lonlat]
    return ev, missing, len(arrays)


def build_from_source():
    """Recompute all spatial fields on first valid actual source coordinates.

Run only after the active AVI reader has verified its attribute hash. This
function writes shared panels, so the coordinator owns execution ordering.
"""
    import geopandas as gpd
    from shapely.geometry import Point
    started = time.time()
    inputs = [LOCATIONS, PILOT / 'device_osm_attributes.csv', PILOT / 'device_terrain.csv',
              PILOT / 'township_centroids_osm.csv']
    for shp in [ROADS, PLACES]:
        inputs.extend([shp.with_suffix(s) for s in ['.shp', '.shx', '.dbf', '.prj', '.cpg'] if shp.with_suffix(s).exists()])
    inputs.extend(sorted(TERRAIN.glob('*.tif')))
    before = [stat(p) for p in inputs]
    mapping = pd.read_csv(ROOT / '01_panels/device_id_map.csv', dtype=str)
    raw = pd.read_csv(LOCATIONS, encoding='utf-8-sig', dtype=str)
    raw.columns = ['dev_name', 'lon', 'lat']
    raw['dev'] = raw['dev_name'].map(mapping.set_index('dev_name')['dev'])
    for c in ['lon', 'lat']: raw[c] = pd.to_numeric(raw[c], errors='coerce')
    raw.loc[raw['lon'].eq(0) | raw['lat'].eq(0), ['lon', 'lat']] = np.nan
    # Identical first-valid selection to panels_v1.py, per §2.1.
    loc = raw.dropna(subset=['dev', 'lon', 'lat']).drop_duplicates('dev').set_index('dev')
    cov = mapping[['dev']].set_index('dev').join(loc[['lon', 'lat']]).reset_index()
    valid = cov['lon'].between(100, 140) & cov['lat'].between(20, 60)
    cov.loc[~valid, ['lon', 'lat']] = np.nan
    trans = Transformer.from_crs(4326, 32651, always_xy=True)
    xy = np.column_stack(trans.transform(cov.loc[valid, 'lon'].values, cov.loc[valid, 'lat'].values))
    cams = gpd.GeoDataFrame(cov.loc[valid, ['dev']].set_index('dev'),
                            geometry=[Point(e, n) for e, n in xy], crs='EPSG:32651')
    roads = gpd.read_file(str(ROADS)).to_crs(32651)
    match = gpd.sjoin_nearest(cams[['geometry']], roads[['fclass', 'name', 'geometry']],
                              how='left', max_distance=80, distance_col='osm_road_dist_m')
    match = match.loc[~match.index.duplicated(keep='first')]
    m = match[['fclass', 'name', 'osm_road_dist_m']].rename(columns={'fclass': 'osm_fclass', 'name': 'osm_road_name'})
    cov = cov.join(m, on='dev')
    cov['road_level'] = cov['osm_fclass'].map(HIER).fillna('unclassified/other')
    cov.loc[cov['osm_fclass'].isna() & valid, 'road_level'] = 'no_road_within_80m'
    cov.loc[~valid, 'road_level'] = None
    places = gpd.read_file(str(PLACES), bbox=(120.4, 29.6, 121.3, 30.4), encoding='utf-8').to_crs(4326)
    towns = places.loc[places['fclass'].isin(['city', 'town'])].copy()
    town_xy = np.column_stack(trans.transform(towns.geometry.x.values, towns.geometry.y.values))
    td, ti = cKDTree(town_xy).query(xy)
    cov['near_town'] = None; cov['town_centre_dist_km'] = np.nan
    cov.loc[valid, 'near_town'] = towns['name'].values[ti]
    cov.loc[valid, 'town_centre_dist_km'] = td / 1000
    bg_rows = towns.loc[towns['name'].isin(['百官', '百官镇', '百官街道'])]
    if not len(bg_rows): raise RuntimeError('Frozen Baiguan OSM city/town point not found in source places')
    bg = bg_rows.iloc[0]
    bg_xy = np.array(trans.transform(bg.geometry.x, bg.geometry.y))
    cov['dist_baiguan_km'] = np.nan
    cov.loc[valid, 'dist_baiguan_km'] = np.linalg.norm(xy - bg_xy, axis=1) / 1000
    ev, terrain_missing, n_tiles = terrain_values(zip(cov.loc[valid, 'lon'], cov.loc[valid, 'lat']))
    cov['elev_m'] = np.nan; cov['relief_300m'] = np.nan
    cov.loc[valid, 'elev_m'] = [v[0] for v in ev]
    cov.loc[valid, 'relief_300m'] = [v[1] for v in ev]
    centres = pd.read_csv(PILOT / 'township_centroids_osm.csv', encoding='utf-8-sig')
    centres.loc[centres['town'].eq('百官'), ['lon', 'lat', 'fclass']] = [bg.geometry.x, bg.geometry.y, bg['fclass']]
    centre_ev, _, _ = terrain_values(zip(centres['lon'], centres['lat']))
    centres['elev_m'] = [v[0] for v in centre_ev]
    pilot_osm = pd.read_csv(PILOT / 'device_osm_attributes.csv', encoding='utf-8-sig').set_index('dev')
    prior = mapping['dev_name'].map(pilot_osm['dist_to_baiguan_km'])
    edges = [0, 2, 4, 7, 12, 20, np.inf]
    ring_changes = int((pd.cut(prior, edges, right=False).astype(str).ne(
                       pd.cut(cov['dist_baiguan_km'], edges, right=False).astype(str)) & valid & prior.notna()).sum())
    after = [stat(p) for p in inputs]
    if before != after: raise RuntimeError('Read-only source metadata changed during spatial reconstruction')
    cov.to_csv(ROOT / '01_panels/spatial_covariates.csv', index=False, encoding='utf-8-sig')
    centres.to_csv(ROOT / '01_panels/township_centroids_osm.csv', index=False, encoding='utf-8-sig')
    report = {'seed': SEED, 'started_epoch': started, 'ended_epoch': time.time(),
              'inputs_before': before, 'inputs_after': after, 'rows': len(cov),
              'n_coordinates': int(valid.sum()), 'n_city_town_points': len(towns), 'n_road_segments': len(roads),
              'places_filter': {'bbox_lon_lat': [120.4, 29.6, 121.3, 30.4], 'n_bbox_places': len(places),
                                'allowed_fclass': ['city', 'town'], 'n_candidates': len(towns),
                                'n_assigned_unique_names': int(cov.loc[valid, 'near_town'].nunique())},
              'n_terrain_missing_due_to_cache_coverage': terrain_missing, 'n_terrain_tiles_used': n_tiles,
              'n_source_coordinate_devices_absent_from_pilot_osm': int((valid & ~mapping['dev_name'].isin(pilot_osm.index)).sum()),
              'ring_assignments_changed_by_unrounded_distance': ring_changes,
              'baiguan_reference_lon_lat': [float(bg.geometry.x), float(bg.geometry.y)],
              'baiguan_source_name': str(bg['name']), 'baiguan_source_fclass': str(bg['fclass']),
              'distance_method': 'EPSG:32651 Euclidean distance on actual first-valid source coordinates',
              'coordinate_method': 'Filter 0 and NaN longitude/latitude before first device duplicate selection, same as formal panels stage',
              'road_method': 'Recomputed source OSM nearest roads within 80 m in UTM 51N on actual first-valid source coordinates',
              'terrain_method': 'Re-extracted fixed pilot 9x9-pixel approximately 300m-wide elevation/relief neighbourhood from 56 read-only cached Terrain Tiles, including newly coordinated devices',
              'town_method': 'Recomputed nearest OSM city/town from actual source places on actual first-valid source coordinates',
              'missing_coordinate_method': 'All spatial fields missing, not no_road_within_80m',
              'outputs': ['01_panels/spatial_covariates.csv', '01_panels/township_centroids_osm.csv']}
    (ROOT / '00_env/spatial_attributes_execution.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: report[k] for k in ['rows', 'n_coordinates', 'n_city_town_points', 'n_road_segments', 'n_terrain_tiles_used']}, ensure_ascii=False))


def build(refresh_places=False):
    started = time.time()
    inputs = [PILOT / 'device_osm_attributes.csv', PILOT / 'device_terrain.csv',
              PILOT / 'township_centroids_osm.csv']
    if refresh_places: inputs.append(PLACES)
    before = [stat(p) for p in inputs]
    mapping = pd.read_csv(ROOT / '01_panels/device_id_map.csv', dtype=str)
    osm = pd.read_csv(inputs[0], encoding='utf-8-sig')
    terrain = pd.read_csv(inputs[1], encoding='utf-8-sig')
    cov = mapping[['dev_name', 'dev']].merge(
        osm[['dev', 'lon', 'lat', 'road_level', 'osm_road_fclass',
             'osm_road_name', 'osm_road_dist_m', 'near_town_name', 'town_centre_dist_km']],
        left_on='dev_name', right_on='dev', how='left', suffixes=('', '_raw'))
    cov = cov.merge(terrain[['dev', 'elev_m', 'relief_300m']],
                    left_on='dev_name', right_on='dev', how='left',
                    suffixes=('', '_terrain_raw'))
    cov = cov.rename(columns={'osm_road_fclass': 'osm_fclass', 'near_town_name': 'near_town'})
    cov = cov.drop(columns=['dev_name', 'dev_raw', 'dev_terrain_raw'])
    valid = cov['lon'].between(100, 140) & cov['lat'].between(20, 60)
    cov.loc[~valid, ['lon', 'lat', 'road_level', 'osm_fclass',
                     'osm_road_name', 'osm_road_dist_m', 'elev_m',
                     'relief_300m']] = np.nan
    trans = Transformer.from_crs(4326, 32651, always_xy=True)
    xy = np.column_stack(trans.transform(cov.loc[valid, 'lon'].values,
                                         cov.loc[valid, 'lat'].values))
    centres = pd.read_csv(inputs[2], encoding='utf-8-sig')
    bg = centres.loc[centres['town'].eq('百官')].iloc[0]
    bg_xy = np.array(trans.transform(bg['lon'], bg['lat']))
    cov['dist_baiguan_km'] = np.nan
    cov.loc[valid, 'dist_baiguan_km'] = np.linalg.norm(xy - bg_xy, axis=1) / 1000
    old_dist = mapping['dev_name'].map(osm.set_index('dev')['dist_to_baiguan_km'])
    edges = [0, 2, 4, 7, 12, 20, np.inf]
    old_rings = pd.cut(old_dist, edges, right=False, include_lowest=True).astype(str)
    new_rings = pd.cut(cov['dist_baiguan_km'], edges, right=False, include_lowest=True).astype(str)
    ring_changes = int((old_rings.ne(new_rings) & valid).sum())
    # The frozen definition uses every OSM city/town in the bounding box,
    # rather than keyword attribution or only the list of 21 townships.
    n_towns = None
    if refresh_places:
        import geopandas as gpd
        places = gpd.read_file(str(PLACES), bbox=(120.4, 29.6, 121.3, 30.4), encoding='utf-8')
        towns = places.loc[places['fclass'].isin(['city', 'town'])].copy()
        town_xy = np.column_stack(trans.transform(towns.geometry.x.values,
                                                  towns.geometry.y.values))
        dist, idx = cKDTree(town_xy).query(xy)
        cov['near_town'] = None
        cov['town_centre_dist_km'] = np.nan
        cov.loc[valid, 'near_town'] = towns['name'].values[idx]
        cov.loc[valid, 'town_centre_dist_km'] = dist / 1000
        n_towns = len(towns)
    cov.to_csv(ROOT / '01_panels/spatial_covariates.csv', index=False, encoding='utf-8-sig')
    shutil.copyfile(inputs[2], ROOT / '01_panels/township_centroids_osm.csv')
    after = [stat(p) for p in inputs]
    if before != after:
        raise RuntimeError('Read-only source metadata changed during spatial attribute construction')
    report = {'seed': SEED, 'started_epoch': started, 'ended_epoch': time.time(),
              'inputs_before': before, 'inputs_after': after,
              'rows': len(cov), 'n_coordinates': int(valid.sum()),
              'n_city_town_points': n_towns,
              'ring_assignments_changed_by_unrounded_distance': ring_changes,
              'baiguan_reference_lon_lat': [float(bg['lon']), float(bg['lat'])],
              'distance_method': 'EPSG:32651 Euclidean distance, unrounded in internal panel',
              'road_method': 'Reused frozen pilot nearest OSM roads within 80 m (UTM 51N)',
              'terrain_method': 'Reused frozen pilot elevation and local relief from 9 x 9 Terrain Tile pixels (approximately 300 m-wide neighbourhood)',
              'town_method': 'Recomputed nearest OSM city/town' if refresh_places else 'Reused frozen pilot nearest OSM city/town identity and distance rounded to 0.01 km; no administrative attribution',
              'missing_coordinate_method': 'Spatial fields missing, not no_road_within_80m',
              'outputs': ['01_panels/spatial_covariates.csv', '01_panels/township_centroids_osm.csv']}
    (ROOT / '00_env/spatial_attributes_execution.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: report[k] for k in ['rows', 'n_coordinates', 'n_city_town_points']}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--refresh-places', action='store_true')
    parser.add_argument('--refresh-source', action='store_true',
                        help='Recompute all spatial fields from actual first-valid source coordinates, source roads/places and frozen cached terrain; coordinator must wait for AVI hash verification first')
    args = parser.parse_args()
    if args.refresh_source: build_from_source()
    else: build(args.refresh_places)
