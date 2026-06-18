"""
WSI Clipper — Python Backend v5
Run: python server.py
Then open: http://localhost:5050
"""

import os, io, math, json, threading, webbrowser, csv
from pathlib import Path
from datetime import datetime

from flask import Flask, request, jsonify, send_file, send_from_directory, Response
from flask_cors import CORS
from PIL import Image, ImageDraw, ImageFont
Image.MAX_IMAGE_PIXELS = None

try:
    import ctypes
    import openslide
    HAS_OPENSLIDE = True
except Exception:
    HAS_OPENSLIDE = False
    openslide = None

try:
    import tifffile
    import numpy as np
    HAS_TIFFFILE = True
except ImportError:
    HAS_TIFFFILE = False

try:
    import pyvips
    HAS_PYVIPS = True
except ImportError:
    HAS_PYVIPS = False

# ── App setup ─────────────────────────────────────────────────────────────────
app = Flask(__name__, static_folder="static")
CORS(app)

UPLOAD_DIR = Path("wsi_uploads")
EXPORT_DIR = Path("wsi_exports")
LOG_FILE   = Path("wsi_exports") / "export_log.csv"
UPLOAD_DIR.mkdir(exist_ok=True)
EXPORT_DIR.mkdir(exist_ok=True)

current_slide = {"path": None, "handle": None, "driver": None, "meta": {}}
_pil_cache    = {"path": None, "img": None}

# ── Export progress tracking ──────────────────────────────────────────────────
export_progress = {"pct": 0, "msg": "", "done": False, "error": None}

def set_progress(pct, msg):
    export_progress["pct"]   = pct
    export_progress["msg"]   = msg
    export_progress["done"]  = False
    export_progress["error"] = None
    print(f"[Export {pct}%] {msg}")

# ── PIL cache ─────────────────────────────────────────────────────────────────
def get_pil_image(path):
    if _pil_cache["path"] != str(path):
        print(f"[PIL cache] Loading {Path(path).name}...")
        img = Image.open(str(path))
        img.load()
        _pil_cache["path"] = str(path)
        _pil_cache["img"]  = img
        print(f"[PIL cache] Done.")
    return _pil_cache["img"]

# ── Open slide ────────────────────────────────────────────────────────────────
def open_slide(path: Path):
    ext = path.suffix.lower()
    if HAS_OPENSLIDE and ext in (".svs",".ndpi",".scn",".mrxs",".tiff",".tif",".bif"):
        try:
            return "openslide", openslide.OpenSlide(str(path))
        except Exception:
            pass
    if HAS_TIFFFILE and ext in (".tiff",".tif",".qptiff"):
        try:
            return "tifffile", tifffile.TiffFile(str(path))
        except Exception:
            pass
    return "pil", Image.open(str(path))

# ── Metadata ──────────────────────────────────────────────────────────────────
def get_meta(driver, handle, path: Path) -> dict:
    meta = {"filename": path.name, "driver": driver}
    if driver == "openslide":
        w, h = handle.dimensions
        meta["width"]  = w
        meta["height"] = h
        meta["level_count"]       = handle.level_count
        meta["level_dimensions"]  = [list(d) for d in handle.level_dimensions]
        meta["level_downsamples"] = [round(d,4) for d in handle.level_downsamples]
        props = dict(handle.properties)
        meta["mpp_x"]  = float(props.get("openslide.mpp-x", 0.25))
        meta["mpp_y"]  = float(props.get("openslide.mpp-y", 0.25))
        meta["vendor"] = props.get("openslide.vendor","unknown")
    elif driver == "tifffile":
        meta.update(_tifffile_meta(handle))
    else:
        meta["width"], meta["height"] = handle.size
        meta["level_count"]       = 1
        meta["level_dimensions"]  = [[meta["width"], meta["height"]]]
        meta["level_downsamples"] = [1.0]
        meta["mpp_x"] = 0.25
        meta["mpp_y"] = 0.25
    meta["file_size_mb"] = round(path.stat().st_size / 1048576, 1)
    return meta

