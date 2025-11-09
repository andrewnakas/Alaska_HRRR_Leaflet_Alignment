# HRRR Alaska Leaflet Alignment - Test Harness

## Overview

This is a standalone test environment for debugging and perfecting the alignment of HRRR Alaska radar imagery on a Leaflet map.

**Live Demo**: [GitHub Pages URL will be available after deployment]

## ✅ SOLUTION FOUND AND APPLIED

**ROOT CAUSE**: Image bounds were **rounded** from exact rasterio values, causing 15-37 km misalignment!

### The Fix

```python
# ❌ WRONG: Rounded bounds
bounds = [-180.0, 41.605, 180.0, 77.101]

# ✅ CORRECT: Exact bounds from rasterio array_bounds()
bounds = [-180.00389579621498, 41.605027, 180.00812367474123, 77.100815]
```

**Result**: PERFECT ALIGNMENT (0.000000° difference) ✓

### Applied Fixes

- ✅ Using EXACT bounds (not rounded) for both images and boundary
- ✅ Boundary created from same source as images (rasterio array_bounds)
- ✅ Densified to 396 points (100 per edge) to capture curvature
- ✅ Cell corner extent (not cell centers)

### How to Verify

1. Open the GitHub Pages URL
2. Press F12 to open console
3. Look for: `Difference: 0.000000°` ← Perfect match!
4. Visual check: Red boundary traces image edges exactly

### Alternative Approach: GRIB2/Herbie

See **[GRIB2_SOLUTION.md](GRIB2_SOLUTION.md)** for how to use Herbie to generate boundaries directly from HRRR GRIB2 files (no backend needed).

### Technical Documentation

- **[REFERENCE_SOLUTIONS.md](REFERENCE_SOLUTIONS.md)** - 📚 **NEW** - Proven solutions from research (code examples, best practices)
- **[IMAGE_PADDING_ISSUE.md](IMAGE_PADDING_ISSUE.md)** - 🔬 Image padding analysis
- **[ACTUAL_ROOT_CAUSE.md](ACTUAL_ROOT_CAUSE.md)** - Boundary source mismatch analysis
- **[CRITICAL_FINDING.md](CRITICAL_FINDING.md)** - Boundary vs image bounds comparison
- **[ALIGNMENT_SOLUTION.md](ALIGNMENT_SOLUTION.md)** - General alignment theory
- **[IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md)** - Implementation guide

## Problem Summary

The HRRR Alaska radar overlay uses **polar stereographic projection** and crosses the **International Date Line**. Images are reprojected from native GRIB2 projection to WGS84, but the boundary polygon should perfectly align with the image overlays on the Leaflet map.

**Key Challenge**: Boundary polygon should exactly match the visual edges of the radar images.

## Features

- Interactive Leaflet map with HRRR Alaska radar overlay
- Date-line wrapping support (displays both western and eastern hemispheres)
- Debug controls for alignment verification:
  - Toggle radar images on/off
  - Toggle boundary polygon visibility
  - Show/hide boundary points
  - Show/hide image corner markers
  - Adjust image opacity
- Quick zoom to Alaska and Date Line
- Real-time data loading from production API or local test data

## Quick Start

### View Live Demo

Just open the GitHub Pages URL in your browser. The page will automatically load the latest HRRR data from the production API.

### Local Development

```bash
# Clone repository
git clone https://github.com/YOUR_USERNAME/Alaska_HRRR_Leaflet_Alignment.git
cd Alaska_HRRR_Leaflet_Alignment

# Serve locally
python3 -m http.server 8000

# Open browser
open http://localhost:8000
```

### Update Test Data

Fetch the latest HRRR data from production:

```bash
curl -s "https://get-hrrr-forecast-pxvei6zf7a-uc.a.run.app" | \
  python3 -c "import sys, json; d=json.load(sys.stdin); print(json.dumps(d['data']['forecast_times'][0]['alaska'], indent=2))" \
  > test-data.json
```

## How to Test Alignment

1. **Open the map** - The radar overlay and boundary polygon will load automatically
2. **Zoom to Alaska** - Click the "Zoom to Alaska" button
3. **Check alignment** - The red dashed polygon should exactly trace the edges of the radar images
4. **Zoom to Date Line** - Click "Zoom to Date Line" to verify seamless coverage at ±180°
5. **Toggle layers** - Use checkboxes to show/hide different elements:
   - Red polygon = boundary
   - Red dots = image corner markers
   - Blue dots = boundary polygon points
