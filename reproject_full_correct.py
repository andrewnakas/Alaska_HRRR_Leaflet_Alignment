#!/usr/bin/env python3
"""
Reproject FULL HRRR Alaska extent correctly.
Uses native grid dimensions, not lat/lon extent.
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

def main():
    print("=" * 80)
    print("Reproject FULL HRRR Alaska (Using Native Grid Dimensions)")
    print("=" * 80)
    print()

    install_if_needed('rasterio')
    install_if_needed('pyproj')

    from herbie import Herbie
    import rasterio
    from rasterio.transform import from_bounds
    from rasterio.warp import reproject, Resampling, calculate_default_transform
    from rasterio.crs import CRS
    from pyproj import Proj

    print("Searching for latest HRRR Alaska GRIB2...")
    print()

    H = None
    for hours_ago in range(0, 12):
        try:
            dt = datetime.utcnow() - timedelta(hours=hours_ago)
            dt = dt.replace(minute=0, second=0, microsecond=0)
            print(f"Trying {dt.strftime('%Y-%m-%d %H:00')} UTC...")
            H = Herbie(dt, model="hrrrak", product="sfc", fxx=0)
            if H.grib:
                print(f"✓ Found: {H.model} {H.date} F{H.fxx:02d}")
                break
            else:
                H = None
        except Exception as e:
            print(f"  Error: {e}")
            continue

    if not H or not H.grib:
        print("ERROR: Could not find HRRR Alaska GRIB2")
        return

    print()
    print("Loading GRIB2 data...")
    print()

    try:
        ds = H.xarray("REFC:entire atmosphere", verbose=False)
        variable = "REFC"
        print(f"✓ Loaded REFC")
    except Exception as e:
        print(f"REFC failed: {e}")
        try:
            ds = H.xarray("TMP:2 m", verbose=False)
            variable = "TMP"
            print(f"✓ Loaded TMP:2 m")
        except Exception as e2:
            print(f"ERROR: {e2}")
            return

    lat_2d = ds.latitude.values
    lon_2d = ds.longitude.values
    ny, nx = lat_2d.shape

    data_var = [v for v in ds.data_vars][0]
    data = ds[data_var].values

    print(f"Data: {data_var}")
    print(f"  Grid: {ny} x {nx}")
    print(f"  Range: {np.nanmin(data):.2f} to {np.nanmax(data):.2f}")
    print()

    # Use HRRR Alaska grid specifications from NOAA documentation
    # Grid dimensions: 1299 x 919
    # Resolution: 3 km
    # Lower-left corner in native projection
    print("Using official HRRR Alaska grid specifications...")

    # Define projection
    proj_params = "+proj=stere +lat_0=90 +lon_0=225 +lat_ts=60 +a=6371229 +b=6371229 +units=m +no_defs"
    p = Proj(proj_params)
    src_crs = CRS.from_proj4(proj_params)

    # Get actual grid extent in native projection by sampling edge cells
    lon_norm = np.where(lon_2d > 180, lon_2d - 360, lon_2d)

    # Get corner coordinates from actual grid edges
    corners_x = []
    corners_y = []

    # Sample corners and edges
    for i in [0, -1]:
        for j in [0, -1]:
            x, y = p(lon_norm[i, j], lat_2d[i, j])
            corners_x.append(x)
            corners_y.append(y)

    # Sample edges (more points)
    for i in range(0, ny, ny//10):
        x, y = p(lon_norm[i, 0], lat_2d[i, 0])
        corners_x.append(x)
        corners_y.append(y)
        x, y = p(lon_norm[i, -1], lat_2d[i, -1])
        corners_x.append(x)
        corners_y.append(y)

    for j in range(0, nx, nx//10):
        x, y = p(lon_norm[0, j], lat_2d[0, j])
        corners_x.append(x)
        corners_y.append(y)
        x, y = p(lon_norm[-1, j], lat_2d[-1, j])
        corners_x.append(x)
        corners_y.append(y)

    x_min = min(corners_x)
    x_max = max(corners_x)
    y_min = min(corners_y)
    y_max = max(corners_y)

    # Extend by half cell (3km = 3000m)
    cell_size = 3000
    x_ll = x_min - cell_size / 2
    x_ur = x_max + cell_size / 2
    y_ll = y_min - cell_size / 2
    y_ur = y_max + cell_size / 2

    print(f"Native grid extent (meters):")
    print(f"  X: {x_ll:.0f} to {x_ur:.0f}")
    print(f"  Y: {y_ll:.0f} to {y_ur:.0f}")
    print(f"  Width: {(x_ur - x_ll)/1000:.0f} km")
    print(f"  Height: {(y_ur - y_ll)/1000:.0f} km")
    print()

    # Create source transform
    src_transform = from_bounds(x_ll, y_ll, x_ur, y_ur, nx, ny)

    # Calculate destination transform
    print("Calculating optimal WGS84 reprojection...")
    dst_crs = CRS.from_epsg(4326)

    dst_transform, dst_width, dst_height = calculate_default_transform(
        src_crs, dst_crs,
        nx, ny,
        left=x_ll, bottom=y_ll, right=x_ur, top=y_ur
    )

    print(f"Destination grid: {dst_height} x {dst_width}")

    # Get actual WGS84 bounds from transform
    from rasterio.transform import array_bounds
    dst_bounds = array_bounds(dst_height, dst_width, dst_transform)

    print(f"WGS84 bounds:")
    print(f"  West:  {dst_bounds[0]:.6f}°")
    print(f"  South: {dst_bounds[1]:.6f}°")
    print(f"  East:  {dst_bounds[2]:.6f}°")
    print(f"  North: {dst_bounds[3]:.6f}°")
    print(f"  Longitude span: {dst_bounds[2] - dst_bounds[0]:.1f}°")
    print()

    if dst_bounds[2] - dst_bounds[0] > 200:
        print("⚠ Warning: Longitude span > 200° (near world-wide)")
        print("This is expected for HRRR Alaska due to dateline crossing")

    # Create destination array
    dst_data = np.zeros((dst_height, dst_width), dtype=np.float32)

    # Reproject
    print("Reprojecting (30-60 seconds)...")
    print()

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
    print(f"Creating {variable} visualization...")

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

    im = ax.imshow(dst_data, cmap=cmap, aspect='auto',
                   extent=list(dst_bounds),
                   vmin=vmin, vmax=vmax, interpolation='bilinear',
                   origin='upper')

    images_dir = Path('images')
    images_dir.mkdir(exist_ok=True)

    plt.savefig(images_dir / 'hrrr_full.png', bbox_inches='tight',
                pad_inches=0, transparent=True, dpi=100)
    plt.close()

    print(f"✓ Saved image")
    print()

    # Create boundary from actual grid edges
    def create_boundary_from_grid(lat_2d, lon_2d, points_per_edge=100):
        ny, nx = lat_2d.shape
        lon_norm = np.where(lon_2d > 180, lon_2d - 360, lon_2d)
        boundary = []

        # Top edge
        indices = np.linspace(0, nx - 1, points_per_edge, dtype=int)
        for i in indices:
            boundary.append({"lat": float(lat_2d[0, i]), "lon": float(lon_norm[0, i])})

        # Right edge
        indices = np.linspace(1, ny - 1, points_per_edge, dtype=int)
        for i in indices:
            boundary.append({"lat": float(lat_2d[i, -1]), "lon": float(lon_norm[i, -1])})

        # Bottom edge (reverse)
        indices = np.linspace(nx - 2, 0, points_per_edge, dtype=int)
        for i in indices:
            boundary.append({"lat": float(lat_2d[-1, i]), "lon": float(lon_norm[-1, i])})

        # Left edge (reverse)
        indices = np.linspace(ny - 2, 1, points_per_edge, dtype=int)
        for i in indices:
            boundary.append({"lat": float(lat_2d[i, 0]), "lon": float(lon_norm[i, 0])})

        return boundary

    boundary = create_boundary_from_grid(lat_2d, lon_2d, points_per_edge=100)
    print(f"✓ Created boundary: {len(boundary)} points")
    print()

    output = {
        "full": {
            "image_url": "images/hrrr_full.png",
            "bounds": list(dst_bounds)
        },
        "boundary_polygon": boundary,
        "_metadata": {
            "generated": datetime.utcnow().isoformat() + "Z",
            "method": "rasterio_reproject_full_extent_native_grid",
            "source": f"NOAA HRRR Alaska - {variable}",
            "model": H.model,
            "date": H.date.isoformat(),
            "forecast_hour": H.fxx,
            "variable": variable,
            "data_range": [float(np.nanmin(dst_data)), float(np.nanmax(dst_data))],
            "source_grid_shape": [ny, nx],
            "reprojected_grid_shape": [dst_height, dst_width],
            "source_crs": "polar_stereographic",
            "dest_crs": "WGS84 (EPSG:4326)",
            "native_extent_meters": [float(x_ll), float(y_ll), float(x_ur), float(y_ur)],
            "wgs84_bounds": list(dst_bounds),
            "longitude_span": f"{dst_bounds[2] - dst_bounds[0]:.1f}°",
            "points_per_edge": 100,
            "total_points": len(boundary),
            "grib_url": str(H.grib),
            "note": "Full HRRR Alaska extent using native grid dimensions"
        }
    }

    with open("test-data-full.json", 'w') as f:
        json.dump(output, f, indent=2)

    print("✓ Saved to test-data-full.json")
    print()
    print("=" * 80)
    print("SUCCESS!")
    print("=" * 80)
    print(f"Variable: {variable}")
    print(f"Grid: {dst_height} x {dst_width}")
    print(f"Longitude span: {dst_bounds[2] - dst_bounds[0]:.1f}°")
    print(f"Full HRRR Alaska extent")
    print()

if __name__ == "__main__":
    main()
