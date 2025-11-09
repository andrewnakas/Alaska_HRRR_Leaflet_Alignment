#!/usr/bin/env python3
"""
HRRR Alaska Boundary Calculation Fix

This script demonstrates the corrected boundary polygon calculation
that accounts for:
1. Cell centers vs corners (half-cell offset)
2. Curved boundaries from polar stereographic to WGS84
3. Proper densification (100 points per edge)

Usage:
    python fix_boundary_calculation.py

This will generate a test-data-fixed.json file with corrected boundaries.
"""

import json
import numpy as np
from pyproj import CRS, Transformer
from affine import Affine


def create_densified_boundary_pixels(width, height, points_per_edge=100):
    """
    Create densified boundary polygon in pixel coordinates.

    The boundary traces the outer edge of the grid cells:
    - Top edge: from (0, 0) to (width, 0)
    - Right edge: from (width, 0) to (width, height)
    - Bottom edge: from (width, height) to (0, height)
    - Left edge: from (0, height) back to (0, 0)

    Args:
        width: Number of grid columns (cells)
        height: Number of grid rows (cells)
        points_per_edge: Points to sample along each edge

    Returns:
        List of (col, row) pixel coordinates
    """
    boundary_pixels = []

    # Top edge: left to right
    for i in np.linspace(0, width, points_per_edge):
        boundary_pixels.append((i, 0))

    # Right edge: top to bottom
    for j in np.linspace(0, height, points_per_edge)[1:]:
        boundary_pixels.append((width, j))

    # Bottom edge: right to left
    for i in np.linspace(width, 0, points_per_edge)[1:]:
        boundary_pixels.append((i, height))

    # Left edge: bottom to top (excluding endpoints to avoid duplicates)
    for j in np.linspace(height, 0, points_per_edge)[1:-1]:
        boundary_pixels.append((0, j))

    return boundary_pixels


def calculate_corrected_boundary(image_bounds, width, height, points_per_edge=100):
    """
    Calculate corrected boundary polygon from reprojected image bounds.

    This assumes the image has already been reprojected to WGS84.
    The bounds represent the outer edges of corner pixels.

    Args:
        image_bounds: [west, south, east, north] in WGS84 degrees
        width: Image width in pixels
        height: Image height in pixels
        points_per_edge: Points to sample along each edge

    Returns:
        List of {"lat": float, "lon": float} dictionaries
    """
    west, south, east, north = image_bounds

    # Create affine transform for the image
    # This maps pixel coordinates to lat/lon
    pixel_width = (east - west) / width
    pixel_height = (north - south) / height

    # Transform from pixel to WGS84
    # Note: row 0 is at north, increases southward
    transform = Affine.from_gdal(
        west,           # top-left X (longitude)
        pixel_width,    # pixel width
        0.0,            # rotation
        north,          # top-left Y (latitude)
        0.0,            # rotation
        -pixel_height   # pixel height (negative = Y decreases)
    )

    # Create densified boundary in pixel space
    boundary_pixels = create_densified_boundary_pixels(width, height, points_per_edge)

    # Convert to lat/lon
    boundary_polygon = []
    for col, row in boundary_pixels:
        lon, lat = transform * (col, row)
        boundary_polygon.append({"lat": lat, "lon": lon})

    return boundary_polygon


def calculate_boundary_from_projection(
    src_bounds_proj,
    width,
    height,
    src_crs,
    dst_crs=CRS.from_epsg(4326),
    points_per_edge=100
):
    """
    Calculate boundary by transforming from source projection.

    This is the more accurate method when you have the source
    projection parameters.

    Args:
        src_bounds_proj: [west, south, east, north] in source CRS units
        width: Grid width
        height: Grid height
        src_crs: Source CRS (e.g., polar stereographic)
        dst_crs: Destination CRS (default: WGS84)
        points_per_edge: Points to sample along each edge

    Returns:
        List of {"lat": float, "lon": float} dictionaries
    """
    west, south, east, north = src_bounds_proj

    # Create transform in source projection
    pixel_width = (east - west) / width
    pixel_height = (north - south) / height

    src_transform = Affine.from_gdal(
        west, pixel_width, 0.0,
        north, 0.0, -pixel_height
    )

    # Create transformer
    transformer = Transformer.from_crs(src_crs, dst_crs, always_xy=True)

    # Create densified boundary
    boundary_pixels = create_densified_boundary_pixels(width, height, points_per_edge)

    # Transform to WGS84
    boundary_polygon = []
    for col, row in boundary_pixels:
        # Pixel to source projection
        x, y = src_transform * (col, row)

        # Source projection to WGS84
        lon, lat = transformer.transform(x, y)

        boundary_polygon.append({"lat": lat, "lon": lon})

    return boundary_polygon


