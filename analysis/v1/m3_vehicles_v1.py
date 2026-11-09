# -*- coding: utf-8 -*-
"""Frozen vehicle recovery analysis, version 1, seed 20261005.

No raw plates are read by this script. Multinomial vehicle-cluster bootstrap is
used directly for margins and on exactly equivalent outcome signatures for
present/cumulative/composition intervals. All days and sensitivity arms persist.
"""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[2]), str(_ReleasePath(__file__).resolve().parents[0])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
import json
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta
import numpy as np
import pandas as pd
from scipy import sparse
from scipy.stats import spearmanr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SEED = 20261005
ROOT = Path(_release_path('project_root'))
TZ = timezone(timedelta(hours=8))
D_ALL = ["2021-06-17"] + pd.date_range("2021-06-28", "2021-08-02").strftime("%Y-%m-%d").tolist()
D_PARTIAL = ["2021-07-08", "2021-07-10", "2021-07-22", "2021-07-23", "2021-07-24", "2021-07-25"]
B1 = [d for d in pd.date_range("2021-07-05", "2021-07-21").strftime("%Y-%m-%d") if d not in D_PARTIAL]
B2 = pd.date_range("2021-07-12", "2021-07-21").strftime("%Y-%m-%d").tolist()
B3 = ["2021-06-17"] + pd.date_range("2021-06-28", "2021-07-04").strftime("%Y-%m-%d").tolist()
BASELINES = {"B1": B1, "B2": B2, "B3": B3}
W_T = pd.date_range("2021-07-12", "2021-07-21").strftime("%Y-%m-%d").tolist()
E_T = pd.date_range("2021-07-25", "2021-08-02").strftime("%Y-%m-%d").tolist()
W_P = pd.date_range("2021-06-28", "2021-07-07").strftime("%Y-%m-%d").tolist()
E_P = pd.date_range("2021-07-11", "2021-07-19").strftime("%Y-%m-%d").tolist()
GRPS_BASE = ["local_zheD_ICE", "local_zheD_NEV", "zhejiang_other_ICE", "zhejiang_other_NEV",
             "other_province_ICE", "other_province_NEV", "unreadable"]
GRPS = GRPS_BASE + ["all", "local_zheD", "zhejiang_other", "other_province", "all_ICE"]
CURVE_GROUPS = ["all", "local_zheD", "zhejiang_other", "other_province"] + GRPS_BASE[:-1]
CLASSES = ["regular", "frequent", "occasional", "earlier_only", "unseen"]
COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#729ece", "#a8c3e3"]
EXPAND = np.zeros((7, len(GRPS)), dtype=float)
EXPAND[:, :7] = np.eye(7)
EXPAND[:6, 7] = 1
EXPAND[:2, 8] = 1
EXPAND[2:4, 9] = 1
EXPAND[4:6, 10] = 1
EXPAND[[0, 2, 4], 11] = 1
DI = {d: i for i, d in enumerate(D_ALL)}
DOW = np.array([pd.Timestamp(d).dayofweek for d in D_ALL])
OUT = ROOT / "04_m3_vehicles"
ROB = ROOT / "07_m6_robustness"
FIG = ROOT / "08_figures"


def stamp():
    return datetime.now(TZ).isoformat()


def csv(frame, path):
    frame = frame.copy()
    counts = {"plates", "baseline_plates", "n_regular", "n_vehicles", "n_other_plates", "n_local_plates"}
    counts.update(c for c in frame if c.startswith("plates_"))
    for col in counts:
        if col in frame:
            numeric = pd.to_numeric(frame[col], errors="coerce")
            if col == "baseline_plates" or col.startswith("plates_baseline_"):
                frame[col] = ["<10" if pd.notna(x) and x < 10 else format(x, ".4f") if pd.notna(x) else
                              original if str(original) == "<10" else "" for original, x in zip(frame[col], numeric)]
            else:
                frame[col] = ["<10" if pd.notna(x) and x < 10 else int(x) if pd.notna(x) else
                              original if str(original) == "<10" else "" for original, x in zip(frame[col], numeric)]
    frame.to_csv(path, index=False, encoding="utf-8-sig", float_format="%.4f")


def group_mask(master, grp):
    if grp == "all":
        return master.cat.values != "unreadable"
    if grp in ["local_zheD", "zhejiang_other", "other_province"]:
        return master.cat.values == grp
    return master.grp.values == grp


def expand(arr):
    return arr.reshape(len(D_ALL), 7).dot(EXPAND)


def draw_readable_vehicle_weights(n_total, readable_idx, rng, probs=None):
    if probs is None:
        probs = np.full(len(readable_idx), 1.0 / len(readable_idx))
    weights = np.ones(n_total, dtype="int64")
    weights[readable_idx] = rng.multinomial(len(readable_idx), probs)
    return weights


