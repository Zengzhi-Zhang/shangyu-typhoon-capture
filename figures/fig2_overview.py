"""Fig. 1 | Observing urban travel through Typhoon In-Fa in Shangyu.

One integrated overview (no panel letters):
  - region: the Typhoon In-Fa track and both landfalls, Zhejiang and Shangyu;
  - district: the camera network on the public 1-km lattice, cameras failed on
    26 July, GPS taxi coverage in the control week, terrain and the boundary;
  - urban core at larger scale, where the 26 July failures meet dense taxi traffic;
  - timeline, 12 July to 2 August 2021: typhoon, analysis windows, camera records,
    failed cameras and taxi GPS distance, with the camera-platform outage.

Only public layers are drawn: camera positions are the published 0.01-degree
lattice (after +/-200 m jitter) and every taxi cell holds at least 10 taxis.
All map geometry is clipped to its frame before drawing, so the vector output
holds no hidden off-frame paths.
"""
from __future__ import annotations

import io
import json
from shapely.geometry import shape
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.collections import PolyCollection  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Circle, Rectangle  # noqa: E402
from shapely.geometry import Polygon  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
try:
    from audit_panel_alignment import require_matplotlib_panel_alignment
except ImportError:
    def require_matplotlib_panel_alignment(*args, **kwargs):
        return {"verdict": "skipped_optional_QA_unavailable"}
from figstyle import COL, MM, secondary_rc, tint  # noqa: E402
from mapbase import (HALO, ROAD, SEA, TO_MERC, baiguan_marker, boundary_lines,  # noqa: E402
                     clip_polygon_parts, district_extent, draw_lines, draw_terrain, extent_for,
                     load_boundary, load_dem, load_roads, map_frame, north_arrow, points_inside,
                     scale_bar)

ROOT = HERE.parent
OUT = HERE.parent / "outputs" / "figures"
OUT.mkdir(parents=True, exist_ok=True)
SRC = HERE.parent / "source_data"
QA = OUT / "qa"
EXT = HERE.parent / "public_layers"

# ---------------------------------------------------------------- publication settings
FS_BODY, FS_TICK, FS_NOTE = 7.0, 6.5, 6.0
PUBLICATION_RC = {
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "svg.fonttype": "none",
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "font.size": 7,
}

# ---------------------------------------------------------------- layout (mm)
FIG_WIDTH_MM = 180.0
FIG_HEIGHT_MM = 150.0
BOX_INSET = (2.0, 102.0, 50.0, 46.0)      # left, bottom, width, height
BOX_LEGEND = (2.0, 46.0, 50.0, 52.0)      # drawn on the canvas
BOX_DISTRICT = (56.0, 46.0, 64.0, 102.0)
BOX_CORE = (124.0, 46.0, 54.0, 102.0)
TL_LEFT, TL_RIGHT, TL_BOTTOM = 24.0, 178.0, 8.0
LANES = [("events", 8.0), ("records", 7.5), ("failed", 6.5), ("taxi", 6.5)]  # top to bottom
LANE_GAP = 1.4
LINESPACING = 1.2

# ---------------------------------------------------------------- colours and places
TAXI_CLASSES = [(0, 30, 0.16), (30, 300, 0.32), (300, 3000, 0.52), (3000, np.inf, 0.78)]
CORE_HALF_WIDTH_M = 7800.0   # Web Mercator metres
CORE_CENTRE = (120.872, 30.062)
CITIES = {"Shanghai": (121.47, 31.23), "Hangzhou": (120.16, 30.27), "Ningbo": (121.55, 29.87)}
INSET_LON, INSET_LAT = (117.6, 125.4), (26.3, 32.55)

T0 = pd.Timestamp("2021-07-12 00:00")
DAYS = pd.date_range("2021-07-12", "2021-08-02")
OUTAGE = (pd.Timestamp("2021-07-21 23:00"), pd.Timestamp("2021-07-25 11:00"))
LANDFALLS = [(pd.Timestamp("2021-07-25 12:30"), "Zhoushan (Putuo)"),
             (pd.Timestamp("2021-07-26 09:50"), "Jiaxing (Pinghu)")]
LEVEL_I_DAY = pd.Timestamp("2021-07-24 12:00")  # day of the provincial Level I decision



