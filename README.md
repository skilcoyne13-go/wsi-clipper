# WSI Clipper v1.0
**Whole Slide Image — Region of Interest Exporter**

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Version](https://img.shields.io/badge/version-1.0-blue.svg)]()
[![Platform](https://img.shields.io/badge/platform-Windows-lightgrey.svg)]()

A free standalone tool for scanning staff and pathology labs to crop a Whole Slide Image (WSI) and export the selected region as a pyramidal TIFF for pathologist review.

**Built by Scott Kilcoyne** — [LinkedIn](https://www.linkedin.com/in/scott-kilcoyne-pathology/)

> Free to use. No subscription. No cloud upload. Your data stays on your machine.

---

## Download
**[→ Download WSI Clipper v1.0 (Windows)](https://github.com/skilcoyne13-go/wsi-clipper/releases/latest)**

Unzip and follow the Quick Start steps below.

---

## Requirements
- Windows 10 or 11
- [Python 3.10 or newer](https://www.python.org/downloads/) — **check "Add Python to PATH"** during install

---

## Quick Start

**First time only:**
1. Install Python from python.org — check **"Add Python to PATH"**
2. Unzip the downloaded file
3. Double-click **`install_and_run.bat`**
4. Wait for dependencies to install — browser opens automatically

**Every time after:**
- Double-click **`run.bat`**
- Browser opens automatically at http://localhost:5050

---

## How to Use
1. Drop your WSI file into the tool
2. Thumbnail of the full slide loads in the viewer
3. Zoom and pan to find the best kidney section
4. Draw a crop rectangle over the target region
5. Add notes and operator name if needed
6. Choose export format and click **Export Image**
7. File saves automatically and downloads to your browser

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

## Features
- Pan, zoom, and navigate gigapixel WSI files
- Minimap navigator showing position on full slide
- Hi-res tile fetching — sharpens as you zoom in
- Scale bar burned into exports
- Notes and operator name embedded in TIFF metadata
- Export log saved to CSV — tracks every export with timestamp
- Brightness and contrast adjustment for viewing
- Keyboard shortcuts: `Space` pan/crop toggle, `C` crop, `+/-` zoom, `F` fit, `Esc` clear

---

## Folder Structure
```
WSI Clipper\
├── server.py              ← Python backend
├── install_and_run.bat    ← First-time setup and launch
├── run.bat                ← Launch after first time
├── requirements.txt       ← Python dependencies
├── static\
│   └── index.html         ← Frontend UI
├── wsi_uploads\           ← Temp folder for uploaded slides
└── wsi_exports\           ← Exported files saved here
    └── export_log.csv     ← Auto-generated export history
```

---

## Known Behaviour
- **KFBio TIFFs**: Converted KFBio files have no embedded pyramid. Tool reads full-res via zarr and builds pyramid on export. First zoom-in triggers a one-time PIL decode into RAM.
- **MPP**: KFBio TIFFs report MPP = 1000 (invalid). Tool ignores values outside 0.05–10.0 µm/px and defaults to 0.25. Override manually in the MPP field if known.
- **Export size**: No crop size limit. Large ROIs (500+ MP) take longer — JPEG is fastest for very large exports.
- **Multiple ROIs same slide**: PIL cache clears after each export and reloads on next tile fetch. Brief delay after export is normal.

---

## v1.0 — Beta
This is an initial release. If you encounter issues with a specific scanner format or file, please open a GitHub Issue with details of the error and file format.

---

## For Developers
To run from source:
```
pip install flask flask-cors pillow tifffile numpy imagecodecs zarr openslide-python
python server.py
```

To build executable (optional):
```
pyinstaller --onedir --add-data "static;static" --name WSI_Clipper server.py
```

---

## Branding
When ready to apply branding:
- Replace `<div class="logo">🔬</div>` in `static\index.html` with `<img src="logo.png" style="height:32px;width:auto;">`
- Save logo as `logo.png` in `static\`
- Update `v1.0` badge and `<title>` tag with your product name
- Rebuild with PyInstaller if distributing as exe

---

## AI Development Continuation Prompt
*To continue development in a new AI session, paste the following:*

---

> I am building a standalone WSI (Whole Slide Image) clipping tool called **WSI Clipper v1.0** for free distribution to pathology labs. Users run it via `python server.py` or `run.bat` — no exe required.
>
> The tool is built with:
> - **Python backend** (`server.py`) using Flask, tifffile, zarr, numpy, PIL, and optionally OpenSlide
> - **Frontend** (`static/index.html`) — single HTML file with three stacked canvases (base thumbnail, hi-res tile, selection overlay), pointer capture for reliable crop selection, viewport tile fetching 120ms after pan/zoom stops, minimap navigator, brightness/contrast sliders, export log, notes/operator fields, scale bar option
> - **Three export formats**: Pyramidal TIFF with OME metadata (QuPath/OMERO), Flat TIFF (Windows Photo Viewer), JPEG (universal)
>
> Key solved problems:
> - KFBio-converted TIFFs: single series, no pyramid, JPEG compressed, requires imagecodecs. Metadata reads correct dimensions via series shape, ignores invalid MPP=1000
> - Zarr for fast partial reads on export; store closed immediately after read
> - PIL image cached in RAM for fast viewport tiles; cache cleared after every export
> - Pointer capture fixes crop selection dropping when cursor leaves canvas
> - Three-canvas architecture: base (thumbnail), tile (hi-res on demand), selection (crop overlay)
> - Windows Photo Viewer cannot open large pyramidal TIFFs — Flat TIFF export solves this
> - MemoryError on large slides fixed by capping tile fetch coverage at 50% and max 2048px
> - Distribution via Python script + bat files — simpler and more reliable than PyInstaller exe for lab environment
> - GitHub: https://github.com/skilcoyne13-go/wsi-clipper
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
