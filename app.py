#!/usr/bin/env python3
"""
Metro Access Control — Submittal Builder (web UI)

    pip install fastapi uvicorn python-multipart pyyaml pymupdf
    python app.py
    -> open http://localhost:8484

Wraps build.py: the form writes jobs/<slug>/job.yaml, saves uploaded
drawings, runs the build, and hands back the finished PDF.
"""
import os, re, glob, json, io, contextlib
import yaml
from fastapi import FastAPI, UploadFile, File, Form, Body
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse

from paths import bundled, data
import build as builder
import drawgen

JOBS = data("jobs")

app = FastAPI(title="Submittal Builder")


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "job"


@app.get("/", response_class=HTMLResponse)
def index():
    return open(bundled("static", "index.html"), encoding="utf-8").read()


@app.get("/api/config")
def config():
    lib = yaml.safe_load(open(data("library", "library.yaml"), encoding="utf-8"))["items"]
    items = {}
    for iid, e in lib.items():
        items[iid] = {
            "title": e.get("title", iid),
            "scope": e.get("scope", ""),
            "category": e.get("category", ""),
            "has_sheet": bool(e.get("sheets")),
            "pending": bool(e.get("sheet_pending")),
        }
    presets = {}
    for p in sorted(glob.glob(data("presets", "*.yaml"))):
        name = os.path.splitext(os.path.basename(p))[0]
        presets[name] = yaml.safe_load(open(p, encoding="utf-8"))["items"]
    return {"items": items, "presets": presets}


@app.get("/api/jobs")
def jobs():
    out = []
    if os.path.isdir(JOBS):
        for d in sorted(os.listdir(JOBS)):
            if d.startswith("_") or not os.path.isdir(os.path.join(JOBS, d)):
                continue
            pdfs = sorted(glob.glob(os.path.join(JOBS, d, "*.pdf")),
                          key=os.path.getmtime, reverse=True)
            out.append({"slug": d,
                        "pdf": os.path.basename(pdfs[0]) if pdfs else None})
    return out


@app.post("/api/build")
async def build(job: str = Form(...), drawings: list[UploadFile] = File(default=[])):
    data = json.loads(job)
    if not data.get("name", "").strip():
        return JSONResponse({"ok": False, "log": "Project name is required."}, status_code=400)

    slug = slugify(data["name"])
    job_dir = os.path.join(JOBS, slug)
    os.makedirs(os.path.join(job_dir, "drawings"), exist_ok=True)

    # save uploaded drawings
    for up in drawings:
        dest = os.path.join(job_dir, "drawings", os.path.basename(up.filename))
        with open(dest, "wb") as f:
            f.write(await up.read())

    # assemble job.yaml structure
    gates = []
    for i, g in enumerate(data.get("gates", []), start=1):
        gate = {
            "id": slugify(g.get("label", "").strip() or f"gate-{i}"),
            "heading": g["heading"],
            "label": g["label"],
            "preset": g.get("preset", ""),
            "items": [{"id": it["id"], "qty": it.get("qty", 1)} for it in g.get("items", [])],
        }
        if g.get("extra_scope"):
            gate["extra_scope"] = g["extra_scope"]
        if g.get("scope_notes"):
            gate["scope_notes"] = [{"item": n["item"], "text": n["text"]}
                                   for n in g["scope_notes"] if n.get("text", "").strip()]
        gates.append(gate)

    manifest = {
        "project": {
            "name": data["name"].upper(),
            "address": [a for a in data.get("address", []) if a.strip()],
            "submitted": data.get("submitted", ""),
        },
        "gates": gates,
        "drawings": [{"file": d["file"],
                      **({"label": d["label"], "pos": [d.get("x", 480), d.get("y", 480)]}
                         if d.get("label", "").strip() else {})}
                     for d in data.get("drawings", [])],
    }
    with open(os.path.join(job_dir, "job.yaml"), "w", encoding="utf-8") as f:
        yaml.safe_dump(manifest, f, sort_keys=False, allow_unicode=True)

    # run the builder in-process (works frozen; build.py has no global state
    # between runs and re-reads library.yaml each call)
    buf = io.StringIO()
    ok = True
    try:
        with contextlib.redirect_stdout(buf):
            builder.main(job_dir)
    except SystemExit as e:          # build.py uses sys.exit(msg) for hard errors
        if e.code not in (None, 0):
            buf.write(f"\n{e.code}")
            ok = False
    except Exception as e:
        buf.write(f"\nERROR: {e}")
        ok = False
    log = buf.getvalue()
    if not ok:
        return JSONResponse({"ok": False, "log": log}, status_code=500)

    pdfs = sorted(glob.glob(os.path.join(job_dir, "*.pdf")), key=os.path.getmtime, reverse=True)
    pdf = os.path.basename(pdfs[0]) if pdfs else None
    return {"ok": True, "log": log, "slug": slug, "pdf": pdf}


@app.get("/download/{slug}/{fname}")
def download(slug: str, fname: str):
    path = os.path.join(JOBS, os.path.basename(slug), os.path.basename(fname))
    if not os.path.isfile(path):
        return JSONResponse({"error": "not found"}, status_code=404)
    return FileResponse(path, media_type="application/pdf", filename=fname)


# ---------------------------------------------------------------- drawings
DRAWINGS = data("drawings")


def _drawing_name(params):
    op = drawgen.ft_in(drawgen._num(params, "opening_in", 288, 24, 1200)).replace('"', "").replace("'", "")
    config = str(params.get("config", "double")).title()
    sheet = str(params.get("sheet_no", "A.01"))
    date = str(params.get("date", "") or "").replace("/", "-")
    stamp = f" - {date}" if date else ""
    return f"{config} Slide Gate {op} - {sheet}{stamp}.pdf".replace("  ", " ")


@app.post("/api/drawing/preview")
def drawing_preview(params: dict = Body(...)):
    d = drawgen.compute(params)
    return {"svg": drawgen.to_svg(d), "scale": d["scale"], "devices": d["devices"],
            "operator_models": drawgen.OPERATOR_MODELS}


@app.post("/api/drawing/save")
def drawing_save(params: dict = Body(...)):
    os.makedirs(DRAWINGS, exist_ok=True)
    name = _drawing_name(params)
    drawgen.to_pdf(drawgen.compute(params), os.path.join(DRAWINGS, name))
    return {"ok": True, "file": name}


@app.get("/download-drawing/{fname}")
def download_drawing(fname: str):
    path = os.path.join(DRAWINGS, os.path.basename(fname))
    if not os.path.isfile(path):
        return JSONResponse({"error": "not found"}, status_code=404)
    return FileResponse(path, media_type="application/pdf", filename=fname)


if __name__ == "__main__":
    import uvicorn
    print("Submittal Builder -> http://localhost:8484")
    uvicorn.run(app, host="0.0.0.0", port=8484)
