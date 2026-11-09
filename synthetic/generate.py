"""Generate fictional first-layer panels at the published sample sizes."""
from pathlib import Path
import argparse
import json
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

SEED = 20261005
N_DEVICE, N_A200, N_GEO, N_TAXI, N_STABLE = 1287, 1221, 1075, 290, 855
DATES = ['2021-06-17'] + pd.date_range('2021-06-28', '2021-08-02').strftime('%Y-%m-%d').tolist()
GPS_DATES = pd.date_range('2021-07-06', '2021-07-31').strftime('%Y-%m-%d').tolist()
BASELINE = [d for d in pd.date_range('2021-07-05', '2021-07-21').strftime('%Y-%m-%d') if d not in ['2021-07-08', '2021-07-10']]
EVENT = pd.date_range('2021-07-25', '2021-08-02').strftime('%Y-%m-%d').tolist()
TRAFFIC = dict(zip(EVENT, [.50, .62, .78, .95, .90, .91, .93, .94, .96]))


def capture_factor(site, date, hour, lane):
    """Hand-set fictional recording loss, unrelated to restricted records."""
    if date in ['2021-07-08', '2021-07-10'] and hour < 5:
        return 0.
    if date in ['2021-07-22', '2021-07-23', '2021-07-24']:
        return .85 if site >= N_DEVICE - 9 else 0.
    if date == '2021-07-07' and site < N_DEVICE - 252 and hour < 5:
        return 0.
    if date == '2021-07-25' and hour < 11:
        return 0.
    if date in EVENT:
        day = EVENT.index(date)
        if site < [100, 150, 90, 75, 65, 60, 55, 50, 45][day]:
            return 0.
        if 240 <= site < 300 and day <= 2 and lane == 2:
            return 0.
        if 300 <= site < 360 and day <= 1 and hour >= 10:
            return 0.
    return .9


def write_csv(frame, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding='utf-8', float_format='%.12g')


