# -*- coding: utf-8 -*-
"""Synthetic-only method checks. No source reads or scientific outputs."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[3]), str(_ReleasePath(__file__).resolve().parents[1]), str(_ReleasePath(__file__).resolve().parent)]
import numpy as np
from common_v3 import ROOT, B_P, SEED, now, write_json
from m3_vehicles_v3 import baseline_days, joint_composition_draws, ratio, DI

assert len(B_P) == 12
assert baseline_days("2021-07-15", "B1_loo") == (["2021-06-17", "2021-07-01"], "B1+B3")
assert baseline_days("2021-07-17", "B1_loo") == (["2021-07-03"], "B1+B3")
assert "2021-07-12" not in baseline_days("2021-07-12", "B1_loo")[0]
N, P = np.ones((37, 12)) * 100, np.ones((37, 12)) * 10
refs, pool = baseline_days("2021-07-26", "B1")
for j, d in enumerate(refs):
    N[DI[d]], P[DI[d]] = (j + 1) * 100, (j + 1) * 5
N[DI["2021-07-26"]], P[DI["2021-07-26"]] = 30, 3
spec = dict(scope="stable", hours="all_day", date="2021-07-26", days=refs)
r = ratio(dict(stable=[N, P]), spec)
assert np.allclose(r["rm"], .5)
assert np.allclose(r["rP"], .3)
rng = np.random.default_rng(SEED)
ev = rng.integers(0, 2, (1200, 9), dtype="int8")
cl = rng.integers(0, 5, 1200, dtype="int8")
bt, bp = joint_composition_draws(ev, ev, cl, cl, np.ones(1200, dtype=bool), rng)
assert np.allclose(bt, bp)
assert np.allclose(bt.sum(axis=2), 1)
merged = np.concatenate([bt[:, :, :3], bt[:, :, 3:].sum(axis=2)[:, :, None]], axis=2)
assert np.allclose(merged.sum(axis=2), 1)
report = dict(status="passed", checked_at=now(), seed=SEED, synthetic_only=True, scientific_outputs_written=False,
              B_P_explicit_12_days=True, B1_loo_empty_weekday_fallback=True, B1_loo_excludes_target=True,
              frozen_rm_mean_daily_ratio=True, shared_vehicle_pair_covariance=True, nonwindow_joint_merge_sum_one=True)
write_json(ROOT / "00_env/vehicle_method_checks_v3.json", report)
print(report)
