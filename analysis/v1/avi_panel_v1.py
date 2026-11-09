# -*- coding: utf-8 -*-
"""Version 1: one read-only AVI pass; raw plates exist only in memory.

The required plate_day schema is kept separate from additional frozen-set/hour
panels.  Fixed target-day online sets are applied to both numerator and baseline.
Run in Git Bash: PYTHONIOENCODING=utf-8 <configured-path> scripts/avi_panel_v1.py
"""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[2]), str(_ReleasePath(__file__).resolve().parents[0])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
import os
import sys
import json
import time
import hmac
import hashlib
from pathlib import Path
from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd

SEED = 20261005
np.random.seed(SEED)
BASE = Path(_release_path('project_root'))
SRC = Path(_release_path('path_004'))
FILES = ["AVI_20210627.csv", "AVI_20210628_0704.csv", "AVI_0705-0803.csv"]
CHUNK = 3_000_000
TARGETS = pd.date_range("2021-07-25", "2021-08-02").strftime("%Y-%m-%d").tolist()
SPECIAL = set("学挂警领港澳使试超临")
TZ = timezone(timedelta(hours=8))


def now():
    return datetime.now(TZ).isoformat()


def source_meta():
    return [{"file_id": "AVI_SOURCE_%02d" % (i + 1), "size": (SRC / f).stat().st_size,
             "mtime_ns": (SRC / f).stat().st_mtime_ns} for i, f in enumerate(FILES)]


def shared_hashes():
    return {p: hashlib.sha256((BASE / p).read_bytes()).hexdigest() for p in
            ["01_panels/device_attributes.csv", "01_panels/device_id_map.csv", "01_panels/online_sets.csv"]}


def classify(p):
    if p in ("-", "无车牌", "") or len(p) < 7:
        return "unreadable", 0
    nev = int(len(p) == 8 and p[-1] not in SPECIAL)
    if p.startswith("浙D"):
        cat = "local_zheD"
    elif p.startswith("浙"):
        cat = "zhejiang_other"
    else:
        cat = "other_province"
    return cat, nev


