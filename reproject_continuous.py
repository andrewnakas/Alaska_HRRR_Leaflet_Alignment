#!/usr/bin/env python3
"""
Reproject HRRR Alaska with continuous longitude bounds (Russia to Alaska).
Normalize coordinates so they span continuously without world-wrapping.
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
    print("HRRR Alaska - Continuous Bounds (Russia → Alaska)")
    print("=" * 80)
    print()

    install_if_needed('rasterio')
    install_if_needed('pyproj')

    from herbie import Herbie
    import rasterio
    from rasterio.transform import from_bounds
    from rasterio.warp import reproject, Resampling
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

    # Normalize longitude to -180/+180
    lon_normalized = np.where(lon_2d > 180, lon_2d - 360, lon_2d)

    # Get extent
    lat_min, lat_max = lat_2d.min(), lat_2d.max()
    lon_min_raw, lon_max_raw = lon_normalized.min(), lon_normalized.max()

    print(f"Raw extent:")
    print(f"  Lat: {lat_min:.2f}° to {lat_max:.2f}°")
    print(f"  Lon: {lon_min_raw:.2f}° to {lon_max_raw:.2f}°")
    print()

    # The data crosses the dateline. To make it continuous (Russia → Alaska),
    # we need to shift positive longitudes (eastern Aleutians) to negative equivalents
    # Example: 170° becomes -190° (170 - 360)

    # Find where the dateline crossing occurs by looking at the grid
    # If we have both large negative (~-180) and large positive (~+180) values,
    # we're crossing the dateline

    has_eastern = np.any(lon_normalized > 100)  # Eastern hemisphere (positive)
    has_western = np.any(lon_normalized < -100)  # Western hemisphere (negative)

    if has_eastern and has_western:
        print("Dateline crossing detected!")
        print("Converting to continuous longitude (Russia → Alaska)...")

        # Convert positive longitudes to their negative equivalents
        # This makes the coordinates continuous
        lon_continuous = np.where(lon_normalized > 0, lon_normalized - 360, lon_normalized)

        lon_min = lon_continuous.min()
        lon_max = lon_continuous.max()

        print(f"Continuous extent:")
        print(f"  Lon: {lon_min:.2f}° to {lon_max:.2f}°")
        print(f"  Span: {lon_max - lon_min:.1f}° (Russia → Alaska)")
        print()
    else:
        # No dateline crossing, use as-is
        lon_continuous = lon_normalized
        lon_min = lon_min_raw
        lon_max = lon_max_raw

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

    print(f"Native projection extent (meters):")
    print(f"  X: {x_ll:.0f} to {x_ur:.0f}")
    print(f"  Y: {y_ll:.0f} to {y_ur:.0f}")
    print()

    src_transform = from_bounds(x_ll, y_ll, x_ur, y_ur, nx, ny)

    # Reproject to WGS84 with continuous bounds
    print("Reprojecting to WGS84 with continuous bounds...")

    dst_crs = CRS.from_epsg(4326)

    # Calculate resolution (~3km)
    resolution = 0.03
    dst_width = int((lon_max - lon_min) / resolution)
    dst_height = int((lat_max - lat_min) / resolution)

    print(f"Destination grid: {dst_height} x {dst_width}")
    print(f"Bounds: [{lon_min:.2f}, {lat_min:.2f}, {lon_max:.2f}, {lat_max:.2f}]")
    print(f"Longitude span: {lon_max - lon_min:.1f}° (continuous, no world-wrapping!)")
    print()

    dst_transform = from_bounds(lon_min, lat_min, lon_max, lat_max, dst_width, dst_height)
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

    print("✓ Reprojection complete!")
    print()

    # Apply optimal alignment transformation
    print("Applying optimal alignment...")

    # Load optimal parameters from alignment_config.json
    config_path = Path('alignment_config.json')
    if config_path.exists():
        with open(config_path, 'r') as f:
            config = json.load(f)

        adjustments = config['adjustments']
        lon_offset = adjustments['lon_offset']
        lat_offset = adjustments['lat_offset']
        lon_scale = adjustments['lon_scale']
        lat_scale = adjustments['lat_scale']

        print(f"  Longitude offset: {lon_offset:+.3f}°")
        print(f"  Latitude offset: {lat_offset:+.3f}°")
        print(f"  Longitude scale: {lon_scale:.3f}x")
        print(f"  Latitude scale: {lat_scale:.3f}x")

        # Calculate center
        center_lon = (lon_min + lon_max) / 2
        center_lat = (lat_min + lat_max) / 2

        # Apply scaling from center
        lon_span = (lon_max - lon_min) * lon_scale
        lat_span = (lat_max - lat_min) * lat_scale

        lon_min_adjusted = center_lon - lon_span / 2
        lon_max_adjusted = center_lon + lon_span / 2
        lat_min_adjusted = center_lat - lat_span / 2
        lat_max_adjusted = center_lat + lat_span / 2

        # Apply offset
        lon_min_adjusted += lon_offset
        lon_max_adjusted += lon_offset
        lat_min_adjusted += lat_offset
        lat_max_adjusted += lat_offset

        print(f"  Adjusted bounds: [{lon_min_adjusted:.2f}, {lat_min_adjusted:.2f}, {lon_max_adjusted:.2f}, {lat_max_adjusted:.2f}]")
        print()

        # Use adjusted bounds for visualization
        lon_min_viz = lon_min_adjusted
        lat_min_viz = lat_min_adjusted
        lon_max_viz = lon_max_adjusted
        lat_max_viz = lat_max_adjusted
    else:
        print("  No alignment_config.json found, using original bounds")
        print()
        lon_min_viz = lon_min
        lat_min_viz = lat_min
        lon_max_viz = lon_max
        lat_max_viz = lat_max

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

    ax.imshow(dst_data, cmap=cmap, aspect='auto',
              extent=[lon_min_viz, lon_max_viz, lat_min_viz, lat_max_viz],
              vmin=vmin, vmax=vmax, interpolation='bilinear',
              origin='lower')

    images_dir = Path('images')
    images_dir.mkdir(exist_ok=True)

    plt.savefig(images_dir / 'hrrr_continuous.png', bbox_inches='tight',
                pad_inches=0, transparent=True, dpi=100)
    plt.close()

    print(f"✓ Saved images/hrrr_continuous.png")
    print()

    # Create boundary polygon with continuous coordinates
    def create_boundary(lat_2d, lon_2d, points_per_edge=100):
        ny, nx = lat_2d.shape
        # Use continuous longitude
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

    output = {
        "continuous": {
            "image_url": "images/hrrr_continuous.png",
            "bounds": [lon_min_viz, lat_min_viz, lon_max_viz, lat_max_viz]
        },
        "boundary_polygon": boundary,
        "_metadata": {
            "generated": datetime.utcnow().isoformat() + "Z",
            "method": "continuous_longitude_russia_to_alaska_optimally_aligned",
            "source": f"NOAA HRRR Alaska - {variable}",
            "model": H.model,
            "date": H.date.isoformat(),
            "variable": variable,
            "source_grid_shape": [ny, nx],
            "reprojected_grid_shape": [dst_height, dst_width],
            "base_bounds": [lon_min, lat_min, lon_max, lat_max],
            "adjusted_bounds": [lon_min_viz, lat_min_viz, lon_max_viz, lat_max_viz],
            "longitude_span": f"{lon_max - lon_min:.1f}°",
            "note": "Continuous longitude from Russia to Alaska with optimal alignment applied"
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
    print(f"Grid: {dst_height} x {dst_width}")
    print(f"Base bounds: {lon_min:.2f}° to {lon_max:.2f}° ({lon_max - lon_min:.1f}° span)")
    print(f"Adjusted bounds: {lon_min_viz:.2f}° to {lon_max_viz:.2f}° ({lon_max_viz - lon_min_viz:.1f}° span)")
    print("Continuous bounds from Russia to Alaska with optimal alignment!")
    print()

if __name__ == "__main__":
    main()
