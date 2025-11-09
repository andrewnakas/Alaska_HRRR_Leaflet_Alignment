#!/usr/bin/env python3
"""
Reproject HRRR Alaska to WGS84 but CROP to actual data extent.
This avoids the world-wide stretching issue.
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
    print("Reproject HRRR Alaska to WGS84 with Smart Cropping")
    print("=" * 80)
    print()

    install_if_needed('rasterio')
    install_if_needed('pyproj')

    from herbie import Herbie
    import rasterio
    from rasterio.transform import from_bounds
    from rasterio.warp import reproject, Resampling, calculate_default_transform
    from rasterio.crs import CRS
    from pyproj import Transformer

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

    # Get lat/lon extent from GRIB2
    lon_normalized = np.where(lon_2d > 180, lon_2d - 360, lon_2d)

    lat_min = lat_2d.min()
    lat_max = lat_2d.max()
    lon_min = lon_normalized.min()
    lon_max = lon_normalized.max()

    # Calculate cell size and extend to corners
    lat_res = np.abs(lat_2d[1, :] - lat_2d[0, :]).mean()
    lon_res = np.abs(lon_normalized[:, 1:] - lon_normalized[:, :-1]).mean()

    target_west = lon_min - lon_res / 2
    target_east = lon_max + lon_res / 2
    target_south = lat_min - lat_res / 2
    target_north = lat_max + lat_res / 2

    print(f"Target WGS84 bounds:")
    print(f"  West:  {target_west:.6f}°")
    print(f"  South: {target_south:.6f}°")
    print(f"  East:  {target_east:.6f}°")
    print(f"  North: {target_north:.6f}°")
    print()

    # Define source CRS
    src_crs = CRS.from_proj4(
        "+proj=stere +lat_0=90 +lon_0=225 +lat_ts=60 +a=6371229 +b=6371229 +units=m +no_defs"
    )

    # Transform WGS84 bounds to native projection
    print("Transforming to native projection...")
    transformer = Transformer.from_crs("EPSG:4326", src_crs, always_xy=True)

    # Sample edge points to get native extent
    x_coords = []
    y_coords = []

    for lat in [target_south, target_north]:
        for lon in np.linspace(target_west, target_east, 100):
            x, y = transformer.transform(lon, lat)
            x_coords.append(x)
            y_coords.append(y)

    for lon in [target_west, target_east]:
        for lat in np.linspace(target_south, target_north, 100):
            x, y = transformer.transform(lon, lat)
            x_coords.append(x)
            y_coords.append(y)

    x_ll = min(x_coords)
    x_ur = max(x_coords)
    y_ll = min(y_coords)
    y_ur = max(y_coords)

    src_transform = from_bounds(x_ll, y_ll, x_ur, y_ur, nx, ny)

    # Calculate destination transform - but limit to Alaska bounds!
    print("Calculating reprojection (cropped to Alaska)...")

    # Instead of auto-calculate, specify Alaska bounds explicitly
    # This prevents world-wide stretching
    alaska_west = -180.0
    alaska_east = -130.0  # Crop eastern edge to mainland Alaska
    alaska_south = target_south
    alaska_north = target_north

    # Calculate reasonable resolution (about 3km in degrees at 60°N)
    res_deg = 0.03  # ~3km at this latitude

    dst_width = int((alaska_east - alaska_west) / res_deg)
    dst_height = int((alaska_north - alaska_south) / res_deg)

    dst_transform = from_bounds(alaska_west, alaska_south, alaska_east, alaska_north,
                                 dst_width, dst_height)

    print(f"Reprojection grid:")
    print(f"  Size: {dst_height} x {dst_width}")
    print(f"  Bounds: [{alaska_west:.2f}, {alaska_south:.2f}, {alaska_east:.2f}, {alaska_north:.2f}]")
    print(f"  Longitude span: {alaska_east - alaska_west:.1f}° (NOT 360°!)")
    print()

    dst_crs = CRS.from_epsg(4326)
    dst_data = np.zeros((dst_height, dst_width), dtype=np.float32)

    # Reproject
    print("Reprojecting (this may take 30-60 seconds)...")
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

    cropped_bounds = [alaska_west, alaska_south, alaska_east, alaska_north]

    print(f"Final bounds (cropped to Alaska):")
    print(f"  West:  {alaska_west:.6f}°")
    print(f"  South: {alaska_south:.6f}°")
    print(f"  East:  {alaska_east:.6f}°")
    print(f"  North: {alaska_north:.6f}°")
    print(f"  Span: {alaska_east - alaska_west:.1f}° longitude (reasonable!)")
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
                   extent=cropped_bounds,
                   vmin=vmin, vmax=vmax, interpolation='bilinear',
                   origin='upper')

    images_dir = Path('images')
    images_dir.mkdir(exist_ok=True)

    plt.savefig(images_dir / 'hrrr_cropped.png', bbox_inches='tight',
                pad_inches=0, transparent=True, dpi=100)
    plt.close()

    print(f"✓ Saved cropped image")
    print()

    # Create boundary
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

    boundary = create_boundary(cropped_bounds)

    output = {
        "cropped": {
            "image_url": "images/hrrr_cropped.png",
            "bounds": cropped_bounds
        },
        "boundary_polygon": boundary,
        "_metadata": {
            "generated": datetime.utcnow().isoformat() + "Z",
            "method": "rasterio_reproject_with_smart_crop",
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
            "cropped_to": "Mainland Alaska (-180° to -130°)",
            "longitude_span": f"{alaska_east - alaska_west:.1f}°",
            "points_per_edge": 100,
            "total_points": len(boundary),
            "grib_url": str(H.grib),
            "note": "Reprojected to WGS84 but cropped to Alaska extent - no world-wide stretching"
        }
    }

    with open("test-data-cropped.json", 'w') as f:
        json.dump(output, f, indent=2)

    print("✓ Saved to test-data-cropped.json")
    print()
    print("=" * 80)
    print("SUCCESS!")
    print("=" * 80)
    print(f"Variable: {variable}")
    print(f"Grid: {dst_height} x {dst_width} (WGS84, cropped)")
    print(f"Bounds: [{alaska_west:.1f}, {alaska_south:.1f}, {alaska_east:.1f}, {alaska_north:.1f}]")
    print(f"Longitude span: {alaska_east - alaska_west:.1f}° (NOT 360°!)")
    print(f"No world-wide stretching - cropped to Alaska only")
    print()

if __name__ == "__main__":
    main()