def mm_box(b):
    left, bottom, width, height = b
    return [left / FIG_WIDTH_MM, bottom / FIG_HEIGHT_MM, width / FIG_WIDTH_MM, height / FIG_HEIGHT_MM]


def tday(ts) -> float:
    return (pd.Timestamp(ts) - T0) / pd.Timedelta(days=1)


# ---------------------------------------------------------------- data
def load_camera_cells():
    cells = pd.read_csv(SRC / "fig2_camera_cells.csv").rename(columns={"cameras":"n_cameras","failed_26jul":"n_failed"})
    assert cells["n_cameras"].sum()==1075 and cells["n_failed"].sum()==137
    cells["x"],cells["y"] = TO_MERC.transform(cells.cell_lon.to_numpy(),cells.cell_lat.to_numpy())
    return cells


def load_taxi_cells(boundary):
    """Coverage cells (>= 10 taxis each) whose centre lies inside the district."""
    t = pd.read_csv(SRC / "fig2_taxi_coverage_cells.csv")
    assert t["n_taxis"].min() >= 10
    x, y = TO_MERC.transform(t["cell_lon"].values, t["cell_lat"].values)
    inside = points_inside(boundary, x, y)
    print(f"taxi cells: {len(t)} with >= 10 taxis, {int(inside.sum())} inside the district")
    t = t[inside].reset_index(drop=True)
    polys = []
    for lon, lat in zip(t["cell_lon"], t["cell_lat"]):
        px, py = TO_MERC.transform(np.array([lon - .005, lon + .005, lon + .005, lon - .005]),
                                   np.array([lat - .005, lat - .005, lat + .005, lat + .005]))
        polys.append(Polygon(np.column_stack([px, py])))
    t["poly"] = polys
    return t


def load_track():
    t = pd.read_csv(SRC / "fig2_typhoon_track_cma_ibtracs.csv").rename(columns={"lat":"CMA_LAT","lon":"CMA_LON","wind_kt":"CMA_WIND","pressure_hpa":"CMA_PRES"})
    t["time_utc"]=pd.to_datetime(t["time_utc"])
    t["time_bjt"]=pd.to_datetime(t["time_bjt"])
    return t


def landfall_positions(track):
    secs = (track["time_bjt"] - T0).dt.total_seconds().to_numpy()
    assert np.all(np.diff(secs) > 0), "track times must increase for interpolation"
    out = []
    for when, place in LANDFALLS:
        s = (when - T0).total_seconds()
        out.append((float(np.interp(s, secs, track["CMA_LON"])), float(np.interp(s, secs, track["CMA_LAT"])),
                    when, place))
    return out


def load_timeline():
    return pd.read_csv(SRC / "fig2_timeline_daily.csv").rename(columns={"camera_records":"records","failed_cameras_A1":"n_failed_A1","taxi_gps_km":"taxi_km","camera_partial_day":"partial_day","camera_platform_outage":"in_outage"})


def load_land():
    layer=json.loads((EXT / "naturalearth_land.geojson").read_text(encoding="utf-8"))
    return shape(layer["features"][0]["geometry"])


def load_zhejiang():
    layer=json.loads((EXT / "osm_zhejiang_boundary.geojson").read_text(encoding="utf-8"))
    return shape(layer["features"][0]["geometry"])


def draw_taxi_cells(ax, taxi, ext, edge=None):
    polys, colours = [], []
    for poly, v in zip(taxi["poly"], taxi["fixes_per_day"]):
        alpha = next(a for lo, hi, a in TAXI_CLASSES if lo <= v < hi)
        for part in clip_polygon_parts(poly, ext):
            polys.append(np.asarray(part.exterior.coords))
            colours.append(tint(COL["teal"], alpha))
    ax.add_collection(PolyCollection(polys, facecolors=colours, edgecolors=edge or "none",
                                     linewidths=0.25 if edge else 0, zorder=2))


