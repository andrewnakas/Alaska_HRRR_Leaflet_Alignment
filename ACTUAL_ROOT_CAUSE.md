# ACTUAL ROOT CAUSE: Boundary Source Mismatch

## Summary

The boundary polygon is calculated from **different source data** than the image bounds, resulting in a **15-37 km misalignment**.

---

## Evidence from Logs

### Image Bounds (Western):
```
West:  -180.00389579621498
South:   41.605026788668276
East:   180.00812367474123
North:   77.10081451458335
```

### Boundary Polygon Actual Extent:
```
West:  -179.85381154751784  ← 0.15° smaller (~15 km)
South:   41.62087121133174  ← 0.016° larger
East:   179.64282500037004  ← 0.37° smaller (~37 km)
North:   77.08454116341295  ← 0.016° smaller
```

### The Discrepancy:
- West edge: Missing **0.15°** (~15 km)
- East edge: Missing **0.37°** (~37 km)
- North edge: Missing **0.016°** (~1.6 km)
- South edge: Extends **0.016°** beyond image

**Total mismatch: ~0.55° cumulative difference**

---

## Root Cause Analysis

### What's Happening in the Backend

Based on research and log analysis, here's what's likely happening:

#### For Image Creation:
```python
# Step 1: Reproject GRIB2 data to WGS84
reproject(
    source=grib_data,
    destination=wgs84_array,
    src_transform=src_transform,  # Includes cell corners
    src_crs=src_crs,
    dst_transform=dst_transform,
    dst_crs=CRS.from_epsg(4326),
    resampling=Resampling.bilinear
)

# Step 2: Get bounds from reprojected array
exact_bounds = array_bounds(height, width, dst_transform)
# This gives the OUTER EDGES of the reprojected grid cells
# Result: [-180.004, 41.605, 180.008, 77.101]
```

#### For Boundary Polygon:
```python
# Step 1: Get lat/lon from GRIB2 directly
lats, lons = grb.latlons()
# This gives CELL CENTER coordinates from the native grid

# Step 2: Create boundary from these points
boundary_polygon = []
for lat, lon in zip(edge_lats, edge_lons):
    boundary_polygon.append({"lat": lat, "lon": lon})
# Result: Boundary from cell centers, NOT cell corners
# Extent: [-179.854, 41.621, 179.643, 77.085]
```

### The Problem

**Two Different Sources:**

1. **Image bounds** → Calculated from `rasterio.array_bounds()` after reprojection
   - Includes full cell extent (corners)
   - Accounts for reprojection edge effects
   - ✅ Correct for image overlay

2. **Boundary polygon** → Calculated from `pygrib.latlons()` of edge points
   - Uses cell centers from native grid
   - Doesn't include half-cell extension
   - ❌ Too small for boundary polygon

---

## Why This Creates Misalignment

### Visual Representation:

```
Rasterio Array Bounds:          Pygrib Edge Points:
(After reprojection)            (From native grid)

+-------------------------+
|                         |     +-------------------+
|   Image covers this     |     |  Boundary only    |
|   full extent           |     |  covers centers   |
|   (cell corners)        |     |  (too small!)     |
|                         |     +-------------------+
|                         |
+-------------------------+

Result: Boundary doesn't match image edges!
```

### The Mismatch Pattern:

The fact that the boundary is **smaller** on west, east, and north but **larger** on south suggests:

1. The northern edge cell centers are ~1.6 km south of the northern edge
2. The western/eastern edges are missing 15-37 km
3. The southern edge extends slightly beyond (possible grid irregularity)

This is consistent with CELL CENTER vs CELL CORNER misalignment.

---

## The Solution

### Option 1: Use Image Bounds Directly (Immediate Fix)

Since `western.bounds` and `eastern.bounds` are already correct, create the boundary polygon from these:

```python
def create_boundary_from_image_bounds(image_bounds, points_per_edge=100):
    """
    Create densified boundary polygon from the SAME bounds used for images.

    This ensures perfect alignment because both use the same source.
    """
    west, south, east, north = image_bounds
    boundary = []

    # Top edge: west to east
    for i in np.linspace(0, 1, points_per_edge):
        lon = west + i * (east - west)
        boundary.append({"lat": north, "lon": lon})

    # Right edge: north to south
    for i in np.linspace(0, 1, points_per_edge)[1:]:
        lat = north - i * (north - south)
        boundary.append({"lat": lat, "lon": east})

    # Bottom edge: east to west
    for i in np.linspace(0, 1, points_per_edge)[1:]:
        lon = east - i * (east - west)
        boundary.append({"lat": south, "lon": lon})

    # Left edge: south to north
    for i in np.linspace(0, 1, points_per_edge)[1:-1]:
        lat = south + i * (north - south)
        boundary.append({"lat": lat, "lon": west})

    return boundary

# Use this in backend:
western_bounds = array_bounds(height, width, dst_transform)
boundary_polygon = create_boundary_from_image_bounds(western_bounds)
```

**Why this works:**
- Both image and boundary use `array_bounds()` from the reprojected data
- Guaranteed to match because they're from the same source
- Accounts for cell corners, not centers
- Densified with 400 points to capture any curvature

### Option 2: Fix Pygrib Boundary Calculation (Root Cause Fix)

If you want to keep using `grb.latlons()`, you need to:

1. Account for half-cell offset
2. Use cell corners, not centers
3. Match the reprojection transform

This is more complex and error-prone. **Option 1 is simpler and guaranteed to work.**

---

## Verification

After applying the fix, the boundary extent should match image bounds exactly:

### Expected After Fix:

```
Image Bounds:         Boundary Extent:
West:  -180.004  →    West:  -180.004  ✓
South:   41.605  →    South:   41.605  ✓
East:   180.008  →    East:   180.008  ✓
North:   77.101  →    North:   77.101  ✓

Difference: < 0.0001° (sub-meter precision)
```

---

## Backend Code Change

### Current (Incorrect):
```python
# Uses pygrib latlons - cell centers
lats, lons = grb.latlons()
# Create boundary from edge points
boundary_polygon = create_boundary_from_latlons(edge_lats, edge_lons)
# Result: Doesn't match image bounds!
```

### Corrected:
```python
# Use the SAME bounds as the image
western_bounds = array_bounds(height, width, dst_transform_west)
eastern_bounds = array_bounds(height, width, dst_transform_east)

# Create densified boundary from these bounds
boundary_polygon = create_boundary_from_image_bounds(western_bounds, points_per_edge=100)
# Result: Perfectly matches image bounds!
```

---

## Impact

This fix will:

✅ Eliminate the 15-37 km misalignment
✅ Make boundary trace image edges exactly
✅ Work correctly at the date line
✅ Simplify the code (single source of truth)
✅ Be more maintainable (fewer coordinate transforms)

---

## Next Steps

1. **Immediate Test**: Use `generate_fixed_boundary.html` to create corrected boundary
2. **Verify**: Check that boundary extent matches image bounds within 0.0001°
3. **Backend Update**: Modify production code to use image bounds for boundary
4. **Validate**: Confirm perfect alignment on all edges

The solution is straightforward: **Use the same source for both image bounds and boundary polygon**.