def generate(output):
    """Write fictional panels; do not read any research table or source file."""
    output = Path(output)
    panels = output / '01_panels'
    cache = output / 'formal_v6/01_internal'
    panels.mkdir(parents=True, exist_ok=True)
    cache.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)
    sites = [f'synsite{i:04d}' for i in range(1, N_DEVICE + 1)]
    taxis = [f'syntaxi{i:03d}' for i in range(1, N_TAXI + 1)]
    hours, lanes = [], []
    profile = .50 + .75 * np.exp(-((np.arange(24) - 8) / 3.) ** 2) + .60 * np.exp(-((np.arange(24) - 17) / 4.) ** 2)
    for site, dev in enumerate(sites):
        level = 42 + 3 * (site % 9) if site < N_A200 else 3.
        for date in DATES:
            weekday = pd.Timestamp(date).weekday()
            demand = TRAFFIC.get(date, 1.) * (1.06 if weekday < 5 else .91)
            lane_counts = []
            for lane in [1, 2]:
                factors = np.array([capture_factor(site, date, hour, lane) for hour in range(24)])
                lane_counts.append(np.maximum(rng.poisson(level * profile * demand * factors), (factors > 0).astype(int)))
            n = lane_counts[0] + lane_counts[1]
            unread = rng.binomial(n, .02)
            hours.extend((dev, date, hour, int(n[hour]), int(unread[hour])) for hour in range(24))
            lanes.extend((date, dev, 'other', str(lane), int(values.sum())) for lane, values in enumerate(lane_counts, 1))
    hourly = pd.DataFrame(hours, columns=['dev', 'date', 'hour', 'n', 'n_unread'])
    del hours
    daily = hourly.groupby(['dev', 'date'], sort=True)[['n', 'n_unread']].sum().reset_index()
    base = daily[daily.date.isin(BASELINE)].groupby('dev').n.mean()
    attrs = pd.DataFrame({
        'dev': sites, 'in_A100': 1,
        'in_A200': [int(i < N_A200) for i in range(N_DEVICE)],
        'in_Sstar': [int(200 <= i < 200 + N_STABLE) for i in range(N_DEVICE)],
        'base_B1': [float(base[d]) for d in sites],
        'lon': [round(123.00 + .01 * (i % 43), 2) if i < N_GEO else np.nan for i in range(N_DEVICE)],
        'lat': [round(10.00 + .01 * (i // 43), 2) if i < N_GEO else np.nan for i in range(N_DEVICE)],
        'org': ['Unit ' + chr(65 + i % 9) for i in range(N_DEVICE)],
        'road_level': ['primary' if i % 3 == 0 else 'secondary' for i in range(N_DEVICE)],
        'dist_baiguan_km': [float(i % 21) for i in range(N_DEVICE)],
        'elev_m': [float(5 + i % 8) for i in range(N_DEVICE)],
        'relief_300m': [float(i % 5) for i in range(N_DEVICE)],
        'gateway': [int(i % 10 == 0) for i in range(N_DEVICE)],
    })
    write_csv(hourly, panels / 'device_hour.csv')
    write_csv(daily, panels / 'device_day.csv')
    write_csv(pd.DataFrame(lanes, columns=['date', 'dev', 'dir', 'lane', 'n']), panels / 'device_dir_lane_day.csv')
    write_csv(attrs, panels / 'device_attributes.csv')
    write_csv(daily[daily.n >= daily.dev.map(base) * .2][['date', 'dev']], panels / 'online_sets.csv')
    # Fictional reference position, with the lookup label required by the reader.
    write_csv(pd.DataFrame([{'town': '百官', 'lon': 123.00, 'lat': 10.00}]), panels / 'township_centroids_osm.csv')
    gps_dir = cache / 'taxi_gps_points'
    gps_dir.mkdir(exist_ok=True)
    writer = None
    for vi, ph in enumerate(taxis):
        gps, avi = [], []
        for date in GPS_DATES:
            passes = max(1, int(np.rint(12 * TRAFFIC.get(date, 1.))))
            slots = np.rint(np.linspace(0, 11, passes)).astype(int)
            # 925 hand-chosen grid sites have exposure; all1075 stay in the cube.
            row = vi % 22
            columns = 43 if row < 21 else 22
            for slot in slots:
                start = pd.Timestamp(date) + pd.Timedelta(minutes=30 + 120 * int(slot), seconds=vi)
                for column in range(-1, columns):
                    timestamp = start + pd.Timedelta(seconds=(column + 1) * 30)
                    gps.append((timestamp, date, round(123.00 + .01 * column, 2), round(10.00 + .01 * row, 2), True, True, 132., 'E', True))
                    if 0 <= column < columns:
                        site = row * 43 + column
                        probability = (.90 if site < 329 else .08) * capture_factor(site, date, timestamp.hour, 1) / .9
                        if rng.random() < probability:
                            avi.append((ph, sites[site], date, int((timestamp - pd.Timestamp(date)).total_seconds()), 'other', '1'))
        pd.DataFrame(gps, columns=['timestamp', 'date', 'lon', 'lat', 'valid_xy', 'moving', 'speed', 'heading', 'occupied']).to_parquet(gps_dir / (ph + '.parquet'), index=False)
        chunk = pa.Table.from_pandas(pd.DataFrame(avi, columns=['ph', 'dev', 'date', 'sec_of_day', 'dir', 'lane']), preserve_index=False)
        if writer is None:
            writer = pq.ParquetWriter(cache / 'taxi_avi_records_v6.parquet', chunk.schema)
        writer.write_table(chunk)
    writer.close()
    features = []
    for row in range(25):
        features.append({'type': 'Feature', 'properties': {'name': f'Synthetic row {row + 1}', 'fclass': 'primary'}, 'geometry': {'type': 'LineString', 'coordinates': [[122.99, round(10.00 + .01 * row, 2)], [123.43, round(10.00 + .01 * row, 2)]]}})
    for column in range(43):
        features.append({'type': 'Feature', 'properties': {'name': f'Synthetic column {column + 1}', 'fclass': 'secondary'}, 'geometry': {'type': 'LineString', 'coordinates': [[round(123.00 + .01 * column, 2), 9.99], [round(123.00 + .01 * column, 2), 10.25]]}})
    (output / 'synthetic_roads.geojson').write_text(json.dumps({'type': 'FeatureCollection', 'features': features}, sort_keys=True, separators=(',', ':')), encoding='utf-8')
    schema = {'seed': SEED, 'cameras': N_DEVICE, 'A200': N_A200, 'A100_only': N_DEVICE - N_A200, 'geolocated_A200': N_GEO, 'Sstar': N_STABLE, 'taxis': N_TAXI, 'dates': DATES,
        'origin': 'Flows, loss, routes and positions are hand-set fiction. No confidential table was read or fitted.',
        'structure_provenance': 'Published manuscript Extended Data Table1 camera/probe counts; Methods eight control dates plus seven event GPS dates; published GPS date domain.',
        'public_structure_counts': {'pre_candidate': 252, 'control_exposed': 925, 'main_control_matchable': 329},
        'schema_from_code': ['analysis/v1/common_v1.py', 'analysis/v6/device_state_v6.py', 'analysis/v6/taxi_parse_v6.py', 'analysis/v7/health_screen_v7.py', 'analysis/v7/capture_wellmatched_v7.py', 'analysis/v9/capture_expected_v9.py'],
        'identifiers': 'synsite and syntaxi prefixes; no hexadecimal pseudonym format',
        'coordinates': 'Wholly fictional grid; stored positions have at most two decimal places'}
    (output / 'synthetic_schema.json').write_text(json.dumps(schema, sort_keys=True, indent=2), encoding='utf-8')
    return schema


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[1] / 'outputs/synthetic/inputs')
    generate(parser.parse_args().output)