def draw_cameras(ax, cells, r1_mm, frame, ext, uniform=False):
    """Camera cells: circle area proportional to the number of cameras (or uniform dots)."""
    m_per_mm = (ext[1] - ext[0]) / frame[2]
    margin = 2.5 * m_per_mm
    keep = cells[cells["x"].between(ext[0] + margin, ext[1] - margin)
                 & cells["y"].between(ext[2] + margin, ext[3] - margin)]
    order = keep.sort_values("n_cameras", ascending=False)
    size = (lambda n: r1_mm) if uniform else (lambda n: r1_mm * math.sqrt(n))
    for _, c in order.iterrows():
        ax.add_patch(Circle((c["x"], c["y"]), size(c["n_cameras"]) * m_per_mm, facecolor="white",
                            edgecolor=COL["blue"], lw=0.45, zorder=5))
    for _, c in order[order["n_failed"] > 0].iterrows():
        r = (r1_mm + 0.05) if uniform else size(c["n_failed"])
        ax.add_patch(Circle((c["x"], c["y"]), r * m_per_mm, facecolor=COL["red"], edgecolor="none",
                            zorder=6))
    return len(keep)


# ---------------------------------------------------------------- map helpers
def map_title(ax, text):
    ax.text(0.97, 0.985, text, transform=ax.transAxes, ha="right", va="top", fontsize=FS_BODY,
            zorder=12, path_effects=HALO)


# ---------------------------------------------------------------- figure parts
def draw_inset(ax, land, zhejiang, boundary_ll, track, landfalls):
    ext = (INSET_LON[0], INSET_LON[1], INSET_LAT[0], INSET_LAT[1])
    ax.set_facecolor(SEA)
    map_frame(ax, ext)
    land_parts = clip_polygon_parts(land, ext)
    ax.add_collection(PolyCollection([np.asarray(p.exterior.coords) for p in land_parts], facecolors="white",
                                     edgecolors=COL["bluegrey"], linewidths=0.3, zorder=1))
    holes = [np.asarray(h.coords) for p in land_parts for h in p.interiors]
    if holes:
        ax.add_collection(PolyCollection(holes, facecolors=SEA, edgecolors=COL["bluegrey"], linewidths=0.3,
                                         zorder=1))
    zj = clip_polygon_parts(zhejiang.intersection(land), ext)
    ax.add_collection(PolyCollection([np.asarray(p.exterior.coords) for p in zj], facecolors=COL["panel"],
                                     edgecolors=COL["ink"], linewidths=0.35, zorder=2))
    ax.add_collection(PolyCollection([np.asarray(p.exterior.coords) for p in clip_polygon_parts(boundary_ll, ext)],
                                     facecolors=COL["ink"], edgecolors="none", zorder=4))
    tr = track[(track["time_bjt"] >= "2021-07-22") & (track["time_bjt"] <= "2021-07-29")]
    draw_lines(ax, [tr[["CMA_LON", "CMA_LAT"]].to_numpy()], ext, COL["orange"], 1.3, 5)
    pad = 0.15
    daily = tr[tr["time_utc"].dt.hour.eq(0) & tr["time_utc"].dt.minute.eq(0)
               & tr["CMA_LON"].between(ext[0] + pad, ext[1] - pad) & tr["CMA_LAT"].between(ext[2] + pad, ext[3] - pad)]
    ax.plot(daily["CMA_LON"], daily["CMA_LAT"], "o", ms=2.6, mfc="white", mec=COL["orange"], mew=0.8, zorder=6)
    for k, (_, r) in enumerate(daily.iterrows()):
        label = f"{r['time_bjt'].day} Jul" if k == 0 else f"{r['time_bjt'].day}"
        near_edge = r["CMA_LON"] > ext[1] - 1.2
        ax.text(r["CMA_LON"] + (-0.22 if near_edge else 0.22), r["CMA_LAT"] + 0.05, label, fontsize=FS_NOTE,
                ha="right" if near_edge else "left", va="bottom", zorder=7, path_effects=HALO)
    for lon, lat, _, _ in landfalls:
        ax.plot([lon], [lat], marker="*", ms=6.5, mfc=COL["orange"], mec=COL["ink"], mew=0.35, zorder=8,
                ls="none")
    city_labels = {"Shanghai": (0.15, 0.08, "left", "bottom"), "Hangzhou": (-0.15, 0.08, "right", "bottom"),
                   "Ningbo": (0.0, -0.14, "center", "top")}
    for name, (lon, lat) in CITIES.items():
        dx, dy, ha, va = city_labels[name]
        ax.plot([lon], [lat], "o", ms=1.8, color=COL["ink"], zorder=7)
        ax.text(lon + dx, lat + dy, name, fontsize=FS_NOTE, ha=ha, va=va, zorder=7, path_effects=HALO)
    c = boundary_ll.centroid
    ax.text(c.x - 0.30, c.y - 0.25, "Shangyu", fontsize=FS_NOTE, ha="right", va="top", zorder=7,
            path_effects=HALO)
    ax.text(123.8, 27.5, "East China Sea", ha="right", va="center", fontsize=FS_NOTE, zorder=7)
    ax.text(119.2, 28.45, "Zhejiang", ha="center", va="center", fontsize=FS_NOTE, zorder=7)
    ax.text(124.75, 29.05, "Typhoon\nIn-Fa", ha="center", va="center", fontsize=FS_NOTE, zorder=7,
            linespacing=LINESPACING)
    deg = 100 / (111.32 * math.cos(math.radians(27.2)))
    ax.add_line(Line2D([118.0, 118.0 + deg], [26.75, 26.75], color=COL["ink"], lw=1.0,
                       solid_capstyle="butt", zorder=9))
    ax.text(118.0 + deg / 2, 26.85, "100 km", fontsize=FS_NOTE, ha="center", va="bottom", zorder=9)


