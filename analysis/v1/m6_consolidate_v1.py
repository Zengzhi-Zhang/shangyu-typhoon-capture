"""Consolidate the completed, prespecified M6 analyses without new source I/O.

Requires final M3/M4/M5 products. No modelling, resampling, source scans or new
stopping rule. Comparison labels describe the signs of the named numeric
effects; equality means equality at the delivery precision, not equivalence.
"""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[2]), str(_ReleasePath(__file__).resolve().parents[0])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
import argparse
import json
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 20261005
TZ = timezone(timedelta(hours=8))
GROUPS = ["all", "local_zheD", "zhejiang_other", "other_province"]
CLASSES = ["regular", "frequent", "occasional", "earlier_only", "unseen"]
BASELINES = ["B1", "B2", "B3"]
EVENT = pd.date_range("2021-07-25", "2021-08-02").strftime("%Y-%m-%d").tolist()
BASE_DATES = ["2021-07-26", "2021-07-27", "2021-07-28"]


def stamp():
    return datetime.now(TZ).isoformat()


def finite(value):
    try:
        return np.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def number(value):
    return float(value) if finite(value) else np.nan


def display(value, digits=4):
    return format(float(value), ".%df" % digits) if finite(value) else "NA"


def compare(reference, effect):
    if not finite(reference) or not finite(effect):
        return "不可比较（NA）"
    ref = round(float(reference), 4)
    val = round(float(effect), 4)
    if np.sign(float(reference)) != np.sign(float(effect)):
        return "翻转"
    if ref == val:
        return "稳定"
    return "方向一致但幅度变" if np.sign(ref) == np.sign(val) else "翻转"


def clean(obj):
    if isinstance(obj, dict):
        return {str(k): clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean(v) for v in obj]
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, (float, np.floating)):
        return float(obj) if np.isfinite(obj) else None
    return obj


