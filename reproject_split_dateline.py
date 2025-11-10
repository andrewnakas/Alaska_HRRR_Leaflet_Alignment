#!/usr/bin/env python3
"""
Properly reproject HRRR Alaska to WGS84 and split at dateline.
This avoids the 360° world-spanning issue.
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
    print("Reproject HRRR Alaska and Split at Dateline")
    print("=" * 80)
    print()

    install_if_needed('rasterio')
    install_if_needed('pyproj')

    from herbie import Herbie
    import rasterio
    from rasterio.transform import from_bounds, array_bounds
    from rasterio.warp import reproject, Resampling, calculate_default_transform
    from rasterio.crs import CRS

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
    except Exception as e:
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

    print(f"Data: {data_var}, Grid: {ny} x {nx}")
    print()

    # Define source projection
    src_crs = CRS.from_proj4(
        "+proj=stere +lat_0=90 +lon_0=225 +lat_ts=60 +a=6371229 +b=6371229 +units=m +no_defs"
    )

    # Get grid extent from lat/lon
    lon_norm = np.where(lon_2d > 180, lon_2d - 360, lon_2d)

    # Get lat/lon bounds
    lat_min, lat_max = lat_2d.min(), lat_2d.max()
    lon_min, lon_max = lon_norm.min(), lon_norm.max()

    print(f"Data extent (lat/lon):")
    print(f"  Lat: {lat_min:.2f}° to {lat_max:.2f}°")
    print(f"  Lon: {lon_min:.2f}° to {lon_max:.2f}°")
    print()

    # Create source transform using actual grid in native projection
    from pyproj import Proj
    p = Proj(src_crs)

    # Sample edges to get native bounds
    x_coords, y_coords = [], []
    for i in range(ny):
        for j in [0, nx-1]:
            x, y = p(lon_norm[i, j], lat_2d[i, j])
            x_coords.append(x)
            y_coords.append(y)
    for j in range(nx):
        for i in [0, ny-1]:
            x, y = p(lon_norm[i, j], lat_2d[i, j])
            x_coords.append(x)
            y_coords.append(y)

    x_ll = min(x_coords) - 1500
    x_ur = max(x_coords) + 1500
    y_ll = min(y_coords) - 1500
    y_ur = max(y_coords) + 1500

    src_transform = from_bounds(x_ll, y_ll, x_ur, y_ur, nx, ny)

    # Split into western and eastern hemispheres at dateline
    # Western: -180° to -130° (Alaska mainland)
    # Eastern: 170° to 180° (Aleutian Islands)

    print("Reprojecting to WGS84 in two parts...")
    print()

    dst_crs = CRS.from_epsg(4326)
    images_dir = Path('images')
    images_dir.mkdir(exist_ok=True)

    regions = [
        {
            'name': 'western',
            'lon_bounds': [-180, -130],
            'label': 'Alaska Mainland'
        },
        {
            'name': 'eastern',
            'lon_bounds': [170, 180],
            'label': 'Western Aleutians'
        }
    ]

    output_regions = {}

    for region in regions:
        print(f"Processing {region['label']}...")

        west_lon = region['lon_bounds'][0]
        east_lon = region['lon_bounds'][1]

        # Calculate transform for this region
        dst_transform = from_bounds(
            west_lon, lat_min, east_lon, lat_max,
            int((east_lon - west_lon) / 0.03),  # ~3km resolution
            int((lat_max - lat_min) / 0.03)
        )

        dst_width = int((east_lon - west_lon) / 0.03)
        dst_height = int((lat_max - lat_min) / 0.03)

        print(f"  Grid: {dst_height} x {dst_width}")
        print(f"  Bounds: [{west_lon}, {lat_min:.2f}, {east_lon}, {lat_max:.2f}]")

        # Create destination array
        dst_data = np.zeros((dst_height, dst_width), dtype=np.float32)

        # Reproject
        reproject(
            source=data,
            destination=dst_data,
            src_transform=src_transform,
            src_crs=src_crs,
            dst_transform=dst_transform,
            dst_crs=dst_crs,
            resampling=Resampling.bilinear
        )

        # Create visualization
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
                  extent=[west_lon, east_lon, lat_min, lat_max],
                  vmin=vmin, vmax=vmax, interpolation='bilinear',
                  origin='upper')

        img_path = images_dir / f'hrrr_{region["name"]}.png'
        plt.savefig(img_path, bbox_inches='tight', pad_inches=0,
                   transparent=True, dpi=100)
        plt.close()

        print(f"  ✓ Saved {img_path}")

        output_regions[region['name']] = {
            'image_url': f'images/hrrr_{region["name"]}.png',
            'bounds': [west_lon, lat_min, east_lon, lat_max],
            'label': region['label']
        }

    print()

    # Create boundary polygon
    def create_boundary(lat_2d, lon_2d, points_per_edge=100):
        ny, nx = lat_2d.shape
        lon_norm = np.where(lon_2d > 180, lon_2d - 360, lon_2d)
        boundary = []

        for i in np.linspace(0, nx - 1, points_per_edge, dtype=int):
            boundary.append({"lat": float(lat_2d[0, i]), "lon": float(lon_norm[0, i])})
        for i in np.linspace(1, ny - 1, points_per_edge, dtype=int):
            boundary.append({"lat": float(lat_2d[i, -1]), "lon": float(lon_norm[i, -1])})
        for i in np.linspace(nx - 2, 0, points_per_edge, dtype=int):
            boundary.append({"lat": float(lat_2d[-1, i]), "lon": float(lon_norm[-1, i])})
        for i in np.linspace(ny - 2, 1, points_per_edge, dtype=int):
            boundary.append({"lat": float(lat_2d[i, 0]), "lon": float(lon_norm[i, 0])})

        return boundary

    boundary = create_boundary(lat_2d, lon_2d)

    output = {
        **output_regions,
        "boundary_polygon": boundary,
        "_metadata": {
            "generated": datetime.utcnow().isoformat() + "Z",
            "method": "rasterio_reproject_split_at_dateline",
            "source": f"NOAA HRRR Alaska - {variable}",
            "model": H.model,
            "date": H.date.isoformat(),
            "variable": variable,
            "source_grid_shape": [ny, nx],
            "split_regions": len(regions),
            "note": "Split at dateline to avoid 360° world-spanning"
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
    print(f"Split into {len(regions)} regions")
    print("Proper alignment with WGS84 - no world-spanning")
    print()

if __name__ == "__main__":
    main()
