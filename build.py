#!/usr/bin/env python3
"""
Metro Access Control — Submittal Package Builder

Usage:
    python3 build.py jobs/<job-name>

Reads:
    library/library.yaml          spec sheet metadata (scope lines, files, stamp positions)
    presets/<preset>.yaml         standard device kits referenced by the job
    jobs/<job>/job.yaml           project info, gates, notes, drawings
    jobs/<job>/drawings/*.pdf     contractor drawings
    assets/cover-template.pdf     branded cover page (logo/frames/exclusions)
    fonts/cambria*.ttf            optional — drop in for exact font match,
                                  otherwise falls back to Liberation Serif / Times

Writes:
    jobs/<job>/Submittal - <project> - <date>.pdf
"""
import sys, os, glob
import yaml
import fitz

from paths import bundled, data

BLUE = (0.0, 0.0, 1.0)
RED = (1.0, 0.0, 0.0)
BLACK = (0.0, 0.0, 0.0)
COLORS = {"blue": BLUE, "red": RED, "black": BLACK}

# ---------------------------------------------------------------- fonts
def find_font(bold=False):
    """Cambria if the user dropped it in fonts/, else Liberation Serif, else Times."""
    pats = ["cambriab*", "cambria-bold*"] if bold else ["cambria.*", "cambria-regular*"]
    for p in pats:
        hits = glob.glob(bundled("fonts", p))
        if hits:
            return hits[0]
    candidates = (
        [r"C:\Windows\Fonts\cambriab.ttf", r"C:\Windows\Fonts\cambria.ttc",
         "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf"] if bold else
        [r"C:\Windows\Fonts\cambria.ttc",
         "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf"])
    for c in candidates:
        if os.path.exists(c):
            return c
    return None

SERIF = find_font(False)
SERIF_BOLD = find_font(True)

def insert(page, point, text, size, color=BLACK, bold=False, fontsize_adjust=0):
    f = SERIF_BOLD if bold else SERIF
    if f:
        page.insert_text(point, text, fontfile=f, fontname="serifB" if bold else "serif",
                         fontsize=size + fontsize_adjust, color=color)
    else:
        page.insert_text(point, text, fontname="tibo" if bold else "tiro",
                         fontsize=size + fontsize_adjust, color=color)

def measure(text, size, bold=False):
    f = SERIF_BOLD if bold else SERIF
    font = fitz.Font(fontfile=f) if f else fitz.Font("tiro")
    return font.text_length(text, fontsize=size)

def wrap(text, size, max_w, bold=False):
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if measure(trial, size, bold) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines

# ---------------------------------------------------------------- cover
def build_cover(doc, template_path, project, gate, items, lib):
    doc.insert_pdf(fitz.open(template_path))
    page = doc[-1]

    # Project block (centered ~x377, matching original baselines)
    cx = 377
    y = 55
    for line in [project["name"], *project["address"]]:
        w = measure(line, 18)
        insert(page, (cx - w / 2, y), line, 18)
        y += 21
    sub = f"Submitted: {project['submitted']}"
    w = measure(sub, 18)
    insert(page, (cx - w / 2, y), sub, 18, color=RED)

    # Scope body
    X_ITEM, X_NOTE, MAX_W, LEAD = 216, 236, 350, 11.7
    y = 199
    insert(page, (180, y), gate["heading"], 10, bold=True)
    y += LEAD
    insert(page, (180, y), "INSTALL", 10)
    y += LEAD

    notes = {n["item"]: n["text"] for n in gate.get("scope_notes", [])}
    for it in items:
        entry = lib[it["id"]]
        scope = entry["scope"]
        if "{qty}" in scope:
            scope = scope.replace("{qty}", str(it.get("qty", 1)))
        for raw in scope.split("\n"):
            hang = raw.startswith(" ")
            for j, ln in enumerate(wrap(raw.strip(), 10, MAX_W)):
                x = X_ITEM if (j == 0 and not hang) else X_ITEM + (4 if hang else 12)
                insert(page, (x, y), ln, 10)
                y += LEAD
        if it["id"] in notes:
            for j, ln in enumerate(wrap(notes[it["id"]], 10, MAX_W - 24)):
                if j == 0:
                    insert(page, (X_NOTE - 6, y), "\u2022", 10)
                insert(page, (X_NOTE, y), ln, 10, color=RED)
                y += LEAD
    for extra in gate.get("extra_scope", []):
        insert(page, (X_ITEM, y), extra, 10)
        y += LEAD
    if y > 640:
        print(f"  WARNING: scope for '{gate['id']}' ran past the exclusions block (y={y:.0f})")

