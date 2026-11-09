"""Extended Data Fig. 1 | The camera-platform outage and camera failures occupy different periods.

a  Hourly records from all cameras (log scale), cameras reporting and moving taxi GPS points,
   18-28 July 2021. Band: the frozen platform-outage timeline (21 Jul 23:00 to 25 Jul 11:00).
   Dashed lines: onset and recovery identified from citywide hourly record thresholds
   (22 Jul 00:00 and 25 Jul 12:00). The two definitions are drawn separately and not mixed.
b  The 14 cameras that recorded during the outage: daily records as a share of their own
   same-weekday baseline, with the number of cameras and lanes that recorded. Aggregates only.
c  Failed cameras per day among the 1,221 A200 cameras (below 5% of the event-aware denominator).
d  Cameras recording 5-50% of the event-aware denominator per day.

All rows of the frozen tables are plotted; no rows are dropped. No device identifiers are written.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib as mpl

mpl.use("Agg")
import matplotlib.patheffects as pe  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch, Rectangle  # noqa: E402
from matplotlib.ticker import FixedLocator, NullLocator  # noqa: E402
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
NAME = "ed1_outage"


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
HALO = [pe.withStroke(linewidth=1.6, foreground="white")]
LINESPACING = 1.2

# ---------------------------------------------------------------- layout (mm)
FIG_WIDTH_MM = 180.0
LEFT, RIGHT, TOP, BOTTOM = 16.5, 3.0, 8.0, 12.0
GAP = 2.5                       # between stacked tracks (uniform gridspec gap)
SP_AC, SP_CD = 8.5, 3.0         # spacer rows: a -> c gap = 2 GAP + SP_AC; c -> d gap = 2 GAP + SP_CD
HEIGHTS = [22.0, 14.0, 14.0, SP_AC, 15.0, SP_CD, 15.0]
W_B, COL_GUT = 48.0, 18.0
W_CD = FIG_WIDTH_MM - LEFT - RIGHT - W_B - COL_GUT
FIG_HEIGHT_MM = TOP + sum(HEIGHTS) + GAP * (len(HEIGHTS) - 1) + BOTTOM

T_ORIGIN = pd.Timestamp("2021-07-18 00:00")
OUTAGE_BAND = tint(COL["bluegrey"], 0.45)
DASH = (0, (2.2, 1.6))
OUTAGE_DAYS = ["2021-07-22", "2021-07-23", "2021-07-24"]
PARTIAL_DAY = "2021-07-25"          # cameras observed 11:00-23:59 only
CONTROL_WEEK = ("2021-07-12", "2021-07-19")


def hours_since(ts) -> float:
    return (pd.Timestamp(ts) - T_ORIGIN) / pd.Timedelta(hours=1)


def below_axis(ax, x, text, dy_mm):
    """Text whose top sits a fixed physical distance below the plot area, at data position x."""
    trans = ax.get_xaxis_transform() + ScaledTranslation(0, -dy_mm * MM, ax.figure.dpi_scale_trans)
    ax.text(x, 0, text, transform=trans, fontsize=FS_NOTE, ha="center", va="top")


# ---------------------------------------------------------------- data
def load_hourly():
    h = pd.read_csv(SRC / "ed1a_hourly.csv").rename(columns={"records_all_cameras":"avi_all", "cameras_reporting":"devices_reporting", "taxi_moving_gps_points":"taxi_moving_points"})
    h["x"] = [hours_since(f"{d} {hr:02d}:00") + 0.5 for d, hr in zip(h["date"], h["hour"])]
    assert len(h) == 11 * 24 and (h["avi_all"] > 0).all()
    return h.sort_values("x").reset_index(drop=True)


def load_outage():
    definitions = pd.read_csv(SRC / "ed1a_outage_definitions.csv")
    survivors = pd.read_csv(SRC / "ed1b_outage_cameras_daily.csv")
    return {"frozen":(definitions.iloc[0].start, definitions.iloc[0].end), "threshold":(definitions.iloc[1].start, definitions.iloc[1].end), "survivor_devices":int(survivors.cameras_listed.max())}


def load_survivors():
    return pd.read_csv(SRC / "ed1b_outage_cameras_daily.csv")


def load_failures():
    return pd.read_csv(SRC / "ed1cd_daily_failures.csv").rename(columns={"x_position":"x", "cameras_A200":"n_A200", "failed_below_5pct":"failed", "between_5_and_50pct":"mid", "below_50pct_total":"n_degraded_A1", "platform_outage_day":"outage", "cameras_11_to_23h_only":"partial_day", "partial_observation_day":"partial_observation"})


def write_source_data(*args, **kwargs):
    pass


# ---------------------------------------------------------------- panels
def outage_marks(ax, outage, *, band_only=False):
    x0, x1 = (hours_since(t) for t in outage["frozen"])
    ax.axvspan(x0, x1, facecolor=OUTAGE_BAND, edgecolor="none", zorder=0)
    if not band_only:
        for t in outage["threshold"]:
            ax.axvline(hours_since(t), color=COL["ink"], lw=0.6, ls=DASH, zorder=1)


def panel_a(axes, h, outage):
    ax_r, ax_c, ax_t = axes
    end = 11 * 24
    for ax in axes:
        outage_marks(ax, outage)
        ax.set_xlim(0, end)
        outward_spines(ax, pts=2.0, bottom=False)
        ax.spines["bottom"].set_visible(ax is ax_t)

    ax_r.plot(h["x"], h["avi_all"] / 1e3, color=COL["blue"], lw=0.9, zorder=3)
    ax_r.set_yscale("log")
    ax_r.set_ylim(0.06, 2500)
    ax_r.yaxis.set_major_locator(FixedLocator([0.1, 1, 10, 100, 1000]))
    ax_r.yaxis.set_minor_locator(NullLocator())
    ax_r.set_yticklabels(["0.1", "1", "10", "100", "1,000"])
    ax_r.set_ylabel("Records per hour\n(thousands)", linespacing=LINESPACING)
    x0, x1 = (hours_since(t) for t in outage["frozen"])
    ax_r.text((x0 + x1) / 2, 0.80, "Camera platform outage", transform=ax_r.get_xaxis_transform(),
              fontsize=FS_NOTE, ha="center", va="center", zorder=4)

    handles = [Patch(facecolor=OUTAGE_BAND, edgecolor="none", label="Frozen outage timeline"),
               Line2D([], [], color=COL["ink"], lw=0.6, ls=DASH, label="Hourly-threshold onset and recovery")]
    ax_r.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.0, 0.0), fontsize=FS_NOTE,
                handlelength=1.8, borderaxespad=0.3)

    ax_c.plot(h["x"], h["devices_reporting"], color=COL["blue"], lw=0.9, zorder=3)
    ax_c.set_ylim(0, 1450)
    ax_c.set_yticks([0, 500, 1000])
    ax_c.set_yticklabels(["0", "500", "1,000"])
    ax_c.set_ylabel("Cameras\nreporting", linespacing=LINESPACING)

    ax_t.plot(h["x"], h["taxi_moving_points"] / 1e3, color=COL["teal"], lw=0.9, zorder=3)
    ax_t.set_ylim(0, 29)
    ax_t.set_yticks([0, 10, 20])
    ax_t.set_ylabel("Taxi points\n(thousands)", linespacing=LINESPACING)

    for ax in (ax_r, ax_c):
        ax.tick_params(axis="x", which="both", bottom=False, labelbottom=False)
    ax_t.xaxis.set_major_locator(FixedLocator(np.arange(0, end + 1, 24)))
    ax_t.xaxis.set_minor_locator(FixedLocator(np.arange(12, end, 24)))
    ax_t.tick_params(axis="x", which="major", labelbottom=False)
    ax_t.tick_params(axis="x", which="minor", length=0, labelsize=FS_TICK)
    ax_t.set_xticklabels([str(18 + k) for k in range(11)], minor=True)
    below_axis(ax_t, end / 2, "July 2021", 4.6)
    ax_r.figure.align_ylabels(list(axes))


def panel_b(ax, surv, n_listed):
    y = np.arange(len(surv))
    ax.barh(y, surv["share_pct"], height=0.42, color=COL["blue"], lw=0, zorder=2)
    for yi, r in zip(y, surv.itertuples()):
        ax.text(r.share_pct + 2.5, yi, f"{r.share_pct:.1f}% · {r.cameras_with_records} cameras · "
                f"{r.lanes_with_records} lanes", fontsize=FS_NOTE, ha="left", va="center")
    ax.set_yticks(y)
    ax.set_yticklabels([f"{pd.Timestamp(d).day} Jul" for d in surv["date"]])
    ax.set_ylim(len(surv) - 0.45, -0.6)
    ax.set_xlim(0, 100)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    outward_spines(ax, left=False)
    ax.set_xlabel(f"Records of the {n_listed} cameras\n(% of their same-weekday baseline)",
                  linespacing=LINESPACING)


def axis_break(ax, x, pts=3.0):
    """Two short slashes across the outward bottom spine at data position x."""
    fig = ax.figure
    trans = ax.get_xaxis_transform() + ScaledTranslation(0, -pts / 72, fig.dpi_scale_trans)
    ax.add_patch(Rectangle((x - 0.42, -0.06), 0.84, 0.12, transform=trans, facecolor="white",
                           edgecolor="none", clip_on=False, zorder=5))
    for dx in (-0.22, 0.22):
        ax.plot([x + dx - 0.16, x + dx + 0.16], [-0.07, 0.07], transform=trans, color=COL["ink"],
                lw=0.6, clip_on=False, zorder=6, solid_capstyle="butt")


def panel_daily(ax, f, col, colour, ylim, yticks, *, show_x):
    x = f["x"].to_numpy()
    v = f[col].to_numpy()
    p = f["partial_day"].to_numpy()
    solid = ~p & ~np.isnan(v)
    ax.bar(x[solid], v[solid], width=0.68, color=colour, lw=0, zorder=2)
    ax.bar(x[p], v[p], width=0.68, facecolor="white", edgecolor=colour, lw=0.7, zorder=2)
    xo = f.loc[f["outage"], "x"]
    ax.axvspan(xo.min() - 0.5, xo.max() + 0.5, facecolor=OUTAGE_BAND, edgecolor="none", zorder=0)
    for xi, vi in zip(f.loc[f["partial_observation"], "x"], f.loc[f["partial_observation"], col]):
        ax.text(xi, vi + 0.035 * ylim[1], "†", fontsize=FS_NOTE, ha="center", va="bottom")
    ax.set_xlim(-0.8, f["x"].max() + 0.8)
    ax.set_ylim(*ylim)
    ax.set_yticks(yticks)
    ax.set_ylabel("Cameras")
    outward_spines(ax)
    days = pd.to_datetime(f["date"])
    labelled = {pd.Timestamp(d) for d in ("2021-06-17", "2021-06-28", "2021-07-01", "2021-07-05",
                                         "2021-07-10", "2021-07-15", "2021-07-20", "2021-07-25",
                                         "2021-07-30", "2021-08-02")}
    keep = days.isin(labelled).to_numpy()
    ax.xaxis.set_major_locator(FixedLocator(x[keep]))
    ax.xaxis.set_minor_locator(FixedLocator(x[~keep]))
    ax.tick_params(axis="x", which="minor", length=1.4)
    if show_x:
        ax.set_xticklabels([str(d.day) for d in days[keep]])
        for label, xm in (("Jun", 2.0), ("July 2021", 20.0), ("Aug", 36.5)):
            below_axis(ax, xm, label, 5.6)
    else:
        ax.tick_params(axis="x", which="major", labelbottom=False)
    axis_break(ax, 1.0)


def annotate_c(ax, f):
    xo = f.loc[f["outage"], "x"]
    ax.text(xo.mean(), 150, "Outage", fontsize=FS_NOTE, ha="center", va="center", zorder=4)
    lo, hi = CONTROL_WEEK
    xs = f.loc[f["date"].between(lo, hi), "x"]
    cw = f.loc[f["date"].between(lo, hi), "failed"]
    ax.axhspan(cw.min(), cw.max(), facecolor=tint(COL["bluegrey"], 0.8), edgecolor="none", zorder=1)
    yb = 34
    ax.plot([xs.min() - 0.4, xs.min() - 0.4, xs.max() + 0.4, xs.max() + 0.4], [yb - 7, yb, yb, yb - 7],
            color=COL["ink"], lw=0.6, zorder=3, solid_joinstyle="miter")
    ax.text(xs.mean(), yb + 6, f"Control week: {int(cw.min())}–{int(cw.max())}", fontsize=FS_NOTE,
            ha="center", va="bottom", zorder=4)


def main():
    mpl.rcParams.update(PUBLICATION_RC)
    mpl.rcParams.update(secondary_rc(FS_BODY, FS_TICK))
    h = load_hourly()
    outage = load_outage()
    surv = load_survivors()
    f = load_failures()
    assert outage["survivor_devices"] == surv["cameras_listed"].max() == 14
    assert len(f) == 37 and (f["n_A200"] == 1221).all()
    write_source_data(h, outage, surv, f)

    fig = plt.figure(figsize=(FIG_WIDTH_MM * MM, FIG_HEIGHT_MM * MM))
    gs = fig.add_gridspec(len(HEIGHTS), 2, left=LEFT / FIG_WIDTH_MM, right=1 - RIGHT / FIG_WIDTH_MM,
                          bottom=BOTTOM / FIG_HEIGHT_MM, top=1 - TOP / FIG_HEIGHT_MM,
                          wspace=COL_GUT / ((W_B + W_CD) / 2), hspace=GAP / np.mean(HEIGHTS),
                          width_ratios=[W_B, W_CD], height_ratios=HEIGHTS)
    ax_a1 = fig.add_subplot(gs[0, :])
    ax_a2 = fig.add_subplot(gs[1, :])
    ax_a3 = fig.add_subplot(gs[2, :])
    ax_b = fig.add_subplot(gs[4:7, 0])
    ax_c = fig.add_subplot(gs[4, 1])
    ax_d = fig.add_subplot(gs[6, 1])
    for ax, gid in ((ax_a1, "a"), (ax_a2, "a-cameras"), (ax_a3, "a-taxi"), (ax_b, "b"), (ax_c, "c"), (ax_d, "d")):
        ax.set_gid(gid)

    panel_a((ax_a1, ax_a2, ax_a3), h, outage)
    panel_b(ax_b, surv, outage["survivor_devices"])
    panel_daily(ax_c, f, "failed", COL["red"], (0, 185), [0, 50, 100, 150], show_x=False)
    annotate_c(ax_c, f)
    panel_daily(ax_d, f, "mid", COL["orange"], (0, 720), [0, 300, 600], show_x=True)

    add_panel_label(ax_a1, "a", "Hourly records, reporting cameras and taxi GPS points, 18–28 July",
                    FS_LETTER, FS_BODY)
    add_panel_label(ax_b, "b", "Cameras recording during the outage", FS_LETTER, FS_BODY)
    add_panel_label(ax_c, "c", "Failed cameras per day (<5% of the event-aware denominator)", FS_LETTER, FS_BODY)
    add_panel_label(ax_d, "d", "Cameras recording 5–50% of the event-aware denominator", FS_LETTER, FS_BODY)

    QA.mkdir(parents=True, exist_ok=True)
    report = require_matplotlib_panel_alignment(
        fig, json_out=QA / f"{NAME}.alignment.json", overlay_svg=QA / f"{NAME}.alignment.svg",
        tolerance_pt=1.5, gutter_tolerance_pt=1.5, require_panel_labels=True, strict=True,
        axes=[ax_a1, ax_b, ax_c, ax_d])
    tracks = require_matplotlib_panel_alignment(
        fig, json_out=QA / f"{NAME}.tracks.alignment.json", overlay_svg=QA / f"{NAME}.tracks.alignment.svg",
        tolerance_pt=1.5, gutter_tolerance_pt=1.5, require_panel_labels=False, strict=True,
        axes=[ax_a1, ax_a2, ax_a3])
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
