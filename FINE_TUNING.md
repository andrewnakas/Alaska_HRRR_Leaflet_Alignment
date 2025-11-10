# HRRR Alaska Fine-Tuning System

## Overview

This system allows you to fine-tune the alignment, positioning, scale, and bounds of the HRRR Alaska data overlay on the Leaflet map.

## Quick Start

1. **Edit** `alignment_config.json` with your desired adjustments
2. **Run** `python3 fine_tune_alignment.py`
3. **Refresh** your browser to see the changes
4. **Repeat** until perfect!

## Configuration File: `alignment_config.json`

### Available Adjustments

```json
{
  "adjustments": {
    "lon_offset": 0.0,        // Shift entire image east (+) or west (-)
    "lat_offset": 0.0,        // Shift entire image north (+) or south (-)
    "lon_scale": 1.0,         // Stretch horizontally (>1 = wider, <1 = narrower)
    "lat_scale": 1.0,         // Stretch vertically (>1 = taller, <1 = shorter)
    "west_adjustment": 0.0,   // Adjust western edge specifically
    "east_adjustment": 0.0,   // Adjust eastern edge specifically
    "north_adjustment": 0.0,  // Adjust northern edge specifically
    "south_adjustment": 0.0,  // Adjust southern edge specifically
    "rotation_degrees": 0.0   // Rotate clockwise (not yet implemented)
  }
}
```

### Parameter Details

#### Global Positioning

- **`lon_offset`**: Move the entire image east (positive) or west (negative) in degrees
  - Example: `"lon_offset": 1.0` shifts everything 1° east
  - Use this if the entire image is misaligned horizontally

- **`lat_offset`**: Move the entire image north (positive) or south (negative) in degrees
  - Example: `"lat_offset": -0.5` shifts everything 0.5° south
  - Use this if the entire image is misaligned vertically

#### Scaling

- **`lon_scale`**: Stretch or compress the image horizontally
  - `1.0` = original width
  - `1.1` = 10% wider
  - `0.9` = 10% narrower
  - Use this if the image is too wide or too narrow

- **`lat_scale`**: Stretch or compress the image vertically
  - `1.0` = original height
  - `1.1` = 10% taller
  - `0.9` = 10% shorter
  - Use this if the image is too tall or too short

#### Edge Adjustments

- **`west_adjustment`**: Adjust only the western (left) edge
  - Positive = move east (make image narrower from left)
  - Negative = move west (make image wider from left)

- **`east_adjustment`**: Adjust only the eastern (right) edge
  - Positive = move east (make image wider from right)
  - Negative = move west (make image narrower from right)

- **`north_adjustment`**: Adjust only the northern (top) edge
  - Positive = move north (make image taller from top)
  - Negative = move south (make image shorter from top)

- **`south_adjustment`**: Adjust only the southern (bottom) edge
  - Positive = move north (make image shorter from bottom)
  - Negative = move south (make image taller from bottom)

## Example Workflows

### Example 1: Image is shifted too far east

```json
{
  "adjustments": {
    "lon_offset": -2.0
  }
}
```

Run `python3 fine_tune_alignment.py` and the image will shift 2° west.

### Example 2: Image is too wide

```json
{
  "adjustments": {
    "lon_scale": 0.95
  }
}
```

This makes the image 5% narrower while keeping it centered.

### Example 3: Western edge needs adjustment

```json
{
  "adjustments": {
    "west_adjustment": -1.5
  }
}
```

Moves only the western edge 1.5° west, leaving other edges unchanged.

### Example 4: Complex adjustment

```json
{
  "adjustments": {
    "lon_offset": -0.5,
    "lat_offset": 0.2,
    "lon_scale": 0.98,
    "west_adjustment": -1.0
  }
}
```

This:
- Shifts everything 0.5° west
- Shifts everything 0.2° north
- Makes image 2% narrower
- Extends western edge 1° further west

## Output & Analysis

When you run `fine_tune_alignment.py`, you'll see:

### 1. Base Bounds
```
Base bounds (before adjustments):
  West:  -203.5632°
  South: 41.6129°
  East:  -115.7757°
  North: 77.0929°
```

### 2. Adjusted Bounds
```
Adjusted bounds (after fine-tuning):
  West:  -203.5632° (Δ +0.0000°)
  South: 41.6129° (Δ +0.0000°)
  East:  -115.7757° (Δ +0.0000°)
  North: 77.0929° (Δ +0.0000°)
```

