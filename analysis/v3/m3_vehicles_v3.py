# -*- coding: utf-8 -*-
"""A2/A3/A4 analyses on frozen v1 panels; writes guarded v3 outputs only."""
import hashlib
import json
import shutil
import sys
import time
from collections import Counter

import numpy as np
import pandas as pd
from scipy import sparse

from common_v3 import ROOT, V1, PANELS, SEED, D_ALL, B1, B2, B3, B_P, W_T, W_P, E_T, E_P, now, guarded, write_json, save_csv

OUT, ROB, ENV = [ROOT / x for x in ("04_m3_vehicles", "07_m6_robustness", "00_env")]
DI = {d: i for i, d in enumerate(D_ALL)}
BASE = ["local_zheD_ICE", "local_zheD_NEV", "zhejiang_other_ICE", "zhejiang_other_NEV", "other_province_ICE", "other_province_NEV", "unreadable"]
GROUPS = BASE + ["all", "local_zheD", "zhejiang_other", "other_province", "all_ICE"]
GEO = ["local_zheD", "zhejiang_other", "other_province"]
POWER = [("all_powertrains", ""), ("ICE_only", "_ICE"), ("NEV_only", "_NEV")]
CL5 = ["regular", "frequent", "occasional", "earlier_only", "unseen"]
CL4 = ["regular", "frequent", "occasional", "nonwindow"]
EXPAND = np.zeros((7, len(GROUPS)))
EXPAND[:, :7] = np.eye(7)
EXPAND[:6, 7] = 1
EXPAND[:2, 8] = 1
EXPAND[2:4, 9] = 1
EXPAND[4:6, 10] = 1
EXPAND[[0, 2, 4], 11] = 1
METRICS = ("rP", "rm", "rN")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def export(frame, path):
    frame = frame.copy()
    for col in frame:
        if col == "plates" or col == "n_regular" or col.startswith("plates_"):
            x = pd.to_numeric(frame[col], errors="coerce")
            frame[col] = ["<10" if pd.notna(v) and v < 10 else int(v) if pd.notna(v) else "" for v in x]
    save_csv(frame, path)


def baseline_days(target, variant):
    day = pd.Timestamp(target).dayofweek
    if variant == "B1_loo":
        ds = [d for d in B1 if d != target and pd.Timestamp(d).dayofweek == day]
        pool = "B1"
        if not ds:
            ds = [d for d in sorted(set(B1 + B3)) if d != target and pd.Timestamp(d).dayofweek == day]
            pool = "B1+B3"
    else:
        ds = [d for d in dict(B1=B1, B2=B2, B3=B3, B_P=B_P)[variant] if pd.Timestamp(d).dayofweek == day]
        pool = variant
    if not ds:
        raise ValueError("No same-weekday baseline")
    return ds, pool


def load():
    pm = pd.read_parquet(PANELS / "plate_master.parquet", columns=["ph", "cat", "nev"])
    groups = pm.cat + np.where(pm.nev.astype(int).values == 1, "_NEV", "_ICE")
    groups[pm.cat == "unreadable"] = "unreadable"
    codes = pd.Categorical(groups, categories=BASE).codes.astype("int8")
    if (codes < 0).any():
        raise ValueError("Unexpected frozen vehicle category")
    index = pd.Index(pm.ph)
    masks = np.zeros(len(pm), dtype="uint64")
    triples = {name: [[], [], []] for name in ("stable", "h11", "online")}
    hdates = {"2021-07-04", "2021-07-11", "2021-07-18", "2021-07-25"}
    odates = set(["2021-07-26"] + baseline_days("2021-07-26", "B1")[0])
    for d in D_ALL:
        day = pd.read_parquet(PANELS / "plate_day" / (d + ".parquet"), columns=["ph", "n_stable"])
        idx = index.get_indexer(day.ph)
        if (idx < 0).any():
            raise ValueError("Vehicle not found in frozen master")
        good = day.n_stable.values > 0
        masks[idx[good]] |= np.uint64(1) << np.uint64(DI[d])
        vals = {"stable": day.n_stable.values}
        if d in hdates or d in odates:
            cols = ["ph"] + (["n_stable_h11"] if d in hdates else []) + (["n_o0726"] if d in odates else [])
            extra = pd.read_parquet(PANELS / "plate_day_extra" / (d + ".parquet"), columns=cols)
            if not np.array_equal(day.ph.values, extra.ph.values):
                raise ValueError("Frozen supplemental panel ordering mismatch")
            if d in hdates:
                vals["h11"] = extra.n_stable_h11.values
            if d in odates:
                vals["online"] = extra.n_o0726.values
        for name, val in vals.items():
            keep = val > 0
            rr, cc, vv = triples[name]
            rr.append(DI[d] * 7 + codes[idx[keep]].astype("int32"))
            cc.append(idx[keep].astype("int32"))
            vv.append(val[keep].astype(float))
        print(now(), "M3_V3_LOAD", d, "anonymous_rows", len(day), flush=True)
    matrices = {}
    for name, (rr, cc, vv) in triples.items():
        mn = sparse.csr_matrix((np.concatenate(vv), (np.concatenate(rr), np.concatenate(cc))), shape=(37 * 7, len(pm)))
        mp = sparse.csr_matrix((np.ones(mn.nnz, dtype="int8"), mn.indices, mn.indptr), shape=mn.shape, copy=False)
        matrices[name] = (mn, mp)
    return pm, masks, matrices


