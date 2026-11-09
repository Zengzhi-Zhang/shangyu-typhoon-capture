"""Shared map layers for the Shangyu figures (Fig. 1 and Fig. 4).

Web Mercator (EPSG:3857) throughout. Every vector layer is clipped to its map
frame before drawing, so vector exports hold no hidden off-frame paths.
"""
from __future__ import annotations

import glob
import json
from shapely.geometry import shape
import math
import re
from pathlib import Path

import numpy as np
import geopandas as gpd
import tifffile
import matplotlib.patheffects as pe
from matplotlib.collections import LineCollection
from matplotlib.colors import LightSource, to_rgb
from matplotlib.lines import Line2D
from matplotlib.path import Path as MplPath
from pyproj import Transformer
from shapely.geometry import LineString, box

from figstyle import COL

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
EXT = HERE.parent / "public_layers"

TO_MERC = Transformer.from_crs(4326, 3857, always_xy=True)
HALO = [pe.withStroke(linewidth=1.6, foreground="white")]
SEA = "#DCE6EC"
ROAD = "#9AA4AA"
BAIGUAN = (120.868954, 30.034191)  # OSM town centre used for the distance rings


def extent_for(cx, cy, half_w, frame):
    """Map extent centred on (cx, cy) whose aspect matches a frame (l, b, w, h) in mm."""
    half_h = half_w * frame[3] / frame[2]
    return (cx - half_w, cx + half_w, cy - half_h, cy + half_h)


