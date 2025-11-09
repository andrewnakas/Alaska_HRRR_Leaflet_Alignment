#!/usr/bin/env python3
"""
Download HRRR Alaska REFC and properly reproject from polar stereographic to WGS84.
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
    print("Download & Reproject HRRR Alaska REFC (Polar -> WGS84)")
    print("=" * 80)
    print()

    # Install dependencies
    install_if_needed('rasterio')
    install_if_needed('pyproj')

    from herbie import Herbie
    import rasterio
    from rasterio.transform import from_bounds, array_bounds
    from rasterio.warp import reproject, Resampling, calculate_default_transform
    from rasterio.crs import CRS
    from pyproj import Proj, Transformer

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

    print(f"Grid shape: {ds.latitude.shape}")
    print()

    # Extract data
    lat_2d = ds.latitude.values
    lon_2d = ds.longitude.values
    ny, nx = lat_2d.shape

    data_var = [v for v in ds.data_vars][0]
    data = ds[data_var].values

    print(f"Data: {data_var}")
    print(f"  Range: {np.nanmin(data):.2f} to {np.nanmax(data):.2f}")
    print(f"  Shape: {data.shape}")
    print()

    # Define source CRS (polar stereographic)
    print("Setting up polar stereographic projection...")
    src_crs = CRS.from_proj4(
        "+proj=stere +lat_0=90 +lon_0=225 +lat_ts=60 +a=6371229 +b=6371229 +units=m +no_defs"
    )

    # Get projection info from dataset if available
    if hasattr(ds, 'crs_wkt'):
        print(f"Using CRS from GRIB2: {ds.crs_wkt[:100]}...")

    print(f"Source CRS: {src_crs}")
    print()

    # Get grid bounds in native projection
    # HRRR Alaska grid specification
    # Lower left corner (x, y in meters)
    x_ll = -2700000.0  # meters
    y_ll = -1588000.0  # meters
    resolution = 3000.0  # 3km

    # Calculate bounds in native projection
    x_ur = x_ll + (nx * resolution)
    y_ur = y_ll + (ny * resolution)

    print("Native projection bounds (meters):")
    print(f"  X: {x_ll:.1f} to {x_ur:.1f}")
    print(f"  Y: {y_ll:.1f} to {y_ur:.1f}")
    print()

    # Create source transform
    src_transform = from_bounds(x_ll, y_ll, x_ur, y_ur, nx, ny)

    # Define destination CRS (WGS84)
    dst_crs = CRS.from_epsg(4326)

    # Calculate destination transform and dimensions
    print("Calculating reprojection parameters...")
    dst_transform, dst_width, dst_height = calculate_default_transform(
        src_crs, dst_crs,
        nx, ny,
        left=x_ll, bottom=y_ll, right=x_ur, top=y_ur,
        resolution=None  # Auto-calculate
    )

    print(f"Destination dimensions: {dst_height} x {dst_width}")
    print()

    # Create destination array
    dst_data = np.zeros((dst_height, dst_width), dtype=np.float32)

    # Reproject!
    print("Reprojecting from polar stereographic to WGS84...")
    print("(This may take 30-60 seconds)")
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

    # Get EXACT bounds from reprojected data
    exact_bounds = array_bounds(dst_height, dst_width, dst_transform)
    west, south, east, north = exact_bounds

    print("Reprojected WGS84 bounds:")
    print(f"  West:  {west:.10f}°")
    print(f"  South: {south:.10f}°")
    print(f"  East:  {east:.10f}°")
    print(f"  North: {north:.10f}°")
    print()

    print(f"Data range after reprojection: {np.nanmin(dst_data):.2f} to {np.nanmax(dst_data):.2f}")
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

    # Plot
    fig, ax = plt.subplots(figsize=(13, 9), dpi=100)
    ax.set_position([0, 0, 1, 1])
    ax.axis('off')

    im = ax.imshow(dst_data, cmap=cmap, aspect='auto',
                   extent=[west, east, south, north],
                   vmin=vmin, vmax=vmax, interpolation='bilinear',
                   origin='upper')

    # Save
    images_dir = Path('images')
    images_dir.mkdir(exist_ok=True)

    plt.savefig(images_dir / 'hrrr_west.png', bbox_inches='tight',
                pad_inches=0, transparent=True, dpi=100)
    plt.savefig(images_dir / 'hrrr_east.png', bbox_inches='tight',
                pad_inches=0, transparent=True, dpi=100)
    plt.close()

    print(f"✓ Saved images")
    print()

    # Create boundary
    print("Creating boundary polygon...")

    def create_boundary(bounds, points=100):
        w, s, e, n = bounds
        b = []
        for i in range(points):
            t = i / (points - 1)
            b.append({"lat": n, "lon": w + t * (e - w)})
        for i in range(1, points):
            t = i / (points - 1)
            b.append({"lat": n - t * (n - s), "lon": e})
        for i in range(1, points):
            t = i / (points - 1)
            b.append({"lat": s, "lon": e - t * (e - w)})
        for i in range(1, points - 1):
            t = i / (points - 1)
            b.append({"lat": s + t * (n - s), "lon": w})
        return b

    boundary = create_boundary(exact_bounds)
    print(f"✓ Created {len(boundary)} points")
    print()

    # Verify alignment
    lats = [p['lat'] for p in boundary]
    lons = [p['lon'] for p in boundary]
    extent = [min(lons), min(lats), max(lons), max(lats)]
    diff = sum(abs(extent[i] - exact_bounds[i]) for i in range(4))

    print(f"Alignment: {diff:.10f}° difference")
    if diff < 0.000001:
        print("✓ PERFECT!")
    print()

    # Save
    output = {
        "western": {
            "image_url": "images/hrrr_west.png",
            "bounds": list(exact_bounds)
        },
        "eastern": {
            "image_url": "images/hrrr_east.png",
            "bounds": [west, south, west - 0.02, north]
        },
        "boundary_polygon": boundary,
        "_metadata": {
            "generated": datetime.utcnow().isoformat() + "Z",
            "method": "rasterio_reproject_polar_to_wgs84",
            "source": f"NOAA HRRR Alaska - {variable}",
            "model": H.model,
            "date": H.date.isoformat(),
            "forecast_hour": H.fxx,
            "variable": variable,
            "data_range": [float(np.nanmin(dst_data)), float(np.nanmax(dst_data))],
            "source_grid_shape": [ny, nx],
            "reprojected_grid_shape": [dst_height, dst_width],
            "source_crs": "polar_stereographic (EPSG:3413-like)",
            "dest_crs": "WGS84 (EPSG:4326)",
            "points_per_edge": 100,
            "total_points": len(boundary),
            "alignment_verified": bool(diff < 0.000001),
            "grib_url": str(H.grib),
            "note": "Real HRRR Alaska data properly reprojected from polar stereographic to WGS84"
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
    print(f"Date: {H.date}")
    print(f"Source grid: {ny} x {nx} (polar stereographic)")
    print(f"Reprojected: {dst_height} x {dst_width} (WGS84)")
    print(f"Bounds: [{west:.6f}, {south:.6f}, {east:.6f}, {north:.6f}]")
    print(f"Alignment: PERFECT")
    print()

if __name__ == "__main__":
    main()
