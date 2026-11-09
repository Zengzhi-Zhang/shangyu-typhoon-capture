"""Taxi GPS coverage on the public 0.01-degree lattice, 12-19 July 2021 (Fig. 1 layer).

Reads the pseudonymised per-vehicle GPS cache (one parquet per vehicle) and writes
cell counts only. Cells with fewer than 10 distinct taxis are dropped, so the output
holds no vehicle identifiers and no cell that could describe a small group of taxis.
"""
from __future__ import annotations

import glob
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SRC = HERE.parent / "source_data"
GPS = ROOT / "formal_v6/01_internal/taxi_gps_points"

CONTROL = ("2021-07-12", "2021-07-19")
BBOX = (120.70, 121.13, 29.70, 30.30)  # lon_min, lon_max, lat_min, lat_max
MIN_TAXIS = 10


def main() -> None:
    files = sorted(glob.glob(str(GPS / "*.parquet")))
    assert len(files) == 290, len(files)
    parts = []
    for k, f in enumerate(files):
        d = pd.read_parquet(f, columns=["date", "lon", "lat", "valid_xy", "moving"])
        d = d[(d["date"] >= CONTROL[0]) & (d["date"] <= CONTROL[1]) & d["valid_xy"] & d["moving"]]
        d = d[d["lon"].between(BBOX[0], BBOX[1]) & d["lat"].between(BBOX[2], BBOX[3])]
        if d.empty:
            continue
        cells = pd.DataFrame({"cell_lon": d["lon"].round(2), "cell_lat": d["lat"].round(2)})
        g = cells.value_counts().rename("n_fixes").reset_index()
        g["vehicle"] = k  # running index only; pseudonyms are never written out
        parts.append(g)
    allc = pd.concat(parts, ignore_index=True)
    out = (allc.groupby(["cell_lon", "cell_lat"])
           .agg(n_taxis=("vehicle", "nunique"), n_fixes=("n_fixes", "sum")).reset_index())
    n_cells_all = len(out)
    out = out[out["n_taxis"] >= MIN_TAXIS].copy()
    out["fixes_per_day"] = (out["n_fixes"] / 8.0).round(1)
    out = out[["cell_lon", "cell_lat", "n_taxis", "fixes_per_day"]].sort_values(["cell_lat", "cell_lon"])
    out["cell_lon"] = out["cell_lon"].map(lambda v: f"{v:.2f}")
    out["cell_lat"] = out["cell_lat"].map(lambda v: f"{v:.2f}")
    SRC.mkdir(exist_ok=True)
    out.to_csv(SRC / "fig1_taxi_coverage_cells.csv", index=False)
    print(f"vehicles with control-period fixes: {allc['vehicle'].nunique()} | cells: {n_cells_all} "
          f"| cells kept (>= {MIN_TAXIS} taxis): {len(out)}")


if __name__ == "__main__":
    main()