def aggregate(matrices, weights):
    return {name: [m.dot(weights).reshape(37, 7).dot(EXPAND) for m in pair] for name, pair in matrices.items()}


def templates():
    specs = []
    for k, d in enumerate(E_T, 1):
        specs.append(dict(id="typhoon_" + str(k), date=d, baseline="B1", scope="stable", hours="h11" if k == 1 else "all_day"))
    for variant in ("B2", "B3"):
        specs.append(dict(id="typhoon_k2_" + variant, date=E_T[1], baseline=variant, scope="stable", hours="all_day"))
    for variant in ("B_P", "B1_loo"):
        for k, d in enumerate(E_P, 1):
            specs.append(dict(id=variant + "_" + str(k), date=d, baseline=variant, scope="stable", hours="all_day"))
        specs.append(dict(id=variant + "_1_h11", date=E_P[0], baseline=variant, scope="stable", hours="h11_sensitivity"))
    specs.append(dict(id="online_k2", date=E_T[1], baseline="B1", scope="online", hours="all_day"))
    for s in specs:
        s["days"], s["pool"] = baseline_days(s["date"], s["baseline"])
    return specs


def ratio(arrays, spec):
    scope = "h11" if spec["hours"].startswith("h11") else spec["scope"]
    N, P = arrays[scope]
    ti = DI[spec["date"]]
    ix = [DI[d] for d in spec["days"]]
    with np.errstate(divide="ignore", invalid="ignore"):
        n, p = N[ti], P[ti]
        bn, bp = N[ix].mean(axis=0), P[ix].mean(axis=0)
        bm = (N[ix] / P[ix]).mean(axis=0)
        u = n[6] / n[:7].sum()
        ub = (N[ix, 6] / N[ix, :7].sum(axis=1)).mean()
        return dict(records=n, plates=p, baseline_records=bn, baseline_plates=bp,
                    rP=p / bp, rm=(n / p) / bm, rN=n / bn, u=u, u_base=ub)


