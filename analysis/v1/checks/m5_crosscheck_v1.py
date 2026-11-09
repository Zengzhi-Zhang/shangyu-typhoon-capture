"""Read-only cross-artifact validation for the completed M5/M6 products.

No source scans, resampling, model fitting or threshold changes. Run after
M1/M2, M4 and M5 have completed on the same final local input panels.
"""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[3]), str(_ReleasePath(__file__).resolve().parents[1])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
import argparse
import json
from pathlib import Path
from datetime import datetime, timezone
import numpy as np
import pandas as pd

SEED = 20261005
EVENT = [d.strftime("%Y-%m-%d") for d in pd.date_range("2021-07-25", "2021-08-02")]
VALIDATE = [d.strftime("%Y-%m-%d") for d in pd.date_range("2021-07-26", "2021-07-30")]
TEST_DATES = ["2021-07-26", "2021-07-28", "2021-08-02"]
TESTS = {"joincount_knn6", "mean_log_base_diff", "chisq_road_level", "chisq_org",
         "mean_dist_baiguan_diff", "share_gateway_diff"}
METHODS = {"naive_zero", "drop", "knn", "stratum"}


def run(root):
    root = Path(root)
    checks = []
    details = {}
    def check(name, passed):
        checks.append({"check": name, "passed": bool(passed)})
    def read(rel):
        return pd.read_csv(root / rel)
    def align_numeric(left, right, keys, cols, tolerance=5.1e-5):
        left = left.set_index(keys).sort_index()
        right = right.set_index(keys).sort_index()
        if not left.index.equals(right.index):
            return False
        return all(np.allclose(pd.to_numeric(left[col], errors="coerce"),
                    pd.to_numeric(right[col], errors="coerce"), equal_nan=True,
                    atol=tolerance, rtol=0) for col in cols)
    out = "06_m5_bias_correction/"
    m2 = read("03_m2_two_sources/m2_daily_ratios.csv")
    visible = read(out + "m5_visible_bias.csv")
    visible2 = read(out + "m5_visible_bias_B2.csv")
    m2b2 = read("03_m2_two_sources/m2_daily_ratios_B2.csv")
    ratio_cols = ["R_naive", "R_online", "R_stable", "R_taxi_km", "n_online", "hour_matched"]
    for name, a, b in [("B1", visible, m2), ("B2", visible2, m2b2)]:
        check("visible_"+name+"_same_event_dates", sorted(a.date) == EVENT)
        check("visible_"+name+"_matches_M2", align_numeric(a, b[b.date.isin(EVENT)], ["date"], ratio_cols))
        for field, ratio in [("delta_naive", "R_naive"), ("delta_online", "R_online"), ("delta_taxi", "R_taxi_km")]:
            check(name+"_"+field+"_identity", np.allclose(a[field], a[ratio]-a.R_stable,
                  equal_nan=True, atol=1.01e-4, rtol=0))
    correction = read(out+"m5_correction_methods.csv")
    check("correction_reuses_observed_ratios", align_numeric(correction, visible, ["date"],
          ["R_naive", "R_online", "R_stable", "hour_matched"]))
    check("7_25_avi_ratio_hour_matched", int(correction.set_index("date").loc["2021-07-25", "hour_matched"]) == 1)
    counts = read(out+"m5_failure_counts.csv")
    check("failure_counts_all_19_dates", counts.date.tolist() == pd.date_range("2021-07-15", "2021-08-02").strftime("%Y-%m-%d").tolist())
    timing = read(out+"m5_failure_timing.csv")
    check("failure_timing_totals_equal_0726_failed", int(timing.n_devices.sum()) == int(counts.set_index("date").loc["2021-07-26", "n_failed_prevweek"]))
    tests = read(out+"m5_failure_nonrandomness.csv")
    check("all_18_prespecified_tests", len(tests) == 18 and set(tests.date) == set(TEST_DATES) and set(tests.test) == TESTS)
    spatial = json.loads((root/"05_m4_spatial/m4_moran.json").read_text(encoding="utf-8"))["joincount"]
    for date in TEST_DATES:
        row = tests[(tests.date == date) & (tests.test == "joincount_knn6")].iloc[0]
        target = spatial[date]
        check("M4_M5_joincount_"+date, all(np.isclose(float(row[key]), float(target[key]),
              atol=5.1e-5, rtol=0) for key in ["observed", "perm_mean", "perm_sd", "z", "p_perm", "n_edges", "n_spatial", "n_failed_spatial"]))
        detail_keys = ["n_test", "n_failed_test", "n_online_test", "n_failed", "n_online"]
        details["joincount_sample_"+date] = {key: int(row[key]) for key in detail_keys}
    raw = read(out+"m5_leaveout_replicates.csv")
    qraw = read(out+"m5_leaveout_by_flow_quantile_replicates.csv")
    grouped = raw.groupby(["masking", "date", "method"])
    check("leaveout_all_40_cells_200_reps", len(grouped) == 40 and grouped.size().eq(200).all())
    check("leaveout_dates_methods_masking", set(raw.date) == set(VALIDATE) and set(raw.method) == METHODS and set(raw.masking) == {"random", "flowweighted"})
    check("leaveout_rep_ids_unique", not raw.duplicated(["masking", "date", "method", "rep"]).any())
    check("leaveout_signed_absolute_error", np.allclose(raw.error, raw.estimate-raw.truth, atol=1.01e-4, rtol=0) and np.allclose(raw.abs_error, abs(raw.error), atol=5.1e-5, rtol=0))
    check("drop_device_mae_NA_proxy_retained", raw.loc[raw.method.eq("drop"), "device_level_mae"].isna().all() and raw.loc[raw.method.eq("drop"), "device_proxy_mae"].notna().all())
    check("non_drop_device_mae_defined", raw.loc[~raw.method.eq("drop"), "device_level_mae"].notna().all())
    for masking, suffix in [("random", ""), ("flowweighted", "_flowweighted")]:
        summary = read(out+"m5_leaveout_validation"+suffix+".csv")
        recomputed = raw[raw.masking.eq(masking)].groupby(["date", "method"]).agg(
            bias_mean=("error", "mean"), bias_sd=("error", "std"), mae=("abs_error", "mean"),
            device_level_mae=("device_level_mae", "mean"), device_proxy_mae=("device_proxy_mae", "mean"), n_reps=("rep", "count")).reset_index()
        check(masking+"_summary_matches_replicates", align_numeric(summary, recomputed, ["date", "method"],
            ["bias_mean", "bias_sd", "mae", "device_level_mae", "device_proxy_mae", "n_reps"], tolerance=1.01e-4))
        qs = read(out+"m5_leaveout_by_flow_quantile"+suffix+".csv")
        qr = qraw[qraw.masking.eq(masking)]
        nq = qr.groupby(["date", "flow_quantile", "method"]).size().reset_index(name="n_reps")
        check(masking+"_quantile_effective_n_reps", align_numeric(qs, nq, ["date", "flow_quantile", "method"], ["n_reps"]))
        check(masking+"_quantile_drop_proxy_label", qs.loc[qs.method.eq("drop"), "error_kind"].eq("city_ratio_proxy").all() and qs.loc[qs.method.eq("drop"), "device_level_mae"].isna().all())
        check(masking+"_quantile_reps_not_fabricated", qs.n_reps.le(200).all() and qs.n_reps.gt(0).all())
        details[masking+"_quantile_nonempty_reps"] = qs[qs.method.eq("knn")][["date", "flow_quantile", "n_reps"]].to_dict(orient="records")
    fig = read("08_figures/fig6_data.csv")
    check("fig6_panel_a_matches_visible", align_numeric(fig[fig.panel.eq("a")], visible, ["date"], ratio_cols+["delta_naive", "delta_online", "delta_taxi"]))
    check("fig6_boxplot_rows_match_replicates", align_numeric(fig[fig.panel.eq("c_d")], raw,
        ["masking", "date", "method", "rep"], ["error", "abs_error", "truth", "estimate", "device_level_mae", "device_proxy_mae"]))
    profile = read(out+"m5_failure_profile.csv")
    plotted = profile[profile.date.eq("2021-07-26") & profile.attribute.eq("base_flow_quantile")]
    check("fig6_profile_matches_panel_b", align_numeric(fig[fig.panel.eq("b")], plotted,
        ["date", "attribute", "category", "status"], ["n_devices", "share", "n_status"]))
    for fig_name in ["fig1_data.csv", "fig2_data.csv"]:
        data = read("08_figures/"+fig_name)
        if "panel" in data:
            data = data[data.panel.eq("daily")]
        check(fig_name+"_M2_ratios_consistent", align_numeric(data, m2[m2.date.isin(data.date)], ["date"], ratio_cols))
    nc = read("07_m6_robustness/m6_negative_control_0708_0710.csv")
    check("all_30_negative_control_tests", len(nc) == 30 and set(nc.test) == TESTS and set(nc.date) == {"2021-07-08", "2021-07-10", "2021-07-22", "2021-07-23", "2021-07-24"})
    hourly = read("07_m6_robustness/m6_negative_control_hourly.csv")
    check("negative_hourly_all_48_cells", len(hourly) == 48 and not hourly.duplicated(["date", "hour"]).any())
    check("negative_hourly_frozen_references", hourly[hourly.date.eq("2021-07-08")].reference_date.eq("2021-07-01").all() and hourly[hourly.date.eq("2021-07-10")].reference_date.eq("2021-07-03").all())
    check("negative_hourly_ratio_identity", np.allclose(hourly.record_ratio, hourly.records/hourly.reference_records, atol=5.1e-5, rtol=0))
    verdict = json.loads((root/(out+"m5_h4_verdict.json")).read_text(encoding="utf-8"))
    p26 = tests[tests.date.eq("2021-07-26")].set_index("test").p_perm
    check("H4_not_pending", verdict["H4"] in {"pass", "fail", "degraded", "mixed"})
    check("H4_stop_uses_frozen_dual_p_rule", bool(verdict["stop_condition_triggered"]) == bool(p26["joincount_knn6"] > .05 and p26["mean_log_base_diff"] > .05))
    result = {"generated_at": datetime.now(timezone.utc).isoformat(), "seed": SEED,
        "scope": "Cross-artifact checks only; source manifest is separately verified by environment stage.",
        "status": "pass" if all(item["passed"] for item in checks) else "fail", "checks": checks, "details": details}
    (root/"00_env/m5_crosschecks.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"M5_crosschecks": result["status"], "checks": len(checks)}), flush=True)
    if result["status"] != "pass":
        raise AssertionError("Cross-artifact mismatch: "+", ".join(item["check"] for item in checks if not item["passed"]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=_release_path('project_root'))
    run(parser.parse_args().root)
