# -*- coding: utf-8 -*-
"""Workbook-isolated, checkpointed taxi grid recovery, frozen definitions v1.

Raw filenames and GPS rows exist in memory only. A worker receives its source
path through an anonymous stdin pipe; process argv and logs contain only HMAC IDs.
Every complete workbook checkpoints aggregate grid/hour counts, and only a fully
verified 290-workbook run publishes the required panels.
"""
import sys as _release_sys; from pathlib import Path as _ReleasePath; _release_sys.path[:0] = [str(_ReleasePath(__file__).resolve().parents[2]), str(_ReleasePath(__file__).resolve().parents[0])]; from analysis._config import configured_path as _release_path, private_value as _release_private, key_file as _release_key_file
import os
import sys
import json
import time
import argparse
import subprocess
from collections import defaultdict
from pathlib import Path
from common_v1 import ROOT, SOURCE, SEED, now, pseudonym, save_csv, write_json
import numpy as np
import pandas as pd

PYTHON = _release_path('python_executable')
SCRIPT = ROOT / "scripts/taxi_grid_resume_v1.py"
SRC = SOURCE / "10_上虞数据/GPS/GPS0706-0731"
CP = ROOT / "01_panels/taxi_grid_checkpoints"
EXPECTED_WORKBOOKS = 290
WORKBOOK_TIMEOUT_SECONDS = 300
INVENTORY_TIMEOUT_SECONDS = 90
MAX_ATTEMPTS = 3
np.random.seed(SEED)


def metadata(p):
    stat = p.stat()
    return {"size": int(stat.st_size), "mtime_ns": int(stat.st_mtime_ns)}


def inventory():
    files = sorted(SRC.glob("*.xls"))
    return [{"source_id": pseudonym(p.stem), "path_in_memory": str(p), **metadata(p)} for p in files]


