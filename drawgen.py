#!/usr/bin/env python3
"""
Parametric gate-drawing generator — top-down (plan) view in Metro's house
format (A.01 EQUIPMENT / A.02 ELECTRICAL LAYOUT sheets).

The drawing = a generated BASE plan (border, SECURE/PUBLIC labels, gate +
driveway + dimensioned opening, title block) plus a list of DEVICE instances
that the user places by dragging. The server renders everything (so the live
preview matches the PDF exactly); each device symbol is emitted inside a
group tagged with its id and a translate, so the client can drag it.

Coordinates are PDF points, origin top-left, y-down — identical in SVG and
PDF. compute(params) takes params["devices"] = [{id,type,x,y}, ...]; if
absent, a default kit is seeded from the gate geometry.
"""
import base64
import math
import os

import fitz

from paths import bundled

# ---- palette --------------------------------------------------------------
INK = (0.07, 0.07, 0.07)
RED = (0.80, 0.06, 0.06)
BLUE = (0.00, 0.12, 0.74)
GREY = (0.84, 0.84, 0.86)
WHITE = (1, 1, 1)

SHEET_W, SHEET_H = 792.0, 612.0
M = 20.0
BORDER = (M, M, SHEET_W - M, SHEET_H - M)

TB_TOP = 520.0
TB_BOT = SHEET_H - M
TB_LOGO = (M, 122)
TB_ADDR = (122, 272)
TB_COLS = [
    (272, 392, "PROJECT NAME"),
    (392, 518, "SITE ADDRESS"),
    (518, 586, "DATE"),
    (586, 676, "TITLE"),
    (676, SHEET_W - M, "SHEET #"),
]
TB_HDR_Y = 538.0
ADDR_LINES = ["2617 NE COLUMBIA BLVD", "PORTLAND, OR 97211", "888.813.6772"]

AREA = (40.0, 40.0, 752.0, 506.0)
GATE_X = 470.0

SCALES = [
    ('1/4" = 1\'-0"', 0.25), ('3/16" = 1\'-0"', 0.1875), ('1/8" = 1\'-0"', 0.125),
    ('3/32" = 1\'-0"', 0.09375), ('1/16" = 1\'-0"', 0.0625), ('1/32" = 1\'-0"', 0.03125),
]

# device types: order drives the legend numbering; label is the legend text
TYPE_ORDER = ["operator", "presence_loop", "free_exit_loop", "gooseneck",
              "fire_switch", "keypad", "edge_sensor", "edge_sensor_h", "safety_eye"]
TYPE_LABEL = {
    "operator": "{model} ON CONCRETE PAD",
    "presence_loop": "PRESENCE LOOP",
    "free_exit_loop": "FREE EXIT LOOP",
    "gooseneck": "GOOSENECK PEDESTAL",
    "fire_switch": "FIRE SWITCH",
    "keypad": "ACCESS KEYPAD",
    "edge_sensor": "VERTICAL GATE EDGE SENSOR",
    "edge_sensor_h": "HORIZONTAL GATE EDGE SENSOR",
    "safety_eye": "SAFETY EYES",
}

# operator graphics by model — extend as new operators are added (vector art).
# (slug, display name); the slug selects the symbol in draw_operator().
OPERATOR_MODELS = [("csl-24ul", "CSL-24UL"), ("csw-24ul", "CSW-24UL")]
OPERATOR_NAME = dict(OPERATOR_MODELS)
DEFAULT_OP_MODEL = "csl-24ul"

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


def _pick_scale(real_h_in, avail_h):
    for label, paper_per_ft in SCALES:
        if real_h_in * paper_per_ft * 6.0 <= avail_h:
            return label, paper_per_ft * 6.0
    label, paper_per_ft = SCALES[-1]
    return label, paper_per_ft * 6.0


