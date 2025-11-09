#!/usr/bin/env python3
"""
Use GRIB2 lat/lon coordinates DIRECTLY - no reprojection to rectangular WGS84.
Save data with its native 919x1299 grid and 2D lat/lon arrays.
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
    print("HRRR Alaska - Direct Lat/Lon (No Rectangular Reprojection)")
    print("=" * 80)
    print()

    from herbie import Herbie

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

    # Normalize longitude to -180/+180
    lon_normalized = np.where(lon_2d > 180, lon_2d - 360, lon_2d)

    # Get approximate bounds for rectangular display
    # Use the actual data extent from the corners
    corner_lats = [lat_2d[0, 0], lat_2d[0, -1], lat_2d[-1, 0], lat_2d[-1, -1]]
    corner_lons = [lon_normalized[0, 0], lon_normalized[0, -1], lon_normalized[-1, 0], lon_normalized[-1, -1]]

    approx_south = min(corner_lats)
    approx_north = max(corner_lats)
    approx_west = min(corner_lons)
    approx_east = max(corner_lons)

    print(f"Approximate rectangular bounds (from corners):")
    print(f"  West:  {approx_west:.6f}°")
    print(f"  South: {approx_south:.6f}°")
    print(f"  East:  {approx_east:.6f}°")
    print(f"  North: {approx_north:.6f}°")
    print(f"  Span: {approx_east - approx_west:.1f}° longitude")
    print()

    # Create visualization - display as rectangular grid with approximate bounds
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
        data = np.ma.masked_less(data, 5)
    else:
        colors = ['#0000ff', '#00ffff', '#00ff00', '#ffff00', '#ff0000']
        cmap = LinearSegmentedColormap.from_list('temp', colors)
        vmin, vmax = -20, 30

    fig, ax = plt.subplots(figsize=(13, 9), dpi=100)
    ax.set_position([0, 0, 1, 1])
    ax.axis('off')

    # Display with approximate rectangular bounds
    # This is an approximation - the actual grid is curvilinear
    im = ax.imshow(data, cmap=cmap, aspect='auto',
                   extent=[approx_west, approx_east, approx_south, approx_north],
                   vmin=vmin, vmax=vmax, interpolation='bilinear',
                   origin='upper')

    images_dir = Path('images')
    images_dir.mkdir(exist_ok=True)

    plt.savefig(images_dir / 'hrrr_direct.png', bbox_inches='tight',
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
    print(f"✓ Created boundary: {len(boundary)} points from actual grid edges")
    print()

    approx_bounds = [approx_west, approx_south, approx_east, approx_north]

    output = {
        "direct": {
            "image_url": "images/hrrr_direct.png",
            "bounds": approx_bounds
        },
        "boundary_polygon": boundary,
        "_metadata": {
            "generated": datetime.utcnow().isoformat() + "Z",
            "method": "direct_latlon_approximate_rectangular",
            "source": f"NOAA HRRR Alaska - {variable}",
            "model": H.model,
            "date": H.date.isoformat(),
            "forecast_hour": H.fxx,
            "variable": variable,
            "data_range": [float(np.nanmin(data)), float(np.nanmax(data))],
            "grid_shape": [ny, nx],
            "projection": "curvilinear (displayed as approximate rectangle)",
            "approximate_bounds": approx_bounds,
            "longitude_span": f"{approx_east - approx_west:.1f}°",
            "points_per_edge": 100,
            "total_points": len(boundary),
            "grib_url": str(H.grib),
            "note": "Direct lat/lon from GRIB2, displayed with approximate rectangular bounds. Boundary polygon follows actual grid edges."
        }
    }

    with open("test-data.json", 'w') as f:
        json.dump(output, f, indent=2)

    print("✓ Saved to test-data.json")
    print()
    print("=" * 80)
    print("SUCCESS!")
    print("=" * 80)
    print(f"Variable: {variable}")
    print(f"Grid: {ny} x {nx} (native)")
    print(f"Approximate span: {approx_east - approx_west:.1f}° longitude")
    print(f"All HRRR Alaska data included")
    print()

if __name__ == "__main__":
    main()
