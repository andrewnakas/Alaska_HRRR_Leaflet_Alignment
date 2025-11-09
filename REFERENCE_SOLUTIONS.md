# Reference Solutions: HRRR Alaska Leaflet Alignment

## Summary of Research Findings

Researched proven solutions for handling HRRR Alaska data in Leaflet with proper boundary alignment and dateline crossing.

---

## 1. Dateline Crossing Solutions

### Solution A: Leaflet.ShadowWrap Plugin ⭐ **RECOMMENDED**

**GitHub**: [germanjoey/Leaflet.ShadowWrap](https://github.com/germanjoey/Leaflet.ShadowWrap)

**What it does**:
- Automatically duplicates geometries that cross the dateline
- Creates "shadow" copies on both sides of the wrap line
- Handles polygons, polylines, and markers

**Code Example**:
```javascript
// Map setup with worldCopyJump
var map = L.map('map', {
    worldCopyJump: true,
    center: [64.0, -152.0],
    zoom: 4
});

// Include Leaflet.ShadowWrap plugin (after leaflet.js)
// Polygons automatically shadow across dateline

// Add boundary polygon - it will auto-shadow
var boundary = L.polygon(alaskaCoords, {
    color: 'red',
    weight: 2
}).addTo(map);

// Control shadow distance
L.ShadowWrap.minimumWrapDistance = 50; // pixels from edge
```

**Why this works**:
- Automatically handles the wrapping logic
- No manual coordinate manipulation needed
- Works with existing polygon code

---

### Solution B: Manual Coordinate "Unfolding" (What We're Currently Using)

**Source**: [Stack Overflow - Wrapping polygons across antimeridian](https://stackoverflow.com/questions/40532496/wrapping-lines-polygons-across-the-antimeridian-in-leaflet-js)

**Our Implementation**:
```javascript
// Create 3 copies: original, +360, -360
const boundaryCoords = alaska.boundary_polygon.map(p => [p.lat, p.lon]);
const boundaryCoords360 = alaska.boundary_polygon.map(p => [p.lat, p.lon + 360]);
const boundaryCoordsNeg360 = alaska.boundary_polygon.map(p => [p.lat, p.lon - 360]);

boundaryLayer = L.layerGroup([
    L.polyline(boundaryCoords, {color: 'red', weight: 2}),
    L.polyline(boundaryCoords360, {color: 'red', weight: 2}),
    L.polyline(boundaryCoordsNeg360, {color: 'red', weight: 2})
]).addTo(map);
```

**Alternative Unfolding Function**:
```javascript
function unfoldCoordinates(latlngs) {
    if (latlngs.length < 2) return latlngs;

    let unfolded = [latlngs[0]];

    for (let i = 1; i < latlngs.length; i++) {
        let prev = unfolded[i - 1];
        let curr = [latlngs[i][0], latlngs[i][1]];

        // Check if crossing dateline (>180 degree jump)
        if (Math.abs(curr[1] - prev[1]) > 180) {
            if (curr[1] < prev[1]) {
                curr[1] += 360; // Crossing eastward
            } else {
                curr[1] -= 360; // Crossing westward
            }
        }
        unfolded.push(curr);
    }

    return unfolded;
}

// Use it
var polygon = L.polygon(unfoldCoordinates(coordinates)).addTo(map);
```

---

## 2. Polar Stereographic Projection Solutions

### Leaflet with Polar Stereographic (Proj4Leaflet)

**Source**: [Leaflet Issue #5617 - Polar Stereographic Fixes](https://github.com/Leaflet/Leaflet/issues/5617)

**For Alaska Polar Stereographic (EPSG:5936)**:
```javascript
// Define Alaska Polar Stereographic CRS
const proj = 'EPSG:5936';
const proj4 = '+proj=stere +lat_0=90 +lon_0=-150 +k=0.994 +x_0=2000000 +y_0=2000000 +datum=WGS84 +units=m';

let crs = new L.Proj.CRS(proj, proj4, {
    resolutions: [8192, 4096, 2048, 1024, 512, 256],
    origin: [-2000000, 2000000],
    bounds: L.bounds([-4000000, -4000000], [4000000, 4000000])
});

// Create map with custom CRS
var map = L.map('map', {
    crs: crs,
    center: [64.0, -152.0],
    zoom: 2
});
```

**For Arctic Polar Stereographic (EPSG:3995)**:
```javascript
const proj = 'EPSG:3995';
const proj4 = '+proj=stere +lat_0=90 +lat_ts=71 +lon_0=0 +k=1 +x_0=0 +y_0=0 +datum=WGS84 +units=m';

let crs = new L.Proj.CRS(proj, proj4, {
    resolutions: [8192, 4096, 2048, 1024, 512, 256],
    origin: [0, 0],
    bounds: L.bounds([-4194304, -4194304], [4194304, 4194304])
});
```

**NOTE**: For HRRR Alaska data already reprojected to WGS84, you DON'T need Proj4Leaflet. The projection issues are already handled in the backend reprojection.

---

## 3. Image Overlay Bounds Calculation

### Handling Reprojected Polar Data

**Source**: [GIS StackExchange - Polar stereographic imageOverlay](https://gis.stackexchange.com/questions/458932/leaflet-image-overlay-align-with-pixel-coordinates-on-map)

**Key Insight**: When images are reprojected from polar stereographic to WGS84, the bounds must account for:
1. Cell centers vs corners (half-cell offset)
2. Curved boundaries from non-linear reprojection
3. Dateline wrapping

**Correct Bounds Calculation**:
```python
# Backend: After reprojection with rasterio
from rasterio.transform import array_bounds
from rasterio.warp import reproject

# Reproject GRIB2 to WGS84
reproject(
    source=grib_data,
    destination=wgs84_array,
    src_transform=src_transform,
    src_crs=src_crs,
    dst_transform=dst_transform,
    dst_crs=CRS.from_epsg(4326),
    resampling=Resampling.bilinear
)

# Get exact bounds from reprojected array
# This accounts for the full cell extent
exact_bounds = array_bounds(height, width, dst_transform)

# Use THESE bounds for both:
# 1. Image overlay
# 2. Boundary polygon generation
```

**Frontend: Image Overlay**:
```javascript
// Use bounds directly from API
L.imageOverlay(
    imageUrl,
    [[south, west], [north, east]],  // [[SW], [NE]]
    {opacity: 0.7}
).addTo(map);

// For dateline crossing, add wrapped copies:
L.imageOverlay(imageUrl, [[south, west+360], [north, east+360]], {opacity: 0.7}).addTo(map);
L.imageOverlay(imageUrl, [[south, west-360], [north, east-360]], {opacity: 0.7}).addTo(map);
```

---

## 4. Boundary Polygon from Image Bounds

### Densified Boundary Generation

**Key Principle**: Use the SAME bounds for both image and boundary

**Code Example**:
```javascript
function createBoundaryFromImageBounds(bounds, pointsPerEdge = 100) {
    const [west, south, east, north] = bounds;
    const boundary = [];

    // Top edge: west to east
    for (let i = 0; i < pointsPerEdge; i++) {
        const t = i / (pointsPerEdge - 1);
        boundary.push({
            lat: north,
            lon: west + t * (east - west)
        });
    }

    // Right edge: north to south
    for (let i = 1; i < pointsPerEdge; i++) {
        const t = i / (pointsPerEdge - 1);
        boundary.push({
            lat: north - t * (north - south),
            lon: east
        });
    }

    // Bottom edge: east to west
    for (let i = 1; i < pointsPerEdge; i++) {
        const t = i / (pointsPerEdge - 1);
        boundary.push({
            lat: south,
            lon: east - t * (east - west)
        });
    }

    // Left edge: south to north
    for (let i = 1; i < pointsPerEdge - 1; i++) {
        const t = i / (pointsPerEdge - 1);
        boundary.push({
            lat: south + t * (north - south),
            lon: west
        });
    }

    return boundary;
}

// Use it
const westernBounds = [-180.004, 41.605, 180.008, 77.101];
const boundary = createBoundaryFromImageBounds(westernBounds, 100);
```

---

## 5. HRRR Data Specific Solutions

### HRRR Alaska Grid Specifications

**From NOAA Documentation**:
- **Native Projection**: Polar Stereographic
  - `lat_0`: 90 (North Pole)
  - `lon_0`: 225 (-135°W)
  - `lat_ts`: 60 (standard parallel)
  - Sphere radius: 6,371,229 m
- **Grid**: 1299 × 919 cells
- **Resolution**: 3 km
- **Domain**: Alaska including Aleutians (crosses dateline)

**Reprojection Parameters** (for backend):
```python
from pyproj import CRS

# Source CRS (HRRR Alaska native)
src_crs = CRS.from_proj4(
    '+proj=stere +lat_0=90 +lon_0=225 +lat_ts=60 '
    '+a=6371229 +b=6371229 +x_0=0 +y_0=0'
)

# Destination CRS (for Leaflet)
dst_crs = CRS.from_epsg(4326)  # WGS84
```

### HRRR Forecast Radar Loop Example

**Source**: [Albany HRRR Loop with Leaflet](https://www.atmos.albany.edu/facstaff/ktyle/hrrr/hrrrloop_leaflet.html)

This is a working example of HRRR radar overlay in Leaflet (though for CONUS, not Alaska). Key techniques:
- Uses tiled overlay for better performance
- Time slider for forecast animation
- Proper opacity handling

---

## 6. Debugging Techniques

### Visualizing Bounds Mismatch

**Our Implementation**:
```javascript
// Show image bounds (blue)
imageBoundsLayers.forEach((bounds, idx) => {
    [0, 360, -360].forEach(offset => {
        const rect = L.rectangle(
            [[south, west + offset], [north, east + offset]],
            {
                color: '#0000ff',
                weight: 3,
                fillOpacity: 0,
                dashArray: '10, 5'
            }
        ).addTo(map);
    });
});

// Console logging with color
console.log('%cImage Bounds:', 'color: blue; font-weight: bold', bounds);
console.log('%cBoundary Extent:', 'color: red; font-weight: bold', extent);
console.log('%cDifference:', 'color: orange; font-weight: bold', diff);
```

### Browser-Based Pixel Analysis

**Our analyze_image_bounds.html tool**:
```javascript
// Load image to canvas
const img = new Image();
img.crossOrigin = 'anonymous';
img.src = imageUrl;

img.onload = () => {
    ctx.drawImage(img, 0, 0);
    const imageData = ctx.getImageData(0, 0, width, height);

    // Find non-transparent pixels
    for (let y = 0; y < height; y++) {
        for (let x = 0; x < width; x++) {
            const idx = (y * width + x) * 4;
            const alpha = imageData.data[idx + 3];

            if (alpha > 0) {
                // Track min/max x, y for actual data
            }
        }
    }

    // Convert pixel bounds to geographic coordinates
    const actualBounds = pixelToGeographic(pixelBounds, statedBounds);
};
```

---

## 7. Best Practices Summary

### For Backend (Python/Rasterio):
1. Use `array_bounds()` after reprojection for exact bounds
2. Use the SAME bounds for both image export and boundary calculation
3. Account for cell centers → corners (half-cell extension)
4. Densify boundary polygon (100 points per edge minimum)

### For Frontend (Leaflet):
1. Use `worldCopyJump: false` to prevent auto-panning
2. Create wrapped copies (+360, -360) for dateline crossing
3. Use the exact bounds from API without modification
4. Add visual debugging overlays (bounds rectangles, etc.)
5. Log bounds comparison to console for verification

### For Alignment:
1. **Single source of truth**: boundary MUST use same bounds as images
2. **Densification**: Need many points to capture curved edges
3. **Wrapping**: Handle dateline by duplicating geometry, not worldCopyJump
4. **Validation**: Console logs + visual overlays to verify alignment

---

## 8. Tools & Libraries

### Essential:
- **Leaflet**: Core mapping library (v1.9.4+)
- **Proj4Leaflet**: For custom projections (if working in native polar stereo)
- **Rasterio**: Backend reprojection (Python)
- **PyGRIB**: Reading GRIB2 files (Python)

### Optional but Helpful:
- **Leaflet.ShadowWrap**: Auto-handle dateline crossing
- **Turf.js**: Advanced geometry operations
- **Canvas API**: Pixel-level image analysis

---

## 9. Common Pitfalls to Avoid

❌ **Don't**:
- Mix boundary calculation methods (pygrib latlons vs rasterio bounds)
- Use only 4 corner points for boundary (need densification)
- Forget to wrap geometry for dateline crossing
- Use `worldCopyJump: true` with manual wrapping (conflicts)
- Assume stated image bounds match actual visible data

✅ **Do**:
- Use same source (`array_bounds`) for images and boundary
- Densify with 100+ points per edge
- Create 3 wrapped copies (0, +360, -360 offsets)
- Verify alignment with visual debugging tools
- Check actual pixel data vs stated bounds

---

## References

1. **Leaflet Dateline Issues**: https://github.com/Leaflet/Leaflet/issues/82
2. **Polar Stereographic Fixes**: https://github.com/Leaflet/Leaflet/pull/5618
3. **Leaflet.ShadowWrap**: https://github.com/germanjoey/Leaflet.ShadowWrap
4. **HRRR Documentation**: https://rapidrefresh.noaa.gov/hrrr/
5. **Rasterio Reprojection**: https://rasterio.readthedocs.io/en/latest/topics/reproject.html

---

## Next Steps for Perfect Alignment

1. ✅ **Dateline wrapping** - DONE (using 3 wrapped copies)
2. ⏳ **Boundary source** - PENDING (backend still uses old pygrib method)
3. ⏳ **Pixel analysis** - USE analyze_image_bounds.html to verify actual data bounds
4. ⏳ **Backend fix** - Update production API to use `array_bounds` for boundary
5. ⏳ **Validation** - Test with visual overlays and console logging

The code examples in this document provide proven solutions used by others for similar problems!