def load_panels():
    pm = pd.read_parquet(ROOT / "01_panels/plate_master.parquet")
    pm["grp"] = pm.cat + np.where(pm.nev.astype(int).values == 1, "_NEV", "_ICE")
    pm.loc[pm.cat == "unreadable", "grp"] = "unreadable"
    pm_index = pd.Index(pm.ph)
    cat_code = pd.Categorical(pm.grp, categories=GRPS_BASE).codes.astype("int8")
    masks = np.zeros(len(pm), dtype="uint64")
    rr, cc, vv = [], [], []
    rh, ch, vh = [], [], []
    h_dates = set(["2021-07-25"] + [d for b in BASELINES.values() for d in b if pd.Timestamp(d).dayofweek == 6])
    hourly_first = []
    extra_stats = []
    for d in D_ALL:
        t = time.time()
        day = pd.read_parquet(ROOT / "01_panels/plate_day" / (d + ".parquet"))
        ex = pd.read_parquet(ROOT / "01_panels/plate_day_extra" / (d + ".parquet"))
        if not np.array_equal(day.ph.values, ex.ph.values):
            raise ValueError("Supplemental panel ordering mismatch")
        idx = pm_index.get_indexer(day.ph)
        if (idx < 0).any():
            raise ValueError("Anonymous plate absent from master")
        gc = cat_code[idx]
        good = day.n_stable.values > 0
        masks[idx[good]] |= np.uint64(1) << np.uint64(DI[d])
        rr.append(DI[d] * 7 + gc[good].astype("int32"))
        cc.append(idx[good].astype("int32"))
        vv.append(day.n_stable.values[good].astype(float))
        if d in h_dates:
            hg = ex.n_stable_h11.values > 0
            rh.append(DI[d] * 7 + gc[hg].astype("int32"))
            ch.append(idx[hg].astype("int32"))
            vh.append(ex.n_stable_h11.values[hg].astype(float))
        first = ex.h_min_stable.values[(good) & (gc != 6) & (ex.h_min_stable.values >= 0)]
        q = np.percentile(first, [10, 25, 50, 75, 90]) if len(first) else [np.nan] * 5
        hourly_first.append({"date": d, "plates": len(first), "p10": q[0], "p25": q[1], "p50": q[2],
                             "p75": q[3], "p90": q[4], "share_first_before_9": np.mean(first < 9) if len(first) else np.nan,
                             "share_first_after_15": np.mean(first > 15) if len(first) else np.nan,
                             "hour_matched": int(d == "2021-07-25"), "scope": "first appearance on Sstar"})
        for col in ex:
            if not col.startswith("n_"):
                continue
            val = ex[col].values
            nb = np.bincount(gc, weights=val, minlength=7).dot(EXPAND)
            pb = np.bincount(gc[val > 0], minlength=7).dot(EXPAND)
            for gi, g in enumerate(GRPS):
                extra_stats.append({"date": d, "scope": col, "grp": g, "records": nb[gi], "plates": pb[gi]})
        print(stamp(), "M3 LOAD", d, "anonymous_rows", len(day), "seconds", round(time.time() - t, 1), flush=True)
    shape = (len(D_ALL) * 7, len(pm))
    M_N = sparse.csr_matrix((np.concatenate(vv), (np.concatenate(rr), np.concatenate(cc))), shape=shape)
    M_P = sparse.csr_matrix((np.ones(M_N.nnz, dtype="int8"), M_N.indices, M_N.indptr), shape=shape, copy=False)
    M_HN = sparse.csr_matrix((np.concatenate(vh), (np.concatenate(rh), np.concatenate(ch))), shape=shape)
    M_HP = sparse.csr_matrix((np.ones(M_HN.nnz, dtype="int8"), M_HN.indices, M_HN.indptr), shape=shape, copy=False)
    del rr, cc, vv, rh, ch, vh
    return pm, masks, M_N, M_P, M_HN, M_HP, pd.DataFrame(hourly_first), pd.DataFrame(extra_stats)


def ratios(N, P, HN, HP, baseline, hour_matched_dates=None):
    hour_matched_dates = {"2021-07-25"} if hour_matched_dates is None else set(hour_matched_dates)
    bn = np.full_like(N, np.nan)
    bp = np.full_like(P, np.nan)
    bm = np.full_like(N, np.nan)
    ub = np.full(len(D_ALL), np.nan)
    with np.errstate(divide="ignore", invalid="ignore"):
        m = N / P
        hm = HN / HP
    for di, d in enumerate(D_ALL):
        ix = [DI[b] for b in baseline if pd.Timestamp(b).dayofweek == DOW[di]]
        use_n, use_p, use_m = (HN, HP, hm) if d in hour_matched_dates else (N, P, m)
        bn[di] = use_n[ix].mean(axis=0)
        bp[di] = use_p[ix].mean(axis=0)
        bm[di] = use_m[ix].mean(axis=0)
        with np.errstate(divide="ignore", invalid="ignore"):
            ub[di] = np.mean(use_n[ix, 6] / use_n[ix, :7].sum(axis=1))
    nn, pp = N.copy(), P.copy()
    for d in hour_matched_dates:
        nn[DI[d]] = HN[DI[d]]
        pp[DI[d]] = HP[DI[d]]
    with np.errstate(divide="ignore", invalid="ignore"):
        mm = nn / pp
        rp, rn, rm = pp / bp, nn / bn, mm / bm
        u = nn[:, 6] / nn[:, :7].sum(axis=1)
        rpc = rp * ((1 - ub) / (1 - u))[:, None]
        rm_exact = mm / (bn / bp)
        resid = np.log(rn) - np.log(rp) - np.log(rm)
    return {"plates": pp, "records": nn, "passes_per_plate": mm, "rP": rp, "rN": rn, "rm": rm,
            "rP_idcorr": rpc, "log_identity_residual": resid,
            "rm_ratio_of_aggregate_sensitivity": rm_exact, "baseline_plates": bp,
            "baseline_records": bn, "baseline_mean_passes": bm, "u": u, "u_base": ub}