def worker(payload):
    import xlrd
    from pyproj import Transformer
    p = Path(payload["path_in_memory"])
    sid = payload["source_id"]
    if p.parent.resolve() != SRC.resolve() or pseudonym(p.stem) != sid:
        raise ValueError("source_alias_mismatch")
    before = metadata(p)
    expected = {"size": payload["size"], "mtime_ns": payload["mtime_ns"]}
    if before != expected:
        raise ValueError("source_metadata_changed_before_read")
    wb = xlrd.open_workbook(str(p), on_demand=True)
    grid, hourly = defaultdict(lambda: [0, 0]), defaultdict(lambda: [0, 0])
    counters = dict(sheets_seen=0, sheets_parsed=0, sheets_empty=0, rows_seen=0,
                    valid_points=0, invalid_xy=0, bad_time=0, date_mismatch=0,
                    out_of_period_points=0, excel_datemode=int(wb.datemode))
    proj = Transformer.from_crs(4326, 32651, always_xy=True)
    try:
        sheet_names = wb.sheet_names()
        for sn in sheet_names:
            counters["sheets_seen"] += 1
            sh = wb.sheet_by_name(sn)
            try:
                if sh.nrows < 3:
                    counters["sheets_empty"] += 1
                    continue
                headers = [str(x).strip() for x in sh.row_values(1)]
                cols = {name: headers.index(name) for name in ["时间", "速度", "经度", "纬度"]}
                vals = {name: sh.col_values(index, 2) for name, index in cols.items()}
                tt = pd.Series(vals["时间"])
                is_num = tt.map(lambda x: isinstance(x, (int, float)))
                stamp = pd.to_datetime(tt.where(~is_num).astype(str).str.replace("/", "-", regex=False), errors="coerce")
                if is_num.any():
                    origin = "1904-01-01" if wb.datemode == 1 else "1899-12-30"
                    stamp.loc[is_num] = pd.to_datetime(pd.to_numeric(tt[is_num]), unit="D", origin=origin, errors="coerce")
                lon, lat, speed = [pd.to_numeric(pd.Series(vals[name]), errors="coerce").to_numpy()
                                   for name in ["经度", "纬度", "速度"]]
                okxy = (lon >= 120.3) & (lon <= 121.4) & (lat >= 29.5) & (lat <= 30.5)
                date_range = (stamp >= pd.Timestamp("2021-07-06")) & (stamp < pd.Timestamp("2021-08-01"))
                timed_xy = okxy & stamp.notna().to_numpy()
                ok = timed_xy & date_range.to_numpy()
                counters["rows_seen"] += len(tt)
                counters["invalid_xy"] += int((~okxy).sum())
                counters["bad_time"] += int(stamp.isna().sum())
                counters["out_of_period_points"] += int((timed_xy & ~date_range.to_numpy()).sum())
                if len(str(sn)) == 8 and str(sn).isdigit():
                    try:
                        sd = pd.to_datetime(str(sn), format="%Y%m%d", errors="raise").strftime("%Y-%m-%d")
                        counters["date_mismatch"] += int((stamp.loc[timed_xy].dt.strftime("%Y-%m-%d") != sd).sum())
                    except (ValueError, TypeError):
                        pass
                if ok.any():
                    e, n = proj.transform(lon[ok], lat[ok])
                    moving = np.isfinite(speed[ok]) & (speed[ok] > 0)
                    frame = pd.DataFrame({"date": stamp.loc[ok].dt.strftime("%Y-%m-%d").to_numpy(),
                                          "gx": np.floor(e / 1000).astype(int), "gy": np.floor(n / 1000).astype(int),
                                          "hour": stamp.loc[ok].dt.hour.to_numpy(), "moving": moving.astype(int)})
                    for (d, x, y), v in frame.groupby(["date", "gx", "gy"]).moving.agg(["size", "sum"]).iterrows():
                        a = grid[(d, int(x), int(y))]
                        a[0] += int(v["size"])
                        a[1] += int(v["sum"])
                    for (d, h), v in frame.groupby(["date", "hour"]).moving.agg(["size", "sum"]).iterrows():
                        a = hourly[(d, int(h))]
                        a[0] += int(v["size"])
                        a[1] += int(v["sum"])
                    counters["valid_points"] += int(ok.sum())
                counters["sheets_parsed"] += 1
            finally:
                wb.unload_sheet(sn)
    finally:
        wb.release_resources()
    after = metadata(p)
    if after != before:
        raise ValueError("source_metadata_changed_after_read")
    if counters["sheets_seen"] != counters["sheets_parsed"] + counters["sheets_empty"]:
        raise ValueError("sheet_completion_mismatch")
    rows_grid = [[d, x, y, a[0], a[1]] for (d, x, y), a in sorted(grid.items())]
    rows_hour = [[d, h, a[0], a[1]] for (d, h), a in sorted(hourly.items())]
    if sum(r[3] for r in rows_grid) != counters["valid_points"] or sum(r[2] for r in rows_hour) != counters["valid_points"]:
        raise ValueError("aggregate_point_sum_mismatch")
    return {"schema": "taxi_grid_checkpoint_v1", "seed": SEED, "source_id": sid, "complete": True,
            "source_before": before, "source_after": after, "counters": counters,
            "grid": rows_grid, "hourly": rows_hour, "completed_at": now()}


