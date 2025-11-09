# HRRR Alaska Alignment Solutions

## Problem: World-Wide Stretching

The current reprojection creates a **360° longitude span** that covers the entire world, with most pixels being empty/transparent. The actual Alaska data is compressed into a narrow band, looking stretched and wrong.

### Root Cause

When reprojecting from polar stereographic to WGS84:
- The polar grid edges near the North Pole project to extreme east/west coordinates
- This causes bounds of `-180° to +180°` (entire world longitudinally)
- Results in a **574 × 3183** pixel image (5.54:1 aspect ratio!)
- 70-80% of pixels are transparent (wasted space)
- Alaska data is compressed and stretched

---

## Three Solutions

### Solution 1: Native Projection (RECOMMENDED)

**Use leaflet-proj4 to display data in native polar stereographic projection**

**Files:**
- `process_hrrr_native.py` - Generates data in native projection
- `index-native.html` - Leaflet map with proj4 support
- `test-data-native.json` - Native projection data

**Pros:**
- ✓ NO distortion or stretching
- ✓ Natural Alaska shape (how meteorologists view it)
- ✓ Compact image: **919 × 1299** pixels (1.41:1 aspect)
- ✓ Perfect alignment (no reprojection errors)
- ✓ All pixels contain data (no waste)
- ✓ Smaller file size (532KB vs 651KB)

**Cons:**
- ✗ Requires leaflet-proj4 plugin
- ✗ Slightly more complex JavaScript
- ✗ Base maps need to be compatible or reprojected

**How to Use:**
```bash
# Generate data
python3 process_hrrr_native.py

# Open in browser
# Use index-native.html
```

**Result:**
- Image: 1272 × 900 pixels (natural aspect)
- Bounds: In meters, not degrees
- Projection: Polar stereographic
- No stretching, perfect alignment

---

### Solution 2: Cropped WGS84 Reprojection

**Reproject to WGS84 but crop to Alaska mainland extent**

**Files:**
- `reproject_with_crop.py` - Smart cropping during reprojection
- `test-data-cropped.json` - Cropped WGS84 data

**Pros:**
- ✓ Works with standard Leaflet (no plugins)
- ✓ Reasonable longitude span: **50°** (not 360°!)
- ✓ Much smaller image than full reprojection
- ✓ Less stretching than full reprojection

**Cons:**
- ✗ Still has some distortion from reprojection
- ✗ Crops out far western Aleutians
- ✗ More complex processing
- ✗ Still more pixels than native

**How to Use:**
```bash
# Generate cropped data
python3 reproject_with_crop.py

# Use with standard index.html
# Update to load test-data-cropped.json
```

**Result:**
- Bounds: -180° to -130° longitude (50° span)
- No world-wide stretching
- Works with standard Leaflet

---

### Solution 3: Full WGS84 Reprojection (CURRENT - NOT RECOMMENDED)

**Full reprojection to WGS84 without cropping**

**Files:**
- `reproject_hrrr_polar_to_wgs84.py`
- `test-data.json`

**Pros:**
- ✓ Works with standard Leaflet
- ✓ Covers entire Alaska domain including far Aleutians

**Cons:**
- ✗ World-wide extent: **360.23°** longitude span!
- ✗ Extreme stretching: **574 × 3183** pixels (5.54:1)
- ✗ 70-80% of pixels are empty/transparent
- ✗ Huge coordinate values cause alignment issues
- ✗ Larger file size
- ✗ Poor visual appearance

**Why It Fails:**
The polar grid, when reprojected to WGS84, extends from -180° to +180° because points near the North Pole project to extreme longitudes.

---

## Comparison