def _fit_lines(text, max_w, size, font="tibo", max_lines=3, min_size=5.5):
    """Word-wrap `text` to fit max_w, shrinking the font until it fits in
    max_lines. Returns (lines, size). Used for title-block cells."""
    text = str(text).strip()
    if not text:
        return [], size
    words = text.split()
    s = size
    while s >= min_size:
        lines, cur, too_long = [], "", False
        for w in words:
            trial = (cur + " " + w).strip()
            if fitz.get_text_length(trial, fontname=font, fontsize=s) <= max_w:
                cur = trial
            else:
                if cur:
                    lines.append(cur)
                cur = w
                if fitz.get_text_length(w, fontname=font, fontsize=s) > max_w:
                    too_long = True
        if cur:
            lines.append(cur)
        if not too_long and len(lines) <= max_lines:
            return lines, s
        s -= 0.5
    return lines, min_size


# --------------------------------------------------------------- compute
def compute(params):
    opening = _num(params, "opening_in", 288, 24, 1200)
    config = str(params.get("config", "double")).lower()
    title = str(params.get("title") or f"{config} slide gate").upper()
    sheet_no = str(params.get("sheet_no", "A.01"))
    sheet_title = str(params.get("sheet_title", "EQUIPMENT LAYOUT")).upper()
    project = str(params.get("project", "") or "")
    site = str(params.get("site", "") or "")
    date = str(params.get("date", "") or "")

    ops = []

    def L(x1, y1, x2, y2, w=0.8, color=INK, dash=None, cls=None):
        ops.append({"t": "line", "x1": x1, "y1": y1, "x2": x2, "y2": y2, "w": w,
                    "color": color, "dash": dash, "cls": cls})

    def R(x, y, w, h, sw=0.9, color=INK, fill=None):
        ops.append({"t": "rect", "x": x, "y": y, "w": w, "h": h, "sw": sw,
                    "color": color, "fill": fill})

    def RR(x, y, w, h, r, sw=0.9, color=INK, dash=None, fill=None):
        ops.append({"t": "rrect", "x": x, "y": y, "w": w, "h": h, "r": r, "sw": sw,
                    "color": color, "dash": dash, "fill": fill})

    def C(cx, cy, r, sw=0.9, color=INK, fill=None, cls=None):
        ops.append({"t": "circle", "cx": cx, "cy": cy, "r": r, "sw": sw,
                    "color": color, "fill": fill, "cls": cls})

    def T(x, y, s, size=9, anchor="start", bold=False, color=INK, serif=False):
        ops.append({"t": "text", "x": x, "y": y, "s": s, "size": size,
                    "anchor": anchor, "bold": bold, "color": color, "serif": serif})

    def IMG(x, y, w, h):
        ops.append({"t": "image", "x": x, "y": y, "w": w, "h": h})

    def gstart(dev_id, x, y):
        ops.append({"t": "gstart", "id": dev_id, "x": x, "y": y})

    def gend():
        ops.append({"t": "gend"})

    def HIT(x, y, w, h):
        # invisible full-footprint grab area (SVG only) so the whole device
        # is draggable, not just its stroke
        ops.append({"t": "hit", "x": x, "y": y, "w": w, "h": h})

    def HANDLE(x, y):
        # visible drag handle (SVG only, omitted from the PDF) for the arm tip
        ops.append({"t": "handle", "x": x, "y": y})

    def arrow(tx, ty, fx, fy, color=INK):
        ang = math.atan2(ty - fy, tx - fx)
        for a in (ang + 2.5, ang - 2.5):
            L(tx, ty, tx - 7 * math.cos(a), ty - 7 * math.sin(a), 0.7, color)

    # ---- border + labels ----
    R(*BORDER[:2], BORDER[2] - BORDER[0], BORDER[3] - BORDER[1], 1.3)
    T(AREA[0] + 6, 58, "(SECURE SIDE)", 15, "start", True, RED, serif=True)
    T(AREA[2] - 6, 58, "(PUBLIC SIDE)", 15, "end", True, RED, serif=True)

    # ---- gate geometry ----
    scale_label, ppi = _pick_scale(opening, 320.0)
    op_pts = opening * ppi
    cy = 232.0
    y_top = cy - op_pts / 2.0
    y_bot = cy + op_pts / 2.0
    track_top, track_bot = AREA[1] + 14, 500.0
    L(AREA[0] + 10, y_top, AREA[2] - 10, y_top, 0.8, INK, dash=1)
    L(AREA[0] + 10, y_bot, AREA[2] - 10, y_bot, 0.8, INK, dash=1)
    lw = 5.0
    L(GATE_X - lw / 2, track_top, GATE_X - lw / 2, track_bot, 1.0)
    L(GATE_X + lw / 2, track_top, GATE_X + lw / 2, track_bot, 1.0)
    L(GATE_X - lw / 2, y_top, GATE_X - lw / 2, y_bot, 1.7)
    L(GATE_X + lw / 2, y_top, GATE_X + lw / 2, y_bot, 1.7)
    dimx = GATE_X + 24
    L(GATE_X + lw / 2, y_top, dimx + 6, y_top, 0.4)
    L(GATE_X + lw / 2, y_bot, dimx + 6, y_bot, 0.4)
    L(dimx, y_top, dimx, y_bot, 0.6)
    for yy in (y_top, y_bot):
        L(dimx - 3, yy + 3, dimx + 3, yy - 3, 0.8)
    T(dimx + 8, cy + 3, f"CLEAR OPENING {ft_in(opening)}", 8, "start")

    # ---- devices (placed by the user; empty drawing by default) ----
    devices = params.get("devices") or []

    # legend keys: most devices key by type; operators key by (operator, model)
    # so different operator models get their own number + legend line.
    def op_model(d):
        return d.get("model") or DEFAULT_OP_MODEL

    def keyfor(d):
        return ("operator", op_model(d)) if d.get("type") == "operator" else d.get("type")

    entries = []   # ordered (key, base_label), following TYPE_ORDER
    for ty in TYPE_ORDER:
        dt = [d for d in devices if d.get("type") == ty]
        if not dt:
            continue
        if ty == "operator":
            seen = []
            for d in dt:
                m = op_model(d)
                if m not in seen:
                    seen.append(m)
            for m in seen:
                entries.append((("operator", m),
                                OPERATOR_NAME.get(m, m.upper()) + " ON CONCRETE PAD"))
        else:
            entries.append((ty, TYPE_LABEL[ty]))
    num_of = {k: i + 1 for i, (k, _) in enumerate(entries)}

    def draw_operator(mdl, adx, ady):
        if mdl == "csw-24ul":            # CSW24UL swing-gate operator (cabinet + arm)
            HIT(-20, -18, 40, 38)
            R(-18, -16, 34, 30, 1.1, INK, fill=GREY)               # cabinet
            L(0, 0, adx, ady, 3.5, INK, cls="arm-line")            # swing arm (movable)
            C(adx, ady, 3.5, 0.9, INK, fill=WHITE, cls="arm-brk")  # arm bracket / gate pivot
            C(0, 0, 8, 0.9, INK, fill=WHITE)                       # gearbox
            C(0, 0, 3, 0.7, INK, fill=GREY)                        # output shaft
            HANDLE(adx, ady)                                       # drag handle (preview only)
            return (-24, 24)
        # CSL-24UL (default). Add `elif mdl == "<slug>"` branches for new models.
        HIT(-23, -23, 46, 46)
        RR(-21, -21, 42, 42, 6, 1.2, INK, fill=GREY)        # housing footprint
        RR(-16, -16, 32, 32, 5, 0.8, INK, fill=WHITE)       # recessed top
        RR(-12, -12, 24, 24, 4, 0.7, INK, fill=GREY)        # cover / lid
        R(-5, -24, 10, 4, 0.7, INK, fill=GREY)              # drive housing tab
        return (-32, -30)

    # symbol drawn at LOCAL origin (0,0); returns the bubble offset (dx,dy)
    def draw_symbol(d):
        t = d.get("type")
        if t == "operator":
            return draw_operator(op_model(d), float(d.get("arm_dx", 38)), float(d.get("arm_dy", -30)))
        if t in ("presence_loop", "free_exit_loop"):
            HIT(-27, -60, 54, 120)
            RR(-27, -60, 54, 120, 14, 1.0, RED, dash=1)
            return (40, -54)
        if t == "gooseneck":             # gooseneck pedestal (top view)
            HIT(-14, -20, 28, 38)
            R(-11, -18, 22, 7, 1.0, INK, GREY)      # mounting head bar
            R(-12, -11, 24, 24, 1.1, INK, WHITE)    # base plate / footing
            C(0, 1, 8, 0.9, INK, WHITE)             # post
            C(0, 1, 3, 0.7, INK, GREY)              # pole
            return (-30, 4)
        if t == "fire_switch":
            HIT(-9, -11, 18, 22)
            R(-5, -8, 10, 16, 0.8, INK, WHITE)
            L(-2, -4, 2, 0, 0.6); L(-2, 0, 2, 4, 0.6)
            return (-26, -20)
        if t == "keypad":
            HIT(-9, -11, 18, 22)
            R(-5, -8, 10, 16, 0.8, INK, WHITE)
            for gy in (-4, 0, 4):
                L(-2.5, gy, 2.5, gy, 0.4)
            return (26, -18)
        if t == "edge_sensor":               # vertical safety edge (unchanged)
            HIT(-8, -8, 16, 16)
            R(-3, -3, 6, 6, 0.8, INK, INK)
            return (22, -16)
        if t == "edge_sensor_h":             # horizontal safety edge: runs in the
            blen = max(40.0, op_pts - 16)    # gate direction, just shorter than the
            HIT(-6, -blen / 2, 12, blen)     # gate; length tracks the opening
            R(-3, -blen / 2, 6, blen, 0.9, INK, GREY)
            return (16, -blen / 2 + 10)
        if t == "safety_eye":
            HIT(-9, -9, 18, 18)
            R(-4, -4, 8, 8, 0.8, INK, INK)
            return (-22, -16)
        return (-26, -22)

    # draw symbols (in draggable groups)
    placed = []   # (key, x, y, bubble_dx, bubble_dy)
    for d in devices:
        if d.get("type") not in TYPE_LABEL:
            continue
        x, y = float(d.get("x", GATE_X)), float(d.get("y", cy))
        gstart(d.get("id", ""), x, y)
        bdx, bdy = draw_symbol(d)
        gend()
        placed.append((keyfor(d), x, y, bdx, bdy))

    # callout bubbles + leaders (absolute coords, refresh after a drag)
    for (k, x, y, bdx, bdy) in placed:
        bx, by = x + bdx, y + bdy
        L(bx, by, x, y, 0.6, INK)
        arrow(x, y, bx, by)
        C(bx, by, 9, 0.9, INK, WHITE)
        T(bx, by + 3.2, str(num_of[k]), 9, "middle", True, INK)

    # legend (bottom-left)
    counts = {}
    for d in devices:
        if d.get("type") in TYPE_LABEL:
            kk = keyfor(d)
            counts[kk] = counts.get(kk, 0) + 1
    lx, ly = AREA[0] + 8, 414.0
    for (k, label) in entries:
        if counts.get(k, 0) > 1:
            label = f"{label}  (x{counts[k]})"
        C(lx + 8, ly - 3, 7.5, 0.9, INK, WHITE)
        T(lx + 8, ly, str(num_of[k]), 8, "middle", True, INK)
        T(lx + 22, ly, label, 8.5, "start", False, BLUE)
        ly += 13

    # ---- title block ----
    L(BORDER[0], TB_TOP, BORDER[2], TB_TOP, 1.1)
    for x in (TB_LOGO[1], TB_ADDR[1], *[c[1] for c in TB_COLS[:-1]]):
        L(x, TB_TOP, x, TB_BOT, 0.9)
    L(TB_COLS[0][0], TB_HDR_Y, BORDER[2], TB_HDR_Y, 0.7)
    if _LOGO_B64 is not None:
        lw2, lh2 = 92.0, 54.0
        IMG(TB_LOGO[0] + (TB_LOGO[1] - TB_LOGO[0] - lw2) / 2,
            (TB_TOP + TB_BOT) / 2 - lh2 / 2, lw2, lh2)
    addr_cx = (TB_ADDR[0] + TB_ADDR[1]) / 2
    ay = TB_TOP + 22
    for line in ADDR_LINES:
        T(addr_cx, ay, line, 9, "middle", True, INK, serif=True)
        ay += 14
    values = {"PROJECT NAME": [project],
              "SITE ADDRESS": [site],
              "DATE": [date],
              "TITLE": [title],
              "SHEET #": [sheet_no, sheet_title]}
    for x0, x1, header in TB_COLS:
        cx = (x0 + x1) / 2
        T(cx, TB_TOP + 13, header, 9, "middle", True, INK, serif=True)
        # fit each value segment to the column width (wrap + shrink), stacked
        drawn = []
        for seg in values.get(header, []):
            lines, sz = _fit_lines(seg, (x1 - x0) - 8, 9)
            drawn.extend((ln, sz) for ln in lines)
        lead = 11.0
        y0 = (TB_HDR_Y + TB_BOT) / 2 - len(drawn) * lead / 2 + 8
        for i, (ln, sz) in enumerate(drawn):
            T(cx, y0 + i * lead, ln, sz, "middle", True, INK, serif=True)

    return {"ops": ops, "w": SHEET_W, "h": SHEET_H, "scale": scale_label,
            "devices": devices}


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
        t = o["t"]
        if t == "gstart":
            out.append(f'<g class="dev" data-id="{_esc(str(o["id"]))}" '
                       f'transform="translate({o["x"]:.2f},{o["y"]:.2f})">')
        elif t == "gend":
            out.append("</g>")
        elif t == "hit":
            out.append(f'<rect x="{o["x"]:.2f}" y="{o["y"]:.2f}" width="{o["w"]:.2f}" '
                       f'height="{o["h"]:.2f}" fill="none" stroke="none" pointer-events="all"/>')
        elif t == "handle":
            # large, translucent, easy-to-grab drag dot (preview only)
            out.append(f'<circle class="arm-handle" cx="{o["x"]:.2f}" cy="{o["y"]:.2f}" r="12" '
                       f'fill="#2433e0" fill-opacity="0.30" stroke="#2433e0" stroke-width="1.6" '
                       f'pointer-events="all"/>')
        elif t == "line":
            dash = ' stroke-dasharray="6 4"' if o.get("dash") else ""
            cls = f' class="{o["cls"]}"' if o.get("cls") else ""
            out.append(f'<line x1="{o["x1"]:.2f}" y1="{o["y1"]:.2f}" x2="{o["x2"]:.2f}" '
                       f'y2="{o["y2"]:.2f}" stroke="{_hex(o["color"])}" stroke-width="{o["w"]}"{dash}{cls}/>')
        elif t == "rect":
            fill = _hex(o["fill"]) if o.get("fill") else "none"
            out.append(f'<rect x="{o["x"]:.2f}" y="{o["y"]:.2f}" width="{o["w"]:.2f}" '
                       f'height="{o["h"]:.2f}" fill="{fill}" stroke="{_hex(o["color"])}" stroke-width="{o["sw"]}"/>')
        elif t == "rrect":
            fill = _hex(o["fill"]) if o.get("fill") else "none"
            dash = ' stroke-dasharray="6 4"' if o.get("dash") else ""
            out.append(f'<rect x="{o["x"]:.2f}" y="{o["y"]:.2f}" width="{o["w"]:.2f}" '
                       f'height="{o["h"]:.2f}" rx="{o["r"]}" ry="{o["r"]}" fill="{fill}" '
                       f'stroke="{_hex(o["color"])}" stroke-width="{o["sw"]}"{dash}/>')
        elif t == "circle":
            fill = _hex(o["fill"]) if o.get("fill") else "none"
            cls = f' class="{o["cls"]}"' if o.get("cls") else ""
            out.append(f'<circle cx="{o["cx"]:.2f}" cy="{o["cy"]:.2f}" r="{o["r"]}" '
                       f'fill="{fill}" stroke="{_hex(o["color"])}" stroke-width="{o["sw"]}"{cls}/>')
        elif t == "text":
            fam = "Georgia, 'Times New Roman', serif" if o.get("serif") else "Segoe UI, Arial, sans-serif"
            weight = "bold" if o.get("bold") else "normal"
            out.append(f'<text x="{o["x"]:.2f}" y="{o["y"]:.2f}" font-family="{fam}" '
                       f'font-size="{o["size"]}" font-weight="{weight}" text-anchor="{o["anchor"]}" '
                       f'fill="{_hex(o["color"])}">{_esc(o["s"])}</text>')
        elif t == "image" and _LOGO_B64:
            out.append(f'<image x="{o["x"]:.2f}" y="{o["y"]:.2f}" width="{o["w"]:.2f}" '
                       f'height="{o["h"]:.2f}" href="{_LOGO_B64}"/>')
    out.append("</svg>")
    return "\n".join(out)


