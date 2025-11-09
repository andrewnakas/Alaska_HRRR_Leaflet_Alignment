#!/usr/bin/env python3
"""
Create perfect HRRR Alaska boundary using Herbie + direct GRIB2 grid analysis.

This script:
1. Downloads latest HRRR Alaska GRIB2 using Herbie
2. Extracts the 2D lat/lon grid (919 x 1299)
3. Computes cell CORNERS (not centers) for exact boundary
4. Creates densified boundary polygon matching the grid extent
5. Generates test-data.json with perfect alignment
"""

import json
import numpy as np
from datetime import datetime, timedelta

def install_dependencies():
    """Install required packages if not available."""
    import subprocess
    import sys

    packages = {
        'herbie-data': 'herbie',
        'cfgrib': 'cfgrib',
        'xarray': 'xarray'
    }

    for package, import_name in packages.items():
        try:
            __import__(import_name)
            print(f"✓ {package} already installed")
        except ImportError:
            print(f"Installing {package}...")
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q', package])
            print(f"✓ {package} installed")

def get_cell_corners_extent(lat_2d, lon_2d):
    """
    Calculate the extent of cell corners from 2D lat/lon grid.

    HRRR grid points represent cell CENTERS. To get the actual data extent,
    we need to extend half a cell in each direction.

    Args:
        lat_2d: 2D array of latitudes (919, 1299)
        lon_2d: 2D array of longitudes (919, 1299)

    Returns:
        (west, south, east, north) in degrees
    """
    ny, nx = lat_2d.shape

    # Get corner points (outermost cells)
    top_left = (lat_2d[0, 0], lon_2d[0, 0])
    top_right = (lat_2d[0, -1], lon_2d[0, -1])
    bottom_left = (lat_2d[-1, 0], lon_2d[-1, 0])
    bottom_right = (lat_2d[-1, -1], lon_2d[-1, -1])

    # Calculate cell size at edges (for half-cell extension)
    # Top edge: average spacing between first two rows
    top_lat_delta = np.abs(lat_2d[1, :] - lat_2d[0, :]).mean()
    top_lon_delta = np.abs(lon_2d[0, 1:] - lon_2d[0, :-1]).mean()

    # Bottom edge
    bottom_lat_delta = np.abs(lat_2d[-1, :] - lat_2d[-2, :]).mean()
    bottom_lon_delta = np.abs(lon_2d[-1, 1:] - lon_2d[-1, :-1]).mean()

    # Left edge
    left_lat_delta = np.abs(lat_2d[1:, 0] - lat_2d[:-1, 0]).mean()
    left_lon_delta = np.abs(lon_2d[:, 1] - lon_2d[:, 0]).mean()

    # Right edge
    right_lat_delta = np.abs(lat_2d[1:, -1] - lat_2d[:-1, -1]).mean()
    right_lon_delta = np.abs(lon_2d[:, -1] - lon_2d[:, -2]).mean()

    # Extend by half cell in each direction
    north = lat_2d[0, :].max() + top_lat_delta / 2
    south = lat_2d[-1, :].min() - bottom_lat_delta / 2

    # Handle dateline crossing for longitude
    # HRRR Alaska uses 0-360 convention, convert to -180/+180
    lon_normalized = np.where(lon_2d > 180, lon_2d - 360, lon_2d)

    west = lon_normalized[:, 0].min() - left_lon_delta / 2
    east = lon_normalized[:, -1].max() + right_lon_delta / 2

    return (west, south, east, north)

def create_densified_boundary_from_2d_grid(lat_2d, lon_2d, points_per_edge=100):
    """
    Create densified boundary from 2D grid edges.

    This samples the actual grid edge points and interpolates between them,
    preserving the curvature from the polar stereographic projection.

    Args:
        lat_2d: 2D array of latitudes (919, 1299)
        lon_2d: 2D array of longitudes (919, 1299)
        points_per_edge: number of points to sample per edge

    Returns:
        List of {"lat": float, "lon": float} dicts
    """
    ny, nx = lat_2d.shape
    boundary = []

    # Normalize longitude to -180/+180
    lon_normalized = np.where(lon_2d > 180, lon_2d - 360, lon_2d)

    # Top edge (left to right): row 0
    indices = np.linspace(0, nx - 1, points_per_edge, dtype=int)
    for i in indices:
        boundary.append({
            "lat": float(lat_2d[0, i]),
            "lon": float(lon_normalized[0, i])
        })

    # Right edge (top to bottom): column -1
    indices = np.linspace(1, ny - 1, points_per_edge, dtype=int)
    for i in indices:
        boundary.append({
            "lat": float(lat_2d[i, -1]),
            "lon": float(lon_normalized[i, -1])
        })

    # Bottom edge (right to left): row -1
    indices = np.linspace(nx - 2, 0, points_per_edge, dtype=int)
    for i in indices:
        boundary.append({
            "lat": float(lat_2d[-1, i]),
            "lon": float(lon_normalized[-1, i])
        })

    # Left edge (bottom to top): column 0
    indices = np.linspace(ny - 2, 1, points_per_edge - 1, dtype=int)
    for i in indices:
        boundary.append({
            "lat": float(lat_2d[i, 0]),
            "lon": float(lon_normalized[i, 0])
        })

    return boundary

