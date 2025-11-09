#!/usr/bin/env python3
"""
Process HRRR Alaska data in NATIVE polar stereographic projection.
No reprojection - keep the data in its original format for perfect display.
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
    print("Process HRRR Alaska in NATIVE Polar Stereographic Projection")
    print("=" * 80)
    print()

    # Install dependencies
    install_if_needed('pyproj')

    from herbie import Herbie
    from pyproj import Proj

    print("Searching for latest HRRR Alaska GRIB2...")
    print()

    # Find latest GRIB2
    H = None
    for hours_ago in range(0, 12):
        try:
            dt = datetime.utcnow() - timedelta(hours=hours_ago)
            dt = dt.replace(minute=0, second=0, microsecond=0)
            print(f"Trying {dt.strftime('%Y-%m-%d %H:00')} UTC...")
            H = Herbie(dt, model="hrrrak", product="sfc", fxx=0)
            if H.grib:
                print(f"✓ Found: {H.model} {H.date} F{H.fxx:02d}")
                print(f"  GRIB: {H.grib}")
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

    # Load REFC
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

    # Extract data
    lat_2d = ds.latitude.values
    lon_2d = ds.longitude.values
    ny, nx = lat_2d.shape

    data_var = [v for v in ds.data_vars][0]
    data = ds[data_var].values

    print(f"Data: {data_var}")
    print(f"  Range: {np.nanmin(data):.2f} to {np.nanmax(data):.2f}")
    print(f"  Shape: {ny} x {nx}")
    print()

    # Define HRRR Alaska polar stereographic projection
    print("Setting up native polar stereographic projection...")
    proj_params = "+proj=stere +lat_0=90 +lon_0=225 +lat_ts=60 +a=6371229 +b=6371229 +units=m +no_defs"
    p = Proj(proj_params)

    # Convert lat/lon to native projection coordinates (meters)
    lon_normalized = np.where(lon_2d > 180, lon_2d - 360, lon_2d)

    # Get corners in native projection
    # Sample edge points and convert to meters
    x_coords = []
    y_coords = []

    # Sample all edges
    for i in range(nx):
        x, y = p(lon_normalized[0, i], lat_2d[0, i])  # Top
        x_coords.append(x)
        y_coords.append(y)
        x, y = p(lon_normalized[-1, i], lat_2d[-1, i])  # Bottom
        x_coords.append(x)
        y_coords.append(y)

    for i in range(ny):
        x, y = p(lon_normalized[i, 0], lat_2d[i, 0])  # Left
        x_coords.append(x)
        y_coords.append(y)
        x, y = p(lon_normalized[i, -1], lat_2d[i, -1])  # Right
        x_coords.append(x)
        y_coords.append(y)

    # Grid extent in meters
    x_min, x_max = min(x_coords), max(x_coords)
    y_min, y_max = min(y_coords), max(y_coords)

    # Calculate cell size (3km nominal)
    x_res = (x_max - x_min) / nx
    y_res = (y_max - y_min) / ny

    print(f"Native projection grid extent (meters):")
    print(f"  X: {x_min:.1f} to {x_max:.1f} (range: {x_max - x_min:.1f} m)")
    print(f"  Y: {y_min:.1f} to {y_max:.1f} (range: {y_max - y_min:.1f} m)")
    print(f"  Cell size: {x_res:.1f} x {y_res:.1f} m")
    print()

    # Extend by half cell to corners
    x_ll = x_min - x_res / 2
    x_ur = x_max + x_res / 2
    y_ll = y_min - y_res / 2
    y_ur = y_max + y_res / 2

    native_bounds = [x_ll, y_ll, x_ur, y_ur]

    print(f"Cell corner bounds (meters):")
    print(f"  X: {x_ll:.1f} to {x_ur:.1f}")
    print(f"  Y: {y_ll:.1f} to {y_ur:.1f}")
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
        data = np.ma.masked_less(data, 5)
    else:
        colors = ['#0000ff', '#00ffff', '#00ff00', '#ffff00', '#ff0000']
        cmap = LinearSegmentedColormap.from_list('temp', colors)
        vmin, vmax = -20, 30

    # Plot in native projection space
    fig, ax = plt.subplots(figsize=(13, 9), dpi=100)
    ax.set_position([0, 0, 1, 1])
    ax.axis('off')

    im = ax.imshow(data, cmap=cmap, aspect='equal',
                   extent=[x_ll, x_ur, y_ll, y_ur],
                   vmin=vmin, vmax=vmax, interpolation='nearest',
                   origin='upper')

    # Save
    images_dir = Path('images')
    images_dir.mkdir(exist_ok=True)

    plt.savefig(images_dir / 'hrrr_native.png', bbox_inches='tight',
                pad_inches=0, transparent=True, dpi=100)
    plt.close()

    print(f"✓ Saved image in native projection")
    print()

    # Create boundary in lat/lon for display
    print("Creating boundary polygon (in lat/lon)...")

    def create_boundary_latlon(lat_2d, lon_2d, points_per_edge=100):
        """Sample actual grid edges in lat/lon."""
        ny, nx = lat_2d.shape
        boundary = []
        lon_norm = np.where(lon_2d > 180, lon_2d - 360, lon_2d)

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

        # Left edge (reverse, skip last to close)
        indices = np.linspace(ny - 2, 1, points_per_edge, dtype=int)
        for i in indices:
            boundary.append({"lat": float(lat_2d[i, 0]), "lon": float(lon_norm[i, 0])})

        return boundary

    boundary = create_boundary_latlon(lat_2d, lon_2d, points_per_edge=100)
    print(f"✓ Created {len(boundary)} points")
    print()

    # Save
    output = {
        "native": {
            "image_url": "images/hrrr_native.png",
            "bounds": native_bounds,
            "crs": proj_params,
            "units": "meters"
        },
        "boundary_polygon": boundary,
        "_metadata": {
            "generated": datetime.utcnow().isoformat() + "Z",
            "method": "native_polar_stereographic_no_reprojection",
            "source": f"NOAA HRRR Alaska - {variable}",
            "model": H.model,
            "date": H.date.isoformat(),
            "forecast_hour": H.fxx,
            "variable": variable,
            "data_range": [float(np.nanmin(data)), float(np.nanmax(data))],
            "grid_shape": [ny, nx],
            "projection": "polar_stereographic",
            "proj4": proj_params,
            "native_bounds_meters": native_bounds,
            "points_per_edge": 100,
            "total_points": len(boundary),
            "grib_url": str(H.grib),
            "note": "HRRR Alaska data in native polar stereographic projection - no reprojection, no distortion"
        }
    }

    with open("test-data-native.json", 'w') as f:
        json.dump(output, f, indent=2)

    print("✓ Saved to test-data-native.json")
    print()
    print("=" * 80)
    print("SUCCESS!")
    print("=" * 80)
    print(f"Variable: {variable}")
    print(f"Date: {H.date}")
    print(f"Grid: {ny} x {nx} (native polar stereographic)")
    print(f"Bounds: [{x_ll:.0f}, {y_ll:.0f}, {x_ur:.0f}, {y_ur:.0f}] meters")
    print(f"NO reprojection - NO distortion - PERFECT alignment")
    print()
    print("Next: Update index.html to use leaflet-proj4 with native projection")
    print()

if __name__ == "__main__":
    main()
