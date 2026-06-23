#!/usr/bin/env python3
"""
Parametric gate-drawing generator — top-down (plan) view in Metro's house
format (matches the A.01 EQUIPMENT / A.02 ELECTRICAL LAYOUT sheets).

compute(params) builds the drawing once as primitive ops (lines / rects /
circles / rounded-rects / text / image) in PDF points, origin top-left,
y-down — coordinates that render identically as SVG (live preview) and as a
vector PDF (save), so preview == PDF.
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

# ---- sheet (ANSI A landscape) ---------------------------------------------
SHEET_W, SHEET_H = 792.0, 612.0
M = 20.0
BORDER = (M, M, SHEET_W - M, SHEET_H - M)

# title block (bottom strip)
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

# drawing region
AREA = (40.0, 40.0, 752.0, 506.0)
GATE_X = 470.0

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


# default equipment kit (matches the A.01 example); UI overrides via params
DEFAULT_EQUIP = {
    "operator_model": "CSL-24UL",
    "presence_loops": 2,
    "free_exit_loop": True,
    "gooseneck": True,
    "fire_switch": True,
    "keypad": True,
    "edge_sensors": 6,
    "safety_eyes": True,
}


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
    eq = dict(DEFAULT_EQUIP)
    eq.update(params.get("equipment") or {})

    ops = []

    def L(x1, y1, x2, y2, w=0.8, color=INK, dash=None):
        ops.append({"t": "line", "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                    "w": w, "color": color, "dash": dash})

    def R(x, y, w, h, sw=0.9, color=INK, fill=None):
        ops.append({"t": "rect", "x": x, "y": y, "w": w, "h": h,
                    "sw": sw, "color": color, "fill": fill})

    def RR(x, y, w, h, r, sw=0.9, color=INK, dash=None, fill=None):
        ops.append({"t": "rrect", "x": x, "y": y, "w": w, "h": h, "r": r,
                    "sw": sw, "color": color, "dash": dash, "fill": fill})

    def C(cx, cy, r, sw=0.9, color=INK, fill=None):
        ops.append({"t": "circle", "cx": cx, "cy": cy, "r": r,
                    "sw": sw, "color": color, "fill": fill})

    def T(x, y, s, size=9, anchor="start", bold=False, color=INK, serif=False):
        ops.append({"t": "text", "x": x, "y": y, "s": s, "size": size,
                    "anchor": anchor, "bold": bold, "color": color, "serif": serif})

    def IMG(x, y, w, h):
        ops.append({"t": "image", "x": x, "y": y, "w": w, "h": h})

    def arrow(tx, ty, fx, fy, color=INK):
        """small arrowhead at (tx,ty) pointing from (fx,fy)."""
        ang = math.atan2(ty - fy, tx - fx)
        for a in (ang + 2.5, ang - 2.5):
            L(tx, ty, tx - 7 * math.cos(a), ty - 7 * math.sin(a), 0.7, color)

    callouts = []   # (number, bubble_x, bubble_y, target_x, target_y)
    legend = []     # (number, label)

    def add(label, bubbles):
        """register one legend item numbered next; bubbles = list of (bx,by,tx,ty)."""
        n = len(legend) + 1
        legend.append((n, label))
        for (bx, by, tx, ty) in bubbles:
            callouts.append((n, bx, by, tx, ty))
        return n

    # ---- sheet border + side labels ----
    R(*BORDER[:2], BORDER[2] - BORDER[0], BORDER[3] - BORDER[1], 1.3)
    T(AREA[0] + 6, 58, "(SECURE SIDE)", 15, "start", True, RED, serif=True)
    T(AREA[2] - 6, 58, "(PUBLIC SIDE)", 15, "end", True, RED, serif=True)

    # ---- gate geometry (opening sits high; legend goes bottom-left) ----
    plan_avail_h = 320.0
    scale_label, ppi = _pick_scale(0, opening, 9999, plan_avail_h)
    op_pts = opening * ppi
    cy = 232.0
    y_top = cy - op_pts / 2.0
    y_bot = cy + op_pts / 2.0
    track_top = AREA[1] + 14
    track_bot = 500.0

    # driveway edge lines (dashed)
    L(AREA[0] + 10, y_top, AREA[2] - 10, y_top, 0.8, INK, dash=1)
    L(AREA[0] + 10, y_bot, AREA[2] - 10, y_bot, 0.8, INK, dash=1)

    # gate track / leaves
    lw = 5.0
    L(GATE_X - lw / 2, track_top, GATE_X - lw / 2, track_bot, 1.0)
    L(GATE_X + lw / 2, track_top, GATE_X + lw / 2, track_bot, 1.0)
    L(GATE_X - lw / 2, y_top, GATE_X - lw / 2, y_bot, 1.7)
    L(GATE_X + lw / 2, y_top, GATE_X + lw / 2, y_bot, 1.7)

    # clear-opening dimension (right of gate)
    dimx = GATE_X + 24
    L(GATE_X + lw / 2, y_top, dimx + 6, y_top, 0.4)
    L(GATE_X + lw / 2, y_bot, dimx + 6, y_bot, 0.4)
    L(dimx, y_top, dimx, y_bot, 0.6)
    for yy in (y_top, y_bot):
        L(dimx - 3, yy + 3, dimx + 3, yy - 3, 0.8)
    T(dimx + 8, cy + 3, f"CLEAR OPENING {ft_in(opening)}", 8, "start")

    # ============================ equipment ============================
    # ① operators (grey cabinets at the driveway edges, secure side)
    cab_w, cab_h = 40.0, 30.0
    def cabinet(yc):
        R(GATE_X - lw / 2 - cab_w, yc - cab_h / 2, cab_w, cab_h, 1.1, INK, GREY)
        R(GATE_X - lw / 2 - cab_w + 5, yc - cab_h / 2 + 5, cab_w - 10, cab_h - 10, 0.6, INK, WHITE)
    op_ys = [y_top, y_bot] if config == "double" else [y_top]
    for yy in op_ys:
        cabinet(yy)
    n_op = len(op_ys)
    ox = GATE_X - lw / 2 - cab_w
    add(f"{eq['operator_model']} ON CONCRETE PAD" + (f"  (x{n_op})" if n_op > 1 else ""),
        [(ox - 26, op_ys[0] - 24, ox + 4, op_ys[0] - cab_h / 2 + 4)])

    # loops as red dashed rounded rectangles spanning the driveway
    loop_h = max(40.0, (y_bot - y_top) - 20)
    loop_y = (y_top + y_bot) / 2 - loop_h / 2
    loop_w = 54.0

    def loop(cx):
        RR(cx - loop_w / 2, loop_y, loop_w, loop_h, 14, 1.0, RED, dash=1)

    # ② presence loops (public + secure)
    pl = int(eq.get("presence_loops", 0) or 0)
    if pl >= 1:
        bubbles = []
        xs = []
        if pl >= 1:
            xs.append(GATE_X + 95)              # public side
        if pl >= 2:
            xs.append(GATE_X - 120)             # secure side
        for cx in xs:
            loop(cx)
            bubbles.append((cx + loop_w / 2 + 26, loop_y - 14, cx + loop_w / 2, loop_y + 12))
        add(f"PRESENCE LOOP  (x{pl})", bubbles)

    # ③ free exit loop (secure side, inner)
    if eq.get("free_exit_loop"):
        cx = GATE_X - 232
        loop(cx)
        add("FREE EXIT LOOP",
            [(cx - loop_w / 2 - 26, loop_y - 14, cx - loop_w / 2, loop_y + 12)])

    # gooseneck pedestal w/ keypad + fire switch (public side, below drive)
    ped_x, ped_y = GATE_X + 150, y_bot + 46
    if eq.get("gooseneck") or eq.get("keypad") or eq.get("fire_switch"):
        R(ped_x - 5, ped_y, 10, 40, 1.0, INK, GREY)        # post
        R(ped_x - 14, ped_y - 22, 28, 22, 1.0, INK, WHITE)  # head/enclosure
        T(ped_x, ped_y + 60, "6' MINIMUM AWAY FROM", 7, "middle", False, RED)
        T(ped_x, ped_y + 70, "MOVING PARTS OF GATE", 7, "middle", False, RED)
    if eq.get("gooseneck"):
        add("GOOSENECK PEDESTAL",
            [(ped_x - 40, ped_y + 30, ped_x - 5, ped_y + 20)])
    if eq.get("fire_switch"):
        R(ped_x - 10, ped_y - 18, 8, 14, 0.7, INK, WHITE)
        add("FIRE SWITCH", [(ped_x + 36, ped_y - 22, ped_x + 2, ped_y - 12)])
    if eq.get("keypad"):
        R(ped_x + 2, ped_y - 18, 8, 14, 0.7, INK, WHITE)
        add("ACCESS KEYPAD", [(ped_x + 36, ped_y - 6, ped_x + 10, ped_y - 8)])

    # ⑦ gate edge contact sensors (small ticks along the closed gate leaves)
    ec = int(eq.get("edge_sensors", 0) or 0)
    if ec >= 1:
        step = (y_bot - y_top) / (ec + 1)
        for i in range(1, ec + 1):
            yy = y_top + step * i
            L(GATE_X + lw / 2, yy, GATE_X + lw / 2 + 6, yy, 1.2, INK)
        add(f"GATE EDGE CONTACT SENSORS  (x{ec})",
            [(GATE_X + 70, y_top + 30, GATE_X + lw / 2 + 6, y_top + step)])

    # ⑧ safety eyes (photo-eye pair across the opening, near the gate posts)
    if eq.get("safety_eyes"):
        for yy in (y_top, y_bot):
            R(GATE_X - lw / 2 - 9, yy - 4, 7, 8, 0.8, INK, INK)
        add("SAFETY EYES",
            [(GATE_X - 60, y_top + 18, GATE_X - lw / 2 - 9, y_top)])

    # ---- draw callouts (bubbles + leaders) ----
    for (n, bx, by, tx, ty) in callouts:
        L(bx, by, tx, ty, 0.6, INK)
        arrow(tx, ty, bx, by)
        C(bx, by, 9, 0.9, INK, WHITE)
        T(bx, by + 3.2, str(n), 9, "middle", True, INK)

    # ---- legend (bottom-left) ----
    lx, ly = AREA[0] + 8, 412.0
    for (n, label) in legend:
        C(lx + 8, ly - 3, 7.5, 0.9, INK, WHITE)
        T(lx + 8, ly, str(n), 8, "middle", True, INK)
        T(lx + 22, ly, label, 8.5, "start", False, BLUE)
        ly += 13

    # ============================ title block ============================
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

    tparts = title.split()
    tvalue = [tparts[0], " ".join(tparts[1:])] if len(tparts) > 1 else tparts
    values = {"PROJECT NAME": [project] if project else [],
              "SITE ADDRESS": [site] if site else [],
              "DATE": [date] if date else [],
              "TITLE": tvalue,
              "SHEET #": [sheet_no, sheet_title]}
    for x0, x1, header in TB_COLS:
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
        t = o["t"]
        if t == "line":
            dash = ' stroke-dasharray="6 4"' if o.get("dash") else ""
            out.append(f'<line x1="{o["x1"]:.2f}" y1="{o["y1"]:.2f}" x2="{o["x2"]:.2f}" '
                       f'y2="{o["y2"]:.2f}" stroke="{_hex(o["color"])}" stroke-width="{o["w"]}"{dash}/>')
        elif t == "rect":
            fill = _hex(o["fill"]) if o.get("fill") else "none"
            out.append(f'<rect x="{o["x"]:.2f}" y="{o["y"]:.2f}" width="{o["w"]:.2f}" '
                       f'height="{o["h"]:.2f}" fill="{fill}" stroke="{_hex(o["color"])}" '
                       f'stroke-width="{o["sw"]}"/>')
        elif t == "rrect":
            fill = _hex(o["fill"]) if o.get("fill") else "none"
            dash = ' stroke-dasharray="6 4"' if o.get("dash") else ""
            out.append(f'<rect x="{o["x"]:.2f}" y="{o["y"]:.2f}" width="{o["w"]:.2f}" '
                       f'height="{o["h"]:.2f}" rx="{o["r"]}" ry="{o["r"]}" fill="{fill}" '
                       f'stroke="{_hex(o["color"])}" stroke-width="{o["sw"]}"{dash}/>')
        elif t == "circle":
            fill = _hex(o["fill"]) if o.get("fill") else "none"
            out.append(f'<circle cx="{o["cx"]:.2f}" cy="{o["cy"]:.2f}" r="{o["r"]}" '
                       f'fill="{fill}" stroke="{_hex(o["color"])}" stroke-width="{o["sw"]}"/>')
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


def _pdf_rrect(page, o):
    x, y, w, h, r = o["x"], o["y"], o["w"], o["h"], o["r"]
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
    for o in drawing["ops"]:
        t = o["t"]
        if t == "line":
            page.draw_line((o["x1"], o["y1"]), (o["x2"], o["y2"]),
                           color=o["color"], width=o["w"],
                           dashes="[6 4] 0" if o.get("dash") else None)
        elif t == "rect":
            page.draw_rect(fitz.Rect(o["x"], o["y"], o["x"] + o["w"], o["y"] + o["h"]),
                           color=o["color"], fill=o.get("fill"), width=o["sw"])
        elif t == "rrect":
            _pdf_rrect(page, o)
        elif t == "circle":
            page.draw_circle((o["cx"], o["cy"]), o["r"], color=o["color"],
                             fill=o.get("fill"), width=o["sw"])
        elif t == "text":
            font = ("tibo" if o.get("bold") else "tiro") if o.get("serif") else \
                   ("hebo" if o.get("bold") else "helv")
            x = o["x"]
            if o["anchor"] in ("middle", "end"):
                tw = fitz.get_text_length(o["s"], fontname=font, fontsize=o["size"])
                x -= tw / 2 if o["anchor"] == "middle" else tw
            page.insert_text((x, o["y"]), o["s"], fontname=font,
                             fontsize=o["size"], color=o["color"])
        elif t == "image" and os.path.isfile(_LOGO_PATH):
            page.insert_image(fitz.Rect(o["x"], o["y"], o["x"] + o["w"], o["y"] + o["h"]),
                              filename=_LOGO_PATH)
    doc.save(path, garbage=3, deflate=True)
    doc.close()