def margins(pm, matrices):
    specs = templates()
    point_arrays = aggregate(matrices, np.ones(len(pm)))
    points = {s["id"]: ratio(point_arrays, s) for s in specs}
    samples = {s["id"]: {m: np.empty((200, len(GROUPS))) for m in METRICS} for s in specs}
    usamples = {s["id"]: {m: np.empty(200) for m in ("u", "u_base")} for s in specs}
    readable = np.flatnonzero(pm.cat.values != "unreadable")
    probs = np.full(len(readable), 1 / len(readable))
    rng = np.random.default_rng(SEED)
    for boot in range(200):
        weight = np.ones(len(pm), dtype="int64")
        weight[readable] = rng.multinomial(len(readable), probs)
        arrays = aggregate(matrices, weight)
        for spec in specs:
            result = ratio(arrays, spec)
            for m in METRICS:
                samples[spec["id"]][m][boot] = result[m]
            for m in ("u", "u_base"):
                usamples[spec["id"]][m][boot] = result[m]
        if boot % 20 == 0:
            print(now(), "M3_V3_BOOTSTRAP", boot, "of200", flush=True)
    smap = {s["id"]: s for s in specs}
    comparison, grouped = [], []
    for variant in ("B_P", "B1_loo"):
        for k in range(1, 10):
            for hours in (["all_day", "h11_sensitivity"] if k == 1 else ["all_day"]):
                ts, ps = "typhoon_" + str(k), variant + "_" + str(k) + ("_h11" if hours == "h11_sensitivity" else "")
                for power, suffix in POWER:
                    li, oi = GROUPS.index("local_zheD" + suffix), GROUPS.index("other_province" + suffix)
                    row = dict(baseline="B1", typhoon_baseline="B1", placebo_baseline=variant, baseline_variant=variant,
                               k=k, date_typhoon=E_T[k - 1], date_placebo=E_P[k - 1], powertrain_scope=power, placebo_hours=hours,
                               typhoon_hour_matched=int(k == 1), placebo_hour_matched=int(hours == "h11_sensitivity"),
                               n_baseline_days_typhoon=len(smap[ts]["days"]), n_baseline_days_placebo=len(smap[ps]["days"]),
                               placebo_baseline_pool=smap[ps]["pool"], placebo_baseline_dates=";".join(smap[ps]["days"]))
                    for side, key in (("typhoon", ts), ("placebo", ps)):
                        row["plates_local_" + side] = points[key]["plates"][li]
                        row["plates_other_" + side] = points[key]["plates"][oi]
                    for m in METRICS:
                        tv, pv = points[ts][m][li] - points[ts][m][oi], points[ps][m][li] - points[ps][m][oi]
                        tb, pb = samples[ts][m][:, li] - samples[ts][m][:, oi], samples[ps][m][:, li] - samples[ps][m][:, oi]
                        for prefix, est, draw in (("typhoon", tv, tb), ("placebo", pv, pb), ("typhoon_minus_placebo", tv - pv, tb - pb)):
                            row[prefix + "_delta_" + m] = est
                            row[prefix + "_delta_" + m + "_lo"], row[prefix + "_delta_" + m + "_hi"] = np.percentile(draw, [2.5, 97.5])
                    comparison.append(row)
                    for grp in GEO:
                        gi = GROUPS.index(grp + suffix)
                        rowg = {x: row[x] for x in ("baseline", "typhoon_baseline", "placebo_baseline", "baseline_variant", "k", "date_typhoon", "date_placebo", "powertrain_scope", "placebo_hours", "typhoon_hour_matched", "placebo_hour_matched", "n_baseline_days_typhoon", "n_baseline_days_placebo", "placebo_baseline_pool", "placebo_baseline_dates")}
                        rowg["grp"] = grp
                        for side, key in (("typhoon", ts), ("placebo", ps)):
                            rowg["plates_" + side] = points[key]["plates"][gi]
                            rowg["records_" + side] = int(points[key]["records"][gi])
                        for m in METRICS + ("u", "u_base"):
                            tv, pv = (points[ts][m], points[ps][m]) if m.startswith("u") else (points[ts][m][gi], points[ps][m][gi])
                            tb, pb = (usamples[ts][m], usamples[ps][m]) if m.startswith("u") else (samples[ts][m][:, gi], samples[ps][m][:, gi])
                            for prefix, est, draw in (("typhoon", tv, tb), ("placebo", pv, pb), ("typhoon_minus_placebo", tv - pv, tb - pb)):
                                rowg[prefix + "_" + m] = est
                                rowg[prefix + "_" + m + "_lo"], rowg[prefix + "_" + m + "_hi"] = np.percentile(draw, [2.5, 97.5])
                        grouped.append(rowg)
    comparison, grouped = pd.DataFrame(comparison), pd.DataFrame(grouped)
    export(comparison, OUT / "m3_h1_placebo_margins_v3.csv")
    export(grouped, OUT / "m3_placebo_by_group_v3.csv")
    variant_rows = []
    for label, key, li, oi in [("B1", "typhoon_2", 8, 10), ("B2", "typhoon_k2_B2", 8, 10),
                               ("B3", "typhoon_k2_B3", 8, 10), ("exclude_NEV", "typhoon_2", 0, 4),
                               ("S_on", "online_k2", 8, 10)]:
        for m in METRICS:
            delta = points[key][m][li] - points[key][m][oi]
            lo, hi = np.percentile(samples[key][m][:, li] - samples[key][m][:, oi], [2.5, 97.5])
            variant_rows.append(dict(variant=label, date="2021-07-26", metric=m, effect=delta, lo=lo, hi=hi,
                                     sign_preserved=bool(np.sign(delta) == np.sign(points["typhoon_2"][m][8] - points["typhoon_2"][m][10])),
                                     ci_excludes_0=bool(lo > 0 or hi < 0),
                                     scope="fixed_2021-07-26_S_on_in_target_and_baselines" if label == "S_on" else "Sstar"))
    variants = pd.DataFrame(variant_rows)
    export(variants, ROB / "m6_h1_variants_v3.csv")
    h1 = verdict_h1(comparison, variants)
    v1margin = pd.read_csv(V1 / "04_m3_vehicles/m3_h1_placebo_margins.csv")
    old = v1margin[(v1margin.baseline == "B1") & (v1margin.k == 2) & (v1margin.powertrain_scope == "all_powertrains") & (v1margin.placebo_hours == "all_day")].iloc[0]
    new = comparison[(comparison.placebo_baseline == "B_P") & (comparison.k == 2) & (comparison.powertrain_scope == "all_powertrains")].iloc[0]
    copied_comparison = {m: bool(round(new["typhoon_delta_" + m], 4) == round(old["typhoon_delta_" + m], 4)) for m in METRICS}
    if not all(copied_comparison.values()):
        raise AssertionError("Unchanged typhoon point estimates differ from frozen v1")
    return comparison, grouped, variants, h1, copied_comparison