Shows what changed (Δ = delta/difference from base).

### 3. Alignment Analysis
```
Alignment Analysis:
  Boundary vs Image bounds:
    West:  0.0000° difference
    South: 0.0000° difference
    East:  0.0000° difference
    North: 0.0002° difference
    Total: 0.0002° difference

  ✓ EXCELLENT alignment!
```

This compares the image bounds to the actual GRIB2 grid boundary:
- **< 0.1°**: Excellent alignment
- **0.1° - 0.5°**: Good alignment
- **0.5° - 2.0°**: Fair alignment - consider fine-tuning
- **> 2.0°**: Poor alignment - needs adjustment

### 4. Suggested Adjustments

If alignment is not excellent, the script will suggest specific adjustments:

```
Suggested adjustments for alignment_config.json:
  "west_adjustment": -0.5234
  "north_adjustment": 0.1234
```

Copy these into `alignment_config.json` and run again.

## Workflow for Perfect Alignment

1. **Initial Run** (no adjustments):
   ```bash
   python3 fine_tune_alignment.py
   ```

2. **Check alignment analysis** in terminal output

3. **If not perfect**, copy suggested adjustments to `alignment_config.json`

4. **Run again**:
   ```bash
   python3 fine_tune_alignment.py
   ```

5. **Commit and push**:
   ```bash
   git add alignment_config.json images/hrrr_continuous.png test-data.json
   git commit -m "Fine-tune alignment"
   git push
   ```

6. **Refresh browser** after GitHub Pages deploys (~1-2 minutes)

7. **Visually verify** alignment in browser

8. **Repeat** steps 3-7 if needed

## Tips

- **Small adjustments**: Start with small values (0.1° - 0.5°) and iterate
- **One parameter at a time**: Adjust one thing at a time to see its effect
- **Visual verification**: Always check in the browser with the OpenStreetMap base layer
- **Zoom in**: Use the map zoom to inspect alignment at boundaries
- **Red boundary**: The red polygon shows the actual GRIB2 grid edges - your image should match this exactly

## Current Alignment Status

As of the latest run:

- **Total alignment error**: 0.0002°
- **Status**: ✓ EXCELLENT alignment!
- **No further adjustments needed**

The HRRR Alaska data is currently very well aligned with the actual grid boundaries.

## Files Modified

When you run the fine-tuning script, it updates:

1. **`images/hrrr_continuous.png`** - The reprojected radar image
2. **`test-data.json`** - Metadata with adjusted bounds
3. **Terminal output** - Analysis and suggestions

## Technical Details

### Projection Used

- **Source**: Polar Stereographic (HRRR Alaska native)
  ```
  +proj=stere +lat_0=90 +lon_0=225 +lat_ts=60 +a=6371229 +b=6371229 +units=m +no_defs
  ```
- **Destination**: WGS84 (EPSG:4326) for Leaflet
- **Resampling**: Bilinear interpolation
- **Grid**: 919 × 1299 (native) → 1182 × 2926 (reprojected)

### How Adjustments Work

1. **Base bounds** are calculated from GRIB2 lat/lon arrays
2. **Edge adjustments** are applied to individual bounds
3. **Scaling** is applied from the center point
4. **Offsets** shift the entire bounds
5. **Rasterio reprojection** is run with adjusted bounds
6. **Alignment** is verified against actual grid boundary

### Coordinate System

- **Longitude**: Continuous from Russia to Alaska (-203° to -115°)
  - No wrapping around 180° dateline
  - Eastern Aleutians converted to negative values (e.g., 170° → -190°)
- **Latitude**: Standard northern hemisphere (41° to 77°N)

## Troubleshooting

### "Image is upside down"
This was fixed by using `origin='lower'` in matplotlib. If you see this again, check `reproject_continuous.py` line 220.

### "Image spans the world"
This should not happen with the continuous longitude approach. If you see this, verify that positive longitudes are being converted to negative (line 106 in fine_tune_alignment.py).

### "Alignment looks good but numbers say otherwise"
Visual alignment in browser is what matters most. The numerical alignment is compared to the grid cell centers, but visual alignment with coastlines and geographic features is the ultimate test.

### "Changes don't appear"
1. Make sure you committed and pushed
2. Wait for GitHub Pages to deploy (1-2 minutes)
3. Hard refresh browser (Ctrl+Shift+R or Cmd+Shift+R)
4. Clear browser cache if needed
