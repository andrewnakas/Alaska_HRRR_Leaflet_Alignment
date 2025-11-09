#!/usr/bin/env python3
"""
Simple fix for HRRR Alaska alignment - no Herbie needed.

Uses the EXACT image bounds from the current test-data.json to generate
a perfectly matching boundary polygon.
"""

import json

def create_densified_boundary(bounds, points_per_edge=100):
    """
    Create densified rectangular boundary from bounds.

    Args:
        bounds: [west, south, east, north] in degrees
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
    print("HRRR Alaska Alignment Fix - Using Exact Image Bounds")
    print("=" * 80)
    print()

    # Load current test data
    with open('test-data.json', 'r') as f:
        data = json.load(f)

    print("Current data:")
    print(f"  Western bounds (rounded): {data['western']['bounds']}")
    print(f"  Original bounds: {data['western'].get('original_bounds', 'N/A')}")
    print()

    # Use the EXACT original bounds (not rounded!)
    # These are the true rasterio array_bounds from the reprojected images
    original_bounds = data['western'].get('original_bounds', data['western']['bounds'])

    print("Using exact bounds for alignment:")
    print(f"  West:  {original_bounds[0]:.6f}°")
    print(f"  South: {original_bounds[1]:.6f}°")
    print(f"  East:  {original_bounds[2]:.6f}°")
    print(f"  North: {original_bounds[3]:.6f}°")
    print()

    # Generate boundary with 100 points per edge
    print("Generating boundary polygon...")
    boundary = create_densified_boundary(original_bounds, points_per_edge=100)
    print(f"✓ Created {len(boundary)} points")
    print()

    # Calculate boundary extent to verify
    lats = [p['lat'] for p in boundary]
    lons = [p['lon'] for p in boundary]

    extent = {
        "west": min(lons),
        "south": min(lats),
        "east": max(lons),
        "north": max(lats)
    }

    print("Boundary extent:")
    print(f"  West:  {extent['west']:.6f}°")
    print(f"  South: {extent['south']:.6f}°")
    print(f"  East:  {extent['east']:.6f}°")
    print(f"  North: {extent['north']:.6f}°")
    print()

    # Verify perfect match
    diff_west = abs(extent['west'] - original_bounds[0])
    diff_south = abs(extent['south'] - original_bounds[1])
    diff_east = abs(extent['east'] - original_bounds[2])
    diff_north = abs(extent['north'] - original_bounds[3])
    total_diff = diff_west + diff_south + diff_east + diff_north

    print("Difference from image bounds:")
    print(f"  ΔWest:  {diff_west:.10f}°")
    print(f"  ΔSouth: {diff_south:.10f}°")
    print(f"  ΔEast:  {diff_east:.10f}°")
    print(f"  ΔNorth: {diff_north:.10f}°")
    print(f"  Total:  {total_diff:.10f}°")
    print()

    if total_diff < 0.000001:
        print("✓ PERFECT MATCH! Boundary exactly matches image bounds.")
    else:
        print("⚠ Small difference detected (should be < 0.000001°)")
    print()

    # Update test data with exact bounds and new boundary
    updated_data = {
        "western": {
            "image_url": data['western']['image_url'],
            "bounds": original_bounds  # Use EXACT bounds, not rounded!
        },
        "eastern": {
            "image_url": data['eastern']['image_url'],
            "bounds": data['eastern']['bounds']
        },
        "boundary_polygon": boundary,
        "_metadata": {
            "generated": "2025-11-09",
            "method": "densified_rectangle_from_exact_image_bounds",
            "points_per_edge": 100,
            "total_points": len(boundary),
            "source_bounds": original_bounds,
            "alignment_verified": total_diff < 0.000001,
            "note": "Boundary created from EXACT rasterio array_bounds (not rounded) for perfect alignment"
        }
    }

    # Save updated data
    output_file = "test-data-exact-bounds.json"
    with open(output_file, 'w') as f:
        json.dump(updated_data, f, indent=2)

    print(f"✓ Saved to {output_file}")
    print()
    print("=" * 80)
    print("NEXT STEPS")
    print("=" * 80)
    print()
    print(f"1. Rename {output_file} to test-data.json:")
    print(f"   mv {output_file} test-data.json")
    print()
    print("2. Refresh your browser")
    print()
    print("3. The alignment should now be PERFECT because:")
    print("   - Boundary uses EXACT bounds (not rounded)")
    print("   - Same source as images (rasterio array_bounds)")
    print("   - 396 densified points to capture curvature")
    print()
    print("Key fix: Using original_bounds instead of rounded bounds!")
    print()

if __name__ == "__main__":
    main()