def core_extent():
    cx, cy = TO_MERC.transform(*CORE_CENTRE)
    return extent_for(cx, cy, CORE_HALF_WIDTH_M, BOX_CORE)


def draw_district(ax, dem, dem_ext, boundary, cells, taxi, roads, ext):
    draw_terrain(ax, dem, dem_ext, boundary, ext, step=2)
    map_frame(ax, ext)
    draw_taxi_cells(ax, taxi, ext)
    draw_lines(ax, roads, ext, ROAD, 0.35, 3)
    draw_lines(ax, boundary_lines(boundary), ext, COL["ink"], 0.7, 8)
    draw_cameras(ax, cells, 0.42, BOX_DISTRICT, ext, uniform=True)
    baiguan_marker(ax, BOX_DISTRICT, ext, FS_NOTE)
    scale_bar(ax, ext, 5, 29.9, FS_NOTE)
    north_arrow(ax, FS_NOTE, x_frac=0.93, y_frac=0.84)  # clear of the zoom leader lines
    ax.text(0.015, 0.985, "Hangzhou\nBay", transform=ax.transAxes, ha="left", va="top", fontsize=FS_NOTE,
            linespacing=LINESPACING, zorder=12, path_effects=HALO)
    map_title(ax, "Shangyu District")


def draw_core(ax, dem, dem_ext, boundary, cells, taxi, roads, ext):
    draw_terrain(ax, dem, dem_ext, boundary, ext, step=1)
    map_frame(ax, ext)
    draw_taxi_cells(ax, taxi, ext, edge="white")
    draw_lines(ax, roads, ext, ROAD, 0.35, 3)
    draw_lines(ax, boundary_lines(boundary), ext, COL["ink"], 0.9, 8)
    draw_cameras(ax, cells, 0.30, BOX_CORE, ext)
    baiguan_marker(ax, BOX_CORE, ext, FS_NOTE, label=(1.6, -2.4))
    map_title(ax, "Urban core")
    scale_bar(ax, ext, 2, 30.06, FS_NOTE)
    north_arrow(ax, FS_NOTE)


def zoom_connectors(canvas, district_ext, core_ext):
    """Box on the district map and two leader lines to the core frame (mm on the canvas)."""
    def to_mm(x, y):
        left, bottom, width, height = BOX_DISTRICT
        return (left + (x - district_ext[0]) / (district_ext[1] - district_ext[0]) * width,
                bottom + (y - district_ext[2]) / (district_ext[3] - district_ext[2]) * height)

    (bl_x, bl_y), (tr_x, tr_y) = to_mm(core_ext[0], core_ext[2]), to_mm(core_ext[1], core_ext[3])
    canvas.add_patch(Rectangle((bl_x, bl_y), tr_x - bl_x, tr_y - bl_y, fill=False, lw=0.6,
                               edgecolor=COL["ink"], zorder=20))
    left, bottom, width, height = BOX_CORE
    for (sx, sy), (ex, ey) in (((tr_x, tr_y), (left, bottom + height)), ((tr_x, bl_y), (left, bottom))):
        canvas.add_line(Line2D([sx, ex], [sy, ey], color=COL["ink"], lw=0.4, alpha=0.7, zorder=20))