def _tifffile_meta(tf_handle) -> dict:
    meta = {"mpp_x":0.25,"mpp_y":0.25,"level_count":1,
            "level_dimensions":[],"level_downsamples":[1.0],"strip_based":False}
    p0 = tf_handle.pages[0]
    if tf_handle.series:
        def series_pixels(s):
            sh = s.shape
            return sh[-1]*sh[-2] if len(sh)>=2 else 0
        main = max(tf_handle.series, key=series_pixels)
        sh = main.shape
        if len(sh)==3:
            if sh[0] in (1,3,4) and sh[0]<sh[1] and sh[0]<sh[2]: h,w = sh[1],sh[2]
            else: h,w = sh[0],sh[1]
        elif len(sh)==2: h,w = sh[0],sh[1]
        else: h,w = p0.imagelength,p0.imagewidth
        meta["width"]  = int(w)
        meta["height"] = int(h)
        aspect = w/h if h>0 else 1
        levels = []
        for s in tf_handle.series:
            ssh = s.shape
            if len(ssh)<2: continue
            sw = int(ssh[-1]); sh2 = int(ssh[-2]) if len(ssh)>=2 else int(ssh[-1])
            if sw<=0 or sh2<=0: continue
            if sw<=w and sh2<=h and abs((sw/sh2)-aspect)<0.15:
                levels.append((sw,sh2,s))
        levels.sort(key=lambda x:x[0], reverse=True)
        if levels:
            meta["level_count"]       = len(levels)
            meta["level_dimensions"]  = [[lw,lh] for lw,lh,_ in levels]
            meta["level_downsamples"] = [round(w/lw,4) for lw,lh,_ in levels]
            current_slide["_series_list"] = [s for _,_,s in levels]
        else:
            meta["level_count"]       = 1
            meta["level_dimensions"]  = [[w,h]]
            meta["level_downsamples"] = [1.0]
            current_slide["_series_list"] = [main]
    else:
        w,h = p0.imagewidth,p0.imagelength
        meta["width"]  = int(w)
        meta["height"] = int(h)
        meta["level_count"]       = 1
        meta["level_dimensions"]  = [[w,h]]
        meta["level_downsamples"] = [1.0]
        current_slide["_series_list"] = []
    try:
        tags = p0.tags
        xres_tag = tags.get(282); unit_tag = tags.get(296)
        if xres_tag and unit_tag:
            xres = xres_tag.value; unit = unit_tag.value
            res  = (xres[0]/xres[1]) if isinstance(xres,tuple) and xres[1]!=0 else float(xres)
            if res>0:
                mpp = None
                if unit==3:   mpp = round(10000.0/res,6)
                elif unit==2: mpp = round(25400.0/res,6)
                if mpp and 0.05<mpp<10.0:
                    meta["mpp_x"] = meta["mpp_y"] = mpp
    except Exception:
        pass
    return meta

def _normalize_array(arr):
    if arr.ndim==3 and arr.shape[0] in (1,3,4) and arr.shape[0]<arr.shape[1]:
        arr = arr.transpose(1,2,0)
    if arr.ndim==3 and arr.shape[2]==1: arr = arr[:,:,0]
    if arr.dtype!=np.uint8:
        mn,mx = arr.min(),arr.max()
        arr = ((arr-mn)/(mx-mn)*255).astype(np.uint8) if mx>mn else np.zeros_like(arr,dtype=np.uint8)
    return arr

