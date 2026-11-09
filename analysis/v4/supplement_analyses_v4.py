# -*- coding: utf-8 -*-
"""Descriptive T24-T26 only; frozen v1/v3 inputs stay read-only."""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[2]), str(_ReleasePath(__file__).resolve().parents[0])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
import hashlib
import json
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

V1 = Path(_release_path('project_root'))
V3 = V1 / "formal_v3"
ROOT = V1 / "formal_v4"
OUT = ROOT / "10_supplementary_analyses"
ENV = ROOT / "00_env"
SEED = 20261005
np.random.seed(SEED)
TZ = timezone(timedelta(hours=8))
DATES = ["2021-06-17"] + pd.date_range("2021-06-28", "2021-08-02").strftime("%Y-%m-%d").tolist()
PARTIAL = ["2021-07-08", "2021-07-10", "2021-07-22", "2021-07-23", "2021-07-24", "2021-07-25"]
B1 = [d for d in pd.date_range("2021-07-05", "2021-07-21").strftime("%Y-%m-%d") if d not in PARTIAL]
B3 = ["2021-06-17"] + pd.date_range("2021-06-28", "2021-07-04").strftime("%Y-%m-%d").tolist()
ORDINARY = sorted(set(B1 + B3) - set(PARTIAL))
WT = pd.date_range("2021-07-12", "2021-07-21").strftime("%Y-%m-%d").tolist()
GRPS = ["all", "local_zheD", "zhejiang_other", "other_province"]
DI = {d: i for i, d in enumerate(DATES)}
MARGIN_INPUT = V3 / "04_m3_vehicles/m3_h1_placebo_margins_v3.csv"
MATRIX_INPUT = V3 / "07_m6_robustness/m6_robustness_matrix_v3.csv"
GAP_INPUT = V3 / "04_m3_vehicles/m3_zhejiang_other_persistent_gap_v3.csv"
T1_INPUT = V1 / "02_m1_observation/m1_daily_coverage.csv"


def now():
    return datetime.now(TZ).isoformat(timespec="seconds")


