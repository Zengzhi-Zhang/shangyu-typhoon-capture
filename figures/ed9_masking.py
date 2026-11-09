"""Extended Data Fig. 9 | Error of four handling methods under the missingness mechanisms tested.

a  The real 26 July failure set (163 cameras) masked on eight ordinary days (12-19 July), where the
   observed truth is known: absolute bias of each method by date (zero-filling on its own axis segment)
b  Largest absolute bias over dates for five masking mechanisms and four methods, against the
   pre-set 0.02
c  Early masking on the fixed stable set, 26-30 July: absolute bias of discarding failed cameras under
   random and flow-weighted masking; the 29 July flow-weighted cell, 0.0217, exceeds 0.02

Absolute bias is the absolute value of the mean error over the repetitions of each date (one fixed set
in a; 200 repetitions in c and in the other mechanisms of b); it is not a mean absolute error. The truth
is the observed flow ratio of the evaluation universe, not independent citywide traffic.
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
from matplotlib.patches import Rectangle  # noqa: E402

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
NAME = "ed9_masking"

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
LEFT, RIGHT, TOP, BOTTOM = 14.0, 3.0, 8.0, 15.0
GAP = 1.5
HEIGHTS = [11.0, 0.0, 44.0]                 # a: zero-filling segment, gap, main segment
W_A, W_B, W_C = 42.0, 67.0, 30.0
COL_GUT = (FIG_WIDTH_MM - LEFT - RIGHT - W_A - W_B - W_C) / 2
FIG_HEIGHT_MM = TOP + sum(HEIGHTS) + GAP * (len(HEIGHTS) - 1) + BOTTOM
LIMIT = 0.02

METHODS = [  # key, legend label, column header in b, colour, marker
    ("naive_zero", "Zero filling", "Zero\nfilling", COL["red"], "o"),
    ("drop", "Discarding", "Discard", COL["blue"], "s"),
    ("knn6", "kNN imputation", "kNN", COL["teal"], "^"),
    ("stratum", "Stratified imputation", "Stratified", COL["purple"], "D")]
MECHANISMS = [("real_failure", "Real 26 Jul failure\nset, fixed replay"),
              ("organisation_block", "Management-unit\nblock"),
              ("spatial_block", "Spatial block"),
              ("mnar_low_recovery", "More missing at\nlow recovery"),
              ("mnar_high_recovery", "More missing at\nhigh recovery")]


# ---------------------------------------------------------------- data
def load():
    return (pd.read_csv(SRC / "ed9a_real_failure_set_ordinary_days.csv"),
            pd.read_csv(SRC / "ed9b_applicability_matrix.csv"),
            pd.read_csv(SRC / "ed9c_early_masking_discarding.csv"))


def write_source_data(*args, **kwargs):
    pass


# ---------------------------------------------------------------- panels
def panel_a(ax_hi, ax_lo, r):
    dates = sorted(r["date"].unique())
    x = np.arange(len(dates))
    for method, label, _, col, mk in METHODS:
        d = r[r["method"] == method].set_index("date").loc[dates]
        ax = ax_hi if method == "naive_zero" else ax_lo
        dx = {"naive_zero": 0, "drop": -0.18, "knn6": 0, "stratum": 0.18}[method]
        ax.plot(x + dx, d["abs_bias"], mk, ms=3.2, color=col, mec="white", mew=0.3, ls="none", zorder=3)
    ax_lo.axhline(LIMIT, color=COL["ink"], lw=0.7, ls=(0, (2.2, 1.6)), zorder=1)
    ax_lo.text(len(dates) - 0.5, LIMIT - 0.0006, "0.02", fontsize=FS_NOTE, ha="right", va="top")
    ax_hi.set_ylim(0.17, 0.23)
    ax_hi.set_yticks([0.18, 0.22])
    ax_lo.set_ylim(0, 0.025)
    ax_lo.set_yticks([0, 0.01, 0.02])
    ax_lo.set_yticklabels(["0", "0.01", "0.02"])
    for ax in (ax_hi, ax_lo):
        ax.set_xlim(-0.6, len(dates) - 0.4)
        ax.set_xticks(x)
        outward_spines(ax)
    ax_hi.spines["bottom"].set_visible(False)
    ax_hi.tick_params(axis="x", length=0, labelbottom=False)
    ax_lo.set_xticklabels([str(pd.Timestamp(d).day) for d in dates])
    ax_lo.set_xlabel("Ordinary day masked (July 2021)")
    ax_lo.set_ylabel("Absolute error")       # one fixed replay per date, so error rather than bias
    # Broken-axis marks on the left spine, sized in points.
    for ax, at in ((ax_hi, 0.0), (ax_lo, 1.0)):
        h_pt = ax.get_position().height * ax.figure.get_figheight() * 72
        dy = 1.6 / h_pt
        trans = ax.transAxes + mpl.transforms.ScaledTranslation(-3 / 72, 0, ax.figure.dpi_scale_trans)
        ax.plot([-0.02, 0.02], [at - dy, at + dy], transform=trans, color=COL["ink"], lw=0.6, clip_on=False,
                zorder=6)
    handles = [Line2D([], [], marker=mk, ls="none", ms=3.2, color=col, mec="white", mew=0.3, label=label)
               for _, label, _, col, mk in METHODS]
    ax_lo.legend(handles=handles, loc="upper left", ncol=2, fontsize=FS_NOTE, handletextpad=0.1,
                 columnspacing=0.6, borderaxespad=0.2)
    ax_lo.figure.align_ylabels([ax_hi, ax_lo])


def panel_b(ax, m):
    n_rows, n_cols = len(MECHANISMS), len(METHODS)
    x_cells = 0.34
    w = (1 - x_cells) / n_cols
    for i, (scheme, label) in enumerate(MECHANISMS):
        y = i
        ax.text(0.0, y, label, fontsize=FS_NOTE, ha="left", va="center", linespacing=1.1)
        for j, (method, _, _, _, _) in enumerate(METHODS):
            v = m[(m["scheme"] == scheme) & (m["method"] == method)]["max_abs_bias"].item()
            if method == "naive_zero":
                face, ink = tint(COL["red"], 0.30), COL["ink"]
            elif v > LIMIT:
                face, ink = COL["orange"], COL["ink"]
            else:
                face, ink = tint(COL["blue"], 0.85), "white"
            ax.add_patch(Rectangle((x_cells + j * w + 0.006, y - 0.40), w - 0.012, 0.80, facecolor=face,
                                   edgecolor="none", zorder=1))
            ax.text(x_cells + (j + 0.5) * w, y, f"{v:.3f}", fontsize=FS_NOTE, ha="center", va="center", color=ink,
                    zorder=2)
    for j, (_, _, header, _, _) in enumerate(METHODS):
        ax.text(x_cells + (j + 0.5) * w, -0.6, header, fontsize=FS_NOTE, ha="center", va="bottom", linespacing=1.1)
    ax.set_xlim(0, 1)
    ax.set_ylim(n_rows - 0.4, -1.75)
    ax.axis("off")
    key = [(tint(COL["blue"], 0.85), "≤0.02"), (COL["orange"], ">0.02"), (tint(COL["red"], 0.30), "Zero filling")]
    for k, (face, label) in enumerate(key):
        x0 = x_cells + k * 0.2
        ax.add_patch(Rectangle((x0, n_rows - 0.15), 0.035, 0.32, facecolor=face, edgecolor="none", clip_on=False))
        ax.text(x0 + 0.05, n_rows + 0.01, label, fontsize=FS_NOTE, ha="left", va="center", clip_on=False)


def panel_c(ax, e):
    dates = sorted(e["date"].unique())
    x = np.arange(len(dates))
    styles = {"random": ("Random", tint(COL["blue"], 0.45), "o"), "flowweighted": ("Flow-weighted", COL["blue"], "s")}
    for k, (masking, (label, col, mk)) in enumerate(styles.items()):
        d = e[e["masking"] == masking].set_index("date").loc[dates]
        ax.plot(x + (k - 0.5) * 0.24, d["drop_abs_bias"], mk, ms=3.4, color=col, mec="white", mew=0.3, ls="none",
                zorder=3, label=label)
    ax.axhline(LIMIT, color=COL["ink"], lw=0.7, ls=(0, (2.2, 1.6)), zorder=1)
    k29 = dates.index("2021-07-29")
    v29 = e[(e["masking"] == "flowweighted") & (e["date"] == "2021-07-29")]["drop_abs_bias"].item()
    ax.plot([k29 + 0.12], [v29], "o", ms=7.0, mfc="none", mec=COL["red"], mew=0.8, zorder=4)
    ax.text(k29 + 0.12, v29 + 0.0016, f"{v29:.4f}", fontsize=FS_NOTE, ha="center", va="bottom", color=COL["red"])
    ax.set_xlim(-0.6, len(dates) - 0.4)
    ax.set_xticks(x)
    ax.set_xticklabels([str(pd.Timestamp(d).day) for d in dates])
    ax.set_xlabel("Event day (July 2021)")
    ax.set_ylim(0, 0.03)
    ax.set_yticks([0, 0.01, 0.02, 0.03])
    ax.set_yticklabels(["0", "0.01", "0.02", "0.03"])
    ax.set_ylabel("Absolute bias, discarding")
    ax.legend(loc="upper left", fontsize=FS_NOTE, handletextpad=0.1, borderaxespad=0.2)
    outward_spines(ax)


def main():
    mpl.rcParams.update(PUBLICATION_RC)
    mpl.rcParams.update(secondary_rc(FS_BODY, FS_TICK))
    r, m, e = load()
    write_source_data(r, m, e)

    fig = plt.figure(figsize=(FIG_WIDTH_MM * MM, FIG_HEIGHT_MM * MM))
    gs = fig.add_gridspec(len(HEIGHTS), 3, left=LEFT / FIG_WIDTH_MM, right=1 - RIGHT / FIG_WIDTH_MM,
                          bottom=BOTTOM / FIG_HEIGHT_MM, top=1 - TOP / FIG_HEIGHT_MM,
                          wspace=COL_GUT / np.mean([W_A, W_B, W_C]), hspace=GAP / np.mean(HEIGHTS),
                          width_ratios=[W_A, W_B, W_C], height_ratios=HEIGHTS)
    ax_a1 = fig.add_subplot(gs[0, 0])
    ax_a2 = fig.add_subplot(gs[2, 0])
    ax_a2.set_gid("a-main")
    ax_b = fig.add_subplot(gs[0:3, 1])
    ax_c = fig.add_subplot(gs[0:3, 2])
    panel_a(ax_a1, ax_a2, r)
    panel_b(ax_b, m)
    panel_c(ax_c, e)
    add_panel_label(ax_a1, "a", "Real failure set replayed on ordinary days", FS_LETTER, FS_BODY)
    add_panel_label(ax_b, "b", "Largest absolute bias by mechanism", FS_LETTER, FS_BODY)
    add_panel_label(ax_c, "c", "Random and flow-weighted", FS_LETTER, FS_BODY)

    QA.mkdir(parents=True, exist_ok=True)
    report = require_matplotlib_panel_alignment(
        fig, json_out=QA / f"{NAME}.alignment.json", overlay_svg=QA / f"{NAME}.alignment.svg",
        tolerance_pt=1.5, gutter_tolerance_pt=1.5, require_panel_labels=True, strict=True,
        axes=[ax_a1, ax_b, ax_c],
        exemptions=[{"panels": ["a", "b", "c"], "checks": ["panel-width"],
                     "reason": "unequal widths by design: date panel, labelled matrix, five-date panel"}])
    pair = require_matplotlib_panel_alignment(
        fig, json_out=QA / f"{NAME}.pair.alignment.json", overlay_svg=QA / f"{NAME}.pair.alignment.svg",
        tolerance_pt=1.5, gutter_tolerance_pt=1.5, require_panel_labels=False, strict=True, axes=[ax_a1, ax_a2])
    fig.savefig(OUT / f"{NAME}.svg")
    fig.savefig(OUT / f"{NAME}.pdf")
    # Uncompressed TIFF: the local libtiff build aborts on LZW compression.
    fig.savefig(OUT / f"{NAME}.tiff", dpi=600)
    fig.savefig(OUT / f"{NAME}.png", dpi=300)
    plt.close(fig)
    print("alignment:", report.get("verdict"), "| pair:", pair.get("verdict"),
          "| size mm:", FIG_WIDTH_MM, round(FIG_HEIGHT_MM, 1))


if __name__ == "__main__":
    main()