def _pdf_rrect(page, o, ox, oy):
    x, y, w, h, r = o["x"] + ox, o["y"] + oy, o["w"], o["h"], o["r"]
    k = r * 0.5523
    sh = page.new_shape()
    sh.draw_line((x + r, y), (x + w - r, y))
    sh.draw_bezier((x + w - r, y), (x + w - r + k, y), (x + w, y + r - k), (x + w, y + r))
    sh.draw_line((x + w, y + r), (x + w, y + h - r))
    sh.draw_bezier((x + w, y + h - r), (x + w, y + h - r + k), (x + w - r + k, y + h), (x + w - r, y + h))
    sh.draw_line((x + w - r, y + h), (x + r, y + h))
    sh.draw_bezier((x + r, y + h), (x + r - k, y + h), (x, y + h - r + k), (x, y + h - r))
    sh.draw_line((x, y + h - r), (x, y + r))
    sh.draw_bezier((x, y + r), (x, y + r - k), (x + r - k, y), (x + r, y))
    sh.finish(color=o["color"], width=o["sw"], fill=o.get("fill"),
              dashes="[6 4] 0" if o.get("dash") else None)
    sh.commit()


def to_pdf(drawing, path):
    doc = fitz.open()
    page = doc.new_page(width=drawing["w"], height=drawing["h"])
    ox = oy = 0.0
    for o in drawing["ops"]:
        t = o["t"]
        if t == "gstart":
            ox, oy = o["x"], o["y"]
            continue
        if t == "gend":
            ox = oy = 0.0
            continue
        if t in ("hit", "handle"):
            continue                      # SVG-only UI affordances; not in the PDF
        if t == "line":
            page.draw_line((o["x1"] + ox, o["y1"] + oy), (o["x2"] + ox, o["y2"] + oy),
                           color=o["color"], width=o["w"],
                           dashes="[6 4] 0" if o.get("dash") else None)
        elif t == "rect":
            page.draw_rect(fitz.Rect(o["x"] + ox, o["y"] + oy, o["x"] + ox + o["w"], o["y"] + oy + o["h"]),
                           color=o["color"], fill=o.get("fill"), width=o["sw"])
        elif t == "rrect":
            _pdf_rrect(page, o, ox, oy)
        elif t == "circle":
            page.draw_circle((o["cx"] + ox, o["cy"] + oy), o["r"], color=o["color"],
                             fill=o.get("fill"), width=o["sw"])
        elif t == "text":
            font = ("tibo" if o.get("bold") else "tiro") if o.get("serif") else \
                   ("hebo" if o.get("bold") else "helv")
            x = o["x"] + ox
            if o["anchor"] in ("middle", "end"):
                tw = fitz.get_text_length(o["s"], fontname=font, fontsize=o["size"])
                x -= tw / 2 if o["anchor"] == "middle" else tw
            page.insert_text((x, o["y"] + oy), o["s"], fontname=font,
                             fontsize=o["size"], color=o["color"])
        elif t == "image" and os.path.isfile(_LOGO_PATH):
            page.insert_image(fitz.Rect(o["x"] + ox, o["y"] + oy, o["x"] + ox + o["w"], o["y"] + oy + o["h"]),
                              filename=_LOGO_PATH)
    doc.save(path, garbage=3, deflate=True)
    doc.close()
