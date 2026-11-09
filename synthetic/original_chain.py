"""Wire fictional first-layer inputs into unchanged historical producers.

No estimator, matching rule, resampling rule or break-even formula is reimplemented
here. Simple renames/grouping below adapt generated panels to original IO schemas.
"""
from pathlib import Path
import importlib
import json
import os
import sys
import numpy as np
import pandas as pd


def csv(frame, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding='utf-8-sig', float_format='%.12g', na_rep='NA')


def fixture(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def install_read_guard(output):
    """Deny old project-data reads while the unchanged native chain runs."""
    repository = Path(__file__).resolve().parents[1]
    workspace = repository.parents[1]
    audit = {'native_project_data_read_operations': 0, 'denied_reads': 0, 'native_project_data_paths': set()}
    extensions = {'.csv', '.parquet', '.npz', '.json', '.geojson', '.xlsx', '.xls', '.txt'}
    def guard(event, args):
        if event != 'open' or not isinstance(args[0], (str, bytes, os.PathLike)):
            return
        mode = args[1]
        if isinstance(mode, str) and not ('r' in mode or '+' in mode):
            return
        if mode is None and isinstance(args[2], int) and args[2] & (os.O_WRONLY | os.O_RDWR):
            return
        path = Path(os.fsdecode(args[0])).resolve()
        if path.suffix.lower() not in extensions or not path.is_relative_to(workspace):
            return
        if not path.is_relative_to(repository):
            audit['denied_reads'] += 1
            raise RuntimeError('Read outside the synthetic repository refused')
        audit['native_project_data_read_operations'] += 1
        audit['native_project_data_paths'].add(path.relative_to(repository).as_posix())
    os.environ.pop('SHANGYU_HMAC_KEY_FILE', None)
    sys.addaudithook(guard)
    return audit


def prepare_protocols(inputs, output):
    v6, v7, v9 = inputs / 'formal_v6', inputs / 'formal_v7', output / 'formal_v9'
    for root in [v6, v7, v9]:
        for sub in ['00_env', '01_internal', '02_device_state', '03_taxi_probe', '05_bounds', '06_s_pre', '07_consequences', '08_figures']:
            (root / sub).mkdir(parents=True, exist_ok=True)
    identity = {'protocol_frozen': True, 'frozen_at': 'SYNTHETIC_INPUT_FIXTURE_NOT_AN_EXECUTION_TIME', 'seed': 20261005, 'scope': 'Fictional published-size demonstration only'}
    for root, name in [(v6, 'v6'), (v7, 'v7'), (v9, 'v9')]:
        fixture(root / f'00_env/protocol_frozen_{name}.json', identity)
    for name in ['interpretation_bias_v6.json', 'implementation_addendum_bias_v6.json', 'interpretation_spatial_v6.json']:
        fixture(v6 / '00_env' / name, {'synthetic_fixture': True})
    interpretation = {'synthetic_fixture': True, 'original_algorithms_unchanged': True}
    fixture(v7 / '00_env/interpretation_health_v7.json', interpretation)
    fixture(v7 / '00_env/interpretation_probe_bounds_v7.json', interpretation)
    fixture(v7 / '00_env/protocol_frozen_v7.json', {**identity, 'interpretations': {'interpretation_probe_bounds_v7.json': interpretation}})
    fixture(v9 / '00_env/input_manifest_v9.json', {'synthetic_fixture': True, 'inputs_generated_in_this_run': True})


def derived_taxi_panels(inputs):
    metrics = importlib.import_module('taxi_parse_v6')
    rings = importlib.import_module('taxi_ring_update_v6')
    from synthetic.generate import DATES
    cache = inputs / 'formal_v6/01_internal'
    attrs = pd.read_csv(inputs / '01_panels/device_attributes.csv').set_index('dev')
    all_rows = []
    aliases = []
    for path in sorted((cache / 'taxi_gps_points').glob('*.parquet')):
        points = pd.read_parquet(path)
        aliases.append(path.stem)
        rows = pd.DataFrame(metrics.daily_metrics(points, path.stem)).set_index('date')
        calibrated = pd.DataFrame(rings.calibrated_ring_rows(points, {'selected_method': 'raw_WGS84'})).set_index('date')
        for column in calibrated:
            rows[column] = calibrated[column]
        for hour in range(24):
            counts = points[points.timestamp.dt.hour.eq(hour)].groupby('date').size()
            rows[f'pts_h{hour:02d}'] = counts.reindex(rows.index, fill_value=0)
            rows[f'mov_h{hour:02d}'] = counts.reindex(rows.index, fill_value=0)
        all_rows.append(rows.reset_index())
    daily = pd.concat(all_rows, ignore_index=True)
    csv(daily, cache / 'taxi_vehicle_day_v6.csv')
    taxi = daily.rename(columns={'vehicle_ph': 'vehicle_hash', 'date': 'sheet_date'})
    taxi['batch'] = 'GPS0706-0731'
    csv(taxi, inputs / '01_panels/taxi_vehicle_day.csv')
    (cache / 'taxi_probe_ph_v6.txt').write_text('\n'.join(aliases) + '\n', encoding='utf-8')
    avi = pd.read_parquet(cache / 'taxi_avi_records_v6.parquet')
    avi['stable'] = avi.dev.map(attrs.in_Sstar).fillna(0).astype(int)
    avi['gateway'] = avi.dev.map(attrs.gateway).fillna(0).astype(int)
    plate = avi.groupby(['ph', 'date']).agg(n=('ph', 'size'), n_stable=('stable', 'sum'), n_gw=('gateway', 'sum')).reset_index()
    plate.to_parquet(cache / 'taxi_plate_day_v6.parquet', index=False)
    seen = avi.groupby('date').ph.nunique()
    stable_seen = avi[avi.stable.eq(1)].groupby('date').ph.nunique()
    panel = pd.DataFrame({'date': DATES})
    panel['plates'] = panel.date.map(seen).fillna(0).astype(int)
    panel['plates_on_stable'] = panel.date.map(stable_seen).fillna(0).astype(int)
    csv(panel, inputs / '01_panels/plate_day_summary.csv')
    fixture(inputs / 'formal_v6/00_env/hash_check_v6.json', {'n_probe': len(aliases), 'S1_triggered': len(set(aliases)) < 250, 'acceptance_ge250': len(set(aliases)) >= 250, 'scope': 'Generated syn aliases, no key or HMAC read'})
    # Capture metadata only: no claim that the historical I3 calibration/grid
    # diagnostic was run on these fictional positions.
    fixture(inputs / 'formal_v6/03_taxi_probe/T29_calibration_v6.json', {'selected_method': 'raw_WGS84', 'calibration_status': 'synthetic_hand_set_raw_reference_not_I3_validation', 'S2': None, 'S3': None})
    return avi


def independent_v6_reference(inputs, cameras):
    """Build the old-interface reference with original v6 pure matching helpers."""
    from scipy.spatial import cKDTree
    capture = importlib.import_module('capture_rate_v6')
    cache = inputs / 'formal_v6/01_internal'
    days = ['2021-07-19', '2021-07-26', '2021-07-27', '2021-07-28']
    avi = pd.read_parquet(cache / 'taxi_avi_records_v6.parquet')
    avi = avi[avi.date.isin(days)]
    observed = {(ph, day, dev): np.sort(g.sec_of_day.to_numpy(float)) for (ph, day, dev), g in avi.groupby(['ph', 'date', 'dev'], sort=False)}
    xy = np.column_stack(capture.PROJECT.transform(cameras.lon.to_numpy(), cameras.lat.to_numpy()))
    tree = cKDTree(xy)
    result = {day: np.zeros((len(cameras), 2), dtype=np.int64) for day in days}
    for path in sorted((cache / 'taxi_gps_points').glob('*.parquet')):
        gps = pd.read_parquet(path)
        for day in days:
            events = capture.segment_events(gps[gps.date.eq(day)], xy, tree, {'selected_method': 'raw_WGS84'})
            if not len(events):
                continue
            for ci, group in pd.DataFrame(events, columns=['camera', 'second', 'distance']).groupby('camera', sort=False):
                ci = int(ci)
                expected = capture.dedup_expected(group.loc[group.distance.le(60), 'second'].to_numpy())
                recorded = observed.get((path.stem, day, cameras.iloc[ci].dev), np.empty(0))
                expected_n, captured_n, _ = capture.capture_counts(expected, recorded, 180)
                result[day][ci] += [expected_n, captured_n]
    rows = []
    for day in days:
        for ci, camera in cameras.iterrows():
            rows.append({'date': day, 'dev': int(camera.dev_public), 'expected': result[day][ci, 0], 'captured': result[day][ci, 1]})
    csv(pd.DataFrame(rows), cache / 'camera_capture_unmasked_v6.csv')


def run_original_chain(inputs, output):
    read_audit = install_read_guard(output)
    prepare_protocols(inputs, output)
    derived_taxi_panels(inputs)
    m1 = importlib.import_module('m1_m2_v1')
    oldbias = importlib.import_module('m5_bias_v1')
    bias = oldbias.Run(inputs)
    bias.load()
    bias.failure_counts()
    m1.main()
    bias.visible_bias()
    newbias = importlib.import_module('m5_bias_v3')
    revised = newbias.Run()
    revised.load()
    revised.counts()
    revised.visible()
    spatial = importlib.import_module('spatial_helpers_v6')
    states6 = importlib.import_module('device_state_v6')
    protocol6 = inputs / 'formal_v6/00_env/protocol_frozen_v6.json'
    states6.main(protocol6)
    panels = spatial.Panels()
    # Produce the Sstar comparator model with the original fitting function on
    # the generated Sstar members; only the interface sample label is adapted.
    models = []
    for day in ['2021-07-26', '2021-07-27', '2021-07-28']:
        n, b = panels.vectors(day, matched=False)
        ratios = np.divide(n, b, out=np.full(panels.n_dev, np.nan), where=b > 0)
        model = spatial.fit_ols(panels.attr, ratios, panels.Sstar, day)
        model['sample'] = 'Sstar'
        models.append(model)
    csv(pd.concat(models, ignore_index=True), inputs / 'formal_v3/05_m4_spatial/m4_ols_v3.csv')
    pre = importlib.import_module('s_pre_v6')
    pre.main(protocol6)
    health = importlib.import_module('health_screen_v7')
    protocol7 = inputs / 'formal_v7/00_env/protocol_frozen_v7.json'
    health.main(protocol7, 'all')
    capture = importlib.import_module('capture_wellmatched_v7')
    cameras = capture.load_attrs()
    cameras = cameras[cameras.in_A200 & cameras.lon.notna() & cameras.lat.notna()].reset_index(drop=True)
    capture.build_counts(cameras)
    independent_v6_reference(inputs, cameras)
    capture.main()
    cap6 = importlib.import_module('capture_rate_v6')
    cap6.ring_records(pd.read_parquet(inputs / 'formal_v6/01_internal/taxi_avi_records_v6.parquet'), pd.read_csv(inputs / '01_panels/device_attributes.csv'))
    probe = importlib.import_module('probe_daily_v6')
    probe.main()
    bounds = importlib.import_module('bounds_v6')
    bounds.run(protocol6, capture=None)
    relative = importlib.import_module('probe_bounds_v7')
    relative.run(protocol7, True)
    assembly = importlib.import_module('t37_tables_v7')
    assembly.tables()
    decomp = importlib.import_module('decomp_v9')
    argv = sys.argv
    historical = None
    try:
        sys.argv = ['decomp_v9.py', '--run']
        decomp.main()
    except AssertionError as error:
        if str(error) != 'Prespecified checks not all reached; outputs retained unchanged':
            raise
        path = output / 'formal_v9/02_decomposition/T38_checks_v9.json'
        if not path.exists():
            raise
        record = json.loads(path.read_text(encoding='utf-8'))
        failed = [name for name, value in record['checks'].items() if not value]
        if not failed or not set(failed).issubset({'T38_0726', 'T38_0802'}):
            raise
        required = ['T39_breakeven_v9.csv', 'T39_sustained_v9.csv']
        if not all((output / 'formal_v9/03_breakeven' / name).is_file() for name in required):
            raise
        historical = {'entry_point': 'analysis/v9/decomp_v9.py::main', 'original_main_passed': False, 'original_exception': 'AssertionError', 'original_exception_message': str(error), 'failed_historical_checks': failed, 'scientific_outputs_written_before_failure': True, 'other_original_checks_passed': True}
    finally:
        sys.argv = argv
    expected = importlib.import_module('capture_expected_v9')
    expected.run()
    family = pd.read_csv(inputs / 'formal_v7/07_consequences/T37_estimator_family_v7.csv')
    recovery = importlib.import_module('consequences_v6')
    sustained = []
    for name, frame in family.groupby('estimator', sort=True):
        frame = frame.sort_values('date')
        if name == 'R_probe':
            frame = frame[frame.date.le('2021-07-31')]
        for theta in recovery.THETAS:
            sustained.append({'estimator': name, 'theta': theta, **recovery.recovery(frame.R.to_numpy(), frame.date.tolist(), theta)})
    csv(pd.DataFrame(sustained), output / 'results/sustained_recovery.csv')
    required_family = ['R_naive', 'R_health', 'R_online', 'R_stable', 'R_health_strict', 'R_spre_health', 'R_upper', 'R_probe']
    frame = family[family.estimator.isin(required_family)]
    csv(frame, output / 'results/Table1_daily_estimator_family.csv')
    be = pd.read_csv(output / 'formal_v9/03_breakeven/T39_breakeven_v9.csv')
    exp = pd.read_csv(output / 'formal_v9/04_expected_capture/T40_expected_capture_v9.csv')
    wide = frame.pivot(index='date', columns='estimator', values='R').reset_index()
    summary = wide.merge(exp[['date', 'E', 'C', 'C_over_E']], on='date', how='left')
    for theta in recovery.THETAS:
        selected = be[be.theta.eq(theta)][['date', 'class']].rename(columns={'class': f'critical_recovery_class_{theta:.2f}'})
        summary = summary.merge(selected, on='date', how='left')
    summary['data_notice'] = 'SYNTHETIC DATA; DO NOT COMPARE WITH PAPER VALUES'
    csv(summary, output / 'synthetic_summary.csv')
    record = {'core_chain_claim': 'awaits_independent_validation', 'Table1_rows': len(frame), 'Table1_families': required_family, 'T37_rows': len(family), 'T40_rows': len(exp), 'T39_rows': len(be), 'T39_sustained_rows': len(pd.read_csv(output / 'formal_v9/03_breakeven/T39_sustained_v9.csv')), 'sustained_rows': len(sustained), 'historical_main_failure': historical,
        'original_producers': ['m1_m2_v1.main', 'm5_bias_v1.Run.visible_bias', 'm5_bias_v3.Run.visible', 'device_state_v6.main', 's_pre_v6.main', 'health_screen_v7.main', 'capture_wellmatched_v7.build_counts/main', 'capture_rate_v6.segment_events/capture_counts/ring_records', 'probe_daily_v6.main', 'bounds_v6.run', 'probe_bounds_v7.run', 't37_tables_v7.tables', 'decomp_v9.main', 'capture_expected_v9.run', 'consequences_v6.recovery'],
        'historical_capture_reference': 'Same-run original v6 pure geometry/matching functions; no historical real table was copied', 'timestamps': 'Original producer clocks and input signatures retained unchanged; all-output SHA comparison must include them'}
    fixture(output / 'chain_status.json', record)
    fixture(output / 'native_read_guard_audit.json', {**read_audit, 'native_project_data_paths': sorted(read_audit['native_project_data_paths']), 'scope': 'Native producer chain after fictional input generation; source/key/workbooks never accessed', 'HMAC_environment_cleared': True})
    return record