# ── Region reading ────────────────────────────────────────────────────────────
def read_region(driver, handle, x, y, w, h, level=0) -> Image.Image:
    if driver=="openslide":
        ds = handle.level_downsamples[level]
        return handle.read_region((x,y),level,(math.ceil(w/ds),math.ceil(h/ds))).convert("RGB")
    elif driver=="tifffile":
        meta = current_slide["meta"]
        series_list = current_slide.get("_series_list",[])
        safe_level  = min(level,len(series_list)-1) if series_list else 0
        ds = meta["level_downsamples"][safe_level] if meta["level_downsamples"] else 1.0
        lx=math.floor(x/ds); ly=math.floor(y/ds)
        lw=math.ceil(w/ds);  lh=math.ceil(h/ds)
        try:
            if series_list and safe_level<len(series_list):
                try:
                    import zarr
                    store = series_list[safe_level].aszarr()
                    z = zarr.open(store,mode='r')
                    sh = z.shape
                    H = sh[0] if sh[0]>sh[-1] else sh[-2]
                    W = sh[1] if sh[0]>sh[-1] else sh[-1]
                    ly2=max(0,min(ly,H-1)); lx2=max(0,min(lx,W-1))
                    lh2=min(lh,H-ly2);     lw2=min(lw,W-lx2)
                    arr = z[ly2:ly2+lh2,lx2:lx2+lw2] if sh[0]>sh[-1] else z[:,ly2:ly2+lh2,lx2:lx2+lw2].transpose(1,2,0)
                    arr = _normalize_array(arr)
                    if arr.ndim==2: arr=np.stack([arr]*3,axis=-1)
                    elif arr.shape[2]==4: arr=arr[:,:,:3]
                    return Image.fromarray(arr).convert("RGB")
                except ImportError:
                    pass
            raise ValueError("use PIL")
        except Exception:
            img = get_pil_image(current_slide["path"])
            iw,ih = img.size
            return img.crop((max(0,lx),max(0,ly),min(lx+lw,iw),min(ly+lh,ih))).convert("RGB")
    else:
        img = get_pil_image(current_slide["path"])
        iw,ih = img.size
        return img.crop((max(0,x),max(0,y),min(x+w,iw),min(y+h,ih))).convert("RGB")

# ── Thumbnail ─────────────────────────────────────────────────────────────────
def _tifffile_thumbnail(tf_handle, max_size=2048):
    meta = current_slide.get("meta",{})
    series_list = current_slide.get("_series_list",[])
    target_series = None
    for i,(lw,lh) in enumerate(reversed(meta.get("level_dimensions",[]))):
        idx = len(meta["level_dimensions"])-1-i
        if idx<len(series_list):
            target_series = series_list[idx]
            if lw>=256 and lh>=256: break
    if target_series is not None:
        try:
            arr = _normalize_array(target_series.asarray())
            if arr.ndim==2: arr=np.stack([arr]*3,axis=-1)
            elif arr.shape[2]==4: arr=arr[:,:,:3]
            img = Image.fromarray(arr).convert("RGB")
            img.thumbnail((max_size,max_size),Image.LANCZOS)
            return img
        except Exception as e:
            print(f"[Thumb] Series failed: {e}")
    img = get_pil_image(current_slide["path"])
    thumb = img.copy()
    thumb.thumbnail((max_size,max_size),Image.LANCZOS)
    return thumb.convert("RGB")

# ── Scale bar ─────────────────────────────────────────────────────────────────
def _draw_scale_bar(img: Image.Image, mpp: float) -> Image.Image:
    """Burn a scale bar into the bottom-left of an exported image."""
    img = img.copy()
    w, h = img.size
    draw = ImageDraw.Draw(img)

    # Pick a round scale bar length in microns
    bar_px_target = w * 0.12   # aim for ~12% of image width
    bar_um = bar_px_target * mpp
    # Round to nearest clean value
    for clean in [50,100,200,500,1000,2000,5000,10000]:
        if clean >= bar_um * 0.5:
            bar_um_final = clean
            break
    else:
        bar_um_final = round(bar_um / 100) * 100

    bar_px = int(bar_um_final / mpp)
    margin = int(w * 0.025)
    bar_h  = max(4, int(h * 0.008))
    x0 = margin
    y0 = h - margin - bar_h - int(h * 0.025)
    x1 = x0 + bar_px
    y1 = y0 + bar_h

    # Shadow + bar
    draw.rectangle([x0+2,y0+2,x1+2,y1+2], fill=(0,0,0,180))
    draw.rectangle([x0,y0,x1,y1], fill=(255,255,255))

    # Label
    if bar_um_final >= 1000:
        label = f"{bar_um_final//1000} mm"
    else:
        label = f"{bar_um_final} µm"

    font_size = max(12, int(h * 0.018))
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except Exception:
        font = ImageFont.load_default()

    tx = x0
    ty = y0 - font_size - 4
    draw.text((tx+1,ty+1), label, fill=(0,0,0), font=font)
    draw.text((tx,ty),     label, fill=(255,255,255), font=font)
    return img

