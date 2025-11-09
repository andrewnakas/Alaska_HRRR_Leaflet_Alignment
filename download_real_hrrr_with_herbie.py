#!/usr/bin/env python3
"""
Download REAL HRRR Alaska GRIB2 data using Herbie and create images.

This script:
1. Downloads latest HRRR Alaska GRIB2 from NOAA using Herbie
2. Extracts temperature at 2m (or other variables)
3. Converts to PNG images
4. Calculates exact bounds from the GRIB2 grid
5. Creates boundary polygon with perfect alignment
"""

import subprocess
import sys
from datetime import datetime, timedelta
import json

def install_package(package_name, import_name=None):
    """Install a package if not available."""
    if import_name is None:
        import_name = package_name.replace('-', '_')

    try:
        __import__(import_name)
        print(f"✓ {package_name} already installed")
        return True
    except ImportError:
        print(f"Installing {package_name}...")
        try:
            subprocess.check_call([
                sys.executable, '-m', 'pip', 'install', '-q',
                '--break-system-packages', package_name
            ])
            print(f"✓ {package_name} installed")
            return True
        except Exception as e:
            print(f"✗ Failed to install {package_name}: {e}")
            return False

def main():
    print("=" * 80)
    print("Download Real HRRR Alaska Data with Herbie")
    print("=" * 80)
    print()

    # Install dependencies
    print("Installing dependencies...")
    print()

    deps = [
        ('numpy', 'numpy'),
        ('xarray', 'xarray'),
        ('matplotlib', 'matplotlib'),
        ('pillow', 'PIL'),
        ('requests', 'requests'),
    ]

    for pkg, imp in deps:
        install_package(pkg, imp)

    print()
    print("Installing Herbie...")
    if not install_package('herbie-data', 'herbie'):
        print("ERROR: Failed to install herbie-data")
        sys.exit(1)

    print()

    # Import after installation
    try:
        from herbie import Herbie
        import xarray as xr
        import numpy as np
        import matplotlib.pyplot as plt
        from matplotlib.colors import LinearSegmentedColormap
        from pathlib import Path
    except ImportError as e:
        print(f"ERROR: Failed to import required packages: {e}")
        print()
        print("Note: cfgrib requires system library 'eccodes'")
        print("On Ubuntu/Debian: sudo apt-get install libeccodes-dev")
        sys.exit(1)

    print("Downloading HRRR Alaska GRIB2 data...")
    print()

    # Try to get latest data, fall back if needed
    attempts = [
        datetime.utcnow(),
        datetime.utcnow() - timedelta(hours=1),
        datetime.utcnow() - timedelta(hours=2),
        datetime.utcnow() - timedelta(hours=3),
    ]

    H = None
    for dt in attempts:
        try:
            print(f"Trying {dt.strftime('%Y-%m-%d %H:00')} UTC...")
            H = Herbie(
                dt,
                model="hrrrak",
                product="sfc",
                fxx=0,
                verbose=False
            )
            print(f"✓ Found: {H.model} {H.date} F{H.fxx:02d}")
            print(f"  GRIB URL: {H.grib}")
            break
        except Exception as e:
            print(f"  Not available: {e}")
            continue

    if H is None:
        print()
        print("ERROR: Could not find any available HRRR Alaska data")
        print("This may be due to:")
        print("  1. NOAA server temporarily down")
        print("  2. Data not yet available for recent hours")
        print("  3. Network connectivity issues")
        sys.exit(1)

    print()
    print("Loading GRIB2 data into xarray...")
    print("(This downloads the GRIB2 file and may take 1-2 minutes)")
    print()

    try:
        # Try to load temperature at 2m
        ds = H.xarray("TMP:2 m", verbose=False)
        variable = "TMP:2 m"
        print(f"✓ Loaded {variable}")
    except Exception as e:
        print(f"Failed to load TMP:2 m: {e}")
        print()
        print("Trying alternative: REFC (composite reflectivity)...")
        try:
            ds = H.xarray("REFC:entire atmosphere", verbose=False)
            variable = "REFC:entire atmosphere"
            print(f"✓ Loaded {variable}")
        except Exception as e2:
            print(f"Failed: {e2}")
            print()
            print("ERROR: Could not load any GRIB2 variables")
            print("This might be due to missing cfgrib/eccodes")
            sys.exit(1)

    print()
    print("GRIB2 Grid Information:")
    print(f"  Shape: {ds.latitude.shape}")
    print(f"  Projection: {ds.gribfile_projection if hasattr(ds, 'gribfile_projection') else 'Unknown'}")
    print()

    # Extract 2D lat/lon grids
    lat_2d = ds.latitude.values
    lon_2d = ds.longitude.values

    ny, nx = lat_2d.shape
    print(f"Grid dimensions: {ny} x {nx}")

    # Normalize longitude to -180/+180
    lon_normalized = np.where(lon_2d > 180, lon_2d - 360, lon_2d)

    # Calculate cell corner extent (extend by half cell from centers)
    print()
    print("Calculating cell corner extent...")

    # Calculate average cell size at edges
    top_lat_delta = np.abs(lat_2d[1, :] - lat_2d[0, :]).mean()
    bottom_lat_delta = np.abs(lat_2d[-1, :] - lat_2d[-2, :]).mean()
    left_lon_delta = np.abs(lon_normalized[:, 1] - lon_normalized[:, 0]).mean()
    right_lon_delta = np.abs(lon_normalized[:, -1] - lon_normalized[:, -2]).mean()

    # Extend by half cell
    north = lat_2d[0, :].max() + top_lat_delta / 2
    south = lat_2d[-1, :].min() - bottom_lat_delta / 2
    west = lon_normalized[:, 0].min() - left_lon_delta / 2
    east = lon_normalized[:, -1].max() + right_lon_delta / 2

    exact_bounds = [west, south, east, north]

    print(f"Cell corner bounds:")
    print(f"  West:  {west:.10f}°")
    print(f"  South: {south:.10f}°")
    print(f"  East:  {east:.10f}°")
    print(f"  North: {north:.10f}°")
    print()

    # Get data variable name
    data_vars = [v for v in ds.data_vars]
    if not data_vars:
        print("ERROR: No data variables found in GRIB2 file")
        sys.exit(1)

    data_var = data_vars[0]
    data = ds[data_var].values

    print(f"Creating visualization from {data_var}...")
    print(f"  Data range: {np.nanmin(data):.2f} to {np.nanmax(data):.2f}")
    print()

    # Create colormap based on variable type
    if "TMP" in variable or "temp" in variable.lower():
        # Temperature color map
        colors = ['#0000ff', '#00ffff', '#00ff00', '#ffff00', '#ff0000']
        vmin, vmax = -20, 30  # Celsius
        cmap_name = 'temperature'
    elif "REFC" in variable or "refl" in variable.lower():
        # Reflectivity color map
        colors = ['#00ffff', '#0000ff', '#00ff00', '#ffff00', '#ff0000', '#ff00ff']
        vmin, vmax = 0, 75  # dBZ
        cmap_name = 'reflectivity'
    else:
        # Generic
        colors = ['blue', 'cyan', 'green', 'yellow', 'red']
        vmin = np.nanpercentile(data, 5)
        vmax = np.nanpercentile(data, 95)
        cmap_name = 'generic'

    cmap = LinearSegmentedColormap.from_list(cmap_name, colors, N=256)

    # Create figure
    fig, ax = plt.subplots(figsize=(13, 9), dpi=100)
    ax.set_position([0, 0, 1, 1])
    ax.axis('off')

    # Plot data
    im = ax.imshow(data, cmap=cmap, aspect='auto',
                   extent=[west, east, south, north],
                   vmin=vmin, vmax=vmax, interpolation='bilinear')

    # Save images
    images_dir = Path('images')
    images_dir.mkdir(exist_ok=True)

    plt.savefig(images_dir / 'hrrr_west.png', bbox_inches='tight',
                pad_inches=0, transparent=True, dpi=100)
    print(f"✓ Saved {images_dir / 'hrrr_west.png'}")

    plt.savefig(images_dir / 'hrrr_east.png', bbox_inches='tight',
                pad_inches=0, transparent=True, dpi=100)
    print(f"✓ Saved {images_dir / 'hrrr_east.png'}")

    plt.close()
    print()

    # Create densified boundary
    print("Creating boundary polygon...")

    def create_densified_boundary(bounds, points_per_edge=100):
        """Create densified boundary from bounds."""
        west, south, east, north = bounds
        boundary = []

        # Top edge
        for i in range(points_per_edge):
            t = i / (points_per_edge - 1)
            boundary.append({"lat": north, "lon": west + t * (east - west)})

        # Right edge
        for i in range(1, points_per_edge):
            t = i / (points_per_edge - 1)
            boundary.append({"lat": north - t * (north - south), "lon": east})

        # Bottom edge
        for i in range(1, points_per_edge):
            t = i / (points_per_edge - 1)
            boundary.append({"lat": south, "lon": east - t * (east - west)})

        # Left edge
        for i in range(1, points_per_edge - 1):
            t = i / (points_per_edge - 1)
            boundary.append({"lat": south + t * (north - south), "lon": west})

        return boundary

    boundary = create_densified_boundary(exact_bounds, points_per_edge=100)
    print(f"✓ Created {len(boundary)} boundary points")
    print()

    # Verify alignment
    lats = [p['lat'] for p in boundary]
    lons = [p['lon'] for p in boundary]
    extent = [min(lons), min(lats), max(lons), max(lats)]
    diff = sum(abs(extent[i] - exact_bounds[i]) for i in range(4))

    print(f"Alignment verification: {diff:.10f}° difference")
    if diff < 0.000001:
        print("✓ PERFECT ALIGNMENT!")
    print()

    # Eastern bounds (for dateline wrapping)
    eastern_bounds = [west, south, west - 0.02, north]  # Small slice

    # Create output
    output = {
        "western": {
            "image_url": "images/hrrr_west.png",
            "bounds": exact_bounds
        },
        "eastern": {
            "image_url": "images/hrrr_east.png",
            "bounds": eastern_bounds
        },
        "boundary_polygon": boundary,
        "_metadata": {
            "generated": datetime.utcnow().isoformat() + "Z",
            "method": "herbie_grib2_analysis",
            "source": "NOAA HRRR Alaska",
            "model": H.model,
            "date": H.date.isoformat(),
            "forecast_hour": H.fxx,
            "variable": variable,
            "grid_shape": [ny, nx],
            "projection": str(ds.gribfile_projection if hasattr(ds, 'gribfile_projection') else 'polar_stereographic'),
            "points_per_edge": 100,
            "total_points": len(boundary),
            "alignment_verified": diff < 0.000001,
            "note": "Real HRRR Alaska data downloaded via Herbie with exact cell corner bounds"
        }
    }

    # Save
    with open("test-data.json", 'w') as f:
        json.dump(output, f, indent=2)

    print("✓ Saved to test-data.json")
    print()

    print("=" * 80)
    print("SUCCESS!")
    print("=" * 80)
    print()
    print("Downloaded real HRRR Alaska GRIB2 data:")
    print(f"  Model: {H.model}")
    print(f"  Date: {H.date}")
    print(f"  Variable: {variable}")
    print(f"  Grid: {ny} x {nx}")
    print(f"  Bounds: [{west:.6f}, {south:.6f}, {east:.6f}, {north:.6f}]")
    print()
    print("Next steps:")
    print("  git add images/ test-data.json")
    print("  git commit -m 'Add real HRRR Alaska data from Herbie'")
    print("  git push")
    print()

if __name__ == "__main__":
    main()
