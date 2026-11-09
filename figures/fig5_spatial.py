"""Fig. 4 | The spatial reading of recovery depends on how failed cameras are treated.

a  Health-screened cameras on 26 July: recovery ratio by public 1-km cell, failed cameras
b  Recovery by distance ring from Baiguan, 26 July: health-screened set and fixed stable set
c  Share failed within each distance ring on 26 July, by number of cameras and by baseline flow
d  Distance coefficient by sample and day (HC1 95% intervals)

All rows of the frozen tables for these samples and days are plotted; no rows are dropped.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.collections import LineCollection  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Circle, Ellipse, Patch  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
try:
    from audit_panel_alignment import require_matplotlib_panel_alignment
except ImportError:
    def require_matplotlib_panel_alignment(*args, **kwargs):
        return {"verdict": "skipped_optional_QA_unavailable"}
from figstyle import COL, MM, add_panel_label, gridspec_mm, outward_spines, secondary_rc, tint  # noqa: E402
from mapbase import (BAIGUAN, HALO, TO_MERC, baiguan_marker, boundary_lines, clip_lines,  # noqa: E402
                     district_extent, draw_lines, draw_terrain, load_boundary, load_dem, map_frame,
                     merc_per_km, north_arrow, scale_bar)

ROOT = HERE.parent
OUT = HERE.parent / "outputs" / "figures"
OUT.mkdir(parents=True, exist_ok=True)
SRC = HERE.parent / "source_data"
QA = OUT / "qa"
SRC.mkdir(exist_ok=True)

# ---------------------------------------------------------------- publication settings
FS_BODY, FS_TICK, FS_NOTE, FS_LETTER = 7.0, 6.5, 6.0, 8.0
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
LEFT, RIGHT, TOP, BOTTOM = 11.0, 3.0, 8.0, 11.0
COL_GUT, ROW_GUT = 20.0, 12.0
PANEL_W = (FIG_WIDTH_MM - LEFT - RIGHT - COL_GUT) / 2
H_B, H_C, H_D = 36.0, 18.0, 39.0
H_MAP = H_B + H_C + H_D + 2 * ROW_GUT
FIG_HEIGHT_MM = TOP + H_MAP + BOTTOM
MAP_FRAME = (LEFT, BOTTOM, PANEL_W, H_MAP)
LINESPACING = 1.2

DATE = "2021-07-26"
RINGS = ["0-2", "2-4", "4-7", "7-12", "12+"]
RING_LABELS = ["0–2", "2–4", "4–7", "7–12", "≥12"]
RING_KM = [2, 4, 7, 12]
RATIO_CLASSES = [(0.0, 0.4, 0.16, "<0.4"), (0.4, 0.5, 0.34, "0.4–0.5"), (0.5, 0.6, 0.52, "0.5–0.6"),
                 (0.6, 0.7, 0.74, "0.6–0.7"), (0.7, np.inf, 1.0, "≥0.7")]
SIZE_REF = 160000.0  # baseline records per day at which the radius gain reaches R_GAIN
R_MIN, R_GAIN = 0.35, 1.45  # mm

SAMPLES = [  # key, label, colour, marker, dates available
    ("health", "Health-screened", "blue", "o"),
    ("health_pc", "Health-screened + some lanes silent", "purple", "o"),
    ("online", "Online set", "teal", "s"),
    ("stable", "Fixed stable set", "orange", "^"),
    ("floor", "All cameras, failed set to floor", "red", "o"),
]
DAYS = ["2021-07-26", "2021-07-27", "2021-07-28"]
DAY_FILL = {"2021-07-26": 1.0, "2021-07-27": 0.35, "2021-07-28": 0.0}
DAY_DY = {"2021-07-26": 0.2, "2021-07-27": 0.0, "2021-07-28": -0.2}
ROW_STEP = 1.2


# ---------------------------------------------------------------- data
def load_cells():
    t = pd.read_csv(SRC / "fig5a_health_cells.csv").sort_values(["cell_lon","cell_lat"],kind="mergesort")
    cells = t[t.health_cameras.gt(0)].copy().rename(columns={"cell_lon":"plot_lon","cell_lat":"plot_lat","baseline_records_per_day":"baseline","ratio_26jul":"ratio"})
    failed = t[t.failed_cameras.gt(0)][["cell_lon","cell_lat","failed_cameras"]].copy().rename(columns={"cell_lon":"plot_lon","cell_lat":"plot_lat"})
    for frame in (cells,failed):
        frame["x"],frame["y"] = TO_MERC.transform(frame.plot_lon.to_numpy(),frame.plot_lat.to_numpy())
    coverage = pd.read_csv(SRC / "ed5a_coverage_26jul.csv").iloc[0]
    note = {"n_unmapped":int(coverage.n_missing),"share_unmapped":coverage.flow_missing}
    assert cells.health_cameras.sum()==882 and failed.failed_cameras.sum()==137
    return cells, failed, note


def load_rings():
    return pd.read_csv(SRC / "fig5b_ring_recovery.csv")


def load_failed_by_ring():
    return pd.read_csv(SRC / "fig5c_failed_by_ring.csv").set_index("ring").reindex(RINGS)


def load_coefficients():
    return pd.read_csv(SRC / "fig5d_distance_coefficients.csv")


# ---------------------------------------------------------------- panel a
def radius_mm(baseline):
    return R_MIN + R_GAIN * np.sqrt(np.asarray(baseline, float) / SIZE_REF)


def ratio_colour(r):
    return tint(COL["blue"], next(a for lo, hi, a, _ in RATIO_CLASSES if lo <= r < hi))


def panel_a(ax, dem, dem_ext, boundary, cells, failed, note):
    ext = district_extent(boundary, MAP_FRAME)
    draw_terrain(ax, dem, dem_ext, boundary, ext, step=2)
    map_frame(ax, ext)
    draw_lines(ax, boundary_lines(boundary), ext, COL["ink"], 0.7, 8)
    m_per_mm = (ext[1] - ext[0]) / MAP_FRAME[2]
    bx, by = TO_MERC.transform(*BAIGUAN)
    t = np.linspace(0, 2 * np.pi, 361)
    circles = [np.column_stack([bx + km * merc_per_km(BAIGUAN[1]) * np.cos(t),
                                by + km * merc_per_km(BAIGUAN[1]) * np.sin(t)]) for km in RING_KM]
    ax.add_collection(LineCollection(clip_lines(circles, ext), colors=COL["ink"], linewidths=0.45,
                                     linestyles=[(0, (2.2, 1.6))], zorder=4))
    r12, ang = RING_KM[-1] * merc_per_km(BAIGUAN[1]), math.radians(-64)
    ax.text(bx + r12 * math.cos(ang), by + r12 * math.sin(ang), f"{RING_KM[-1]} km", fontsize=FS_NOTE,
            ha="center", va="center", zorder=11, path_effects=HALO)
    inside = cells[cells["x"].between(ext[0], ext[1]) & cells["y"].between(ext[2], ext[3])]
    for _, c in inside.sort_values("baseline", ascending=False).iterrows():
        ax.add_patch(Circle((c["x"], c["y"]), radius_mm(c["baseline"]) * m_per_mm,
                            facecolor=ratio_colour(c["ratio"]), edgecolor="white", lw=0.3, zorder=5))
    ax.plot(failed["x"], failed["y"], "x", ms=3.0, mew=0.8, color=COL["red"], zorder=7)
    baiguan_marker(ax, MAP_FRAME, ext, FS_NOTE)
    scale_bar(ax, ext, 5, 29.9, FS_NOTE)
    north_arrow(ax, FS_NOTE)
    legend_a(ax)
    return ext


def key_dot(ax, x, y, r_mm, **kw):
    """A round symbol of radius r_mm at axes-fraction (x, y) on the non-square map frame."""
    ax.add_patch(Ellipse((x, y), 2 * r_mm / MAP_FRAME[2], 2 * r_mm / MAP_FRAME[3], transform=ax.transAxes,
                         zorder=12, **kw))


def legend_a(ax):
    """Key in the open land north-east of the district (axes fraction)."""
    x0, y = 0.645, 0.955
    ax.text(x0, y, "Recovery ratio", transform=ax.transAxes, fontsize=FS_NOTE, ha="left", va="center",
            zorder=12)
    for lo, hi, a, label in RATIO_CLASSES:
        y -= 0.027
        key_dot(ax, x0 + 0.02, y, 0.75, facecolor=tint(COL["blue"], a), edgecolor="white", lw=0.3)
        ax.text(x0 + 0.05, y, label, transform=ax.transAxes, fontsize=FS_NOTE, ha="left", va="center",
                zorder=12)
    y -= 0.042
    ax.text(x0, y, "Baseline records/day", transform=ax.transAxes, fontsize=FS_NOTE, ha="left",
            va="center", zorder=12)
    y -= 0.034
    w_mm = MAP_FRAME[2]
    xs = x0 + 0.02
    for b, label in ((1000, "1k"), (10000, "10k"), (100000, "100k")):
        r = float(radius_mm(b))
        key_dot(ax, xs, y, r, facecolor="white", edgecolor=COL["blue"], lw=0.45)
        ax.text(xs + r / w_mm + 0.012, y, label, transform=ax.transAxes, fontsize=FS_NOTE, ha="left",
                va="center", zorder=12)
        xs += (2 * r + 6.2) / w_mm
    y -= 0.042
    ax.plot([x0 + 0.02], [y], "x", ms=3.0, mew=0.8, color=COL["red"], transform=ax.transAxes, zorder=12)
    ax.text(x0 + 0.05, y, "Failed, 26 Jul", transform=ax.transAxes, fontsize=FS_NOTE, ha="left", va="center",
            zorder=12)
    y -= 0.03
    ax.add_line(Line2D([x0, x0 + 0.04], [y, y], transform=ax.transAxes, color=COL["ink"], lw=0.45,
                       ls=(0, (2.2, 1.6)), zorder=12))
    ax.text(x0 + 0.05, y, "2, 4, 7, 12 km rings", transform=ax.transAxes, fontsize=FS_NOTE, ha="left",
            va="center", zorder=12)


# ---------------------------------------------------------------- panels b to d
def panel_b(ax, rings, note):
    x = np.arange(len(RINGS))
    styles = {"health": (COL["blue"], "o", (0, ()), 1.6, -0.07, "Health-screened"),
              "stable": (COL["orange"], "^", (0, (1.2, 1.2)), 1.1, 0.07, "Fixed stable set")}
    handles = []
    for key, (col, mk, dash, lw, dx, label) in styles.items():
        r = rings[rings["sample"] == key].set_index("ring").reindex(RINGS)
        ax.plot(x + dx, r["R"], color=col, lw=lw, ls=dash, zorder=3)
        ax.vlines(x + dx, r["ci_lo"], r["ci_hi"], color=col, lw=0.8, zorder=2)
        ax.plot(x + dx, r["R"], mk, ms=3.8, color=col, mec="white", mew=0.4, ls="none", zorder=4)
        handles.append(Line2D([], [], color=col, lw=lw, ls=dash, marker=mk, ms=3.8, mec="white", mew=0.4,
                              label=label))
    ax.legend(handles=handles, loc="upper right", fontsize=FS_NOTE, handlelength=2.4)
    ax.text(-0.42, 0.408, f"Not in any ring: {note['n_unmapped']} health-screened cameras without\n"
            f"coordinates ({100 * note['share_unmapped']:.1f}% of their baseline flow)", fontsize=FS_NOTE,
            ha="left", va="bottom", linespacing=LINESPACING)
    ax.set_xlim(-0.5, len(RINGS) - 0.5)
    ax.set_ylim(0.40, 0.76)
    ax.set_yticks([0.4, 0.5, 0.6, 0.7])
    ax.set_xticks(x)
    ax.set_xticklabels([])
    ax.set_ylabel("Recovery ratio")
    outward_spines(ax)


def panel_c(ax, fr):
    x = np.arange(len(RINGS))
    w = 0.34
    ax.bar(x - w / 2, 100 * fr["share_cameras"], width=w, color=COL["red"], lw=0, label="Cameras")
    ax.bar(x + w / 2, 100 * fr["share_baseline_flow"], width=w, color=tint(COL["red"], 0.4), lw=0,
           label="Baseline flow")
    ax.legend(handles=[Patch(facecolor=COL["red"], label="By number of cameras"),
                       Patch(facecolor=tint(COL["red"], 0.4), label="By baseline flow")],
              loc="upper right", fontsize=FS_NOTE, handlelength=1.0, handleheight=0.8)
    ax.set_xlim(-0.5, len(RINGS) - 0.5)
    ax.set_ylim(0, 40)
    ax.set_yticks([0, 20, 40])
    ax.set_xticks(x)
    ax.set_xticklabels(RING_LABELS)
    ax.tick_params(axis="x", length=0)
    ax.set_xlabel("Distance from Baiguan (km)")
    ax.set_ylabel("Failed within ring (%)")
    outward_spines(ax, bottom=False)


def panel_d(ax, coefs):
    n = len(SAMPLES)
    ax.axvline(0, color=COL["bluegrey"], lw=0.8, ls=(0, (3, 2)), zorder=1)
    for k, (key, label, cname, mk) in enumerate(SAMPLES):
        y0 = (n - 1 - k) * ROW_STEP
        col = COL[cname]
        rows = coefs[coefs["sample"] == key].set_index("date")
        for day in DAYS:
            if day not in rows.index:
                continue
            r = rows.loc[day]
            y = y0 + DAY_DY[day]
            ax.add_line(Line2D([r["ci_lo"], r["ci_hi"]], [y, y], color=col, lw=0.9, zorder=2))
            ax.plot([r["coef"]], [y], mk, ms=3.6, mfc=tint(col, DAY_FILL[day]) if DAY_FILL[day] else "white",
                    mec=col, mew=0.9, zorder=3)
        ax.text(-0.175, y0 + 0.36, label, fontsize=FS_NOTE, ha="left", va="bottom")
    handles = [Line2D([], [], ls="none", marker="o", ms=3.6, mec=COL["ink"], mew=0.9,
                      mfc=tint(COL["ink"], DAY_FILL[d]) if DAY_FILL[d] else "white",
                      label=f"{pd.Timestamp(d).day} Jul")
               for d in DAYS]
    ax.legend(handles=handles, loc="upper right", ncol=3, fontsize=FS_NOTE, handlelength=0.8,
              columnspacing=0.9, borderaxespad=0.0)
    ax.set_xlim(-0.18, 0.18)
    ax.set_xticks([-0.15, -0.10, -0.05, 0, 0.05, 0.10, 0.15])
    ax.set_xticklabels(["−0.15", "−0.10", "−0.05", "0", "0.05", "0.10", "0.15"])
    ax.set_ylim(-0.45, (n - 1) * ROW_STEP + 0.95)
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    ax.set_xlabel("Distance coefficient (<0: lower farther out)")
    outward_spines(ax, left=False)


# ---------------------------------------------------------------- source data
def write_source_data(*args, **kwargs):
    pass


def main():
    mpl.rcParams.update(PUBLICATION_RC)
    mpl.rcParams.update(secondary_rc(FS_BODY, FS_TICK))
    dem, dem_ext = load_dem()
    boundary = load_boundary()
    cells, failed, note = load_cells()
    rings = load_rings()
    fr = load_failed_by_ring()
    coefs = load_coefficients()
    write_source_data(cells, failed, rings, fr, coefs)

    fig = plt.figure(figsize=(FIG_WIDTH_MM * MM, FIG_HEIGHT_MM * MM))
    gs = gridspec_mm(fig, 3, 2, width_mm=FIG_WIDTH_MM, height_mm=FIG_HEIGHT_MM, left=LEFT, right=RIGHT,
                     top=TOP, bottom=BOTTOM, col_gutter=COL_GUT, row_gutter=ROW_GUT, panel_w=PANEL_W,
                     panel_h_avg=(H_B + H_C + H_D) / 3, height_ratios=[H_B, H_C, H_D])
    ax_a = fig.add_subplot(gs[:, 0])
    ax_b = fig.add_subplot(gs[0, 1])
    ax_c = fig.add_subplot(gs[1, 1])
    ax_d = fig.add_subplot(gs[2, 1])
    panel_a(ax_a, dem, dem_ext, boundary, cells, failed, note)
    panel_b(ax_b, rings, note)
    panel_c(ax_c, fr)
    panel_d(ax_d, coefs)
    add_panel_label(ax_a, "a", "Recovery among health-screened cameras, 26 Jul", FS_LETTER, FS_BODY)
    add_panel_label(ax_b, "b", "Recovery by distance ring, 26 Jul", FS_LETTER, FS_BODY)
    add_panel_label(ax_c, "c", "Share failed within each ring, 26 Jul", FS_LETTER, FS_BODY)
    add_panel_label(ax_d, "d", "Distance gradient by sample and day", FS_LETTER, FS_BODY)

    QA.mkdir(exist_ok=True)
    report = require_matplotlib_panel_alignment(
        fig, json_out=QA / "fig5_spatial.alignment.json", overlay_svg=QA / "fig5_spatial.alignment.svg",
        tolerance_pt=1.5, gutter_tolerance_pt=1.5, require_panel_labels=True, strict=True)
    fig.savefig(OUT / "fig5_spatial.svg")
    fig.savefig(OUT / "fig5_spatial.pdf")
    # Uncompressed TIFF: the local libtiff build aborts on LZW compression.
    fig.savefig(OUT / "fig5_spatial.tiff", dpi=600)
    fig.savefig(OUT / "fig5_spatial.png", dpi=300)
    plt.close(fig)
    print("alignment:", report.get("verdict"), "| size mm:", FIG_WIDTH_MM, round(FIG_HEIGHT_MM, 1))


if __name__ == "__main__":
    main()