# ── Export log ────────────────────────────────────────────────────────────────
def _write_log(entry: dict):
    file_exists = LOG_FILE.exists()
    with open(str(LOG_FILE), "a", newline="") as f:
        cols = ["timestamp","filename","source_file","x","y","width","height",
                "width_mm","height_mm","megapixels","format","compression",
                "size_mb","notes","operator"]
        writer = csv.DictWriter(f, fieldnames=cols)
        if not file_exists:
            writer.writeheader()
        writer.writerow({k: entry.get(k,"") for k in cols})

# ── Routes ────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory("static","index.html")

@app.route("/api/open", methods=["POST"])
def api_open():
    if "file" in request.files:
        f = request.files["file"]
        dest = UPLOAD_DIR / f.filename
        f.save(str(dest))
        path = dest
    elif request.json and "path" in request.json:
        path = Path(request.json["path"])
    else:
        return jsonify({"error":"No file or path provided"}),400
    if not path.exists():
        return jsonify({"error":f"File not found: {path}"}),404
    try:
        if current_slide["handle"] and current_slide["driver"]=="openslide":
            try: current_slide["handle"].close()
            except: pass
        _pil_cache["path"] = None
        _pil_cache["img"]  = None
        current_slide["_series_list"] = []
        driver, handle = open_slide(path)
        meta = get_meta(driver, handle, path)
        current_slide.update({"path":path,"driver":driver,"handle":handle,"meta":meta})
        return jsonify({"ok":True,"meta":meta})
    except Exception as e:
        import traceback
        return jsonify({"error":str(e),"trace":traceback.format_exc()}),500

@app.route("/api/thumbnail")
def api_thumbnail():
    if not current_slide["handle"]:
        return jsonify({"error":"No slide loaded"}),400
    try:
        driver = current_slide["driver"]
        handle = current_slide["handle"]
        if driver=="openslide":
            thumb = handle.get_thumbnail((2048,2048)).convert("RGB")
        elif driver=="tifffile":
            thumb = _tifffile_thumbnail(handle,2048)
        else:
            img = get_pil_image(current_slide["path"])
            thumb = img.copy(); thumb.thumbnail((2048,2048),Image.LANCZOS)
            thumb = thumb.convert("RGB")
        buf = io.BytesIO()
        thumb.save(buf,"JPEG",quality=85)
        buf.seek(0)
        return send_file(buf,mimetype="image/jpeg")
    except Exception as e:
        import traceback; print(traceback.format_exc())
        return jsonify({"error":str(e)}),500

@app.route("/api/region")
def api_region():
    if not current_slide["handle"]:
        return jsonify({"error":"No slide loaded"}),400
    try:
        x=int(request.args.get("x",0)); y=int(request.args.get("y",0))
        w=int(request.args.get("w",512)); h=int(request.args.get("h",512))
        lv=int(request.args.get("level",0)); q=int(request.args.get("q",85))
        region = read_region(current_slide["driver"],current_slide["handle"],x,y,w,h,lv)
        buf = io.BytesIO()
        region.save(buf,"JPEG",quality=q)
        buf.seek(0)
        return send_file(buf,mimetype="image/jpeg")
    except Exception as e:
        import traceback; print(traceback.format_exc())
        return jsonify({"error":str(e)}),500

@app.route("/api/progress")
def api_progress():
    return jsonify(export_progress)