def district_extent(boundary, frame, pad_m=1600.0):
    """Extent showing the whole district at the height of the frame."""
    bx = boundary.bounds
    half_h = (bx[3] - bx[1]) / 2 + pad_m
    return extent_for((bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2, half_h * frame[2] / frame[3], frame)


# ---------------------------------------------------------------- clipping helpers
def clip_lines(lines, ext):
    """Clip polylines (arrays of x, y) to a rectangular extent."""
    frame = box(ext[0], ext[2], ext[1], ext[3])
    out = []
    for xy in lines:
        if len(xy) < 2:
            continue
        g = LineString(xy).intersection(frame)
        for part in getattr(g, "geoms", [g]):
            if part.geom_type == "LineString" and not part.is_empty:
                out.append(np.asarray(part.coords))
    return out


def clip_polygon_parts(geom, ext):
    """Polygon parts of a (multi)polygon clipped to a rectangular extent."""
    g = geom.intersection(box(ext[0], ext[2], ext[1], ext[3]))
    return [p for p in getattr(g, "geoms", [g]) if p.geom_type == "Polygon" and not p.is_empty]


def polygon_rings(geom):
    for p in getattr(geom, "geoms", [geom]):
        yield np.asarray(p.exterior.coords)


def boundary_lines(boundary):
    return [ring[:, :2] for ring in polygon_rings(boundary)]


def points_inside(boundary, x, y):
    inside = np.zeros(len(x), dtype=bool)
    for ring in polygon_rings(boundary):
        inside |= MplPath(ring[:, :2]).contains_points(np.column_stack([x, y]))
    return inside


# ---------------------------------------------------------------- data
def load_dem():
    # Hillshade values are a lossless public raster, not a restricted DEM/cache.
    return json.loads((EXT / "terrain_manifest.json").read_text(encoding="utf-8")), None


def load_boundary():
    layer = json.loads((EXT / "osm_shangyu_boundary.geojson").read_text(encoding="utf-8"))
    boundary = shape(layer["features"][0]["geometry"])
    return gpd.GeoSeries([boundary],crs=4326).to_crs(3857).iloc[0]


def load_roads():
    layer = json.loads((EXT / "osm_major_roads.geojson").read_text(encoding="utf-8"))
    geometries = [shape(f["geometry"]) for f in layer["features"]]
    projected = gpd.GeoSeries(geometries,crs=4326).to_crs(3857)
    return [np.asarray(part.coords)[:, :2] for geom in projected for part in getattr(geom,"geoms",[geom]) if part.geom_type=="LineString"]


# ---------------------------------------------------------------- drawing
def terrain_rgb(dem, dem_ext, boundary, ext, step):
    """Hillshade cropped to a map extent; land outside the district is faded."""
    px0 = (dem_ext[1] - dem_ext[0]) / dem.shape[1]
    c0 = max(int((ext[0] - dem_ext[0]) / px0) - 2, 0)
    c1 = min(int((ext[1] - dem_ext[0]) / px0) + 2, dem.shape[1])
    r0 = max(int((dem_ext[3] - ext[3]) / px0) - 2, 0)
    r1 = min(int((dem_ext[3] - ext[2]) / px0) + 2, dem.shape[0])
    d = dem[r0:r1:step, c0:c1:step]
    crop_ext = (dem_ext[0] + c0 * px0, dem_ext[0] + c1 * px0, dem_ext[3] - r1 * px0, dem_ext[3] - r0 * px0)
    px = px0 * step
    hs = LightSource(azdeg=315, altdeg=42).hillshade(np.maximum(d, 0), vert_exag=2.5, dx=px, dy=px)
    v = np.clip(1.0 - 0.55 * (math.sin(math.radians(42)) - hs), 0.66, 1.0)
    rgb = np.dstack([v, v, v])
    sea = d <= 0
    xs = crop_ext[0] + (np.arange(d.shape[1]) + 0.5) * (crop_ext[1] - crop_ext[0]) / d.shape[1]
    ys = crop_ext[3] - (np.arange(d.shape[0]) + 0.5) * (crop_ext[3] - crop_ext[2]) / d.shape[0]
    gx, gy = np.meshgrid(xs, ys)
    inside = points_inside(boundary, gx.ravel(), gy.ravel()).reshape(d.shape)
    outside_land = ~inside & ~sea
    rgb[outside_land] = 0.45 * rgb[outside_land] + 0.55 * np.array(to_rgb(COL["panel"]))
    rgb[sea] = np.array(to_rgb(SEA))
    return rgb, crop_ext


def draw_terrain(ax, dem, dem_ext, boundary, ext, step):
    candidates = [r for r in dem["rasters"] if r["step"]==step and np.allclose(r["plot_extent"],ext,rtol=0,atol=1e-6)]
    if len(candidates)!=1:
        raise ValueError("Public hillshade frame not registered")
    item = candidates[0]
    rgb = tifffile.imread(EXT / item["file"])
    ax.imshow(rgb,extent=item["raster_extent"],origin="upper",interpolation="bilinear",zorder=0)


def map_frame(ax, ext):
    ax.set_xlim(ext[0], ext[1])
    ax.set_ylim(ext[2], ext[3])
    ax.set_xticks([])
    ax.set_yticks([])
    for side in ("left", "right", "top", "bottom"):
        ax.spines[side].set_visible(True)
        ax.spines[side].set_linewidth(0.5)
        ax.spines[side].set_color(COL["ink"])


def merc_per_km(lat_deg: float) -> float:
    """Web Mercator metres per true kilometre at a latitude."""
    return 1000.0 / math.cos(math.radians(lat_deg))


def scale_bar(ax, ext, km, lat, fontsize, x_frac=0.06, y_frac=0.035):
    length = km * merc_per_km(lat)
    bx, by = ext[0] + x_frac * (ext[1] - ext[0]), ext[2] + y_frac * (ext[3] - ext[2])
    ax.add_line(Line2D([bx, bx + length], [by, by], color=COL["ink"], lw=1.0, solid_capstyle="butt",
                       zorder=12))
    ax.text(bx + length / 2, by + 0.014 * (ext[3] - ext[2]), f"{km:g} km", ha="center", va="bottom",
            fontsize=fontsize, zorder=12, path_effects=HALO)


def north_arrow(ax, fontsize, x_frac=0.93, y_frac=0.035):
    ax.text(x_frac, y_frac, "N", transform=ax.transAxes, ha="center", va="bottom", fontsize=fontsize,
            zorder=12, path_effects=HALO)
    ax.annotate("", xy=(x_frac, y_frac + 0.075), xytext=(x_frac, y_frac + 0.035), xycoords="axes fraction",
                arrowprops=dict(arrowstyle="-|>", color=COL["ink"], lw=0.6, mutation_scale=5,
                                shrinkA=0, shrinkB=0), zorder=12)


def draw_lines(ax, lines, ext, colour, lw, zorder):
    ax.add_collection(LineCollection(clip_lines(lines, ext), colors=colour, linewidths=lw, zorder=zorder,
                                     capstyle="round"))


def baiguan_marker(ax, frame, ext, fontsize, label=None):
    x, y = TO_MERC.transform(*BAIGUAN)
    ax.plot([x], [y], marker="*", ms=5.5, mfc=COL["ink"], mec="white", mew=0.4, zorder=10, ls="none")
    if label is not None:
        m_per_mm = (ext[1] - ext[0]) / frame[2]
        ax.text(x + label[0] * m_per_mm, y + label[1] * m_per_mm, "Baiguan", fontsize=fontsize,
                ha="left", va="center", zorder=10, path_effects=HALO)