class Consolidate:
    def __init__(self, root):
        self.root = Path(root)
        self.rob = self.root / "07_m6_robustness"
        self.inputs = {}
        self.outputs = []
        self.rows = []
        self.started = stamp()

    def register(self, rel):
        path = self.root / rel
        s = path.stat()
        self.inputs[rel] = {"size": s.st_size, "mtime_ns": s.st_mtime_ns}
        return path

    def read(self, rel):
        frame = pd.read_csv(self.register(rel), encoding="utf-8-sig")
        if len(frame) == 0:
            raise RuntimeError("Required final table is empty: " + rel)
        return frame

    def jread(self, rel):
        return json.loads(self.register(rel).read_text(encoding="utf-8"))

    def save(self, frame, rel):
        frame = frame.copy()
        # Count columns remain masked if the upstream vehicle aggregation used
        # <10. Never reconstruct their hidden values from another table.
        counts = {"plates", "n_regular", "n_vehicles", "n_other_plates", "n_local_plates"}
        for col in counts.intersection(frame.columns):
            values = pd.to_numeric(frame[col], errors="coerce")
            frame[col] = ["<10" if str(original) == "<10" or (pd.notna(v) and v < 10)
                          else str(int(v)) if pd.notna(v) else ""
                          for original, v in zip(frame[col], values)]
        for col in [c for c in frame if c.startswith("plates_") and "baseline" not in c]:
            values = pd.to_numeric(frame[col], errors="coerce")
            frame[col] = ["<10" if str(original) == "<10" or (pd.notna(v) and v < 10)
                          else str(int(v)) if pd.notna(v) else ""
                          for original, v in zip(frame[col], values)]
        path = self.root / rel
        frame.to_csv(path, index=False, encoding="utf-8-sig", float_format="%.4f")
        self.outputs.append({"file": rel, "rows": len(frame)})

    def load(self):
        self.m2, self.m3 = {}, {}
        for baseline in BASELINES:
            suffix = "" if baseline == "B1" else "_" + baseline
            self.m2[baseline] = self.read("03_m2_two_sources/m2_daily_ratios" + suffix + ".csv")
            self.m3[baseline] = self.read("04_m3_vehicles/m3_daily_by_group" + suffix + ".csv")
        self.curve = self.read("04_m3_vehicles/m3_return_curve.csv")
        self.comp = self.read("04_m3_vehicles/m3_composition.csv")
        self.gap = self.read("04_m3_vehicles/m3_return_gap.csv")
        self.placebo = self.read("04_m3_vehicles/m3_h1_placebo_margins.csv")
        self.comp_paired = self.read("04_m3_vehicles/m3_h2_composition_placebo.csv")
        self.comp_trends = self.read("04_m3_vehicles/m3_h2_composition_trends.csv")
        self.nev = self.read("07_m6_robustness/m6_exclude_nev.csv")
        self.ident = self.read("07_m6_robustness/m6_identification_correction.csv")
        self.online = self.read("07_m6_robustness/m6_online_set_variant_vehicles.csv")
        self.gateway = self.read("07_m6_robustness/m6_gateway_split.csv")
        self.gateway_sync = self.jread("07_m6_robustness/m6_gateway_sync.json")
        self.vehicle_verdict = self.jread("04_m3_vehicles/m3_h1_h2_verdict.json")
        self.h3 = self.jread("05_m4_spatial/m4_h3_verdict.json")
        self.h4 = self.jread("06_m5_bias_correction/m5_h4_verdict.json")
        self.ols = self.read("05_m4_spatial/m4_ols.csv")
        self.neg_ols = self.read("07_m6_robustness/m6_spatial_negative_control_ols.csv")
        self.failure_tests = self.read("06_m5_bias_correction/m5_failure_nonrandomness.csv")
        self.neg_failure = self.read("07_m6_robustness/m6_negative_control_0708_0710.csv")
        self.correction = self.read("06_m5_bias_correction/m5_correction_methods.csv")
        self.validation = self.read("06_m5_bias_correction/m5_leaveout_validation.csv")
        self.validation_fw = self.read("06_m5_bias_correction/m5_leaveout_validation_flowweighted.csv")
        statuses = [self.vehicle_verdict.get(h, {}).get("status") for h in ["H1", "H2"]]
        statuses += [self.h3.get("status", self.h3.get("H3")), self.h4.get("H4")]
        if any(v in [None, "pending", "incomplete"] for v in statuses):
            raise RuntimeError("All actual M3/M4/M5 verdicts must be complete before M6 consolidation")
        if set(self.curve.thr) != {6, 8, 9} or set(self.curve.window) != {"typhoon", "placebo"}:
            raise AssertionError("All frozen return arms are required")

    @staticmethod
    def select(frame, date, grp=None, baseline=None):
        subset = frame[frame.date.eq(date)]
        if grp is not None:
            subset = subset[subset.grp.eq(grp)]
        if baseline is not None and "baseline" in subset:
            subset = subset[subset.baseline.eq(baseline)]
        if len(subset) != 1:
            raise AssertionError("Expected exactly one aggregate row for the selected date/group/baseline")
        return subset.iloc[0]

    @classmethod
    def margin_effect(cls, frame, date, metric, baseline=None,
                      local="local_zheD", other="other_province"):
        return number(cls.select(frame, date, local, baseline)[metric]) - number(
            cls.select(frame, date, other, baseline)[metric])

    def row(self, hypothesis, conclusion, variant, metric, reference, effect,
            date="", grp="all", reference_variant="B1/Sstar", **extra):
        self.rows.append({"hypothesis": hypothesis, "conclusion": conclusion,
            "date": date, "grp": grp, "variant": variant,
            "reference_variant": reference_variant, "metric": metric,
            "reference_effect": number(reference), "effect": number(effect),
            "reference_sign": int(np.sign(float(reference))) if finite(reference) else np.nan,
            "effect_sign": int(np.sign(float(effect))) if finite(effect) else np.nan,
            "status": compare(reference, effect), **extra})

    def deliverables(self):
        long_rows = []
        for baseline in BASELINES:
            for date in BASE_DATES:
                row = self.select(self.m2[baseline], date)
                long_rows.append({"module": "M2", "date": date, "baseline": baseline,
                                  "grp": "all", "metric": "R_stable", "value": row.R_stable})
            for grp in GROUPS:
                row = self.select(self.m3[baseline], "2021-07-26", grp)
                for metric in ["rP", "rm"]:
                    long_rows.append({"module": "M3", "date": "2021-07-26", "baseline": baseline,
                                      "grp": grp, "metric": metric, "value": row[metric]})
        baseline_long = pd.DataFrame(long_rows)
        self.save(baseline_long, "07_m6_robustness/m6_baseline_sensitivity.csv")
        online_parts = []
        for baseline in BASELINES:
            x = self.m2[baseline].copy()
            x["module"], x["baseline"], x["grp"] = "M2", baseline, "all"
            x["scope"] = "target_day_S_on_fixed_in_baseline"
            x["R_stable_reference"] = x.R_stable
            x["variant"] = "S_on"
            online_parts.append(x)
        x = self.online.copy()
        x["module"], x["variant"] = "M3", "S_on"
        online_parts.append(x)
        online = pd.concat(online_parts, ignore_index=True, sort=False)
        self.save(online, "07_m6_robustness/m6_online_set_variant.csv")
        curves = self.curve.copy()
        curves["row_type"] = "return_curve"
        composition = self.comp.copy()
        composition["row_type"], composition["grp"] = "composition", "all"
        firsts = {"typhoon": pd.Timestamp("2021-07-25"), "placebo": pd.Timestamp("2021-07-11")}
        composition["k"] = [(pd.Timestamp(d)-firsts[w]).days+1 for w, d in zip(composition.window, composition.date)]
        combined = pd.concat([curves, composition], ignore_index=True, sort=False)
        self.save(combined, "07_m6_robustness/m6_threshold_sensitivity.csv")
        return baseline_long, online, combined

    def margins(self):
        h1_exact = self.vehicle_verdict["H1"]["2021-07-26_local_minus_other"]
        for metric in ["rP", "rm"]:
            for date in EVENT:
                reference = self.margin_effect(self.m3["B1"], date, metric)
                if date == "2021-07-26":
                    reference = number(h1_exact["B1"][metric])
                for baseline in ["B2", "B3"]:
                    effect = self.margin_effect(self.m3[baseline], date, metric)
                    if date == "2021-07-26":
                        effect = number(h1_exact[baseline][metric])
                    self.row("H1", "本地减次与外省缺席两边际", baseline, "local_minus_other_"+metric,
                             reference, effect, date=date, baseline=baseline,
                             frozen_stop_triggered=self.vehicle_verdict["H1"]["stop_condition_triggered"])
                ice = self.margin_effect(self.nev, date, metric, baseline="B1",
                                         local="local_zheD_ICE", other="other_province_ICE")
                self.row("H1", "剔除新能源后的两边际", "exclude_nev", "local_minus_other_"+metric,
                         reference, ice, date=date)
                for baseline in BASELINES:
                    ref = self.margin_effect(self.m3[baseline], date, metric)
                    effect = self.margin_effect(self.online, date, metric, baseline=baseline)
                    self.row("H1", "逐日在线集合替代稳定集合", "S_on_"+baseline,
                             "local_minus_other_"+metric, ref, effect, date=date,
                             reference_variant=baseline+"/Sstar", baseline=baseline)
        for date in EVENT[:4]:
            reference = self.margin_effect(self.ident, date, "rP")
            effect = self.margin_effect(self.ident, date, "rP_idcorr")
            self.row("H1", "识别率代理校正车牌边际", "identification_correction",
                     "local_minus_other_rP", reference, effect, date=date,
                     note="Only the rP direction is checked; rm is not silently identification corrected.")
        p = self.placebo[(self.placebo.powertrain_scope == "all_powertrains") &
                         (self.placebo.placebo_hours == "all_day")]
        for _, row in p.iterrows():
            for metric in ["rP", "rm"]:
                self.row("H1", "同滞后同星期安慰剂两边际", "lag_matched_placebo_"+row.baseline,
                         "local_minus_other_"+metric, row["typhoon_delta_"+metric],
                         row["placebo_delta_"+metric], date=row.date_typhoon,
                         reference_variant=row.baseline+"/typhoon", baseline=row.baseline,
                         k=row.k, placebo_date=row.date_placebo,
                         typhoon_minus_placebo_effect=row["typhoon_minus_placebo_delta_"+metric],
                         note="Same sign is not magnitude equivalence; no new falsification threshold.")

    def first_k(self, threshold, grp):
        stored = self.vehicle_verdict["H2"]["first_k_gap_le_005"][str(threshold)].get(grp)
        return float(stored) if stored is not None else np.nan

    def ordering_effect(self, threshold, other):
        local, outside = self.first_k(threshold, "local_zheD"), self.first_k(threshold, other)
        if finite(local) and finite(outside):
            return local-outside, float(np.sign(local-outside)), local-outside, local-outside
        if finite(local):
            return np.nan, -1.0, np.nan, local-10
        if finite(outside):
            return np.nan, 1.0, 10-outside, np.nan
        return np.nan, np.nan, np.nan, np.nan

    def threshold(self):
        for threshold in [6, 8, 9]:
            for other in ["zhejiang_other", "other_province"]:
                ref, refs, ref_lo, ref_hi = self.ordering_effect(8, other)
                value, signs, lo, hi = self.ordering_effect(threshold, other)
                if finite(refs) and finite(signs):
                    status = "翻转" if refs != signs else ("稳定" if
                        ((finite(ref) and finite(value) and ref == value) or threshold == 8) else "方向一致但幅度变")
                else:
                    status = "不可比较（右删失）"
                self.row("H2", "规律车首次缺口闭合顺序", "threshold_"+str(threshold),
                    "first_k_local_minus_nonlocal", ref, value, grp=other,
                    reference_variant="threshold_8", thr=threshold,
                    first_k_local=self.first_k(threshold, "local_zheD"),
                    first_k_nonlocal=self.first_k(threshold, other),
                    reference_first_k_local=self.first_k(8, "local_zheD"),
                    reference_first_k_nonlocal=self.first_k(8, other),
                    reference_effect_lower=ref_lo, reference_effect_upper=ref_hi,
                    effect_lower=lo, effect_upper=hi,
                    right_censoring="NA first day means deficit not <=0.05 by k9; bounds use >=10, not an observed first day.")
                self.rows[-1].update({"status": status, "reference_sign": refs, "effect_sign": signs})
            for grp in GROUPS:
                for metric in ["present", "cum"]:
                    def value(thr, window):
                        x = self.curve[(self.curve.thr == thr) & (self.curve.grp == grp) &
                                       (self.curve.k == 9) & (self.curve.window == window)]
                        if len(x) != 1:
                            raise AssertionError("Missing return arm")
                        return number(x.iloc[0][metric])
                    ref_t, ref_p = value(8, "typhoon"), value(8, "placebo")
                    vt, vp = value(threshold, "typhoon"), value(threshold, "placebo")
                    self.row("H2", "第9日规律车台风与安慰剂差", "threshold_"+str(threshold),
                        metric+"_typhoon_minus_placebo_k9", ref_t-ref_p, vt-vp,
                        date="2021-08-02", grp=grp, reference_variant="threshold_8", thr=threshold,
                        present_or_cum_typhoon=vt, present_or_cum_placebo=vp,
                        reference_typhoon=ref_t, reference_placebo=ref_p,
                        first_k_gap_le_005=self.first_k(threshold, grp))
            for k in range(1, 10):
                for cls in CLASSES:
                    def share(thr, window):
                        subset = self.comp[(self.comp.thr == thr) & (self.comp.window == window)].sort_values("date")
                        return number(subset.iloc[k-1]["share_"+cls])
                    reference = share(8, "typhoon")-share(8, "placebo")
                    effect = share(threshold, "typhoon")-share(threshold, "placebo")
                    ref_ci = self.comp_paired[(self.comp_paired.thr == 8) & (self.comp_paired.k == k) & (self.comp_paired["class"] == cls)].iloc[0]
                    ci = self.comp_paired[(self.comp_paired.thr == threshold) & (self.comp_paired.k == k) & (self.comp_paired["class"] == cls)].iloc[0]
                    self.row("H2", "构成份额的台风与安慰剂差", "threshold_"+str(threshold),
                        "share_"+cls+"_typhoon_minus_placebo", reference, effect,
                        date=EVENT[k-1], grp=cls, reference_variant="threshold_8", thr=threshold, k=k,
                        reference_effect_lo=ref_ci.gap_lo, reference_effect_hi=ref_ci.gap_hi,
                        effect_lo=ci.gap_lo, effect_hi=ci.gap_hi,
                        share_typhoon=share(threshold, "typhoon"), share_placebo=share(threshold, "placebo"))
        for _, trend in self.comp_trends.iterrows():
            for metric in ["change", "slope_per_day"]:
                self.row("H2", "构成变化在同滞后安慰剂中的方向", "lag_matched_placebo_threshold_"+str(trend.thr),
                    "composition_"+metric, trend["typhoon_"+metric], trend["placebo_"+metric],
                    date="2021-08-02", grp=trend["class"], reference_variant="typhoon_threshold_"+str(trend.thr),
                    thr=trend.thr, k_start=trend.k_start, k_end=trend.k_end,
                    reference_effect_lo=trend["typhoon_"+metric+"_lo"], reference_effect_hi=trend["typhoon_"+metric+"_hi"],
                    effect_lo=trend["placebo_"+metric+"_lo"], effect_hi=trend["placebo_"+metric+"_hi"],
                    typhoon_minus_placebo_effect=trend["typhoon_minus_placebo_"+metric],
                    note="Same-direction trends do not imply equal-sized shifts; both k1-k9 and full-day k2-k9 contexts retained.")

    def observation_and_spatial(self):
        for date in BASE_DATES:
            reference = number(self.select(self.m2["B1"], date).R_stable)-1
            for baseline in ["B2", "B3"]:
                self.row("M2", "稳定卡口流量相对基线的增减方向", baseline, "R_stable_minus_one",
                         reference, number(self.select(self.m2[baseline], date).R_stable)-1,
                         date=date, baseline=baseline)
        for date in EVENT:
            for baseline in BASELINES:
                selected = self.select(self.m2[baseline], date)
                self.row("M2", "在线集合替代稳定集合的流量方向", "S_on_"+baseline,
                         "R_minus_one", number(selected.R_stable)-1, number(selected.R_online)-1,
                         date=date, reference_variant=baseline+"/Sstar", baseline=baseline)
        distance = self.ols[self.ols.term.eq("np.log1p(dist_baiguan_km)")]
        ref = distance[distance.date.eq("2021-07-26")].iloc[0]
        for _, row in self.neg_ols[self.neg_ols.term.eq("np.log1p(dist_baiguan_km)")].iterrows():
            self.row("H3", "控制协变量后的距离关联与平台阴性对照", "platform_control_"+row.date,
                     "OLS_log1p_distance_coef", ref.coef, row.coef, date="2021-07-26",
                     reference_variant="event_0726", reference_p=ref.p, p=row.p,
                     control_date=row.date, module_verdict=self.h3.get("status", self.h3.get("H3")))
        correlations = self.h3.get("taxi_camera_correlations", {})
        for label, values in correlations.items():
            camera = values["spearman_dist_camera"]
            taxi = values["spearman_dist_taxi"]
            self.row("H3", "同网格卡口与出租车距离梯度", "taxi_paired_grids", "spearman_dist_ratio",
                     camera.get("rho"), taxi.get("rho"), date="2021-"+label[:2]+"-"+label[2:],
                     reference_variant="camera_paired_grids", reference_p=camera.get("p"), p=taxi.get("p"),
                     n_grids=values["n_grids"], module_verdict=self.h3.get("status", self.h3.get("H3")))
        ref_failure = self.failure_tests[self.failure_tests.date.eq("2021-07-26")].set_index("test")
        for _, row in self.neg_failure[self.neg_failure.date.isin(["2021-07-08", "2021-07-10"])].iterrows():
            refrow = ref_failure.loc[row.test]
            self.row("H4", "失效属性与平台阴性对照", "platform_control_"+row.date,
                     row.test+"_standardized_z", refrow.z, row.z, date="2021-07-26",
                     reference_variant="event_0726", test=row.test, control_date=row.date,
                     reference_observed=refrow.observed, observed=row.observed,
                     reference_p=refrow.p_perm, p=row.p_perm,
                     module_verdict=self.h4["H4"], frozen_stop_triggered=self.h4["stop_condition_triggered"],
                     note="Different failure counts affect join-count scale; raw observed, z and p remain alongside each other.")
        for _, row in self.correction.iterrows():
            ref = row.R_naive-row.R_stable
            for method in ["knn", "stratum"]:
                self.row("H4", "校正后与稳定集合的可见比例差", method, "R_minus_R_stable",
                         ref, row["R_"+method]-row.R_stable, date=row.date,
                         reference_variant="naive", module_verdict=self.h4["H4"],
                         note="Sstar is an observed benchmark, not unobserved citywide truth.")
        r = self.validation.set_index(["date", "method"])
        for _, row in self.validation_fw.iterrows():
            ref = r.loc[(row.date, row.method)]
            self.row("H4", "随机与流量加权掩蔽预测偏差", "flowweighted", "signed_leaveout_bias",
                     ref.bias_mean, row.bias_mean, date=row.date, grp=row.method,
                     reference_variant="random", reference_mae=ref.mae, mae=row.mae,
                     module_verdict=self.h4["H4"], note="Validation is within Sstar only.")

    def gateway_rows(self):
        reference = self.gateway_sync["nongateway_flow_vs_outside_plates"]
        for name, values in self.gateway_sync.items():
            effect = values.get("spearman", values.get("rho"))
            ref = reference.get("spearman", reference.get("rho")) if name == "gateway_flow_vs_outside_plates" else np.nan
            self.row("M6_gateway", "门户与非门户同步性", name, "Spearman_rho", ref, effect,
                     reference_variant="nongateway_flow_vs_outside_plates" if finite(ref) else "descriptive_only",
                     date="", date_start="2021-07-25", date_end="2021-08-02", p=values.get("p"), n_days=values.get("n_days"),
                     note="No significance or equivalence threshold is introduced for gateway synchrony.")
            if not finite(ref):
                self.rows[-1]["status"] = "不判定（描述性相关）"

    def summary(self, matrix):
        h1, h2 = self.vehicle_verdict["H1"], self.vehicle_verdict["H2"]
        signs = h1["2021-07-26_local_minus_other"]
        text = ["# M6 稳健性与阴性对照\n",
            "全部预设变体已由实际正式面板计算。状态矩阵逐项列出参照效应、变体效应及符号；“稳定”仅指同符号且四位导出精度相等，“方向一致但幅度变”指同符号但数值不同，“翻转”包括反号或零与非零变化，均不等同于统计等效或假设的新停止条件。NA 与右删失单列，不填零。\n"]
        text.append("H1：%s；冻结停止条件%s。7/26 本地−外省的 (rP, rm) 差：%s。识别率代理只校正 rP，剔除新能源和 S_on 保留各自完整数字；不将这些比较另设停止阈值。\n" % (
            h1["status"], "触发" if h1["stop_condition_triggered"] else "未触发",
            "；".join(b+" ("+display(signs[b]["rP"])+", "+display(signs[b]["rm"])+")" for b in BASELINES)))
        context = h1.get("contextual_evidence", {})
        if context:
            text.append("同滞后安慰剂 k=2：台风/安慰剂 ΔrP=%s/%s，Δrm=%s/%s；同方向不代表幅度等效，完整配对差及区间见 m3_h1_placebo_margins.csv。\n" % tuple(
                display(context.get(k)) for k in ["typhoon_delta_rP", "placebo_delta_rP", "typhoon_delta_rm", "placebo_delta_rm"]))
        threshold_lines = []
        for thr in [6, 8, 9]:
            values = [display(self.first_k(thr, grp), 0) if finite(self.first_k(thr, grp)) else ">9（右删失）" for grp in GROUPS[1:]]
            threshold_lines.append(str(thr)+"："+"/".join(values))
        text.append("H2：%s。首次缺口≤0.05 的 k（本地/浙江其他/外省）：%s。第9日 present/cum 的台风−安慰剂差和五类构成份额在全部阈值下均落盘；评价窗保持同星期与同滞后，7/25 仍有半天观测限制。\n" % (h2["status"], "；".join(threshold_lines)))
        trends = h2.get("contextual_evidence", {}).get("composition_trends_thr8", {}).get("k2_k9", {})
        if trends:
            text.append("构成全日上下文 k2–k9（阈值8）：规律份额变化台风/安慰剂=%s/%s，陌生份额变化=%s/%s。全部阈值与两个起点的变化、斜率和配对区间均列入矩阵；同方向不构成幅度等效证据。\n" % tuple(
                display(trends.get(key)) for key in ["typhoon_regular_change", "placebo_regular_change", "typhoon_unseen_change", "placebo_unseen_change"]))
        for h in ["H1", "H2"]:
            selected = matrix[matrix.hypothesis.eq(h)]
            tally = selected.status.value_counts()
            text.append(h+"数值方向比较："+"、".join(str(key)+" "+str(value)+" 项" for key, value in tally.items())+"；各比较的实际效应及参照定义见矩阵，翻转项全部保留。\n")
        d = self.ols[self.ols.term.eq("np.log1p(dist_baiguan_km)")]
        dtext = "；".join(row.date+" coef="+display(row.coef)+", p="+display(row.p) for _, row in d.iterrows())
        text.append("H3：%s。距离系数：%s。平台阴性对照及同一网格两源梯度的 rho/p 均列入矩阵；地形项不显著不能证明地形无关，完整判定沿用 m4_h3_verdict.json。\n" % (self.h3.get("status", self.h3.get("H3")), dtext))
        text.append("H4：%s；冻结强制停止条件%s，7/26 join-count/基线流量差异 p=%s/%s。阴性日全部检验、两种掩蔽方式及校正与稳定集合的实际比例差均报告；drop 的设备级 MAE 为 NA，外推代理误差单独标注。留出仅验证 S* 内预测，不能据此宣称全城真实恢复。\n" % (
            self.h4["H4"], "触发" if self.h4["stop_condition_triggered"] else "未触发",
            display(self.h4["joincount_0726_p"]), display(self.h4["mean_log_base_diff_0726_p"])))
        text.append("门户同步性（7/25–8/2）："+"；".join(name+" rho="+display(v.get("spearman", v.get("rho")))+", p="+display(v.get("p"), 6) for name, v in self.gateway_sync.items())+"。不新增相关显著性或等效阈值。\n")
        text.append("所有源校验由环境阶段单独完成；本脚本只读正式聚合产物，不改变冻结基线、设备集合、安慰剂或判定规则。7/22–7/24 仅描述观测系统状态；未使用因果或跨城市外推解释。\n")
        path = self.rob / "m6_summary.md"
        path.write_text("\n".join(text), encoding="utf-8")
        self.outputs.append({"file": "07_m6_robustness/m6_summary.md", "rows": None})

    def run(self):
        t = time.monotonic()
        self.load()
        baseline, online, threshold = self.deliverables()
        self.margins()
        self.threshold()
        self.observation_and_spatial()
        self.gateway_rows()
        matrix = pd.DataFrame(self.rows)
        self.save(matrix, "07_m6_robustness/m6_robustness_matrix.csv")
        self.summary(matrix)
        checks = {"baseline_long_33_rows": len(baseline) == 33,
            "baseline_long_schema": baseline.columns.tolist() == ["module", "date", "baseline", "grp", "metric", "value"],
            "online_vehicle_rows_preserved": int(online.module.eq("M3").sum()) == len(self.online),
            "online_M2_three_baselines_all_days": int(online.module.eq("M2").sum()) == sum(len(x) for x in self.m2.values()),
            "threshold_curve_and_composition_complete": len(threshold) == len(self.curve)+len(self.comp),
            "threshold_row_types": set(threshold.row_type) == {"return_curve", "composition"},
            "all_matrix_rows_have_numeric_effect_or_explicit_NA": matrix.status.notna().all(),
            "no_pending_verdict": all(v not in [None, "pending", "incomplete"] for v in [self.vehicle_verdict["H1"]["status"], self.vehicle_verdict["H2"]["status"], self.h3.get("status", self.h3.get("H3")), self.h4["H4"]])}
        for rel, before in self.inputs.items():
            stat = (self.root/rel).stat()
            checks["input_unchanged:"+rel] = before == {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns}
        if not all(bool(v) for v in checks.values()):
            raise AssertionError("M6 consolidation check failed")
        report = {"seed": SEED, "script": "scripts/m6_consolidate_v1.py", "status": "complete",
            "started": self.started, "ended": stamp(), "seconds": round(time.monotonic()-t, 2),
            "inputs": self.inputs, "outputs": self.outputs, "checks": checks,
            "status_definition": "Sign change has priority. Stable means matching sign and equality at four exported decimal places; otherwise matching sign with different magnitude. This is descriptive and adds no stopping rule.",
            "right_censoring": "Unknown first gap day remains NA; >=10 is only a bound for ordering, never an observed k."}
        (self.root/"00_env/m6_consolidate_execution.json").write_text(json.dumps(clean(report), ensure_ascii=False, indent=2), encoding="utf-8")
        (self.rob/"M6_CONSOLIDATE_CHECKS.json").write_text(json.dumps(clean(checks), ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"M6_consolidate": "complete", "matrix_rows": len(matrix), "seconds": report["seconds"]}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=_release_path('project_root'))
    args = parser.parse_args()
    Consolidate(args.root).run()
