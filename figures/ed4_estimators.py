"""Extended Data Fig. 4 | The eight estimators day by day, and a Wednesday-baseline variant.

a  Daily values and 95% intervals of the eight estimators in Table 1, 25 July to 2 August
   (probe-corrected ratio to 31 July, when the taxi data end); the health-screened ratio is repeated
   as a grey reference line in every other panel
b  28 July under the frozen baseline B1 (Wednesdays 7, 14 and 21 July) and the Wednesday variant B1w
   (14 July only)
c  Sustained attainment of illustrative thresholds under B1w, in the format of Fig. 4b

All rows of the frozen tables are plotted; no rows are dropped.
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
from figstyle import COL, MM, add_panel_label, outward_spines, secondary_rc  # noqa: E402

ROOT = HERE.parent
OUT = HERE.parent / "outputs" / "figures"
OUT.mkdir(parents=True, exist_ok=True)
SRC = HERE.parent / "source_data"
QA = OUT / "qa"
NAME = "ed4_estimators"

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
LEFT, RIGHT, TOP, BOTTOM = 14.0, 3.0, 8.0, 10.0
COL_GUT = 9.5
W_SMALL = (FIG_WIDTH_MM - LEFT - RIGHT - 3 * COL_GUT) / 4
GAP = 4.0
H_SMALL, ROW_GUT, H_BC = 27.0, 16.0, 58.0
COL_GUT_BC = 19.0                           # b-c gutter carries the short row names of c
W_BC = (FIG_WIDTH_MM - LEFT - RIGHT - COL_GUT_BC) / 2
FIG_HEIGHT_MM = TOP + 2 * H_SMALL + GAP + ROW_GUT + H_BC + BOTTOM

DATES = pd.date_range("2021-07-25", "2021-08-02").strftime("%Y-%m-%d").tolist()
DAY_LABELS = ["25", "26", "27", "28", "29", "30", "31", "1", "2"]
FAMILY = [  # Table 1 order; the first four labels and colours as in Fig. 4a
    ("R_naive", "All cameras (record ratio)", "red"),
    ("R_health", "Health-screened", "blue"),
    ("R_online", "Online set", "teal"),
    ("R_stable", "Fixed stable set", "orange"),
    ("R_health_strict", "Strict health-screened", "purple"),
    ("R_spre_health", "Pre-event set, health-screened", "purple"),
    ("R_upper", "Neighbour-imputation scenario", "purple"),
    ("R_probe", "Probe-corrected‡", "purple"),
]
THETAS = [0.80, 0.85, 0.90, 0.95]


# ---------------------------------------------------------------- data
def load_family():
    return pd.read_csv(SRC / "ed4a_estimator_family_daily.csv")


def load_wednesday():
    w = pd.read_csv(SRC / "ed4b_28jul_baseline_variant.csv")
    delta = w.groupby("estimator")["B1w_minus_B1_pp"].first()
    return w, delta


def load_sustained(baseline):
    p = pd.read_csv(SRC / "ed4c_sustained_B1w_vs_B1.csv")
    return p.set_index(["estimator","theta"])[["point_"+baseline,"lower_"+baseline]].rename(columns={"point_"+baseline:"sustained_point","lower_"+baseline:"sustained_lower_ci"})


def cell_status(sus, est, theta):
    """Same classes as Fig. 4b: "both" when point estimate and daily lower bound are each sustained
    within the window (start dates may differ), "point" when only the point estimate is, else "none"."""
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


def compare_matrices(b1, b1w):
    rows = []
    for est, label, _ in FAMILY:
        for theta in THETAS:
            c1 = cell_status(b1, est, theta)
            c2 = cell_status(b1w, est, theta)
            rows.append(dict(estimator=est, label=label.rstrip("‡"), theta=theta, class_B1=c1[0],
                             point_B1=c1[1], lower_B1=c1[2], class_B1w=c2[0], point_B1w=c2[1],
                             lower_B1w=c2[2], identical=c1 == c2))
    return pd.DataFrame(rows)


def write_source_data(*args, **kwargs):
    pass


# ---------------------------------------------------------------- panels
def small_multiple(ax, fam, est, label, cname, *, show_x, show_y):
    x = np.arange(len(DATES))
    ref = fam[fam["estimator"] == "R_health"].set_index("date").reindex(DATES)
    ax.hlines(1.0, -0.5, len(DATES) - 0.5, color=COL["bluegrey"], lw=0.7, ls=(0, (3, 2)), zorder=0)
    if est != "R_health":
        ax.plot(x, ref["R"], color=COL["bluegrey"], lw=1.1, zorder=1)
    s = fam[fam["estimator"] == est].set_index("date").reindex(DATES)
    col = COL[cname]
    ok = s["R"].notna().to_numpy()
    ax.vlines(x[ok], s["ci_lo"][ok], s["ci_hi"][ok], color=col, lw=0.8, zorder=2)
    ax.plot(x[ok], s["R"][ok], color=col, lw=1.0, zorder=3)
    ax.plot(x[1:][ok[1:]], s["R"].to_numpy()[1:][ok[1:]], "o", ms=2.8, color=col, mec="white", mew=0.3,
            ls="none", zorder=4)
    ax.plot(x[:1], s["R"].to_numpy()[:1], "o", ms=2.8, mfc="white", mec=col, mew=0.8, ls="none", zorder=4)
    # The name sits in a band above every series (data and intervals stay below 1.10); the
    # health-screened panel also keys the grey reference line repeated in the other seven.
    if est == "R_health":
        label = f"{label}\n(grey line in the other panels)"
    ax.text(0.04, 0.97, label, transform=ax.transAxes, fontsize=FS_NOTE, ha="left", va="top", zorder=5,
            linespacing=1.2)
    ax.set_xlim(-0.6, len(DATES) - 0.4)
    ax.set_ylim(0.3, 1.36)
    ax.set_yticks([0.4, 0.6, 0.8, 1.0])
    ax.set_xticks(x)
    if show_x:
        ax.set_xticklabels(DAY_LABELS, fontsize=FS_NOTE)
    else:
        ax.tick_params(axis="x", labelbottom=False)
    if not show_y:
        ax.tick_params(axis="y", labelleft=False)
    outward_spines(ax, pts=2.0)


def panel_b(ax, w, delta):
    n = len(FAMILY)
    for k, (est, label, cname) in enumerate(FAMILY):
        y = n - 1 - k
        col = COL[cname]
        # Reference lines are drawn row by row so that they stop below each row label.
        ax.vlines([0.90, 0.95], y - 0.34, y + 0.26, color=COL["bluegrey"], lw=0.6, ls=(0, (1, 1.5)), zorder=0)
        ax.vlines(1.0, y - 0.34, y + 0.26, color=COL["bluegrey"], lw=0.8, ls=(0, (3, 2)), zorder=0)
        for base, dy, filled in (("B1", 0.13, True), ("B1w", -0.13, False)):
            r = w[(w["estimator"] == est) & (w["baseline"] == base)].iloc[0]
            ax.add_line(Line2D([r["ci_lo"], r["ci_hi"]], [y + dy, y + dy], color=col, lw=0.9, zorder=2))
            ax.plot([r["value"]], [y + dy], "o", ms=3.6, mfc=col if filled else "white", mec=col, mew=0.9, zorder=3)
        ax.text(0.865, y + 0.30, label, fontsize=FS_NOTE, ha="left", va="bottom")
    handles = [Line2D([], [], ls="none", marker="o", ms=3.6, color=COL["ink"], label="B1 (7, 14, 21 Jul)"),
               Line2D([], [], ls="none", marker="o", ms=3.6, mfc="white", mec=COL["ink"], mew=0.9,
                      label="B1w (14 Jul only)")]
    ax.legend(handles=handles, loc="upper right", ncol=2, fontsize=FS_NOTE, handlelength=0.8,
              columnspacing=0.9, borderaxespad=0.0, bbox_to_anchor=(1.0, 1.0))
    ax.set_xlim(0.865, 1.12)
    ax.set_ylim(-0.6, n + 1.25)
    ax.set_xticks([0.90, 0.95, 1.00, 1.05, 1.10])
    ax.set_xticklabels(["0.90", "0.95", "1.00", "1.05", "1.10"])
    ax.set_xlabel("Recovery ratio on 28 July")
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    outward_spines(ax, left=False)


ROW_SHORT = {"R_naive": "All cameras", "R_health": "Health-screened", "R_online": "Online set",
             "R_stable": "Fixed stable set", "R_health_strict": "Strict health", "R_spre_health": "Pre-event set",
             "R_upper": "Imputation", "R_probe": "Probe-corrected‡"}


def panel_c(ax, sus, n_identical):
    n = len(FAMILY)
    fills = {"both": COL["blue"], "point": COL["bluegrey"], "none": COL["panel"]}
    inks = {"both": "white", "point": COL["ink"], "none": COL["ink"]}
    edges = {"both": "none", "point": "none", "none": COL["bluegrey"]}
    short = lambda iso: f"{pd.Timestamp(iso).day} {pd.Timestamp(iso).strftime('%b')}"
    for k, (est, _, _) in enumerate(FAMILY):
        y = n - 1 - k
        ax.text(-0.6, y, ROW_SHORT[est], fontsize=FS_NOTE, ha="right", va="center", clip_on=False)
        for j, theta in enumerate(THETAS):
            status, point, lower = cell_status(sus, est, theta)
            ax.add_patch(Rectangle((j - 0.46, y - 0.42), 0.92, 0.84, facecolor=fills[status],
                                   edgecolor=edges[status], lw=0.5, zorder=1))
            if point is None:
                continue
            if lower is not None and lower != point:
                for dy, text in ((0.19, f"Point {short(point)}"), (-0.19, f"Lower {short(lower)}")):
                    ax.text(j, y + dy, text, fontsize=FS_NOTE, ha="center", va="center", color=inks[status],
                            zorder=2)
            else:
                ax.text(j, y, short(point), fontsize=FS_NOTE, ha="center", va="center", color=inks[status],
                        zorder=2)
    handles = [Patch(facecolor=fills[s], edgecolor=edges[s], lw=0.5, label=lab)
               for s, lab in (("both", "Point and lower bound"), ("point", "Point only"),
                              ("none", "Not sustained in window"))]
    ax.legend(handles=handles, loc="upper left", ncol=3, fontsize=FS_NOTE, handlelength=1.0, handleheight=0.8,
              columnspacing=1.0, borderaxespad=0.0, bbox_to_anchor=(0.0, 1.0))
    ax.text(-0.46, n + 0.45, "Start date of sustained attainment; window ends 2 Aug (31 Jul for the probe)",
            fontsize=FS_NOTE, ha="left", va="center")
    ax.text(-0.46, n - 0.05, f"{n_identical} of {n * len(THETAS)} cells identical to Fig. 4b (baseline B1)",
            fontsize=FS_NOTE, ha="left", va="center")
    ax.set_xlim(-0.55, len(THETAS) - 0.45)
    ax.set_ylim(-0.6, n + 1.25)
    ax.set_xticks(range(len(THETAS)))
    ax.set_xticklabels([f"{t:.2f}" for t in THETAS])
    ax.tick_params(axis="x", length=0)
    ax.set_xlabel("Illustrative threshold θ")
    ax.set_yticks([])
    for side in ("left", "bottom"):
        ax.spines[side].set_visible(False)


def main():
    mpl.rcParams.update(PUBLICATION_RC)
    mpl.rcParams.update(secondary_rc(FS_BODY, FS_TICK))
    fam = load_family()
    w, delta = load_wednesday()
    b1, b1w = load_sustained("B1"), load_sustained("B1w")
    cmp_ = compare_matrices(b1, b1w)
    write_source_data(fam, w, delta, cmp_)

    fig = plt.figure(figsize=(FIG_WIDTH_MM * MM, FIG_HEIGHT_MM * MM))
    a_bottom = TOP + 2 * H_SMALL + GAP
    gs = fig.add_gridspec(2, 4, left=LEFT / FIG_WIDTH_MM, right=1 - RIGHT / FIG_WIDTH_MM,
                          bottom=1 - a_bottom / FIG_HEIGHT_MM, top=1 - TOP / FIG_HEIGHT_MM,
                          wspace=COL_GUT / W_SMALL, hspace=GAP / H_SMALL)
    # b and c sit on their own grid so that their gutter can be wider than the small-multiple gutters.
    gs_bc = fig.add_gridspec(1, 2, left=LEFT / FIG_WIDTH_MM, right=1 - RIGHT / FIG_WIDTH_MM,
                             bottom=BOTTOM / FIG_HEIGHT_MM, top=1 - (a_bottom + ROW_GUT) / FIG_HEIGHT_MM,
                             wspace=COL_GUT_BC / W_BC)
    smalls = []
    for k, (est, label, cname) in enumerate(FAMILY):
        r, c = divmod(k, 4)
        ax = fig.add_subplot(gs[r, c])
        ax.set_gid(f"a-{est}")
        small_multiple(ax, fam, est, label, cname, show_x=(r == 1), show_y=True)
        smalls.append(ax)
    smalls[0].set_gid("a")
    ax_b = fig.add_subplot(gs_bc[0, 0])
    ax_c = fig.add_subplot(gs_bc[0, 1])
    panel_b(ax_b, w, delta)
    panel_c(ax_c, b1w, int(cmp_["identical"].sum()))
    smalls[0].set_ylabel("Recovery ratio")
    smalls[4].set_ylabel("Recovery ratio")
    add_panel_label(smalls[0], "a", "Daily values of the eight estimators, 25 July – 2 August", FS_LETTER, FS_BODY)
    add_panel_label(ax_b, "b", "28 July under two Wednesday baselines", FS_LETTER, FS_BODY)
    add_panel_label(ax_c, "c", "Sustained attainment under B1w", FS_LETTER, FS_BODY)

    QA.mkdir(parents=True, exist_ok=True)
    report = require_matplotlib_panel_alignment(
        fig, json_out=QA / f"{NAME}.alignment.json", overlay_svg=QA / f"{NAME}.alignment.svg",
        tolerance_pt=1.5, gutter_tolerance_pt=1.5, require_panel_labels=True, strict=True,
        axes=[smalls[0], ax_b, ax_c])
    grid = require_matplotlib_panel_alignment(
        fig, json_out=QA / f"{NAME}.grid.alignment.json", overlay_svg=QA / f"{NAME}.grid.alignment.svg",
        tolerance_pt=1.5, gutter_tolerance_pt=1.5, require_panel_labels=False, strict=True, axes=smalls)
    fig.savefig(OUT / f"{NAME}.svg")
    fig.savefig(OUT / f"{NAME}.pdf")
    # Uncompressed TIFF: the local libtiff build aborts on LZW compression.
    fig.savefig(OUT / f"{NAME}.tiff", dpi=600)
    fig.savefig(OUT / f"{NAME}.png", dpi=300)
    plt.close(fig)
    print("alignment:", report.get("verdict"), "| grid:", grid.get("verdict"),
          "| identical cells:", int(cmp_["identical"].sum()), "| size mm:", FIG_WIDTH_MM, round(FIG_HEIGHT_MM, 1))


if __name__ == "__main__":
    main()
