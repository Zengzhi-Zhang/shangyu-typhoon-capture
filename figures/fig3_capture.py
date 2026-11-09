"""Fig. 2 | Camera capture collapsed where taxi traffic persisted.

a  How capture is measured with GPS-tracked taxis (schematic)
b  Capture at the same cameras, 12-19 July and 26 July: one line per camera, pooled capture in bold,
   and for failed cameras the capture their own control-period rates would have given (hero panel)
c  Taxi passages at failed and stable cameras on 26 July
d  Relative capture by recording state on 26 July
e  All-camera to stable-camera record ratio: GPS taxis versus all vehicles
f  Robustness of pooled capture to the passage geometry

All observations of the frozen comparison groups are plotted; no rows are dropped.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.collections import LineCollection  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Circle, Polygon, Rectangle  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
try:
    from audit_panel_alignment import require_matplotlib_panel_alignment
except ImportError:
    def require_matplotlib_panel_alignment(*args, **kwargs):
        return {"verdict": "skipped_optional_QA_unavailable"}
from figstyle import (COL, MM, add_panel_label,  # noqa: E402
                      outward_spines, secondary_rc, spread_offsets)

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
# Three columns shared by both rows. The middle column is wider because b carries the decisive
# camera-level evidence; the outer columns are equal. The top row (a-c) is taller than the bottom row.
FIG_WIDTH_MM = 180.0
LEFT, RIGHT, TOP, BOTTOM = 12.0, 3.0, 8.0, 10.5
COL_GUT, ROW_GUT = 11.0, 17.0
W_MID = 63.0
W_SIDE = (FIG_WIDTH_MM - LEFT - RIGHT - 2 * COL_GUT - W_MID) / 2
H_TOP, H_BOTTOM = 52.0, 40.0
FIG_HEIGHT_MM = TOP + H_TOP + ROW_GUT + H_BOTTOM + BOTTOM
PANEL_W, PANEL_H = W_SIDE, H_TOP      # panel a (schematic) is drawn in millimetres

# panel b: x positions of the two periods for each group
B_X = {"failed": (0.0, 1.0), "stable": (3.0, 4.0)}
B_XLIM = (-0.7, 4.65)


# ---------------------------------------------------------------- data
def load_camera_capture():
    t = pd.read_csv(SRC / "fig3bc_camera_capture_exposure.csv")
    # The published group/index order makes alpha compositing reproducible.
    # These are public display indices, not restricted device identifiers.
    t = t.sort_values(["group", "camera_index"], kind="mergesort").reset_index(drop=True)
    t = t.rename(columns={"control_capture_rate":"control_rate", "capture_rate_26jul":"event_rate", "taxi_exposure_ratio":"exposure"})
    pooled = pd.read_csv(SRC / "fig3b_pooled_and_expected.csv")
    groups = []
    for name in ("failed", "stable"):
        g = t[t.group.eq(name)].copy()
        rows = pooled[pooled.group.eq(name) & pooled.quantity.eq("recorded")]
        control = rows[rows.period.eq("12-19 Jul (control)")].iloc[0]
        event = rows[rows.period.eq("26 Jul")].iloc[0]
        g.attrs["pooled_rates"] = (100 * control.recordings / control.passages, 100 * event.recordings / event.passages)
        g.attrs["pooled_counts"] = (int(event.recordings), int(event.passages))
        if name == "failed":
            g.attrs["expected_recordings"] = float(pooled[pooled.quantity.ne("recorded")].iloc[0].recordings)
        groups.append(g)
    assert len(groups[0]) == 64 and len(groups[1]) == 170
    return tuple(groups)


def load_state_capture():
    return pd.read_csv(SRC / "fig3d_capture_by_state.csv").set_index("state")


def load_network_ratio():
    return pd.read_csv(SRC / "fig3e_network_record_ratio.csv").sort_values("date")


def load_expected_capture():
    p = pd.read_csv(SRC / "fig3b_pooled_and_expected.csv")
    r = p[p.quantity.ne("recorded")].iloc[0]
    c = p[p.group.eq("failed") & p.quantity.eq("recorded") & p.period.eq("26 Jul")].iloc[0]
    return pd.Series({"E":r.recordings,"C":c.recordings,"n_report_cameras":r.n_cameras,"E_camera_ci_lo":r.camera_ci_lo,"E_camera_ci_hi":r.camera_ci_hi})


def load_geometry_variants():
    return pd.read_csv(SRC / "fig3f_geometry_variants.csv")


# ---------------------------------------------------------------- panel a helpers
def check_mark(ax, x, y, s, color):
    ax.add_line(Line2D([x, x + 0.35 * s, x + s], [y + 0.45 * s, y, y + 0.95 * s],
                       color=color, lw=1.1, solid_capstyle="round", solid_joinstyle="round"))


def cross_mark(ax, x, y, s, color):
    ax.add_line(Line2D([x, x + s], [y, y + s], color=color, lw=1.1, solid_capstyle="round"))
    ax.add_line(Line2D([x, x + s], [y + s, y], color=color, lw=1.1, solid_capstyle="round"))


def camera_icon(ax, x, y_top_of_road, color):
    ax.add_line(Line2D([x, x], [y_top_of_road, y_top_of_road + 5.0], color=color, lw=0.8))
    ax.add_patch(Rectangle((x - 1.7, y_top_of_road + 5.0), 3.0, 1.7, facecolor=color,
                           edgecolor="none"))
    ax.add_patch(Polygon([[x + 1.3, y_top_of_road + 5.45], [x + 2.3, y_top_of_road + 5.0],
                          [x + 2.3, y_top_of_road + 6.7], [x + 1.3, y_top_of_road + 6.25]],
                         closed=True, facecolor=color, edgecolor="none"))


# ---------------------------------------------------------------- panels
def panel_a(ax):
    """Schematic of the matching logic, drawn in millimetres (no real geometry)."""
    ax.set_xlim(0, PANEL_W)
    ax.set_ylim(0, PANEL_H)
    ax.axis("off")
    cam_x = 0.52 * PANEL_W
    fixes = np.array([0.10, 0.34, 0.70, 0.91]) * PANEL_W
    for base, title, ok in ((32.8, "12–19 Jul (control)", True), (10.0, "26 Jul", False)):
        road_y = base + 6.0
        ax.text(0.8, base + 16.2, title, fontsize=FS_NOTE, ha="left", va="baseline")
        ax.add_patch(Rectangle((0.8, road_y - 2.6), PANEL_W - 1.6, 5.2,
                               facecolor=COL["panel"], edgecolor=COL["bluegrey"], lw=0.6))
        ax.add_patch(Circle((cam_x, road_y), 6.4, fill=False, edgecolor=COL["bluegrey"],
                            lw=0.7, ls=(0, (2.0, 1.6))))
        sect = COL["blue"] if ok else COL["red"]
        ax.add_line(Line2D([cam_x, cam_x], [road_y - 2.6, road_y + 2.6], color=sect, lw=0.9,
                           ls=(0, (1.6, 1.1))))
        camera_icon(ax, cam_x, road_y + 2.6, COL["ink"])
        ax.add_line(Line2D(fixes, np.full(fixes.size, road_y), color=COL["teal"], lw=0.9))
        ax.plot(fixes, np.full(fixes.size, road_y), "o", ms=3.0, color=COL["teal"], mec="white",
                mew=0.4, zorder=4)
        ax.plot([cam_x], [road_y], "o", ms=3.4, mfc="white", mec=COL["teal"], mew=0.9, zorder=5)
        ax.annotate("", xy=(fixes[-1] + 2.3, road_y), xytext=(fixes[-1] + 0.6, road_y),
                    arrowprops=dict(arrowstyle="-|>", color=COL["teal"], lw=0.8,
                                    mutation_scale=5, shrinkA=0, shrinkB=0))
        mark_x, mark_y = cam_x + 3.6, road_y + 8.4
        if ok:
            check_mark(ax, mark_x, mark_y - 0.2, 1.8, COL["blue"])
            ax.text(mark_x + 2.6, mark_y, "recorded", fontsize=FS_NOTE, ha="left", va="baseline")
            ax.text(0.8, road_y - 4.9, "Taxi GPS fixes", fontsize=FS_NOTE, ha="left", va="baseline")
            ax.text(cam_x + 6.9, road_y - 4.9, "60 m", fontsize=FS_NOTE, ha="left", va="baseline")
        else:
            cross_mark(ax, mark_x + 0.1, mark_y - 0.3, 1.5, COL["red"])
            ax.text(mark_x + 2.6, mark_y, "not recorded", fontsize=FS_NOTE, ha="left",
                    va="baseline")
    ax.text(0.8, 0.4, "Capture = recorded ÷\nGPS-inferred passages", fontsize=FS_NOTE, ha="left",
            va="bottom", linespacing=1.25)


def pooled_rates(g):
    return g.attrs["pooled_rates"]


def panel_b(ax, failed, stable, t40):
    """Slope chart: one thin line per camera, pooled capture in bold. For failed cameras the dashed
    line ends at the capture their own control-period rates would have given on 26 July (T40)."""
    groups = (("failed", failed, COL["red"], 0.28), ("stable", stable, COL["blue"], 0.22))
    pooled = {}
    for name, g, col, alpha in groups:
        x0, x1 = B_X[name]
        segs = [[(x0, 100 * a), (x1, 100 * b)] for a, b in zip(g["control_rate"], g["event_rate"])]
        ax.add_collection(LineCollection(segs, colors=[col], linewidths=0.5, alpha=alpha, zorder=2))
        pooled[name] = pooled_rates(g)
    cap, exp = failed.attrs["pooled_counts"]
    expected = failed.attrs["expected_recordings"]
    assert (cap, exp) == (55, 14335)
    assert abs(expected - t40["E"]) < 1.0 and int(t40["C"]) == cap and int(t40["n_report_cameras"]) == 64
    e_pct = 100 * expected / exp
    (f0, f1), (s0, s1) = pooled["failed"], pooled["stable"]
    assert (round(f0, 1), round(f1, 2), round(s0, 1), round(s1, 1)) == (60.5, 0.38, 74.0, 70.1)
    fx0, fx1 = B_X["failed"]
    ax.add_line(Line2D([fx0, fx1], [f0, e_pct], color=COL["red"], lw=1.0, ls=(0, (3.0, 1.8)),
                       zorder=3))
    ax.plot([fx1], [e_pct], "o", ms=4.4, mfc="white", mec=COL["red"], mew=0.9, zorder=5)
    for name, g, col, _ in groups:
        x0, x1 = B_X[name]
        p0, p1 = pooled[name]
        ax.add_line(Line2D([x0, x1], [p0, p1], color=col, lw=2.0, solid_capstyle="round", zorder=4))
        ax.plot([x0, x1], [p0, p1], "o", ms=4.4, color=col, mec="white", mew=0.7, zorder=6)
    pad = 0.10
    ax.text(fx0 - pad, f0, f"{f0:.1f}%", fontsize=FS_NOTE, ha="right", va="center")
    ax.text(fx1 + pad, e_pct, f"About {round(expected, -2):,.0f} expected\nat own control rates",
            fontsize=FS_NOTE, ha="left", va="center", linespacing=1.2)
    ax.text(fx1 + pad, 1.0, f"{cap} of {exp:,}\nrecorded ({f1:.2f}%)", fontsize=FS_NOTE,
            ha="left", va="bottom", color=COL["red"], linespacing=1.2, zorder=7)
    sx0, sx1 = B_X["stable"]
    ax.text(sx0 - pad, s0, f"{s0:.1f}%", fontsize=FS_NOTE, ha="right", va="center")
    ax.text(sx1 + pad, s1, f"{s1:.1f}%", fontsize=FS_NOTE, ha="left", va="center")
    # group headers double as the colour key
    ax.text(np.mean(B_X["failed"]), 103.0, f"Failed on 26 Jul (n = {len(failed)})",
            fontsize=FS_NOTE, ha="center", va="baseline", color=COL["red"])
    ax.text(np.mean(B_X["stable"]), 103.0, f"Stable set (n = {len(stable)})",
            fontsize=FS_NOTE, ha="center", va="baseline", color=COL["blue"])
    handles = [Line2D([], [], color=COL["ink"], lw=0.5, alpha=0.6, label="One camera"),
               Line2D([], [], color=COL["ink"], lw=2.0, marker="o", ms=4.4, mec="white", mew=0.7,
                      label="Pooled")]
    xmid = (np.mean([B_X["failed"][1], B_X["stable"][0]]) - B_XLIM[0]) / (B_XLIM[1] - B_XLIM[0])
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(xmid, 0.89), fontsize=FS_NOTE,
              handlelength=1.6, borderaxespad=0.0)
    ax.set_xlim(*B_XLIM)
    ax.set_ylim(-3, 108)
    ax.set_xticks([*B_X["failed"], *B_X["stable"]])
    ax.set_xticklabels(["12–19 Jul", "26 Jul", "12–19 Jul", "26 Jul"])
    ax.tick_params(axis="x", length=0)
    ax.spines["bottom"].set_visible(False)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.spines["left"].set_bounds(0, 100)
    ax.set_ylabel("Capture rate (%)")
    outward_spines(ax, bottom=False)
    return dict(failed_control=f0, failed_event=f1, stable_control=s0, stable_event=s1,
                failed_expected=expected, failed_expected_pct=e_pct, recorded=cap, passages=exp)


def panel_c(ax, failed, stable):
    groups = [failed["exposure"].to_numpy(), stable["exposure"].to_numpy()]
    cols = [COL["red"], COL["blue"]]
    ax.axhline(1.0, color=COL["bluegrey"], lw=0.8, ls=(0, (3, 2)), zorder=1)
    for i, (vals, col) in enumerate(zip(groups, cols)):
        order = np.argsort(vals)
        dx = np.empty(vals.size)
        dx[order] = spread_offsets(vals.size, 0.16)
        ax.scatter(i + dx, vals, s=6, c=col, alpha=0.55, edgecolors="none", zorder=2)
        ax.boxplot([vals], positions=[i], widths=0.46, showfliers=False, patch_artist=True,
                   medianprops=dict(color=COL["ink"], lw=1.1),
                   boxprops=dict(facecolor="none", edgecolor=COL["ink"], lw=0.7),
                   whiskerprops=dict(color=COL["ink"], lw=0.7),
                   capprops=dict(color=COL["ink"], lw=0.7), zorder=3)
        ax.text(i + 0.27, np.median(vals), f"{np.median(vals):.2f}", fontsize=FS_NOTE,
                ha="left", va="center")
    ax.set_xticks([0, 1])
    ax.set_xticklabels([f"Failed\nn = {len(failed)}", f"Stable set\nn = {len(stable)}"])
    ax.tick_params(axis="x", length=0)
    ax.set_xlim(-0.55, 1.6)
    ax.set_ylim(0, 2.4)
    ax.set_yticks([0, 0.5, 1.0, 1.5, 2.0])
    ax.set_ylabel("Taxi passages, 26 Jul ÷ control mean")
    outward_spines(ax, bottom=False)


STATE_ROWS = [
    ("normal", "Normal recording", "blue"),
    ("partial_channel", "Some lanes silent", "blue"),
    ("recognition_degraded", "Plate recognition degraded", "orange"),
    ("degraded_other", "Other degradation", "orange"),
    ("partial_day", "Recording stopped part-day", "red"),
    ("low_all_channels", "All lanes very low", "red"),
    ("zero", "No records", "red"),
]


def panel_d(ax, state):
    n_rows = len(STATE_ROWS)
    for k, (key, label, cname) in enumerate(STATE_ROWS):
        y = n_rows - 1 - k
        r = state.loc[key]
        col = COL[cname]
        ax.add_line(Line2D([1.0, 1.0], [y - 0.28, y + 0.16], color=COL["bluegrey"], lw=0.7,
                           ls=(0, (2, 1.5)), zorder=1))
        ax.add_line(Line2D([r["camera_ci_lo"], r["camera_ci_hi"]], [y, y], color=col, lw=1.0,
                           zorder=2))
        small = int(r["n"]) < 5
        ax.plot([r["median"]], [y], "o", ms=3.8, mfc="white" if small else col, mec=col,
                mew=0.9, zorder=3)
        ax.text(0.0, y + 0.30, f"{label} (n = {int(r['n'])})", fontsize=FS_NOTE, ha="left",
                va="bottom")
    ax.set_xlim(-0.02, 1.2)
    ax.set_ylim(-0.6, n_rows - 0.1)
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_xlabel("Relative capture, 26 Jul ÷ control")
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    outward_spines(ax, left=False)


def panel_e(ax, net):
    x = np.arange(len(net))
    hollow = (net["date"] == "2021-07-25").to_numpy()
    series = [("q_fleet", COL["blue"], "o", "All vehicles"),
              ("q_probe", COL["teal"], "s", "GPS taxis (n = 290)")]
    ax.axhline(1.0, color=COL["bluegrey"], lw=0.8, ls=(0, (3, 2)), zorder=1)
    handles = []
    for key, col, mk, lab in series:
        y = net[key].to_numpy()
        lo, hi = net[f"{key}_ci_lo"].to_numpy(), net[f"{key}_ci_hi"].to_numpy()
        ax.fill_between(x, lo, hi, color=col, alpha=0.18, lw=0, zorder=2)
        ax.plot(x, y, color=col, lw=1.2, zorder=3)
        ax.plot(x[~hollow], y[~hollow], mk, ms=3.4, color=col, mec="white", mew=0.4, zorder=4)
        ax.plot(x[hollow], y[hollow], mk, ms=3.4, mfc="white", mec=col, mew=0.9, zorder=4)
        handles.append(Line2D([], [], color=col, marker=mk, ms=3.4, mec="white", mew=0.4,
                              lw=1.2, label=lab))
    ax.legend(handles=handles, loc="lower right", fontsize=FS_NOTE, handlelength=1.6)
    ax.set_xticks(x)
    ax.set_xticklabels([d[-2:].lstrip("0") for d in net["date"]])
    ax.set_xlim(-0.4, len(net) - 0.6)
    ax.set_ylim(0.6, 1.02)
    ax.set_yticks([0.6, 0.7, 0.8, 0.9, 1.0])
    ax.set_xlabel("July 2021")
    ax.set_ylabel("All-camera ÷ stable-set records")
    outward_spines(ax)


F_DEFS = [("Main: 60 m, 180 s", "Main"), ("Direction and road consistent", "Direction\nand road"),
          ("40 m radius", "40 m\nradius")]
F_DX = 0.17
F_NROW = 84.0      # common row for the camera counts, above every open marker


def panel_f(ax, geo):
    """Vertical dumbbells on the capture axis of b: open, 12-19 July; filled, 26 July."""
    for j, (definition, _) in enumerate(F_DEFS):
        for group, dx, cname in (("failed", -F_DX, "red"), ("stable", F_DX, "blue")):
            r = geo[(geo["group"] == group) & (geo["definition"] == definition)].iloc[0]
            col, x = COL[cname], j + dx
            c0, c1 = 100 * r["control_rate"], 100 * r["event_rate"]
            assert c0 + 2.5 < F_NROW
            ax.add_line(Line2D([x, x], [c1, c0], color=col, lw=1.0, alpha=0.55, zorder=1))
            ax.plot([x], [c0], "o", ms=3.8, mfc="white", mec=col, mew=0.9, zorder=3)
            ax.plot([x], [c1], "o", ms=3.8, color=col, mec=col, mew=0.9, zorder=3)
            ax.text(x, F_NROW, f"{int(r['n'])}", fontsize=FS_NOTE, ha="center", va="bottom")
    handles = [Line2D([], [], ls="none", marker="o", ms=3.8, color=COL["red"], label="Failed"),
               Line2D([], [], ls="none", marker="o", ms=3.8, color=COL["blue"], label="Stable set"),
               Line2D([], [], ls="none", marker="o", ms=3.8, mfc="white", mec=COL["ink"], mew=0.9,
                      label="12–19 Jul"),
               Line2D([], [], ls="none", marker="o", ms=3.8, color=COL["ink"], label="26 Jul")]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 1.0), ncol=2,
              fontsize=FS_NOTE, handlelength=0.8, columnspacing=1.0, borderaxespad=0.0)
    ax.set_xlim(-0.55, len(F_DEFS) - 0.45)
    ax.set_ylim(-3, 113)
    ax.set_xticks(range(len(F_DEFS)))
    ax.set_xticklabels([tick for _, tick in F_DEFS], linespacing=1.1)
    ax.tick_params(axis="x", length=0)
    ax.spines["bottom"].set_visible(False)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.spines["left"].set_bounds(0, 100)
    ax.set_ylabel("Pooled capture (%)")
    outward_spines(ax, bottom=False)


# ---------------------------------------------------------------- source data
def write_source_data(*args, **kwargs):
    """Source CSV bytes are immutable; readers use the published files directly."""
    pass


def write_b_summary(*args, **kwargs):
    pass


def main():
    mpl.rcParams.update(PUBLICATION_RC)
    mpl.rcParams.update(secondary_rc(FS_BODY, FS_TICK))
    failed, stable = load_camera_capture()
    state = load_state_capture()
    net = load_network_ratio()
    geo = load_geometry_variants()
    t40 = load_expected_capture()
    write_source_data(failed, stable, state, net, geo)

    fig = plt.figure(figsize=(FIG_WIDTH_MM * MM, FIG_HEIGHT_MM * MM))
    # wspace/hspace are fractions of the mean column width / row height, so the gutters stay at
    # COL_GUT and ROW_GUT millimetres with unequal ratios.
    gs = fig.add_gridspec(
        2, 3, left=LEFT / FIG_WIDTH_MM, right=1 - RIGHT / FIG_WIDTH_MM,
        bottom=BOTTOM / FIG_HEIGHT_MM, top=1 - TOP / FIG_HEIGHT_MM,
        width_ratios=[W_SIDE, W_MID, W_SIDE], height_ratios=[H_TOP, H_BOTTOM],
        wspace=COL_GUT / ((2 * W_SIDE + W_MID) / 3), hspace=ROW_GUT / ((H_TOP + H_BOTTOM) / 2))
    axes = [fig.add_subplot(gs[r, c]) for r in range(2) for c in range(3)]
    titles = ["Measuring capture with taxis", "Capture at the same cameras",
              "Taxi passages persisted", "Capture by recording state",
              "Network-level comparison", "Robustness to passage geometry"]
    panel_a(axes[0])
    b = panel_b(axes[1], failed, stable, t40)
    write_b_summary(failed, stable, b, t40)
    panel_c(axes[2], failed, stable)
    panel_d(axes[3], state)
    panel_e(axes[4], net)
    panel_f(axes[5], geo)
    for ax, letter, title in zip(axes, "abcdef", titles):
        add_panel_label(ax, letter, title, FS_LETTER, FS_BODY)

    QA.mkdir(exist_ok=True)
    report = require_matplotlib_panel_alignment(
        fig, json_out=QA / "fig3_capture.alignment.json", overlay_svg=QA / "fig3_capture.alignment.svg",
        tolerance_pt=1.5, gutter_tolerance_pt=1.5, require_panel_labels=True, strict=True,
        exemptions=[{"panels": ["b", "e"], "checks": ["panel-width"],
                     "reason": "hero column: b carries the camera-level evidence and e shares its "
                               "column; the outer columns a/c and d/f stay equal"}])
    fig.savefig(OUT / "fig3_capture.svg")
    fig.savefig(OUT / "fig3_capture.pdf")
    # Uncompressed TIFF: the local libtiff build aborts on LZW compression.
    fig.savefig(OUT / "fig3_capture.tiff", dpi=600)
    fig.savefig(OUT / "fig3_capture.png", dpi=300)
    plt.close(fig)
    print("alignment:", report.get("verdict"), "| size mm:", FIG_WIDTH_MM, round(FIG_HEIGHT_MM, 1))


if __name__ == "__main__":
    main()
