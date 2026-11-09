"""M5 and failure negative controls, protocol v2, seed 20261005.

Reads only anonymous local panels. No source-data writes. Exact coordinates
remain in memory; all module outputs contain anonymous IDs or aggregates.
"""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[2]), str(_ReleasePath(__file__).resolve().parents[0])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from pyproj import Transformer
from statsmodels.stats.multitest import multipletests

from spatial_stats_v1 import joincount_knn6

SEED = 20261005
N_BOOT = 500
N_PERM = 999
N_LEAVEOUT = 200
D_PARTIAL = pd.to_datetime(["2021-07-08", "2021-07-10", "2021-07-22",
                            "2021-07-23", "2021-07-24", "2021-07-25"])
B1 = pd.date_range("2021-07-05", "2021-07-21").difference(
    pd.to_datetime(["2021-07-08", "2021-07-10"]))
B2 = pd.date_range("2021-07-12", "2021-07-21")
B3 = pd.to_datetime(["2021-06-17"] + list(pd.date_range(
    "2021-06-28", "2021-07-04").strftime("%Y-%m-%d")))
EVENT = pd.date_range("2021-07-25", "2021-08-02")
TEST_DATES = pd.to_datetime(["2021-07-26", "2021-07-28", "2021-08-02"])
NC_DATES = pd.to_datetime(["2021-07-08", "2021-07-10", "2021-07-22",
                           "2021-07-23", "2021-07-24"])
RING_LABELS = ["0-2", "2-4", "4-7", "7-12", "12-20", "20+"]


def stamp():
    return datetime.now(timezone.utc).isoformat()


