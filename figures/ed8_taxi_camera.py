"""Extended Data Fig. 8 | Taxis and cameras give different spatial pictures of recovery.

a  26 July taxi GPS-point ratio against camera record ratio (fixed stable set) in the 130 shared 1 km
   grid cells with at least 200 baseline taxi points
b  Both ratios against distance from Baiguan in the same cells
c  Shift in the share of taxi GPS points by distance ring (event day minus same-weekday baseline),
   25-28 July, with 95% intervals
d  Spearman rank correlations for 25-28 July at grid thresholds of 100, 200 and 400 taxi points

Cell-level ratios only; grid coordinates are not written. All rows of the frozen tables are plotted.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.ticker import FixedLocator, NullLocator  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
try:
    from audit_panel_alignment import require_matplotlib_panel_alignment
except ImportError:
    def require_matplotlib_panel_alignment(*args, **kwargs):
        return {"verdict": "skipped_optional_QA_unavailable"}
from figstyle import COL, MM, add_panel_label, outward_spines, secondary_rc, tint  # noqa: E402

ROOT = HERE.parent
OUT = HERE.parent / "outputs" / "figures"
OUT.mkdir(parents=True, exist_ok=True)
SRC = HERE.parent / "source_data"
QA = OUT / "qa"
NAME = "ed8_taxi_camera"

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
LEFT, RIGHT, TOP, BOTTOM = 14.0, 3.0, 8.0, 11.0
COL_GUT, ROW_GUT = 18.0, 17.0
W = (FIG_WIDTH_MM - LEFT - RIGHT - COL_GUT) / 2
H_TOP, H_BOTTOM = 52.0, 46.0
FIG_HEIGHT_MM = TOP + H_TOP + ROW_GUT + H_BOTTOM + BOTTOM

DATE = "2021-07-26"
DATES = ["2021-07-25", "2021-07-26", "2021-07-27", "2021-07-28"]
RINGS = ["0-2", "2-4", "4-7", "7-12", "12+"]
METRICS = [("taxi_camera", "Taxi vs camera", COL["ink"]),
           ("dist_taxi", "Taxi vs distance", COL["teal"]),
           ("dist_camera", "Camera vs distance", COL["blue"])]
THRESHOLDS = [(100, "o", "100"), (200, "s", "200"), (400, "D", "400")]
LOG_TICKS = [0.125, 0.25, 0.5, 1, 2, 4]


# ---------------------------------------------------------------- data
def load():
    p = pd.read_csv(SRC / "ed8ab_paired_cells_threshold200.csv")
    c = pd.read_csv(SRC / "ed8d_rank_correlations.csv")
    r = pd.read_csv(SRC / "ed8c_taxi_share_shift.csv")
    key = c[(c["date"] == DATE) & (c["threshold"] == 200)].set_index("metric")
    return p, c, r, key


def write_source_data(*args, **kwargs):
    pass


# ---------------------------------------------------------------- panels
def set_log(ax, which, lim):
    getattr(ax, f"set_{which}scale")("log")
    getattr(ax, f"set_{which}lim")(*lim)
    loc = getattr(ax, f"{which}axis")
    loc.set_major_locator(FixedLocator(LOG_TICKS))
    loc.set_minor_locator(NullLocator())
    getattr(ax, f"set_{which}ticklabels")(["0.125", "0.25", "0.5", "1", "2", "4"])


def panel_a(ax, p, key):
    d = p[p["date"] == DATE]
    ax.plot([0.1, 4.5], [0.1, 4.5], color=COL["bluegrey"], lw=0.8, ls=(0, (3, 2)), zorder=1)
    ax.scatter(d["r_camera"], d["r_taxi_pts"], s=9, facecolor=tint(COL["ink"], 0.75), edgecolor="white",
               linewidth=0.3, zorder=2)
    set_log(ax, "x", (0.2, 4.0))
    set_log(ax, "y", (0.1, 4.0))
    ax.set_xlabel("Camera record ratio, fixed stable set")
    ax.set_ylabel("Taxi GPS-point ratio")
    k = key.loc["taxi_camera"]
    ax.text(0.97, 0.03, f"Spearman ρ = {k['spearman_rho']:.2f}, P = {k['spearman_p']:.2f}\n"
            f"n = {int(k['n_grids'])} grid cells, 26 July", transform=ax.transAxes, fontsize=FS_NOTE, ha="right",
            va="bottom", linespacing=1.15)
    ax.text(3.9, 1.6, "Equal ratios", fontsize=FS_NOTE, ha="right", va="top", color=COL["ink"])
    outward_spines(ax)


def panel_b(ax, p, key):
    d = p[p["date"] == DATE]
    ax.scatter(d["dist_baiguan_km"], d["r_taxi_pts"], s=9, marker="o", facecolor=COL["teal"], edgecolor="white",
               linewidth=0.3, zorder=2)
    ax.scatter(d["dist_baiguan_km"], d["r_camera"], s=9, marker="s", facecolor=COL["blue"], edgecolor="white",
               linewidth=0.3, zorder=3)
    set_log(ax, "y", (0.1, 4.0))
    ax.set_xlim(0, 26)
    ax.set_xticks([0, 5, 10, 15, 20, 25])
    ax.set_xlabel("Distance from Baiguan (km)")
    ax.set_ylabel("Ratio on 26 July")
    t, c = key.loc["dist_taxi"], key.loc["dist_camera"]
    fmt = lambda v: f"{v:+.2f}".replace("-", "−")
    handles = [Line2D([], [], marker="o", ls="none", ms=3.4, mfc=COL["teal"], mec="white", mew=0.3,
                      label=f"Taxi GPS points: ρ = {fmt(t['spearman_rho'])} (P = {t['spearman_p']:.3f})"),
               Line2D([], [], marker="s", ls="none", ms=3.2, mfc=COL["blue"], mec="white", mew=0.3,
                      label=f"Camera records: ρ = {fmt(c['spearman_rho'])} (P = {c['spearman_p']:.3f})")]
    ax.legend(handles=handles, loc="lower right", fontsize=FS_NOTE, handletextpad=0.2, borderaxespad=0.2)
    outward_spines(ax)


def panel_c(ax, r):
    x0 = np.arange(len(RINGS))
    shades = [0.65, 1.0, 0.45, 0.3]       # 26 July, the key date, darkest
    for k, date in enumerate(DATES):
        d = r[r["date"] == date].set_index("distance_ring").loc[RINGS]
        x = x0 + (k - 1.5) * 0.17
        col = tint(COL["teal"], shades[k]) if date != DATE else COL["teal"]
        ax.vlines(x, d["share_shift_ci_lo"], d["share_shift_ci_hi"], color=col, lw=0.9, zorder=2)
        ax.plot(x, d["share_shift"], "o", ms=3.2, color=col, mec="white", mew=0.3, ls="none", zorder=3,
                label=f"{pd.Timestamp(date).day} Jul")
    ax.axhline(0, color=COL["bluegrey"], lw=0.8, ls=(0, (3, 2)), zorder=1)
    ax.set_xlim(-0.6, len(RINGS) - 0.4)
    ax.set_xticks(x0)
    ax.set_xticklabels([r_.replace("-", "–") for r_ in RINGS])
    ax.set_xlabel("Distance ring from Baiguan (km)")
    ax.set_ylim(-0.2, 0.12)
    ax.set_yticks([-0.2, -0.1, 0, 0.1])
    ax.set_yticklabels(["−0.2", "−0.1", "0", "0.1"])
    ax.set_ylabel("Shift in share of\ntaxi GPS points", linespacing=1.15)
    ax.legend(loc="lower right", ncol=4, fontsize=FS_NOTE, handletextpad=0.1, columnspacing=0.8,
              borderaxespad=0.2)
    outward_spines(ax)


def panel_d(ax, c):
    block = len(DATES) + 1.2
    for m, (metric, label, col) in enumerate(METRICS):
        for t, (thr, mk, _) in enumerate(THRESHOLDS):
            d = c[(c["metric"] == metric) & (c["threshold"] == thr)].set_index("date").loc[DATES]
            x = m * block + np.arange(len(DATES)) + (t - 1) * 0.2
            filled = d["spearman_p"] < 0.05
            ax.plot(x[filled.to_numpy()], d["spearman_rho"][filled], mk, ms=3.0, color=col, mec=col, ls="none",
                    zorder=3)
            ax.plot(x[~filled.to_numpy()], d["spearman_rho"][~filled], mk, ms=3.0, mfc="white", mec=col, mew=0.7,
                    ls="none", zorder=3)
        ax.text(m * block + (len(DATES) - 1) / 2, 0.36, label, fontsize=FS_NOTE, ha="center", va="bottom",
                color=col)
    ax.axhline(0, color=COL["bluegrey"], lw=0.8, ls=(0, (3, 2)), zorder=1)
    ticks = [m * block + i for m in range(len(METRICS)) for i in range(len(DATES))]
    ax.set_xticks(ticks)
    ax.set_xticklabels([str(pd.Timestamp(d).day) for _ in METRICS for d in DATES])
    ax.set_xlim(-0.6, (len(METRICS) - 1) * block + len(DATES) - 0.4)
    ax.set_xlabel("July 2021")
    ax.set_ylim(-0.52, 0.45)
    ax.set_yticks([-0.4, -0.2, 0, 0.2, 0.4])
    ax.set_yticklabels(["−0.4", "−0.2", "0", "0.2", "0.4"])
    ax.set_ylabel("Spearman ρ")
    handles = [Line2D([], [], marker=mk, ls="none", ms=3.0, mfc="white", mec=COL["ink"], mew=0.7,
                      label=f"≥{lab} points") for _, mk, lab in THRESHOLDS]
    handles.append(Line2D([], [], marker="o", ls="none", ms=3.0, color=COL["ink"], label="Filled: P < 0.05"))
    ax.legend(handles=handles, loc="lower left", ncol=4, fontsize=FS_NOTE, handletextpad=0.1, columnspacing=0.8,
              borderaxespad=0.2)
    outward_spines(ax)


def main():
    mpl.rcParams.update(PUBLICATION_RC)
    mpl.rcParams.update(secondary_rc(FS_BODY, FS_TICK))
    p, c, r, key = load()
    write_source_data(p, c, r)

    fig = plt.figure(figsize=(FIG_WIDTH_MM * MM, FIG_HEIGHT_MM * MM))
    gs = fig.add_gridspec(2, 2, left=LEFT / FIG_WIDTH_MM, right=1 - RIGHT / FIG_WIDTH_MM,
                          bottom=BOTTOM / FIG_HEIGHT_MM, top=1 - TOP / FIG_HEIGHT_MM,
                          wspace=COL_GUT / W, hspace=ROW_GUT / ((H_TOP + H_BOTTOM) / 2),
                          height_ratios=[H_TOP, H_BOTTOM])
    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])
    ax_c = fig.add_subplot(gs[1, 0])
    ax_d = fig.add_subplot(gs[1, 1])
    panel_a(ax_a, p, key)
    panel_b(ax_b, p, key)
    panel_c(ax_c, r)
    panel_d(ax_d, c)
    add_panel_label(ax_a, "a", "Taxi against camera ratios in shared grid cells", FS_LETTER, FS_BODY)
    add_panel_label(ax_b, "b", "Both ratios against distance", FS_LETTER, FS_BODY)
    add_panel_label(ax_c, "c", "Where taxi GPS points shifted", FS_LETTER, FS_BODY)
    add_panel_label(ax_d, "d", "Rank correlations across dates and thresholds", FS_LETTER, FS_BODY)

    QA.mkdir(parents=True, exist_ok=True)
    report = require_matplotlib_panel_alignment(
        fig, json_out=QA / f"{NAME}.alignment.json", overlay_svg=QA / f"{NAME}.alignment.svg",
        tolerance_pt=1.5, gutter_tolerance_pt=1.5, require_panel_labels=True, strict=True)
    fig.savefig(OUT / f"{NAME}.svg")
    fig.savefig(OUT / f"{NAME}.pdf")
    # Uncompressed TIFF: the local libtiff build aborts on LZW compression.
    fig.savefig(OUT / f"{NAME}.tiff", dpi=600)
    fig.savefig(OUT / f"{NAME}.png", dpi=300)
    plt.close(fig)
    print("alignment:", report.get("verdict"), "| size mm:", FIG_WIDTH_MM, round(FIG_HEIGHT_MM, 1))


if __name__ == "__main__":
    main()
