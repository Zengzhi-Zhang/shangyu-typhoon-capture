# -*- coding: utf-8 -*-
"""Independent checks using existing aggregate tables only."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[3]), str(_ReleasePath(__file__).resolve().parents[1])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd

V1 = Path(_release_path('project_root'))
ROOT = V1 / "formal_v4"
OUT = ROOT / "10_supplementary_analyses"
quality = pd.read_csv(OUT / "t24_plate_quality_v4.csv")
old_summary = pd.read_csv(V1 / "01_panels/plate_day_summary.csv").set_index("date")
for scope, pc, nc in (("full_network", "plates", "records"), ("Sstar", "plates_Sstar", "records_Sstar")):
    sub = quality[(quality.scope == scope) & (quality.grp == "all")].set_index("date")
    assert np.array_equal(pd.to_numeric(sub.plates).values, old_summary.loc[sub.index, pc].values)
    assert np.array_equal(sub.records.values, old_summary.loc[sub.index, nc].values)
assert (quality.flag_plate_noise == (quality.singleton_deviation.abs() > 2.5 * quality.baseline_singleton_MAD)).all()
null = pd.read_csv(OUT / "t25_margin_null_distribution_v4.csv")
daily = pd.read_csv(V1 / "04_m3_vehicles/m3_daily_by_group.csv").set_index(["date", "grp"])
ordinary = null[null["sample"] == "ordinary_loo"]
error = []
for r in ordinary.itertuples(index=False):
    refs = r.baseline_dates.split(";")
    assert r.date not in refs and len(refs) == r.n_baseline_days
    assert all(pd.Timestamp(d).dayofweek == pd.Timestamp(r.date).dayofweek for d in refs)
    ratios = {}
    for grp in ("local_zheD", "other_province"):
        data = daily.xs(grp, level="grp")
        n, p = float(data.loc[r.date, "records"]), float(data.loc[r.date, "plates"])
        bn, bp = data.loc[refs, "records"].astype(float), data.loc[refs, "plates"].astype(float)
        ratios[grp] = dict(rP=p / bp.mean(), rN=n / bn.mean(), rm=(n / p) / (bn / bp).mean())
    for m in ("rP", "rm", "rN"):
        value = ratios["local_zheD"][m] - ratios["other_province"][m]
        error.append(abs(value - getattr(r, "delta_" + m)))
assert max(error) < .000051
contrast = pd.read_csv(OUT / "t25_typhoon_vs_envelope_v4.csv")
for r in contrast.itertuples(index=False):
    assert r.outside_envelope == (abs(r.delta_typhoon) > r.null_max_abs)
    assert r.exceeds_p975 == (abs(r.delta_typhoon) > r.null_abs_p975)
classified = pd.read_csv(OUT / "t26_robustness_by_class_v4.csv")
matrix = pd.read_csv(V1 / "formal_v3/07_m6_robustness/m6_robustness_matrix_v3.csv")
original = classified[classified.record_origin == "original_matrix"]
assert original.source_csv_row.tolist() == list(range(2, 812))
for c in matrix:
    a, b = original[c].reset_index(drop=True), matrix[c].reset_index(drop=True)
    pd.testing.assert_series_equal(a, b, check_dtype=False, check_names=False)
assert set(classified.class_item) >= {"C1", "C2", "C3", "C4"}
false_a = classified[(classified.robustness_class == "A") & (classified.sign_preserved == False)]
assert len(false_a) == 1 and false_a.source_csv_row.iloc[0] == 218
report = dict(status="passed", checked_at=datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
              source_raw_read=False, HMAC_key_read=False, panel_read=False,
              T24_all_full_and_stable_74_daily_count_checks_equal=True, T24_two_sided_MAD_flags_preserved=True,
              T25_ordinary_69_metrics_reproduced_max_abs_csv_rounding_error=max(error),
              T25_all_27_envelope_flags_reproduced=True, T26_all_810_original_rows_and_fields_equal=True,
              T26_C_four_items_complete=True, T26_A_non_sign_preserving_row218_retained=True)
path = ROOT / "00_env/supplement_independent_checks_v4.json"
path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(report, ensure_ascii=False))