def guard(path):
    path = Path(path).resolve()
    if ROOT.resolve() not in path.parents:
        raise RuntimeError("v4 write outside authorised directory")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def clean(x):
    if isinstance(x, dict):
        return {str(k): clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [clean(v) for v in x]
    if isinstance(x, np.generic):
        return clean(x.item())
    if isinstance(x, float):
        return round(x, 4) if np.isfinite(x) else None
    return x


def write_json(path, obj):
    guard(path).write_text(json.dumps(clean(obj), ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def csv(df, path):
    df = df.copy()
    for col in df:
        if col in ("plates", "singleton_plates", "two_day_plates", "regular_plates"):
            df[col] = df[col].map(lambda n: "<10" if pd.notna(n) and n < 10 else int(n) if pd.notna(n) else "")
    df.to_csv(guard(path), index=False, encoding="utf-8-sig", float_format="%.4f")


def fingerprint(paths):
    out = []
    for p in paths:
        st = p.stat()
        h = hashlib.sha256()
        with p.open("rb") as f:
            for chunk in iter(lambda: f.read(4 * 1024 * 1024), b""):
                h.update(chunk)
        out.append(dict(path=str(p), size=st.st_size, mtime_ns=st.st_mtime_ns, sha256=h.hexdigest()))
    return out


def group_values(codes, keep, weights=None):
    v = np.bincount(codes[keep], weights=None if weights is None else weights[keep], minlength=4)
    return np.array([v.sum(), v[0], v[1], v[2]])


def t24():
    master = pd.read_parquet(V1 / "01_panels/plate_master.parquet", columns=["ph", "cat"])
    cats = ["local_zheD", "zhejiang_other", "other_province", "unreadable"]
    codes = pd.Categorical(master.cat, categories=cats).codes.astype("int8")
    assert (codes >= 0).all()
    index = pd.Index(master.ph)
    assert index.is_unique
    counts = {scope: np.zeros(len(master), dtype="uint8") for scope in ("full_network", "Sstar")}
    wk = np.zeros(len(master), dtype="uint8")
    totals = {scope: dict(N=np.zeros((37, 4)), P=np.zeros((37, 4))) for scope in counts}
    for d in DATES:
        day = pd.read_parquet(V1 / "01_panels/plate_day" / (d + ".parquet"), columns=["ph", "n", "n_stable"])
        idx = index.get_indexer(day.ph)
        assert (idx >= 0).all() and day.ph.is_unique
        cc = codes[idx]
        for scope, column in (("full_network", "n"), ("Sstar", "n_stable")):
            val = day[column].values
            visible = val > 0
            counts[scope][idx[visible]] += 1
            totals[scope]["N"][DI[d]] = group_values(cc, visible, val)
            totals[scope]["P"][DI[d]] = group_values(cc, visible)
            if scope == "Sstar" and d in WT:
                wk[idx[visible]] += 1
        print(now(), "T24_PRESENCE", d, flush=True)
    regular = (wk >= 8) & (codes != 3)
    rows = []
    for d in DATES:
        day = pd.read_parquet(V1 / "01_panels/plate_day" / (d + ".parquet"), columns=["ph", "n", "n_stable"])
        idx = index.get_indexer(day.ph)
        cc = codes[idx]
        for scope, column in (("full_network", "n"), ("Sstar", "n_stable")):
            visible = day[column].values > 0
            p, n = totals[scope]["P"][DI[d]], totals[scope]["N"][DI[d]]
            singleton = group_values(cc, visible & (counts[scope][idx] == 1))
            two = group_values(cc, visible & (counts[scope][idx] <= 2))
            reg = group_values(cc, visible & regular[idx])
            for gi, grp in enumerate(GRPS):
                rows.append(dict(date=d, scope=scope, primary_scope=int(scope == "Sstar"), grp=grp,
                                 plates=int(p[gi]), records=int(n[gi]), plates_per_1000_records=1000 * p[gi] / n[gi] if n[gi] else np.nan,
                                 singleton_plates=int(singleton[gi]), two_day_plates=int(two[gi]), regular_plates=int(reg[gi]),
                                 singleton_share=singleton[gi] / p[gi] if p[gi] else np.nan,
                                 two_day_share=two[gi] / p[gi] if p[gi] else np.nan,
                                 regular_share_window=reg[gi] / p[gi] if p[gi] else np.nan,
                                 regular_share_window_context=int(d >= WT[0]), regular_cohort_scope="readable_Sstar_W_T_k_ge_8", readable_only=int(grp != "all"),
                                 plate_count_semantics="panel_distinct_ph_including_unreadable_placeholders_diagnostic_only" if grp == "all" else "readable_vehicle_category"))
    frame = pd.DataFrame(rows)
    flag_info = {}
    for (scope, grp), sub in frame.groupby(["scope", "grp"], sort=False):
        base = sub[sub.date.isin(ORDINARY)].singleton_share.values
        med = np.median(base)
        mad = np.median(np.abs(base - med))
        ix = sub.index
        deviation = sub.singleton_share.values - med
        frame.loc[ix, "baseline_singleton_median"] = med
        frame.loc[ix, "baseline_singleton_MAD"] = mad
        frame.loc[ix, "singleton_deviation"] = deviation
        frame.loc[ix, "flag_plate_noise"] = (np.abs(deviation) > 2.5 * mad).astype(int)
        frame.loc[ix, "noise_flag_direction"] = np.where(np.abs(deviation) > 2.5 * mad, np.where(deviation > 0, "high", "low"), "unflagged")
        flag_info[scope + "/" + grp] = dict(ordinary_days=len(base), median=med, MAD=mad, threshold=2.5 * mad,
               flagged_dates=frame.loc[ix][frame.loc[ix, "flag_plate_noise"] == 1][["date", "singleton_share", "noise_flag_direction"]].to_dict("records"))
    frame.flag_plate_noise = frame.flag_plate_noise.astype(int)
    event = frame.date.between("2021-07-25", "2021-07-27")
    frame["event_interpretation"] = np.where(event, "singleton减少可能反映一次性外来车辆减少或捕获机会改变；两种机制不能由此诊断区分，Sstar为主", "描述性质量指标，不把MAD标记解释为已证实识别错误")
    primary = frame[(frame.scope == "Sstar") & (frame.grp == "all")].set_index("date")
    acceptance = dict(expected_high_days={d: bool(primary.loc[d, "flag_plate_noise"]) for d in ("2021-07-06", "2021-07-14", "2021-07-15")},
                      expected_event_unflagged={d: bool(primary.loc[d, "flag_plate_noise"] == 0) for d in ("2021-07-25", "2021-07-26", "2021-07-27")})
    t1 = pd.read_csv(T1_INPUT).set_index("date")
    full = frame[(frame.scope == "full_network") & (frame.grp == "all")].set_index("date")
    assert (full.records == t1.loc[full.index, "records"]).all()
    assert (full.plates == t1.loc[full.index, "plates_all"]).all()
    assert int(full.records.sum()) == 282152315
    info = dict(primary_scope="Sstar", all_group="all panel ph and all records including unreadable placeholders; diagnostic count, not a true vehicle total", singleton_presence="37 days separately within each scope",
                regular_cohort="Frozen Sstar W_T visible>=8days, common to both diagnostic scopes", ordinary_dates=ORDINARY,
                MAD_rule="abs(singleton_share-median)>2.5*raw_MAD; two-sided including low outliers; no1.4826scale", by_scope_group=flag_info,
                acceptance=acceptance, event_primary=primary.loc["2021-07-25":"2021-07-27"].reset_index().to_dict("records"),
                T1_independent_check=dict(all37_records_equal=True, all37_distinct_ph_equal=True, records_total=int(full.records.sum()),
                                         maximum_daily_records_difference=0, maximum_daily_distinct_ph_difference=0, source="formal_v1/02_m1_observation/m1_daily_coverage.csv"))
    assert len(frame) == 37 * 2 * 4
    assert (frame.singleton_share <= frame.two_day_share).all()
    assert frame[["singleton_share", "two_day_share", "regular_share_window"]].ge(0).all().all()
    assert frame[["singleton_share", "two_day_share", "regular_share_window"]].le(1).all().all()
    csv(frame, OUT / "t24_plate_quality_v4.csv")
    write_json(OUT / "t24_flagged_dates_v4.json", info)
    return frame, totals["Sstar"], info


def ordinary_refs(target):
    dow = pd.Timestamp(target).dayofweek
    if target in B3:
        pool, ds = "B1+B3", sorted(set(B1 + B3))
    else:
        pool, ds = "B1", B1
    refs = [d for d in ds if d != target and pd.Timestamp(d).dayofweek == dow]
    if not refs:
        pool = "B1+B3"
        refs = [d for d in sorted(set(B1 + B3)) if d != target and pd.Timestamp(d).dayofweek == dow]
    assert refs and target not in refs
    return refs, pool


def t25(totals):
    N, P = totals["N"], totals["P"]
    rows = []
    for d in ORDINARY:
        refs, pool = ordinary_refs(d)
        ix, ti = [DI[x] for x in refs], DI[d]
        rP = P[ti] / P[ix].mean(axis=0)
        rN = N[ti] / N[ix].mean(axis=0)
        rm = (N[ti] / P[ti]) / (N[ix] / P[ix]).mean(axis=0)
        rows.append(dict(sample="ordinary_loo", date=d, k=np.nan, baseline_pool=pool, n_baseline_days=len(refs),
                         baseline_dates=";".join(refs), hour_matched=0,
                         delta_rP=rP[1] - rP[3], delta_rm=rm[1] - rm[3], delta_rN=rN[1] - rN[3]))
    margins = pd.read_csv(MARGIN_INPUT)
    placebo = margins[(margins.placebo_baseline == "B_P") & (margins.powertrain_scope == "all_powertrains") & (margins.placebo_hours == "all_day")].sort_values("k")
    assert len(placebo) == 9 and not placebo.k.duplicated().any()
    for row in placebo.itertuples(index=False):
        rows.append(dict(sample="placebo_BP", date=row.date_placebo, k=int(row.k), baseline_pool="B_P",
                         n_baseline_days=int(row.n_baseline_days_placebo), baseline_dates=row.placebo_baseline_dates,
                         hour_matched=0, delta_rP=row.placebo_delta_rP, delta_rm=row.placebo_delta_rm, delta_rN=row.placebo_delta_rN))
    null = pd.DataFrame(rows)
    summaries = {}
    for name, sub in (("ordinary_loo", null[null["sample"] == "ordinary_loo"]), ("placebo_BP", null[null["sample"] == "placebo_BP"]), ("combined", null)):
        summaries[name] = {}
        for m in ("rP", "rm", "rN"):
            a = sub["delta_" + m].values
            q = np.percentile(a, [2.5, 50, 97.5])
            summaries[name][m] = dict(n=len(a), p025=q[0], p50=q[1], p975=q[2], abs_p975=np.percentile(np.abs(a), 97.5), max_abs=np.abs(a).max())
    typhoon_rows = []
    for row in placebo.itertuples(index=False):
        for m in ("rP", "rm", "rN"):
            estimate = getattr(row, "typhoon_delta_" + m)
            limits = summaries["combined"][m]
            typhoon_rows.append(dict(k=int(row.k), date=row.date_typhoon, metric=m, baseline="B1", hour_matched=int(row.typhoon_hour_matched),
               delta_typhoon=estimate, delta_typhoon_lo=getattr(row, "typhoon_delta_" + m + "_lo"), delta_typhoon_hi=getattr(row, "typhoon_delta_" + m + "_hi"),
               null_n=limits["n"], null_p025=limits["p025"], null_p50=limits["p50"], null_p975=limits["p975"], null_abs_p975=limits["abs_p975"],
               null_max_abs=limits["max_abs"], outside_envelope=abs(estimate) > limits["max_abs"], exceeds_p975=abs(estimate) > limits["abs_p975"],
               outside_signed_p025_p975=estimate < limits["p025"] or estimate > limits["p975"]))
    contrast = pd.DataFrame(typhoon_rows)
    acceptance = dict(k1_k3_both_margins_outside_max={str(k): bool(contrast[(contrast.k == k) & contrast.metric.isin(["rP", "rm"])].outside_envelope.all()) for k in (1, 2, 3)},
                      k4_k9_rP_at_least_one_inside_max=bool((~contrast[(contrast.k >= 4) & (contrast.metric == "rP")].outside_envelope).any()),
                      k4_k9_rP_all_inside_max=bool((~contrast[(contrast.k >= 4) & (contrast.metric == "rP")].outside_envelope).all()))
    first_inside = {}
    for m in ("rP", "rm"):
        sub = contrast[contrast.metric == m].sort_values("k")
        match = sub[~sub.outside_envelope]
        first_inside[m] = int(match.k.iloc[0]) if len(match) else None
    info = dict(descriptive_only=True, verdict_changes=False, ordinary_dates=ORDINARY, ordinary_n=23, placebo_n=9, combined_n=32,
                envelope=summaries, exceeds_p975_definition="abs(delta_typhoon)>P97.5(abs(delta_null)); signed lower/upper quantiles and outside_signed_p025_p975 also retained",
                first_k_inside_max_envelope=first_inside, acceptance=acceptance, typhoon_comparisons=contrast.to_dict("records"),
                provenance_placebo="existing formal_v3 B_P all_powertrains all_day rows; no recomputation", k1="Typhoon11-23matchedB1; main placeboJuly11all-day unchanged")
    assert len(null) == 32 and len(contrast) == 27 and len(ORDINARY) == 23
    csv(null, OUT / "t25_margin_null_distribution_v4.csv")
    csv(contrast, OUT / "t25_typhoon_vs_envelope_v4.csv")
    write_json(OUT / "t25_summary_v4.json", info)
    return null, contrast, info


def classify(row):
    v, h, m, g, d = [str(row[x]) if pd.notna(row[x]) else "" for x in ("variant", "hypothesis", "metric", "grp", "date")]
    if v == "A100_floor":
        return "C", "C1", "A100-floor距离系数已知方向不一致项"
    if v == "taxi_paired_grids" or m.startswith("dist_taxi/") or m.startswith("dist_camera/"):
        return "C", "C2", "出租车与卡口距离梯度并列；不作为估计量保号"
    if h == "H2" and g == "zhejiang_other" and v == "threshold_8" and m == "present_typhoon_minus_placebo_k9":
        return "C", "C3", "浙江其他规律车辆主阈值第9日小缺口；k5-9另直接引用既有v3结果"
    if m == "R_stable_B3" or (h == "M2" and v == "B3" and d == "2021-07-28" and m == "R_stable_minus_one"):
        return "C", "C4", "B3夏季漂移与7/28稳定口径方向；不改原效应"
    if "placebo" in v.lower() or v in ("B_P", "B1_loo") or v.startswith("platform_control_") or (h == "H2" and m == "gap"):
        return "B", "B", "安慰剂/阴性对照或描述性两窗口比较，不计翻转"
    if v in ("B2", "B3", "exclude_NEV", "exclude_nev", "identification_correction", "threshold_6", "threshold_9", "S_on") or v.startswith("S_on_") or "A6" in v:
        return "A", "A", "方案列出的估计量变体；不因效应或保号结果排除"
    return "D", "D", "原估计、主阈值或未列入A的其他描述/校正/留出结果，保留全部行"


def t26():
    matrix = pd.read_csv(MATRIX_INPUT)
    assert len(matrix) == 810
    matrix["source_csv_row"] = np.arange(len(matrix)) + 2
    tuples = matrix.apply(classify, axis=1)
    matrix[["robustness_class", "class_item", "classification_reason"]] = pd.DataFrame(tuples.tolist(), index=matrix.index)
    matrix["record_origin"] = "original_matrix"
    matrix["count_in_A_denominator"] = matrix.robustness_class == "A"
    original = matrix.copy()
    extra = pd.read_csv(GAP_INPUT)
    assert len(extra) == 5 and set(extra.k) == set(range(5, 10))
    addition = pd.DataFrame([dict(hypothesis="H2", conclusion="浙江其他规律车辆k5-9小缺口", date=r.date_typhoon, grp="zhejiang_other", variant="threshold_8_existing_v3",
                  metric="present_typhoon_minus_placebo", effect=r.gap, lo=r.gap_lo, hi=r.gap_hi, reference_effect=np.nan, sign_preserved=np.nan,
                  ci_excludes_0=bool(r.gap_lo > 0 or r.gap_hi < 0), source="existing_v3_result:04_m3_vehicles/m3_zhejiang_other_persistent_gap_v3.csv",
                  k=r.k, thr=r.thr, source_csv_row=i + 2, robustness_class="C", class_item="C3", classification_reason="方案要求完整k5-9，直接引用既有v3行；无新效应计算",
                  record_origin="existing_v3_result", count_in_A_denominator=False) for i, r in enumerate(extra.itertuples(index=False))])
    matrix = pd.concat([matrix, addition], ignore_index=True)
    stats = []
    for (cls, hyp, conclusion), sub in original.groupby(["robustness_class", "hypothesis", "conclusion"], dropna=False, sort=False):
        s = sub.sign_preserved.dropna().astype(bool)
        ci = sub.ci_excludes_0.dropna().astype(bool)
        stats.append(dict(robustness_class=cls, hypothesis=hyp, conclusion=conclusion if pd.notna(conclusion) else "原矩阵未给conclusion；按metric/variant明细追溯",
              n_rows=len(sub), n_sign_available=len(s), n_sign_preserved=int(s.sum()) if cls == "A" else np.nan,
              sign_preserved_share=float(s.mean()) if cls == "A" and len(s) else np.nan,
              n_ci_available=len(ci), n_ci_excludes_0=int(ci.sum()) if len(ci) else np.nan,
              ci_excludes_0_share=float(ci.mean()) if len(ci) else np.nan, sign_flip_counted=int(cls == "A")))
    stats = pd.DataFrame(stats)
    false_a = original[(original.robustness_class == "A") & (original.sign_preserved == False)].copy()
    by_hyp = []
    for hyp in ["H1", "H2", "H3", "H4", "M2"]:
        sub = original[(original.robustness_class == "A") & (original.hypothesis == hyp)]
        s, ci = sub.sign_preserved.dropna().astype(bool), sub.ci_excludes_0.dropna().astype(bool)
        by_hyp.append(dict(hypothesis=hyp, n_rows=len(sub), n_sign_available=len(s), n_sign_preserved=int(s.sum()),
                          sign_preserved_share=float(s.mean()) if len(s) else np.nan, non_sign_preserving=len(s) - int(s.sum()),
                          n_ci_available=len(ci), n_ci_excludes_0=int(ci.sum()), ci_excludes_0_share=float(ci.mean()) if len(ci) else np.nan))
    by_hyp = pd.DataFrame(by_hyp)
    csv(matrix, OUT / "t26_robustness_by_class_v4.csv")
    csv(stats, OUT / "t26_class_summary_v4.csv")
    csv(by_hyp, OUT / "t26_A_by_hypothesis_v4.csv")
    csv(false_a, OUT / "t26_non_sign_preserving_A_v4.csv")
    citems = {item: int((matrix.class_item == item).sum()) for item in ("C1", "C2", "C3", "C4")}
    assert set(original.source_csv_row) == set(range(2, 812)) and all(citems.values())
    inherited = original[[c for c in pd.read_csv(MATRIX_INPUT, nrows=0).columns]]
    pd.testing.assert_frame_equal(inherited.reset_index(drop=True), pd.read_csv(MATRIX_INPUT).reset_index(drop=True), check_dtype=False)
    assert len(matrix) == 815 and len(original) == 810
    table = by_hyp.to_markdown(index=False, floatfmt=".4f")
    failures = false_a[["source_csv_row", "hypothesis", "date", "grp", "variant", "metric", "effect", "reference_effect"]].to_markdown(index=False, floatfmt=".4f")
    text = "# T26 稳健性矩阵分类汇总\n\n" + \
      "原矩阵810行全部保留，另直接引用既有v3浙江其他k5–9缺口5行，共815行。效应、区间、原保号与CI字段均未重算或修改。A依据方案列出的变体分类；B为安慰剂/平台及两窗口描述比较，不计翻转；C为四项已知方向不一致；其余D保留原估计、校正方法和留出结果。各行带source_csv_row及分类原因。\n\n" + table + \
      "\n\n比例分母仅为原字段可用行，缺失不会填True。H4在指定A变体中没有行，因此保号率为NA，不能写100%。有CI的原比例恢复水平行，其ci_excludes_0表示区间不含0，不等于相对1显著。全部不保号A行如下：\n\n" + failures + \
      "\n\nC四项均完整单列：C1 A100-floor距离系数7/26为+0.0523，区间[-0.0507,0.1554]，相对Sstar负系数反号；C2出租车与卡口距离梯度并列，7/26原矩阵为+0.1932与参照-0.2836；C3浙江其他k5–9缺口直接引用既有v3五行，k7区间含0，不能概括五日均有显著2–3pp缺口；C4 B3下7/28 R_stable_minus_one=-0.1267，即同一既有效应的R_stable=0.8733，夏季漂移在矩阵既有15日R_stable_B3中并列（方案概述φ≈0.90）。\n\n" + \
      "验收期待A全部100%且无不保号项未满足时按明细如实报告，不通过重新分类异常来获得100%。以上为描述性整理，不改H1–H4定稿verdict。"
    guard(OUT / "t26_summary_v4.md").write_text(text + "\n", encoding="utf-8")
    summary = dict(original_rows=810, appended_existing_v3_rows=5, output_rows=815, class_counts=original.robustness_class.value_counts().to_dict(),
                   C_item_counts=citems, A_by_hypothesis=by_hyp.to_dict("records"), A_non_sign_preserving=false_a.to_dict("records"),
                   all_original_effects_and_flags_equal=True, acceptance=dict(C_four_items_complete=all(citems.values()), A_zero_non_sign_preserving=len(false_a) == 0,
                   A_each_H1_H2_H3_H4_all_100=bool(all((x["n_sign_available"] > 0 and x["non_sign_preserving"] == 0) for x in by_hyp[by_hyp.hypothesis.isin(["H1", "H2", "H3", "H4"])].to_dict("records")))))
    write_json(OUT / "t26_summary_v4.json", summary)
    return matrix, summary


def main():
    started, clock = now(), time.monotonic()
    inputs = [V1 / "01_panels/plate_master.parquet"] + [V1 / "01_panels/plate_day" / (d + ".parquet") for d in DATES] + [MARGIN_INPUT, MATRIX_INPUT, GAP_INPUT, T1_INPUT]
    before = fingerprint(inputs)
    try:
        quality, totals, quality_summary = t24()
        null, contrasts, null_summary = t25(totals)
        matrix, matrix_summary = t26()
        after = fingerprint(inputs)
        assert before == after
        public = [p for p in OUT.glob("*") if p.suffix in (".csv", ".json", ".md", ".txt")]
        plate_pattern = re.compile(r"[京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼使领][A-Z][A-Z0-9]{5,6}")
        hm_pattern = re.compile(r"(?<![0-9a-fA-F.])[0-9a-fA-F]{16}(?![0-9a-fA-F.])")
        hits = [p.name for p in public if plate_pattern.search(p.read_text(encoding="utf-8-sig")) or hm_pattern.search(p.read_text(encoding="utf-8-sig")) or "\ufffd" in p.read_text(encoding="utf-8-sig")]
        assert not hits
        details = dict(status="complete", started=started, ended=now(), seconds=time.monotonic() - clock, command=[sys.executable] + sys.argv,
                       seed=SEED, input_fingerprints_begin=before, input_fingerprints_end=after, inputs_unchanged=True,
                       raw_source_access=False, hmac_key_access=False, M3_M6_reexecution=False, verdict_changes=False,
                       checks=dict(T24_rows=len(quality), T25_ordinary_rows=23, T25_null_rows=len(null), T25_contrast_rows=len(contrasts),
                                   T26_original_rows=810, T26_output_rows=len(matrix), all_original_matrix_effects_equal=True, public_privacy_hits=hits),
                       acceptance=dict(T24=quality_summary["acceptance"], T25=null_summary["acceptance"], T26=matrix_summary["acceptance"]),
                       T1_independent_check=quality_summary["T1_independent_check"],
                       output_files=[str(p.relative_to(ROOT)) for p in public])
        write_json(ENV / "supplement_execution_v4.json", details)
        print(now(), "SUPPLEMENTS_COMPLETE", "seconds", round(time.monotonic() - clock, 1), flush=True)
    except Exception as exc:
        write_json(ENV / "supplement_execution_v4.json", dict(status="failed", started=started, ended=now(), seconds=time.monotonic() - clock,
                   command=[sys.executable] + sys.argv, safe_error_type=type(exc).__name__, input_fingerprints_begin=before))
        raise


if __name__ == "__main__":
    main()