def main():
    started = now()
    before = source_meta()
    shared_before = shared_hashes()
    for folder in ("01_panels/plate_day", "01_panels/plate_day_extra", "00_env", "00_env/avi_tmp"):
        (BASE / folder).mkdir(parents=True, exist_ok=True)
    log_path = BASE / "00_env/avi_read_progress.log"
    logf = log_path.open("a", encoding="utf-8")

    def log(message):
        line = now() + " " + message
        print(line, flush=True)
        logf.write(line + "\n")
        logf.flush()

    key = (_ReleasePath(_release_key_file())).read_bytes()
    if len(key) != 32:
        raise ValueError("Local key must contain 32 raw bytes")
    attrs = pd.read_csv(BASE / "01_panels/device_attributes.csv", dtype={"dev": str})
    devmap = pd.read_csv(BASE / "01_panels/device_id_map.csv", dtype=str)
    name_to_dev = dict(zip(devmap.dev_name, devmap.dev))
    stable = set(attrs.loc[attrs.in_Sstar.astype(int) == 1, "dev"])
    a100 = set(attrs.loc[attrs.in_A100.astype(int) == 1, "dev"])
    gateway = set(attrs.loc[(attrs.gateway.astype(int) == 1) & (attrs.in_A100.astype(int) == 1), "dev"])
    online = pd.read_csv(BASE / "01_panels/online_sets.csv", dtype=str)
    target_sets = [set(online.loc[online.date == d, "dev"]) for d in TARGETS]
    selectors = {}
    for raw, anon in name_to_dev.items():
        selectors[raw] = (int(anon in stable), int(anon in gateway), int(anon in a100 and anon not in gateway),
                          sum((1 << i) for i, s in enumerate(target_sets) if anon in s),
                          int("高速" in raw or "国道" in raw))
    cache = {}
    tmp = BASE / "00_env/avi_tmp"
    online_cols = ["n_o" + d[5:].replace("-", "") for d in TARGETS]
    counts = ["n", "n_stable", "n_gw", "n_stable_h11", "n_gw_a100", "n_nongw_a100",
              "n_gw_a100_h11", "n_nongw_a100_h11"] + online_cols + ["n_o0725_h11"]
    mins = ["h_min", "h_min_stable"]
    maxs = ["h_max", "h_max_stable"]
    pass_start = time.time()
    bad_times = 0
    unknown_devices = set()
    chunk_rows = 0
    for fi, filename in enumerate(FILES):
        log("BEGIN AVI_SOURCE_%02d bytes=%d" % (fi + 1, before[fi]["size"]))
        reader = pd.read_csv(SRC / filename, usecols=[0, 1, 2, 3, 4], dtype=str,
                             names=["plate", "dev", "dir", "lane", "ts"], header=0,
                             chunksize=CHUNK, encoding="utf-8-sig", keep_default_na=False, quotechar='"')
        for ci, rawdf in enumerate(reader):
            t0 = time.time()
            sp = rawdf.ts.str.strip('"').str.split(" ", n=1, expand=True)
            dates = {v: datetime.strptime(v.strip('"').strip(), "%Y/%m/%d").strftime("%Y-%m-%d")
                     for v in sp[0].unique()}
            hour = pd.to_numeric(sp[1].str.split(":", n=1).str[0] if sp.shape[1] > 1 else
                                 pd.Series(-1, index=rawdf.index), errors="coerce").fillna(-1).astype("int16")
            bad_times += int((hour < 0).sum())
            pl = rawdf.plate.str.strip('"')
            unique_plates = pl.unique()
            for p in unique_plates:
                if p not in cache:
                    cat, nev = classify(p)
                    ph = hmac.new(key, p.encode("utf-8"), hashlib.sha256).hexdigest()[:16]
                    cache[p] = (ph, cat, nev, len(p))
            df = pd.DataFrame({"date": sp[0].map(dates),
                               "ph": pl.map({p: cache[p][0] for p in unique_plates}),
                               "n": np.ones(len(rawdf), dtype=np.int8)})
            chunk_dev = rawdf.dev.unique()
            for raw in chunk_dev:
                if raw not in selectors:
                    unknown_devices.add(raw)
                    selectors[raw] = (0, 0, 0, 0, int("高速" in raw or "国道" in raw))
            local_selectors = {d: selectors[d] for d in chunk_dev}
            stable_row = rawdf.dev.map({d: s[0] for d, s in local_selectors.items()}).astype("int8")
            gw_row = rawdf.dev.map({d: s[1] for d, s in local_selectors.items()}).astype("int8")
            nongw_row = rawdf.dev.map({d: s[2] for d, s in local_selectors.items()}).astype("int8")
            mask = rawdf.dev.map({d: s[3] for d, s in local_selectors.items()}).astype("int16")
            h11 = ((hour >= 11) & (hour <= 23)).astype("int8")
            df["n_stable"] = stable_row
            df["n_gw"] = rawdf.dev.map({d: s[4] for d, s in local_selectors.items()}).astype("int8")
            df["n_stable_h11"] = stable_row * h11
            df["n_gw_a100"] = gw_row
            df["n_nongw_a100"] = nongw_row
            df["n_gw_a100_h11"] = gw_row * h11
            df["n_nongw_a100_h11"] = nongw_row * h11
            for i, col in enumerate(online_cols):
                df[col] = ((mask & (1 << i)) != 0).astype("int8")
            df["n_o0725_h11"] = df["n_o0725"] * h11
            df["h_min"] = hour.where(hour >= 0, 99)
            df["h_max"] = hour
            df["h_min_stable"] = hour.where((stable_row == 1) & (hour >= 0), 99)
            df["h_max_stable"] = hour.where(stable_row == 1, -1)
            agg = {c: "sum" for c in counts}
            agg.update({c: "min" for c in mins})
            agg.update({c: "max" for c in maxs})
            group = df.groupby(["date", "ph"], sort=False).agg(agg).reset_index()
            for d, subset in group.groupby("date", sort=False):
                (tmp / d).mkdir(exist_ok=True)
                subset.drop(columns="date").to_parquet(tmp / d / ("s%02d_c%04d.parquet" % (fi + 1, ci)), index=False)
            chunk_rows += len(rawdf)
            log("AVI_SOURCE_%02d chunk=%04d records=%d cached_anonymous=%d seconds=%.1f elapsed_min=%.1f" %
                (fi + 1, ci, len(rawdf), len(cache), time.time() - t0, (time.time() - pass_start) / 60))
            del rawdf, df, group, pl, sp
    master = pd.DataFrame(list(cache.values()), columns=["ph", "cat", "nev", "plate_len"])
    if master.ph.duplicated().any():
        raise RuntimeError("HMAC collision detected")
    master.to_parquet(BASE / "01_panels/plate_master.parquet", index=False)
    summary = []
    for d in sorted(p.name for p in tmp.iterdir() if p.is_dir()):
        parts = sorted((tmp / d).glob("*.parquet"))
        day = pd.concat([pd.read_parquet(p) for p in parts], ignore_index=True)
        agg = {c: "sum" for c in counts}
        agg.update({c: "min" for c in mins})
        agg.update({c: "max" for c in maxs})
        day = day.groupby("ph", as_index=False, sort=False).agg(agg)
        for c in mins:
            day[c] = day[c].where(day[c] < 99, -1).astype("int16")
        for c in maxs:
            day[c] = day[c].astype("int16")
        for c in counts:
            day[c] = day[c].astype("uint32")
        basic = ["ph", "n", "n_stable", "n_gw", "h_min", "h_max"]
        day[basic].to_parquet(BASE / "01_panels/plate_day" / (d + ".parquet"), index=False)
        day[[c for c in day if c not in basic or c == "ph"]].to_parquet(
            BASE / "01_panels/plate_day_extra" / (d + ".parquet"), index=False)
        summary.append({"date": d, "plates": len(day), "records": int(day.n.sum()),
                        "plates_Sstar": int((day.n_stable > 0).sum()),
                        "records_Sstar": int(day.n_stable.sum()),
                        "plates_on_stable": int((day.n_stable > 0).sum()),
                        "records_on_stable": int(day.n_stable.sum()),
                        "records_Sstar_h11": int(day.n_stable_h11.sum())})
        log("FINAL date=%s anonymous_plates=%d records=%d" % (d, len(day), int(day.n.sum())))
        for part in parts:
            part.unlink()
        (tmp / d).rmdir()
    pd.DataFrame(summary).to_csv(BASE / "01_panels/plate_day_summary.csv", index=False, encoding="utf-8-sig")
    check = pd.read_csv(BASE / "01_panels/device_hour.csv").groupby("date").n.sum()
    formal = pd.DataFrame(summary).set_index("date").records
    aligned = formal.reindex(check.index)
    daily_equal = bool(aligned.notna().all() and (aligned.values == check.values).all())
    after = source_meta()
    source_unchanged = before == after
    categories = {str(k): int(v) for k, v in master.cat.value_counts().items()}
    checks = {"daily_records_equal_device_hour": daily_equal, "source_metadata_unchanged": source_unchanged,
              "shared_definitions_unchanged": shared_before == shared_hashes(),
              "master_rows": len(master), "category_counts": categories, "nev": int(master.nev.sum()),
              "total_input_records": chunk_rows, "date_only_rows": bad_times,
              "unknown_device_count": len(unknown_devices), "dates": len(summary), "hmac_unique": True,
              "pilot_expected_master_rows": 3857792,
              "pilot_master_relative_difference": len(master) / 3857792 - 1}
    execution = {"script": "scripts/avi_panel_v1.py", "seed": SEED, "started": started, "ended": now(),
                 "seconds": time.time() - pass_start, "sources_before": before, "sources_after": after,
                 "shared_input_sha256": shared_before,
                 "checks": checks, "output_summary": summary}
    (BASE / "00_env/vehicle_avi_execution.json").write_text(json.dumps(execution, ensure_ascii=False, indent=2), encoding="utf-8")
    (BASE / "01_panels/VEHICLE_PANEL_CHECKS.md").write_text(
        "# AVI vehicle panel checks\n\n" + "\n".join("- %s: %s" % (k, v) for k, v in checks.items()) +
        "\n\nplate_day, plate_day_extra and plate_master are internal, non-public HMAC panels."
        " Exact target-day online membership is held fixed for same-weekday baselines.\n", encoding="utf-8")
    log("COMPLETE daily_equal=%s unchanged=%s anonymous_master=%d" % (daily_equal, source_unchanged, len(master)))
    logf.close()
    if not daily_equal or not source_unchanged or not checks["shared_definitions_unchanged"]:
        raise RuntimeError("AVI stage verification failed; inspect anonymous check report")


if __name__ == "__main__":
    main()
