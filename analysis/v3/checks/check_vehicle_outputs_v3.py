# -*- coding: utf-8 -*-
"""Independent aggregate-table check of vehicle point estimates; no panel reads."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[3]), str(_ReleasePath(__file__).resolve().parents[1]), str(_ReleasePath(__file__).resolve().parent)]
import numpy as np
import pandas as pd
from common_v3 import ROOT, V1, B_P, now, write_json

old = pd.read_csv(V1 / "04_m3_vehicles/m3_daily_by_group.csv")
new = pd.read_csv(ROOT / "04_m3_vehicles/m3_placebo_by_group_v3.csv")
main = new[(new.placebo_baseline == "B_P") & (new.powertrain_scope == "all_powertrains") & (new.placebo_hours == "all_day")]
errors = []
for row in main.itertuples(index=False):
    data = old[old.grp == row.grp].set_index("date")
    refs = [d for d in B_P if pd.Timestamp(d).dayofweek == pd.Timestamp(row.date_placebo).dayofweek]
    n, p = data.loc[row.date_placebo, ["records", "plates"]].astype(float).values
    bn = data.loc[refs, "records"].astype(float).mean()
    bp = data.loc[refs, "plates"].astype(float).mean()
    bm = (data.loc[refs, "records"].astype(float) / data.loc[refs, "plates"].astype(float)).mean()
    for metric, value in (("rP", p / bp), ("rm", (n / p) / bm), ("rN", n / bn)):
        errors.append(abs(value - getattr(row, "placebo_" + metric)))
assert max(errors) < .000051
variants = pd.read_csv(ROOT / "07_m6_robustness/m6_h1_variants_v3.csv")
online = pd.read_csv(V1 / "07_m6_robustness/m6_online_set_variant_vehicles.csv")
online = online[(online.date == "2021-07-26") & (online.baseline == "B1")].set_index("grp")
online_errors = []
for row in variants[variants.variant == "S_on"].itertuples(index=False):
    original = online.loc["local_zheD", row.metric] - online.loc["other_province", row.metric]
    online_errors.append(abs(original - row.effect))
assert max(online_errors) < .000101
v1comp = pd.read_csv(V1 / "04_m3_vehicles/m3_composition.csv").set_index(["window", "thr", "date"])
v3comp = pd.read_csv(ROOT / "04_m3_vehicles/m3_composition_v3.csv").set_index(["window", "thr", "date"])
class_errors = []
for cls in ("regular", "frequent", "occasional", "earlier_only", "unseen"):
    a = v1comp["share_" + cls].sort_index()
    b = v3comp["share_" + cls + "_5class"].sort_index()
    class_errors.append(float(np.max(np.abs(a.values - b.values))))
assert max(class_errors) == 0
report = dict(status="passed", checked_at=now(), raw_source_read=False, panel_read=False,
              B_P_points_from_frozen_v1_count_tables_max_abs_csv_rounding_error=max(errors),
              S_on_contrast_from_frozen_v1_variant_max_abs_csv_rounding_error=max(online_errors),
              original_five_class_point_values_equal_v1_at4decimals=True,
              B_P_main_group_rows_checked=len(main), S_on_metrics_checked=len(online_errors))
write_json(ROOT / "00_env/vehicle_output_checks_v3.json", report)
print(report)
