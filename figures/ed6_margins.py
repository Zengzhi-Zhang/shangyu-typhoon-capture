"""Extended Data Fig. 6 | The local minus out-of-province difference on both margins, across settings.

a  26 July difference (local minus out-of-province plates) in the ratio of vehicles seen (rP) and in
   records per vehicle (rm) on the fixed stable set, under baselines B1, B2 and B3, excluding
   new-energy vehicles, and with the online set fixed at 26 July; bands are the null envelopes
   (largest absolute difference over 32 reference days)
b  Ratio of vehicles seen before and after correcting for unreadable plates, 25-27 July, by plate group
c  Daily path of the two margins, vehicles seen (rP) against records per vehicle (rm), 25 July to
   2 August, one panel per plate group (moved here from Fig. 5a, 2026-11-08)

Group-level ratios only; no plate counts are written. All rows of the frozen tables are plotted.
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

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
try:
    from audit_panel_alignment import require_matplotlib_panel_alignment
except ImportError:
    def require_matplotlib_panel_alignment(*args, **kwargs):
        return {"verdict": "skipped_optional_QA_unavailable"}
from figstyle import (COL, LABEL_DY_MM, MM, add_panel_label, mm_offset,  # noqa: E402
                      outward_spines, secondary_rc, tint)

ROOT = HERE.parent
OUT = HERE.parent / "outputs" / "figures"
OUT.mkdir(parents=True, exist_ok=True)
SRC = HERE.parent / "source_data"
QA = OUT / "qa"
NAME = "ed6_margins"

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
LEFT, RIGHT, TOP, BOTTOM = 41.0, 3.0, 8.0, 12.0
GAP = 5.0
WIDTHS = [33.0, 33.0, 4.0]           # a (rP), a (rm), spacer; b takes the rest
W_B = FIG_WIDTH_MM - LEFT - RIGHT - sum(WIDTHS) - 3 * GAP
WIDTHS.append(W_B)
H = 55.0
# row 2 (c): three phase panels with equal units on both axes
RP_LIM, RM_LIM = (0.35, 1.14), (0.58, 1.22)
ISO = [0.4, 0.6, 0.8, 1.0]
LEFT2, GAP2, ROW_GAP = 12.0, 6.0, 16.0
W2 = (FIG_WIDTH_MM - LEFT2 - RIGHT - 2 * GAP2) / 3
H2 = W2 * (RM_LIM[1] - RM_LIM[0]) / (RP_LIM[1] - RP_LIM[0])
FIG_HEIGHT_MM = TOP + H + ROW_GAP + H2 + BOTTOM
TRAJ_DATES = pd.date_range("2021-07-25", "2021-08-02").strftime("%Y-%m-%d").tolist()
HALO = [pe.withStroke(linewidth=1.6, foreground="white")]
# "28 Jul†" label: offset from the 28 July point (rP, rm) and alignment, set clear of the contours
LABEL_28 = {"local_zheD": (0.0, 0.016, "center", "bottom"),
            "zhejiang_other": (0.015, 0.0, "left", "center"),
            "other_province": (-0.014, 0.014, "right", "bottom")}

SETTINGS = [
    ("B1", "Baseline B1, 5–21 Jul (main)"),
    ("B2", "Baseline B2, 12–21 Jul"),
    ("B3", "Baseline B3, 17 Jun and 28 Jun–4 Jul"),
    ("exclude_NEV", "Excluding new-energy vehicles"),
    ("S_on", "Online set fixed at 26 Jul"),
]
GROUPS = [("local_zheD", "Local plates", "blue", "o"), ("zhejiang_other", "Other Zhejiang", "teal", "s"),
          ("other_province", "Out of province", "red", "^")]
DATES = ["2021-07-25", "2021-07-26", "2021-07-27"]


# ---------------------------------------------------------------- data
def load_variants():
    v = pd.read_csv(SRC / "ed6a_differences_by_setting.csv")
    e = v.groupby("metric")["null_envelope_half_width"].first()
    return v, e


def load_idcorr():
    return pd.read_csv(SRC / "ed6b_identification_correction.csv")


def load_margins():
    return pd.read_csv(SRC / "ed6c_daily_margins.csv")


def write_source_data(*args, **kwargs):
    pass


# ---------------------------------------------------------------- panels
def panel_a(ax, v, half, metric, xlim, xticks, xlabel, *, labels):
    n = len(SETTINGS)
    ax.axvspan(-half, half, color=tint(COL["bluegrey"], 0.45), lw=0, zorder=0)
    # The zero line stops above the envelope label at the foot of the panel.
    ax.vlines(0, -0.6, n - 0.85, color=COL["bluegrey"], lw=0.8, ls=(0, (3, 2)), zorder=1)
    for k, (key, _) in enumerate(SETTINGS):
        r = v[(v["variant"] == key) & (v["metric"] == metric)].iloc[0]
        ax.hlines(k, r["lo"], r["hi"], color=COL["ink"], lw=1.0, zorder=2)
        ax.plot([r["effect"]], [k], "o", ms=3.4, color=COL["ink"], mec="white", mew=0.4, zorder=3)
    ax.set_ylim(n - 0.4, -0.6)
    ax.set_yticks(range(n))
    if labels:
        ax.set_yticklabels([lab for _, lab in SETTINGS])
    else:
        ax.tick_params(axis="y", labelleft=False)
    ax.tick_params(axis="y", length=0)
    ax.set_xlim(*xlim)
    ax.set_xticks(xticks)
    ax.set_xticklabels([f"{t:.1f}".replace("-", "−") if t else "0" for t in xticks])
    ax.set_xlabel(xlabel)
    ax.spines["left"].set_visible(False)
    outward_spines(ax, left=False)
    ax.text(0, n - 0.48, f"±{half:.4f}", fontsize=FS_NOTE, ha="center", va="bottom", color=COL["ink"])


def panel_b(ax, t):
    x0 = np.arange(len(DATES))
    for k, (grp, label, cname, mk) in enumerate(GROUPS):
        d = t[t["grp"] == grp].set_index("date").loc[DATES]
        x = x0 + (k - 1) * 0.22
        col = COL[cname]
        ax.vlines(x, d["rP"], d["rP_idcorr"], color=col, lw=0.9, zorder=2)
        ax.plot(x, d["rP"], mk, ms=3.6, color=col, mec="white", mew=0.4, ls="none", zorder=3)
        ax.plot(x, d["rP_idcorr"], mk, ms=3.6, mfc="white", mec=col, mew=0.9, ls="none", zorder=3)
        ax.text(x[-1] + 0.14, d["rP"].iloc[-1], label, fontsize=FS_NOTE, ha="left", va="center", color=col)
    ax.set_xlim(-0.5, len(DATES) - 0.5 + 0.75)
    ax.set_xticks(x0)
    ax.set_xticklabels(["25 Jul\n(11–23 h)", "26 Jul", "27 Jul"], linespacing=1.1)
    ax.set_ylim(0.3, 1.0)
    ax.set_yticks([0.4, 0.6, 0.8, 1.0])
    ax.set_ylabel("Ratio of vehicles seen (rP)")
    outward_spines(ax)
    ax.spines["bottom"].set_bounds(-0.5, len(DATES) - 0.5)
    handles = [Line2D([], [], marker="o", ls="none", ms=3.6, color=COL["ink"], mec="white", mew=0.4,
                      label="Observed"),
               Line2D([], [], marker="o", ls="none", ms=3.6, mfc="white", mec=COL["ink"], mew=0.9,
                      label="Corrected for unreadable plates")]
    ax.legend(handles=handles, loc="lower right", fontsize=FS_NOTE, handletextpad=0.2, borderaxespad=0.2)


def panel_c(ax, m, focal, *, ylabels, xlabel):
    """Phase plot for one plate group: contours of rP x rm, the daily path and its direction."""
    for c in ISO:  # only the part of each curve inside the frame, so no path runs off-axes
        x = np.linspace(max(RP_LIM[0], c / RM_LIM[1]), min(RP_LIM[1], c / RM_LIM[0]), 300)
        ax.plot(x, c / x, color=COL["bluegrey"], lw=0.7, ls=(0, (3, 2)), zorder=1)
    for c in ISO:  # labels where each curve leaves the frame
        if c / RP_LIM[1] >= RM_LIM[0]:
            ax.text(RP_LIM[1] - 0.008, c / RP_LIM[1], f"{c:.1f}", fontsize=FS_NOTE, ha="right", va="bottom",
                    zorder=2, path_effects=HALO)
        else:
            ax.text(c / RM_LIM[0] + 0.006, RM_LIM[0] + 0.008, f"{c:.1f}", fontsize=FS_NOTE, ha="left",
                    va="bottom", zorder=2, path_effects=HALO)
    ax.plot([1.0], [1.0], marker="+", ms=6, mew=0.9, color=COL["ink"], zorder=3)  # baseline
    key, label, cname, mk = next(g for g in GROUPS if g[0] == focal)
    col = COL[cname]
    g = m[m["grp"] == key].set_index("date").reindex(TRAJ_DATES)
    xs, ys = g["rP"].to_numpy(), g["rm"].to_numpy()
    ax.plot(xs, ys, color=col, lw=0.9, zorder=4)
    for i in range(3):  # direction of travel on the first three steps
        ax.annotate("", xy=(0.45 * xs[i] + 0.55 * xs[i + 1], 0.45 * ys[i] + 0.55 * ys[i + 1]),
                    xytext=(0.6 * xs[i] + 0.4 * xs[i + 1], 0.6 * ys[i] + 0.4 * ys[i + 1]),
                    arrowprops=dict(arrowstyle="-|>", color=col, lw=0.9, mutation_scale=6,
                                    shrinkA=0, shrinkB=0), zorder=5)
    ax.plot(xs[1:], ys[1:], mk, ms=3.2, color=col, mec="white", mew=0.4, ls="none", zorder=6)
    ax.plot(xs[:1], ys[:1], mk, ms=3.4, mfc="white", mec=col, mew=0.9, ls="none", zorder=6)
    ax.plot(xs[1:2], ys[1:2], mk, ms=4.8, color=col, mec="white", mew=0.5, ls="none", zorder=7)
    dx, dy, ha, va = LABEL_28[key]
    ax.text(xs[3] + dx, ys[3] + dy, "28 Jul†", fontsize=FS_NOTE, ha=ha, va=va, zorder=8, path_effects=HALO)
    ax.set_xlim(*RP_LIM)
    ax.set_ylim(*RM_LIM)
    ax.set_xticks([0.4, 0.6, 0.8, 1.0])
    ax.set_yticks([0.6, 0.8, 1.0, 1.2])
    if not ylabels:
        ax.tick_params(axis="y", labelleft=False)
    else:
        ax.set_ylabel("Records per vehicle, rm")
    if xlabel:
        ax.set_xlabel("Vehicles seen, rP")
    outward_spines(ax)
    return label


def main():
    mpl.rcParams.update(PUBLICATION_RC)
    mpl.rcParams.update(secondary_rc(FS_BODY, FS_TICK))
    v, e = load_variants()
    t = load_idcorr()
    m = load_margins()
    write_source_data(v, e, t, m)

    fig = plt.figure(figsize=(FIG_WIDTH_MM * MM, FIG_HEIGHT_MM * MM))
    gs = fig.add_gridspec(1, 4, left=LEFT / FIG_WIDTH_MM, right=1 - RIGHT / FIG_WIDTH_MM,
                          bottom=(BOTTOM + H2 + ROW_GAP) / FIG_HEIGHT_MM, top=1 - TOP / FIG_HEIGHT_MM,
                          wspace=GAP / np.mean(WIDTHS), width_ratios=WIDTHS)
    gs2 = fig.add_gridspec(1, 3, left=LEFT2 / FIG_WIDTH_MM, right=1 - RIGHT / FIG_WIDTH_MM,
                           bottom=BOTTOM / FIG_HEIGHT_MM, top=(BOTTOM + H2) / FIG_HEIGHT_MM,
                           wspace=GAP2 / W2)
    ax_p = fig.add_subplot(gs[0, 0])
    ax_m = fig.add_subplot(gs[0, 1])
    ax_m.set_gid("a-rm")
    ax_b = fig.add_subplot(gs[0, 3])
    panel_a(ax_p, v, e["rP"], "rP", (-0.2, 0.42), [-0.2, 0, 0.2, 0.4], "ΔrP, vehicles seen", labels=True)
    panel_a(ax_m, v, e["rm"], "rm", (-0.3, 0.2), [-0.2, 0, 0.2], "Δrm, records per vehicle", labels=False)
    panel_b(ax_b, t)
    add_panel_label(ax_p, "a", "Local minus out-of-province, 26 July", FS_LETTER, FS_BODY)
    add_panel_label(ax_b, "b", "Correction for unreadable plates", FS_LETTER, FS_BODY)
    axes_c = [fig.add_subplot(gs2[0, k]) for k in range(3)]
    for k, (ax, (key, *_)) in enumerate(zip(axes_c, GROUPS)):
        ax.set_gid(f"c-{key}")
        label = panel_c(ax, m, key, ylabels=(k == 0), xlabel=(k == 1))
        if k == 0:
            add_panel_label(ax, "c", label, FS_LETTER, FS_BODY)
        else:  # small-multiple headers, set at the plot-area edge
            ax.text(0, 1, label, transform=mm_offset(ax, 0.0, LABEL_DY_MM), fontsize=FS_BODY, ha="left",
                    va="baseline", color=COL["ink"], clip_on=False)

    QA.mkdir(parents=True, exist_ok=True)
    trio = require_matplotlib_panel_alignment(
        fig, json_out=QA / f"{NAME}.c.alignment.json", overlay_svg=QA / f"{NAME}.c.alignment.svg",
        tolerance_pt=1.5, gutter_tolerance_pt=1.5, require_panel_labels=False, strict=True, axes=axes_c)
    report = require_matplotlib_panel_alignment(
        fig, json_out=QA / f"{NAME}.alignment.json", overlay_svg=QA / f"{NAME}.alignment.svg",
        tolerance_pt=1.5, gutter_tolerance_pt=1.5, require_panel_labels=True, strict=True, axes=[ax_p, ax_b])
    pair = require_matplotlib_panel_alignment(
        fig, json_out=QA / f"{NAME}.pair.alignment.json", overlay_svg=QA / f"{NAME}.pair.alignment.svg",
        tolerance_pt=1.5, gutter_tolerance_pt=1.5, require_panel_labels=False, strict=True, axes=[ax_p, ax_m])
    fig.savefig(OUT / f"{NAME}.svg")
    fig.savefig(OUT / f"{NAME}.pdf")
    # Uncompressed TIFF: the local libtiff build aborts on LZW compression.
    fig.savefig(OUT / f"{NAME}.tiff", dpi=600)
    fig.savefig(OUT / f"{NAME}.png", dpi=300)
    plt.close(fig)
    print("alignment:", report.get("verdict"), "| pair:", pair.get("verdict"), "| c:", trio.get("verdict"),
          "| size mm:", FIG_WIDTH_MM, round(FIG_HEIGHT_MM, 1))


if __name__ == "__main__":
    main()