def main_margins(pm, MN, MP, HN, HP):
    one = np.ones(len(pm), dtype=float)
    N, P, NH, PH = [expand(m.dot(one)) for m in (MN, MP, HN, HP)]
    points = {b: ratios(N, P, NH, PH, days) for b, days in BASELINES.items()}
    placebo_h11_points = {b: ratios(N, P, NH, PH, days, {"2021-07-25", "2021-07-11"})
                          for b, days in BASELINES.items()}
    rng = np.random.default_rng(SEED)
    readable_idx = np.flatnonzero(pm.cat.values != "unreadable")
    probs = np.full(len(readable_idx), 1.0 / len(readable_idx))
    samples = {b: {m: np.empty((200, len(D_ALL), len(GRPS))) for m in ("rP", "rN", "rm", "rP_idcorr")}
               for b in BASELINES}
    placebo_h11_samples = {b: {m: np.empty((200, len(GRPS))) for m in ("rP", "rN", "rm")}
                           for b in BASELINES}
    for k in range(200):
        # Unreadable strings are placeholders, not vehicle clusters. Their
        # observed records remain fixed; identification intervals are conditional
        # on these observed counts while readable vehicle records are resampled.
        weights = draw_readable_vehicle_weights(len(pm), readable_idx, rng, probs)
        arrays = [expand(m.dot(weights)) for m in (MN, MP, HN, HP)]
        for b, days in BASELINES.items():
            rb = ratios(*arrays, days)
            for m in samples[b]:
                samples[b][m][k] = rb[m]
            rp11 = ratios(*arrays, days, hour_matched_dates={"2021-07-25", "2021-07-11"})
            for m in placebo_h11_samples[b]:
                placebo_h11_samples[b][m][k] = rp11[m][DI["2021-07-11"]]
        if k % 10 == 0:
            print(stamp(), "M3 MULTINOMIAL MARGINS", k, "of 200", flush=True)
    tables = {}
    for b in BASELINES:
        p = points[b]
        intervals = {m: np.nanpercentile(s, [2.5, 97.5], axis=0) for m, s in samples[b].items()}
        for it in intervals.values():
            it[:, :, GRPS.index("unreadable")] = np.nan
        rows = []
        for di, d in enumerate(D_ALL):
            for gi, g in enumerate(GRPS):
                row = {"date": d, "grp": g, "baseline": b, "hour_matched": int(d == "2021-07-25")}
                row["plate_semantics"] = "distinct_unreadable_placeholders" if g == "unreadable" else "readable_vehicles"
                row["ci_scope"] = "vehicle_bootstrap_not_applicable" if g == "unreadable" else "readable_vehicle_clusters; idcorr_conditional_on_observed_unreadable_records"
                for m in ["plates", "records", "passes_per_plate", "rP", "rN", "rm", "rP_idcorr",
                          "log_identity_residual", "rm_ratio_of_aggregate_sensitivity", "baseline_plates",
                          "baseline_records", "baseline_mean_passes"]:
                    row[m] = p[m][di, gi]
                row["plates"] = int(row["plates"])
                row["records"] = int(row["records"])
                row["log_decomp_rP"] = np.log(row["rP"]) if row["rP"] > 0 else np.nan
                row["log_decomp_rm"] = np.log(row["rm"]) if row["rm"] > 0 else np.nan
                row["unread_share"] = p["u"][di]
                row["unread_share_base"] = p["u_base"][di]
                for m, it in intervals.items():
                    row["ci_" + m + "_lo"] = it[0, di, gi]
                    row["ci_" + m + "_hi"] = it[1, di, gi]
                rows.append(row)
        tables[b] = pd.DataFrame(rows)
        suffix = "" if b == "B1" else "_" + b
        csv(tables[b], OUT / ("m3_daily_by_group" + suffix + ".csv"))
    rows = []
    for b, frame in tables.items():
        subset = frame[frame.date.isin(E_T[:6])].copy()
        gi_l, gi_o = GRPS.index("local_zheD"), GRPS.index("other_province")
        for d in E_T[:6]:
            di = DI[d]
            for metric in ("rP", "rm", "rN"):
                delta = points[b][metric][di, gi_l] - points[b][metric][di, gi_o]
                boot = samples[b][metric][:, di, gi_l] - samples[b][metric][:, di, gi_o]
                lo, hi = np.nanpercentile(boot, [2.5, 97.5])
                subset.loc[subset.date == d, "delta_local_minus_other_" + metric] = delta
                subset.loc[subset.date == d, "delta_local_minus_other_" + metric + "_lo"] = lo
                subset.loc[subset.date == d, "delta_local_minus_other_" + metric + "_hi"] = hi
        rows.append(subset)
    margins = pd.concat(rows, ignore_index=True)
    csv(margins, OUT / "m3_two_margins_table.csv")
    csv(pd.concat([f[f.date == "2021-07-26"] for f in tables.values()]), ROB / "m6_baseline_sensitivity_vehicles.csv")
    csv(tables["B1"][tables["B1"].date.isin(E_T[:4])], ROB / "m6_identification_correction.csv")
    ice = tables["B1"][tables["B1"].grp.isin(["all_ICE", "local_zheD_ICE", "zhejiang_other_ICE", "other_province_ICE"])].copy()
    ice["variant"] = "exclude_nev"
    csv(ice, ROB / "m6_exclude_nev.csv")
    signs = {}
    for b in BASELINES:
        di = DI["2021-07-26"]
        signs[b] = {m: float(points[b][m][di, GRPS.index("local_zheD")] -
                            points[b][m][di, GRPS.index("other_province")]) for m in ("rP", "rm")}
    flip = any(np.sign(signs[b][m]) != np.sign(signs["B1"][m]) for b in ("B2", "B3") for m in ("rP", "rm"))
    expected = signs["B1"]["rP"] > 0 and signs["B1"]["rm"] < 0
    h1 = {"status": "degraded" if flip else "pass" if expected else "fail",
          "baseline_stability_status": "degraded" if flip else "stable",
          "stop_condition_triggered": bool(flip), "2021-07-26_local_minus_other": signs,
          "groups_for_verdict": "local_zheD and other_province, all readable powertrain types",
          "bootstrap_population": "readable ph only; unreadable record counts fixed, identification CI conditional on these counts",
          "mean_operator_note": "rm uses mean of daily N/P; the formal log identity is not generally exact. Residual is reported."}
    evidence = h1_placebo_evidence(points, samples, placebo_h11_points, placebo_h11_samples)
    matched = evidence[(evidence.baseline == "B1") & (evidence.k == 2) &
                       (evidence.powertrain_scope == "all_powertrains") & (evidence.placebo_hours == "all_day")].iloc[0]
    h1["contextual_evidence"] = {
        "matched_k": 2, "typhoon_date": E_T[1], "placebo_date": E_P[1], "baseline": "B1",
        "same_direction_two_margins": bool(matched.same_direction_two_margins),
        "typhoon_delta_rP": float(matched.typhoon_delta_rP),
        "typhoon_delta_rm": float(matched.typhoon_delta_rm),
        "placebo_delta_rP": float(matched.placebo_delta_rP),
        "placebo_delta_rm": float(matched.placebo_delta_rm),
        "typhoon_minus_placebo_delta_rP": float(matched.typhoon_minus_placebo_delta_rP),
        "typhoon_minus_placebo_delta_rm": float(matched.typhoon_minus_placebo_delta_rm),
        "evidence_file": "04_m3_vehicles/m3_h1_placebo_margins.csv",
        "interpretation": "Same sign is a contextual warning, not proof of equal effects. No magnitude-equivalence or significance threshold was specified or introduced.",
        "placebo_baseline_note": "E_P uses unchanged B1/B2/B3, some of which include placebo evaluation dates. W_P is not silently substituted as an additional margin baseline."
    }
    for metric in ("rP", "rm"):
        for prefix in ("typhoon", "placebo", "typhoon_minus_placebo"):
            h1["contextual_evidence"][prefix + "_delta_" + metric + "_ci"] = [
                float(matched[prefix + "_delta_" + metric + "_lo"]),
                float(matched[prefix + "_delta_" + metric + "_hi"])]
    if not flip and expected and bool(matched.same_direction_two_margins):
        h1["status"] = "mixed"
    h1["frozen_stop_rule_status"] = "degraded" if flip else "not_triggered"
    return tables, h1


