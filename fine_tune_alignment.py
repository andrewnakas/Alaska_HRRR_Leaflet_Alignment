#!/usr/bin/env python3
"""
Fine-tuning system for HRRR Alaska alignment.
Edit alignment_config.json to adjust positioning, then run this script.
"""

import json
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from datetime import datetime, timedelta
from pathlib import Path
import subprocess
import sys

def install_if_needed(package):
    try:
        __import__(package.replace('-', '_'))
    except ImportError:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q', '--break-system-packages', package])

def load_config():
    """Load fine-tuning configuration."""
    with open('alignment_config.json', 'r') as f:
        config = json.load(f)
    return config['adjustments']

def apply_adjustments(bounds, adjustments):
    """Apply fine-tuning adjustments to bounds."""
    west, south, east, north = bounds

    # Apply specific edge adjustments
    west += adjustments.get('west_adjustment', 0.0)
    east += adjustments.get('east_adjustment', 0.0)
    south += adjustments.get('south_adjustment', 0.0)
    north += adjustments.get('north_adjustment', 0.0)

    # Calculate center
    center_lon = (west + east) / 2
    center_lat = (south + north) / 2

    # Apply scale adjustments
    lon_scale = adjustments.get('lon_scale', 1.0)
    lat_scale = adjustments.get('lat_scale', 1.0)

    lon_span = (east - west) * lon_scale
    lat_span = (north - south) * lat_scale

    west = center_lon - lon_span / 2
    east = center_lon + lon_span / 2
    south = center_lat - lat_span / 2
    north = center_lat + lat_span / 2

    # Apply offset adjustments
    lon_offset = adjustments.get('lon_offset', 0.0)
    lat_offset = adjustments.get('lat_offset', 0.0)

    west += lon_offset
    east += lon_offset
    south += lat_offset
    north += lat_offset

    return [west, south, east, north]

