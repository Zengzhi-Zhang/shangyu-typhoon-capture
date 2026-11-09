"""Fig. 1 | Camera records combine passing traffic with capture, and taxi traces can separate the two.

Concept figure: a schematic that draws no study data. Three panels of equal width.
a  Same record count, two causes. Records = traffic x capture; fewer vehicles and missed vehicles
   leave the same count. Quantities are illustrative (10 and 5 passages).
b  Taxis as independent witnesses. A taxi's GPS fixes give an inferred passage at each camera; the
   passage counts as recorded when the camera logs that taxi. Capture = taxi passages recorded /
   GPS-inferred taxi passages, camera by camera. The matching rule itself is in Fig. 3a.
c  A judgement with its condition. Network recovery mixes kept cameras with screened-out roads of
   unseen recovery x. The bar spans two readings of x and the dot is the x needed to reach a
   threshold, in the encoding of Fig. 4c; the three positions give the three verdicts.
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
try:
    from audit_panel_alignment import require_matplotlib_panel_alignment
except ImportError:
    def require_matplotlib_panel_alignment(*args, **kwargs):
        return {"verdict": "skipped_optional_QA_unavailable"}
from figstyle import COL, MM, add_panel_label, gridspec_mm, secondary_rc, tint  # noqa: E402

OUT = HERE.parent / "outputs" / "figures"
OUT.mkdir(parents=True, exist_ok=True)
QA = OUT / "qa"
NAME = "fig1_concept"

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
LEFT, RIGHT, TOP, BOTTOM = 10.0, 1.5, 6.5, 1.5
COL_GUT = 10.0
PANEL_W = (FIG_WIDTH_MM - LEFT - RIGHT - 2 * COL_GUT) / 3   # 49.5 mm
PANEL_H = 56.0
FIG_HEIGHT_MM = TOP + PANEL_H + BOTTOM

INK = COL["ink"]
ROAD = tint(COL["bluegrey"], 0.55)
CAR = tint(COL["ink"], 0.55)
SQ = 1.8        # side of a log square (mm)
SQ_GAP = 0.5
DASH = (0, (1.6, 1.0))


# ---------------------------------------------------------------- drawing primitives (data units = mm)
def road(ax, x0, x1, yc, h=4.0):
    ax.add_patch(Rectangle((x0, yc - h / 2), x1 - x0, h, facecolor=ROAD, edgecolor="none", zorder=1))
    ax.plot([x0 + 0.8, x1 - 0.8], [yc, yc], color="white", lw=0.6, ls=(0, (3, 2.5)),
            solid_capstyle="butt", zorder=1.5)


def vehicle(ax, x, y, colour, w=2.1, h=1.25, roof=False):
    ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h, boxstyle="round,pad=0,rounding_size=0.35",
                                facecolor=colour, edgecolor="none", zorder=4))
    if roof:  # taxi roof sign
        ax.add_patch(Rectangle((x - 0.5, y + h / 2), 1.0, 0.45, facecolor=colour, edgecolor="none", zorder=4))


def camera(ax, x_body, y_body, colour, pole_x, pole_y0, wedge):
    """Gantry camera: pole, arm, body with lens and a translucent field of view."""
    arm_y = y_body + 1.15
    mount = tint(INK, 0.75)
    ax.plot([pole_x, pole_x], [pole_y0, arm_y], color=mount, lw=0.8, solid_capstyle="butt", zorder=3)
    ax.plot([pole_x, x_body], [arm_y, arm_y], color=mount, lw=0.8, solid_capstyle="butt", zorder=3)
    ax.add_patch(Polygon(wedge, closed=True, facecolor=colour, edgecolor="none", alpha=0.18, zorder=2))
    ax.add_patch(FancyBboxPatch((x_body - 1.4, y_body - 0.8), 2.8, 1.6, boxstyle="round,pad=0,rounding_size=0.3",
                                facecolor=colour, edgecolor="none", zorder=5))
    ax.add_patch(Circle((x_body - 0.65, y_body), 0.42, facecolor="white", edgecolor="none", zorder=6))


def log_square(ax, x, y, kind, colour):
    """kind 'record' = filled square; 'missed' = open dashed square (a passage without a record)."""
    if kind == "record":
        ax.add_patch(Rectangle((x, y), SQ, SQ, facecolor=colour, edgecolor="none", zorder=4))
    else:
        ax.add_patch(Rectangle((x + 0.15, y + 0.15), SQ - 0.3, SQ - 0.3, facecolor="white", edgecolor=colour,
                               lw=0.65, ls=DASH, zorder=4))


def text(ax, x, y, s, size=FS_NOTE, **kw):
    kw.setdefault("ha", "center")
    kw.setdefault("va", "center")
    kw.setdefault("color", INK)
    return ax.text(x, y, s, fontsize=size, **kw)


def blank(ax):
    ax.set_xlim(0, PANEL_W)
    ax.set_ylim(0, PANEL_H)
    ax.set_axis_off()


# ---------------------------------------------------------------- panel a
def panel_a(ax):
    blank(ax)
    text(ax, PANEL_W / 2, 52.6, "Records = traffic × capture", size=FS_BODY, fontweight="bold")
    text(ax, 12.0, 47.6, "Passing vehicles")
    text(ax, 33.6, 47.6, "Camera log")
    text(ax, 44.6, 47.6, "Records")

    rows = [  # label, vehicles, camera colour, records, passages without a record, road centre
        ("Baseline day", 10, COL["blue"], 10, 0, 39.0),
        ("Fewer vehicles", 5, COL["blue"], 5, 0, 26.0),
        ("Missed vehicles", 10, COL["red"], 5, 5, 13.0),
    ]
    lanes_10 = [(2.0, 0.95), (4.2, -0.95), (6.4, 0.95), (8.6, -0.95), (10.8, 0.95), (13.0, -0.95),
                (15.2, 0.95), (17.4, -0.95), (19.6, 0.95), (21.8, -0.95)]
    lanes_5 = [(2.6, 0.95), (7.0, -0.95), (11.4, 0.95), (15.8, -0.95), (20.2, 0.95)]
    xs_log = [28.8 + k * (SQ + SQ_GAP) for k in range(5)]
    for label, n_veh, cam_col, n_rec, n_miss, yc in rows:
        text(ax, 0.0, yc + 4.9, label, size=FS_TICK, ha="left")
        road(ax, 0.0, 24.0, yc)
        for x, dy in (lanes_10 if n_veh == 10 else lanes_5):
            vehicle(ax, x, yc + dy, CAR)
        camera(ax, x_body=21.6, y_body=yc + 4.5, colour=cam_col, pole_x=24.9, pole_y0=yc - 2.0,
               wedge=[(20.95, yc + 3.75), (16.6, yc + 2.0), (22.4, yc + 2.0)])
        kinds = ["record"] * n_rec + ["missed"] * n_miss
        for k, kind in enumerate(kinds):
            row, col = divmod(k, 5)
            y = yc + 0.25 if row == 0 else yc - 0.25 - SQ
            log_square(ax, xs_log[col], y, kind, COL["blue"] if kind == "record" else COL["red"])
        text(ax, 44.6, yc, str(n_rec), size=FS_BODY, fontweight="bold")

    # rows 2 and 3 leave the same count
    xb = 47.2
    ax.plot([xb - 0.6, xb, xb, xb - 0.6], [26.0, 26.0, 13.0, 13.0], color=INK, lw=0.6, zorder=3)
    text(ax, xb + 1.7, 19.5, "Same count", rotation=90, rotation_mode="anchor")

    # key
    log_square(ax, 0.0, 3.3, "record", COL["blue"])
    text(ax, 2.6, 4.2, "Record", ha="left")
    log_square(ax, 13.6, 3.3, "missed", COL["red"])
    text(ax, 16.2, 4.2, "Passage without a record", ha="left")


# ---------------------------------------------------------------- panel b
def panel_b(ax):
    blank(ax)
    yc = 32.0
    road(ax, 0.0, PANEL_W, yc, h=5.0)

    # key
    ax.add_patch(Circle((0.9, 50.6), 0.42, facecolor=COL["teal"], edgecolor="none", zorder=4))
    text(ax, 2.2, 50.6, "GPS fix", ha="left")
    ax.add_patch(Circle((13.9, 50.6), 0.9, facecolor="white", edgecolor=COL["teal"], lw=0.8, zorder=4))
    text(ax, 15.6, 50.6, "Inferred passage", ha="left")

    # the taxi trace: fixes, the path between them, the taxi
    fixes = [(1.6, 0.3), (6.6, -0.2), (10.9, 0.4), (17.5, -0.3), (22.5, 0.2), (27.8, -0.4), (32.4, 0.3),
             (39.0, -0.1)]
    taxi_x = 45.4
    path_x = [x for x, _ in fixes] + [taxi_x]
    path_y = [yc + dy for _, dy in fixes] + [yc]
    ax.plot(path_x, path_y, color=COL["teal"], lw=0.6, alpha=0.85, zorder=3)
    for x, dy in fixes:
        ax.add_patch(Circle((x, yc + dy), 0.42, facecolor=COL["teal"], edgecolor="none", zorder=5))
    vehicle(ax, taxi_x, yc, COL["teal"], w=3.4, h=1.9, roof=True)

    cams = [(14.0, COL["blue"], "Working camera", ["record", "record", "record", "taxi"], "Taxi recorded"),
            (35.5, COL["red"], "Failed camera", ["taxi-missed"], "Taxi passed, no record")]
    for x, colour, name, log, outcome in cams:
        camera(ax, x_body=x, y_body=38.7, colour=colour, pole_x=x + 3.1, pole_y0=yc + 2.5,
               wedge=[(x - 0.65, 37.95), (x - 2.4, yc + 0.9), (x + 2.0, yc + 0.9)])
        text(ax, x, 43.4, name, color=colour)
        y_pass = yc + 0.05 * (-1 if x < 20 else 1)
        ax.add_patch(Circle((x, y_pass), 0.9, facecolor="white", edgecolor=COL["teal"], lw=0.8, zorder=6))
        ax.add_patch(FancyArrowPatch((x, yc - 1.15), (x, 27.4), arrowstyle="-|>,head_length=1.6,head_width=1.0",
                                     mutation_scale=1.0, lw=0.5, color=tint(INK, 0.6), zorder=3,
                                     shrinkA=0, shrinkB=0))
        width = len(log) * SQ + (len(log) - 1) * SQ_GAP
        for k, kind in enumerate(log):
            xs = x - width / 2 + k * (SQ + SQ_GAP)
            if kind == "record":
                log_square(ax, xs, 25.0, "record", COL["blue"])
            elif kind == "taxi":
                log_square(ax, xs, 25.0, "record", COL["teal"])
            else:
                log_square(ax, xs, 25.0, "missed", COL["teal"])
        text(ax, x, 22.2, outcome)

    # capture as a ratio of two taxi counts
    text(ax, 0.6, 13.0, "Capture =", size=FS_TICK, ha="left")
    xm = 29.0
    text(ax, xm, 14.8, "Taxi passages recorded", size=FS_TICK)
    ax.plot([14.8, 43.2], [13.0, 13.0], color=INK, lw=0.6, solid_capstyle="butt", zorder=3)
    text(ax, xm, 11.2, "GPS-inferred taxi passages", size=FS_TICK)
    text(ax, PANEL_W / 2, 5.0, "per camera, control period and event days")


# ---------------------------------------------------------------- panel c
def panel_c(ax):
    blank(ax)
    # composition of baseline records
    text(ax, PANEL_W / 2, 54.6, "Share of baseline records")
    y0, h, split = 49.6, 3.2, 0.64 * PANEL_W
    ax.add_patch(Rectangle((0.0, y0), split, h, facecolor=COL["blue"], edgecolor="none", zorder=2))
    ax.add_patch(Rectangle((split, y0), PANEL_W - split, h, facecolor=COL["orange"], edgecolor="none", zorder=2))
    text(ax, split / 2, y0 + h / 2, "Kept cameras", color="white")
    text(ax, (split + PANEL_W) / 2, y0 + h / 2, "Screened out")
    text(ax, split / 2, 47.3, "1 − w")
    text(ax, (split + PANEL_W) / 2, 47.3, "w")
    text(ax, PANEL_W / 2, 43.6, "Network = (1 − w) · kept + w · x", size=FS_TICK)
    text(ax, PANEL_W / 2, 40.2, "x: unseen recovery of screened-out roads")
    text(ax, PANEL_W / 2, 37.3, "Assumes kept cameras capture as at baseline")

    # three situations in the encoding of the break-even panel
    xs, lo, hi = [20.0, 32.0, 44.0], 14.0, 26.0
    dots = [10.0, 20.0, 30.6]
    verdicts = [("Holds", "either way"), ("Depends", "on x"), ("Fails", "either way")]
    for x, yd, (v1, v2) in zip(xs, dots, verdicts):
        ax.add_patch(Rectangle((x - 1.1, lo), 2.2, hi - lo, facecolor=tint(COL["orange"], 0.45),
                               edgecolor="none", zorder=2))
        ax.plot([x - 1.6, x + 1.6], [lo, lo], color=COL["red"], lw=1.4, solid_capstyle="butt", zorder=3)
        ax.plot([x - 1.6, x + 1.6], [hi, hi], color=COL["blue"], lw=1.4, solid_capstyle="butt", zorder=3)
        ax.add_patch(Circle((x, yd), 0.85, facecolor=INK, edgecolor="none", zorder=4))
        text(ax, x, 5.0, v1)
        text(ax, x, 2.4, v2)
    text(ax, 17.6, hi, "As kept roads", color=COL["blue"], ha="right")
    text(ax, 17.6, lo, "Own record ratio", color=COL["red"], ha="right")
    text(ax, 17.6, dots[0], "x needed for θ", ha="right")


def main():
    mpl.rcParams.update(PUBLICATION_RC)
    mpl.rcParams.update(secondary_rc(FS_BODY, FS_TICK))
    fig = plt.figure(figsize=(FIG_WIDTH_MM * MM, FIG_HEIGHT_MM * MM))
    gs = gridspec_mm(fig, 1, 3, width_mm=FIG_WIDTH_MM, height_mm=FIG_HEIGHT_MM, left=LEFT, right=RIGHT,
                     top=TOP, bottom=BOTTOM, col_gutter=COL_GUT, row_gutter=0.0, panel_w=PANEL_W,
                     panel_h_avg=PANEL_H)
    ax_a, ax_b, ax_c = (fig.add_subplot(gs[0, k]) for k in range(3))
    panel_a(ax_a)
    panel_b(ax_b)
    panel_c(ax_c)
    add_panel_label(ax_a, "a", "Same record count, two causes", FS_LETTER, FS_BODY)
    add_panel_label(ax_b, "b", "Taxis as independent witnesses", FS_LETTER, FS_BODY)
    add_panel_label(ax_c, "c", "A judgement with its condition", FS_LETTER, FS_BODY)

    QA.mkdir(exist_ok=True)
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