def h1_placebo_evidence(points, samples, h11points, h11samples):
    rows = []
    comparisons = [("all_powertrains", "local_zheD", "other_province"),
                   ("ICE_only", "local_zheD_ICE", "other_province_ICE"),
                   ("NEV_only", "local_zheD_NEV", "other_province_NEV")]
    for baseline in BASELINES:
        for k, (dt, dp) in enumerate(zip(E_T, E_P), 1):
            scopes = ["all_day", "h11_sensitivity"] if k == 1 else ["all_day"]
            for hours in scopes:
                for name, local, other in comparisons:
                    li, oi = GRPS.index(local), GRPS.index(other)
                    ti, pi = DI[dt], DI[dp]
                    pp = h11points[baseline] if hours == "h11_sensitivity" else points[baseline]
                    row = {"baseline": baseline, "k": k, "date_typhoon": dt, "date_placebo": dp,
                           "powertrain_scope": name, "placebo_hours": hours,
                           "typhoon_hour_matched": int(dt == "2021-07-25"),
                           "placebo_hour_matched": int(hours == "h11_sensitivity"),
                           "plates_local_typhoon": int(points[baseline]["plates"][ti, li]),
                           "plates_other_typhoon": int(points[baseline]["plates"][ti, oi]),
                           "plates_local_placebo": int(pp["plates"][pi, li]),
                           "plates_other_placebo": int(pp["plates"][pi, oi])}
                    for metric in ("rP", "rm", "rN"):
                        tv = points[baseline][metric][ti, li] - points[baseline][metric][ti, oi]
                        pv = pp[metric][pi, li] - pp[metric][pi, oi]
                        ts = samples[baseline][metric][:, ti, li] - samples[baseline][metric][:, ti, oi]
                        ps = (h11samples[baseline][metric][:, li] - h11samples[baseline][metric][:, oi]
                              if hours == "h11_sensitivity" else
                              samples[baseline][metric][:, pi, li] - samples[baseline][metric][:, pi, oi])
                        for prefix, estimate, draw in [("typhoon", tv, ts), ("placebo", pv, ps),
                                                       ("typhoon_minus_placebo", tv - pv, ts - ps)]:
                            row[prefix + "_delta_" + metric] = float(estimate)
                            row[prefix + "_delta_" + metric + "_lo"], row[prefix + "_delta_" + metric + "_hi"] = np.nanpercentile(draw, [2.5, 97.5])
                    row["typhoon_h1_direction"] = bool(row["typhoon_delta_rP"] > 0 and row["typhoon_delta_rm"] < 0)
                    row["placebo_h1_direction"] = bool(row["placebo_delta_rP"] > 0 and row["placebo_delta_rm"] < 0)
                    row["same_direction_two_margins"] = bool(row["typhoon_h1_direction"] and row["placebo_h1_direction"])
                    rows.append(row)
    frame = pd.DataFrame(rows)
    csv(frame, OUT / "m3_h1_placebo_margins.csv")
    return frame


def bits(masks, dates):
    return np.column_stack([((masks >> np.uint64(DI[d])) & np.uint64(1)).astype("int8") for d in dates])


