# CRITICAL FINDING: Boundary vs Image Bounds Mismatch

## The Real Problem

Looking at your logs, I found the root cause:

### Image Bounds (from API):
```
Western: [-180.004, 41.605, 180.008, 77.101]
Eastern: [-179.985, 41.605, 179.994, 77.101]
```

### Boundary Polygon Actual Extent:
```
West:  -179.854  (should be -180.004)  ← Missing 0.15° (~15km)
East:   179.643  (should be  180.008)  ← Missing 0.37° (~37km)
North:   77.085  (should be   77.101)  ← Missing 0.016° (~1.6km)
South:   41.621  (should be   41.605)  ← Extends 0.016° beyond
```

## The Issue

**The boundary polygon is significantly SMALLER than the image bounds!**

This explains the misalignment - the boundary is being calculated from GRIB2 grid cell centers,
while the images are reprojected to include the full extent of those cells (including half-cell
beyond the outermost centers).

## Visual Representation

```
Image Bounds:                    Boundary Polygon:
+-------------------------+
|                         |      +-------------------+
|   Boundary should       |      |  Actual boundary  |
|   match this exactly    |      |  is too small!    |
|                         |      +-------------------+
|                         |
+-------------------------+
```

## The Fix

The boundary polygon MUST be calculated from the **same source** as the image bounds.

### Option 1: Use Image Bounds Directly (Simplest)

Since we already have `western.bounds` and `eastern.bounds`, create a densified boundary
that traces these exact bounds:

```python
# In backend: Use the SAME bounds that were used for the images
western_bounds = exact_bounds_west  # The bounds used for western image
boundary_polygon = calculate_densified_boundary(western_bounds, width, height)
```

### Option 2: Fix Grid Cell Offset (Root Cause)

The GRIB2 grid points are cell CENTERS, so when creating the boundary:

```python
# Add half-cell offset to extend to actual cell edges
first_corner_x = first_center_x - dx / 2.0
first_corner_y = first_center_y - dy / 2.0
```

## Why This Matters

The current ~0.15° to 0.37° discrepancy is approximately **15-37 km** of misalignment at these
latitudes. That's why the boundary doesn't trace the image edges - it's literally calculated
from a different extent!

## Action Required

The backend code needs to ensure:
1. Image bounds calculation includes half-cell extension
2. Boundary polygon uses THE EXACT SAME bounds as the images
3. Both are calculated from grid corners (not centers)

The boundary should match `western.bounds` exactly when densified and traced.