def draw_legend(canvas):
    left, bottom, width, height = BOX_LEGEND
    x = left + 1.0
    y = bottom + height - 3.0
    # The concept lines ("Camera records = traffic × capture" and its two-line gloss) moved to the
    # concept figure, manuscript Fig. 1, on 2026-11-08. The symbol rows start lower so that the
    # legend sits midway between the location inset and the timeline.
    y -= 2.8
    sx = x + 2.2  # symbol column centre
    tx = x + 5.2  # text column

    def row(text):
        canvas.text(tx, y, text, fontsize=FS_NOTE, ha="left", va="center")

    canvas.text(sx - 1.3, y, "Licence-plate cameras per 1-km cell", fontsize=FS_NOTE, ha="left", va="center")
    y -= 3.7
    for n, cx in ((1, sx), (10, sx + 3.2), (40, sx + 8.0)):
        canvas.add_patch(Circle((cx, y), 0.30 * math.sqrt(n), facecolor="white", edgecolor=COL["blue"],
                                lw=0.45))
    canvas.text(sx + 11.0, y, "1, 10, 40 cameras (urban core)", fontsize=FS_NOTE, ha="left", va="center")
    y -= 3.6
    canvas.add_patch(Circle((sx, y), 0.42, facecolor="white", edgecolor=COL["blue"], lw=0.45))
    row("One dot per cell (district map)")
    y -= 3.4
    canvas.add_patch(Circle((sx, y), 0.6, facecolor=COL["red"], edgecolor="none"))
    row("Failed on 26 Jul (in the urban core, red")
    y -= 2.7
    row("area gives the number on the same scale)")
    y -= 3.6
    for k, (_, _, a) in enumerate(TAXI_CLASSES):
        canvas.add_patch(Rectangle((sx - 1.3 + k * 2.5, y - 0.95), 2.3, 1.9, facecolor=tint(COL["teal"], a),
                                   edgecolor="none"))
    # The four classes are the frozen TAXI_CLASSES bins, written out so the shading reads as numbers.
    edges = [f"{int(lo):,}" for lo, _, _ in TAXI_CLASSES[1:]]
    canvas.text(sx + 9.6, y, "Taxi GPS fixes per cell per day:", fontsize=FS_NOTE, ha="left", va="center")
    y -= 2.7
    canvas.text(sx + 9.6, y, f"<{edges[0]}, {edges[0]}–{edges[1]}, {edges[1]}–{edges[2]}, ≥{edges[2]}",
                fontsize=FS_NOTE, ha="left", va="center")
    y -= 2.7
    canvas.text(sx + 9.6, y, "12–19 Jul (cells with ≥10 taxis)", fontsize=FS_NOTE, ha="left", va="center")
    y -= 3.7
    canvas.add_line(Line2D([sx - 1.6, sx + 1.4], [y, y], color=COL["orange"], lw=1.3))
    canvas.add_line(Line2D([sx + 3.0], [y], marker="*", ms=6.0, mfc=COL["orange"], mec=COL["ink"],
                           mew=0.35, ls="none"))
    canvas.text(tx + 2.4, y, "Typhoon track (CMA), landfalls", fontsize=FS_NOTE, ha="left", va="center")
    y -= 3.4
    canvas.add_line(Line2D([sx - 1.6, sx + 1.6], [y, y], color=COL["ink"], lw=0.7))
    row("District boundary")
    y -= 3.4
    canvas.add_line(Line2D([sx - 1.6, sx + 1.6], [y, y], color=ROAD, lw=0.6))
    row("Motorways and primary roads")
    y -= 3.4
    canvas.add_line(Line2D([sx], [y], marker="*", ms=5.5, mfc=COL["ink"], mec="white", mew=0.4,
                           ls="none"))
    row("Baiguan, the district centre")


