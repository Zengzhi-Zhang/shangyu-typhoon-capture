"""Fig. 3 | How the handling of failed cameras changes the recovery a city would report.

a  Daily recovery ratio, 25 July to 2 August. The two anchor estimators carry 95% intervals;
   the online and fixed stable sets are thin context lines (their intervals are in Extended Data Fig. 4a).
b  Start date of sustained attainment of illustrative thresholds, by estimator (rows as in Table 1).
c  Break-even recovery: the recovery that roads with screened-out cameras would need for the A200
   network to reach 0.85 or 0.90, if kept cameras captured as in the baseline, against the two
   readings that bound it (screened-out cameras' record ratio and the health-screened ratio).

All estimator-day values in the frozen tables are plotted; no rows are dropped.
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
from matplotlib.patches import Patch, Rectangle  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
try:
    from audit_panel_alignment import require_matplotlib_panel_alignment
except ImportError:
    def require_matplotlib_panel_alignment(*args, **kwargs):
        return {"verdict": "skipped_optional_QA_unavailable"}
from figstyle import (COL, MM, add_panel_label, gridspec_mm,  # noqa: E402
                      outward_spines, secondary_rc, tint)

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
LEFT, RIGHT, TOP, BOTTOM = 12.0, 3.0, 8.0, 12.0
COL_GUT, ROW_GUT = 13.0, 17.0   # the b-c gutter carries the y-axis of c
H_TOP, H_BOTTOM = 50.0, 58.0
PANEL_W = (FIG_WIDTH_MM - LEFT - RIGHT - COL_GUT) / 2
FIG_HEIGHT_MM = TOP + H_TOP + ROW_GUT + H_BOTTOM + BOTTOM

DATES = pd.date_range("2021-07-25", "2021-08-02").strftime("%Y-%m-%d").tolist()
DATE_LABELS = ["25 Jul", "26 Jul", "27 Jul", "28 Jul†", "29 Jul", "30 Jul", "31 Jul",
               "1 Aug", "2 Aug"]
DATE_LABELS_SHORT = ["25 Jul", "26", "27", "28†", "29", "30", "31", "1 Aug", "2"]

KEY = [  # estimator, legend label, colour, marker, dash, dodge, anchor
    ("R_health", "Health-screened ratio", "blue", "o", (0, ()), -0.08, True),
    ("R_naive", "All-camera record ratio", "red", "o", (0, ()), 0.08, True),
    ("R_online", "Online-set ratio", "teal", "s", (0, (4, 1.6)), -0.26, False),
    ("R_stable", "Fixed stable-set ratio", "orange", "^", (0, (1.2, 1.2)), -0.18, False),
]
FAMILY = [  # rows of b, top to bottom, in the order of Table 1
    ("R_naive", "All-camera record ratio"),
    ("R_health", "Health-screened ratio"),
    ("R_online", "Online-set ratio"),
    ("R_stable", "Fixed stable-set ratio"),
    ("R_health_strict", "Strict health-screened ratio"),
    ("R_spre_health", "Pre-event set, health-screened"),
    ("R_upper", "Neighbour-imputation scenario"),
    ("R_probe", "Probe-corrected ratio"),
]
ROW_SHORT = {"R_naive": "All cameras", "R_health": "Health-screened", "R_online": "Online set",
             "R_stable": "Fixed stable set", "R_health_strict": "Strict health", "R_spre_health": "Pre-event set",
             "R_upper": "Imputation", "R_probe": "Probe-corrected‡"}
THETAS = [0.80, 0.85, 0.90, 0.95]
THETAS_C = [0.85, 0.90]          # thresholds discussed in the text and drawn in c

# panel b geometry (column units): cells span j +/- CELL_HW; row names sit left of the cells
CELL_HW = 0.47
B_XMIN, B_XMAX = -1.74, len(THETAS) - 0.5
ROWNAME_X = -0.57

# panel c geometry
BAR_HW, DX, C_YMAX = 0.30, 0.12, 1.75
ZONE = tint(COL["orange"], 0.30)   # the range in which the verdict depends on screened-out roads


# ---------------------------------------------------------------- data
def load_family():
    return pd.read_csv(SRC / "fig4a_recovery_four_estimators.csv")


def load_sustained():
    p = pd.read_csv(SRC / "fig4b_sustained_attainment.csv")
    return p.set_index(["estimator","theta"])[["first_crossing","sustained_point","sustained_lower_bound"]].rename(columns={"first_crossing":"first_ge","sustained_lower_bound":"sustained_lower_ci"})


def load_breakeven():
    be = pd.read_csv(SRC / "fig4c_breakeven.csv")
    geo = np.where(be["x_star"] <= be["R_O"], "A", np.where(be["x_star"] <= be["R_H"], "B", "C"))
    assert (geo == be["class"].to_numpy()).all()
    assert np.allclose((1 - be["w_O"]) * be["R_H"] + be["w_O"] * be["R_O"], be["R_A200"], atol=6e-4)
    return be


def load_audit():
    return pd.read_csv(SRC / "fig4c_taxi_audit_coverage.csv")


def cell_status(sus, est, theta):
    """Class of a cell and the start dates of sustained attainment within the observation window.

    "both": point estimate and daily lower bound are each sustained (their start dates may differ);
    "point": only the point estimate is sustained; "none": neither is sustained within the window.
    """
    key = (est, theta)
    point = sus.loc[key, "sustained_point"] if key in sus.index else np.nan
    lower = sus.loc[key, "sustained_lower_ci"] if key in sus.index else np.nan
    point = point if isinstance(point, str) else None
    lower = lower if isinstance(lower, str) else None
    assert not (lower and not point), (est, theta)
    if point is None:
        return "none", None, None
    if lower is not None:
        return "both", point, lower
    return "point", point, None


def short_date(iso):
    d = pd.Timestamp(iso)
    return f"{d.day} {d.strftime('%b')}"


# ---------------------------------------------------------------- panels
def panel_a(ax, fam):
    x = np.arange(len(DATES))
    x_end = len(DATES) - 0.5  # reference lines and x-axis stop at the data window
    # the two example thresholds at which sustained-attainment judgements differ (panels b and c)
    ax.hlines([0.85, 0.90], -0.5, x_end, color=COL["bluegrey"], lw=0.6, ls=(0, (1, 1.5)), zorder=0)
    ax.hlines(1.0, -0.5, x_end, color=COL["bluegrey"], lw=0.8, ls=(0, (3, 2)), zorder=1)
    ax.text(x_end + 0.12, 0.875, "θ = 0.85, 0.90", fontsize=FS_NOTE, ha="left", va="center")
    ax.text(x_end + 0.12, 1.0, "Baseline", fontsize=FS_NOTE, ha="left", va="center")
    handles = []
    for est, label, cname, mk, dash, dodge, anchor in KEY:
        col = COL[cname]
        s = fam[fam["estimator"] == est].set_index("date").reindex(DATES)
        assert s["R"].notna().all(), est
        xs = x + dodge
        y = s["R"].to_numpy()
        lw, ms, z = (1.6, 3.6, 6) if anchor else (0.8, 2.6, 3)
        ax.plot(xs, y, color=col, lw=lw, ls=dash, zorder=z)
        if anchor:  # intervals of the context lines are in Extended Data Fig. 4a
            ax.vlines(xs, s["ci_lo"].to_numpy(), s["ci_hi"].to_numpy(), color=col, lw=0.8, zorder=z - 1)
        ax.plot(xs[1:], y[1:], mk, ms=ms, color=col, mec="white", mew=0.4, ls="none", zorder=z + 1)
        ax.plot(xs[:1], y[:1], mk, ms=ms, mfc="white", mec=col, mew=0.9 if anchor else 0.7, ls="none",
                zorder=z + 1)
        handles.append(Line2D([], [], color=col, lw=lw, ls=dash, marker=mk, ms=ms, mec="white",
                              mew=0.4, label=label))
    # The gap between the two anchors on 26 July, drawn between their dodged markers.
    i26 = DATES.index("2021-07-26")
    lo = fam.query("estimator == 'R_naive' and date == '2021-07-26'")["R"].iloc[0]
    hi = fam.query("estimator == 'R_health' and date == '2021-07-26'")["R"].iloc[0]
    gap_pts = (hi - lo) * 100
    assert f"{gap_pts:.1f}" == "11.4", gap_pts
    ax.annotate("", xy=(i26, hi), xytext=(i26, lo), zorder=8,
                arrowprops=dict(arrowstyle="<->", color=COL["ink"], lw=0.6, shrinkA=0, shrinkB=0,
                                mutation_scale=5))
    ax.text(i26 + 0.18, lo - 0.035, f"Gap {gap_pts:.1f} points", fontsize=FS_NOTE, ha="left", va="center")
    ax.legend(handles=handles, loc="lower right", fontsize=FS_NOTE, handlelength=2.4,
              bbox_to_anchor=(0.93, 0.02))
    ax.set_xticks(x)
    ax.set_xticklabels(DATE_LABELS)
    ax.set_xlim(-0.5, 9.4)
    ax.set_ylim(0.3, 1.1)
    ax.set_yticks([0.4, 0.6, 0.8, 1.0])
    ax.set_xlabel("Date (2021)")
    ax.set_ylabel("Recovery ratio")
    outward_spines(ax)
    ax.spines["bottom"].set_bounds(-0.5, x_end)


def panel_b(ax, sus):
    n = len(FAMILY)
    fills = {"both": COL["blue"], "point": COL["bluegrey"], "none": COL["panel"]}
    inks = {"both": "white", "point": COL["ink"], "none": COL["ink"]}
    # Empty cells keep a hairline outline so they stay visible in print.
    edges = {"both": "none", "point": "none", "none": COL["bluegrey"]}
    for k, (est, _) in enumerate(FAMILY):
        y = n - 1 - k
        ax.text(ROWNAME_X, y, ROW_SHORT[est], fontsize=FS_NOTE, ha="right", va="center")
        for j, theta in enumerate(THETAS):
            status, point, lower = cell_status(sus, est, theta)
            ax.add_patch(Rectangle((j - CELL_HW, y - 0.42), 2 * CELL_HW, 0.84, facecolor=fills[status],
                                   edgecolor=edges[status], lw=0.5, zorder=1))
            if point is None:
                continue
            if lower is not None and lower != point:
                # Two separate lines, so their text boxes cannot overlap.
                for dy, text in ((0.19, f"Point {short_date(point)}"), (-0.19, f"Lower {short_date(lower)}")):
                    ax.text(j, y + dy, text, fontsize=FS_NOTE, ha="center", va="center", color=inks[status],
                            zorder=2)
            else:
                ax.text(j, y, short_date(point), fontsize=FS_NOTE, ha="center", va="center",
                        color=inks[status], zorder=2)
    handles = [Patch(facecolor=fills[s], edgecolor=edges[s], lw=0.5, label=lab)
               for s, lab in (("both", "Point and lower bound"), ("point", "Point only"),
                              ("none", "Not sustained in window"))]
    ax.legend(handles=handles, loc="upper left", ncol=3, fontsize=FS_NOTE, handlelength=1.0,
              handleheight=0.8, columnspacing=1.0, borderaxespad=0.0, bbox_to_anchor=(0.0, 1.0))
    ax.text(B_XMIN, n - 0.05, "Start date of sustained attainment; window ends 2 Aug (31 Jul for the probe)",
            fontsize=FS_NOTE, ha="left", va="center")
    ax.set_xlim(B_XMIN, B_XMAX)
    ax.set_ylim(-0.6, n + 0.75)
    ax.set_xticks(range(len(THETAS)))
    ax.set_xticklabels([f"{t:.2f}" for t in THETAS])
    ax.tick_params(axis="x", length=0)
    ax.set_xlabel("Illustrative threshold θ")
    # centre the axis title on the cells rather than on the whole axes, which includes the row names
    ax.xaxis.label.set_x((1.5 - B_XMIN) / (B_XMAX - B_XMIN))
    ax.set_yticks([])
    for side in ("left", "bottom"):
        ax.spines[side].set_visible(False)


def panel_c(ax, be, audit):
    n = len(DATES)
    ink = COL["ink"]
    ax.hlines(1.0, -0.5, n - 0.5, color=COL["bluegrey"], lw=0.8, ls=(0, (3, 2)), zorder=0)
    ax.text(n - 0.55, 1.02, "Baseline", fontsize=FS_NOTE, ha="right", va="bottom")
    off_scale = []
    for i, d in enumerate(DATES):
        day = be[be["date"] == d]
        ro, rh = day["R_O"].iloc[0], day["R_H"].iloc[0]
        assert np.allclose(day["R_O"], ro) and np.allclose(day["R_H"], rh) and ro < rh, d
        ax.add_patch(Rectangle((i - BAR_HW, ro), 2 * BAR_HW, rh - ro, facecolor=ZONE, edgecolor="none",
                               zorder=1))
        ax.hlines(ro, i - BAR_HW, i + BAR_HW, color=COL["red"], lw=1.4, zorder=2)
        ax.hlines(rh, i - BAR_HW, i + BAR_HW, color=COL["blue"], lw=1.4, zorder=2)
        for theta, dx, filled in ((THETAS_C[0], -DX, True), (THETAS_C[1], DX, False)):
            r = day[np.isclose(day["theta"], theta)].iloc[0]
            xs = i + dx
            face = ink if filled else "white"
            if r["x_star"] > C_YMAX:  # off scale (25 July): an upward triangle at the top edge
                off_scale.append(r["x_star"])
                ax.plot([xs], [C_YMAX - 0.05], marker="^", ms=3.4, mfc=face, mec=ink, mew=0.8, ls="none",
                        zorder=4)
                continue
            assert r["x_star_ci_hi"] <= C_YMAX, (d, theta)
            ax.vlines(xs, r["x_star_ci_lo"], r["x_star_ci_hi"], color=ink, lw=0.8, zorder=3)
            ax.plot([xs], [r["x_star"]], "o", ms=3.4, mfc=face, mec=ink, mew=0.8, ls="none", zorder=4)
    assert len(off_scale) == 2, off_scale
    ax.text(0, C_YMAX - 0.17, ", ".join(f"{v:.2f}" for v in off_scale), fontsize=FS_NOTE,
            ha="center", va="center")

    # Taxi audit window: descriptive only; it does not enter x*.
    gps = audit[audit["GPS_available"]].sort_values("date")
    i0, i1 = DATES.index(gps["date"].iloc[0]), DATES.index(gps["date"].iloc[-1])
    cap_lo, cap_hi = gps["pooled_relative_capture"].min(), gps["pooled_relative_capture"].max()
    assert (f"{cap_lo:.2f}", f"{cap_hi:.2f}") == ("0.43", "0.77"), (cap_lo, cap_hi)
    yb = 0.10
    ax.plot([i0 - 0.4, i1 + 0.4], [yb, yb], color=ink, lw=0.6, solid_capstyle="butt")
    ax.vlines([i0 - 0.4, i1 + 0.4], yb - 0.025, yb + 0.025, color=ink, lw=0.6)
    ax.text((i0 + i1) / 2, yb - 0.06, f"Taxi audit: capture {cap_lo:.2f}–{cap_hi:.2f} of control",
            fontsize=FS_NOTE, ha="center", va="center")
    ax.text((i1 + 1 + n - 1) / 2, yb - 0.06, "No taxi data", fontsize=FS_NOTE, ha="center", va="center")

    handles = [
        Line2D([], [], ls="none", marker="o", ms=3.4, color=ink, label="Needed for θ = 0.85"),
        Line2D([], [], ls="none", marker="o", ms=3.4, mfc="white", mec=ink, mew=0.8,
               label="Needed for θ = 0.90"),
        Line2D([], [], color=COL["blue"], lw=1.4, label="Health-screened ratio"),
        Line2D([], [], color=COL["red"], lw=1.4, label="Screened-out cameras' record ratio"),
        Patch(facecolor=ZONE, edgecolor="none", label="Within bar: depends on screened-out roads"),
        # text-only rows that say how to read a point against its bar
        Line2D([], [], ls="none", label="Below bar: met under both readings"),
        Line2D([], [], ls="none", label="Above bar: unmet under both readings"),
    ]
    ax.legend(handles=handles, loc="upper right", fontsize=FS_NOTE, handlelength=1.4,
              handleheight=0.8, borderaxespad=0.0, bbox_to_anchor=(1.0, 1.0))
    ax.set_xticks(range(n))
    ax.set_xticklabels(DATE_LABELS_SHORT)
    ax.set_xlim(-0.6, n - 0.5)
    ax.set_ylim(0.0, C_YMAX)
    ax.set_yticks([0.0, 0.5, 1.0, 1.5])
    ax.set_yticklabels(["0", "0.5", "1.0", "1.5"])
    ax.set_xlabel("Date (2021)")
    ax.set_ylabel("Recovery ratio")
    outward_spines(ax)
    ax.spines["bottom"].set_bounds(-0.6, n - 0.5)


# ---------------------------------------------------------------- source data
def write_source_data(*args, **kwargs):
    pass


def main():
    mpl.rcParams.update(PUBLICATION_RC)
    mpl.rcParams.update(secondary_rc(FS_BODY, FS_TICK))
    fam = load_family()
    sus = load_sustained()
    be = load_breakeven()
    audit = load_audit()
    write_source_data(fam, sus, be, audit)

    fig = plt.figure(figsize=(FIG_WIDTH_MM * MM, FIG_HEIGHT_MM * MM))
    gs = gridspec_mm(fig, 2, 2, width_mm=FIG_WIDTH_MM, height_mm=FIG_HEIGHT_MM, left=LEFT,
                     right=RIGHT, top=TOP, bottom=BOTTOM, col_gutter=COL_GUT, row_gutter=ROW_GUT,
                     panel_w=PANEL_W, panel_h_avg=(H_TOP + H_BOTTOM) / 2,
                     height_ratios=[H_TOP, H_BOTTOM])
    ax_a = fig.add_subplot(gs[0, :])
    ax_b = fig.add_subplot(gs[1, 0])
    ax_c = fig.add_subplot(gs[1, 1])
    panel_a(ax_a, fam)
    panel_b(ax_b, sus)
    panel_c(ax_c, be, audit)
    add_panel_label(ax_a, "a", "Recovery read through four estimators", FS_LETTER, FS_BODY)
    add_panel_label(ax_b, "b", "Sustained attainment of a recovery threshold", FS_LETTER, FS_BODY)
    add_panel_label(ax_c, "c", "Recovery that screened-out roads would need", FS_LETTER, FS_BODY)

    QA.mkdir(exist_ok=True)
    report = require_matplotlib_panel_alignment(
        fig, json_out=QA / "fig4_recovery.alignment.json", overlay_svg=QA / "fig4_recovery.alignment.svg",
        tolerance_pt=1.5, gutter_tolerance_pt=1.5, require_panel_labels=True, strict=True)
    fig.savefig(OUT / "fig4_recovery.svg")
    fig.savefig(OUT / "fig4_recovery.pdf")
    # Uncompressed TIFF: the local libtiff build aborts on LZW compression.
    fig.savefig(OUT / "fig4_recovery.tiff", dpi=600)
    fig.savefig(OUT / "fig4_recovery.png", dpi=300)
    plt.close(fig)
    print("alignment:", report.get("verdict"), "| size mm:", FIG_WIDTH_MM, round(FIG_HEIGHT_MM, 1))


if __name__ == "__main__":
    main()
