"""Extended Data Fig. 2 | How recording states are assigned and which ones each screening removes.

a  The eight recording-state labels, applied in order (the first rule met assigns the state), and the
   two screened sets built from them
b  Cameras in each state on 26 July, with the failed cameras among them (below 5% of the
   event-aware denominator, rule A1) and the share of baseline flow
c  Daily composition by screening role: control day (19 July) and 25 July to 2 August

All 1,221 A200 cameras are counted on every date; no rows are dropped. Group-level counts only.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Patch, Rectangle  # noqa: E402
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
NAME = "ed2_states"

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
LEFT, RIGHT, TOP, BOTTOM = 14.5, 3.0, 8.0, 9.0
W_A, W_B, COL_GUT = 90.0, 60.5, 12.0
NAME_COL_MM = 38.0              # width of the state-name column inside panel a
H_TOP, H_C, ROW_GUT = 72.0, 34.0, 16.0
FIG_HEIGHT_MM = TOP + H_TOP + ROW_GUT + H_C + BOTTOM

# ---------------------------------------------------------------- states and screening roles
# Rule order follows the frozen v6 task book with the v7 part-day state inserted after "offline".
HEALTH_OUT, STRICT_OUT, KEPT = "health_out", "strict_out", "kept"
ROWS = [
    ("zero", "No records", "Zero records all day", HEALTH_OUT),
    ("offline", "Offline", "Records in ≤4 hours (≤2 on 25 Jul)", HEALTH_OUT),
    ("partial_day", "Recording stopped part-day",
     "Records in 5–11 hours, with a stop hour\nor ≥6 consecutive empty hours", HEALTH_OUT),
    ("partial_channel", "Some lanes silent", "≥1 lane below 5% and ≥1 lane at or\nabove 50% of its baseline",
     HEALTH_OUT),
    ("recognition_degraded", "Plate recognition degraded",
     "Unreadable-plate share ≥0.10 above\nbaseline, and ratio ≥0.20", KEPT),
    ("low_all_channels", "All lanes very low",
     "Ratio <0.05, records in ≥12 hours, no\nlane split or recognition spike", STRICT_OUT),
    ("degraded_other", "Other degradation", "Ratio 0.05–0.50", STRICT_OUT),
    ("normal", "Normal recording", "None of rules 1–7 met (fallback label)", KEPT),
]
SETS = [
    ("health", "Health-screened set", "States 5–8: removes states 1–4"),
    ("strict", "Strict health-screened set", "States 5 and 8: also removes 6 and 7"),
]
ROLE_COLOUR = {HEALTH_OUT: COL["bluegrey"], STRICT_OUT: COL["purple"], KEPT: COL["blue"]}
ROLE_FILL = {HEALTH_OUT: tint(COL["bluegrey"], 0.35), STRICT_OUT: tint(COL["purple"], 0.18),
             KEPT: tint(COL["blue"], 0.14)}
ROLE_LABEL = {KEPT: "Kept by both screenings", STRICT_OUT: "Removed by the strict screening only",
              HEALTH_OUT: "Removed by the health screening"}
DAYS = ["2021-07-19"] + [d.strftime("%Y-%m-%d") for d in pd.date_range("2021-07-25", "2021-08-02")]
FOCUS = "2021-07-26"
PARTIAL_DAY = "2021-07-25"
N_ROWS = len(ROWS) + len(SETS)


# ---------------------------------------------------------------- data
def load_states():
    return pd.read_csv(SRC / "ed2c_states_daily.csv")


def focus_table(s):
    return pd.read_csv(SRC / "ed2b_states_26jul.csv")


def daily_roles(s):
    g = pd.read_csv(SRC / "ed2c_roles_daily.csv").set_index("date").reindex(DAYS)
    return g.rename(columns={"kept_by_both":KEPT,"removed_by_strict_only":STRICT_OUT,"removed_by_health":HEALTH_OUT})[[KEPT,STRICT_OUT,HEALTH_OUT]].astype(int)


def write_source_data(*args, **kwargs):
    pass


# ---------------------------------------------------------------- panels
def row_y(k):
    """Row centre; the two screened-set rows sit below a small gap."""
    return k + (0.35 if k >= len(ROWS) else 0.0)


Y_MAX = row_y(N_ROWS - 1) + 0.5
Y_TOP, Y_HEAD = -1.25, -0.85      # header row above the first state


def panel_a(ax):
    ax.set_xlim(0, 1)
    ax.set_ylim(Y_MAX, Y_TOP)
    ax.axis("off")
    w_mm = ax.get_position().width * FIG_WIDTH_MM
    stripe = 1.6 / w_mm
    x_name, x_rule = stripe + 1.6 / w_mm, NAME_COL_MM / w_mm
    for x, txt in ((x_name, "State, in order of application"), (x_rule, "Rule")):
        ax.text(x, Y_HEAD, txt, fontsize=FS_NOTE, ha="left", va="center")
    for k, (key, label, rule, role) in enumerate(ROWS):
        y = row_y(k)
        ax.add_patch(FancyBboxPatch((0, y - 0.42), 1, 0.84, boxstyle="square,pad=0", facecolor=ROLE_FILL[role],
                                    edgecolor="none", zorder=1))
        ax.add_patch(Rectangle((0, y - 0.42), stripe, 0.84, facecolor=ROLE_COLOUR[role], edgecolor="none", zorder=2))
        ax.text(x_name, y, f"{k + 1}  {label}", fontsize=FS_NOTE + 0.5, ha="left", va="center", zorder=3)
        ax.text(x_rule, y, rule, fontsize=FS_NOTE, ha="left", va="center", linespacing=LINESPACING, zorder=3)
    for j, (key, label, rule) in enumerate(SETS):
        y = row_y(len(ROWS) + j)
        ax.add_patch(Rectangle((0, y - 0.42), 1, 0.84, facecolor=COL["panel"], edgecolor="none", zorder=1))
        ax.text(x_name, y, label, fontsize=FS_NOTE + 0.5, ha="left", va="center", zorder=3)
        ax.text(x_rule, y, rule, fontsize=FS_NOTE, ha="left", va="center", zorder=3)
    ysep = (row_y(len(ROWS) - 1) + row_y(len(ROWS))) / 2
    ax.plot([0, 1], [ysep, ysep], color=COL["ink"], lw=0.5, zorder=3)


def panel_b(ax, t):
    ax.set_ylim(Y_MAX, Y_TOP)
    xmax_bar, x_fail, x_flow, x_end = 1221, 1560, 1960, 2120
    ax.set_xlim(0, x_end)
    h = 0.56
    for k, r in enumerate(t.itertuples()):
        y = row_y(k)
        if r.role == "set":
            kept = int(t.loc[t["role"] == KEPT, "cameras"].sum())
            ax.barh(y, kept, height=h, color=ROLE_COLOUR[KEPT], lw=0, zorder=2)
            if r.state == "health":
                ax.barh(y, r.cameras - kept, left=kept, height=h, color=ROLE_COLOUR[STRICT_OUT], lw=0, zorder=2)
        else:
            ax.barh(y, r.cameras, height=h, color=ROLE_COLOUR[r.role], lw=0, zorder=2)
        if r.a1_failed:
            ax.barh(y, r.a1_failed, height=h * 0.42, color=COL["red"], lw=0, zorder=3)
        ax.text(r.cameras + 22, y, f"{r.cameras:,}", fontsize=FS_NOTE, ha="left", va="center")
        ax.text(x_fail, y, f"{r.a1_failed:,}", fontsize=FS_NOTE, ha="right", va="center",
                color=COL["red"] if r.a1_failed else COL["ink"])
        ax.text(x_flow, y, f"{100 * r.baseline_flow_share:.1f}%", fontsize=FS_NOTE, ha="right", va="center")
    ysep = (row_y(len(ROWS) - 1) + row_y(len(ROWS))) / 2
    ax.plot([0, x_end], [ysep, ysep], color=COL["ink"], lw=0.5, zorder=3)
    for x, txt, ha in ((0, "Cameras", "left"), (x_fail, "Failed", "right"), (x_flow, "Flow share", "right")):
        ax.text(x, Y_HEAD, txt, fontsize=FS_NOTE, ha=ha, va="center",
                color=COL["red"] if txt == "Failed" else COL["ink"])
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    outward_spines(ax, left=False)
    ax.spines["bottom"].set_bounds(0, xmax_bar)
    ax.set_xticks([0, 600, 1200])
    ax.set_xticklabels(["0", "600", "1,200"])
    ax.set_xlabel("Cameras on 26 July (of 1,221)", x=xmax_bar / 2 / x_end)


def panel_c(ax, g):
    x = np.array([0] + list(range(2, 2 + len(DAYS) - 1)), dtype=float)
    bottom = np.zeros(len(DAYS))
    for role in (KEPT, STRICT_OUT, HEALTH_OUT):
        v = g[role].to_numpy().astype(float)
        for xi, b, vi, day in zip(x, bottom, v, DAYS):
            if day == PARTIAL_DAY:
                ax.bar(xi, vi, bottom=b, width=0.66, facecolor="white", edgecolor=ROLE_COLOUR[role], lw=0.7, zorder=2)
            else:
                ax.bar(xi, vi, bottom=b, width=0.66, color=ROLE_COLOUR[role], lw=0, zorder=2)
            if vi >= 80:
                dark = role != HEALTH_OUT and day != PARTIAL_DAY
                ax.text(xi, b + vi / 2, f"{int(vi):,}", fontsize=FS_NOTE, ha="center", va="center",
                        color="white" if dark else COL["ink"], zorder=3)
        bottom += v
    ax.set_xlim(-0.7, x[-1] + 0.7)
    ax.set_ylim(0, 1221)
    ax.set_yticks([0, 600, 1200])
    ax.set_yticklabels(["0", "600", "1,200"])
    ax.set_ylabel("Cameras")
    outward_spines(ax)
    ax.xaxis.set_major_locator(FixedLocator(x))
    ax.set_xticklabels([str(pd.Timestamp(d).day) for d in DAYS])
    k = DAYS.index(FOCUS)
    ax.add_patch(Rectangle((x[k] - 0.45, 0), 0.9, 1221, facecolor="none", edgecolor=COL["ink"], lw=0.6,
                           ls=(0, (2, 1.4)), zorder=4))
    trans = lambda dy: ax.get_xaxis_transform() + ScaledTranslation(0, -dy * MM, ax.figure.dpi_scale_trans)
    for label, xm in (("Control", 0.0), ("July 2021", float(np.mean(x[1:8]))), ("Aug", float(np.mean(x[8:])))):
        ax.text(xm, 0, label, transform=trans(5.6), fontsize=FS_NOTE, ha="center", va="top")


def main():
    mpl.rcParams.update(PUBLICATION_RC)
    mpl.rcParams.update(secondary_rc(FS_BODY, FS_TICK))
    s = load_states()
    t = focus_table(s)
    g = daily_roles(s)
    write_source_data(s, t, g)

    fig = plt.figure(figsize=(FIG_WIDTH_MM * MM, FIG_HEIGHT_MM * MM))
    gs = fig.add_gridspec(2, 2, left=LEFT / FIG_WIDTH_MM, right=1 - RIGHT / FIG_WIDTH_MM,
                          bottom=BOTTOM / FIG_HEIGHT_MM, top=1 - TOP / FIG_HEIGHT_MM,
                          wspace=COL_GUT / ((W_A + W_B) / 2), hspace=ROW_GUT / ((H_TOP + H_C) / 2),
                          width_ratios=[W_A, W_B], height_ratios=[H_TOP, H_C])
    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])
    ax_c = fig.add_subplot(gs[1, 0])
    panel_a(ax_a)
    panel_b(ax_b, t)
    panel_c(ax_c, g)
    add_panel_label(ax_a, "a", "Recording states, assigned in order", FS_LETTER, FS_BODY)
    add_panel_label(ax_b, "b", "Cameras in each state on 26 July", FS_LETTER, FS_BODY)
    add_panel_label(ax_c, "c", "Cameras per day by screening role", FS_LETTER, FS_BODY)

    # Legend in the free cell beside c, aligned with b's left edge.
    bb = ax_b.get_position()
    cb = ax_c.get_position()
    handles = [Patch(facecolor=ROLE_COLOUR[r], edgecolor="none", label=ROLE_LABEL[r]) for r in (KEPT, STRICT_OUT, HEALTH_OUT)]
    handles.append(Patch(facecolor=COL["red"], edgecolor="none", label="Failed (<5% of the event-aware denominator)"))
    handles.append(Patch(facecolor="white", edgecolor=COL["ink"], lw=0.7, label="25 July: cameras observed 11:00–23:59"))
    fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(bb.x0, cb.y1), fontsize=FS_NOTE,
               handlelength=1.4, handleheight=0.9, borderaxespad=0.0, frameon=False)

    QA.mkdir(parents=True, exist_ok=True)
    report = require_matplotlib_panel_alignment(
        fig, json_out=QA / f"{NAME}.alignment.json", overlay_svg=QA / f"{NAME}.alignment.svg",
        tolerance_pt=1.5, gutter_tolerance_pt=1.5, require_panel_labels=True, strict=True)
    fig.savefig(OUT / f"{NAME}.svg")
    fig.savefig(OUT / f"{NAME}.pdf")
    # Uncompressed TIFF: the local libtiff build aborts on LZW compression.
    fig.savefig(OUT / f"{NAME}.tiff", dpi=600)
    fig.savefig(OUT / f"{NAME}.png", dpi=300)
    plt.close(fig)
    print("alignment:", report.get("verdict"), "| size mm:", FIG_WIDTH_MM, round(FIG_HEIGHT_MM, 1))


if __name__ == "__main__":
    main()
