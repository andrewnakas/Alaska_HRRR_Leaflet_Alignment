#!/usr/bin/env python3
"""
Find optimal alignment where PNG non-transparent pixels fit inside boundary
and maximize pixels touching the border.
"""

import json
import numpy as np
from PIL import Image
from pathlib import Path
from shapely.geometry import Polygon, Point
from shapely.prepared import prep
from scipy.optimize import differential_evolution
import matplotlib.pyplot as plt

def load_data():
    """Load boundary polygon and image bounds from test-data.json"""
    with open('test-data.json', 'r') as f:
        data = json.load(f)

    # Get boundary polygon
    boundary_coords = [(p['lon'], p['lat']) for p in data['boundary_polygon']]
    boundary_poly = Polygon(boundary_coords)

    # Get base image bounds
    bounds = data['continuous']['bounds']  # [west, south, east, north]

    return boundary_poly, bounds, data

def load_image():
    """Load PNG and find non-transparent pixels"""
    img_path = Path('images/hrrr_continuous.png')
    img = Image.open(img_path).convert('RGBA')
    img_array = np.array(img)

    # Find non-transparent pixels (alpha > 0)
    alpha = img_array[:, :, 3]
    non_transparent = alpha > 0

    return img_array, non_transparent

def transform_bounds(base_bounds, lon_offset, lat_offset, lon_scale, lat_scale):
    """Apply transformation to bounds"""
    west, south, east, north = base_bounds

    # Calculate center
    center_lon = (west + east) / 2
    center_lat = (south + north) / 2

    # Apply scaling from center
    lon_span = (east - west) * lon_scale
    lat_span = (north - south) * lat_scale

    west = center_lon - lon_span / 2
    east = center_lon + lon_span / 2
    south = center_lat - lat_span / 2
    north = center_lat + lat_span / 2

    # Apply offset
    west += lon_offset
    east += lon_offset
    south += lat_offset
    north += lat_offset

    return [west, south, east, north]

def rotate_point(lon, lat, center_lon, center_lat, rotation_deg):
    """Rotate a point around a center by rotation_deg degrees"""
    # Convert to radians
    theta = np.radians(rotation_deg)

    # Translate to origin
    lon_rel = lon - center_lon
    lat_rel = lat - center_lat

    # Rotate
    lon_rotated = lon_rel * np.cos(theta) - lat_rel * np.sin(theta)
    lat_rotated = lon_rel * np.sin(theta) + lat_rel * np.cos(theta)

    # Translate back
    return center_lon + lon_rotated, center_lat + lat_rotated

def get_pixel_coords(non_transparent, bounds, rotation_deg=0):
    """Get geographic coordinates of non-transparent pixels"""
    west, south, east, north = bounds
    height, width = non_transparent.shape

    # Create coordinate grids
    lons = np.linspace(west, east, width)
    lats = np.linspace(north, south, height)  # Top to bottom

    # Get coordinates of non-transparent pixels
    y_indices, x_indices = np.where(non_transparent)
    pixel_lons = lons[x_indices]
    pixel_lats = lats[y_indices]

    # Apply rotation if specified
    if rotation_deg != 0:
        center_lon = (west + east) / 2
        center_lat = (south + north) / 2
        pixel_lons, pixel_lats = rotate_point(pixel_lons, pixel_lats, center_lon, center_lat, rotation_deg)

    return pixel_lons, pixel_lats

