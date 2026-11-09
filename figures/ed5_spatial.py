"""Extended Data Fig. 5 | Coverage of the spatial analysis and all regression coefficients.

a  Health-screened cameras on 26 July with and without coordinates: share of cameras and of baseline
   flow, and the recovery ratio of each group (coverage statement only)
b  Cameras and baseline records per distance ring from Baiguan, health-screened set and fixed stable set
c  All coefficients of the 26 July model on the health-screened set (log recovery ratio, HC1 95% intervals)
d  The same model on the fixed stable set and on all cameras with failed cameras entered at the floor

Elevation and relief coefficients are rescaled to per 100 m and per 10 m (exact linear rescaling).
Management units are anonymised (letters as in Extended Data Fig. 3). All rows of the frozen tables
are plotted except the intercepts, which are written to the source data.
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
from figstyle import COL, MM, add_panel_label, outward_spines, secondary_rc, tint  # noqa: E402
from ed_common import unit_letters  # noqa: E402

ROOT = HERE.parent
OUT = HERE.parent / "outputs" / "figures"
OUT.mkdir(parents=True, exist_ok=True)
SRC = HERE.parent / "source_data"
QA = OUT / "qa"
NAME = "ed5_spatial"

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
LEFT, RIGHT, TOP, BOTTOM = 47.0, 3.0, 8.0, 15.0
COL_GUT = 15.0
W = (FIG_WIDTH_MM - LEFT - RIGHT - COL_GUT) / 2
GAP = 1.5
HEIGHTS = [17.0, 0.0, 17.0, 12.0, 84.0]        # b tracks (a spans both), spacer, c and d
FIG_HEIGHT_MM = TOP + sum(HEIGHTS) + GAP * (len(HEIGHTS) - 1) + BOTTOM

DATE = "2021-07-26"
RINGS = ["0-2", "2-4", "4-7", "7-12", "12+"]
SETS = {"health": ("Health-screened", COL["blue"]), "stable": ("Fixed stable set", COL["orange"])}
MODELS = {"R_health": ("Health-screened", COL["blue"]), "Sstar": ("Fixed stable set", COL["orange"]),
          "A100_floor": ("All cameras, failed at floor", COL["red"])}
SCALE = {"elev_m": 100.0, "relief_300m": 10.0}

# Display rows: (term in the frozen tables, label); None marks a group heading.
ROAD = [("primary", "Primary"), ("secondary", "Secondary"), ("tertiary", "Tertiary"),
        ("residential/service", "Residential or service"), ("unclassified/other", "Unclassified or other"),
        ("no_road_within_80m", "No road within 80 m")]


def term_rows():
    rows = [("np.log1p(dist_baiguan_km)", "Distance to Baiguan, log(1 + km)"),
            ("log_base", "Baseline flow, log"),
            ("elev_m", "Elevation (per 100 m)"),
            ("relief_300m", "Local relief, ~300 m (per 10 m)"),
            ("gateway", "Expressway or national-highway camera"),
            (None, "Road class (vs motorway or trunk)")]
    rows += [(f"C(road_level)[T.{k}]", v) for k, v in ROAD]
    letters = unit_letters()
    ref = [raw for raw, lab in letters.items() if lab == "Unit D"][0]
    rows.append((None, "Management unit (vs Unit D)"))
    units = sorted(((lab, raw) for raw, lab in letters.items() if raw not in ("nan", ref)))
    rows += [(f"C(org)[T.{raw}]", lab) for lab, raw in units]
    return rows


# ---------------------------------------------------------------- data
def load_coverage():
    cov = pd.read_csv(SRC / "ed5a_coverage_26jul.csv").iloc[0].to_dict()
    for name in ["n_city","n_with","n_missing","n_ols"]:
        cov[name] = int(cov[name])
    return cov


def load_rings():
    return pd.read_csv(SRC / "ed5b_rings_26jul.csv")


def load_ols():
    t = pd.read_csv(SRC / "ed5cd_ols_coefficients_26jul.csv")
    label_to_term = {label:term for term,label in term_rows() if term is not None}
    t["term"] = t["label"].map(label_to_term).fillna("Intercept")
    return t


def write_source_data(*args, **kwargs):
    pass


# ---------------------------------------------------------------- panels
def panel_a(ax, cov):
    rows = [("Cameras", cov["n_with"] / cov["n_city"], f"{cov['n_with']}", f"{cov['n_missing']}"),
            ("Baseline flow", cov["flow_with"], f"{100 * cov['flow_with']:.1f}%", f"{100 * cov['flow_missing']:.1f}%")]
    colours = [COL["blue"], tint(COL["bluegrey"], 0.75)]
    for y, (label, share, t_with, t_missing) in enumerate(rows):
        ax.barh(y, share, height=0.5, color=colours[0], lw=0, zorder=2)
        ax.barh(y, 1 - share, left=share, height=0.5, color=colours[1], lw=0, zorder=2)
        ax.text(share / 2, y, t_with, fontsize=FS_NOTE, ha="center", va="center", color="white", zorder=3)
        ax.text(share + (1 - share) / 2, y, t_missing, fontsize=FS_NOTE, ha="center", va="center", zorder=3)
    ax.set_yticks([0, 1])
    ax.set_yticklabels([r[0] for r in rows])
    ax.set_ylim(2.6, -0.45)
    ax.set_xlim(0, 1)
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_xticklabels(["0", "25", "50", "75", "100"])
    ax.set_xlabel(f"Share of the {cov['n_city']} health-screened cameras (%)")
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    outward_spines(ax, left=False)
    handles = [Patch(facecolor=colours[0], edgecolor="none",
                     label=f"With coordinates: recovery ratio {cov['r_with']:.3f}"),
               Patch(facecolor=colours[1], edgecolor="none",
                     label=f"Without coordinates: recovery ratio {cov['r_missing']:.3f}")]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.0, 0.37), fontsize=FS_NOTE, handlelength=1.2,
              borderaxespad=0.0)
    ax.text(0.0, 2.45, f"All {cov['n_city']} cameras: recovery ratio {cov['r_city']:.3f}\n"
            f"{cov['n_ols']} of the {cov['n_with']} with coordinates enter the model in c",
            fontsize=FS_NOTE, ha="left", va="bottom", linespacing=LINESPACING)


def panel_b(ax_n, ax_f, rings):
    x = np.arange(len(RINGS))
    for k, (key, (label, colour)) in enumerate(SETS.items()):
        d = rings[rings["set"] == key].set_index("distance_ring").loc[RINGS]
        dx = -0.19 if k == 0 else 0.19
        ax_n.bar(x + dx, d["n_devices"], width=0.36, color=colour, lw=0, zorder=2, label=label)
        ax_f.bar(x + dx, d["baseline_records"] / 1e6, width=0.36, color=colour, lw=0, zorder=2)
    ax_n.set_ylim(0, 250)
    ax_n.set_yticks([0, 100, 200])
    ax_n.set_ylabel("Cameras")
    ax_f.set_ylim(0, 1.3)
    ax_f.set_yticks([0, 0.5, 1.0])
    ax_f.set_yticklabels(["0", "0.5", "1.0"])
    ax_f.set_ylabel("Baseline\n(10⁶ records)", linespacing=LINESPACING)
    for ax in (ax_n, ax_f):
        ax.set_xlim(-0.6, len(RINGS) - 0.4)
        ax.set_xticks(x)
        outward_spines(ax)
    ax_n.tick_params(axis="x", labelbottom=False, length=0)
    ax_n.spines["bottom"].set_visible(False)
    ax_f.set_xticklabels([r.replace("-", "–") for r in RINGS])
    ax_f.set_xlabel("Distance ring from Baiguan (km)")
    ax_n.legend(loc="upper right", ncol=2, fontsize=FS_NOTE, handlelength=1.0, columnspacing=0.8,
                borderaxespad=0.0, bbox_to_anchor=(1.0, 1.08))
    ax_n.figure.align_ylabels([ax_n, ax_f])


def row_positions(rows):
    y, out = 0.0, []
    for k, (term, _) in enumerate(rows):
        if term is None and k > 0:
            y += 0.45
        out.append(y)
        y += 1.0
    return np.array(out), y


def forest(ax, ols, rows, samples, *, labels):
    ys, y_end = row_positions(rows)
    ax.axvline(0, color=COL["bluegrey"], lw=0.8, ls=(0, (3, 2)), zorder=0)
    k_dist = [term for term, _ in rows].index("np.log1p(dist_baiguan_km)")
    ax.add_patch(Rectangle((-1.05, ys[k_dist] - 0.5), 2.1, 1.0, facecolor=COL["panel"], edgecolor="none", zorder=0))
    offsets = {1: [0.0], 2: [-0.17, 0.17]}[len(samples)]
    for (sample, dy) in zip(samples, offsets):
        label, colour = MODELS[sample]
        d = ols[ols["sample"] == sample].set_index("term")
        for (term, _), y in zip(rows, ys):
            if term is None:
                continue
            r = d.loc[term]
            ax.hlines(y + dy, r["ci_lo"], r["ci_hi"], color=colour, lw=0.9, zorder=2)
            filled = r["p"] < 0.05
            ax.plot([r["coef"]], [y + dy], "o", ms=3.0, mfc=colour if filled else "white", mec=colour, mew=0.8,
                    zorder=3)
    ax.set_ylim(y_end - 0.4, -0.7)
    ax.set_xlim(-1.05, 1.05)
    ax.set_xticks([-1.0, -0.5, 0, 0.5, 1.0])
    ax.set_xticklabels(["−1.0", "−0.5", "0", "0.5", "1.0"])
    ax.set_xlabel("Coefficient on log recovery ratio")
    ax.set_yticks([y for (term, _), y in zip(rows, ys) if term is not None])
    if labels:
        ax.set_yticklabels([lab for term, lab in rows if term is not None], fontsize=FS_NOTE)
        for (term, lab), y in zip(rows, ys):
            if term is None:
                ax.text(-0.02, y, lab, transform=ax.get_yaxis_transform(), fontsize=FS_NOTE, ha="right",
                        va="center", style="italic")
    else:
        ax.tick_params(axis="y", labelleft=False)
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    outward_spines(ax, left=False)


def main():
    mpl.rcParams.update(PUBLICATION_RC)
    mpl.rcParams.update(secondary_rc(FS_BODY, FS_TICK))
    cov = load_coverage()
    rings = load_rings()
    ols = load_ols()
    rows = term_rows()
    write_source_data(cov, rings, ols, rows)

    fig = plt.figure(figsize=(FIG_WIDTH_MM * MM, FIG_HEIGHT_MM * MM))
    gs = fig.add_gridspec(len(HEIGHTS), 2, left=LEFT / FIG_WIDTH_MM, right=1 - RIGHT / FIG_WIDTH_MM,
                          bottom=BOTTOM / FIG_HEIGHT_MM, top=1 - TOP / FIG_HEIGHT_MM,
                          wspace=COL_GUT / W, hspace=GAP / np.mean(HEIGHTS), height_ratios=HEIGHTS)
    ax_a = fig.add_subplot(gs[0:3, 0])
    ax_b1 = fig.add_subplot(gs[0, 1])
    ax_b2 = fig.add_subplot(gs[2, 1])
    ax_b2.set_gid("b-flow")
    ax_c = fig.add_subplot(gs[4, 0])
    ax_d = fig.add_subplot(gs[4, 1])
    panel_a(ax_a, cov)
    panel_b(ax_b1, ax_b2, rings)
    forest(ax_c, ols, rows, ["R_health"], labels=True)
    forest(ax_d, ols, rows, ["Sstar", "A100_floor"], labels=False)
    # One key for c and d, in a single row below both panels.
    handles = [Line2D([], [], marker="o", ls="none", ms=3.0, mfc=c, mec=c, label=f"{lab}")
               for s, (lab, c) in MODELS.items()]
    handles.append(Line2D([], [], marker="o", ls="none", ms=3.0, mfc="white", mec=COL["ink"], mew=0.8,
                          label="Open: P ≥ 0.05"))
    cb, db = ax_c.get_position(), ax_d.get_position()
    fig.legend(handles=handles, loc="lower center", bbox_to_anchor=((cb.x0 + db.x1) / 2, 1.2 / FIG_HEIGHT_MM),
               ncol=4, fontsize=FS_NOTE, handletextpad=0.2, columnspacing=1.6, borderaxespad=0.0, frameon=False)
    n = ols.groupby("sample")["n"].first()
    add_panel_label(ax_a, "a", "Coverage of the spatial analysis, 26 July", FS_LETTER, FS_BODY)
    add_panel_label(ax_b1, "b", "Cameras and baseline flow by distance ring", FS_LETTER, FS_BODY)
    add_panel_label(ax_c, "c", f"Health-screened set (n = {n['R_health']:,})", FS_LETTER, FS_BODY)
    add_panel_label(ax_d, "d", f"Fixed stable set (n = {n['Sstar']:,}); all cameras (n = {n['A100_floor']:,})",
                    FS_LETTER, FS_BODY)

    QA.mkdir(parents=True, exist_ok=True)
    report = require_matplotlib_panel_alignment(
        fig, json_out=QA / f"{NAME}.alignment.json", overlay_svg=QA / f"{NAME}.alignment.svg",
        tolerance_pt=1.5, gutter_tolerance_pt=1.5, require_panel_labels=True, strict=True,
        axes=[ax_a, ax_b1, ax_c, ax_d])
    tracks = require_matplotlib_panel_alignment(
        fig, json_out=QA / f"{NAME}.tracks.alignment.json", overlay_svg=QA / f"{NAME}.tracks.alignment.svg",
        tolerance_pt=1.5, gutter_tolerance_pt=1.5, require_panel_labels=False, strict=True,
        axes=[ax_b1, ax_b2])
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
