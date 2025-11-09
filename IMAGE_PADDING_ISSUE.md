# Image Padding Issue - The Real Problem?

## User's Insight

The user identified that **the border of the HRRR data/image does not align with the edge of the actual HRRR image bounds**.

This means: The images might have **transparent padding** or the actual data doesn't fill the entire image!

---

## The Problem

### Scenario 1: Transparent Padding
```
Stated Image Bounds: [-180.004, 41.605, 180.008, 77.101]

Actual Image:
+----------------------------------+
|  (transparent padding)           |
|    +----------------------+      |
|    |  ACTUAL HRRR DATA    |      |
|    |  (visible pixels)    |      |
|    +----------------------+      |
|  (transparent padding)           |
+----------------------------------+

The actual data might be at:
[-179.5, 42.0, 179.5, 76.5]  ← Different!
```

### Scenario 2: Reprojection Artifacts
When reprojecting from polar stereographic to WGS84, rasterio might:
- Create an image with the stated bounds
- But the actual data doesn't fill all the way to the edges
- Leaving transparent regions around the edges

---

## The Solution: Pixel Analysis

I've created **`analyze_image_bounds.html`** which:

### 1. Downloads the Actual Images
Loads the real HRRR WebP images from Firebase Storage

### 2. Analyzes Every Pixel
- Scans the entire image pixel by pixel
- Identifies non-transparent pixels (alpha > 0)
- Finds the min/max X and Y coordinates of actual data

### 3. Calculates Real Bounds
Converts the pixel bounding box to geographic coordinates:
```javascript
actualWest = statedWest + (minPixelX / imageWidth) * (statedEast - statedWest)
actualEast = statedWest + (maxPixelX / imageWidth) * (statedEast - statedWest)
// Similar for North/South
```

### 4. Visualizes the Difference
- Shows the image with a red box around actual data
- Displays stated bounds vs actual data bounds
- Calculates the degree difference

### 5. Generates Corrected Boundary
Creates a new boundary polygon from the **actual data bounds**, not the stated image bounds.

---

## How to Use

### On GitHub Pages:

1. Visit: `https://andrewnakas.github.io/Alaska_HRRR_Leaflet_Alignment/analyze_image_bounds.html`

2. The tool will automatically:
   - Load your test-data.json
   - Download and analyze both HRRR images
   - Show you the results

3. Look for:
   - **Data coverage percentage**: Should be ~100% if no padding
   - **Difference in degrees**: Should be ~0° if bounds match data
   - **Visual red box**: Should cover entire image if no padding

4. If there IS padding/mismatch:
   - Click "Download Corrected Boundary"
   - Save as `test-data-actual-bounds.json`
   - Rename to `test-data.json`
   - Refresh the map
   - **Alignment should now be perfect!**

---

## Expected Findings

### Scenario A: No Padding (Coverage = 100%)
```
Image size: 1299 × 919 pixels
Data coverage: 1299 × 919 pixels (100%)

Stated bounds match actual data bounds
→ Previous fix was correct
→ Problem must be elsewhere
```

### Scenario B: Padding Exists (Coverage < 100%)
```
Image size: 1299 × 919 pixels
Data coverage: 1250 × 880 pixels (96.2% × 95.8%)

Actual data bounds:
  West: -179.5° (stated: -180.004°) → Δ 0.504°
  East:  179.3° (stated:  180.008°) → Δ 0.708°

→ THIS is the real problem!
→ Must use actual data bounds, not stated bounds
```

### Scenario C: Irregular Data Region
```
Data doesn't form a perfect rectangle
→ Boundary needs to follow the actual data shape
→ May need more complex polygon tracing
```

---

## Why This Matters

If there's even a **0.5° difference** between stated and actual bounds:
- At Alaska's latitude (~65°), that's **~20-50 km** of misalignment!
- This would explain why the boundary doesn't match the visible image

---

## Technical Details

### How Rasterio Might Create Padding

When reprojecting with `rasterio.warp.reproject()`:

```python
# Calculate destination transform
dst_transform, width, height = calculate_default_transform(
    src_crs, dst_crs, src_width, src_height, *src_bounds
)

# This might create a slightly larger destination
# to ensure all data is captured during reprojection

# Result: Image bounds include some extra space
# that doesn't have actual data
```

### The Fix

Instead of using `dst_transform` bounds for the boundary, we should:

1. Reproject the data
2. Find the actual extent of non-null data
3. Use THAT for the boundary polygon

Or, as this tool does:
1. Analyze the final PNG/WebP images
2. Find actual visible data extent
3. Create boundary from that

---

## Next Steps

1. **Run the analysis tool** on GitHub Pages
2. **Check the results**:
   - Is data coverage 100%?
   - Are stated vs actual bounds different?
3. **If padding exists**:
   - Download the corrected boundary
   - Test alignment
4. **If no padding**:
   - The issue is something else
   - May need to examine the projection parameters

---

## Files

- `analyze_image_bounds.html` - Pixel analysis tool (browser-based, no dependencies)
- `IMAGE_PADDING_ISSUE.md` - This document

---

This tool will definitively answer: **Do the stated image bounds match the actual visible data?**
