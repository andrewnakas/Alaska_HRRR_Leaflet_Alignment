# HRRR Alaska Leaflet Alignment

Real-time HRRR Alaska composite reflectivity (REFC) data displayed on a Leaflet map with proper alignment and dateline handling.

## 🌐 Live Demo

- **Main Map**: [https://andrewnakas.github.io/Alaska_HRRR_Leaflet_Alignment/](https://andrewnakas.github.io/Alaska_HRRR_Leaflet_Alignment/)
- **🎨 Alignment Tuner**: [https://andrewnakas.github.io/Alaska_HRRR_Leaflet_Alignment/alignment-ui.html](https://andrewnakas.github.io/Alaska_HRRR_Leaflet_Alignment/alignment-ui.html)

## 🎯 Features

- ✅ Real HRRR Alaska REFC data from NOAA GRIB2 files
- ✅ Proper polar stereographic to WGS84 reprojection
- ✅ Continuous longitude bounds (Russia → Alaska, no world-wrapping)
- ✅ Correct orientation and alignment
- ✅ **Interactive fine-tuning UI**
- ✅ 87.8° span (not 360°!)

## 🎨 Interactive Alignment Tuner

The **Alignment Tuner** is an interactive web UI for fine-tuning the positioning, scale, and bounds of the radar overlay.

### 🚀 Access it here:

**[https://andrewnakas.github.io/Alaska_HRRR_Leaflet_Alignment/alignment-ui.html](https://andrewnakas.github.io/Alaska_HRRR_Leaflet_Alignment/alignment-ui.html)**

### Features:
- 🎚️ Real-time visual preview with sliders
- 📊 Adjust position, scale, and individual edges
- 💾 Export configuration to JSON
- 🔄 Preset adjustments
- 📏 Live bounds calculation

### How to Use:
1. Open the Alignment Tuner link above
2. Adjust sliders to fine-tune positioning
3. Click "Apply Adjustments" to preview changes
4. Export config when satisfied
5. Run `python3 fine_tune_alignment.py` locally
6. Commit and push to deploy

See **[FINE_TUNING.md](FINE_TUNING.md)** for complete documentation.

## 📊 Current Status

- **Alignment Error**: 0.0002° (EXCELLENT!)
- **Longitude Span**: 87.8° (continuous from Russia to Alaska)
- **Grid Size**: 919 × 1299 (native) → 1182 × 2926 (reprojected)
- **Projection**: Polar Stereographic → WGS84
- **Orientation**: Correct (north at top)

## 🛠️ Technical Details

### Projection Parameters

**Source (HRRR Alaska Native):**
```
+proj=stere +lat_0=90 +lon_0=225 +lat_ts=60 +a=6371229 +b=6371229 +units=m +no_defs
```

**Destination:**
- WGS84 (EPSG:4326) for Leaflet compatibility

### Dateline Handling

HRRR Alaska crosses the International Date Line. Solution:
- Normalize all coordinates to western hemisphere
- Eastern Aleutians: 170°E → -190° (subtract 360°)
- Result: Continuous bounds from -203.56° to -115.78°
- No world-wrapping or 360° span issues

### Data Source

- **Model**: NOAA HRRR Alaska (hrrrak)
- **Variable**: REFC (Composite Reflectivity)
- **Resolution**: 3 km
- **Update Frequency**: Hourly
- **Source**: NOMADS / AWS Open Data

## 📁 Repository Structure

```
├── index.html                    # Main map viewer
├── alignment-ui.html             # 🎨 Interactive alignment tuner
├── test-data.json                # Current data and bounds
├── alignment_config.json         # Fine-tuning configuration
├── fine_tune_alignment.py        # Apply adjustments script
├── reproject_continuous.py       # Reprojection script
├── images/
│   └── hrrr_continuous.png       # Reprojected radar image
├── FINE_TUNING.md                # Complete tuning documentation
└── SOLUTIONS.md                  # Technical research & solutions
```

## 🚀 Local Development

### Generate New Data

```bash
# Reproject with current settings
python3 reproject_continuous.py

# Or fine-tune alignment
python3 fine_tune_alignment.py
```

### Test Locally

```bash
# Serve locally
python3 -m http.server 8000

# Open in browser
# Main map: http://localhost:8000/
# Alignment UI: http://localhost:8000/alignment-ui.html
```

### Deploy Changes

```bash
git add images/hrrr_continuous.png test-data.json
git commit -m "Update HRRR Alaska data"
git push
```

GitHub Pages will automatically deploy in 1-2 minutes.

## 📖 Documentation

- **[FINE_TUNING.md](FINE_TUNING.md)** - Complete guide to the fine-tuning system
- **[SOLUTIONS.md](SOLUTIONS.md)** - Technical research and solution approaches

## 🎓 How It Works

1. **Download**: Fetch latest HRRR Alaska GRIB2 from NOAA
2. **Extract**: Get REFC data and 2D lat/lon arrays
3. **Normalize**: Convert coordinates to continuous western hemisphere
4. **Reproject**: Transform from polar stereographic to WGS84
5. **Visualize**: Create PNG with matplotlib
6. **Display**: Show on Leaflet map with proper bounds

## 🔧 Requirements

- Python 3.8+
- herbie-data
- rasterio
- pyproj
- matplotlib
- numpy
- xarray
- cfgrib (requires eccodes)

## 🎯 Key Features of the Solution

### ✅ Continuous Bounds
- Russia → Alaska in one span: -203.56° to -115.78°
- No 360° world-wrapping issue
- Proper handling of dateline crossing

### ✅ Correct Orientation
- Uses `origin='lower'` in matplotlib
- North at top, south at bottom
- Matches geographic orientation

### ✅ Interactive Fine-Tuning
- Web-based UI for adjustments
- Real-time preview
- Export/import configurations
- No manual JSON editing needed

### ✅ Perfect Alignment
- Boundary polygon from actual GRIB2 grid edges
- 0.0002° total alignment error
- Visual and numerical verification

## 🆘 Troubleshooting

### Images not loading
- Check GitHub Pages deployment status
- Verify files are committed and pushed
- Hard refresh browser (Ctrl+Shift+R)

### Alignment looks off
1. Open the Alignment Tuner
2. Adjust sliders to fine-tune
3. Export configuration
4. Run `python3 fine_tune_alignment.py`
5. Commit and push

### Data is outdated
```bash
# Regenerate with latest HRRR data
python3 reproject_continuous.py
git add images/hrrr_continuous.png test-data.json
git commit -m "Update to latest HRRR data"
git push
```

## 📝 License

This project is for educational and research purposes. HRRR data is provided by NOAA.

## 🙏 Credits

- **NOAA**: HRRR Alaska model and GRIB2 data
- **Herbie**: Python library for HRRR data access
- **Leaflet**: Interactive mapping library
- **OpenStreetMap**: Base map tiles

---

**Need help?**
- Check [FINE_TUNING.md](FINE_TUNING.md) for detailed documentation
- Try the [Alignment Tuner](https://andrewnakas.github.io/Alaska_HRRR_Leaflet_Alignment/alignment-ui.html)
- Open an issue on GitHub