def draw_timeline(fig, t):
    total = sum(h for _, h in LANES) + LANE_GAP * (len(LANES) - 1)
    axes = {}
    y = TL_BOTTOM + total
    for name, h in LANES:
        y -= h
        ax = fig.add_axes(mm_box((TL_LEFT, y, TL_RIGHT - TL_LEFT, h)))
        ax.set_gid(f"timeline-{name}")
        ax.set_xlim(0, len(DAYS))
        ax.set_facecolor("none")
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        axes[name] = ax
        y -= LANE_GAP
    x = np.arange(len(DAYS)) + 0.5
    xo0, xo1 = tday(OUTAGE[0]), tday(OUTAGE[1])

    ev = axes["events"]
    ev.set_ylim(0, 1)
    ev.axis("off")
    ev.add_patch(Rectangle((0, 0.10), 8, 0.2, facecolor=COL["bluegrey"], edgecolor="none"))
    ev.text(0.1, 0.40, "Capture control, 12–19 Jul", fontsize=FS_NOTE, ha="left", va="bottom")
    ev.add_patch(Rectangle((xo1, 0.10), len(DAYS) - xo1, 0.2, facecolor=COL["blue"], edgecolor="none"))
    ev.text(len(DAYS) - 0.1, 0.40, "Event window, 25 Jul–2 Aug", fontsize=FS_NOTE, ha="right", va="bottom")
    xl = tday(LEVEL_I_DAY)
    ev.plot([xl], [0.80], marker="v", ms=3.6, mfc="white", mec=COL["orange"], mew=0.9, ls="none")
    ev.text(xl - 0.45, 0.80, "Zhejiang Level I response", fontsize=FS_NOTE, ha="right", va="center")
    for when, _ in LANDFALLS:
        ev.plot([tday(when)], [0.80], marker="*", ms=6.0, mfc=COL["orange"], mec=COL["ink"], mew=0.35,
                ls="none")
    ev.text(tday(LANDFALLS[1][0]) + 0.6, 0.80, "Landfalls", fontsize=FS_NOTE, ha="left", va="center")

    p = t["partial_day"].to_numpy()
    rec = axes["records"]
    vals = t["records"].to_numpy() / 1e6
    rec.bar(x, vals, width=0.68, color=COL["blue"], lw=0)
    rec.bar(x[p], vals[p], width=0.68, facecolor="white", edgecolor=COL["blue"], lw=0.7)
    rec.set_ylim(0, 10.5)
    rec.set_yticks([0, 10])
    rec.set_yticklabels(["", "10"])

    fl = axes["failed"]
    fv = t["n_failed_A1"].to_numpy().astype(float)
    fv[t["in_outage"].to_numpy()] = np.nan
    fl.bar(x, fv, width=0.68, color=COL["red"], lw=0)
    fl.bar(x[p], fv[p], width=0.68, facecolor="white", edgecolor=COL["red"], lw=0.7)
    fl.set_ylim(0, 175)
    fl.set_yticks([0, 150])
    fl.set_yticklabels(["", "150"])

    tx = axes["taxi"]
    tx.bar(x, t["taxi_km"].to_numpy() / 1e3, width=0.68, color=COL["teal"], lw=0)
    tx.set_ylim(0, 105)
    tx.set_yticks([0, 100])
    tx.text(len(DAYS) - 1.0, 52, "Probe ends\n31 Jul", fontsize=FS_NOTE, ha="center", va="center",
            linespacing=LINESPACING)

    for name in ("records", "failed"):
        ax = axes[name]
        ax.add_patch(Rectangle((xo0, 0), xo1 - xo0, ax.get_ylim()[1], facecolor=tint(COL["bluegrey"], 0.45),
                               edgecolor="none", zorder=0))
    rec.text((xo0 + xo1) / 2, 5.4, "Camera platform\noutage", fontsize=FS_NOTE, ha="center", va="center",
             linespacing=LINESPACING, zorder=3, path_effects=HALO)
    for name in ("records", "failed", "taxi"):
        ax = axes[name]
        ax.spines["left"].set_position(("outward", 1.5))
        ax.spines["bottom"].set_visible(name == "taxi")
        ax.tick_params(axis="y", labelsize=FS_NOTE, length=2.0, pad=1.0)
        if name != "taxi":
            ax.set_xticks([])
    tx.set_xticks(x)
    tx.set_xticklabels([str(d.day) for d in DAYS], fontsize=FS_NOTE)
    tx.tick_params(axis="x", length=2.0, pad=1.0)
    tx.text(10.0, -0.62, "July 2021", transform=tx.get_xaxis_transform(), fontsize=FS_NOTE, ha="center",
            va="top")
    tx.text(21.0, -0.62, "Aug", transform=tx.get_xaxis_transform(), fontsize=FS_NOTE, ha="center", va="top")
    return axes


