# WSI Clipper v1.0
**Whole Slide Image — Region of Interest Exporter**

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Version](https://img.shields.io/badge/version-1.0-blue.svg)]()
[![Platform](https://img.shields.io/badge/platform-Windows-lightgrey.svg)]()

A free standalone tool for scanning staff and pathology labs to crop a Whole Slide Image (WSI) and export the selected region as a pyramidal TIFF for pathologist review.

**Built by Scott Kilcoyne** — [LinkedIn](https://www.linkedin.com/in/scott-kilcoyne-pathology/)

> Free to use. No subscription. No cloud upload. Your data stays on your machine.

---

## Folder Structure
```
WSI Clipper\
├── server.py            ← Python backend
├── WSI_Clipper.spec     ← PyInstaller build spec
├── static\
│   ├── index.html       ← Frontend UI
│   └── logo.png         ← Brand logo (add when ready)
├── dist\
│   └── WSI_Clipper.exe  ← Packaged executable for distribution
├── wsi_uploads\         ← Temp folder for uploaded slides
└── wsi_exports\         ← Exported files saved here
```

## Download
**[→ Download WSI Clipper v1.0 (Windows)](https://github.com/skilcoyne13-go/wsi-clipper/releases/latest)**

No Python required. Unzip and double-click `WSI_Clipper.exe`.

---

## Quick Start
1. Double-click `WSI_Clipper.exe`
2. Drop your WSI file into the tool
3. Pan and zoom to find the best section
4. Draw a crop rectangle
5. Choose export format and click Export

---
```
cd Desktop\WSI Clipper
python server.py
```
Browser opens automatically at http://localhost:5050

---

## Dependencies
```
pip install flask flask-cors pillow tifffile numpy imagecodecs zarr openslide-python
```

### Optional (faster exports)
```
pip install pyvips
```
Requires libvips binary — download from https://github.com/libvips/libvips/releases

---

## Building the Executable for Distribution
```
pyinstaller --onefile --add-data "static;static" --name WSI_Clipper server.py
```
Output: `dist\WSI_Clipper.exe`

**What to zip and send to clients:**
- `dist\WSI_Clipper.exe`
- `static\` folder (must stay alongside the exe)

Client unzips and double-clicks. No Python needed.

> Note: Windows SmartScreen may warn on first run. Click "More info" → "Run anyway".

---

## How It Works
1. User drops a WSI file into the tool
2. Thumbnail of the full slide loads in the viewer
3. User zooms and pans to find the best section
4. User draws a crop rectangle over the target region
5. Choose export format and click Export
6. File saves to `wsi_exports\` and downloads automatically

---

## Export Formats
| Format | Use Case | Opens In |
|--------|----------|----------|
| Pyramidal TIFF | QuPath, OMERO, digital pathology viewers | QuPath, OMERO, ImageJ |
| Flat TIFF | Simple review, sending to pathologist | Windows Photo Viewer, any image app |
| JPEG | Smallest file, universal sharing | Everything |

> **Windows Photo Viewer note:** WPV cannot open large pyramidal TIFFs. Use **Flat TIFF** when the recipient uses WPV. Works at any crop size.

---

## Supported Formats
| Format | Extension | Driver |
|--------|-----------|--------|
| Aperio SVS | `.svs` | OpenSlide |
| Hamamatsu NDPI | `.ndpi` | OpenSlide |
| Leica SCN | `.scn` | OpenSlide |
| Pyramidal TIFF | `.tiff`, `.tif` | tifffile + zarr |
| KFBio-converted TIFF | `.tiff` | tifffile + zarr |
| PerkinElmer QPTIFF | `.qptiff` | tifffile |
| PNG / JPEG | `.png`, `.jpg` | PIL |

---

## Known Behaviour
- **KFBio TIFFs**: Converted KFBio files have no embedded pyramid. Tool reads full-res via zarr and builds pyramid on export. First zoom-in triggers a one-time PIL decode into RAM.
- **MPP**: KFBio TIFFs report MPP = 1000 (invalid). Tool ignores values outside 0.05–10.0 µm/px and defaults to 0.25. Override manually in the MPP field if known.
- **Export size**: No crop size limit. Large ROIs (500+ MP) take longer — JPEG is fastest for very large exports.
- **Multiple ROIs same slide**: PIL cache clears after each export and reloads on next tile fetch. Brief delay after export is normal.
--
## v1.0 — Beta

This is an initial release. If you encounter issues with a specific scanner format or file, please open a GitHub Issue with details of the error and file format.

---

## Branding
When ready to apply branding:
- In `static\index.html` replace `<div class="logo">🔬</div>` with `<img src="logo.png" style="height:32px;width:auto;">`
- Save your logo as `logo.png` in the `static\` folder
- Update the `v1.0` badge text with your company name
- Update `<title>WSI Clipper v1.0</title>` with your product name
- Rebuild exe with PyInstaller

---

## AI Development Continuation Prompt
*To continue development of this project in a new AI session, paste the following:*

---

> I am building a standalone WSI (Whole Slide Image) clipping tool called **WSI Clipper v1.0** for free distribution to pathology labs. The tool allows scanning staff to open a whole slide image, pan and zoom to find the best section, draw a crop rectangle, and export the selected region for pathologists.
>
> The tool is built with:
> - **Python backend** (`server.py`) using Flask, tifffile, zarr, numpy, PIL, and optionally OpenSlide/pyvips
> - **Frontend** (`static/index.html`) — single HTML file with three stacked canvases (base thumbnail, hi-res tile, selection overlay), pointer capture for reliable crop selection, and viewport tile fetching that requests hi-res regions from the server 120ms after pan/zoom stops
> - **Three export formats**: Pyramidal TIFF (QuPath/OMERO), Flat TIFF (Windows Photo Viewer compatible, single-page LZW), JPEG (universal)
>
> Key solved problems:
> - KFBio-converted TIFFs: single series, no pyramid, JPEG compressed (compression=7), requires imagecodecs. Metadata reads 84,041 × 44,058 px via series shape, ignores invalid MPP=1000
> - Zarr for fast partial reads on export; store closed immediately after read to release file handle
> - PIL image cached in RAM for fast viewport tiles; cache cleared after every export so subsequent ROIs on same slide work
> - Pointer capture (`setPointerCapture`) fixes crop selection dropping when cursor leaves canvas
> - Three-canvas architecture: base (thumbnail always visible), tile (hi-res on demand), selection (crop overlay)
> - Windows Photo Viewer cannot open large pyramidal TIFFs — Flat TIFF export solves this
> - PyInstaller: `--onefile --add-data "static;static"` — exe + static\ folder distributed together
> - No branding applied yet — placeholder 🔬 logo and v1.0 badge, ready for new brand when decided
>
> Please continue development from here. The current files are attached.

---

## License
MIT License — free to use, modify, and distribute. Attribution appreciated but not required.

Copyright (c) 2026 Scott Kilcoyne

---

## Contributing
Bug reports and pull requests welcome via GitHub Issues.
If this tool saves your lab time, consider reaching out about consulting services.

---

## Author
**Scott Kilcoyne**
Computational Pathology Consultant
[LinkedIn](https://www.linkedin.com/in/scott-kilcoyne-pathology/)

---

*Last updated: June 2026 — v1.0*