def criterion(cid, statement, threshold, observed, met, required=True):
    return dict(id=cid, criterion=statement, threshold=threshold, observed=observed, met=bool(met), required_for_supported=required)


def verdict_h1(comparison, variants):
    target = comparison[(comparison.placebo_baseline == "B_P") & (comparison.k == 2) & (comparison.powertrain_scope == "all_powertrains")].iloc[0]
    obs1 = {m: [target["typhoon_delta_" + m], target["typhoon_delta_" + m + "_lo"], target["typhoon_delta_" + m + "_hi"]] for m in ("rP", "rm")}
    met1 = obs1["rP"][0] > 0 and obs1["rP"][1] > 0 and obs1["rm"][0] < 0 and obs1["rm"][2] < 0
    obs2, met2 = {}, True
    for m in ("rP", "rm"):
        p = target["placebo_delta_" + m]
        bound = max(.03, .2 * abs(target["typhoon_delta_" + m]))
        delta = [target["typhoon_minus_placebo_delta_" + m + suffix] for suffix in ("", "_lo", "_hi")]
        obs2[m] = dict(placebo_delta=p, maximum_placebo_magnitude=bound, paired_difference=delta)
        met2 &= abs(p) <= bound and (delta[1] > 0 or delta[2] < 0)
    baselines = variants[variants.variant.isin(["B2", "B3"]) & variants.metric.isin(["rP", "rm"])]
    met3 = bool(baselines.sign_preserved.all())
    sensitive = variants[variants.variant.isin(["exclude_NEV", "S_on"]) & variants.metric.isin(["rP", "rm"])]
    met4 = bool(sensitive.sign_preserved.all() and sensitive.ci_excludes_0.all())
    criteria = [criterion(1, "July26 B1 local-minus-other has opposite margins with95%CI excluding0", "delta_rP>0; delta_rm<0; both CI exclude0", obs1, met1),
                criterion(2, "Matched-lag B_P placebo has small magnitude and both paired differences exclude0", "abs(placebo)<=max(0.03,0.2*abs(typhoon)); both paired CI exclude0", obs2, met2),
                criterion(3, "B2 and B3 preserve both signs; frozen stop has priority", "No rP or rm sign reversal", baselines.to_dict("records"), met3),
                criterion(4, "ExcludeNEV and S_on preserve both signs and CI exclude0", "Both variants, both margins", sensitive.to_dict("records"), met4)]
    status = "supported" if all([met1, met2, met3, met4]) else "partial" if met1 and met3 else "not_supported"
    acceptance = []
    for m in ("rP", "rm"):
        acceptance.append(dict(check="B_P_k2_abs_placebo_" + m + "_le_0.03", observed=target["placebo_delta_" + m], met=bool(abs(target["placebo_delta_" + m]) <= .03)))
    for k in (5, 7):
        row = comparison[(comparison.placebo_baseline == "B_P") & (comparison.k == k) & (comparison.powertrain_scope == "all_powertrains")].iloc[0]
        acceptance.append(dict(check="B_P_k%d_not_algebraic_zero" % k, observed={m: row["placebo_delta_" + m] for m in METRICS}, met=bool(any(row["placebo_delta_" + m] != 0 for m in METRICS))))
    return dict(status=status, criteria=criteria, stop_condition_triggered=not met3, acceptance_checks=acceptance,
                seed=SEED, bootstrap=200, comparison="local_zheD minus other_province", placebo_baseline="B_P",
                reviewer_authorised_amendments=["A2", "A3"], vehicle_bootstrap="readable vehicle clusters; shared weights across all variants")


