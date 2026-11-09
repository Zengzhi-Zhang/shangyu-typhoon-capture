"""Extended Data Fig. 3 | Where the capture check applies, and whether passage geometry drives it.

a  Cameras eligible for matching (at least 30 GPS-inferred passages in the control period, 12-19 July)
   and cameras selected as matchable (control-period capture at least 0.3), by baseline-flow quartile
   and by anonymised management unit
b  Control-period capture of the 925 eligible cameras, with the 0.3 selection threshold
c  Share of GPS-inferred passages kept by three geometry filters (direction-consistent, same-road,
   both), event period against control period, for failed matchable cameras and comparable
   stable-set cameras, 25-28 July
d  Projected distance of passages from the camera: median per-camera shift (event minus control) and
   the pooled share of passages 40-60 m from the camera

Selection uses the control period only. All rows of the frozen tables are plotted.
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
from matplotlib.patches import Patch  # noqa: E402
from matplotlib.ticker import FixedLocator  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
try:
    from audit_panel_alignment import require_matplotlib_panel_alignment
except ImportError:
    def require_matplotlib_panel_alignment(*args, **kwargs):
        return {"verdict": "skipped_optional_QA_unavailable"}
from figstyle import COL, MM, add_panel_label, outward_spines, secondary_rc, tint  # noqa: E402
from ed_common import unit_table  # noqa: E402

ROOT = HERE.parent
OUT = HERE.parent / "outputs" / "figures"
OUT.mkdir(parents=True, exist_ok=True)
SRC = HERE.parent / "source_data"
QA = OUT / "qa"
NAME = "ed3_matchable"

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
LINESPACING = 1.15

# ---------------------------------------------------------------- layout (mm)
FIG_WIDTH_MM = 180.0
LEFT, RIGHT, TOP, BOTTOM = 15.5, 3.0, 8.0, 10.0
COL_GUT = 17.0
W = (FIG_WIDTH_MM - LEFT - RIGHT - COL_GUT) / 2
GAP = 1.5
H_TOP, SP_MID, H_D1, SP_D, H_D2 = 58.0, 13.0, 23.0, 0.0, 23.0   # row-1 -> row-2 gap = 2 GAP + SP_MID
HEIGHTS = [H_TOP, SP_MID, H_D1, SP_D, H_D2]
FIG_HEIGHT_MM = TOP + sum(HEIGHTS) + GAP * (len(HEIGHTS) - 1) + BOTTOM

GROUPS = {"A1_failed": ("Failed matchable cameras", COL["red"]),
          "Sstar": ("Comparable stable-set cameras", COL["blue"])}
FILTERS = {"G1": ("Direction-consistent", "o"), "G2": ("Same road", "s"), "G3": ("Both", "^")}
DATES = ["2021-07-25", "2021-07-26", "2021-07-27", "2021-07-28"]


# ---------------------------------------------------------------- data
def load_quartiles():
    t = pd.read_csv(SRC / "ed3a_selection.csv")
    return t[t.grouping.eq("baseline-flow quartile")].drop(columns="grouping").reset_index(drop=True)


def load_units():
    return unit_table().rename(columns={"unit":"label"})


def load_capture():
    return pd.read_csv(SRC / "ed3b_control_capture_eligible.csv")


def load_geometry():
    return pd.read_csv(SRC / "ed3c_geometry_filter_shares.csv"), pd.read_csv(SRC / "ed3d_distance_shift.csv")


def write_source_data(*args, **kwargs):
    pass


# ---------------------------------------------------------------- panels
def panel_a(ax, q, u):
    rows = pd.concat([q, u], ignore_index=True)
    y = np.r_[np.arange(len(q)), np.arange(len(u)) + len(q) + 0.8]
    h = 0.62
    ax.barh(y, rows["eligible"], height=h, color=tint(COL["bluegrey"], 0.75), lw=0, zorder=1)
    ax.barh(y, rows["matchable"], height=h, color=COL["blue"], lw=0, zorder=2)
    for yi, r in zip(y, rows.itertuples()):
        ax.text(r.eligible + 4, yi, f"{r.matchable} / {r.eligible}", fontsize=FS_NOTE, ha="left", va="center")
    ax.set_yticks(y)
    ax.set_yticklabels(rows["label"])
    ax.set_ylim(y[-1] + 0.6, -0.6)
    ax.set_xlim(0, 285)
    ax.set_xticks([0, 100, 200])
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    outward_spines(ax, left=False)
    ax.spines["bottom"].set_bounds(0, 250)
    ax.set_xlabel("Cameras")
    ysep = len(q) - 0.1
    ax.plot([0, 285], [ysep, ysep], color=COL["ink"], lw=0.4, zorder=3)
    handles = [Patch(facecolor=tint(COL["bluegrey"], 0.75), edgecolor="none", label="Eligible (≥30 passages)"),
               Patch(facecolor=COL["blue"], edgecolor="none", label="Matchable (capture ≥0.3)")]
    ax.legend(handles=handles, loc="lower right", bbox_to_anchor=(1.0, 0.0), fontsize=FS_NOTE, handlelength=1.2,
              borderaxespad=0.2)


def panel_b(ax, cap):
    bins = np.arange(21) / 20   # exact edges, so a capture of 0.3000 falls in the 0.30 bin
    lo = cap.loc[~cap["matchable"], "capture"]
    hi = cap.loc[cap["matchable"], "capture"]
    ax.hist(lo, bins=bins, color=tint(COL["bluegrey"], 0.75), lw=0, zorder=2)
    ax.hist(hi, bins=bins, color=COL["blue"], lw=0, zorder=2)
    ax.axvline(0.3, color=COL["ink"], lw=0.7, ls=(0, (2.2, 1.6)), zorder=3)
    ax.text(0.315, 395, "Threshold 0.3", fontsize=FS_NOTE, ha="left", va="top")
    ax.text(0.15, 230, f"{len(lo)} below", fontsize=FS_NOTE, ha="center", va="bottom")
    ax.text(0.65, 230, f"{len(hi)} matchable", fontsize=FS_NOTE, ha="center", va="bottom", color=COL["blue"])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 400)
    ax.set_yticks([0, 100, 200, 300, 400])
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_xticklabels(["0", "0.25", "0.50", "0.75", "1.00"])
    ax.set_xlabel("Control-period capture rate")
    ax.set_ylabel("Eligible cameras")
    outward_spines(ax)


def panel_c(ax, s):
    lim = (0.45, 1.0)
    ax.plot(lim, lim, color=COL["bluegrey"], lw=0.8, ls=(0, (3, 2)), zorder=1)
    ax.text(0.81, 0.775, "Event = control", fontsize=FS_NOTE, ha="left", va="top")
    for (grp, flt), d in s.groupby(["group", "filter"]):
        colour = GROUPS[grp][1]
        ax.scatter(d["control_retained_share"], d["event_retained_share"], s=13, marker=FILTERS[flt][1],
                   facecolor=colour, edgecolor="white", linewidth=0.35, zorder=3)
    ax.set_xlim(*lim)
    ax.set_ylim(*lim)
    ticks = [0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    ax.set_xticks(ticks)
    ax.set_yticks(ticks)
    ax.set_xticklabels([f"{t:.1f}" for t in ticks])
    ax.set_yticklabels([f"{t:.1f}" for t in ticks])
    ax.set_xlabel("Passages kept, control period")
    ax.set_ylabel("Passages kept, event day")
    outward_spines(ax)
    group_handles = [Line2D([], [], marker="o", ls="none", ms=3.6, mfc=c, mec="none", label=lab)
                     for lab, c in GROUPS.values()]
    filter_handles = [Line2D([], [], marker=m, ls="none", ms=3.6, mfc=COL["ink"], mec="none", label=lab)
                      for lab, m in FILTERS.values()]
    leg = ax.legend(handles=group_handles, loc="upper left", bbox_to_anchor=(0.0, 1.0), fontsize=FS_NOTE,
                    handletextpad=0.2, borderaxespad=0.2)
    ax.add_artist(leg)
    ax.legend(handles=filter_handles, loc="lower right", bbox_to_anchor=(1.0, 0.0), fontsize=FS_NOTE,
              handletextpad=0.2, borderaxespad=0.2)


def date_positions():
    base = np.arange(len(DATES), dtype=float)
    return {"A1_failed": base - 0.14, "Sstar": base + 0.14}


def panel_d(ax_shift, ax_band, g):
    pos = date_positions()
    for grp, (label, colour) in GROUPS.items():
        d = g[g["group"] == grp].set_index("date").loc[DATES]
        x = pos[grp]
        ax_shift.vlines(x, d["shift_q25_m"], d["shift_q75_m"], color=colour, lw=1.0, zorder=2)
        ax_shift.plot(x, d["shift_median_m"], "o", ms=3.4, mfc=colour, mec="white", mew=0.4, zorder=3, ls="none")
        ax_band.vlines(x, d["control_40_60_share"], d["event_40_60_share"], color=colour, lw=0.8, zorder=2)
        ax_band.plot(x, d["control_40_60_share"], "o", ms=3.4, mfc="white", mec=colour, mew=0.8, zorder=3, ls="none")
        ax_band.plot(x, d["event_40_60_share"], "o", ms=3.4, mfc=colour, mec="white", mew=0.4, zorder=3, ls="none")
    ax_shift.axhline(0, color=COL["bluegrey"], lw=0.8, ls=(0, (3, 2)), zorder=1)
    ax_shift.set_ylim(-9, 3)
    ax_shift.set_yticks([-8, -4, 0])
    ax_shift.set_ylabel("Event − control\ndistance (m)", linespacing=LINESPACING)
    ax_band.set_ylim(0.10, 0.30)
    ax_band.set_yticks([0.10, 0.20, 0.30])
    ax_band.set_yticklabels(["0.10", "0.20", "0.30"])
    ax_band.set_ylabel("Share at\n40–60 m", linespacing=LINESPACING)
    for ax in (ax_shift, ax_band):
        ax.set_xlim(-0.5, len(DATES) - 0.5)
        outward_spines(ax)
    ax_shift.tick_params(axis="x", labelbottom=False)
    ax_shift.spines["bottom"].set_visible(False)
    ax_shift.tick_params(axis="x", length=0)
    ax_band.xaxis.set_major_locator(FixedLocator(range(len(DATES))))
    ax_band.set_xticklabels([f"{pd.Timestamp(d).day} Jul" for d in DATES])
    ax_shift.text(len(DATES) - 0.45, 2.6, "Median and interquartile range", fontsize=FS_NOTE, ha="right", va="top")
    handles = [Line2D([], [], marker="o", ls="none", ms=3.4, mfc="white", mec=COL["ink"], mew=0.8, label="Control"),
               Line2D([], [], marker="o", ls="none", ms=3.4, mfc=COL["ink"], mec="none", label="Event day")]
    ax_band.legend(handles=handles, loc="upper right", bbox_to_anchor=(1.0, 1.04), ncol=2, fontsize=FS_NOTE,
                   handletextpad=0.1, columnspacing=0.8, borderaxespad=0.0)
    ax_shift.figure.align_ylabels([ax_shift, ax_band])


def main():
    mpl.rcParams.update(PUBLICATION_RC)
    mpl.rcParams.update(secondary_rc(FS_BODY, FS_TICK))
    q = load_quartiles()
    u = load_units()
    cap = load_capture()
    s, g = load_geometry()
    write_source_data(q, u, cap, s, g)

    fig = plt.figure(figsize=(FIG_WIDTH_MM * MM, FIG_HEIGHT_MM * MM))
    gs = fig.add_gridspec(len(HEIGHTS), 2, left=LEFT / FIG_WIDTH_MM, right=1 - RIGHT / FIG_WIDTH_MM,
                          bottom=BOTTOM / FIG_HEIGHT_MM, top=1 - TOP / FIG_HEIGHT_MM,
                          wspace=COL_GUT / W, hspace=GAP / np.mean(HEIGHTS), height_ratios=HEIGHTS)
    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])
    ax_c = fig.add_subplot(gs[2:5, 0])
    ax_d1 = fig.add_subplot(gs[2, 1])
    ax_d2 = fig.add_subplot(gs[4, 1])
    ax_d2.set_gid("d-band")
    panel_a(ax_a, q, u)
    panel_b(ax_b, cap)
    panel_c(ax_c, s)
    panel_d(ax_d1, ax_d2, g)
    add_panel_label(ax_a, "a", "Eligible and matchable cameras", FS_LETTER, FS_BODY)
    add_panel_label(ax_b, "b", "Control-period capture of eligible cameras", FS_LETTER, FS_BODY)
    add_panel_label(ax_c, "c", "Passages kept by geometry filters, 25–28 July", FS_LETTER, FS_BODY)
    add_panel_label(ax_d1, "d", "Distance of passages from the camera", FS_LETTER, FS_BODY)

    QA.mkdir(parents=True, exist_ok=True)
    report = require_matplotlib_panel_alignment(
        fig, json_out=QA / f"{NAME}.alignment.json", overlay_svg=QA / f"{NAME}.alignment.svg",
        tolerance_pt=1.5, gutter_tolerance_pt=1.5, require_panel_labels=True, strict=True,
        axes=[ax_a, ax_b, ax_c, ax_d1])
    tracks = require_matplotlib_panel_alignment(
        fig, json_out=QA / f"{NAME}.tracks.alignment.json", overlay_svg=QA / f"{NAME}.tracks.alignment.svg",
        tolerance_pt=1.5, gutter_tolerance_pt=1.5, require_panel_labels=False, strict=True,
        axes=[ax_d1, ax_d2])
    fig.savefig(OUT / f"{NAME}.svg")
    fig.savefig(OUT / f"{NAME}.pdf")
    # Uncompressed TIFF: the local libtiff build aborts on LZW compression.
    fig.savefig(OUT / f"{NAME}.tiff", dpi=600)
    fig.savefig(OUT / f"{NAME}.png", dpi=300)
    plt.close(fig)
    print("alignment:", report.get("verdict"), "| tracks:", tracks.get("verdict"),
          "| size mm:", FIG_WIDTH_MM, round(FIG_HEIGHT_MM, 1))


if __name__ == "__main__":
    main()