@app.route("/api/export", methods=["POST"])
def api_export():
    data  = request.json or {}
    x     = int(data.get("x",0));   y    = int(data.get("y",0))
    w     = int(data.get("w",1000)); h    = int(data.get("h",1000))
    lvls  = int(data.get("out_levels",4))
    ts    = int(data.get("tile_size",256))
    comp  = data.get("compression","jpeg")
    jq    = int(data.get("jpeg_quality",90))
    fmt   = data.get("export_format","pyramid")
    fname = data.get("filename","roi_export").replace(" ","_")
    notes = data.get("notes","")
    operator = data.get("operator","")
    scale_bar = data.get("scale_bar", False)

    if not current_slide["handle"]:
        return jsonify({"error":"No slide loaded"}),400

    ext      = ".jpg" if fmt=="jpeg" else ".tiff"
    out_path = EXPORT_DIR / (fname + ext)
    meta     = current_slide["meta"]
    mpp      = float(data.get("mpp_override",0)) or meta.get("mpp_x",0.25)

    try:
        export_progress.update({"pct":0,"msg":"Starting...","done":False,"error":None})

        # ── Read ROI ──────────────────────────────────────────────────────────
        set_progress(5, "Reading ROI from source...")
        driver = current_slide["driver"]
        handle = current_slide["handle"]
        path   = current_slide["path"]

        if driver=="openslide":
            region = handle.read_region((x,y),0,(w,h)).convert("RGB")
        elif driver=="tifffile":
            try:
                import zarr
                series_list = current_slide.get("_series_list",[])
                if series_list:
                    store = series_list[0].aszarr()
                    z = zarr.open(store,mode='r')
                    sh = z.shape
                    y2=min(y+h,sh[0]); x2=min(x+w,sh[1])
                    arr = z[y:y2,x:x2]
                    arr = _normalize_array(arr)
                    if arr.ndim==2: arr=np.stack([arr]*3,axis=-1)
                    elif arr.shape[2]==4: arr=arr[:,:,:3]
                    region = Image.fromarray(arr).convert("RGB")
                    store.close()
                else:
                    raise ValueError("No series")
            except Exception as ze:
                print(f"[Export] zarr failed ({ze}), PIL fallback...")
                img = get_pil_image(path)
                iw,ih = img.size
                region = img.crop((max(0,x),max(0,y),min(x+w,iw),min(y+h,ih))).convert("RGB")
        else:
            img = get_pil_image(path)
            iw,ih = img.size
            region = img.crop((max(0,x),max(0,y),min(x+w,iw),min(y+h,ih))).convert("RGB")

        set_progress(30, f"ROI read: {region.size[0]}×{region.size[1]} px")

        # Optionally burn scale bar
        if scale_bar and mpp>0:
            set_progress(35,"Adding scale bar...")
            region = _draw_scale_bar(region, mpp)

        # ── Write output ──────────────────────────────────────────────────────
        if fmt=="jpeg":
            set_progress(40,"Writing JPEG...")
            region.save(str(out_path),"JPEG",quality=jq,subsampling=0)
            set_progress(90,"Finalising...")

        elif fmt=="flat":
            set_progress(40,"Writing flat TIFF (Windows Photo Viewer compatible)...")
            res_ppcm = 10000.0/mpp
            region.save(str(out_path),"TIFF",
                        compression="tiff_lzw",
                        resolution=(res_ppcm,res_ppcm),
                        resolutionunit=3,
                        software="WSI Clipper v1.0")
            set_progress(90,"Finalising...")

        else:
            # Pyramidal TIFF with OME metadata
            set_progress(40,"Building pyramid levels...")
            tf_comp = {"lzw":"lzw","jpeg":"jpeg","deflate":"deflate","none":None}.get(comp,"jpeg")
            res_ppcm = 10000.0/mpp

            # Build OME-XML — strict 7-bit ASCII, no special characters
            fname_safe = ''.join(c for c in fname if ord(c) < 128)
            ome_xml = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<OME xmlns="http://www.openmicroscopy.org/Schemas/OME/2016-06">'
                '<Image ID="Image:0" Name="' + fname_safe + '">'
                '<Description>Exported by WSI Clipper v1.0 | Built by Scott Kilcoyne | https://github.com/skilcoyne13-go/wsi-clipper</Description>'
                '<Pixels ID="Pixels:0" Type="uint8"'
                ' SizeX="' + str(w) + '" SizeY="' + str(h) + '"'
                ' SizeZ="1" SizeC="3" SizeT="1"'
                ' PhysicalSizeX="' + str(mpp) + '"'
                ' PhysicalSizeXUnit="um"'
                ' PhysicalSizeY="' + str(mpp) + '"'
                ' PhysicalSizeYUnit="um"'
                ' DimensionOrder="XYZCT">'
                '<Channel ID="Channel:0:0" SamplesPerPixel="3"/>'
                '<TiffData/>'
                '</Pixels>'
                '</Image>'
                '</OME>'
            ).encode('ascii').decode('ascii')  # hard fail if anything slips through

            with tifffile.TiffWriter(str(out_path), bigtiff=(w*h>100_000_000)) as tw:
                for lv in range(lvls):
                    factor = 2**lv
                    lw = max(1,w//factor)
                    lh = max(1,h//factor)
                    lv_img = region if lv==0 else region.resize((lw,lh),Image.LANCZOS)
                    pct = 40 + int((lv/lvls)*50)
                    set_progress(pct, f"Writing level {lv+1}/{lvls}: {lw}×{lh} px")
                    arr  = np.array(lv_img)
                    opts = dict(
                        tile=(ts,ts),
                        photometric="rgb",
                        resolutionunit=tifffile.RESUNIT.CENTIMETER,
                        resolution=(res_ppcm/factor,res_ppcm/factor),
                        subfiletype=1 if lv>0 else 0,
                        software="WSI Clipper v1.0",
                    )
                    if tf_comp:
                        opts["compression"] = tf_comp
                    if comp=="jpeg":
                        opts["compressionargs"] = {"level":jq}
                    # Embed OME-XML in first IFD only, skip if tifffile rejects it
                    if lv == 0:
                        try:
                            opts["description"] = ome_xml
                            tw.write(arr, **opts)
                        except Exception:
                            opts.pop("description", None)
                            tw.write(arr, **opts)
                    else:
                        tw.write(arr, **opts)
            set_progress(92,"Finalising...")

        # Flush and verify
        size_mb = round(out_path.stat().st_size/1048576,1)

        # Reset PIL cache so next ROI fetch works
        _pil_cache["path"] = None
        _pil_cache["img"]  = None

        # Write export log
        _write_log({
            "timestamp":  datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "filename":   out_path.name,
            "source_file":current_slide["meta"].get("filename",""),
            "x":x,"y":y,"width":w,"height":h,
            "width_mm":  round(w*mpp/1000,3),
            "height_mm": round(h*mpp/1000,3),
            "megapixels":round(w*h/1e6,1),
            "format":    fmt,
            "compression":comp,
            "size_mb":   size_mb,
            "notes":     notes,
            "operator":  operator,
        })

        set_progress(100, f"Done: {out_path.name} ({size_mb} MB)")
        export_progress["done"] = True

        return jsonify({"ok":True,"path":str(out_path.resolve()),
                        "size_mb":size_mb,"filename":out_path.name})

    except Exception as e:
        import traceback; tb = traceback.format_exc()
        print(tb)
        export_progress["error"] = str(e)
        return jsonify({"error":str(e),"trace":tb}),500

@app.route("/api/download/<filename>")
def api_download(filename):
    return send_from_directory(str(EXPORT_DIR.resolve()),filename,as_attachment=True)

@app.route("/api/log")
def api_log():
    if not LOG_FILE.exists():
        return jsonify([])
    rows = []
    with open(str(LOG_FILE),newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return jsonify(rows[-20:])  # last 20 entries

@app.route("/api/capabilities")
def api_capabilities():
    return jsonify({"openslide":HAS_OPENSLIDE,"tifffile":HAS_TIFFFILE,
                    "pyvips":HAS_PYVIPS,"pil":True})

# ── Launch ────────────────────────────────────────────────────────────────────
if __name__=="__main__":
    PORT = 5050
    print("\n"+"═"*55)
    print("  WSI Clipper — Backend Server v5")
    print("═"*55)
    print(f"  OpenSlide : {'✓' if HAS_OPENSLIDE else '✗'}")
    print(f"  tifffile  : {'✓' if HAS_TIFFFILE  else '✗'}")
    print(f"  pyvips    : {'✓' if HAS_PYVIPS    else '✗'}")
    print("═"*55)
    print(f"\n  → Open http://localhost:{PORT}\n")
    threading.Timer(1.2,lambda: webbrowser.open(f"http://localhost:{PORT}")).start()
    app.run(host="0.0.0.0",port=PORT,debug=False,threaded=True)