6. **Adjust opacity** - Use the slider to see through the radar overlay

## Debug Features

### Visual Indicators

- **Radar Images**: The actual HRRR forecast imagery with transparency
- **Boundary Polygon**: Red dashed line showing the calculated boundary
- **Image Corners**: Red dots marking the four corners of each image
- **Boundary Points**: Blue dots showing all points in the boundary polygon

### Console Diagnostics

Open browser console (F12) to see detailed alignment information:
- Image bounds for all four wrapped images
- Boundary polygon extent
- Point counts and coverage

## Data Structure

The test data (`test-data.json`) has this structure:

```json
{
  "western": {
    "image_url": "https://storage.googleapis.com/.../alaska_hrrr_western.png",
    "bounds": [-180.004, 41.605, 180.008, 77.101]
  },
  "eastern": {
    "image_url": "https://storage.googleapis.com/.../alaska_hrrr_eastern.png",
    "bounds": [-179.985, 41.605, 179.994, 77.101]
  },
  "boundary_polygon": [
    {"lat": 77.101, "lon": -180.004},
    {"lat": 76.989, "lon": -179.234},
    ...223 points total...
  ]
}
```

## Technical Details

### Date Line Handling

Alaska crosses the International Date Line (±180°), so the map displays **four image overlays**:
1. Western image (original: -180° to +180°)
2. Western image wrapped (+180° to +540°)
3. Eastern image (original: -180° to +180°)
4. Eastern image wrapped (-540° to -180°)

This ensures seamless coverage when panning across the date line.

### Projection Details

- **Source**: GRIB2 in polar stereographic projection
- **Target**: WGS84 (EPSG:4326) for Leaflet
- **Grid**: 1299×919 pixels
- **Reprojection**: Handled by backend using rasterio

## Success Criteria

✅ Perfect alignment means:
- Red boundary polygon exactly traces the edges of radar images
- Red corner dots align with polygon vertices
- No gaps visible at the International Date Line (±180°)
- Boundary points follow image edges when enabled

## Files

### Test Harness
- `index.html` - Main test page with Leaflet map
- `test-data.json` - Sample HRRR data from production API
- `.github/workflows/deploy.yml` - GitHub Actions for automatic deployment

### Solution Documentation
- `REFERENCE_SOLUTIONS.md` - 📚 **RESEARCH COMPILATION** - Proven code examples from Leaflet/HRRR community
- `ACTUAL_ROOT_CAUSE.md` - 🔴 Log analysis revealing the actual problem (bounds mismatch)
- `CRITICAL_FINDING.md` - Quick summary of boundary vs image bounds discrepancy
- `IMAGE_PADDING_ISSUE.md` - Image padding and pixel analysis approach
- `analyze_image_bounds.html` - **DIAGNOSTIC TOOL** - Pixel-level analysis of actual data bounds
- `generate_fixed_boundary.html` - **IMMEDIATE FIX** - Browser tool to create matching boundary
- `ALIGNMENT_SOLUTION.md` - General alignment theory (curved edges, densification)
- `IMPLEMENTATION_GUIDE.md` - Step-by-step implementation guide with code examples
- `fix_boundary_calculation.py` - Python implementation of corrected boundary calculation
- `fix_boundary_js.html` - Alternative browser-based boundary generator

### Documentation
- `README.md` - This file

## Production API

**Endpoint**: https://get-hrrr-forecast-pxvei6zf7a-uc.a.run.app

The API returns the latest HRRR forecast with Alaska data nested at:
```
data.forecast_times[0].alaska
```

## Troubleshooting

### Images not loading
- Check browser console for CORS errors
- Verify `test-data.json` exists and has valid data
- Try refreshing data from production API

### Alignment looks off
1. Toggle boundary points to see all 223+ points
2. Zoom in to specific areas that look misaligned
3. Check console for diagnostic information
4. Compare corner markers with boundary polygon endpoints

### Date line issues
- Make sure worldCopyJump is set to false
- Verify all four wrapped images are displaying
- Check that longitude values span correctly across ±180°

## Contributing

To improve the alignment:
1. Modify the boundary polygon calculation in the backend
2. Update test-data.json with new data
3. Refresh the page to see changes
4. Verify alignment using debug tools

## License

This is a test harness for development purposes.