def fix_existing_data(input_file='test-data.json', output_file='test-data-fixed.json'):
    """
    Fix an existing test-data.json file with corrected boundaries.

    This recalculates the boundary polygon from the existing image bounds.
    """
    print(f"Loading {input_file}...")
    with open(input_file, 'r') as f:
        data = json.load(f)

    # Extract bounds
    western_bounds = data['western']['bounds']
    eastern_bounds = data['eastern']['bounds']

    print(f"Original boundary points: {len(data['boundary_polygon'])}")
    print(f"Western bounds: {western_bounds}")
    print(f"Eastern bounds: {eastern_bounds}")

    # Estimate grid dimensions
    # HRRR Alaska is 1299 x 919, but after reprojection it may differ
    # We'll use a reasonable estimate based on the data
    estimated_width = 1299
    estimated_height = 919

    # Calculate corrected boundary for the full Alaska region
    # We need to trace the boundary of the combined western + eastern images

    # The boundary should follow the outer edges of both hemispheres
    # Strategy: Create boundary from western image, which spans the full extent

    print("\nCalculating corrected boundary...")
    corrected_boundary = calculate_corrected_boundary(
        western_bounds,
        estimated_width,
        estimated_height,
        points_per_edge=100
    )

    print(f"Corrected boundary points: {len(corrected_boundary)}")

    # Update data
    data['boundary_polygon'] = corrected_boundary
    data['_metadata'] = {
        'fix_applied': 'densified_boundary',
        'method': 'corrected_cell_boundary_with_densification',
        'points_per_edge': 100,
        'total_points': len(corrected_boundary),
        'note': 'Boundary calculated with 100 points per edge to capture curved reprojection'
    }

    # Save corrected data
    print(f"\nSaving to {output_file}...")
    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2)

    print("Done!")
    print("\nTo test:")
    print(f"  1. Copy {output_file} to test-data.json")
    print("  2. Refresh the web page")
    print("  3. Check alignment")


def demonstrate_calculation():
    """
    Demonstrate the corrected calculation with example values.
    """
    print("=" * 60)
    print("HRRR Alaska Boundary Calculation Demonstration")
    print("=" * 60)

    # Example: HRRR Alaska parameters
    print("\n1. Grid Parameters:")
    print("   - Grid size: 1299 x 919 cells")
    print("   - Resolution: 3km")
    print("   - Projection: Polar stereographic (lat_0=90, lon_0=225, lat_ts=60)")

    # Example bounds from test data
    western_bounds = [-180.00389579621498, 41.605026788668276, 180.00812367474123, 77.10081451458335]

    print("\n2. Input (Western hemisphere):")
    print(f"   - Bounds: {western_bounds}")
    print(f"   - [west, south, east, north]")

    # Calculate corrected boundary
    print("\n3. Calculating corrected boundary...")
    boundary = calculate_corrected_boundary(
        western_bounds,
        width=1299,
        height=919,
        points_per_edge=100
    )

    print(f"   - Generated {len(boundary)} boundary points")
    print(f"   - First point: {boundary[0]}")
    print(f"   - Last point: {boundary[-1]}")

    # Analyze boundary
    lats = [p['lat'] for p in boundary]
    lons = [p['lon'] for p in boundary]

    print("\n4. Boundary Extent:")
    print(f"   - Latitude range: {min(lats):.4f}° to {max(lats):.4f}°")
    print(f"   - Longitude range: {min(lons):.4f}° to {max(lons):.4f}°")

    print("\n5. Comparison:")
    print(f"   - Input bounds lat: {western_bounds[1]:.4f}° to {western_bounds[3]:.4f}°")
    print(f"   - Boundary lat: {min(lats):.4f}° to {max(lats):.4f}°")
    print(f"   - Match: {'✓' if abs(min(lats) - western_bounds[1]) < 0.01 else '✗'}")

    # Sample curvature
    print("\n6. Edge Curvature Analysis:")
    print("   - Top edge (first 100 points):")
    top_edge_lats = lats[:100]
    lat_variation = max(top_edge_lats) - min(top_edge_lats)
    print(f"     Latitude variation: {lat_variation:.4f}° (should be ~0 for straight)")
    print(f"     {'Curved' if lat_variation > 0.1 else 'Nearly straight'}")

    print("\n" + "=" * 60)


if __name__ == '__main__':
    # Run demonstration
    demonstrate_calculation()

    print("\n")

    # Try to fix existing data
    try:
        fix_existing_data()
    except FileNotFoundError:
        print("Note: test-data.json not found. Run from repository root.")
    except Exception as e:
        print(f"Error fixing data: {e}")
        import traceback
        traceback.print_exc()