# ---------------------------------------------------------------- stamps
def stamp_box(page, pos, lines, color=BLUE, size=10):
    """Bordered callout box with auto width/height, original style."""
    pad, lead = 4, size * 1.25
    wrapped = []
    for i, ln in enumerate(lines):
        wrapped.extend(wrap(ln, size, 150))
        if i < len(lines) - 1:
            wrapped.append("")          # blank line between gate labels
    w = max((measure(l, size) for l in wrapped if l), default=50) + 2 * pad
    h = len(wrapped) * lead + 2 * pad
    x, y = pos
    rect = fitz.Rect(x, y, x + w, y + h)
    shape = page.new_shape()
    shape.draw_rect(rect)
    shape.finish(color=color, width=0.8, fill=(1, 1, 1), fill_opacity=0.85)
    shape.commit()
    ty = y + pad + size * 0.85
    for ln in wrapped:
        if ln:
            insert(page, (x + pad, ty), ln, size, color=color)
        ty += lead

# ---------------------------------------------------------------- main
def main(job_dir):
    job = yaml.safe_load(open(os.path.join(job_dir, "job.yaml"), encoding="utf-8"))
    lib = yaml.safe_load(open(data("library", "library.yaml"), encoding="utf-8"))["items"]
    out = fitz.open()

    # Resolve each gate's item list (preset + overrides), collect labels per item
    gate_items, item_labels, order = {}, {}, []
    for gate in job["gates"]:
        if gate.get("items") is not None:          # explicit list (e.g. from the web UI)
            items = [dict(i) for i in gate["items"]]   # may be empty — overrides preset entirely
        else:
            preset = yaml.safe_load(open(data("presets", gate["preset"] + ".yaml"), encoding="utf-8"))
            items = [dict(i) for i in preset["items"]]
        for rm in gate.get("remove", []):
            items = [i for i in items if i["id"] != rm]
        for ov in gate.get("qty_overrides", []):
            for i in items:
                if i["id"] == ov["id"]:
                    i["qty"] = ov["qty"]
        items += [dict(i) for i in gate.get("add", [])]
        gate_items[gate["id"]] = items
        for i in items:
            if i["id"] not in lib:
                sys.exit(f"ERROR: item '{i['id']}' not in library.yaml")
            if i["id"] not in item_labels:
                item_labels[i["id"]] = []
                order.append(i["id"])
            if gate.get("label", "").strip():
                item_labels[i["id"]].append(gate["label"].strip())

    # 1. Cover page per gate
    tpl = bundled("assets", "cover-template.pdf")
    for gate in job["gates"]:
        build_cover(out, tpl, job["project"], gate, gate_items[gate["id"]], lib)
        print(f"cover: {gate['id']} ({len(gate_items[gate['id']])} line items)")

    # Sheet notes indexed by item id
    sheet_notes = {}
    for gate in job["gates"]:
        for n in gate.get("sheet_notes", []):
            sheet_notes.setdefault(n["item"], []).append(n)

    # 2. Spec sheets, deduped, stamped with every gate that uses them
    missing = []
    for item_id in order:
        entry = lib[item_id]
        if not entry.get("sheets"):
            if entry.get("sheet_pending"):
                missing.append(item_id)
            continue
        for s_idx, sheet in enumerate(entry["sheets"], start=1):
            path = data("library", sheet["file"])
            src = fitz.open(path)
            first = len(out)
            out.insert_pdf(src)
            if item_labels[item_id]:
                stamp_box(out[first], sheet.get("stamp", [40, 15]), item_labels[item_id])
            for n in sheet_notes.get(item_id, []):
                if n.get("sheet", 1) == s_idx:
                    stamp_box(out[first + 0], n["pos"], [n["text"]],
                              color=COLORS.get(n.get("color", "red"), RED))
            src.close()
            n = len(item_labels[item_id])
            print(f"sheet: {sheet['file']}" + (f" -> stamped for {n} gate(s)" if n else " (no stamp)"))
    for m in missing:
        print(f"  WARNING: '{m}' is in scope but has no cut sheet in the library")

    # 3. Drawings
    for d in job.get("drawings", []):
        path = os.path.join(job_dir, "drawings", d["file"])
        src = fitz.open(path)
        first = len(out)
        out.insert_pdf(src)
        if d.get("label"):
            stamp_box(out[first], d.get("pos", [40, 15]), [d["label"]])
        src.close()
        print(f"drawing: {d['file']}")

    name = f"Submittal - {job['project']['name'].title()} - {job['project']['submitted'].replace('/', '-')}.pdf"
    dest = os.path.join(job_dir, name)
    out.save(dest, garbage=3, deflate=True)
    print(f"\nwrote {dest} ({len(out)} pages)")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