def place_lane_titles(canvas, axes):
    titles = {"events": "Typhoon and\nanalysis windows", "records": "Camera records\n(millions)",
              "failed": "Failed\ncameras", "taxi": "Taxi distance\n(1,000 km)"}
    for name, ax in axes.items():
        bb = ax.get_position()
        canvas.text(2.0, (bb.y0 + bb.y1) / 2 * FIG_HEIGHT_MM, titles[name], fontsize=FS_NOTE, ha="left",
                    va="center", linespacing=LINESPACING)


# ---------------------------------------------------------------- source data
def write_source_data(*args, **kwargs):
    pass


# ---------------------------------------------------------------- main
def main():
    mpl.rcParams.update(PUBLICATION_RC)
    mpl.rcParams.update(secondary_rc(FS_BODY, FS_TICK))

    dem, dem_ext = load_dem()
    boundary = load_boundary()
    boundary_ll = gpd.GeoSeries([boundary], crs=3857).to_crs(4326).iloc[0]
    cells = load_camera_cells()
    taxi = load_taxi_cells(boundary)
    roads = load_roads()
    track = load_track()
    landfalls = landfall_positions(track)
    timeline = load_timeline()
    land = load_land()
    zhejiang = load_zhejiang()
    write_source_data(cells, taxi, track, landfalls, timeline)

    fig = plt.figure(figsize=(FIG_WIDTH_MM * MM, FIG_HEIGHT_MM * MM))
    canvas = fig.add_axes([0, 0, 1, 1], zorder=10)
    canvas.set_xlim(0, FIG_WIDTH_MM)
    canvas.set_ylim(0, FIG_HEIGHT_MM)
    canvas.axis("off")
    canvas.set_gid("canvas")
    ax_inset = fig.add_axes(mm_box(BOX_INSET))
    ax_inset.set_gid("region")
    ax_district = fig.add_axes(mm_box(BOX_DISTRICT))
    ax_district.set_gid("district")
    ax_core = fig.add_axes(mm_box(BOX_CORE))
    ax_core.set_gid("core")

    ext_district, ext_core = district_extent(boundary, BOX_DISTRICT), core_extent()
    draw_inset(ax_inset, land, zhejiang, boundary_ll, track, landfalls)
    draw_district(ax_district, dem, dem_ext, boundary, cells, taxi, roads, ext_district)
    draw_core(ax_core, dem, dem_ext, boundary, cells, taxi, roads, ext_core)
    zoom_connectors(canvas, ext_district, ext_core)
    draw_legend(canvas)
    lanes = draw_timeline(fig, timeline)
    place_lane_titles(canvas, lanes)

    QA.mkdir(exist_ok=True)
    report = require_matplotlib_panel_alignment(
        fig, json_out=QA / "fig2_overview.alignment.json", overlay_svg=QA / "fig2_overview.alignment.svg",
        tolerance_pt=1.5, gutter_tolerance_pt=1.5, require_panel_labels=False, strict=True,
        axes=[ax_district, ax_core, *lanes.values()],
        row_groups=[{"id": "maps", "panels": ["district", "core"]}],
        column_groups=[{"id": "timeline", "panels": [f"timeline-{n}" for n, _ in LANES]}])

    fig.savefig(OUT / "fig2_overview.svg")
    fig.savefig(OUT / "fig2_overview.pdf")
    # Uncompressed TIFF: the local libtiff build aborts on LZW compression.
    fig.savefig(OUT / "fig2_overview.tiff", dpi=600)
    fig.savefig(OUT / "fig2_overview.png", dpi=300)
    plt.close(fig)
    print("alignment:", report.get("verdict"), "| size mm:", FIG_WIDTH_MM, FIG_HEIGHT_MM)


if __name__ == "__main__":
    main()