def signature_bootstrap(present, classes=None, rng=None):
    """Exact multinomial cluster bootstrap after grouping identical outcomes."""
    if rng is None:
        rng = np.random.default_rng(SEED)
    n = len(present)
    if not n:
        return np.full((200, 9), np.nan), np.full((200, 9), np.nan), None
    sig = (present.astype("uint16") * (1 << np.arange(9, dtype="uint16"))).sum(axis=1).astype("int32")
    labels = sig if classes is None else sig + classes.astype("uint16") * 512
    uniq, cnt = np.unique(labels, return_counts=True)
    ps = ((uniq[:, None] % 512) & (1 << np.arange(9))) != 0
    ws = rng.multinomial(n, cnt / n, size=200)
    pb = ws.dot(ps.astype(float)) / n
    cb = ws.dot(np.maximum.accumulate(ps, axis=1).astype(float)) / n
    shares = None
    if classes is not None:
        shares = np.empty((200, 9, 5))
        denom = ws.dot(ps.astype(float))
        for c in range(5):
            num = ws.dot((ps & ((uniq // 512)[:, None] == c)).astype(float))
            with np.errstate(divide="ignore", invalid="ignore"):
                shares[:, :, c] = num / denom
    return pb, cb, shares


def paired_gap_bootstrap(ev_t, ev_p, regular_t, regular_p, rng):
    """Preserve shared vehicle covariance in two-window comparisons."""
    keep = regular_t | regular_p
    nt = regular_t[keep]
    np_ = regular_p[keep]
    n = int(keep.sum())
    if not n:
        return np.full((200, 9), np.nan)
    powers = 1 << np.arange(9, dtype="int32")
    st = (ev_t[keep] * powers).sum(axis=1).astype("int32")
    sp = (ev_p[keep] * powers).sum(axis=1).astype("int32")
    st[~nt] = 512
    sp[~np_] = 512
    labels = st + 513 * sp
    uniq, cnt = np.unique(labels, return_counts=True)
    tc, pc = uniq % 513, uniq // 513
    rt, rp = tc != 512, pc != 512
    tp = ((tc[:, None] & powers) != 0) & rt[:, None]
    pp = ((pc[:, None] & powers) != 0) & rp[:, None]
    ws = rng.multinomial(n, cnt / n, size=200)
    with np.errstate(divide="ignore", invalid="ignore"):
        return ws.dot(tp.astype(float)) / ws.dot(rt.astype(float))[:, None] - \
            ws.dot(pp.astype(float)) / ws.dot(rp.astype(float))[:, None]


def paired_composition_bootstrap(ev_t, ev_p, class_t, class_p, readable, rng):
    """Joint vehicle signatures preserve cross-window composition covariance."""
    t, p = ev_t[readable], ev_p[readable]
    ct, cp = class_t[readable], class_p[readable]
    powers = 1 << np.arange(9, dtype="int32")
    st = (t * powers).sum(axis=1).astype("int32") + ct.astype("int32") * 512
    sp = (p * powers).sum(axis=1).astype("int32") + cp.astype("int32") * 512
    uniq, cnt = np.unique(st + 2560 * sp, return_counts=True)
    tc, pc = uniq % 2560, uniq // 2560
    tp = ((tc % 512)[:, None] & powers) != 0
    pp = ((pc % 512)[:, None] & powers) != 0
    ws = rng.multinomial(len(t), cnt / len(t), size=200).astype(float)
    den_t, den_p = ws.dot(tp.astype(float)), ws.dot(pp.astype(float))
    bt, bp = np.empty((200, 9, 5)), np.empty((200, 9, 5))
    with np.errstate(divide="ignore", invalid="ignore"):
        for c in range(5):
            bt[:, :, c] = ws.dot((tp & ((tc // 512)[:, None] == c)).astype(float)) / den_t
            bp[:, :, c] = ws.dot((pp & ((pc // 512)[:, None] == c)).astype(float)) / den_p
    return bt, bp


def h2_composition_evidence(pm, comp, window_cache, class_cache, rng):
    paired_rows, trend_rows = [], []
    readable = group_mask(pm, "all")
    for thr in (6, 8, 9):
        tf = comp[(comp.window == "typhoon") & (comp.thr == thr)].sort_values("date")
        pf = comp[(comp.window == "placebo") & (comp.thr == thr)].sort_values("date")
        cols = ["share_" + c for c in CLASSES]
        tp, pp = tf[cols].values, pf[cols].values
        bt, bp = paired_composition_bootstrap(window_cache["typhoon"][1], window_cache["placebo"][1],
                                             class_cache[("typhoon", thr)], class_cache[("placebo", thr)], readable, rng)
        for ki in range(9):
            for ci, cls in enumerate(CLASSES):
                row = {"thr": thr, "k": ki + 1, "class": cls, "date_typhoon": E_T[ki], "date_placebo": E_P[ki],
                       "share_typhoon": tp[ki, ci], "share_placebo": pp[ki, ci], "gap": tp[ki, ci] - pp[ki, ci],
                       "plates_visible_typhoon": int(tf.plates.iloc[ki]), "plates_visible_placebo": int(pf.plates.iloc[ki]),
                       "typhoon_partial_day": int(ki == 0), "placebo_partial_day": 0}
                for prefix, draw in [("share_typhoon", bt[:, ki, ci]), ("share_placebo", bp[:, ki, ci]),
                                     ("gap", bt[:, ki, ci] - bp[:, ki, ci])]:
                    row[prefix + "_lo"], row[prefix + "_hi"] = np.nanpercentile(draw, [2.5, 97.5])
                paired_rows.append(row)
        for start in (0, 1):
            k = np.arange(start + 1, 10, dtype=float)
            sw = (k - k.mean()) / np.sum((k - k.mean()) ** 2)
            for ci, cls in enumerate(CLASSES):
                row = {"thr": thr, "class": cls, "k_start": start + 1, "k_end": 9,
                       "endpoint_scope": "all_prespecified_days" if start == 0 else "full_day_context_k2_k9",
                       "typhoon_first_day_partial": int(start == 0)}
                for metric, tval, pval, tdraw, pdraw in [
                    ("change", tp[-1, ci] - tp[start, ci], pp[-1, ci] - pp[start, ci],
                     bt[:, -1, ci] - bt[:, start, ci], bp[:, -1, ci] - bp[:, start, ci]),
                    ("slope_per_day", sw.dot(tp[start:, ci]), sw.dot(pp[start:, ci]),
                     bt[:, start:, ci].dot(sw), bp[:, start:, ci].dot(sw))]:
                    for prefix, estimate, draw in [("typhoon", tval, tdraw), ("placebo", pval, pdraw),
                                                   ("typhoon_minus_placebo", tval - pval, tdraw - pdraw)]:
                        row[prefix + "_" + metric] = float(estimate)
                        row[prefix + "_" + metric + "_lo"], row[prefix + "_" + metric + "_hi"] = np.nanpercentile(draw, [2.5, 97.5])
                    row["same_direction_" + metric] = bool(np.sign(tval) == np.sign(pval))
                trend_rows.append(row)
    paired, trends = pd.DataFrame(paired_rows), pd.DataFrame(trend_rows)
    csv(paired, OUT / "m3_h2_composition_placebo.csv")
    csv(trends, OUT / "m3_h2_composition_trends.csv")
    contexts = {}
    for start in (1, 2):
        sub = trends[(trends.thr == 8) & (trends.k_start == start)].set_index("class")
        regular, unseen = sub.loc["regular"], sub.loc["unseen"]
        contexts["k%d_k9" % start] = {
            "typhoon_regular_change": float(regular.typhoon_change),
            "placebo_regular_change": float(regular.placebo_change),
            "typhoon_unseen_change": float(unseen.typhoon_change),
            "placebo_unseen_change": float(unseen.placebo_change),
            "same_regular_decline_unseen_increase_direction": bool(
                regular.typhoon_change < 0 and regular.placebo_change < 0 and
                unseen.typhoon_change > 0 and unseen.placebo_change > 0),
            "partial_first_typhoon_day": start == 1
        }
        for cls, series in [("regular", regular), ("unseen", unseen)]:
            for prefix in ("typhoon", "placebo", "typhoon_minus_placebo"):
                contexts["k%d_k9" % start][prefix + "_" + cls + "_change_ci"] = [
                    float(series[prefix + "_change_lo"]), float(series[prefix + "_change_hi"])]
    return {"composition_trends_thr8": contexts,
            "evidence_files": ["04_m3_vehicles/m3_h2_composition_placebo.csv", "04_m3_vehicles/m3_h2_composition_trends.csv"],
            "intervals": "200 joint vehicle-cluster multinomial draws, preserving shared vehicle covariance",
            "interpretation": "Same sign alone does not establish equal-sized compositional shifts. Complete effects and intervals are given without a new equivalence/significance cutoff."}


def return_and_composition(pm, masks):
    curve, comp = [], []
    window_cache, class_cache = {}, {}
    rng = np.random.default_rng(SEED)
    windows = {"typhoon": (W_T, E_T), "placebo": (W_P, E_P)}
    for wn, (window, evaluation) in windows.items():
        wk = bits(masks, window).sum(axis=1)
        before_days = [d for d in D_ALL if d < window[0]]
        earlier = bits(masks, before_days).any(axis=1) if before_days else np.zeros(len(pm), dtype=bool)
        ev = bits(masks, evaluation)
        window_cache[wn] = (wk, ev)
        for thr in (6, 8, 9):
            cl = np.full(len(pm), 4, dtype="int8")
            cl[(wk == 0) & earlier] = 3
            cl[(wk >= 1) & (wk <= 3)] = 2
            cl[(wk >= 4) & (wk < thr)] = 1
            cl[wk >= thr] = 0
            class_cache[(wn, thr)] = cl
            readable = group_mask(pm, "all")
            _, _, sb = signature_bootstrap(ev[readable], cl[readable], rng)
            for ki, d in enumerate(evaluation):
                alive = (ev[:, ki] == 1) & readable
                total = int(alive.sum())
                row = {"window": wn, "thr": thr, "date": d, "plates": total, "hour_matched": int(d == "2021-07-25")}
                for ci, c in enumerate(CLASSES):
                    row["share_" + c] = float(((cl == ci) & alive).sum() / total) if total else np.nan
                    row["share_" + c + "_lo"], row["share_" + c + "_hi"] = np.nanpercentile(sb[:, ki, ci], [2.5, 97.5])
                comp.append(row)
            for grp in CURVE_GROUPS:
                regular = (wk >= thr) & group_mask(pm, grp)
                pp = ev[regular]
                n = int(regular.sum())
                pb, cb, _ = signature_bootstrap(pp, rng=rng)
                for ki, d in enumerate(evaluation):
                    plo, phi = np.nanpercentile(pb[:, ki], [2.5, 97.5])
                    clo, chi = np.nanpercentile(cb[:, ki], [2.5, 97.5])
                    curve.append({"window": wn, "thr": thr, "k": ki + 1, "date": d, "grp": grp, "n_regular": n,
                                  "present": float(pp[:, ki].mean()) if n else np.nan, "present_lo": plo, "present_hi": phi,
                                  "cum": float(pp[:, :ki + 1].any(axis=1).mean()) if n else np.nan,
                                  "cum_lo": clo, "cum_hi": chi, "hour_matched": int(d == "2021-07-25")})
    curve = pd.DataFrame(curve)
    comp = pd.DataFrame(comp)
    gaprows, firsts = [], {}
    for thr in (6, 8, 9):
        firsts[str(thr)] = {}
        for grp in CURVE_GROUPS:
            tf = curve[(curve.window == "typhoon") & (curve.thr == thr) & (curve.grp == grp)].sort_values("k")
            pf = curve[(curve.window == "placebo") & (curve.thr == thr) & (curve.grp == grp)].sort_values("k")
            delta = tf.present.values - pf.present.values
            deficit = -delta
            wkt, evt = window_cache["typhoon"]
            wkp, evp = window_cache["placebo"]
            gm = group_mask(pm, grp)
            db = paired_gap_bootstrap(evt, evp, (wkt >= thr) & gm, (wkp >= thr) & gm, rng)
            lo, hi = np.nanpercentile(db, [2.5, 97.5], axis=0)
            eligible = np.flatnonzero(deficit <= .05)
            first = int(eligible[0] + 1) if len(eligible) else None
            firsts[str(thr)][grp] = first
            for ki in range(9):
                gaprows.append({"thr": thr, "k": ki + 1, "grp": grp, "date_typhoon": E_T[ki], "date_placebo": E_P[ki],
                                "present_typhoon": tf.present.values[ki], "present_placebo": pf.present.values[ki],
                                "gap": delta[ki], "gap_lo": lo[ki], "gap_hi": hi[ki], "deficit": deficit[ki],
                                "first_k_gap_le_005": first})
    gap = pd.DataFrame(gaprows)
    csv(curve, OUT / "m3_return_curve.csv")
    csv(comp, OUT / "m3_composition.csv")
    csv(gap, OUT / "m3_return_gap.csv")
    csv(curve, ROB / "m6_threshold_sensitivity.csv")
    csv(comp, ROB / "m6_threshold_composition_sensitivity.csv")
    ordering = {}
    for thr in (6, 8, 9):
        f = firsts[str(thr)]
        local = f["local_zheD"]
        other = [f["zhejiang_other"], f["other_province"]]
        ordering[str(thr)] = bool(local is not None and all(x is None or local <= x for x in other))
    h2 = {"status": "pass" if all(ordering.values()) else "fail", "first_k_gap_le_005": firsts,
          "first_k_gap_le_0.05": firsts,
          "frozen_return_order_status": "stable_local_first" if all(ordering.values()) else "not_stable_local_first",
          "local_returns_no_later_than_nonlocal": ordering,
          "verdict_criterion": "Local regular cohort first deficit <=0.05 occurs no later than either nonlocal cohort at all thresholds; complete composition evidence is reported separately.",
          "specification_note": "Section 3.10 gives explicit stop rules for H1 and H4 only; this H2 criterion is an implementation interpretation of H2's stated threshold-order falsification condition.",
          "deficit_definition": "present_placebo minus present_typhoon; first day deficit <= 0.05",
          "window_note": "Both windows start Monday; evaluation starts Sunday at identical +4 through +12 day lags.",
          "threshold_composition_rule": "regular >= thr; frequent 4 <= k < thr; occasional 1..3; earlier_only/unseen unchanged"}
    h2["contextual_evidence"] = h2_composition_evidence(pm, comp, window_cache, class_cache, rng)
    if all(ordering.values()) and any(x["same_regular_decline_unseen_increase_direction"]
                                     for x in h2["contextual_evidence"]["composition_trends_thr8"].values()):
        h2["status"] = "mixed"
    return curve, comp, h2


def robustness_extras(extra):
    rows = []
    for target in E_T:
        scope = "n_o" + target[5:].replace("-", "")
        hs = "n_o0725_h11" if target == "2021-07-25" else scope
        for grp in GRPS:
            chosen = extra[(extra.scope == hs) & (extra.grp == grp)].set_index("date")
            for b, baseline in BASELINES.items():
                bd = [d for d in baseline if pd.Timestamp(d).dayofweek == pd.Timestamp(target).dayofweek]
                n, p = chosen.loc[target, ["records", "plates"]].values.astype(float)
                bn = chosen.loc[bd, "records"].mean()
                bp = chosen.loc[bd, "plates"].mean()
                bm = (chosen.loc[bd, "records"] / chosen.loc[bd, "plates"]).mean()
                rows.append({"date": target, "grp": grp, "baseline": b, "scope": "target_day_S_on_fixed_in_baseline",
                             "records": int(n), "plates": int(p), "rN": n / bn if bn else np.nan,
                             "rP": p / bp if bp else np.nan, "rm": (n / p) / bm if p and bm else np.nan,
                             "hour_matched": int(target == "2021-07-25")})
    csv(pd.DataFrame(rows), ROB / "m6_online_set_variant_vehicles.csv")
    grow = []
    for target in D_ALL:
        bd = [d for d in B1 if pd.Timestamp(d).dayofweek == pd.Timestamp(target).dayofweek]
        row = {"date": target, "hour_matched": int(target == "2021-07-25")}
        for label in ("gw", "nongw"):
            scope = "n_" + label + "_a100" + ("_h11" if target == "2021-07-25" else "")
            total = extra[(extra.scope == scope) & extra.grp.isin(["all", "unreadable"])].groupby("date").records.sum()
            plates = extra[(extra.scope == scope) & (extra.grp == "other_province")].set_index("date").plates
            row["r_flow_" + label] = total.loc[target] / total.loc[bd].mean() if total.loc[bd].mean() else np.nan
            row["r_other_plates_" + label] = plates.loc[target] / plates.loc[bd].mean() if plates.loc[bd].mean() else np.nan
        grow.append(row)
    gframe = pd.DataFrame(grow)
    ev = gframe[gframe.date.isin(E_T)]
    sync = {}
    for name, x, y in [("flow_between_sets", "r_flow_gw", "r_flow_nongw"),
                       ("outside_plates_between_sets", "r_other_plates_gw", "r_other_plates_nongw"),
                       ("gateway_flow_vs_outside_plates", "r_flow_gw", "r_other_plates_gw"),
                       ("nongateway_flow_vs_outside_plates", "r_flow_nongw", "r_other_plates_nongw")]:
        rho, p = spearmanr(ev[x], ev[y], nan_policy="omit")
        sync[name] = {"spearman": float(rho), "p": float(p), "n_days": len(ev)}
        gframe[name + "_rho"] = rho
        gframe[name + "_p"] = p
    csv(gframe, ROB / "m6_gateway_split.csv")
    (ROB / "m6_gateway_sync.json").write_text(json.dumps(sync, indent=2), encoding="utf-8")


def figures(main_table, curve):
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "text.color": "#333333",
                         "axes.labelcolor": "#333333", "xtick.color": "#333333", "ytick.color": "#333333"})
    groups = ["all", "local_zheD", "zhejiang_other", "other_province"]
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.8), sharex=True)
    dat = main_table[main_table.date.isin(E_T[:6]) & main_table.grp.isin(groups)].copy()
    for ax, metric, title in zip(axes, ["rP", "rm", "rN"], ["Visible vehicle ratio", "Passes per vehicle ratio", "Records ratio"]):
        for gi, grp in enumerate(groups):
            sub = dat[dat.grp == grp].sort_values("date")
            x = np.arange(len(sub))
            ax.plot(x, sub[metric].values, "o-", color=COLORS[gi], linewidth=2, markersize=8, label=grp)
            ax.fill_between(x, sub["ci_" + metric + "_lo"].values, sub["ci_" + metric + "_hi"].values, color=COLORS[gi], alpha=.12)
        ax.set_title(title)
        ax.set_xticks(np.arange(6))
        ax.set_xticklabels([d[5:] for d in E_T[:6]], rotation=35)
        ax.axhline(1, color="#999999", lw=.8)
        ax.grid(alpha=.18, linewidth=.5)
        ax.legend(fontsize=8)
    fig.text(.5, .01, "7/25: observed 11:00–23:59, with weekday and hour-matched baselines. Intervals: 200 vehicle-cluster draws.", ha="center", fontsize=9)
    fig.tight_layout(rect=[0, .04, 1, 1])
    fig.savefig(FIG / "fig3_two_margins.png", dpi=180)
    plt.close(fig)
    csv(dat, FIG / "fig3_two_margins_data.csv")
    csv(dat, FIG / "fig3_data.csv")
    fig, axes = plt.subplots(2, 4, figsize=(16, 8), sharex=True, sharey=True)
    dat = curve[(curve.thr == 8) & curve.grp.isin(groups)]
    for gi, grp in enumerate(groups):
        for rowi, metric in enumerate(("present", "cum")):
            ax = axes[rowi, gi]
            for wn, style in [("typhoon", "-"), ("placebo", "--")]:
                sub = dat[(dat.grp == grp) & (dat.window == wn)].sort_values("k")
                ax.plot(sub.k.values, sub[metric].values, style, color=COLORS[gi], lw=2, marker="o", markersize=8, label=wn)
                ax.fill_between(sub.k.values, sub[metric + "_lo"].values, sub[metric + "_hi"].values, color=COLORS[gi], alpha=.1)
            ax.set_title(grp + (" / present" if rowi == 0 else " / cumulative"))
            ax.grid(alpha=.18, linewidth=.5)
            ax.set_ylim(0, 1.05)
            ax.set_xticks(np.arange(1, 10))
            ax.legend(fontsize=8)
            if rowi == 1:
                ax.set_xlabel("Evaluation day (same weekday and lag)")
    fig.text(.5, .005, "Regular cohort: visible on Sstar on at least 8 of 10 window days. The first typhoon day has afternoon AVI coverage.", ha="center", fontsize=9)
    fig.tight_layout(rect=[0, .03, 1, 1])
    fig.savefig(FIG / "fig4_return_curves.png", dpi=180)
    plt.close(fig)
    csv(dat, FIG / "fig4_return_curves_data.csv")
    csv(dat, FIG / "fig4_data.csv")


def main():
    started = stamp()
    start = time.time()
    for folder in (OUT, ROB, FIG):
        folder.mkdir(parents=True, exist_ok=True)
    pm, masks, MN, MP, HN, HP, first, extra = load_panels()
    csv(first, OUT / "m3_first_hour.csv")
    tables, h1 = main_margins(pm, MN, MP, HN, HP)
    del MN, MP, HN, HP
    curve, comp, h2 = return_and_composition(pm, masks)
    robustness_extras(extra)
    figures(tables["B1"], curve)
    verdict = {"H1": h1, "H2": h2, "seed": SEED, "vehicle_cluster_bootstrap": 200}
    (OUT / "m3_h1_h2_verdict.json").write_text(json.dumps(verdict, indent=2, ensure_ascii=False), encoding="utf-8")
    checks = {"D_ALL_days": len(D_ALL), "master_rows": len(pm), "return_rows": len(curve), "composition_rows": len(comp),
              "bootstrap_readable_vehicle_count": int((pm.cat != "unreadable").sum()),
              "unreadable_distinct_placeholders": int((pm.cat == "unreadable").sum()),
              "bootstrap_readable_only": True,
              "unreadable_ci_not_applicable": bool(tables["B1"].loc[tables["B1"].grp == "unreadable", ["ci_rP_lo", "ci_rP_hi", "ci_rN_lo", "ci_rN_hi", "ci_rm_lo", "ci_rm_hi"]].isna().all().all()),
              "return_present_in_0_1": bool(curve.loc[curve.n_regular > 0, "present"].between(0, 1).all()),
              "return_cumulative_in_0_1": bool(curve.loc[curve.n_regular > 0, "cum"].between(0, 1).all()),
              "empty_regular_cohort_rows": int((curve.n_regular == 0).sum()),
              "composition_sum_one": bool(np.allclose(comp[["share_" + c for c in CLASSES]].sum(axis=1), 1)),
              "exact_ratio_of_aggregates_log_residual_max": float(np.nanmax(np.abs(
                  np.log(tables["B1"].rN) - np.log(tables["B1"].rP) - np.log(tables["B1"].rm_ratio_of_aggregate_sensitivity)))),
              "frozen_mean_daily_log_residual_max": float(np.nanmax(np.abs(tables["B1"].log_identity_residual))),
              "H1_stop_condition_triggered": h1["stop_condition_triggered"]}
    (OUT / "M3_CHECKS.md").write_text("# M3 checks\n\n" + "\n".join("- %s: %s" % (k, v) for k, v in checks.items()) +
        "\n\nThe main rm uses the frozen mean of daily N/P. Its log identity residual is disclosed;"
        " the ratio of aggregate baselines is a labelled diagnostic only. Unreadable placeholders are"
        " excluded from all-readable vehicle cohorts, and retained as a separate grp.\n", encoding="utf-8")
    deviations = [
        {"item": "Frozen log identity", "type": "mathematical incompatibility disclosure",
         "original": "rm=(N/P)/mean_B(N/P); log rN=log rP+log rm", "implementation": "Frozen mean ratio preserved; log_identity_residual reported.",
         "reason": "Mean of ratios differs from ratio of means", "affected": ["M3", "M6"]},
        {"item": "Threshold composition", "type": "sensitivity implementation clarification",
         "implementation": "regular >= thr; frequent 4 <= k < thr; occasional 1..3", "reason": "Mutually exclusive, exhaustive classes at thresholds 6 and 9"},
        {"item": "First deficit threshold", "type": "semantic clarification",
         "implementation": "deficit = present_placebo - present_typhoon; first deficit <= 0.05",
         "reason": "The required signed gap is negative during a deficit; applying <=0.05 to signed gap would trivially return k=1"},
        {"item": "H1 placebo and H2 composition context", "type": "predeclared evidence reporting, no new magnitude threshold",
         "implementation": "All matched-lag placebo effects/CI; complete composition pairings and endpoint/slope effects/CI. Same direction labels may qualify an overall assessment as mixed, but do not establish equal magnitude or trigger a new stop rule.",
         "reason": "The plan specifies placebo falsification qualitatively and no equivalence-size cutoff. E_P main remains all-day; 7/11 h11 is sensitivity only.",
         "affected": ["M3", "M6", "H1", "H2"]},
        {"item": "Sparse row arithmetic", "type": "implementation bug correction before M3 execution",
         "implementation": "Cast group code to int32 before day*7 addition", "reason": "Prevent int8 overflow around row 128; no scientific definition changed"},
        {"item": "Unreadable bootstrap semantics", "type": "vehicle-cluster implementation correction; all point estimates preserved",
         "implementation": "Only readable ph resampled as vehicle clusters; unreadable records held at observed values for the u proxy. Unreadable point estimates retained with distinct_unreadable_placeholders semantics, CI NA/vehicle_bootstrap_not_applicable.",
         "reason": "Unreadable strings do not identify vehicles; recognition-corrected intervals are conditional on the observed unreadable record counts.",
         "affected": ["M3", "M6"]}]
    (ROOT / "00_env/vehicle_deviations.json").write_text(json.dumps(deviations, ensure_ascii=False, indent=2), encoding="utf-8")
    execution = {"script": "scripts/m3_vehicles_v1.py", "started": started, "ended": stamp(), "seconds": time.time() - start,
                 "checks": checks, "output_files": [str(p.relative_to(ROOT)) for folder in (OUT, ROB, FIG) for p in folder.glob("*") if p.is_file()]}
    (ROOT / "00_env/vehicle_execution.json").write_text(json.dumps(execution, ensure_ascii=False, indent=2), encoding="utf-8")
    pending = OUT / "PENDING_OUTPUTS.json"
    if pending.is_file():
        pending.unlink()
    methods = OUT / "METHODS.md"
    if methods.is_file():
        text = methods.read_text(encoding="utf-8")
        start_mark, end_mark = "<!-- runtime-status -->", "<!-- runtime-status-end -->"
        if start_mark in text and end_mark in text:
            text = text.split(start_mark)[0] + start_mark + "\n当前状态：本轮 AVI 与 M3 已执行，实际结果与自检见本目录 CSV、m3_h1_h2_verdict.json 和 M3_CHECKS.md。\n" + end_mark + text.split(end_mark, 1)[1]
            methods.write_text(text, encoding="utf-8")
    print(stamp(), "M3 COMPLETE", "seconds", round(time.time() - start, 1), "H1", h1["status"], "H2", h2["status"], flush=True)


if __name__ == "__main__":
    main()