def main():
    print("=" * 80)
    print("HRRR Alaska Fine-Tuning System")
    print("=" * 80)
    print()

    # Load configuration
    print("Loading alignment_config.json...")
    try:
        adjustments = load_config()
        print("✓ Configuration loaded")
        print()
        print("Active adjustments:")
        for key, value in adjustments.items():
            if value != 0.0:
                print(f"  {key}: {value}")
        if all(v == 0.0 for v in adjustments.values()):
            print("  (No adjustments - using defaults)")
        print()
    except Exception as e:
        print(f"ERROR loading config: {e}")
        print("Using default adjustments (no changes)")
        adjustments = {}

    install_if_needed('rasterio')
    install_if_needed('pyproj')

    from herbie import Herbie
    import rasterio
    from rasterio.transform import from_bounds
    from rasterio.warp import reproject, Resampling
    from rasterio.crs import CRS

    print("Searching for latest HRRR Alaska GRIB2...")

    H = None
    for hours_ago in range(0, 12):
        try:
            dt = datetime.utcnow() - timedelta(hours=hours_ago)
            dt = dt.replace(minute=0, second=0, microsecond=0)
            H = Herbie(dt, model="hrrrak", product="sfc", fxx=0)
            if H.grib:
                print(f"✓ Found: {H.model} {H.date} F{H.fxx:02d}")
                break
            else:
                H = None
        except Exception:
            continue

    if not H or not H.grib:
        print("ERROR: Could not find HRRR Alaska GRIB2")
        return

    print()
    print("Loading GRIB2 data...")

    try:
        ds = H.xarray("REFC:entire atmosphere", verbose=False)
        variable = "REFC"
        print(f"✓ Loaded REFC")
    except Exception:
        try:
            ds = H.xarray("TMP:2 m", verbose=False)
            variable = "TMP"
            print(f"✓ Loaded TMP:2 m")
        except Exception as e:
            print(f"ERROR: {e}")
            return

    lat_2d = ds.latitude.values
    lon_2d = ds.longitude.values
    ny, nx = lat_2d.shape

    data_var = [v for v in ds.data_vars][0]
    data = ds[data_var].values

    print(f"Data: {data_var}, Grid: {ny} x {nx}")
    print()

    # Normalize longitude
    lon_normalized = np.where(lon_2d > 180, lon_2d - 360, lon_2d)

    # Get base extent
    lat_min, lat_max = lat_2d.min(), lat_2d.max()
    lon_min_raw, lon_max_raw = lon_normalized.min(), lon_normalized.max()

    # Convert to continuous
    lon_continuous = np.where(lon_normalized > 0, lon_normalized - 360, lon_normalized)
    lon_min = lon_continuous.min()
    lon_max = lon_continuous.max()

    base_bounds = [lon_min, lat_min, lon_max, lat_max]

    print(f"Base bounds (before adjustments):")
    print(f"  West:  {base_bounds[0]:.4f}°")
    print(f"  South: {base_bounds[1]:.4f}°")
    print(f"  East:  {base_bounds[2]:.4f}°")
    print(f"  North: {base_bounds[3]:.4f}°")
    print(f"  Span: {base_bounds[2] - base_bounds[0]:.2f}° × {base_bounds[3] - base_bounds[1]:.2f}°")
    print()

    # Apply adjustments
    adjusted_bounds = apply_adjustments(base_bounds, adjustments)

    print(f"Adjusted bounds (after fine-tuning):")
    print(f"  West:  {adjusted_bounds[0]:.4f}° (Δ {adjusted_bounds[0] - base_bounds[0]:+.4f}°)")
    print(f"  South: {adjusted_bounds[1]:.4f}° (Δ {adjusted_bounds[1] - base_bounds[1]:+.4f}°)")
    print(f"  East:  {adjusted_bounds[2]:.4f}° (Δ {adjusted_bounds[2] - base_bounds[2]:+.4f}°)")
    print(f"  North: {adjusted_bounds[3]:.4f}° (Δ {adjusted_bounds[3] - base_bounds[3]:+.4f}°)")
    print(f"  Span: {adjusted_bounds[2] - adjusted_bounds[0]:.2f}° × {adjusted_bounds[3] - adjusted_bounds[1]:.2f}°")
    print()

    # Define source projection
    src_crs = CRS.from_proj4(
        "+proj=stere +lat_0=90 +lon_0=225 +lat_ts=60 +a=6371229 +b=6371229 +units=m +no_defs"
    )

    # Get native projection bounds
    from pyproj import Proj
    p = Proj(src_crs)

    x_coords, y_coords = [], []
    for i in range(0, ny, ny//20):
        for j in range(0, nx, nx//20):
            x, y = p(lon_continuous[i, j], lat_2d[i, j])
            x_coords.append(x)
            y_coords.append(y)

    x_ll = min(x_coords) - 1500
    x_ur = max(x_coords) + 1500
    y_ll = min(y_coords) - 1500
    y_ur = max(y_coords) + 1500

    src_transform = from_bounds(x_ll, y_ll, x_ur, y_ur, nx, ny)

    # Reproject with adjusted bounds
    print("Reprojecting with adjusted bounds...")

    dst_crs = CRS.from_epsg(4326)

    lon_min_adj, lat_min_adj, lon_max_adj, lat_max_adj = adjusted_bounds
    resolution = 0.03
    dst_width = int((lon_max_adj - lon_min_adj) / resolution)
    dst_height = int((lat_max_adj - lat_min_adj) / resolution)

    print(f"Destination grid: {dst_height} x {dst_width}")

    dst_transform = from_bounds(lon_min_adj, lat_min_adj, lon_max_adj, lat_max_adj,
                                dst_width, dst_height)
    dst_data = np.zeros((dst_height, dst_width), dtype=np.float32)

    reproject(
        source=data,
        destination=dst_data,
        src_transform=src_transform,
        src_crs=src_crs,
        dst_transform=dst_transform,
        dst_crs=dst_crs,
        resampling=Resampling.bilinear
    )

    print("✓ Reprojection complete!")
    print()

    # Create visualization
    print(f"Creating visualization...")

    if variable == "REFC":
        colors = [
            (0.0, (0, 0, 0, 0)),
            (0.15, (0, 255, 255)),
            (0.3, (0, 0, 255)),
            (0.45, (0, 255, 0)),
            (0.6, (255, 255, 0)),
            (0.75, (255, 165, 0)),
            (0.9, (255, 0, 0)),
            (1.0, (255, 0, 255))
        ]
        cmap = LinearSegmentedColormap.from_list('refc',
            [(pos, tuple(c/255 if i < 3 else c for i, c in enumerate(color)))
             for pos, color in colors])
        vmin, vmax = 0, 75
        dst_data = np.ma.masked_less(dst_data, 5)
    else:
        colors = ['#0000ff', '#00ffff', '#00ff00', '#ffff00', '#ff0000']
        cmap = LinearSegmentedColormap.from_list('temp', colors)
        vmin, vmax = -20, 30

    fig, ax = plt.subplots(figsize=(13, 9), dpi=100)
    ax.set_position([0, 0, 1, 1])
    ax.axis('off')

    ax.imshow(dst_data, cmap=cmap, aspect='auto',
              extent=adjusted_bounds,
              vmin=vmin, vmax=vmax, interpolation='bilinear',
              origin='lower')

    images_dir = Path('images')
    images_dir.mkdir(exist_ok=True)

    plt.savefig(images_dir / 'hrrr_continuous.png', bbox_inches='tight',
                pad_inches=0, transparent=True, dpi=100)
    plt.close()

    print(f"✓ Saved images/hrrr_continuous.png")
    print()

    # Create boundary polygon
    def create_boundary(lat_2d, lon_2d, points_per_edge=100):
        ny, nx = lat_2d.shape
        lon_cont = np.where(lon_2d > 180, lon_2d - 360, lon_2d)
        lon_cont = np.where(lon_cont > 0, lon_cont - 360, lon_cont)

        boundary = []
        for i in np.linspace(0, nx - 1, points_per_edge, dtype=int):
            boundary.append({"lat": float(lat_2d[0, i]), "lon": float(lon_cont[0, i])})
        for i in np.linspace(1, ny - 1, points_per_edge, dtype=int):
            boundary.append({"lat": float(lat_2d[i, -1]), "lon": float(lon_cont[i, -1])})
        for i in np.linspace(nx - 2, 0, points_per_edge, dtype=int):
            boundary.append({"lat": float(lat_2d[-1, i]), "lon": float(lon_cont[-1, i])})
        for i in np.linspace(ny - 2, 1, points_per_edge, dtype=int):
            boundary.append({"lat": float(lat_2d[i, 0]), "lon": float(lon_cont[i, 0])})

        return boundary

    boundary = create_boundary(lat_2d, lon_2d)

    # Calculate alignment metrics
    boundary_lons = [p['lon'] for p in boundary]
    boundary_lats = [p['lat'] for p in boundary]

    boundary_west = min(boundary_lons)
    boundary_east = max(boundary_lons)
    boundary_south = min(boundary_lats)
    boundary_north = max(boundary_lats)

    west_diff = abs(boundary_west - adjusted_bounds[0])
    south_diff = abs(boundary_south - adjusted_bounds[1])
    east_diff = abs(boundary_east - adjusted_bounds[2])
    north_diff = abs(boundary_north - adjusted_bounds[3])
    total_diff = west_diff + south_diff + east_diff + north_diff

    print("Alignment Analysis:")
    print(f"  Boundary vs Image bounds:")
    print(f"    West:  {west_diff:.4f}° difference")
    print(f"    South: {south_diff:.4f}° difference")
    print(f"    East:  {east_diff:.4f}° difference")
    print(f"    North: {north_diff:.4f}° difference")
    print(f"    Total: {total_diff:.4f}° difference")
    print()

    if total_diff < 0.1:
        print("  ✓ EXCELLENT alignment!")
    elif total_diff < 0.5:
        print("  ✓ Good alignment")
    elif total_diff < 2.0:
        print("  ⚠ Fair alignment - consider fine-tuning")
    else:
        print("  ⚠ Poor alignment - needs adjustment")
    print()

    # Suggest adjustments
    if total_diff > 0.1:
        print("Suggested adjustments for alignment_config.json:")
        if west_diff > 0.05:
            suggested = adjusted_bounds[0] + (boundary_west - adjusted_bounds[0])
            print(f"  \"west_adjustment\": {suggested - base_bounds[0]:.4f}")
        if east_diff > 0.05:
            suggested = adjusted_bounds[2] + (boundary_east - adjusted_bounds[2])
            print(f"  \"east_adjustment\": {suggested - base_bounds[2]:.4f}")
        if south_diff > 0.05:
            suggested = adjusted_bounds[1] + (boundary_south - adjusted_bounds[1])
            print(f"  \"south_adjustment\": {suggested - base_bounds[1]:.4f}")
        if north_diff > 0.05:
            suggested = adjusted_bounds[3] + (boundary_north - adjusted_bounds[3])
            print(f"  \"north_adjustment\": {suggested - base_bounds[3]:.4f}")
        print()

    output = {
        "continuous": {
            "image_url": "images/hrrr_continuous.png",
            "bounds": adjusted_bounds
        },
        "boundary_polygon": boundary,
        "_metadata": {
            "generated": datetime.utcnow().isoformat() + "Z",
            "method": "fine_tuned_continuous_longitude",
            "source": f"NOAA HRRR Alaska - {variable}",
            "model": H.model,
            "date": H.date.isoformat(),
            "variable": variable,
            "source_grid_shape": [ny, nx],
            "reprojected_grid_shape": [dst_height, dst_width],
            "base_bounds": base_bounds,
            "adjusted_bounds": adjusted_bounds,
            "adjustments_applied": adjustments,
            "alignment_error": {
                "west": float(west_diff),
                "south": float(south_diff),
                "east": float(east_diff),
                "north": float(north_diff),
                "total": float(total_diff)
            },
            "longitude_span": f"{adjusted_bounds[2] - adjusted_bounds[0]:.1f}°",
            "note": "Fine-tuned alignment using alignment_config.json"
        }
    }

    with open("test-data.json", 'w') as f:
        json.dump(output, f, indent=2)

    print("✓ Saved to test-data.json")
    print()
    print("=" * 80)
    print("FINE-TUNING COMPLETE!")
    print("=" * 80)
    print(f"Total alignment error: {total_diff:.4f}°")
    print()
    print("To further adjust:")
    print("1. Edit alignment_config.json with suggested values")
    print("2. Run: python3 fine_tune_alignment.py")
    print("3. Check browser: refresh GitHub Pages")
    print("4. Repeat until perfect!")
    print()

if __name__ == "__main__":
    main()
