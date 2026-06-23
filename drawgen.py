#!/usr/bin/env python3
"""
Parametric gate-drawing generator — top-down (plan) view in Metro's house
format (matches the A.01 EQUIPMENT / A.02 ELECTRICAL LAYOUT sheets).

compute(params) builds the drawing once as primitive ops (lines / rects /
text / images) in PDF points, origin top-left, y-down — coordinates that
render identically as SVG (live preview) and as a vector PDF (save), so
preview == PDF.

Stage 1: sheet border, title block (with logo), SECURE/PUBLIC labels, and
the base slide gate in plan with operators + driveway edges. Loops, numbered
callouts, legend, and the electrical overlay come next.
"""
import base64
import os

import fitz

from paths import bundled

# ---- palette --------------------------------------------------------------
INK = (0.07, 0.07, 0.07)
RED = (0.80, 0.06, 0.06)
BLUE = (0.00, 0.12, 0.74)
GREY = (0.84, 0.84, 0.86)

# ---- sheet (ANSI A landscape) ---------------------------------------------
SHEET_W, SHEET_H = 792.0, 612.0
M = 20.0
BORDER = (M, M, SHEET_W - M, SHEET_H - M)

# title block (bottom strip)
TB_TOP = 520.0
TB_BOT = SHEET_H - M           # 592
# column x-edges across the title block
TB_LOGO = (M, 122)
TB_ADDR = (122, 272)
TB_COLS = [                    # (x0, x1, header, value-lines)
    (272, 392, "PROJECT NAME", []),
    (392, 518, "SITE ADDRESS", []),
    (518, 586, "DATE", []),
    (586, 676, "TITLE", ["DOUBLE", "SLIDE GATE"]),
    (676, SHEET_W - M, "SHEET #", ["A.01", "EQUIPMENT LAYOUT"]),
]
TB_HDR_Y = 538.0               # divider between header labels and values

# drawing region (above the title block)
AREA = (40.0, 40.0, 752.0, 506.0)

ADDR_LINES = ["2617 NE COLUMBIA BLVD", "PORTLAND, OR 97211", "888.813.6772"]

# architectural scales, largest first: (label, paper inches per 1'-0")
SCALES = [
    ('1/4" = 1\'-0"', 0.25), ('3/16" = 1\'-0"', 0.1875), ('1/8" = 1\'-0"', 0.125),
    ('3/32" = 1\'-0"', 0.09375), ('1/16" = 1\'-0"', 0.0625), ('1/32" = 1\'-0"', 0.03125),
]

_LOGO_PATH = bundled("assets", "metro-logo.png")
try:
    with open(_LOGO_PATH, "rb") as f:
        _LOGO_B64 = "data:image/png;base64," + base64.b64encode(f.read()).decode()
except Exception:
    _LOGO_B64 = None


def ft_in(inches):
    inches = int(round(inches))
    f, i = divmod(inches, 12)
    return f"{f}'-{i}\"" if i else f"{f}'"


def _num(params, key, default, lo, hi):
    try:
        v = float(params.get(key, default))
    except (TypeError, ValueError):
        v = default
    return max(lo, min(hi, v))


def _pick_scale(real_w_in, real_h_in, avail_w, avail_h):
    for label, paper_per_ft in SCALES:
        ppi = paper_per_ft * 6.0
        if real_w_in * ppi <= avail_w and real_h_in * ppi <= avail_h:
            return label, ppi
    label, paper_per_ft = SCALES[-1]
    return label, paper_per_ft * 6.0