def isolated(mode, payload=None, timeout=WORKBOOK_TIMEOUT_SECONDS):
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    try:
        r = subprocess.run([PYTHON, str(SCRIPT), mode], input=json.dumps(payload or {}, ensure_ascii=False).encode("utf-8"),
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=ROOT, env=env, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, {"error_type": "TimeoutExpired", "timeout_seconds": timeout}
    if r.returncode != 0:
        # Never persist exception messages or stderr: source filenames may carry plates.
        error_type = "WorkerExit"
        try:
            safe = json.loads(r.stdout.decode("utf-8"))
            error_type = str(safe.get("error_type", error_type))
        except Exception:
            pass
        return None, {"error_type": error_type, "exit_code": r.returncode, "stderr_bytes": len(r.stderr)}
    try:
        return json.loads(r.stdout.decode("utf-8")), None
    except Exception:
        return None, {"error_type": "WorkerInvalidJSON", "stdout_bytes": len(r.stdout), "stderr_bytes": len(r.stderr)}


def safe_inventory(log):
    for attempt in range(1, MAX_ATTEMPTS + 1):
        inv, failure = isolated("--inventory-worker", timeout=INVENTORY_TIMEOUT_SECONDS)
        if failure is None:
            if len(inv) != EXPECTED_WORKBOOKS or len({r["source_id"] for r in inv}) != EXPECTED_WORKBOOKS:
                raise RuntimeError("Expected exactly 290 distinct second-batch workbooks")
            return inv
        log("inventory_attempt=%d error=%s" % (attempt, failure["error_type"]))
        if attempt < MAX_ATTEMPTS:
            time.sleep(2 * attempt)
    raise RuntimeError("Source inventory failed after bounded retries")


def checkpoint_valid(record, source):
    expected = {"size": source["size"], "mtime_ns": source["mtime_ns"]}
    return (record.get("schema") == "taxi_grid_checkpoint_v1" and record.get("seed") == SEED and
            record.get("source_id") == source["source_id"] and record.get("complete") is True and
            record.get("source_before") == expected and record.get("source_after") == expected and
            record.get("counters", {}).get("sheets_seen") ==
            record.get("counters", {}).get("sheets_parsed", 0) + record.get("counters", {}).get("sheets_empty", 0))


def main():
    start, start_mono = now(), time.monotonic()
    CP.mkdir(parents=True, exist_ok=True)
    logpath = ROOT / "00_env/taxi_grid_resume_progress.log"
    logf = logpath.open("a", encoding="utf-8")
    failures, reused, completed = [], 0, 0

    def log(message):
        line = now() + " " + message
        print(line, flush=True)
        logf.write(line + "\n")
        logf.flush()

    before = safe_inventory(log)
    snapshot_before = [{k: v for k, v in r.items() if k != "path_in_memory"} for r in before]
    write_json(ROOT / "00_env/taxi_grid_resume_source_before.json", snapshot_before)
    log("BEGIN workbooks=290 checkpointed workbook isolation retries=3 timeout_seconds=300")
    try:
        for i, source in enumerate(before, 1):
            sid = source["source_id"]
            cppath = CP / (sid + ".json")
            cached = None
            if cppath.is_file():
                try:
                    cached = json.loads(cppath.read_text(encoding="utf-8"))
                except Exception:
                    pass
            if cached is not None and checkpoint_valid(cached, source):
                reused += 1
                completed += 1
                log("REUSED workbook_id=%s progress=%d/290" % (sid, completed))
                continue
            success = None
            for attempt in range(1, MAX_ATTEMPTS + 1):
                t0 = time.monotonic()
                result, failure = isolated("--workbook-worker", source)
                if failure is None and checkpoint_valid(result, source):
                    success = result
                    break
                failure = failure or {"error_type": "CheckpointVerificationFailed"}
                failure.update(workbook_id=sid, attempt=attempt, seconds=round(time.monotonic() - t0, 2))
                failures.append(failure)
                log("RETRY workbook_id=%s attempt=%d error=%s" % (sid, attempt, failure["error_type"]))
                write_json(ROOT / "00_env/taxi_grid_resume_failures.json", failures)
                if attempt < MAX_ATTEMPTS:
                    time.sleep(2 * attempt)
            if success is None:
                raise RuntimeError("A workbook remains incomplete after bounded retries; resume from complete checkpoints")
            temp = cppath.with_suffix(".json.tmp")
            write_json(temp, success)
            os.replace(temp, cppath)
            completed += 1
            log("COMPLETE workbook_id=%s progress=%d/290 sheets=%d valid_points=%d elapsed_minutes=%.1f" %
                (sid, completed, success["counters"]["sheets_seen"], success["counters"]["valid_points"],
                 (time.monotonic() - start_mono) / 60))
        after = safe_inventory(log)
        snapshot_after = [{k: v for k, v in r.items() if k != "path_in_memory"} for r in after]
        write_json(ROOT / "00_env/taxi_grid_resume_source_after.json", snapshot_after)
        if snapshot_before != snapshot_after:
            raise RuntimeError("Source workbook set or size/mtime changed across the stage")
        grid, hourly = defaultdict(lambda: [0, 0, 0]), defaultdict(lambda: [0, 0, 0])
        counters = defaultdict(int)
        for source in before:
            record = json.loads((CP / (source["source_id"] + ".json")).read_text(encoding="utf-8"))
            if not checkpoint_valid(record, source):
                raise RuntimeError("A checkpoint became invalid before aggregation")
            for name, count in record["counters"].items():
                if name != "excel_datemode":
                    counters[name] += int(count)
            for d, x, y, npnt, nmov in record["grid"]:
                a = grid[(d, int(x), int(y))]
                a[0] += int(npnt)
                a[1] += int(nmov)
                a[2] += 1  # each complete workbook contributes once to each cell/day
            for d, h, npnt, nmov in record["hourly"]:
                a = hourly[(d, int(h))]
                a[0] += int(npnt)
                a[1] += int(nmov)
                a[2] += int(nmov > 0)  # one moving vehicle per workbook/hour/day
        out = pd.DataFrame([dict(date=d, gx=x, gy=y, n_points=a[0], n_moving=a[1], n_vehicles=a[2])
                            for (d, x, y), a in sorted(grid.items())])
        hr = pd.DataFrame([dict(date=d, hour=h, taxi_points=a[0], taxi_moving_points=a[1], taxi_vehicles_moving=a[2])
                           for (d, h), a in sorted(hourly.items())])
        if out.empty or int(out.n_points.sum()) != counters["valid_points"] or int(hr.taxi_points.sum()) != counters["valid_points"]:
            raise RuntimeError("Final aggregate valid-point check failed")
        if (out.n_moving > out.n_points).any() or (hr.taxi_moving_points > hr.taxi_points).any():
            raise RuntimeError("Moving points exceed valid points")
        if not out.date.between("2021-07-06", "2021-07-31").all():
            raise RuntimeError("Out-of-period date in final panel")
        out.n_vehicles = out.n_vehicles.map(lambda n: "<10" if n < 10 else str(int(n)))
        hr.taxi_vehicles_moving = hr.taxi_vehicles_moving.map(lambda n: "<10" if n < 10 else str(int(n)))
        save_csv(out, ROOT / "01_panels/taxi_grid_day.csv")
        save_csv(hr, ROOT / "01_panels/taxi_hour_valid.csv")
        from pyproj import Transformer
        centers = out[["gx", "gy"]].drop_duplicates().sort_values(["gx", "gy"])
        inverse = Transformer.from_crs(32651, 4326, always_xy=True)
        centers["lon"], centers["lat"] = inverse.transform((centers.gx + .5) * 1000, (centers.gy + .5) * 1000)
        save_csv(centers, ROOT / "01_panels/taxi_grid_centroids.csv")
        checks = dict(counters)
        checks.update(workbooks=EXPECTED_WORKBOOKS, verified_workbooks=completed, verified_complete=True,
                      checkpoints_reused=reused, failed_attempts=len(failures), failures=failures,
                      source_metadata_unchanged=True, grid_rows=len(out), hour_rows=len(hr),
                      date_min=out.date.min(), date_max=out.date.max(), bbox=[120.3, 121.4, 29.5, 30.5],
                      grid_metres=1000, crs="EPSG:32651", seed=SEED,
                      valid_point_sums_equal=True, moving_points_no_greater_than_points=True,
                      elapsed_minutes=(time.monotonic() - start_mono) / 60,
                      checkpoint_privacy="aggregate only; HMAC filenames; no raw plates, GPS rows, drivers, terminal fields or sheet identifiers")
        write_json(ROOT / "00_env/taxi_grid_checks.json", checks)
        write_json(ROOT / "00_env/taxi_grid_resume_execution.json", dict(status="complete", script="scripts/taxi_grid_resume_v1.py",
                   command=_release_path('path_012'),
                   started=start, ended=now(), checks=checks, source_before=snapshot_before, source_after=snapshot_after,
                   outputs=["01_panels/taxi_grid_day.csv", "01_panels/taxi_grid_centroids.csv", "01_panels/taxi_hour_valid.csv"],
                   original_run_note="Original taxi_grid_v1 process ended without final panels; its in-memory partial aggregates were not reused."))
        log("COMPLETE verified=290/290 grid_rows=%d hourly_rows=%d failures_recovered=%d" % (len(out), len(hr), len(failures)))
    except Exception as exc:
        write_json(ROOT / "00_env/taxi_grid_resume_execution.json", dict(status="incomplete", script="scripts/taxi_grid_resume_v1.py",
                   command=_release_path('path_012'),
                   started=start, ended=now(), completed_workbooks=completed, reused=reused, failures=failures,
                   safe_error_type=type(exc).__name__, source_before=snapshot_before))
        log("INCOMPLETE completed=%d/290 error_type=%s" % (completed, type(exc).__name__))
        raise SystemExit(1)
    finally:
        logf.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory-worker", action="store_true")
    parser.add_argument("--workbook-worker", action="store_true")
    args = parser.parse_args()
    if args.inventory_worker or args.workbook_worker:
        try:
            payload = json.loads(sys.stdin.buffer.read().decode("utf-8"))
            result = inventory() if args.inventory_worker else worker(payload)
            sys.stdout.write(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
        except Exception as exc:
            sys.stdout.write(json.dumps({"error_type": type(exc).__name__}))
            sys.exit(1)
    else:
        main()