def create_simple_rect_boundary(bounds, points_per_edge=100):
    """
    Create simple rectangular boundary from bounds for comparison.

    Args:
        bounds: (west, south, east, north)
        points_per_edge: number of points per edge

    Returns:
        List of {"lat": float, "lon": float} dicts
    """
    west, south, east, north = bounds
    boundary = []

    # Top edge: west to east
    for i in range(points_per_edge):
        t = i / (points_per_edge - 1)
        boundary.append({
            "lat": north,
            "lon": west + t * (east - west)
        })

    # Right edge: north to south
    for i in range(1, points_per_edge):
        t = i / (points_per_edge - 1)
        boundary.append({
            "lat": north - t * (north - south),
            "lon": east
        })

    # Bottom edge: east to west
    for i in range(1, points_per_edge):
        t = i / (points_per_edge - 1)
        boundary.append({
            "lat": south,
            "lon": east - t * (east - west)
        })

    # Left edge: south to north
    for i in range(1, points_per_edge - 1):
        t = i / (points_per_edge - 1)
        boundary.append({
            "lat": south + t * (north - south),
            "lon": west
        })

    return boundary

def main():
    print("=" * 80)
    print("HRRR Alaska Boundary Generator using Herbie + GRIB2")
    print("=" * 80)
    print()

    # Check dependencies
    print("Checking dependencies...")
    install_dependencies()
    print()

    # Import after installation
    from herbie import Herbie

    print("Downloading latest HRRR Alaska GRIB2 data...")
    print()

    # Get latest HRRR Alaska forecast (hour 0)
    try:
        H = Herbie(
            datetime.utcnow(),
            model="hrrrak",
            product="sfc",
            fxx=0,
            verbose=False
        )

        print(f"✓ Found: {H.model} {H.date} F{H.fxx:02d}")
        print(f"  File: {H.grib}")
        print()

    except Exception as e:
        print(f"⚠ Could not get current data: {e}")
        print("  Trying yesterday's data...")
        H = Herbie(
            datetime.utcnow() - timedelta(days=1),
            model="hrrrak",
            product="sfc",
            fxx=0,
            verbose=False
        )
        print(f"✓ Found: {H.model} {H.date} F{H.fxx:02d}")
        print()

    print("Loading data into xarray (this may take a moment)...")

    # Load a simple variable to get the grid
    # Use temperature at 2m - always available
    ds = H.xarray("TMP:2 m", verbose=False)

    print("✓ Data loaded")
    print()

    # Extract 2D lat/lon grids
    lat_2d = ds.latitude.values
    lon_2d = ds.longitude.values

    print(f"Grid shape: {lat_2d.shape} (y, x)")
    print(f"Projection: {ds.gribfile_projection}")
    print()

    # Get cell corner extent
    print("Calculating cell corner extent...")
    west, south, east, north = get_cell_corners_extent(lat_2d, lon_2d)

    print(f"Grid Extent (cell corners):")
    print(f"  West:  {west:.6f}°")
    print(f"  South: {south:.6f}°")
    print(f"  East:  {east:.6f}°")
    print(f"  North: {north:.6f}°")
    print()

    # Create two types of boundaries for comparison
    print("Creating boundary polygons...")

    # Method 1: Follow actual grid edge (recommended - captures curvature)
    boundary_grid = create_densified_boundary_from_2d_grid(lat_2d, lon_2d, points_per_edge=100)

    # Method 2: Simple rectangle from extent
    boundary_rect = create_simple_rect_boundary((west, south, east, north), points_per_edge=100)

    print(f"✓ Grid-based boundary: {len(boundary_grid)} points")
    print(f"✓ Rectangle boundary: {len(boundary_rect)} points")
    print()

    # For dateline-crossing images, split into western and eastern
    # Western: crosses the dateline (-180 to +180)
    # Eastern: on the other side (-180 to -180.x)

    # Use the simple rect method for now (can switch to grid method if needed)
    boundary_polygon = boundary_rect

    # Create output data structure
    output = {
        "western": {
            "image_url": "https://storage.googleapis.com/noaa-hrrr-alaska-pds/western_image.webp",
            "bounds": [west, south, east, north]
        },
        "eastern": {
            "image_url": "https://storage.googleapis.com/noaa-hrrr-alaska-pds/eastern_image.webp",
            "bounds": [west, south, east, north]
        },
        "boundary_polygon": boundary_polygon,
        "_metadata": {
            "source": "herbie_grib2_analysis",
            "model": H.model,
            "date": H.date.isoformat(),
            "forecast_hour": H.fxx,
            "grid_shape": list(lat_2d.shape),
            "projection": str(ds.gribfile_projection),
            "method": "cell_corner_extent_with_densified_boundary",
            "points_per_edge": 100,
            "total_boundary_points": len(boundary_polygon),
            "generated_at": datetime.utcnow().isoformat() + "Z"
        }
    }

    # Save to file
    output_file = "test-data-herbie.json"
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"✓ Saved to {output_file}")
    print()

    # Also save grid-based boundary separately for testing
    output_grid = output.copy()
    output_grid["boundary_polygon"] = boundary_grid
    output_grid["_metadata"]["method"] = "grid_edge_sampling_with_interpolation"

    output_file_grid = "test-data-herbie-gridmethod.json"
    with open(output_file_grid, 'w') as f:
        json.dump(output_grid, f, indent=2)

    print(f"✓ Saved grid-based version to {output_file_grid}")
    print()

    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print()
    print("Two boundary methods generated:")
    print()
    print(f"1. {output_file}")
    print("   - Rectangle boundary from cell corner extent")
    print("   - Simple but accurate for regularly gridded data")
    print()
    print(f"2. {output_file_grid}")
    print("   - Follows actual grid edge points")
    print("   - Captures polar stereographic curvature")
    print("   - RECOMMENDED for best alignment")
    print()
    print("Next steps:")
    print("1. Copy one of these files to test-data.json")
    print("2. Refresh your map in the browser")
    print("3. Check alignment - should be perfect!")
    print()
    print("Note: You'll need to update image URLs to match your actual HRRR images")
    print()

if __name__ == "__main__":
    main()
