#!/usr/bin/env python3
"""
Parametric gate-drawing generator.

compute(params) builds a to-scale elevation as a list of primitive ops
(lines / rects / texts) in PDF points, origin top-left, y-down — coordinates
that render identically as SVG (live preview) and as a vector PDF (save).
One geometry source, two renderers, so preview == PDF.

v1: slide gate, simple schematic (leaf frame, two posts, ground line,
dimensioned clear opening + gate height, auto-fit architectural scale).
"""
import fitz

# ---- sheet (ANSI A landscape, matches the submittal drawing sheets) -------
SHEET_W, SHEET_H = 792.0, 612.0
BORDER = (20, 20, 772, 592)
TITLE_TOP = 532                      # title block occupies y 532..592

# gate drawing region (leaves room for dims + title block)
REGION_X0, REGION_X1 = 110.0, 740.0  # 630 pt wide
REGION_TOP = 110.0                   # geometry is vertically centered in
REGION_BOTTOM = 460.0                # the band [REGION_TOP, REGION_BOTTOM]
AVAIL_W = REGION_X1 - REGION_X0
AVAIL_H = REGION_BOTTOM - REGION_TOP

DIM_V_X = 78.0                       # vertical (height) dimension line

# architectural scales, largest first: (label, paper inches per 1'-0")
SCALES = [
    ('1" = 1\'-0"', 1.0), ('3/4" = 1\'-0"', 0.75), ('1/2" = 1\'-0"', 0.5),
    ('3/8" = 1\'-0"', 0.375), ('1/4" = 1\'-0"', 0.25), ('3/16" = 1\'-0"', 0.1875),
    ('1/8" = 1\'-0"', 0.125), ('3/32" = 1\'-0"', 0.09375), ('1/16" = 1\'-0"', 0.0625),
]


def ft_in(inches):
    """246 -> 20'-6\"  ;  240 -> 20'-0\""""
    inches = int(round(inches))
    f, i = divmod(inches, 12)
    return f"{f}'-{i}\""


def _pick_scale(overall_w_in, overall_h_in):
    """Largest standard scale whose drawing fits the region."""
    for label, paper_per_ft in SCALES:
        ppi = paper_per_ft * 6.0     # points per real inch (paper_in/ft / 12 * 72)
        if overall_w_in * ppi <= AVAIL_W and overall_h_in * ppi <= AVAIL_H:
            return label, ppi
    label, paper_per_ft = SCALES[-1]
    return label, paper_per_ft * 6.0


def _num(params, key, default, lo, hi):
    try:
        v = float(params.get(key, default))
    except (TypeError, ValueError):
        v = default
    return max(lo, min(hi, v))


