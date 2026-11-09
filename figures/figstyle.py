"""Shared colour vocabulary and layout helpers for the Shangyu typhoon figures.

Each figure script owns its publication rcParams block and its exports so that
it can be audited on its own; this module only holds the fixed colour mapping,
secondary rcParams, panel-label and grid helpers, and the alignment gate.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import matplotlib as mpl

mpl.use("Agg")
from matplotlib.colors import to_rgb  # noqa: E402
from matplotlib.transforms import ScaledTranslation  # noqa: E402

try:
    from audit_panel_alignment import require_matplotlib_panel_alignment
except ImportError:
    def require_matplotlib_panel_alignment(*args, **kwargs):
        return {"verdict": "skipped_optional_QA_unavailable"}

MM = 1 / 25.4  # inches per millimetre

# Colour vocabulary (fixed across figures)
COL = {
    "blue": "#3B6B8A",      # primary: stable cameras, health-screened ratio
    "teal": "#5B9B91",      # comparison: taxi probe, online-set ratio
    "red": "#C66B63",       # key result: failed cameras, all-camera record ratio
    "orange": "#D9A35F",    # secondary emphasis: partial capture, fixed stable set
    "purple": "#8C82A6",    # auxiliary estimators
    "bluegrey": "#B7C9D3",  # reference lines and light fills
    "ink": "#333333",       # text and axes
    "panel": "#F2F4F5",     # zone backgrounds
}

LETTER_DX_MM = -9.0   # panel letter offset from the plot-area top-left corner
TITLE_DX_MM = -5.6
LABEL_DY_MM = 2.6


def secondary_rc(fs_body: float, fs_tick: float) -> dict:
    return {
        "axes.labelsize": fs_body,
        "axes.titlesize": fs_body,
        "xtick.labelsize": fs_tick,
        "ytick.labelsize": fs_tick,
        "legend.fontsize": fs_tick,
        "axes.linewidth": 0.6,
        "axes.facecolor": "none",
        "axes.edgecolor": COL["ink"],
        "axes.labelcolor": COL["ink"],
        "axes.labelpad": 2.5,
        "text.color": COL["ink"],
        "xtick.color": COL["ink"],
        "ytick.color": COL["ink"],
        "xtick.major.width": 0.6,
        "ytick.major.width": 0.6,
        "xtick.major.size": 2.5,
        "ytick.major.size": 2.5,
        "xtick.major.pad": 1.8,
        "ytick.major.pad": 1.8,
        "axes.spines.right": False,
        "axes.spines.top": False,
        "legend.frameon": False,
        "legend.handletextpad": 0.4,
        "legend.borderaxespad": 0.2,
        "legend.labelspacing": 0.35,
        "lines.linewidth": 1.2,
        "lines.solid_capstyle": "round",
        "lines.dash_capstyle": "round",
        "patch.linewidth": 0.6,
        "figure.dpi": 150,
        "axes.unicode_minus": True,
    }


def mm_offset(ax, dx_mm: float, dy_mm: float):
    return ax.transAxes + ScaledTranslation(dx_mm * MM, dy_mm * MM, ax.figure.dpi_scale_trans)


def add_panel_label(ax, letter: str, title: str | None, fs_letter: float, fs_title: float) -> None:
    """Bold lowercase letter and a short title, both at a fixed physical offset."""
    ax.text(0, 1, letter, transform=mm_offset(ax, LETTER_DX_MM, LABEL_DY_MM),
            fontsize=fs_letter, fontweight="bold", ha="left", va="baseline",
            color=COL["ink"], clip_on=False)
    if title:
        ax.text(0, 1, title, transform=mm_offset(ax, TITLE_DX_MM, LABEL_DY_MM),
                fontsize=fs_title, ha="left", va="baseline", color=COL["ink"], clip_on=False)


def outward_spines(ax, pts: float = 3.0, left: bool = True, bottom: bool = True) -> None:
    if left:
        ax.spines["left"].set_position(("outward", pts))
    if bottom:
        ax.spines["bottom"].set_position(("outward", pts))


def gridspec_mm(fig, nrows, ncols, *, width_mm, height_mm, left, right, top, bottom,
                col_gutter, row_gutter, panel_w, panel_h_avg, height_ratios=None):
    """GridSpec whose plot areas and gutters are fixed in millimetres."""
    return fig.add_gridspec(
        nrows, ncols,
        left=left / width_mm, right=1 - right / width_mm,
        bottom=bottom / height_mm, top=1 - top / height_mm,
        wspace=(col_gutter / panel_w) if ncols > 1 else 0.0,
        hspace=(row_gutter / panel_h_avg) if nrows > 1 else 0.0,
        height_ratios=height_ratios,
    )


def alignment_gate(fig, name: str, qa_dir: Path, **kwargs) -> dict:
    """Blocking render-time alignment audit (1.5 pt), run after the final layout."""
    qa_dir = Path(qa_dir)
    qa_dir.mkdir(parents=True, exist_ok=True)
    return require_matplotlib_panel_alignment(
        fig,
        json_out=qa_dir / f"{name}.alignment.json",
        overlay_svg=qa_dir / f"{name}.alignment.svg",
        tolerance_pt=1.5,
        gutter_tolerance_pt=1.5,
        require_panel_labels=True,
        strict=True,
        **kwargs,
    )


def tint(hex_colour: str, alpha: float):
    """Palette colour mixed with white; alpha = 1 gives the colour itself."""
    c = np.array(to_rgb(hex_colour))
    return tuple(alpha * c + (1 - alpha) * np.ones(3))


def spread_offsets(n: int, half_width: float) -> "list[float]":
    """Deterministic horizontal spread for strip plots (golden-ratio sequence)."""
    phi = 0.6180339887498949
    return [((k * phi) % 1.0 - 0.5) * 2 * half_width for k in range(n)]