# --------------------------------------------------------------- compute
def compute(params):
    opening = _num(params, "opening_in", 288, 24, 1200)     # clear opening (drive width)
    config = str(params.get("config", "double")).lower()
    title = str(params.get("title") or f"{config} slide gate").upper()
    sheet_no = str(params.get("sheet_no", "A.01"))
    sheet_title = str(params.get("sheet_title", "EQUIPMENT LAYOUT")).upper()
    project = str(params.get("project", "") or "")
    site = str(params.get("site", "") or "")
    date = str(params.get("date", "") or "")

    ops = []

    def L(x1, y1, x2, y2, w=0.8, color=INK, dash=None):
        ops.append({"t": "line", "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                    "w": w, "color": color, "dash": dash})

    def R(x, y, w, h, sw=0.9, color=INK, fill=None):
        ops.append({"t": "rect", "x": x, "y": y, "w": w, "h": h,
                    "sw": sw, "color": color, "fill": fill})

    def T(x, y, s, size=9, anchor="start", bold=False, color=INK, serif=False):
        ops.append({"t": "text", "x": x, "y": y, "s": s, "size": size,
                    "anchor": anchor, "bold": bold, "color": color, "serif": serif})

    def IMG(x, y, w, h):
        ops.append({"t": "image", "x": x, "y": y, "w": w, "h": h})

    # ---- sheet border ----
    R(*BORDER[:2], BORDER[2] - BORDER[0], BORDER[3] - BORDER[1], 1.3)

    # ---- SECURE / PUBLIC labels ----
    T(AREA[0] + 6, 58, "(SECURE SIDE)", 15, "start", True, RED, serif=True)
    T(AREA[2] - 6, 58, "(PUBLIC SIDE)", 15, "end", True, RED, serif=True)

    # ======================= base plan: slide gate =======================
    # Driveway runs left<->right; the gate is a vertical barrier in the
    # center. The track runs nearly full height (leaves retract along it);
    # operators sit at the driveway edges (the fence line) on the secure side.
    plan_avail_h = 340.0
    scale_label, ppi = _pick_scale(0, opening, 9999, plan_avail_h)

    gate_x = 470.0
    cy = (AREA[1] + 14 + AREA[3] - 14) / 2.0       # center of plan area
    op_pts = opening * ppi
    y_top = cy - op_pts / 2.0                       # driveway edge (top)
    y_bot = cy + op_pts / 2.0                       # driveway edge (bottom)
    track_top = AREA[1] + 14
    track_bot = AREA[3] - 14

    # driveway edge lines (dashed), extending across the drive
    L(AREA[0] + 10, y_top, AREA[2] - 10, y_top, 0.8, INK, dash="dash")
    L(AREA[0] + 10, y_bot, AREA[2] - 10, y_bot, 0.8, INK, dash="dash")

    # gate track / leaves: a double line down the center (full-height track,
    # heavier within the closed opening)
    leaf_w = 5.0
    L(gate_x - leaf_w / 2, track_top, gate_x - leaf_w / 2, track_bot, 1.0)
    L(gate_x + leaf_w / 2, track_top, gate_x + leaf_w / 2, track_bot, 1.0)
    L(gate_x - leaf_w / 2, y_top, gate_x - leaf_w / 2, y_bot, 1.7)
    L(gate_x + leaf_w / 2, y_top, gate_x + leaf_w / 2, y_bot, 1.7)

    # operators (grey cabinets) at the driveway edges, on the secure side
    cab_w, cab_h = 40.0, 30.0
    def cabinet(yc):
        R(gate_x - leaf_w / 2 - cab_w, yc - cab_h / 2, cab_w, cab_h, 1.1, INK, GREY)
        R(gate_x - leaf_w / 2 - cab_w + 5, yc - cab_h / 2 + 5, cab_w - 10, cab_h - 10, 0.6, INK, (1, 1, 1))
    cabinet(y_top)
    if config == "double":
        cabinet(y_bot)

    # clear-opening dimension (vertical), to the right of the gate
    dimx = gate_x + 26
    L(gate_x + leaf_w / 2, y_top, dimx + 6, y_top, 0.4)
    L(gate_x + leaf_w / 2, y_bot, dimx + 6, y_bot, 0.4)
    L(dimx, y_top, dimx, y_bot, 0.6)
    for yy in (y_top, y_bot):
        L(dimx - 3, yy + 3, dimx + 3, yy - 3, 0.8)
    T(dimx + 8, (y_top + y_bot) / 2 + 3, f"CLEAR OPENING {ft_in(opening)}", 8, "start")

    # ============================ title block ============================
    L(BORDER[0], TB_TOP, BORDER[2], TB_TOP, 1.1)
    for x in (TB_LOGO[1], TB_ADDR[1], *[c[1] for c in TB_COLS[:-1]]):
        L(x, TB_TOP, x, TB_BOT, 0.9)
    L(TB_COLS[0][0], TB_HDR_Y, BORDER[2], TB_HDR_Y, 0.7)   # header/value divider

    if _LOGO_B64 is not None:
        lw, lh = 92.0, 54.0
        IMG(TB_LOGO[0] + (TB_LOGO[1] - TB_LOGO[0] - lw) / 2,
            (TB_TOP + TB_BOT) / 2 - lh / 2, lw, lh)
    addr_cx = (TB_ADDR[0] + TB_ADDR[1]) / 2
    ay = TB_TOP + 22
    for line in ADDR_LINES:
        T(addr_cx, ay, line, 9, "middle", True, INK, serif=True)
        ay += 14

    values = {"PROJECT NAME": [project] if project else [],
              "SITE ADDRESS": [site] if site else [],
              "DATE": [date] if date else [],
              "TITLE": title.split(" ", 1) if title else [],
              "SHEET #": [sheet_no, sheet_title]}
    # nicer TITLE wrap: "DOUBLE SLIDE GATE" -> ["DOUBLE","SLIDE GATE"]
    if title:
        parts = title.split()
        values["TITLE"] = [parts[0], " ".join(parts[1:])] if len(parts) > 1 else parts
    for x0, x1, header, _ in TB_COLS:
        cx = (x0 + x1) / 2
        T(cx, TB_TOP + 13, header, 9, "middle", True, INK, serif=True)
        vlines = values.get(header, [])
        vsize = 9 if len(vlines) <= 1 else 8
        for i, ln in enumerate(vlines):
            T(cx, TB_HDR_Y + 16 + i * 14, ln, vsize, "middle", True, INK, serif=True)

    return {"ops": ops, "w": SHEET_W, "h": SHEET_H, "scale": scale_label}


# --------------------------------------------------------------- renderers
def _hex(c):
    return "#%02x%02x%02x" % tuple(int(round(v * 255)) for v in c)


def _esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def to_svg(drawing):
    w, h = drawing["w"], drawing["h"]
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
           f'width="100%" style="background:#fff">']
    for o in drawing["ops"]:
        if o["t"] == "line":
            dash = ' stroke-dasharray="6 4"' if o.get("dash") else ""
            out.append(f'<line x1="{o["x1"]:.2f}" y1="{o["y1"]:.2f}" x2="{o["x2"]:.2f}" '
                       f'y2="{o["y2"]:.2f}" stroke="{_hex(o["color"])}" '
                       f'stroke-width="{o["w"]}"{dash}/>')
        elif o["t"] == "rect":
            fill = _hex(o["fill"]) if o.get("fill") else "none"
            out.append(f'<rect x="{o["x"]:.2f}" y="{o["y"]:.2f}" width="{o["w"]:.2f}" '
                       f'height="{o["h"]:.2f}" fill="{fill}" stroke="{_hex(o["color"])}" '
                       f'stroke-width="{o["sw"]}"/>')
        elif o["t"] == "text":
            fam = "Georgia, 'Times New Roman', serif" if o.get("serif") else "Segoe UI, Arial, sans-serif"
            weight = "bold" if o.get("bold") else "normal"
            out.append(f'<text x="{o["x"]:.2f}" y="{o["y"]:.2f}" font-family="{fam}" '
                       f'font-size="{o["size"]}" font-weight="{weight}" '
                       f'text-anchor="{o["anchor"]}" fill="{_hex(o["color"])}">{_esc(o["s"])}</text>')
        elif o["t"] == "image" and _LOGO_B64:
            out.append(f'<image x="{o["x"]:.2f}" y="{o["y"]:.2f}" width="{o["w"]:.2f}" '
                       f'height="{o["h"]:.2f}" href="{_LOGO_B64}"/>')
    out.append("</svg>")
    return "\n".join(out)


def to_pdf(drawing, path):
    doc = fitz.open()
    page = doc.new_page(width=drawing["w"], height=drawing["h"])
    for o in drawing["ops"]:
        if o["t"] == "line":
            page.draw_line((o["x1"], o["y1"]), (o["x2"], o["y2"]),
                           color=o["color"], width=o["w"],
                           dashes="[6 4] 0" if o.get("dash") else None)
        elif o["t"] == "rect":
            page.draw_rect(fitz.Rect(o["x"], o["y"], o["x"] + o["w"], o["y"] + o["h"]),
                           color=o["color"], fill=o.get("fill"), width=o["sw"])
        elif o["t"] == "text":
            font = ("tibo" if o.get("bold") else "tiro") if o.get("serif") else \
                   ("hebo" if o.get("bold") else "helv")
            x = o["x"]
            if o["anchor"] in ("middle", "end"):
                tw = fitz.get_text_length(o["s"], fontname=font, fontsize=o["size"])
                x -= tw / 2 if o["anchor"] == "middle" else tw
            page.insert_text((x, o["y"]), o["s"], fontname=font,
                             fontsize=o["size"], color=o["color"])
        elif o["t"] == "image" and os.path.isfile(_LOGO_PATH):
            page.insert_image(fitz.Rect(o["x"], o["y"], o["x"] + o["w"], o["y"] + o["h"]),
                              filename=_LOGO_PATH)
    doc.save(path, garbage=3, deflate=True)
    doc.close()