def bits(masks, days):
    return np.column_stack([((masks >> np.uint64(DI[d])) & np.uint64(1)).astype("int8") for d in days])


def joint_composition_draws(et, ep, ct, cp, readable, rng):
    t, p = et[readable], ep[readable]
    powers = 1 << np.arange(9, dtype="int32")
    st = (t * powers).sum(axis=1).astype("int32") + ct[readable].astype("int32") * 512
    sp = (p * powers).sum(axis=1).astype("int32") + cp[readable].astype("int32") * 512
    uniq, count = np.unique(st + 2560 * sp, return_counts=True)
    tc, pc = uniq % 2560, uniq // 2560
    tp, pp = ((tc % 512)[:, None] & powers) != 0, ((pc % 512)[:, None] & powers) != 0
    weight = rng.multinomial(len(t), count / len(t), size=200).astype(float)
    den_t, den_p = weight.dot(tp.astype(float)), weight.dot(pp.astype(float))
    bt, bp = np.empty((200, 9, 5)), np.empty((200, 9, 5))
    with np.errstate(divide="ignore", invalid="ignore"):
        for c in range(5):
            bt[:, :, c] = weight.dot((tp & ((tc // 512)[:, None] == c)).astype(float)) / den_t
            bp[:, :, c] = weight.dot((pp & ((pc // 512)[:, None] == c)).astype(float)) / den_p
    return bt, bp


def composition(pm, masks):
    readable = pm.cat.values != "unreadable"
    cache = {}
    for label, window, evaluation in (("typhoon", W_T, E_T), ("placebo", W_P, E_P)):
        wk = bits(masks, window).sum(axis=1)
        prev = [d for d in D_ALL if d < window[0]]
        earlier = bits(masks, prev).any(axis=1)
        cache[label] = (wk, earlier, bits(masks, evaluation))
    rows, pairrows, five_rows, convergence = [], [], [], []
    rng = np.random.default_rng(SEED)
    for thr in (6, 8, 9):
        classes = {}
        for label in cache:
            wk, earlier, ev = cache[label]
            cl = np.full(len(pm), 4, dtype="int8")
            cl[(wk == 0) & earlier] = 3
            cl[(wk >= 1) & (wk <= 3)] = 2
            cl[(wk >= 4) & (wk < thr)] = 1
            cl[wk >= thr] = 0
            classes[label] = cl
        et, ep = cache["typhoon"][2], cache["placebo"][2]
        bt5, bp5 = joint_composition_draws(et, ep, classes["typhoon"], classes["placebo"], readable, rng)
        points, draws = {}, {}
        for label, ev, draw in (("typhoon", et, bt5), ("placebo", ep, bp5)):
            cl = classes[label]
            pt = np.array([[(readable & (ev[:, ki] == 1) & (cl == ci)).sum() / (readable & (ev[:, ki] == 1)).sum() for ci in range(5)] for ki in range(9)])
            p4 = np.column_stack([pt[:, :3], pt[:, 3:].sum(axis=1)])
            b4 = np.concatenate([draw[:, :, :3], draw[:, :, 3:].sum(axis=2)[:, :, None]], axis=2)
            points[label] = (p4, pt)
            draws[label] = (b4, draw)
            for ki, date in enumerate(E_T if label == "typhoon" else E_P):
                row = dict(window=label, thr=thr, k=ki + 1, date=date,
                           plates=int((readable & (ev[:, ki] == 1)).sum()), hour_matched=int(label == "typhoon" and ki == 0),
                           source="recomputed_A4_from_formal_v1_panels")
                for ci, cls in enumerate(CL4):
                    row["share_" + cls] = p4[ki, ci]
                    row["share_" + cls + "_lo"], row["share_" + cls + "_hi"] = np.percentile(b4[:, ki, ci], [2.5, 97.5])
                for ci, cls in enumerate(CL5):
                    row["share_" + cls + "_5class"] = pt[ki, ci]
                    row["share_" + cls + "_5class_lo"], row["share_" + cls + "_5class_hi"] = np.percentile(draw[:, ki, ci], [2.5, 97.5])
                rows.append(row)
        for ci, cls in enumerate(CL4):
            gap = points["typhoon"][0][:, ci] - points["placebo"][0][:, ci]
            increases = np.flatnonzero(np.diff(np.abs(gap[1:])) > 0) + 3
            if cls == "regular":
                convergence.append(dict(thr=thr, criterion="abs(regular_gap) narrows k2..k9, at most1 increasing step", increasing_step_count=len(increases),
                                        increasing_to_k=";".join(str(x) for x in increases), met=bool(len(increases) <= 1)))
            for ki in range(9):
                row = dict(thr=thr, k=ki + 1, **{"class": cls}, date_typhoon=E_T[ki], date_placebo=E_P[ki],
                           share_typhoon=points["typhoon"][0][ki, ci], share_placebo=points["placebo"][0][ki, ci],
                           gap=gap[ki], typhoon_minus_placebo=gap[ki], typhoon_partial_day=int(ki == 0), placebo_partial_day=0)
                for prefix, draw in (("share_typhoon", draws["typhoon"][0][:, ki, ci]), ("share_placebo", draws["placebo"][0][:, ki, ci]),
                                     ("gap", draws["typhoon"][0][:, ki, ci] - draws["placebo"][0][:, ki, ci])):
                    row[prefix + "_lo"], row[prefix + "_hi"] = np.percentile(draw, [2.5, 97.5])
                pairrows.append(row)
        for ci, cls in enumerate(CL5):
            for ki in range(9):
                row = dict(thr=thr, k=ki + 1, **{"class_5class": cls}, date_typhoon=E_T[ki], date_placebo=E_P[ki],
                           share_typhoon_5class=points["typhoon"][1][ki, ci], share_placebo_5class=points["placebo"][1][ki, ci],
                           gap_5class=points["typhoon"][1][ki, ci] - points["placebo"][1][ki, ci])
                for prefix, draw in (("share_typhoon", bt5[:, ki, ci]), ("share_placebo", bp5[:, ki, ci]), ("gap", bt5[:, ki, ci] - bp5[:, ki, ci])):
                    row[prefix + "_5class_lo"], row[prefix + "_5class_hi"] = np.percentile(draw, [2.5, 97.5])
                five_rows.append(row)
        print(now(), "M3_V3_COMPOSITION", "threshold", thr, flush=True)
    frame, paired, five = pd.DataFrame(rows), pd.DataFrame(pairrows), pd.DataFrame(five_rows)
    export(frame, OUT / "m3_composition_v3.csv")
    export(paired, OUT / "m3_h2_composition_placebo_v3.csv")
    export(five, OUT / "m3_h2_composition_placebo_5class_v3.csv")
    export(pd.DataFrame(convergence), OUT / "m3_composition_convergence_v3.csv")
    gap = pd.read_csv(V1 / "04_m3_vehicles/m3_return_gap.csv")
    h2 = verdict_h2(paired, gap, convergence)
    return frame, paired, five, h2


def verdict_h2(paired, gap, convergence):
    firsts, ordered = {}, {}
    for thr in (6, 8, 9):
        firsts[str(thr)] = {}
        for grp in GEO:
            sub = gap[(gap.thr == thr) & (gap.grp == grp)].sort_values("k")
            matches = sub[sub.deficit <= .05]
            firsts[str(thr)][grp] = int(matches.k.iloc[0]) if len(matches) else None
        vals = [firsts[str(thr)][g] for g in GEO]
        ordered[str(thr)] = all(v is not None for v in vals) and vals[0] <= vals[1] <= vals[2]
    vals = [firsts["8"][g] for g in GEO]
    met1 = all(ordered.values()) and (vals[0] < vals[1] or vals[1] < vals[2])
    k2 = paired[(paired.thr == 8) & (paired.k == 2)].set_index("class")
    rr, nw = k2.loc["regular"], k2.loc["nonwindow"]
    met2 = rr.gap > 0 and rr.gap_lo > 0 and nw.gap < 0 and nw.gap_hi < 0
    k9 = paired[(paired.thr == 8) & (paired.k == 9) & (paired["class"] == "nonwindow")].iloc[0]
    met3 = k9.gap_lo <= 0 <= k9.gap_hi or abs(k9.gap) <= .03
    persistent = gap[(gap.thr == 8) & (gap.grp == "zhejiang_other") & gap.k.between(5, 9)].copy()
    persists = bool((persistent.gap < 0).all() and (persistent.gap_hi < 0).all())
    persistence_note = "浙江其他规律车辆存在约2–3个百分点的持续缺口" if persists else "浙江其他规律车辆k5..9未全部表现为区间排除0的负缺口；逐日值已完整报告"
    export(persistent, OUT / "m3_zhejiang_other_persistent_gap_v3.csv")
    criteria = [criterion(1, "First deficit<=0.05 is ordered across3geographic cohorts atall thresholds", "thr8 local<=zhejiang_other<=other_province with>=1strict; thr6/9 order preserved", dict(first_k=firsts, ordered=ordered), met1),
                criterion(2, "thr8 k2 four-class composition has opposite signed contrasts", "regular>0; nonwindow<0; both95%CI exclude0", {"regular": rr.to_dict(), "nonwindow": nw.to_dict()}, met2),
                criterion(3, "thr8 k9 nonwindow converges", "95%CI contains0 or abs(gap)<=0.03", k9.to_dict(), met3),
                criterion(4, "Report Zhejiang-other k5..9 present deficit", "Descriptive; does not affect H2 verdict", dict(persistent=persists, rows=persistent.to_dict("records"), note=persistence_note), True, required=False)]
    status = "supported" if met1 and met2 and met3 else "partial" if met1 and met2 else "not_supported"
    return dict(status=status, criteria=criteria, first_k_gap_le_005=firsts, first_k_gap_le_0_05=firsts,
                persistent_zhejiang_other_gap=dict(persistent=persists, note=persistence_note, rows=persistent.to_dict("records")),
                acceptance_checks=dict(nonwindow_k9_point_within_003=bool(abs(k9.gap) <= .03), regular_narrowing=convergence),
                seed=SEED, bootstrap=200, reviewer_authorised_amendments=["A3", "A4"],
                deficit_definition="present_placebo minus present_typhoon; first deficit<=0.05", five_class_descriptive_only=True,
                **{"first_k_gap_le_0.05": firsts})


def copy_results():
    copied = []
    for name in ("m3_return_curve.csv", "m3_return_gap.csv", "m3_two_margins_table.csv"):
        src, target = V1 / "04_m3_vehicles" / name, OUT / name
        shutil.copyfile(src, guarded(target))
        if sha(src) != sha(target):
            raise AssertionError("Copied frozen result differs")
        copied.append(dict(file="04_m3_vehicles/" + name, source="formal_v1", sha256=sha(target)))
    return copied


def main():
    started, clock = now(), time.monotonic()
    protocol = ENV / "vehicle_protocol_v3.json"
    frozen = json.loads(protocol.read_text(encoding="utf-8"))
    if frozen["status"] != "frozen_before_calculation" or frozen["B_P"] != B_P:
        raise AssertionError("Frozen vehicle protocol differs from calculation definitions")
    protocol_hash = sha(protocol)
    for folder in (OUT, ROB, ENV):
        folder.mkdir(parents=True, exist_ok=True)
    try:
        pm, masks, matrices = load()
        comparisons, grouped, variants, h1, equal_v1 = margins(pm, matrices)
        del matrices
        comp, paired, five, h2 = composition(pm, masks)
        copied = copy_results()
        checks = dict(status="passed", seed=SEED, master_rows=len(pm), readable_vehicle_clusters=int((pm.cat != "unreadable").sum()),
                      protocol_unchanged=sha(protocol) == protocol_hash, B_P_days=len(B_P), B_P_weekday_counts=dict(Counter(pd.Timestamp(d).dayofweek for d in B_P)),
                      T19_comparison_rows=len(comparisons), T19_group_rows=len(grouped), T20_composition_rows=len(comp),
                      T20_fourclass_paired_rows=len(paired), T20_fiveclass_paired_rows=len(five), unchanged_typhoon_k2_points_equal_v1=equal_v1,
                      composition4_sum_one=bool(np.allclose(comp[["share_" + c for c in CL4]].sum(axis=1), 1)),
                      composition5_sum_one=bool(np.allclose(comp[["share_" + c + "_5class" for c in CL5]].sum(axis=1), 1)),
                      nonwindow_exact_sum_earlier_unseen=bool(np.allclose(comp.share_nonwindow, comp.share_earlier_only_5class + comp.share_unseen_5class)),
                      paired_fourclass_gap_sum_zero=bool(np.allclose(paired.pivot(index=["thr", "k"], columns="class", values="gap").sum(axis=1), 0)),
                      source_access="Existing formal_v1/01_panels and aggregate results only", hmac_key_access=False, panel_copies=False,
                      copied_results=copied)
        if not all(checks[x] for x in ("protocol_unchanged", "composition4_sum_one", "composition5_sum_one", "nonwindow_exact_sum_earlier_unseen", "paired_fourclass_gap_sum_zero")):
            raise AssertionError("Vehicle checks failed")
        write_json(OUT / "m3_h1_verdict_v3.json", h1)
        write_json(OUT / "m3_h2_verdict_v3.json", h2)
        write_json(OUT / "m3_h1_h2_verdict_v3.json", dict(H1=h1, H2=h2, seed=SEED, vehicle_cluster_bootstrap=200))
        write_json(ENV / "vehicle_checks_v3.json", checks)
        write_json(OUT / "vehicle_results_v3.json", dict(placebo_BP=grouped[grouped.placebo_baseline == "B_P"].to_dict("records"),
                   placebo_contrasts=comparisons[comparisons.placebo_baseline == "B_P"].to_dict("records"),
                   composition_4class=paired.to_dict("records"), verdicts_v3=dict(H1=h1, H2=h2)))
        write_json(ENV / "vehicle_execution_v3.json", dict(status="complete", started=started, ended=now(), seconds=time.monotonic() - clock,
                   command=[sys.executable] + sys.argv, seed=SEED, protocol_sha256=protocol_hash, checks=checks,
                   H1=h1["status"], H2=h2["status"], output_files=[str(p.relative_to(ROOT)) for folder in (OUT, ROB) for p in folder.glob("*") if p.is_file()]))
        print(now(), "M3_V3_COMPLETE", "H1", h1["status"], "H2", h2["status"], "seconds", round(time.monotonic() - clock, 1), flush=True)
    except Exception as exc:
        write_json(ENV / "vehicle_execution_v3.json", dict(status="failed", started=started, ended=now(), seconds=time.monotonic() - clock,
                   command=[sys.executable] + sys.argv, safe_error_type=type(exc).__name__, protocol_sha256=protocol_hash))
        raise


if __name__ == "__main__":
    main()