def compute(params):
    opening = _num(params, "opening_in", 240, 12, 1200)     # 1' .. 100'
    height = _num(params, "height_in", 72, 12, 240)         # 1' .. 20'
    post_w = _num(params, "post_in", 4, 2, 12)
    drive = str(params.get("drive", "cantilever")).lower()
    date = str(params.get("date", "") or "")

    clearance = 3.0
    post_h = height + 6.0
    overall_w = post_w + opening + post_w
    overall_h = max(post_h, height + clearance)

    scale_label, ppi = _pick_scale(overall_w, overall_h)

    total_w = overall_w * ppi
    total_h = overall_h * ppi
    x0 = REGION_X0 + (AVAIL_W - total_w) / 2.0
    GROUND_Y = REGION_TOP + (AVAIL_H + total_h) / 2.0   # center the band
    DIM_H_Y = GROUND_Y + 28.0                           # width dim below ground
    pw = post_w * ppi
    op = opening * ppi
    gh = height * ppi
    ph = post_h * ppi
    cl = clearance * ppi

    ops = []
    L = lambda x1, y1, x2, y2, w=0.8: ops.append(
        {"t": "line", "x1": x1, "y1": y1, "x2": x2, "y2": y2, "w": w})
    R = lambda x, y, w, h, sw=1.0: ops.append(
        {"t": "rect", "x": x, "y": y, "w": w, "h": h, "sw": sw})
    T = lambda x, y, s, size=9, anchor="start", bold=False: ops.append(
        {"t": "text", "x": x, "y": y, "s": s, "size": size, "anchor": anchor, "bold": bold})

    # sheet border + title block
    R(BORDER[0], BORDER[1], BORDER[2] - BORDER[0], BORDER[3] - BORDER[1], 1.2)
    L(BORDER[0], TITLE_TOP, BORDER[2], TITLE_TOP, 1.0)

    # posts (left + right of the clear opening)
    rx = x0 + pw + op                       # right post left edge
    R(x0, GROUND_Y - ph, pw, ph)
    R(rx, GROUND_Y - ph, pw, ph)

    # gate leaf filling the clear opening, lifted by ground clearance
    gx, gw = x0 + pw, op
    g_bot = GROUND_Y - cl
    g_top = g_bot - gh
    R(gx, g_top, gw, gh, 1.2)
    L(gx, g_bot, gx + gw, g_top, 0.7)       # single diagonal brace

    # ground line + a little earth hatch
    L(REGION_X0 - 15, GROUND_Y, REGION_X1 + 15, GROUND_Y, 1.4)
    for k in range(int(REGION_X0) - 10, int(REGION_X1) + 16, 22):
        L(k, GROUND_Y, k - 7, GROUND_Y + 7, 0.5)

    # ---- dimensions -------------------------------------------------------
    def tick(x, y):
        L(x - 3, y + 3, x + 3, y - 3, 0.8)

    # clear opening (horizontal), measured between the post inner faces
    L(gx, GROUND_Y, gx, DIM_H_Y + 6, 0.4)       # extension lines
    L(gx + gw, GROUND_Y, gx + gw, DIM_H_Y + 6, 0.4)
    L(gx, DIM_H_Y, gx + gw, DIM_H_Y, 0.6)
    tick(gx, DIM_H_Y); tick(gx + gw, DIM_H_Y)
    T((gx + gx + gw) / 2, DIM_H_Y - 5, f"CLEAR OPENING  {ft_in(opening)}", 9, "middle")

    # gate height (vertical) on the left
    L(gx, g_top, DIM_V_X - 6, g_top, 0.4)
    L(gx, g_bot, DIM_V_X - 6, g_bot, 0.4)
    L(DIM_V_X, g_top, DIM_V_X, g_bot, 0.6)
    tick(DIM_V_X, g_top); tick(DIM_V_X, g_bot)
    T(DIM_V_X - 4, (g_top + g_bot) / 2 - 2, ft_in(height), 9, "end")

    # ---- title block ------------------------------------------------------
    ty = TITLE_TOP
    L(250, ty, 250, BORDER[3], 0.8)
    L(560, ty, 560, BORDER[3], 0.8)
    T(32, ty + 24, "METRO ACCESS CONTROL", 12, "start", True)
    T(32, ty + 44, "Gate Submittal Drawing", 9)
    T(262, ty + 22, "SLIDE GATE ELEVATION", 11, "start", True)
    T(262, ty + 42, f"{drive.upper()} SLIDE GATE", 9)
    T(572, ty + 20, f"SCALE:  {scale_label}", 9)
    T(572, ty + 36, f"OPENING:  {ft_in(opening)}", 9)
    T(572, ty + 52, f"HEIGHT:  {ft_in(height)}", 9)
    if date:
        T(748, ty + 20, date, 9, "end")

    return {"ops": ops, "w": SHEET_W, "h": SHEET_H, "scale": scale_label}


# ---------------------------------------------------------------- renderers
def _esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def to_svg(drawing):
    w, h = drawing["w"], drawing["h"]
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
           f'width="100%" style="background:#fff">']
    for o in drawing["ops"]:
        if o["t"] == "line":
            out.append(f'<line x1="{o["x1"]:.2f}" y1="{o["y1"]:.2f}" '
                       f'x2="{o["x2"]:.2f}" y2="{o["y2"]:.2f}" '
                       f'stroke="#111" stroke-width="{o["w"]}"/>')
        elif o["t"] == "rect":
            out.append(f'<rect x="{o["x"]:.2f}" y="{o["y"]:.2f}" '
                       f'width="{o["w"]:.2f}" height="{o["h"]:.2f}" '
                       f'fill="none" stroke="#111" stroke-width="{o["sw"]}"/>')
        elif o["t"] == "text":
            anchor = {"start": "start", "middle": "middle", "end": "end"}[o["anchor"]]
            weight = "bold" if o.get("bold") else "normal"
            out.append(f'<text x="{o["x"]:.2f}" y="{o["y"]:.2f}" '
                       f'font-family="Segoe UI, Arial, sans-serif" font-size="{o["size"]}" '
                       f'font-weight="{weight}" text-anchor="{anchor}" fill="#111">'
                       f'{_esc(o["s"])}</text>')
    out.append("</svg>")
    return "\n".join(out)


def to_pdf(drawing, path):
    doc = fitz.open()
    page = doc.new_page(width=drawing["w"], height=drawing["h"])
    for o in drawing["ops"]:
        if o["t"] == "line":
            page.draw_line((o["x1"], o["y1"]), (o["x2"], o["y2"]),
                           color=(0.07, 0.07, 0.07), width=o["w"])
        elif o["t"] == "rect":
            page.draw_rect(fitz.Rect(o["x"], o["y"], o["x"] + o["w"], o["y"] + o["h"]),
                           color=(0.07, 0.07, 0.07), width=o["sw"])
        elif o["t"] == "text":
            font = "hebo" if o.get("bold") else "helv"
            x = o["x"]
            if o["anchor"] in ("middle", "end"):
                tw = fitz.get_text_length(o["s"], fontname=font, fontsize=o["size"])
                x -= tw / 2 if o["anchor"] == "middle" else tw
            page.insert_text((x, o["y"]), o["s"], fontname=font,
                             fontsize=o["size"], color=(0.07, 0.07, 0.07))
    doc.save(path, garbage=3, deflate=True)
    doc.close()
