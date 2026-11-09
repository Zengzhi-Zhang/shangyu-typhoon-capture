"""Extended Data Fig. 7 | Day-to-day noise in distinct-plate counts, unrelated to record volume.

a  Share of each day's distinct plates on the fixed stable set that appear on only one of the 37 days,
   by plate group; band: ordinary-day median +/- 2.5 MAD for all plates; open markers: dates flagged
   by that rule within each group
b  Records per day on the fixed stable set (top) and distinct plates per 1,000 records (bottom)

A descriptive quality indicator: flags are not read as proven recognition errors. Platform-outage days
(22-24 July) are left blank and kept in the source data. All other rows of the frozen table are plotted.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402
from matplotlib.ticker import FixedLocator  # noqa: E402
from matplotlib.transforms import ScaledTranslation  # noqa: E402

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
NAME = "ed7_plates"

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
LEFT, RIGHT, TOP, BOTTOM = 13.0, 3.0, 8.0, 13.0
COL_GUT = 17.0
W = (FIG_WIDTH_MM - LEFT - RIGHT - COL_GUT) / 2
GAP = 1.5
HEIGHTS = [26.0, 0.0, 26.0]          # b tracks; a spans all rows
FIG_HEIGHT_MM = TOP + sum(HEIGHTS) + GAP * (len(HEIGHTS) - 1) + BOTTOM

GROUPS = [("all", "All plates", "ink", "o"), ("local_zheD", "Local plates", "blue", "o"),
          ("zhejiang_other", "Other Zhejiang", "teal", "s"), ("other_province", "Out of province", "red", "^")]
OUTAGE_DAYS = ["2021-07-22", "2021-07-23", "2021-07-24"]
PARTIAL_DAY = "2021-07-25"
OUTAGE_BAND = tint(COL["bluegrey"], 0.45)
LABELLED = ["2021-06-17", "2021-06-28", "2021-07-01", "2021-07-05", "2021-07-10", "2021-07-15", "2021-07-20",
            "2021-07-25", "2021-07-30", "2021-08-02"]


# ---------------------------------------------------------------- data
def load_quality():
    t = pd.read_csv(SRC / "ed7_plate_quality_Sstar.csv")
    dates = pd.to_datetime(t["date"])
    first_run = pd.Timestamp("2021-06-28")
    t["x"] = np.where(dates < first_run, 0, 2 + (dates - first_run).dt.days)
    t["outage"] = t["platform_outage_day"]
    t["partial_day"] = t["cameras_11_to_23h_only"]
    row = t[t.grp.eq("all")].iloc[0]
    band = {"median":row.baseline_singleton_median,"MAD":row.baseline_singleton_MAD,"threshold":2.5 * row.baseline_singleton_MAD}
    return t, band


def write_source_data(*args, **kwargs):
    pass


# ---------------------------------------------------------------- helpers
def below_axis(ax, x, text, dy_mm):
    trans = ax.get_xaxis_transform() + ScaledTranslation(0, -dy_mm * MM, ax.figure.dpi_scale_trans)
    ax.text(x, 0, text, transform=trans, fontsize=FS_NOTE, ha="center", va="top")


def axis_break(ax, x, pts=3.0, half_pt=1.8):
    """Two short slashes across the outward bottom spine, sized in points so that they never reach the
    tick labels whatever the panel height."""
    trans = ax.get_xaxis_transform() + ScaledTranslation(0, -pts / 72, ax.figure.dpi_scale_trans)
    h_pt = ax.get_position().height * ax.figure.get_figheight() * 72
    dy = half_pt / h_pt
    ax.add_patch(Rectangle((x - 0.42, -dy * 0.8), 0.84, dy * 1.6, transform=trans, facecolor="white",
                           edgecolor="none", clip_on=False, zorder=5))
    for dx in (-0.22, 0.22):
        ax.plot([x + dx - 0.16, x + dx + 0.16], [-dy, dy], transform=trans, color=COL["ink"], lw=0.6,
                clip_on=False, zorder=6, solid_capstyle="butt")


def date_axis(ax, t, *, show_labels, band_top=1.0):
    d = t[t["grp"] == "all"].sort_values("x")
    x = d["x"].to_numpy()
    keep = d["date"].isin(LABELLED).to_numpy()
    ax.set_xlim(-0.8, x.max() + 0.8)
    ax.xaxis.set_major_locator(FixedLocator(x[keep]))
    ax.xaxis.set_minor_locator(FixedLocator(x[~keep]))
    ax.tick_params(axis="x", which="minor", length=1.4)
    xo = d.loc[d["outage"], "x"]
    ax.axvspan(xo.min() - 0.5, xo.max() + 0.5, ymax=band_top, facecolor=OUTAGE_BAND, edgecolor="none", zorder=0)
    if show_labels:
        ax.set_xticklabels([str(pd.Timestamp(v).day) for v in d.loc[keep, "date"]])
        for label, xm in (("Jun", 2.0), ("July 2021", 20.0), ("Aug", 36.5)):
            below_axis(ax, xm, label, 5.6)
    else:
        ax.tick_params(axis="x", which="major", labelbottom=False)
    axis_break(ax, 1.0)


def series(ax, d, col, value, mk="o", ms=2.6, lw=0.9, flagged=None):
    d = d.sort_values("x")
    shown = d[~d["outage"]]
    # Lines join consecutive days only: they break at the axis break and across the outage.
    run = (shown["x"].diff().fillna(1) > 1).cumsum()
    for _, seg in shown.groupby(run):
        ax.plot(seg["x"], seg[value], color=col, lw=lw, zorder=3)
    solid = shown[~shown["partial_day"]]
    ax.plot(solid["x"], solid[value], mk, ms=ms, color=col, mec="white", mew=0.3, ls="none", zorder=4)
    p = shown[shown["partial_day"]]
    ax.plot(p["x"], p[value], mk, ms=ms, mfc="white", mec=col, mew=0.7, ls="none", zorder=4)
    if flagged is not None:
        f = shown[shown["flag_plate_noise"] == 1]
        ax.plot(f["x"], f[value], "o", ms=ms + 2.6, mfc="none", mec=col, mew=0.7, ls="none", zorder=5)


# ---------------------------------------------------------------- panels
def panel_a(ax, t, band):
    lo, hi = band["median"] - band["threshold"], band["median"] + band["threshold"]
    ax.axhspan(lo, hi, color=tint(COL["ink"], 0.12), lw=0, zorder=1)
    for grp, label, cname, mk in GROUPS:
        d = t[t["grp"] == grp]
        series(ax, d, COL[cname], "singleton_share", mk=mk, flagged=True)
    ax.set_ylim(0, 0.62)
    ax.set_yticks([0, 0.1, 0.2, 0.3, 0.4])
    ax.set_yticklabels(["0", "0.1", "0.2", "0.3", "0.4"])
    ax.set_ylabel("Share of plates seen on one day only")
    outward_spines(ax)
    ax.spines["left"].set_bounds(0, 0.45)
    date_axis(ax, t, show_labels=True, band_top=0.47 / 0.62)   # the band stops below the legend
    xo = t.loc[t["outage"] & (t["grp"] == "all"), "x"]
    ax.text(xo.mean(), 0.02, "Outage", fontsize=FS_NOTE, ha="left", va="center", rotation=90,
            rotation_mode="anchor", zorder=6)
    handles = [Line2D([], [], color=COL[c], marker=m, ms=2.6, lw=0.9, mec="white", mew=0.3, label=lab)
               for _, lab, c, m in GROUPS]
    handles.append(Line2D([], [], marker="o", ms=5.2, mfc="none", mec=COL["ink"], mew=0.7, ls="none",
                          label="Flagged: >2.5 MAD from median"))
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.0, 1.0), ncol=3, fontsize=FS_NOTE,
              handlelength=1.6, columnspacing=1.0, borderaxespad=0.0)


def panel_b(ax_r, ax_p, t):
    d = t[(t["grp"] == "all") & ~t["outage"]].sort_values("x")
    flagged_high = d["noise_flag_direction"] == "high"
    col_bar = [COL["orange"] if f else tint(COL["blue"], 0.75) for f in flagged_high]
    solid = ~d["partial_day"].to_numpy()
    ax_r.bar(d["x"][solid], d["records"][solid] / 1e6, width=0.68, color=[c for c, s in zip(col_bar, solid) if s],
             lw=0, zorder=2)
    p = d["partial_day"].to_numpy()
    ax_r.bar(d["x"][p], d["records"][p] / 1e6, width=0.68, facecolor="white", edgecolor=tint(COL["blue"], 0.75),
             lw=0.7, zorder=2)
    ax_r.set_ylim(0, 8)
    ax_r.set_yticks([0, 4, 8])
    ax_r.set_ylabel("Records\n(millions)", linespacing=LINESPACING)
    outward_spines(ax_r)
    date_axis(ax_r, t, show_labels=False)

    series(ax_p, t[t["grp"] == "all"], COL["ink"], "plates_per_1000_records")
    hi = d[flagged_high]
    ax_p.plot(hi["x"], hi["plates_per_1000_records"], "o", ms=4.0, color=COL["orange"], mec="white", mew=0.4,
              ls="none", zorder=6)
    ax_p.set_ylim(40, 90)
    ax_p.set_yticks([40, 60, 80])
    ax_p.set_ylabel("Plates per\n1,000 records", linespacing=LINESPACING)
    outward_spines(ax_p)
    date_axis(ax_p, t, show_labels=True)
    days = ", ".join(str(pd.Timestamp(v).day) for v in hi["date"])
    ax_p.legend(handles=[Line2D([], [], marker="o", ms=4.0, color=COL["orange"], mec="white", mew=0.4, ls="none",
                                label=f"Flagged high in a ({days} Jul)")],
                loc="upper left", fontsize=FS_NOTE, handletextpad=0.2, borderaxespad=0.2)
    ax_r.figure.align_ylabels([ax_r, ax_p])


def main():
    mpl.rcParams.update(PUBLICATION_RC)
    mpl.rcParams.update(secondary_rc(FS_BODY, FS_TICK))
    t, band = load_quality()
    write_source_data(t)

    fig = plt.figure(figsize=(FIG_WIDTH_MM * MM, FIG_HEIGHT_MM * MM))
    gs = fig.add_gridspec(len(HEIGHTS), 2, left=LEFT / FIG_WIDTH_MM, right=1 - RIGHT / FIG_WIDTH_MM,
                          bottom=BOTTOM / FIG_HEIGHT_MM, top=1 - TOP / FIG_HEIGHT_MM,
                          wspace=COL_GUT / W, hspace=GAP / np.mean(HEIGHTS), height_ratios=HEIGHTS)
    ax_a = fig.add_subplot(gs[0:3, 0])
    ax_b1 = fig.add_subplot(gs[0, 1])
    ax_b2 = fig.add_subplot(gs[2, 1])
    ax_b2.set_gid("b-plates")
    panel_a(ax_a, t, band)
    panel_b(ax_b1, ax_b2, t)
    add_panel_label(ax_a, "a", "One-day plates on the fixed stable set", FS_LETTER, FS_BODY)
    add_panel_label(ax_b1, "b", "Records and plates per 1,000 records", FS_LETTER, FS_BODY)

    QA.mkdir(parents=True, exist_ok=True)
    report = require_matplotlib_panel_alignment(
        fig, json_out=QA / f"{NAME}.alignment.json", overlay_svg=QA / f"{NAME}.alignment.svg",
        tolerance_pt=1.5, gutter_tolerance_pt=1.5, require_panel_labels=True, strict=True, axes=[ax_a, ax_b1])
    tracks = require_matplotlib_panel_alignment(
        fig, json_out=QA / f"{NAME}.tracks.alignment.json", overlay_svg=QA / f"{NAME}.tracks.alignment.svg",
        tolerance_pt=1.5, gutter_tolerance_pt=1.5, require_panel_labels=False, strict=True, axes=[ax_b1, ax_b2])
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
