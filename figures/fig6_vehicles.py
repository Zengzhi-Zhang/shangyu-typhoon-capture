"""Fig. 5 | Vehicle-group patterns once observation conditions are made explicit.

a  Two margins on the fixed stable set: vehicles seen (rP) against records per vehicle (rm),
   daily trajectories 25 July to 2 August for local, other-Zhejiang and other-province plates
b  Local minus other-province difference in rP, against the null envelope of 32 reference days
c  The same for rm
d  Regular-vehicle cohorts (seen on at least 8 of 10 days): presence deficit against a
   lagged, matched placebo window
e  First day the deficit falls to 0.05 or below, for cohort thresholds of 6, 8 and 9 days

All rows of the frozen tables for these groups and days are plotted; no rows are dropped.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib as mpl

mpl.use("Agg")
import matplotlib.patheffects as pe  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
try:
    from audit_panel_alignment import require_matplotlib_panel_alignment
except ImportError:
    def require_matplotlib_panel_alignment(*args, **kwargs):
        return {"verdict": "skipped_optional_QA_unavailable"}
from figstyle import COL, MM, add_panel_label, gridspec_mm, outward_spines, secondary_rc, tint  # noqa: E402

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
COL_GUT, ROW_GUT = 20.0, 14.0
PANEL_W = (FIG_WIDTH_MM - LEFT - RIGHT - COL_GUT) / 2
H_B, H_C, H_D = 25.0, 25.0, 40.0
FIG_HEIGHT_MM = TOP + H_B + H_C + H_D + 2 * ROW_GUT + BOTTOM
LINESPACING = 1.2
HALO = [pe.withStroke(linewidth=1.6, foreground="white")]

DATES = pd.date_range("2021-07-25", "2021-08-02").strftime("%Y-%m-%d").tolist()
DAY_LABELS = ["25", "26", "27", "28†", "29", "30", "31", "1", "2"]
GROUPS = [  # key, label, colour, marker
    ("local_zheD", "Local plates", "blue", "o"),
    ("zhejiang_other", "Other Zhejiang", "teal", "s"),
    ("other_province", "Out of province", "red", "^"),
]
# panel a: two date blocks of three group rows; the left of the axes carries the row labels
A_BLOCKS = [("2021-07-26", "26 Jul", [6.1, 5.1, 4.1], 6.95),   # date, header, row y, header y
            ("2021-08-02", "2 Aug", [2.1, 1.1, 0.1], 2.95)]
A_XLIM, A_DATA, A_YLIM = (0.12, 1.12), (0.4, 1.1), (-0.5, 8.0)
A_LABEL_X = 0.135
THRESHOLDS = [6, 8, 9]


# ---------------------------------------------------------------- data
def load_margins():
    return pd.read_csv(SRC / "fig6a_two_margins.csv")


def load_envelope():
    return pd.read_csv(SRC / "fig6bc_local_minus_other_province.csv")


def load_cohorts():
    gaps = pd.read_csv(SRC / "fig6d_cohort_deficit_thr8.csv").assign(thr=8)
    p = pd.read_csv(SRC / "fig6e_first_day_by_threshold.csv")
    first = p.pivot(index="threshold_days",columns="group",values="first_day_k")
    sizes = p.pivot(index="group",columns="threshold_days",values="cohort_size")
    return gaps, first, sizes


# ---------------------------------------------------------------- panel a
def panel_a(ax, m):
    """Paired points per plate group on 26 July and 2 August: vehicles seen (filled), records per
    vehicle (open) and the record ratio (bar). Daily paths from 25 July are in Extended Data Fig. 6c."""
    ax.vlines(1.0, A_YLIM[0] + 0.1, A_BLOCKS[0][3] - 0.25, color=COL["bluegrey"], lw=0.8,
              ls=(0, (3, 2)), zorder=0)
    for date, head, ys, yh in A_BLOCKS:
        ax.text(A_LABEL_X, yh, head, fontsize=FS_TICK, fontweight="bold", ha="left", va="center")
        day = m[m["date"] == date].set_index("grp")
        assert (day["hour_matched"] == 0).all()
        for (key, label, cname, mk), y in zip(GROUPS, ys):
            r = day.loc[key]
            col = COL[cname]
            ax.text(A_LABEL_X, y, label, fontsize=FS_TICK, ha="left", va="center")
            ax.hlines(y, A_DATA[0], A_DATA[1], color=tint(COL["bluegrey"], 0.45), lw=0.5, zorder=0)
            ax.hlines(y, min(r["rP"], r["rm"]), max(r["rP"], r["rm"]), color=tint(col, 0.5), lw=1.6,
                      zorder=1)
            for lo, hi in ((r["ci_rP_lo"], r["ci_rP_hi"]), (r["ci_rm_lo"], r["ci_rm_hi"])):
                ax.hlines(y, lo, hi, color=col, lw=0.8, zorder=2)
            ax.plot([r["rN"]], [y], "|", ms=7.0, mew=1.2, color=COL["ink"], zorder=3)
            ax.plot([r["rP"]], [y], mk, ms=4.2, color=col, mec="white", mew=0.4, zorder=4)
            ax.plot([r["rm"]], [y], mk, ms=4.2, mfc="white", mec=col, mew=0.9, zorder=4)
            if date == "2021-07-26":
                ax.text(r["rN"], y + 0.30, f"{r['rN']:.2f}", fontsize=FS_NOTE, ha="center", va="bottom")
    handles = [Line2D([], [], ls="none", marker="o", ms=4.2, color=COL["ink"], mec="white", mew=0.4,
                      label="Vehicles seen, rP"),
               Line2D([], [], ls="none", marker="o", ms=4.2, mfc="white", mec=COL["ink"], mew=0.9,
                      label="Records per vehicle, rm"),
               Line2D([], [], ls="none", marker="|", ms=7.0, mew=1.2, color=COL["ink"],
                      label="Record ratio, rN")]
    ax.legend(handles=handles, loc="upper right", fontsize=FS_NOTE, handlelength=1.0, borderaxespad=0.0)
    ax.set_xlim(*A_XLIM)
    ax.set_ylim(*A_YLIM)
    ax.set_xticks([0.4, 0.6, 0.8, 1.0])
    ax.spines["bottom"].set_bounds(*A_DATA)
    ax.set_xlabel("Ratio to baseline")
    ax.xaxis.label.set_x((np.mean(A_DATA) - A_XLIM[0]) / (A_XLIM[1] - A_XLIM[0]))
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    outward_spines(ax, left=False)
    # the two out-of-town groups share a record ratio on 26 July but differ in their margins
    d26 = m[m["date"] == "2021-07-26"].set_index("grp")
    assert round(d26.loc["zhejiang_other", "rN"], 2) == round(d26.loc["other_province", "rN"], 2) == 0.46


# ---------------------------------------------------------------- panels b and c
def panel_delta(ax, env, metric, ylim, yticks, show_x):
    e = env[env["metric"] == metric].set_index("date").reindex(DATES)
    x = np.arange(len(DATES))
    half = float(e["null_max_abs"].iloc[0])
    ax.axhspan(-half, half, color=tint(COL["bluegrey"], 0.45), lw=0, zorder=0)
    ax.axhline(0, color=COL["bluegrey"], lw=0.8, ls=(0, (3, 2)), zorder=1)
    ax.vlines(x, e["delta_typhoon_lo"], e["delta_typhoon_hi"], color=COL["ink"], lw=0.8, zorder=2)
    ax.plot(x, e["delta_typhoon"], color=COL["ink"], lw=0.8, zorder=2)
    outside = e["outside_envelope"].to_numpy(bool)
    first = np.arange(len(DATES)) == 0
    ax.plot(x[outside & ~first], e["delta_typhoon"].to_numpy()[outside & ~first], "o", ms=3.4, color=COL["ink"],
            mec="white", mew=0.4, ls="none", zorder=3)
    ax.plot(x[~outside], e["delta_typhoon"].to_numpy()[~outside], "o", ms=3.4, mfc=tint(COL["ink"], 0.3),
            mec=COL["ink"], mew=0.6, ls="none", zorder=3)
    ax.plot(x[first], e["delta_typhoon"].to_numpy()[first], "o", ms=3.4, mfc="white", mec=COL["ink"], mew=0.9,
            ls="none", zorder=3)
    ax.text(len(DATES) - 0.6, half, f"Null envelope ±{half:.2f}", fontsize=FS_NOTE, ha="right", va="bottom",
            path_effects=HALO, zorder=4)
    ax.set_xlim(-0.5, len(DATES) - 0.5)
    ax.set_ylim(*ylim)
    ax.set_yticks(yticks)
    ax.set_yticklabels([f"{v:g}".replace("-", "−") for v in yticks])
    ax.set_xticks(x)
    ax.set_xticklabels(DAY_LABELS if show_x else [])
    if show_x:
        ax.set_xlabel("July–August 2021")
    ax.set_ylabel(f"Δ{metric}")
    outward_spines(ax)
    return e


# ---------------------------------------------------------------- panels d and e
def panel_d(ax, gaps, first):
    x = np.arange(len(DATES))
    ax.axhline(0.05, color=COL["ink"], lw=0.6, ls=(0, (3, 2)), zorder=1)
    ax.text(len(DATES) - 0.6, 0.06, "0.05", fontsize=FS_NOTE, ha="right", va="bottom", zorder=4,
            path_effects=HALO)
    ax.axhline(0, color=COL["bluegrey"], lw=0.6, zorder=0)
    for key, label, cname, mk in GROUPS:
        col = COL[cname]
        g = gaps[(gaps["thr"] == 8) & (gaps["grp"] == key)].sort_values("k")
        ax.vlines(x, g["deficit_lo"], g["deficit_hi"], color=col, lw=0.8, zorder=2)
        ax.plot(x, g["deficit"], color=col, lw=1.1, zorder=2)
        ax.plot(x[1:], g["deficit"].to_numpy()[1:], mk, ms=3.2, color=col, mec="white", mew=0.4, ls="none", zorder=3)
        ax.plot(x[:1], g["deficit"].to_numpy()[:1], mk, ms=3.4, mfc="white", mec=col, mew=0.9, ls="none", zorder=3)
        k = int(first.loc[8, key]) - 1
        ax.plot([x[k]], [g["deficit"].to_numpy()[k]], "o", ms=8.0, mfc="none", mec=col, mew=0.9, zorder=4)
    ax.set_xlim(-0.5, len(DATES) - 0.5)
    ax.set_ylim(-0.04, 0.52)
    ax.set_yticks([0, 0.1, 0.2, 0.3, 0.4, 0.5])
    ax.set_xticks(x)
    ax.set_xticklabels(DAY_LABELS)
    ax.set_xlabel("July–August 2021")
    ax.set_ylabel("Presence deficit vs placebo")
    handles = [Line2D([], [], color=COL[c], marker=mk, ms=3.2, mec="white", mew=0.4, lw=1.1, label=lab)
               for _, lab, c, mk in GROUPS]
    handles.append(Line2D([], [], ls="none", marker="o", ms=8.0, mfc="none", mec=COL["ink"], mew=0.9,
                          label="First day ≤0.05"))
    ax.legend(handles=handles, loc="upper right", fontsize=FS_NOTE, handlelength=1.6)
    outward_spines(ax)


def panel_e(ax, first, sizes):
    n = len(GROUPS)
    for r, (key, label, cname, _) in enumerate(GROUPS):
        y = n - 1 - r
        ax.text(-0.62, y + 0.12, label, fontsize=FS_NOTE, ha="left", va="bottom")
        ax.text(-0.62, y - 0.10, f"n = {int(sizes.loc[key, 8]):,} (≥8)", fontsize=FS_NOTE, ha="left", va="top",
                color=COL["ink"])
        for j, thr in enumerate(THRESHOLDS):
            k = int(first.loc[thr, key])
            date = pd.Timestamp(DATES[k - 1])
            ax.add_patch(Rectangle((j + 0.62, y - 0.36), 0.92, 0.72, facecolor=tint(COL[cname], 0.55 if thr == 8 else 0.25),
                                   edgecolor="none", zorder=1))
            ax.text(j + 1.08, y, f"{date.day} {date.strftime('%b')}", fontsize=FS_NOTE, ha="center",
                    va="center", zorder=2)
    ax.set_xlim(-0.65, len(THRESHOLDS) + 0.58)
    ax.set_ylim(-0.6, n - 0.25)
    ax.set_xticks([j + 1.08 for j in range(len(THRESHOLDS))])
    ax.set_xticklabels([f"≥{t} of 10" for t in THRESHOLDS])
    ax.tick_params(axis="x", length=0)
    ax.set_xlabel("Regular-cohort threshold (days seen)")
    ax.set_yticks([])
    for side in ("left", "bottom"):
        ax.spines[side].set_visible(False)


# ---------------------------------------------------------------- source data
def write_source_data(*args, **kwargs):
    pass


def main():
    mpl.rcParams.update(PUBLICATION_RC)
    mpl.rcParams.update(secondary_rc(FS_BODY, FS_TICK))
    m = load_margins()
    env = load_envelope()
    gaps, first, sizes = load_cohorts()
    write_source_data(m, env, gaps, first, sizes)

    fig = plt.figure(figsize=(FIG_WIDTH_MM * MM, FIG_HEIGHT_MM * MM))
    gs = gridspec_mm(fig, 3, 2, width_mm=FIG_WIDTH_MM, height_mm=FIG_HEIGHT_MM, left=LEFT, right=RIGHT,
                     top=TOP, bottom=BOTTOM, col_gutter=COL_GUT, row_gutter=ROW_GUT, panel_w=PANEL_W,
                     panel_h_avg=(H_B + H_C + H_D) / 3, height_ratios=[H_B, H_C, H_D])
    ax_a = fig.add_subplot(gs[0:2, 0])
    ax_b = fig.add_subplot(gs[0, 1])
    ax_c = fig.add_subplot(gs[1, 1])
    ax_d = fig.add_subplot(gs[2, 0])
    ax_e = fig.add_subplot(gs[2, 1])
    panel_a(ax_a, m)
    panel_delta(ax_b, env, "rP", (-0.2, 0.42), [-0.2, 0, 0.2, 0.4], show_x=False)
    panel_delta(ax_c, env, "rm", (-0.3, 0.2), [-0.2, 0, 0.2], show_x=True)
    panel_d(ax_d, gaps, first)
    panel_e(ax_e, first, sizes)
    add_panel_label(ax_a, "a", "Two margins by plate group", FS_LETTER, FS_BODY)
    add_panel_label(ax_b, "b", "Vehicles seen: local minus out-of-province", FS_LETTER, FS_BODY)
    add_panel_label(ax_c, "c", "Records per vehicle: local minus out-of-province", FS_LETTER, FS_BODY)
    add_panel_label(ax_d, "d", "Regular-vehicle cohorts (seen ≥8 of 10 days)", FS_LETTER, FS_BODY)
    add_panel_label(ax_e, "e", "First day with deficit ≤0.05", FS_LETTER, FS_BODY)

    QA.mkdir(exist_ok=True)
    report = require_matplotlib_panel_alignment(
        fig, json_out=QA / "fig6_vehicles.alignment.json", overlay_svg=QA / "fig6_vehicles.alignment.svg",
        tolerance_pt=1.5, gutter_tolerance_pt=1.5, require_panel_labels=True, strict=True)
    fig.savefig(OUT / "fig6_vehicles.svg")
    fig.savefig(OUT / "fig6_vehicles.pdf")
    # Uncompressed TIFF: the local libtiff build aborts on LZW compression.
    fig.savefig(OUT / "fig6_vehicles.tiff", dpi=600)
    fig.savefig(OUT / "fig6_vehicles.png", dpi=300)
    plt.close(fig)
    print("alignment:", report.get("verdict"), "| size mm:", FIG_WIDTH_MM, round(FIG_HEIGHT_MM, 1))


if __name__ == "__main__":
    main()