def evaluate_alignment(params, base_bounds, non_transparent, boundary_poly, prepared_boundary):
    """
    Evaluate alignment quality.
    Returns penalty (lower is better).
    """
    lon_offset, lat_offset, lon_scale, lat_scale, rotation_deg = params

    # Transform bounds
    transformed_bounds = transform_bounds(base_bounds, lon_offset, lat_offset, lon_scale, lat_scale)

    # Get pixel coordinates with rotation
    pixel_lons, pixel_lats = get_pixel_coords(non_transparent, transformed_bounds, rotation_deg)

    # Sample pixels for faster computation (use every Nth pixel)
    sample_rate = max(1, len(pixel_lons) // 5000)
    pixel_lons = pixel_lons[::sample_rate]
    pixel_lats = pixel_lats[::sample_rate]

    # Check if all pixels are inside boundary
    points = [Point(lon, lat) for lon, lat in zip(pixel_lons, pixel_lats)]
    inside = [prepared_boundary.contains(point) for point in points]

    num_inside = sum(inside)
    num_total = len(points)

    # If any pixels outside, heavy penalty
    if num_inside < num_total:
        num_outside = num_total - num_inside
        penalty = 1000000 + num_outside * 1000
        return penalty

    # All pixels inside - now maximize border contact
    # Calculate distance to boundary for each pixel
    distances = [boundary_poly.boundary.distance(point) for point in points]

    # Count pixels near boundary (within threshold)
    threshold = 0.5  # degrees
    near_boundary = sum(1 for d in distances if d < threshold)

    # We want to maximize near_boundary, so minimize negative
    # Also penalize if bounds are too small (incentivize filling space)
    west, south, east, north = transformed_bounds
    area = (east - west) * (north - south)

    # Penalty is negative of border contact score, with area bonus
    penalty = -near_boundary - (area / 1000)

    return penalty

def find_optimal_alignment():
    """Find optimal alignment parameters"""
    print("="*80)
    print("Finding Optimal Alignment")
    print("="*80)
    print()

    # Load data
    print("Loading data...")
    boundary_poly, base_bounds, data = load_data()
    prepared_boundary = prep(boundary_poly)

    print(f"Base bounds: {base_bounds}")
    print(f"Boundary polygon: {len(boundary_poly.exterior.coords)} points")
    print()

    # Load image
    print("Loading image...")
    img_array, non_transparent = load_image()
    num_pixels = non_transparent.sum()
    print(f"Image shape: {img_array.shape[:2]}")
    print(f"Non-transparent pixels: {num_pixels:,}")
    print()

    # Define search bounds for optimization
    # [lon_offset, lat_offset, lon_scale, lat_scale, rotation_deg]
    bounds = [
        (-20, 20),   # lon_offset: ±20 degrees
        (-20, 20),   # lat_offset: ±20 degrees
        (0.5, 2.0),  # lon_scale: 0.5x to 2.0x
        (0.5, 2.0),  # lat_scale: 0.5x to 2.0x
        (-45, 45)    # rotation_deg: ±45 degrees
    ]

    print("Starting optimization...")
    print("Search space:")
    print(f"  Longitude offset: {bounds[0]}")
    print(f"  Latitude offset: {bounds[1]}")
    print(f"  Longitude scale: {bounds[2]}")
    print(f"  Latitude scale: {bounds[3]}")
    print(f"  Rotation: {bounds[4]}")
    print()

    # Run optimization
    result = differential_evolution(
        evaluate_alignment,
        bounds,
        args=(base_bounds, non_transparent, boundary_poly, prepared_boundary),
        maxiter=100,
        popsize=15,
        tol=0.01,
        seed=42,
        workers=1,
        updating='deferred',
        disp=True
    )

    print()
    print("="*80)
    print("Optimization Results")
    print("="*80)

    lon_offset, lat_offset, lon_scale, lat_scale, rotation_deg = result.x

    print(f"Optimal parameters:")
    print(f"  Longitude offset: {lon_offset:+.3f}°")
    print(f"  Latitude offset: {lat_offset:+.3f}°")
    print(f"  Longitude scale: {lon_scale:.3f}x")
    print(f"  Latitude scale: {lat_scale:.3f}x")
    print(f"  Rotation: {rotation_deg:+.1f}°")
    print(f"  Penalty score: {result.fun:.2f}")
    print()

    # Calculate final bounds
    optimal_bounds = transform_bounds(base_bounds, lon_offset, lat_offset, lon_scale, lat_scale)

    print(f"Optimal bounds:")
    print(f"  West: {optimal_bounds[0]:.4f}°")
    print(f"  South: {optimal_bounds[1]:.4f}°")
    print(f"  East: {optimal_bounds[2]:.4f}°")
    print(f"  North: {optimal_bounds[3]:.4f}°")
    print()

    # Verify all pixels inside
    pixel_lons, pixel_lats = get_pixel_coords(non_transparent, optimal_bounds, rotation_deg)
    sample_rate = max(1, len(pixel_lons) // 10000)
    sample_lons = pixel_lons[::sample_rate]
    sample_lats = pixel_lats[::sample_rate]

    points = [Point(lon, lat) for lon, lat in zip(sample_lons, sample_lats)]
    inside = [prepared_boundary.contains(point) for point in points]

    print(f"Verification (sampled {len(points):,} pixels):")
    print(f"  Inside boundary: {sum(inside):,} / {len(points):,}")
    print(f"  Coverage: {100*sum(inside)/len(points):.1f}%")
    print()

    # Save to alignment_config.json
    config = {
        "comment": "Optimal alignment found programmatically with rotation",
        "adjustments": {
            "lon_offset": float(lon_offset),
            "lat_offset": float(lat_offset),
            "lon_scale": float(lon_scale),
            "lat_scale": float(lat_scale),
            "west_adjustment": 0.0,
            "east_adjustment": 0.0,
            "north_adjustment": 0.0,
            "south_adjustment": 0.0,
            "rotation_degrees": float(rotation_deg),
            "skew_x": 0.0,
            "skew_y": 0.0
        },
        "instructions": {
            "note": "These values were computed automatically to maximize alignment with rotation included",
            "lon_offset": f"Shift entire image east (+) or west (-) in degrees: {lon_offset:+.3f}°",
            "lat_offset": f"Shift entire image north (+) or south (-) in degrees: {lat_offset:+.3f}°",
            "lon_scale": f"Horizontal scale factor: {lon_scale:.3f}x",
            "lat_scale": f"Vertical scale factor: {lat_scale:.3f}x",
            "rotation_degrees": f"Rotation clockwise in degrees: {rotation_deg:+.1f}°"
        },
        "optimal_bounds": {
            "west": float(optimal_bounds[0]),
            "south": float(optimal_bounds[1]),
            "east": float(optimal_bounds[2]),
            "north": float(optimal_bounds[3])
        }
    }

    with open('alignment_config.json', 'w') as f:
        json.dump(config, f, indent=2)

    print("✓ Saved to alignment_config.json")
    print()
    print("="*80)
    print("SUCCESS!")
    print("="*80)

    return result

if __name__ == '__main__':
    result = find_optimal_alignment()