def json_clean(obj):
    if isinstance(obj, dict):
        return {str(k): json_clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [json_clean(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (float, np.floating)):
        return float(obj) if np.isfinite(obj) else None
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    return obj


class Run:
    def __init__(self, root):
        self.root = Path(root)
        self.out = self.root / "06_m5_bias_correction"
        self.rob = self.root / "07_m6_robustness"
        self.fig = self.root / "08_figures"
        for folder in [self.out, self.rob, self.fig, self.root / "00_env"]:
            folder.mkdir(exist_ok=True, parents=True)
        self.outputs = []
        self.notes = []
        self.execution = {"started_at": stamp(), "seed": SEED,
                          "script": "scripts/m5_bias_v1.py", "outputs": self.outputs}

    def save(self, frame, path):
        frame.to_csv(path, index=False, encoding="utf-8-sig", float_format="%.4f")
        self.outputs.append({"file": str(path.relative_to(self.root)).replace("\\", "/"),
                             "rows": len(frame)})

    def load(self):
        input_paths = [self.root / "01_panels/device_hour.csv",
                       self.root / "01_panels/device_attributes.csv"]
        self.input_paths = input_paths
        self.execution["input_files_before"] = [{"path": str(path), "size": path.stat().st_size,
            "mtime_ns": path.stat().st_mtime_ns} for path in input_paths]
        self.attr = pd.read_csv(self.root / "01_panels/device_attributes.csv")
        self.attr["dev"] = self.attr.dev.astype(str)
        self.attr = self.attr.set_index("dev").sort_index()
        for name in ["in_A100", "in_A200", "in_Sstar"]:
            self.attr[name] = self.attr[name].astype(str).str.lower().isin(["1", "true", "1.0"])
        for name in ["base_B1", "lon", "lat", "dist_baiguan_km", "gateway"]:
            self.attr[name] = pd.to_numeric(self.attr[name], errors="coerce")
        self.attr["gateway"] = self.attr.gateway.fillna(0).astype(int)
        for name in ["road_level", "org"]:
            self.attr[name] = self.attr[name].fillna("missing").astype(str)
        self.attr["distance_ring"] = pd.cut(self.attr.dist_baiguan_km,
            [-np.inf, 2, 4, 7, 12, 20, np.inf], labels=RING_LABELS,
            right=False).astype(object).fillna("missing")
        h = pd.read_csv(self.root / "01_panels/device_hour.csv",
                        usecols=["date", "dev", "hour", "n"])
        h["date"] = pd.to_datetime(h.date.astype(str).str.replace('"', '', regex=False))
        h["dev"] = h.dev.astype(str)
        h["hour"] = pd.to_numeric(h.hour).astype(int)
        h["n"] = pd.to_numeric(h.n).astype(np.int64)
        self.h = h
        self.days = pd.DatetimeIndex(sorted(h.date.unique()))
        self.devs = self.attr.index.to_numpy()
        self.daily = h.groupby(["date", "dev"]).n.sum().unstack("dev").reindex(
            index=self.days, columns=self.devs, fill_value=0).fillna(0)
        self.matched = h[h.hour >= 11].groupby(["date", "dev"]).n.sum().unstack("dev").reindex(
            index=self.days, columns=self.devs, fill_value=0).fillna(0)
        self.a100 = self.attr.in_A100.to_numpy()
        self.a200 = self.attr.in_A200.to_numpy()
        self.stable = self.attr.in_Sstar.to_numpy()
        self.base_mean = self.attr.base_B1.to_numpy(float)
        self.xy = np.full((len(self.attr), 2), np.nan)
        ok = self.attr.lon.notna() & self.attr.lat.notna() & self.attr.lon.ne(0) & self.attr.lat.ne(0)
        transformer = Transformer.from_crs("EPSG:4326", "EPSG:32651", always_xy=True)
        self.xy[ok] = np.column_stack(transformer.transform(self.attr.loc[ok, "lon"], self.attr.loc[ok, "lat"]))
        self.coord_ok = np.isfinite(self.xy).all(axis=1)
        self.strata = (self.attr.road_level.astype(str) + "|" + self.attr.distance_ring.astype(str)).to_numpy()
        self.quantile = np.full(len(self.attr), "missing", dtype=object)
        for subset in [self.a200, self.stable]:
            ranks = pd.Series(self.base_mean[subset]).rank(method="first")
            q = pd.qcut(ranks, 4, labels=["Q1", "Q2", "Q3", "Q4"]).astype(str)
            if subset is self.a200:
                self.profile_quantile = np.full(len(self.attr), "missing", dtype=object)
                self.profile_quantile[subset] = q.to_numpy()
            else:
                self.quantile[subset] = q.to_numpy()
        missing_coords = int((self.stable & ~self.coord_ok).sum())
        if missing_coords:
            self.notes.append({"type": "implementation_fallback", "module": "M5",
                "detail": "Targets lacking usable coordinates use the median ratio of all online donors for kNN; stratum still uses its available layer.",
                "n_Sstar_without_coordinates": missing_coords})
        self.execution["input_rows"] = {"device_hour": len(h), "device_attributes": len(self.attr)}
        self.execution["sets"] = {"A100": int(self.a100.sum()), "A200": int(self.a200.sum()), "Sstar": int(self.stable.sum())}

    def values(self, date):
        return (self.matched if date == pd.Timestamp("2021-07-25") else self.daily).loc[date].to_numpy(float)

    def baseline(self, date, baseline=B1, hour_matched=True):
        source = self.matched if hour_matched and date == pd.Timestamp("2021-07-25") else self.daily
        refs = baseline[baseline.dayofweek == date.dayofweek]
        return source.loc[refs].mean().to_numpy(float)

    def failure(self, date):
        n = self.values(date)
        baseline = self.baseline(date)
        failure_n = self.daily.loc[date].to_numpy(float)
        failure_base = self.baseline(date, hour_matched=False)
        previous = date - pd.Timedelta(days=7)
        fallback = previous in D_PARTIAL or previous not in self.days
        prev_raw = self.daily.loc[previous].to_numpy(float) if previous in self.days else np.full(len(n), np.nan)
        denom = failure_base if fallback else prev_raw
        failed = self.a200 & (failure_n < .05 * denom)
        degraded = self.a200 & (failure_n < .50 * denom)
        with np.errstate(divide="ignore", invalid="ignore"):
            ratio = np.divide(n, baseline, out=np.zeros_like(n), where=baseline > 0)
            daily_ratio = np.divide(failure_n, failure_base, out=np.zeros_like(failure_n), where=failure_base > 0)
        online = self.a100 & (daily_ratio >= .20)
        return {"n": n, "base": baseline, "failure_n": failure_n, "failure_base": failure_base,
                "denom": denom, "prev_raw": prev_raw,
                "fallback": fallback, "failed": failed, "degraded": degraded,
                "failed_baseline": self.a200 & (failure_n < .05 * failure_base),
                "degraded_baseline": self.a200 & (failure_n < .50 * failure_base),
                "ratio": ratio, "online": online}

    def failure_counts(self):
        rows = []
        for date in pd.date_range("2021-07-15", "2021-08-02"):
            d = self.failure(date)
            rows.append({"date": date.strftime("%Y-%m-%d"), "n_A200": int(self.a200.sum()),
                "n_failed_prevweek": int(d["failed"].sum()), "n_degraded_prevweek": int(d["degraded"].sum()),
                "n_failed_baseline": int(d["failed_baseline"].sum()),
                "n_degraded_baseline": int(d["degraded_baseline"].sum()),
                "n_failed_prevweek_raw": int((self.a200 & (d["failure_n"] < .05*d["prev_raw"])).sum()),
                "n_degraded_prevweek_raw": int((self.a200 & (d["failure_n"] < .5*d["prev_raw"])).sum()),
                "prevweek_date": (date-pd.Timedelta(days=7)).strftime("%Y-%m-%d"),
                "prevweek_denominator": "b_dow_B1" if d["fallback"] else "same_day_prevweek",
                "hour_matched": 0})
        frame = pd.DataFrame(rows)
        self.save(frame, self.out / "m5_failure_counts.csv")
        return frame

    def failure_timing(self):
        failed26 = self.failure(pd.Timestamp("2021-07-26"))["failed"]
        failed25 = self.a200 & (self.matched.loc[pd.Timestamp("2021-07-25")].to_numpy(float)
                               < .05*self.matched.loc[pd.Timestamp("2021-07-18")].to_numpy(float))
        rows = []
        for idx in np.flatnonzero(failed26):
            start = pd.Timestamp("2021-07-25") if failed25[idx] else pd.Timestamp("2021-07-26")
            recovery = "not_by_0802"
            for date in pd.date_range(start, "2021-08-02"):
                d = self.failure(date)
                if d["denom"][idx] > 0 and d["failure_n"][idx] >= .5*d["denom"][idx]:
                    recovery = date.strftime("%Y-%m-%d")
                    break
            rows.append({"first_failure_date": start.strftime("%Y-%m-%d"),
                         "first_failure_period": "11:00-23:59" if start.day == 25 else "full_day",
                         "recovery_date": recovery})
        frame = pd.DataFrame(rows, columns=["first_failure_date", "first_failure_period", "recovery_date"]).groupby(
            ["first_failure_date", "first_failure_period", "recovery_date"]).size().reset_index(name="n_devices")
        self.save(frame, self.out / "m5_failure_timing.csv")
        return frame

    @staticmethod
    def permutation_test(values, labels, categorical=False, seed=SEED):
        values = np.asarray(values)
        labels = np.asarray(labels, bool)
        if labels.sum() == 0 or (~labels).sum() == 0:
            return {"observed": np.nan, "perm_mean": np.nan, "perm_sd": np.nan,
                    "z": np.nan, "p_perm": np.nan}
        if categorical:
            levels, codes = np.unique(values.astype(str), return_inverse=True)
            total = np.bincount(codes, minlength=len(levels)).astype(float)
            nfail = int(labels.sum())
            expected_fail = total * nfail / len(labels)
            expected_online = total * (len(labels)-nfail) / len(labels)
            def statistic(lab):
                a = np.bincount(codes[lab], minlength=len(levels)).astype(float)
                c = total-a
                return float(np.divide((a-expected_fail)**2, expected_fail,
                    out=np.zeros_like(a), where=expected_fail>0).sum() +
                    np.divide((c-expected_online)**2, expected_online,
                    out=np.zeros_like(a), where=expected_online>0).sum())
        else:
            values = values.astype(float)
            def statistic(lab):
                return float(values[lab].mean()-values[~lab].mean())
        obs = statistic(labels)
        rng = np.random.default_rng(seed)
        perm = np.array([statistic(rng.permutation(labels)) for _ in range(N_PERM)])
        sd = float(perm.std(ddof=1))
        if categorical:
            p = (1 + (perm >= obs).sum())/(N_PERM+1)
        else:
            p = (1 + (np.abs(perm) >= abs(obs)).sum())/(N_PERM+1)
        return {"observed": obs, "perm_mean": float(perm.mean()), "perm_sd": sd,
                "z": (obs-perm.mean())/sd if sd else np.nan, "p_perm": float(p)}

    def nonrandomness(self, dates):
        rows = []
        profile = []
        for date in dates:
            state = self.failure(date)
            failed = state["failed"]
            online = self.a200 & state["online"] & ~failed
            spatial = self.a200 & self.coord_ok
            result = joincount_knn6(self.xy[spatial], failed[spatial], seed=SEED)
            rows.append({"date": date.strftime("%Y-%m-%d"), "test": "joincount_knn6", **result,
                "n_failed": int(failed.sum()), "n_online": int(online.sum()),
                "n_test": int(spatial.sum()), "n_failed_test": int(failed[spatial].sum()),
                "n_online_test": int((~failed[spatial]).sum()),
                "n_excluded_intermediate": int((self.a200 & ~failed & ~online).sum()),
                "prevweek_denominator": "b_dow_B1" if state["fallback"] else "same_day_prevweek"})
            values_map = {
                "mean_log_base_diff": (np.log(np.maximum(self.base_mean, 1e-12)), False),
                "chisq_road_level": (self.attr.road_level.to_numpy(), True),
                "chisq_org": (self.attr.org.to_numpy(), True),
                "mean_dist_baiguan_diff": (self.attr.dist_baiguan_km.to_numpy(float), False),
                "share_gateway_diff": (self.attr.gateway.to_numpy(float), False)}
            for test, (values, categorical) in values_map.items():
                subset = (failed | online)
                if not categorical:
                    subset &= np.isfinite(values)
                result = self.permutation_test(values[subset], failed[subset], categorical=categorical)
                rows.append({"date": date.strftime("%Y-%m-%d"), "test": test, **result,
                    "n_failed": int(failed.sum()), "n_online": int(online.sum()),
                    "n_test": int(subset.sum()), "n_failed_test": int(failed[subset].sum()),
                    "n_online_test": int(online[subset].sum()),
                    "n_excluded_intermediate": int((self.a200 & ~failed & ~online).sum()),
                    "prevweek_denominator": "b_dow_B1" if state["fallback"] else "same_day_prevweek"})
            for attribute, vals in [("road_level", self.attr.road_level.to_numpy()),
                                    ("org", self.attr.org.to_numpy()),
                                    ("distance_ring", self.attr.distance_ring.to_numpy()),
                                    ("base_flow_quantile", self.profile_quantile)]:
                for status, mask in [("failed", failed), ("online", online)]:
                    for category in sorted(set(vals[self.a200])):
                        count = int((mask & (vals == category)).sum())
                        profile.append({"date": date.strftime("%Y-%m-%d"),
                            "attribute": attribute, "category": category, "status": status,
                            "n_devices": count, "share": count/int(mask.sum()) if mask.sum() else np.nan,
                            "n_status": int(mask.sum())})
        frame = pd.DataFrame(rows)
        finite = frame.p_perm.notna()
        frame["p_holm"] = np.nan
        frame.loc[finite, "p_holm"] = multipletests(frame.loc[finite, "p_perm"], method="holm")[1]
        return frame, pd.DataFrame(profile)

    def visible_bias(self):
        all_frames = []
        for suffix in ["", "_B2"]:
            input_path = self.root / ("03_m2_two_sources/m2_daily_ratios%s.csv" % suffix)
            self.input_paths.append(input_path)
            self.execution["input_files_before"].append({"path": str(input_path),
                "size": input_path.stat().st_size, "mtime_ns": input_path.stat().st_mtime_ns})
            ratios = pd.read_csv(input_path)
            ratios.date = ratios.date.astype(str).str.replace('"', '', regex=False)
            ratios = ratios[ratios.date.isin(EVENT.strftime("%Y-%m-%d"))]
            cols = ["date", "R_naive", "R_online", "R_stable", "R_taxi_km"]
            frame = ratios[cols].copy()
            for name in ["naive", "online", "taxi"]:
                source = "R_taxi_km" if name == "taxi" else "R_" + name
                frame["delta_"+name] = frame[source]-frame.R_stable
            frame["n_A100"] = int(self.a100.sum())
            frame["n_online"] = [int(self.failure(pd.Timestamp(d))["online"].sum()) for d in frame.date]
            frame["n_Sstar"] = int(self.stable.sum())
            frame["hour_matched"] = (frame.date == "2021-07-25").astype(int)
            self.save(frame, self.out / ("m5_visible_bias%s.csv" % suffix))
            all_frames.append(frame)
        return all_frames[0]

    def predict(self, ratio, donor_mask, target_mask):
        donors = np.flatnonzero(donor_mask)
        target = np.flatnonzero(target_mask)
        if len(donors) == 0:
            raise ValueError("No online donor devices")
        global_median = float(np.median(ratio[donors]))
        knn = np.full(len(ratio), np.nan)
        stratum = np.full(len(ratio), np.nan)
        knn[target] = global_median
        donor_xy = donors[self.coord_ok[donors]]
        target_xy = target[self.coord_ok[target]]
        if len(donor_xy) and len(target_xy):
            k = min(6, len(donor_xy))
            neighbour = cKDTree(self.xy[donor_xy]).query(self.xy[target_xy], k=k)[1]
            neighbour = np.asarray(neighbour).reshape(len(target_xy), k)
            knn[target_xy] = np.median(ratio[donor_xy[neighbour]], axis=1)
        stratum[target] = knn[target]
        fallback = np.ones(len(ratio), dtype=bool)
        for layer in np.unique(self.strata[target]):
            if layer.endswith("|missing") or layer.startswith("missing|"):
                continue
            layer_donors = donors[self.strata[donors] == layer]
            layer_targets = target[self.strata[target] == layer]
            if len(layer_donors) >= 5:
                stratum[layer_targets] = np.median(ratio[layer_donors])
                fallback[layer_targets] = False
        return knn, stratum, {"n_knn_global_fallback": int((target_mask & ~self.coord_ok).sum()),
                              "n_stratum_knn_fallback": int(fallback[target].sum())}

    def correction(self, visible):
        rows = []
        for date in EVENT:
            state = self.failure(date)
            donor = state["online"] & ~state["failed"]
            knn, stratum, fallbacks = self.predict(state["ratio"], donor, state["failed"])
            total_base = state["base"][self.a100].sum()
            adjusted = {}
            for method, pred in [("knn", knn), ("stratum", stratum)]:
                n = state["n"].copy()
                n[state["failed"]] = state["base"][state["failed"]]*pred[state["failed"]]
                adjusted["R_"+method] = n[self.a100].sum()/total_base
            raw = visible.set_index("date").loc[date.strftime("%Y-%m-%d")]
            rows.append({"date": date.strftime("%Y-%m-%d"),
                "R_naive": raw.R_naive, "R_online": raw.R_online, "R_stable": raw.R_stable,
                **adjusted, "n_imputed": int(state["failed"].sum()), **fallbacks,
                "hour_matched": int(date == pd.Timestamp("2021-07-25"))})
        frame = pd.DataFrame(rows)
        self.save(frame, self.out / "m5_correction_methods.csv")
        return frame

    def leaveout(self):
        records = []
        quantile_records = []
        devices = np.flatnonzero(self.stable)
        nmask = max(1, int(round(.20*len(devices))))
        probabilities = self.base_mean[devices]/self.base_mean[devices].sum()
        for masking in ["random", "flowweighted"]:
            rng = np.random.default_rng(SEED)
            for date in pd.date_range("2021-07-26", "2021-07-30"):
                state = self.failure(date)
                n, base, ratio = state["n"], state["base"], state["ratio"]
                truth = n[self.stable].sum()/base[self.stable].sum()
                for rep in range(N_LEAVEOUT):
                    masked = rng.choice(devices, nmask, replace=False,
                                        p=probabilities if masking == "flowweighted" else None)
                    target = np.zeros(len(self.devs), bool)
                    target[masked] = True
                    donor = self.stable & ~target
                    knn, stratum, fallback = self.predict(ratio, donor, target)
                    drop_est = n[donor].sum()/base[donor].sum()
                    predictions = {"naive_zero": np.zeros(len(ratio)),
                                   "drop": np.full(len(ratio), drop_est),
                                   "knn": knn, "stratum": stratum}
                    for method, pred in predictions.items():
                        estimate = drop_est if method == "drop" else (
                            n[donor].sum() + (base[target]*pred[target]).sum())/base[self.stable].sum()
                        error = estimate-truth
                        device_error = float(np.abs(pred[target]-ratio[target]).mean())
                        records.append({"masking": masking, "date": date.strftime("%Y-%m-%d"),
                            "rep": rep+1, "method": method, "truth": truth,
                            "estimate": estimate, "error": error, "abs_error": abs(error),
                            "device_level_mae": np.nan if method == "drop" else device_error,
                            "device_proxy_mae": device_error if method == "drop" else np.nan,
                            "n_masked": nmask, "masked_base_share": base[target].sum()/base[self.stable].sum(),
                            **fallback})
                        for quantile in ["Q1", "Q2", "Q3", "Q4"]:
                            subset = target & (self.quantile == quantile)
                            if not subset.any():
                                continue
                            qtruth = n[subset].sum()/base[subset].sum()
                            qestimate = (base[subset]*pred[subset]).sum()/base[subset].sum()
                            qerror = qestimate-qtruth
                            qdevice_error = float(np.abs(pred[subset]-ratio[subset]).mean())
                            quantile_records.append({"masking": masking,
                                "date": date.strftime("%Y-%m-%d"), "rep": rep+1,
                                "flow_quantile": quantile, "method": method,
                                "error": qerror, "abs_error": abs(qerror),
                                "error_kind": "city_ratio_proxy" if method == "drop" else "device_predictions",
                                "device_level_mae": np.nan if method == "drop" else qdevice_error,
                                "device_proxy_mae": qdevice_error if method == "drop" else np.nan,
                                "n_masked_quantile": int(subset.sum())})
                print("M5 leaveout completed %s %s" % (masking, date.strftime("%Y-%m-%d")), flush=True)
        raw = pd.DataFrame(records)
        qraw = pd.DataFrame(quantile_records)
        self.save(raw, self.out / "m5_leaveout_replicates.csv")
        self.save(qraw, self.out / "m5_leaveout_by_flow_quantile_replicates.csv")
        summary = raw.groupby(["masking", "date", "method"]).agg(
            bias_mean=("error", "mean"), bias_sd=("error", "std"),
            mae=("abs_error", "mean"), device_level_mae=("device_level_mae", "mean"),
            device_proxy_mae=("device_proxy_mae", "mean"),
            n_reps=("rep", "count")).reset_index()
        qsummary = qraw.groupby(["masking", "date", "flow_quantile", "method"]).agg(
            bias_mean=("error", "mean"), bias_sd=("error", "std"), mae=("abs_error", "mean"),
            device_level_mae=("device_level_mae", "mean"), n_reps=("rep", "count"),
            device_proxy_mae=("device_proxy_mae", "mean"),
            n_masked_mean=("n_masked_quantile", "mean")).reset_index()
        qsummary["error_kind"] = np.where(qsummary.method.eq("drop"), "city_ratio_proxy", "device_predictions")
        for masking, suffix in [("random", ""), ("flowweighted", "_flowweighted")]:
            self.save(summary[summary.masking == masking].drop(columns="masking"),
                      self.out / ("m5_leaveout_validation%s.csv" % suffix))
            self.save(qsummary[qsummary.masking == masking].drop(columns="masking"),
                      self.out / ("m5_leaveout_by_flow_quantile%s.csv" % suffix))
        return summary, raw

    def relabel_drop_mae(self):
        """Correct an output label without resampling an already validated run.

The drop estimator has a city-level prediction only. Its former device MAE
is retained as an explicitly auxiliary city-ratio proxy, never fabricated
as an individual camera prediction. Existing aggregate bias/MAE stay intact.
"""
        filenames = ["m5_leaveout_replicates.csv",
                     "m5_leaveout_by_flow_quantile_replicates.csv",
                     "m5_leaveout_validation.csv",
                     "m5_leaveout_validation_flowweighted.csv",
                     "m5_leaveout_by_flow_quantile.csv",
                     "m5_leaveout_by_flow_quantile_flowweighted.csv"]
        for name in filenames:
            path = self.out / name
            frame = pd.read_csv(path)
            drop = frame.method.eq("drop")
            changed = "device_proxy_mae" not in frame
            if changed:
                frame["device_proxy_mae"] = np.where(drop, frame.device_level_mae, np.nan)
            if frame.loc[drop, "device_level_mae"].notna().any():
                frame.loc[drop, "device_level_mae"] = np.nan
                changed = True
            if "quantile" in name and "error_kind" not in frame:
                frame["error_kind"] = np.where(drop, "city_ratio_proxy", "device_predictions")
                changed = True
            if changed:
                self.save(frame, path)

    def negative_control(self):
        tests, _ = self.nonrandomness(NC_DATES)
        rows = []
        for date in NC_DATES:
            state = self.failure(date)
            rows.append({"date": date.strftime("%Y-%m-%d"),
                "n_A200": int(self.a200.sum()), "n_failed_prevweek": int(state["failed"].sum()),
                "n_degraded_prevweek": int(state["degraded"].sum()),
                "n_failed_baseline": int(state["failed_baseline"].sum()),
                "n_degraded_baseline": int(state["degraded_baseline"].sum()),
                "prevweek_date": (date-pd.Timedelta(days=7)).strftime("%Y-%m-%d"),
                "hour_matched": 0})
        frame = tests.drop(columns="prevweek_denominator").merge(pd.DataFrame(rows), on="date", how="left")
        self.save(frame, self.rob / "m6_negative_control_0708_0710.csv")
        counts = self.h.groupby(["date", "hour"]).n.sum().unstack("hour", fill_value=0)
        hourly = []
        for date, reference in [(pd.Timestamp("2021-07-08"), pd.Timestamp("2021-07-01")),
                                (pd.Timestamp("2021-07-10"), pd.Timestamp("2021-07-03"))]:
            for hour in range(24):
                numerator = int(counts.loc[date, hour])
                denominator = int(counts.loc[reference, hour])
                refs = B1[B1.dayofweek == date.dayofweek]
                bmean = float(counts.loc[refs, hour].mean())
                hourly.append({"date": date.strftime("%Y-%m-%d"), "hour": hour,
                    "reference_date": reference.strftime("%Y-%m-%d"), "records": numerator,
                    "reference_records": denominator, "record_ratio": numerator/denominator if denominator else np.nan,
                    "baseline_records": bmean, "record_ratio_baseline": numerator/bmean if bmean else np.nan})
        self.save(pd.DataFrame(hourly), self.rob / "m6_negative_control_hourly.csv")
        return frame

    def verdict(self, tests, controls, validation, correction=None):
        focus = tests[tests.date == "2021-07-26"].set_index("test")
        joinp = float(focus.loc["joincount_knn6", "p_perm"])
        flowp = float(focus.loc["mean_log_base_diff", "p_perm"])
        stop = joinp > .05 and flowp > .05
        weighted = validation[validation.masking == "flowweighted"].groupby("method").agg(
            bias=("bias_mean", "mean"), mae=("mae", "mean"))
        improved = {method: {"mae_lower_than_naive_zero": bool(weighted.loc[method, "mae"] < weighted.loc["naive_zero", "mae"]),
            "absolute_bias_lower_than_naive_zero": bool(abs(weighted.loc[method, "bias"]) < abs(weighted.loc["naive_zero", "bias"]))}
            for method in ["drop", "knn", "stratum"]}
        negative_similar = []
        for date in ["2021-07-08", "2021-07-10"]:
            sub = controls[controls.date == date].set_index("test")
            negative_similar.append({"date": date,
                "joincount_p": float(sub.loc["joincount_knn6", "p_perm"]),
                "flow_p": float(sub.loc["mean_log_base_diff", "p_perm"]),
                "flow_diff": float(sub.loc["mean_log_base_diff", "observed"]),
                "same_nonrandomness_criterion": bool(float(sub.loc["joincount_knn6", "p_perm"]) <= .05 and
                    float(sub.loc["mean_log_base_diff", "p_perm"]) <= .05 and
                    np.sign(float(sub.loc["mean_log_base_diff", "observed"])) ==
                    np.sign(float(focus.loc["mean_log_base_diff", "observed"])))})
        correction_improves = any(improved[k]["mae_lower_than_naive_zero"] and improved[k]["absolute_bias_lower_than_naive_zero"] for k in ["knn", "stratum"])
        similar = any(x["same_nonrandomness_criterion"] for x in negative_similar)
        negative_cluster = any(x["joincount_p"] <= .05 for x in negative_similar)
        imputation_beats_drop = {method: bool(weighted.loc[method, "mae"] < weighted.loc["drop", "mae"]) for method in ["knn", "stratum"]}
        qualifiers = ["Platform controls show spatial clustering." if negative_cluster else
                      "Platform controls do not show spatial clustering at the prespecified raw p threshold."]
        qualifiers.append("At least one imputation method improves both absolute bias and MAE relative to zero masking." if correction_improves else
                          "Neither imputation method improves both absolute bias and MAE relative to zero masking.")
        qualifiers.append("At least one imputation method has a higher MAE than drop." if not all(imputation_beats_drop.values()) else
                          "Both imputation methods have a lower MAE than drop.")
        qualifiers.append("These results do not identify unobserved citywide truth.")
        # Only the dual-p stop is a frozen numerical verdict. The full hypothesis
        # contains several claims; report their evidence separately and retain
        # partial support rather than treating zero-mask prediction gain as proof
        # of unobserved citywide recovery.
        state = "degraded" if stop else "mixed"
        verdict = {"H4": state, "stop_condition_triggered": stop,
            "mandatory_stop_status": "degraded" if stop else "not_triggered",
            "full_status_is_contextual_interpretation": True,
            "stop_condition_rule": "7/26 joincount p>0.05 AND mean_log_base_diff p>0.05",
            "joincount_0726_p": joinp, "mean_log_base_diff_0726_p": flowp,
            "mean_log_base_diff_0726": float(focus.loc["mean_log_base_diff", "observed"]),
            "negative_controls": negative_similar, "flowweighted_leaveout": weighted.to_dict(orient="index"),
            "calibration_improvement": improved, "calibration_improves": correction_improves,
            "negative_controls_share_joint_flow_and_clustering_signal": similar,
            "negative_control_spatial_clustering": negative_cluster,
            "imputation_beats_drop_mae": imputation_beats_drop,
            "interpretation": "Association and within-Sstar predictive validation; no causal or unobserved-city truth claim.",
            "hypothesis_status_rule": "Only the section 3.10 mandatory stop is a frozen numerical rule. Mixed denotes partial support with control or prediction limitations; root summary reviews each full-hypothesis component.",
            "evidence_qualification": " ".join(qualifiers)}
        path = self.out / "m5_h4_verdict.json"
        path.write_text(json.dumps(json_clean(verdict), ensure_ascii=False, indent=2), encoding="utf-8")
        self.outputs.append({"file": str(path.relative_to(self.root)).replace("\\", "/"), "rows": None})
        return verdict

    def plot(self, visible, profile, raw, correction):
        from common_v1 import setup_plot
        plt = setup_plot()
        plt.rcParams.update({"font.size": 10,
            "text.color": "#333333", "axes.labelcolor": "#333333",
            "xtick.color": "#333333", "ytick.color": "#333333",
            "axes.spines.top": False, "axes.spines.right": False,
            "lines.linewidth": 2, "lines.markersize": 8, "figure.dpi": 180})
        colors = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
        fig, axes = plt.subplots(2, 2, figsize=(14, 10), constrained_layout=True)
        ax = axes[0, 0]
        for name, label, color in [("R_stable", "Stable cameras", colors[0]),
                                   ("R_taxi_km", "Taxi distance", colors[1]),
                                   ("R_naive", "All cameras", colors[2]),
                                   ("R_online", "Online cameras", colors[3])]:
            ax.plot(pd.to_datetime(visible.date), visible[name], "o-", label=label, color=color)
        ax.axhline(1, color="#777777", linewidth=1)
        ax.set(title="(a) Observed recovery ratios", ylabel="Ratio to weekday baseline")
        ax.legend(fontsize=8)
        ax.tick_params(axis="x", rotation=40)
        ax.grid(alpha=.18, linewidth=.5)
        ax = axes[0, 1]
        subset = profile[(profile.date == "2021-07-26") & (profile.attribute == "base_flow_quantile")]
        categories = ["Q1", "Q2", "Q3", "Q4"]
        x = np.arange(len(categories))
        for offset, status, color in [(-.18, "failed", colors[1]), (.18, "online", colors[0])]:
            vals = subset[subset.status == status].set_index("category").reindex(categories).share
            ax.bar(x+offset, vals, .36, label=status.title(), color=color)
        ax.set_xticks(x, categories)
        ax.set(title="(b) 26 July baseline-flow distribution", ylabel="Device share", xlabel="Baseline-flow quartile")
        ax.legend()
        ax.grid(axis="y", alpha=.18, linewidth=.5)
        for ax, field, label in [(axes[1, 0], "error", "Signed error"), (axes[1, 1], "abs_error", "Absolute error")]:
            methods = ["naive_zero", "drop", "knn", "stratum"]
            plots = []
            positions = []
            for k, method in enumerate(methods):
                for masking, offset in [("random", -.18), ("flowweighted", .18)]:
                    plots.append(raw[(raw.method == method) & (raw.masking == masking)][field])
                    positions.append(k+offset)
            box = ax.boxplot(plots, positions=positions, widths=.28, showfliers=False, patch_artist=True)
            for k, patch in enumerate(box["boxes"]):
                patch.set_facecolor(colors[k % 2])
                patch.set_alpha(.8)
            from matplotlib.patches import Patch
            ax.legend(handles=[Patch(facecolor=colors[0], label="Random masking"),
                               Patch(facecolor=colors[1], label="Flow-weighted masking")], fontsize=8)
            ax.set_xticks(np.arange(4), ["Zero", "Drop", "6-NN", "Stratum"])
            ax.axhline(0, color="#777777", linewidth=1)
            ax.set(title="(c) Leaveout validation" if field == "error" else "(d) Leaveout absolute errors",
                   ylabel=label)
            ax.grid(axis="y", alpha=.18, linewidth=.5)
        fig.savefig(self.fig / "fig6_bias_correction.png", dpi=180)
        plt.close(fig)
        self.outputs.append({"file": "08_figures/fig6_bias_correction.png", "rows": None})
        frames = []
        v = visible.copy(); v["panel"] = "a"; v["source"] = "m5_visible_bias"; frames.append(v)
        p = profile[(profile.date == "2021-07-26") & (profile.attribute == "base_flow_quantile")].copy()
        p["panel"] = "b"; p["source"] = "m5_failure_profile"; frames.append(p)
        r = raw.copy(); r["panel"] = "c_d"; r["source"] = "m5_leaveout_replicates"; frames.append(r)
        self.save(pd.concat(frames, ignore_index=True, sort=False), self.fig / "fig6_data.csv")

    def checks(self, counts, tests, controls, validation, raw, correction=None):
        checks = {"failure_counts_19_dates": len(counts) == 19,
            "nonrandomness_18_rows": len(tests) == 18,
            "negative_control_30_rows": len(controls) == 30,
            "leaveout_replicates_8000": len(raw) == 2*5*200*4,
            "leaveout_each_method_200": bool((validation.n_reps == 200).all()),
            "bias_signed_definition": bool(np.allclose(raw.error, raw.estimate-raw.truth, atol=1.1e-4)),
            "mae_absolute_definition": bool(np.allclose(raw.abs_error, np.abs(raw.error), atol=1.1e-4)),
            "drop_device_prediction_undefined": bool(raw.loc[raw.method.eq("drop"), "device_level_mae"].isna().all()),
            "7_25_hour_matched": bool(correction[correction.date == "2021-07-25"].hour_matched.eq(1).all()) if correction is not None else "pending_finish",
            "fewer_than_10_vehicle_cells": "not_applicable_device_aggregates_only",
            "seed": SEED, "N_PERM": N_PERM, "N_LEAVEOUT": N_LEAVEOUT}
        if not all(v for v in checks.values() if isinstance(v, (bool, np.bool_))):
            raise AssertionError("M5 self checks failed: " + json.dumps(json_clean(checks)))
        (self.out / "M5_CHECKS.json").write_text(json.dumps(json_clean(checks), indent=2), encoding="utf-8")
        self.outputs.append({"file": "06_m5_bias_correction/M5_CHECKS.json", "rows": None})
        notes = {"frozen_definitions": "Applied protocol v2 sections 3.1-3.3,3.7,3.9 unchanged.",
            "failure_denominator": "Previous week, unless partial/absent then weekday B1; baseline and raw previous-week counts reported separately.",
            "7_25": "AVI recovery ratios restricted to hours 11-23; F/G device counts retain the frozen full-day n definition; failure timing separately checks the afternoon.",
            "online_attribute_reference": "A200 intersect S_on minus failed; S_on eligibility always uses frozen full-day n/b_dow, including 7/25; interpolation neighbour ratios are hour matched on 7/25. Intermediate nonfailed offline devices excluded from attribute comparisons.",
            "joincount": "All geolocated A200, undirected union of six-neighbour edges; right-tail label permutation, fixed failed count.",
            "distance_ties": "cKDTree deterministically selects tied-distance neighbours, including colocated devices.",
            "correction_targets": "Frozen F(t), i.e. failed A200 devices; all other A100 records remain observed.",
            "numeric_tests": "Two-sided raw difference permutation; categorical chi-square and join count right-tail; Holm p included.",
            "drop_device_proxy": "Drop has no individual prediction: device_level_mae is NA. Its citywide surviving-device weighted ratio applied to masked devices is reported only as auxiliary device_proxy_mae.",
            "quantile_errors": "Heldout-quartile aggregate predicted ratio minus truth ratio; drop quartile errors are explicitly auxiliary city_ratio_proxy. Device MAE unweighted; quartiles frozen from B1 mean within Sstar. Empty heldout quartiles have no defined error; n_reps is the actual nonempty count, not forced to 200.",
            "random_masking": "Simple random sample without replacement of round(20%*|Sstar|).",
            "flowweighted_masking": "Without-replacement sample with selection probabilities proportional to B1 mean device flow.",
            "limits": "Leaveout validates within Sstar only; citywide unseen truth and causal effects are not identified."}
        (self.out / "M5_METHOD_NOTES.json").write_text(json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8")
        self.outputs.append({"file": "06_m5_bias_correction/M5_METHOD_NOTES.json", "rows": None})

    def pilot_deviations(self, counts):
        indexed = counts.set_index("date")
        for date, lower, upper in [("2021-07-27", 84, 84),
                                   ("2021-07-28", 77, 78),
                                   ("2021-08-02", 55, 56)]:
            formal = int(indexed.loc[date, "n_failed_prevweek"])
            if formal < .90*lower or formal > 1.10*upper:
                self.notes.append({"type": "pilot_count_deviation", "date": date,
                    "metric": "n_failed_prevweek", "pilot_range": [lower, upper],
                    "formal": formal, "formal_baseline": int(indexed.loc[date, "n_failed_baseline"]),
                    "definition_changed": False,
                    "reason": "Frozen previous-week denominator is used unless partial/absent. The previous dates 7/20, 7/21 and 7/26 already have losses or event suppression; baseline counts remain separately reported."})
        usual = indexed.loc["2021-07-15":"2021-07-21", "n_failed_prevweek"].astype(int)
        if (usual.lt(.9*11) | usual.gt(1.1*18)).any():
            self.notes.append({"type": "pilot_ordinary_day_count_deviation",
                "metric": "n_failed_prevweek_0715_0721", "pilot_range": [11, 18],
                "formal_by_date": usual.to_dict(), "definition_changed": False,
                "reason": "7/15 and 7/17 use fallback B1 with a sole same-weekday day equal to themselves, hence zero failures; other previous-week dates reflect each day's observed panel. No dates dropped or thresholds changed."})

    def run(self, stage="all"):
        started = time.monotonic()
        self.execution["stage"] = stage
        self.load()
        correction = None
        if stage != "finish":
            counts = self.failure_counts()
            self.failure_timing()
            tests, profile = self.nonrandomness(TEST_DATES)
            self.save(tests, self.out / "m5_failure_nonrandomness.csv")
            self.save(profile, self.out / "m5_failure_profile.csv")
            validation, raw = self.leaveout()
            controls = self.negative_control()
        else:
            self.relabel_drop_mae()
            counts = pd.read_csv(self.out / "m5_failure_counts.csv")
            tests = pd.read_csv(self.out / "m5_failure_nonrandomness.csv")
            profile = pd.read_csv(self.out / "m5_failure_profile.csv")
            controls = pd.read_csv(self.rob / "m6_negative_control_0708_0710.csv")
            raw = pd.read_csv(self.out / "m5_leaveout_replicates.csv")
            summaries = []
            for masking, suffix in [("random", ""), ("flowweighted", "_flowweighted")]:
                summary = pd.read_csv(self.out / ("m5_leaveout_validation%s.csv" % suffix))
                summary["masking"] = masking
                summaries.append(summary)
            validation = pd.concat(summaries, ignore_index=True)
        if stage != "core":
            visible = self.visible_bias()
            correction = self.correction(visible)
            self.plot(visible, profile, raw, correction)
        verdict = self.verdict(tests, controls, validation, correction)
        self.checks(counts, tests, controls, validation, raw, correction)
        self.pilot_deviations(counts)
        review_note = self.root / "00_env/m5_audit_note.json"
        if review_note.exists():
            self.notes.append(json.loads(review_note.read_text(encoding="utf-8")))
        self.execution.update({"ended_at": stamp(), "elapsed_seconds": round(time.monotonic()-started, 2),
                               "status": "core_complete" if stage == "core" else "complete", "H4": verdict["H4"]})
        self.execution["input_files_after"] = [{"path": str(path), "size": path.stat().st_size,
            "mtime_ns": path.stat().st_mtime_ns} for path in self.input_paths]
        self.execution["local_inputs_unchanged"] = self.execution["input_files_before"] == self.execution["input_files_after"]
        if not self.execution["local_inputs_unchanged"]:
            self.execution["status"] = "failed_input_mutation"
            failure_path = self.root / "00_env/bias_failed_input_mutation.json"
            failure_path.write_text(json.dumps(json_clean(self.execution), ensure_ascii=False, indent=2), encoding="utf-8")
            raise AssertionError("M5 local input size/mtime changed during execution")
        execution_path = self.root / ("00_env/bias_core_execution.json" if stage == "core" else "00_env/bias_execution.json")
        execution_path.write_text(json.dumps(json_clean(self.execution), ensure_ascii=False, indent=2), encoding="utf-8")
        (self.root / "00_env/bias_deviations.json").write_text(json.dumps(json_clean(self.notes), ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"M5": "complete", "H4": verdict["H4"], "n_outputs": len(self.outputs)}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=_release_path('project_root'))
    parser.add_argument("--stage", choices=["all", "core", "finish"], default="all")
    args = parser.parse_args()
    Run(args.root).run(args.stage)