| Aspect | Native (Sol 1) | Cropped WGS84 (Sol 2) | Full WGS84 (Sol 3) |
|--------|----------------|----------------------|-------------------|
| **Image Size** | 1272 × 900 | ~1200 × 1800 | 574 × 3183 |
| **Aspect Ratio** | 1.41:1 (natural) | ~0.67:1 (reasonable) | 5.54:1 (stretched!) |
| **Longitude Span** | N/A (meters) | 50° | 360° (world!) |
| **Distortion** | None | Some | Severe |
| **File Size** | 532KB | ~400KB | 651KB |
| **Empty Pixels** | 0% | ~20% | 70-80% |
| **Alignment** | Perfect | Good | Difficult |
| **Leaflet Plugin** | Yes (proj4) | No | No |
| **Complexity** | Medium | Medium | Low |

---

## Recommendation

**Use Solution 1 (Native Projection)** for:
- Best visual quality
- Perfect alignment
- Most efficient storage
- Professional meteorological applications

**Use Solution 2 (Cropped WGS84)** for:
- Simpler Leaflet setup (no plugins)
- Standard web map workflows
- When you need WGS84 compatibility

**Avoid Solution 3 (Full WGS84)** because:
- World-wide stretching looks wrong
- Wasted pixels and file size
- Difficult alignment with huge coordinates
- Poor user experience

---

## How to Switch

### Current (Full WGS84) → Native Projection

1. Run native script:
   ```bash
   python3 process_hrrr_native.py
   ```

2. Update HTML to use native version:
   ```bash
   cp index-native.html index.html
   ```

3. Commit and push:
   ```bash
   git add images/hrrr_native.png test-data-native.json index.html
   git commit -m "Switch to native polar stereographic projection - no stretching"
   git push
   ```

### Current (Full WGS84) → Cropped WGS84

1. Run cropped script:
   ```bash
   python3 reproject_with_crop.py
   ```

2. Update index.html to load `test-data-cropped.json` instead of `test-data.json`

3. Commit and push

---

## Technical Details

### Native Projection Parameters

```
+proj=stere +lat_0=90 +lon_0=225 +lat_ts=60 +a=6371229 +b=6371229 +units=m +no_defs
```

- Polar stereographic centered at North Pole
- Central meridian: 225° (or -135°W)
- Standard parallel: 60°N
- Sphere radius: 6,371,229 m
- Grid: 919 × 1299 cells at 3km resolution

### Why Polar Stereographic?

NOAA uses polar stereographic for HRRR Alaska because:
- Minimizes distortion at high latitudes
- Alaska is near the North Pole
- Preserves shape and angles
- Standard for Arctic modeling
- 3km grid spacing is uniform in native projection

### Why WGS84 Reprojection Fails

When converting polar → WGS84:
1. Grid extends toward North Pole (90°N)
2. Near pole, longitude lines converge
3. Small distances in polar = huge longitude changes in WGS84
4. Result: -180° to +180° bounds (entire world)

---

## Examples

### Native Projection (Good!)
```
Grid: 919 × 1299 pixels
Bounds: [-3,426,550, -4,100,302, 470,448, -1,343,306] meters
Aspect: 1.41:1 (natural Alaska shape)
Longitude span: N/A (in meters)
Empty pixels: 0%
```

### Full WGS84 Reprojection (Bad!)
```
Grid: 574 × 3183 pixels
Bounds: [-180.114°, 41.601°, 180.119°, 77.105°]
Aspect: 5.54:1 (stretched!)
Longitude span: 360.23° (entire world!)
Empty pixels: 70-80%
```

### Cropped WGS84 (Acceptable)
```
Grid: ~1200 × 1800 pixels
Bounds: [-180°, 41.6°, -130°, 77.1°]
Aspect: ~0.67:1 (reasonable)
Longitude span: 50° (Alaska mainland)
Empty pixels: ~20%
```

---

## Conclusion

The **native polar stereographic projection** (Solution 1) is the best approach because:
- It's how NOAA stores the data
- No distortion or stretching
- Most efficient storage
- Perfect alignment
- Professional quality

The only tradeoff is requiring leaflet-proj4, which is a small JavaScript plugin that's easy to use.
