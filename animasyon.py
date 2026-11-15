"""
Merak Makinesi — 2D çizgi film animasyon motoru v2 (tamamen kodla çizilir, ücretsiz, yerel).

- Karakter kadrosu (siyah kafa, iri beyaz gözler, renkli kıyafet tarzı): hero, mom, dad, friend,
  scientist, kid, grandpa, girl, astronaut. Göz kırpma, göz kapağıyla ifade, el-kol pozları,
  yürüme, koşma, zıplama, uyuma, savrulma, dönme, titreme...
- 12 derinlikli mekân: perspektifli odalar, katmanlı manzaralar, paralaks kamera, ön plan nesneleri,
  gölgeler ve vinyet.
- Sahne başına 1-3 karakter, uzaktaki karakter küçük ve geride.

render(sahneler, cikti_mp4, ass, W, H, muzik)
sahne = {"ses_dosya", "sure", "arka_plan", "kamera", "nesne",
         "karakterler": [{"tip", "ifade", "hareket"}, ...]}
"""
import math
import os
import random
import subprocess
import tempfile

import cairo

FPS = 30
INK = (0.08, 0.08, 0.10)
SKIN = "#141414"


def hx(h, a=1.0):
    h = h.lstrip("#")
    return (int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255, a)


def mix(h1, h2, k):
    a, b = hx(h1), hx(h2)
    return tuple(a[i] + (b[i] - a[i]) * k for i in range(3)) + (1.0,)


def ease(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def lerp(a, b, t):
    return a + (b - a) * t


# ============================================================ çizim yardımcıları
def setc(c, col):
    if isinstance(col, str):
        col = hx(col)
    c.set_source_rgba(*(col if len(col) == 4 else (*col, 1)))


def fs(c, fill, lw=0, stroke=INK):
    setc(c, fill)
    if lw:
        c.fill_preserve()
        setc(c, stroke)
        c.set_line_width(lw)
        c.set_line_join(cairo.LINE_JOIN_ROUND)
        c.stroke()
    else:
        c.fill()


def poly(c, pts, fill, lw=0, stroke=INK):
    c.move_to(*pts[0])
    for p in pts[1:]:
        c.line_to(*p)
    c.close_path()
    fs(c, fill, lw, stroke)


def rrect(c, x, y, w, h, r):
    r = max(0.01, min(r, abs(w) / 2, abs(h) / 2))
    c.new_sub_path()
    c.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    c.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    c.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    c.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    c.close_path()


def ell(c, x, y, rx, ry):
    c.save()
    c.translate(x, y)
    c.scale(max(rx, 0.01), max(ry, 0.01))
    c.arc(0, 0, 1, 0, 2 * math.pi)
    c.restore()


def ln(c, pts, lw, col=INK):
    c.set_line_cap(cairo.LINE_CAP_ROUND)
    c.set_line_join(cairo.LINE_JOIN_ROUND)
    c.move_to(*pts[0])
    for p in pts[1:]:
        c.line_to(*p)
    setc(c, col)
    c.set_line_width(lw)
    c.stroke()


def vgrad(c, x, y, w, h, top, bottom):
    g = cairo.LinearGradient(0, y, 0, y + h)
    g.add_color_stop_rgba(0, *hx(top))
    g.add_color_stop_rgba(1, *hx(bottom))
    c.rectangle(x, y, w, h)
    c.set_source(g)
    c.fill()


def glow(c, x, y, r, col, a=0.5):
    g = cairo.RadialGradient(x, y, 0, x, y, r)
    g.add_color_stop_rgba(0, *hx(col, a))
    g.add_color_stop_rgba(1, *hx(col, 0))
    c.arc(x, y, r, 0, 2 * math.pi)
    c.set_source(g)
    c.fill()


def shadow(c, x, y, rx, ry, a=0.22):
    ell(c, x, y, rx, ry)
    c.set_source_rgba(0, 0, 0, a)
    c.fill()


def qpt(q, u, v):
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = q
    tx, ty = lerp(x0, x1, u), lerp(y0, y1, u)
    bx, by = lerp(x3, x2, u), lerp(y3, y2, u)
    return lerp(tx, bx, v), lerp(ty, by, v)


def subquad(q, u0, v0, u1, v1):
    return [qpt(q, u0, v0), qpt(q, u1, v0), qpt(q, u1, v1), qpt(q, u0, v1)]


class Layer:
    """Paralaks katmanı: derinlik 0 = sabit (uzak), 1 = karakter düzlemi, >1 = ön plan."""

    def __init__(self, c, pan, depth):
        self.c, self.dx = c, -pan * depth

    def __enter__(self):
        self.c.save()
        self.c.translate(self.dx, 0)

    def __exit__(self, *a):
        self.c.restore()


def box(c, front, depth_vec, fill, top_fill=None, side_fill=None, lw=3):
    """Önden görünen kutu + üst ve yan yüzey (perspektif hissi)."""
    x, y, w, h = front
    dx, dy = depth_vec
    poly(c, [(x, y), (x + w, y), (x + w + dx, y + dy), (x + dx, y + dy)], top_fill or mix(fill, "#FFFFFF", 0.25), lw)
    if dx > 0:
        poly(c, [(x + w, y), (x + w + dx, y + dy), (x + w + dx, y + h + dy), (x + w, y + h)],
             side_fill or mix(fill, "#000000", 0.2), lw)
    elif dx < 0:
        poly(c, [(x, y), (x + dx, y + dy), (x + dx, y + h + dy), (x, y + h)],
             side_fill or mix(fill, "#000000", 0.2), lw)
    rrect(c, x, y, w, h, 2)
    fs(c, fill, lw)


# ============================================================ karakter kadrosu
KARAKTERLER = {
    "hero": dict(shirt="#FFE8C2", jacket="#FF7B00", legs=SKIN, shoes="#F4F4F4", acc=None, scale=1.0),
    "mom": dict(shirt="#FFFFFF", jacket="#E56B9B", legs=SKIN, shoes="#B5179E", acc="bun", scale=0.97),
    "dad": dict(shirt="#CDE7B0", jacket="#3E6B48", legs="#2B2D42", shoes="#5C3D2E", acc="glasses", scale=1.05),
    "friend": dict(shirt="#FFFFFF", jacket="#00A6A6", legs=SKIN, shoes="#FFD166", acc="cap", scale=1.0),
    "scientist": dict(shirt="#9AD1FF", jacket="#F5F5F5", legs="#4A4E69", shoes="#2B2D42", acc="lab", scale=1.0),
    "kid": dict(shirt="#E63946", jacket=None, legs="#1D3557", shoes="#FFFFFF", acc="propeller", scale=0.72),
    "grandpa": dict(shirt="#F1E3D3", jacket="#8D6E63", legs="#5D4037", shoes="#3E2723", acc="whitehair", scale=0.95),
    "girl": dict(shirt="#FFF0F6", jacket="#7B61FF", legs=SKIN, shoes="#FF6FB5", acc="bow", scale=0.88),
    "astronaut": dict(shirt="#E9ECEF", jacket="#F8F9FA", legs="#E9ECEF", shoes="#ADB5BD", acc="helmet", scale=1.02),
}

POZLAR = {
    "idle": ((10, 6), (10, 6)),
    "explain": ((26, 55), (38, 75)),
    "wave": ((10, 6), (150, 25)),
    "point": ((10, 6), (95, 0)),
    "shrug": ((48, 100), (48, 100)),
    "hands_up": ((160, 10), (160, 10)),
    "think": ((40, -100), (-20, -150)),
    "hips": ((40, -100), (40, -100)),
    "cheer": ((135, -20), (135, -20)),
    "facepalm": ((10, 6), (-15, -160)),
    "hug": ((70, 60), (70, 60)),
}

# ifade: (göz ölçeği, göz kapağı örtüsü, kapak eğimi (+ kızgın / - üzgün), göz bebeği ölçeği, ağız)
IFADELER = {
    "neutral": (1.0, 0.18, 0.0, 1.0, "line"),
    "happy": (1.0, 0.0, 0.0, 1.0, "smile"),
    "excited": (1.12, 0.0, 0.0, 1.05, "open_smile"),
    "shocked": (1.25, 0.0, 0.0, 0.6, "o"),
    "worried": (1.05, 0.25, -0.5, 0.9, "grimace"),
    "thinking": (0.95, 0.3, -0.15, 0.95, "side"),
    "sad": (1.0, 0.3, -0.6, 1.0, "frown"),
    "angry": (0.95, 0.35, 0.7, 0.85, "grimace"),
    "smug": (0.95, 0.5, 0.15, 1.0, "smirk"),
    "scared": (1.2, 0.05, -0.4, 0.55, "grimace"),
    "sleepy": (1.0, 0.65, 0.0, 1.0, "line"),
}


def arm_pts(side, upper, elbow, sh):
    a1 = math.radians(upper)
    ex, ey = sh[0] + side * 13 * math.sin(a1), sh[1] + 13 * math.cos(a1)
    a2 = math.radians(upper + elbow)
    return [sh, (ex, ey), (ex + side * 12 * math.sin(a2), ey + 12 * math.cos(a2))]


def draw_arm(c, p, pts):
    col = p["jacket"] or p["shirt"]
    ln(c, pts, 6.6, INK)
    ln(c, pts, 4.4, col)
    ell(c, pts[2][0], pts[2][1], 3.0, 3.0)
    fs(c, "#ADB5BD" if p["acc"] == "helmet" else SKIN, 1.2 if p["acc"] == "helmet" else 0)


def draw_character(c, kind, st):
    p = KARAKTERLER[kind]
    t = st.get("t", 0)
    c.save()
    c.translate(st["x"], st["y"])
    sc = st["s"] * p["scale"]
    c.scale(sc * st["facing"], sc)
    c.rotate(math.radians(st.get("lean", 0)))
    if st.get("spin"):
        c.translate(0, -48)
        c.rotate(math.radians(st["spin"]))
        c.translate(0, 48)
    bob = st.get("bob", 0)
    lw = 1.7

    leg = st.get("leg", 0)
    for side, ph in ((-1, 1), (1, -1)):
        hip = (side * 5, -16 + bob)
        a = math.radians(leg * ph)
        foot = (hip[0] + 15 * math.sin(a), hip[1] + 15.5 * math.cos(a))
        if p["legs"] == SKIN:
            ln(c, [hip, foot], 3.4, SKIN)
        else:
            ln(c, [hip, foot], 6.2, INK)
            ln(c, [hip, foot], 4.0, p["legs"])
        ell(c, foot[0] + side * 1.5 + 1.2, foot[1] - 0.6, 4.6, 2.6)
        fs(c, p["shoes"], 1.4)

    sh_l, sh_r = (-11, -45 + bob), (11, -45 + bob)
    (ul, el), (ur, er) = st["arms"]
    draw_arm(c, p, arm_pts(-1, ul, el, sh_l))

    c.save()
    c.translate(0, bob)
    c.move_to(-10, -48)
    c.curve_to(-14, -40, -14, -24, -13, -15)
    c.line_to(13, -15)
    c.curve_to(14, -24, 14, -40, 10, -48)
    c.curve_to(4, -50, -4, -50, -10, -48)
    c.close_path()
    fs(c, p["shirt"], lw)
    if p["jacket"]:
        for side in (-1, 1):
            c.move_to(side * 3.2, -49)
            c.curve_to(side * 9, -50, side * 14, -44, side * 14.2, -36)
            c.curve_to(side * 14.5, -26, side * 14, -18, side * 13.5, -14)
            c.line_to(side * 3.6, -14)
            c.curve_to(side * 4.5, -26, side * 3.0, -40, side * 3.2, -49)
            c.close_path()
            fs(c, p["jacket"], lw)
        if p["acc"] == "lab":
            for yy in (-38, -30, -22):
                ell(c, 4.6, yy, 0.9, 0.9)
                fs(c, INK)
            rrect(c, 6.5, -30, 5, 6, 1)
            fs(c, "#DDE3EA", 1)
    if p["acc"] == "helmet":
        rrect(c, -6, -42, 12, 9, 2)
        fs(c, "#4DABF7", 1.2)
    c.restore()

    hy = -68 + bob * 1.15
    eye_s, lid, tilt, pup, mouth = IFADELER.get(st["expr"], IFADELER["neutral"])
    eo = st.get("eyes_open", 1.0)
    if p["acc"] == "bun":
        ell(c, 0, hy - 21, 7.5, 6.5)
        fs(c, "#2A2A2A", lw)
    if p["acc"] == "bow":
        for s2 in (-1, 1):
            ell(c, s2 * 15, hy - 3, 4.2, 9.5)
            fs(c, "#2A2A2A", lw)
    ell(c, 0, hy, 20.5, 19.5)
    fs(c, SKIN)
    ell(c, -8, hy - 10, 6, 3.5)
    c.set_source_rgba(1, 1, 1, 0.08)
    c.fill()
    if p["acc"] == "whitehair":
        for s2 in (-1, 1):
            ell(c, s2 * 18.5, hy - 6, 4.5, 6)
            fs(c, "#F1F3F5", 1.2)
    if p["acc"] == "cap":
        c.move_to(-19.5, hy - 5)
        c.curve_to(-18, hy - 25, 18, hy - 25, 19.5, hy - 5)
        c.close_path()
        fs(c, "#E63946", lw)
        rrect(c, 4, hy - 8, 20, 4.5, 2.2)
        fs(c, "#E63946", lw)
    if p["acc"] == "propeller":
        c.move_to(-19, hy - 6)
        c.curve_to(-17, hy - 24, 17, hy - 24, 19, hy - 6)
        c.close_path()
        fs(c, "#4361EE", lw)
        ln(c, [(0, hy - 19), (0, hy - 25)], 1.6)
        w2 = 9 * abs(math.cos(t * 14))
        ln(c, [(-w2, hy - 26), (w2, hy - 26)], 2.6, "#FFD60A")
    if p["acc"] == "bow":
        for s2 in (-1, 1):
            poly(c, [(8, hy - 17), (8 + s2 * 7, hy - 22), (8 + s2 * 7, hy - 12)], "#FF6FB5", 1.2)

    lx, ly = st.get("look", (0, 0))
    for side in (-1, 1):
        ex, ey = side * 7.4, hy - 1.5
        rx, ry = 6.4 * eye_s, 8.2 * eye_s * eo
        if st["expr"] == "happy" and eo > 0.5:
            c.move_to(ex - rx * 0.9, ey + 2)
            c.curve_to(ex - rx * 0.5, ey - 5, ex + rx * 0.5, ey - 5, ex + rx * 0.9, ey + 2)
            c.set_line_width(2.6)
            setc(c, "#FFFFFF")
            c.set_line_cap(cairo.LINE_CAP_ROUND)
            c.stroke()
            continue
        ell(c, ex, ey, rx, max(ry, 0.7))
        fs(c, "#FFFFFF")
        if eo > 0.3:
            ell(c, ex + lx * 2.2 * eye_s, ey + ly * 2.6 * eye_s + 0.8, 2.5 * pup, 2.5 * pup)
            fs(c, INK)
        cover = lid if eo > 0.3 else 0
        if cover > 0 or tilt:
            yt = ey - ry
            c.save()
            ell(c, ex, ey, rx + 0.3, max(ry, 0.7) + 0.3)
            c.clip()
            d = tilt * 6
            yl = yt + cover * 2 * ry
            inner_y, outer_y = yl + d, yl - d       # + eğim: iç uç aşağı (kızgın)
            if side < 0:
                pts = [(ex - rx - 1, yt - 4), (ex + rx + 1, yt - 4), (ex + rx + 1, inner_y), (ex - rx - 1, outer_y)]
            else:
                pts = [(ex - rx - 1, yt - 4), (ex + rx + 1, yt - 4), (ex + rx + 1, outer_y), (ex - rx - 1, inner_y)]
            poly(c, pts, SKIN)
            c.restore()
    if p["acc"] == "glasses":
        for side in (-1, 1):
            rrect(c, side * 7.4 - 7.4, hy - 9.5, 14.8, 15, 4)
            setc(c, "#E9ECEF")
            c.set_line_width(1.5)
            c.stroke()
    if p["acc"] == "lab":
        for side in (-1, 1):
            ell(c, side * 7.4, hy - 1.5, 8, 8)
            setc(c, "#E9ECEF")
            c.set_line_width(1.3)
            c.stroke()
        for s2 in (-1, 1):
            ell(c, s2 * 18, hy - 9, 4, 5)
            fs(c, "#DEE2E6", 1.2)
    if p["acc"] == "whitehair":
        c.move_to(-8, hy + 9.5)
        c.curve_to(-4, hy + 7, 4, hy + 7, 8, hy + 9.5)
        c.curve_to(4, hy + 12, -4, hy + 12, -8, hy + 9.5)
        fs(c, "#F1F3F5")

    my = hy + 10
    WH = "#FFFFFF"
    c.set_line_cap(cairo.LINE_CAP_ROUND)
    if mouth == "smile":
        c.move_to(-6, my - 1)
        c.curve_to(-3, my + 4, 3, my + 4, 6, my - 1)
        setc(c, WH)
        c.set_line_width(2.2)
        c.stroke()
    elif mouth == "open_smile":
        c.move_to(-7, my - 2)
        c.curve_to(-5, my + 7, 5, my + 7, 7, my - 2)
        c.close_path()
        fs(c, "#7A1F2B", 1.6, WH)
        rrect(c, -5.5, my - 2, 11, 2.4, 1)
        fs(c, WH)
    elif mouth == "o":
        ell(c, 0, my + 1.5, 3.6, 4.6)
        fs(c, "#7A1F2B", 1.8, WH)
    elif mouth == "grimace":
        rrect(c, -7, my - 2.6, 14, 6, 2)
        fs(c, WH, 1.0, INK)
        ln(c, [(-6.5, my + 0.4), (6.5, my + 0.4)], 0.8)
        for xx in (-3.5, 0, 3.5):
            ln(c, [(xx, my - 2.4), (xx, my + 3.2)], 0.8)
    elif mouth == "frown":
        c.move_to(-5.5, my + 2.5)
        c.curve_to(-2.5, my - 1.5, 2.5, my - 1.5, 5.5, my + 2.5)
        setc(c, WH)
        c.set_line_width(2.2)
        c.stroke()
    elif mouth == "smirk":
        c.move_to(-4, my + 0.5)
        c.curve_to(0, my + 1.5, 3, my + 0.5, 6, my - 2.5)
        setc(c, WH)
        c.set_line_width(2.2)
        c.stroke()
    elif mouth == "side":
        ln(c, [(1, my + 0.5), (6, my - 0.5)], 2.0, WH)
    else:
        ln(c, [(-4, my + 0.5), (4, my + 0.5)], 2.0, WH)

    if p["acc"] == "helmet":
        ell(c, 0, hy, 27, 26)
        c.set_source_rgba(0.75, 0.88, 1, 0.22)
        c.fill_preserve()
        setc(c, "#CED4DA")
        c.set_line_width(2.4)
        c.stroke()
        c.move_to(-16, hy - 14)
        c.curve_to(-12, hy - 20, -6, hy - 22, 0, hy - 22)
        setc(c, (1, 1, 1, 0.7))
        c.set_line_width(2.4)
        c.stroke()

    draw_arm(c, p, arm_pts(1, ur, er, sh_r))
    for ef, k in st.get("effects", []):
        draw_effect(c, ef, k, hy, t)
    c.restore()


def draw_effect(c, ef, k, hy, t):
    if k <= 0:
        return
    if ef == "!":
        s = ease(k * 3)
        c.save()
        c.translate(25, hy - 25)
        c.scale(s, s)
        c.rotate(0.2)
        rrect(c, -2.4, -14, 4.8, 13, 2.4)
        fs(c, "#FF3B30", 1.4)
        ell(c, 0, 4, 2.6, 2.6)
        fs(c, "#FF3B30", 1.4)
        c.restore()
    elif ef == "?":
        c.save()
        c.translate(26, hy - 22)
        c.scale(ease(k * 3), ease(k * 3))
        c.select_font_face("DejaVu Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        c.set_font_size(19)
        c.move_to(-6, 6)
        c.text_path("?")
        fs(c, "#FFD60A", 1.4)
        c.restore()
    elif ef == "sweat":
        yy = hy - 10 + (t * 14) % 10
        c.move_to(22, yy - 6)
        c.curve_to(26, yy, 26, yy + 4, 22, yy + 4)
        c.curve_to(18, yy + 4, 18, yy, 22, yy - 6)
        fs(c, "#7FD3FF", 1.2)
    elif ef == "sparkle":
        for i, (sx, sy) in enumerate(((-28, hy - 18), (28, hy - 26), (32, hy + 4))):
            r = 3 + 2 * abs(math.sin(t * 4 + i * 2))
            c.save()
            c.translate(sx, sy)
            c.move_to(0, -r * 2)
            for j in range(4):
                a = j * math.pi / 2
                c.line_to(r * 0.45 * math.cos(a + math.pi / 4), r * 0.45 * math.sin(a + math.pi / 4))
                c.line_to(r * 2 * math.cos(a + math.pi / 2), r * 2 * math.sin(a + math.pi / 2))
            c.close_path()
            fs(c, "#FFD60A")
            c.restore()
    elif ef == "speed":
        for i in range(3):
            yy = -58 + i * 17
            ln(c, [(-28, yy), (-44 - 6 * math.sin(t * 20 + i), yy)], 2, (0, 0, 0, 0.45))
    elif ef == "zzz":
        c.select_font_face("DejaVu Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        for i in range(3):
            k2 = (t * 0.5 + i / 3) % 1
            c.save()
            c.translate(20 + k2 * 18, hy - 22 - k2 * 40)
            c.set_font_size(8 + k2 * 10)
            c.move_to(0, 0)
            c.text_path("Z")
            c.set_source_rgba(*hx("#4361EE", 1 - k2))
            c.fill()
            c.restore()
    elif ef == "heart":
        for i in range(2):
            k2 = (t * 0.6 + i / 2) % 1
            c.save()
            c.translate(18 + i * 10, hy - 20 - k2 * 30)
            c.scale(0.6 + k2 * 0.4, 0.6 + k2 * 0.4)
            c.move_to(0, 4)
            c.curve_to(-8, -2, -4, -9, 0, -4)
            c.curve_to(4, -9, 8, -2, 0, 4)
            c.set_source_rgba(*hx("#FF4D6D", 1 - k2))
            c.fill()
            c.restore()


# ============================================================ perspektifli iç mekân
def room_shell(c, W, H, wall, side, floor, board, ceil):
    """Tek kaçış noktalı oda. Arka duvar sınırlarını ve yan duvar dörtgenlerini döndürür."""
    vx, vy = W / 2, H * 0.42
    L, R, T, B = W * 0.12, W * 0.88, H * 0.06, H * 0.60
    yb_edge = B + (B - vy) / (vx - L) * L
    yt_edge = T - (vy - T) / (vx - L) * L
    poly(c, [(-200, -10), (W + 200, -10), (W + 200, yt_edge), (R, T), (L, T), (-200, yt_edge)], ceil)
    poly(c, [(L, T), (R, T), (R, B), (L, B)], wall)
    g = cairo.RadialGradient(W / 2, H * 0.3, 50, W / 2, H * 0.3, W * 0.6)
    g.add_color_stop_rgba(0, 1, 1, 1, 0.18)
    g.add_color_stop_rgba(1, 1, 1, 1, 0)
    c.rectangle(L, T, R - L, B - T)
    c.set_source(g)
    c.fill()
    poly(c, [(-200, yt_edge - 10), (L, T), (L, B), (-200, yb_edge + 40)], side)
    poly(c, [(W + 200, yt_edge - 10), (R, T), (R, B), (W + 200, yb_edge + 40)], side)
    floor_pts = [(L, B), (R, B), (W + 200, yb_edge + 40), (W + 200, H + 10), (-200, H + 10), (-200, yb_edge + 40)]
    poly(c, floor_pts, floor)
    c.save()
    c.move_to(*floor_pts[0])
    for p_ in floor_pts[1:]:
        c.line_to(*p_)
    c.close_path()
    c.clip()
    for i in range(-10, 11):
        bx = vx + i * (R - L) / 10
        ex_ = vx + (bx - vx) * (H - vy) / (B - vy)
        ln(c, [(bx, B), (ex_, H)], 3, board)
    for j in range(1, 7):
        yy = B + (H - B) * (j / 7) ** 1.6
        ln(c, [(-200, yy), (W + 200, yy)], 2, board)
    g = cairo.LinearGradient(0, B, 0, B + 70)
    g.add_color_stop_rgba(0, 0, 0, 0, 0.22)
    g.add_color_stop_rgba(1, 0, 0, 0, 0)
    c.rectangle(-200, B, W + 400, 70)
    c.set_source(g)
    c.fill()
    c.restore()
    edge = mix(side, "#000000", 0.3)
    for a, b in (((L, T), (L, B)), ((R, T), (R, B)), ((L, B), (R, B)), ((L, T), (R, T)),
                 ((L, B), (-200, yb_edge + 40)), ((R, B), (W + 200, yb_edge + 40))):
        ln(c, [a, b], 3, edge)
    left_wall = [(0, yt_edge), (L, T), (L, B), (0, yb_edge)]
    right_wall = [(R, T), (W, yt_edge), (W, yb_edge), (R, B)]
    return (L, T, R, B), left_wall, right_wall


def window(c, x, y, w, h, t, night=False):
    rrect(c, x - 10, y - 10, w + 20, h + 20, 8)
    fs(c, "#FFFFFF", 3)
    c.save()
    rrect(c, x, y, w, h, 4)
    c.clip()
    if night:
        vgrad(c, x, y, w, h, "#0D1B2A", "#33415C")
        ell(c, x + w * 0.7, y + h * 0.3, 22, 22)
        fs(c, "#F8F3D4")
    else:
        vgrad(c, x, y, w, h, "#7EC8FF", "#D7F0FF")
        cx = x + ((t * 18) % (w + 220)) - 110
        for dx, dy, r in ((0, h * 0.35, 30), (34, h * 0.3, 38), (70, h * 0.37, 26)):
            ell(c, cx + dx, y + dy, r, r * 0.65)
            c.set_source_rgba(1, 1, 1, 0.95)
            c.fill()
        ell(c, x + w * 0.3, y + h * 1.1, w * 0.8, h * 0.35)
        fs(c, "#8FD694")
    c.restore()
    ln(c, [(x + w / 2, y), (x + w / 2, y + h)], 5, "#FFFFFF")
    ln(c, [(x, y + h / 2), (x + w, y + h / 2)], 5, "#FFFFFF")
    rrect(c, x, y, w, h, 4)
    setc(c, INK)
    c.set_line_width(3)
    c.stroke()


def potted_plant(c, x, y, s, t):
    c.save()
    c.translate(x, y)
    c.scale(s, s)
    for i, a in enumerate((-0.6, -0.25, 0.1, 0.45, 0.8)):
        c.save()
        c.rotate(a + 0.05 * math.sin(t * 1.3 + i))
        c.move_to(0, -40)
        c.curve_to(-22, -90, -10, -140, 0, -160)
        c.curve_to(10, -140, 22, -90, 0, -40)
        fs(c, "#2D6A4F" if i % 2 else "#40916C", 3)
        c.restore()
    poly(c, [(-45, -45), (45, -45), (34, 40), (-34, 40)], "#C8553D", 4)
    c.restore()


# ============================================================ mekânlar
def bg_bedroom(c, W, H, t, rnd, pan):
    with Layer(c, pan, 0.25):
        (L, T, R, B), lw_, rw_ = room_shell(c, W, H, "#F3D2C1", "#E3B9A6", "#B07D58", "#97664A", "#F8E1D4")
        window(c, W * 0.5, H * 0.13, W * 0.26, H * 0.17, t)
        for sx in (W * 0.47, W * 0.76):
            rrect(c, sx - 12, H * 0.1, 50, H * 0.25, 18)
            fs(c, "#5E60CE", 3)
        q = subquad(lw_, 0.3, 0.22, 0.85, 0.5)
        poly(c, q, "#FFFFFF", 3)
        poly(c, subquad(q, 0.12, 0.12, 0.88, 0.88), "#FFB703")
        poly(c, subquad(q, 0.3, 0.4, 0.7, 0.88), "#FB8500")
        box(c, (W * 0.15, B - 40, W * 0.28, 110), (-40, 40), "#4CC9F0", lw=3)
        rrect(c, W * 0.15, B - 120, W * 0.05, 90, 8)
        fs(c, "#8D5B3B", 3)
        rrect(c, W * 0.21, B - 62, W * 0.08, 30, 12)
        fs(c, "#FFFFFF", 3)
        glow(c, W * 0.86, B - 190, 220, "#FFE066", 0.45)
        box(c, (W * 0.8, B - 80, 130, 140), (40, 30), "#A47148", lw=3)
        poly(c, [(W * 0.82, B - 230), (W * 0.9, B - 230), (W * 0.92, B - 170), (W * 0.8, B - 170)], "#FFD166", 3)
        ln(c, [(W * 0.86, B - 170), (W * 0.86, B - 82)], 5)
    with Layer(c, pan, 0.6):
        ell(c, W * 0.5, H * 0.8, W * 0.44, H * 0.06)
        fs(c, "#E76F51", 4)
        ell(c, W * 0.5, H * 0.8, W * 0.34, H * 0.045)
        setc(c, "#F4A261")
        c.set_line_width(8)
        c.stroke()
    with Layer(c, pan, 1.5):
        potted_plant(c, -10, H * 0.98, 2.2, t)


def bg_kitchen(c, W, H, t, rnd, pan):
    with Layer(c, pan, 0.25):
        (L, T, R, B), lw_, rw_ = room_shell(c, W, H, "#E9F5DB", "#CFE1B9", "#D4A373", "#BC8A5F", "#F6FBEF")
        c.save()
        c.rectangle(L, H * 0.33, R - L, B - H * 0.33)
        c.clip()
        for yy in range(int(H * 0.33), int(B), 48):
            ln(c, [(L, yy), (R, yy)], 2, "#C9DDB3")
        for xx in range(int(L), int(R), 48):
            ln(c, [(xx, H * 0.33), (xx, B)], 2, "#C9DDB3")
        c.restore()
        for i in range(3):
            rrect(c, L + 20 + i * 180, H * 0.1, 165, H * 0.13, 6)
            fs(c, "#F28482", 3)
            ell(c, L + 102 + i * 180, H * 0.215, 8, 4)
            fs(c, INK)
        box(c, (L - 10, B - 120, W * 0.56, 150), (0, -24), "#84A59D", top_fill="#EDEDE9", lw=3)
        for i in range(3):
            rrect(c, L + 15 + i * 190, B - 100, 175, 120, 6)
            setc(c, "#52796F")
            c.set_line_width(3)
            c.stroke()
        ell(c, W * 0.32, B - 140, 60, 16)
        fs(c, "#343A40", 3)
        for i in range(3):
            k = (t * 0.6 + i / 3) % 1
            ell(c, W * 0.32 + 15 * math.sin(t * 2 + i), B - 170 - k * 120, 16 + k * 20, 12 + k * 16)
            c.set_source_rgba(1, 1, 1, 0.6 * (1 - k))
            c.fill()
        box(c, (W * 0.72, H * 0.24, 190, B - H * 0.24 + 50), (-34, 22), "#F8F9FA", lw=3)
        ln(c, [(W * 0.72, H * 0.4), (W * 0.72 + 190, H * 0.4)], 3)
        rrect(c, W * 0.72 + 16, H * 0.29, 9, 60, 4)
        fs(c, "#ADB5BD", 2)
    with Layer(c, pan, 1.5):
        potted_plant(c, W + 20, H * 0.98, 2.0, t)


def bg_classroom(c, W, H, t, rnd, pan):
    with Layer(c, pan, 0.25):
        (L, T, R, B), lw_, rw_ = room_shell(c, W, H, "#FFF3B0", "#F2E19B", "#9C6644", "#7F5539", "#FFFBE6")
        rrect(c, W * 0.2, H * 0.14, W * 0.6, H * 0.21, 8)
        fs(c, "#2D6A4F", 10, "#8D5B3B")
        for i in range(3):
            ln(c, [(W * 0.26, H * 0.19 + i * 60), (W * (0.45 + 0.08 * i), H * 0.19 + i * 60)], 5, (1, 1, 1, 0.85))
        ell(c, W * 0.66, H * 0.25, 45, 45)
        setc(c, (1, 1, 1, 0.85))
        c.set_line_width(5)
        c.stroke()
        ell(c, W * 0.5, H * 0.085, 32, 32)
        fs(c, "#FFFFFF", 4)
        a = t * 1.2
        ln(c, [(W * 0.5, H * 0.085), (W * 0.5 + 22 * math.sin(a), H * 0.085 - 22 * math.cos(a))], 3)
        q = subquad(lw_, 0.3, 0.25, 0.9, 0.55)
        poly(c, q, "#A8DADC", 3)
        poly(c, subquad(q, 0.2, 0.2, 0.55, 0.7), "#80B918")
        for row, (yy, s) in enumerate(((B + 20, 0.55), (B + 95, 0.72))):
            for col in range(3):
                x = W * (0.18 + col * 0.25) - row * 20
                box(c, (x, yy - 60 * s, 170 * s, 50 * s), (0, -22 * s), "#E9C46A", lw=3)
                ln(c, [(x + 10, yy - 10 * s), (x + 10, yy + 40 * s)], 4)
                ln(c, [(x + 160 * s, yy - 10 * s), (x + 160 * s, yy + 40 * s)], 4)
    with Layer(c, pan, 1.5):
        potted_plant(c, -20, H * 0.99, 2.0, t)


def bg_lab(c, W, H, t, rnd, pan):
    with Layer(c, pan, 0.25):
        (L, T, R, B), lw_, rw_ = room_shell(c, W, H, "#E7EEF5", "#D3DDE7", "#B8C4CF", "#A3B0BD", "#F4F7FA")
        for i in range(2):
            yy = H * (0.2 + i * 0.15)
            rrect(c, W * 0.17, yy, W * 0.36, 12, 4)
            fs(c, "#8D99AE", 3)
            for k, col in enumerate(("#06D6A0", "#FFD166", "#EF476F", "#4CC9F0")):
                x = W * 0.19 + k * 92
                poly(c, [(x, yy), (x + 10, yy - 70), (x + 34, yy - 70), (x + 44, yy)], hx(col, 0.85), 3)
                by = yy - 80 - ((t * 35 + k * 25 + i * 10) % 60)
                ell(c, x + 22, by, 6, 6)
                c.set_source_rgba(*hx(col, 0.6))
                c.fill()
        glow(c, W * 0.72, H * 0.21, 280, "#4CC9F0", 0.22)
        rrect(c, W * 0.6, H * 0.14, W * 0.24, H * 0.14, 8)
        fs(c, "#1B263B", 4)
        pts = [(W * 0.62 + i * 15, H * 0.21 + 40 * math.sin(i * 0.6 + t * 4)) for i in range(16)]
        ln(c, pts, 4, "#06D6A0")
        box(c, (W * 0.58, B - 60, W * 0.3, 90), (-30, 30), "#ADB5BD", top_fill="#F8F9FA", lw=3)
        for k in range(3):
            ell(c, W * 0.64 + k * 90, B - 82, 18, 24)
            fs(c, hx(("#F72585", "#7209B7", "#3A0CA3")[k], 0.8), 3)
    with Layer(c, pan, 1.5):
        poly(c, [(W * 0.82, H), (W * 0.86, H * 0.86), (W * 0.94, H * 0.86), (W * 0.98, H)], hx("#06D6A0", 0.85), 4)
        glow(c, W * 0.9, H * 0.93, 140, "#06D6A0", 0.3)


def bg_street(c, W, H, t, rnd, pan):
    vx, vy = W / 2, H * 0.44
    with Layer(c, pan, 0.05):
        vgrad(c, -200, 0, W + 400, vy + 10, "#74C0FC", "#FFE5D9")
        for i in range(3):
            x = ((t * 15 * (1 + i * 0.4) + i * 380) % (W + 500)) - 250
            for dx, dy, r in ((0, 0, 40), (45, -14, 52), (95, 0, 38)):
                ell(c, x + dx, H * (0.07 + 0.06 * i) + dy, r, r * 0.65)
                c.set_source_rgba(1, 1, 1, 0.9)
                c.fill()
    with Layer(c, pan, 0.15):
        x = -200
        while x < W + 200:
            bw, bh = rnd.randint(50, 90), rnd.randint(60, 200)
            c.rectangle(x, vy - bh, bw, bh)
            setc(c, mix("#6C8EAD", "#FFE5D9", 0.45))
            c.fill()
            x += bw + 4
    with Layer(c, pan, 0.45):
        c.rectangle(-300, vy - 2, W + 600, H - vy + 12)
        fs(c, "#ADB5BD")
        poly(c, [(vx - 30, vy), (vx + 30, vy), (W + 300, H), (-300, H)], "#495057")
        poly(c, [(vx - 30, vy), (vx - 60, vy), (-800, H), (-300, H)], "#ADB5BD")
        poly(c, [(vx + 30, vy), (vx + 60, vy), (W + 800, H), (W + 300, H)], "#ADB5BD")
        for j in range(8):
            ph = (t * 1.2) % 1
            k0, k1 = ((j + ph) / 8) ** 2, ((j + 0.45 + ph) / 8) ** 2
            y0, y1 = lerp(vy, H, k0), lerp(vy, H, k1)
            w0, w1 = lerp(2, 18, k0), lerp(2, 18, k1)
            poly(c, [(vx - w0, y0), (vx + w0, y0), (vx + w1, y1), (vx - w1, y1)], "#FFD43B")
        cols = ["#E76F51", "#2A9D8F", "#F4A261", "#457B9D", "#E9C46A", "#6D597A"]
        for side in (-1, 1):
            edges = [0.0, 0.3, 0.52, 0.68]
            for i in range(3):
                a, b = edges[i], edges[i + 1]
                ka, kb = 1 - a, 1 - b
                xa, xb = vx + side * W * 0.8 * ka, vx + side * W * 0.8 * kb
                ya, yb = lerp(vy, H, ka) - 120 * ka, lerp(vy, H, kb) - 120 * kb
                ha, hb = H * 0.6 * ka + 30, H * 0.6 * kb + 30
                q = [(xa, ya - ha), (xb, yb - hb), (xb, yb), (xa, ya)]
                if side > 0:
                    q = [q[1], q[0], q[3], q[2]]
                poly(c, q, cols[i + (3 if side > 0 else 0)], 3)
                for r_ in range(4):
                    for k_ in range(3):
                        wq = subquad(q, 0.12 + k_ * 0.29, 0.1 + r_ * 0.21, 0.3 + k_ * 0.29, 0.24 + r_ * 0.21)
                        poly(c, wq, "#FFE8A3" if (r_ + k_ + i) % 3 == 0 else "#BDE0FE", 2)
    with Layer(c, pan, 1.5):
        x = -30
        ln(c, [(x + 60, H + 10), (x + 60, H * 0.38), (x + 140, H * 0.36)], 16, "#343A40")
        glow(c, x + 160, H * 0.37, 160, "#FFE066", 0.35)
        ell(c, x + 160, H * 0.37, 26, 14)
        fs(c, "#FFE066", 4)


def bg_park(c, W, H, t, rnd, pan):
    hz = H * 0.5
    with Layer(c, pan, 0.03):
        vgrad(c, -200, 0, W + 400, hz, "#4DABF7", "#E7F5FF")
        glow(c, W * 0.8, H * 0.1, 220, "#FFF3BF", 0.8)
        ell(c, W * 0.8, H * 0.1, 70, 70)
        fs(c, "#FFE066")
    with Layer(c, pan, 0.08):
        for i in range(3):
            x = ((t * 16 * (1 + i * 0.3) + i * 400) % (W + 500)) - 250
            for dx, dy, r in ((0, 0, 46), (52, -16, 58), (110, 0, 42)):
                ell(c, x + dx, H * (0.08 + 0.07 * i) + dy, r, r * 0.65)
                c.set_source_rgba(1, 1, 1, 0.92)
                c.fill()
    with Layer(c, pan, 0.12):
        c.move_to(-300, hz)
        for i in range(9):
            c.line_to(-300 + i * 220 + 110, hz - 180 - (i * 53) % 120)
            c.line_to(-300 + (i + 1) * 220, hz - 40)
        c.line_to(W + 300, hz)
        c.close_path()
        fs(c, "#A5C8E4")
    with Layer(c, pan, 0.25):
        ell(c, W * 0.15, hz + 30, 600, 160)
        fs(c, "#9BD49A")
        ell(c, W * 0.9, hz + 40, 650, 170)
        fs(c, "#86C98A")
        for i in range(8):
            ell(c, -150 + i * 190, hz - 25, 42, 52)
            fs(c, "#52B788", 2)
    with Layer(c, pan, 0.5):
        poly(c, [(-300, hz + 20), (W + 300, hz + 20), (W + 300, H + 10), (-300, H + 10)], "#74C365")
        poly(c, [(W / 2 - 20, hz + 20), (W / 2 + 20, hz + 20), (W * 0.95, H + 10), (W * 0.05, H + 10)], "#E9D8A6")
        for x in (W * 0.06, W * 0.92):
            rrect(c, x - 26, H * 0.36, 52, H * 0.3, 16)
            fs(c, "#8D5B3B", 4)
            sway = 6 * math.sin(t * 1.2 + x)
            for dx, dy, r in ((-90, 0.37, 110), (95, 0.36, 115), (0, 0.3, 150)):
                ell(c, x + dx + sway, H * dy, r, r)
                fs(c, "#2D6A4F" if dx else "#40916C", 4)
        box(c, (W * 0.62, H * 0.6, 220, 30), (30, -18), "#B5651D", lw=3)
        ln(c, [(W * 0.64, H * 0.6 + 30), (W * 0.64, H * 0.66)], 6)
        ln(c, [(W * 0.62 + 200, H * 0.6 + 30), (W * 0.62 + 200, H * 0.66)], 6)
    with Layer(c, pan, 1.5):
        for x, r in ((-40, 180), (W + 40, 200)):
            ell(c, x, H + 30, r, r * 0.8)
            fs(c, "#2B9348", 4)


def bg_space(c, W, H, t, rnd, pan):
    vgrad(c, 0, 0, W, H, "#03071E", "#1B263B")
    for depth, n, size in ((0.03, 90, 1.6), (0.1, 50, 2.4), (0.2, 25, 3.4)):
        with Layer(c, pan, depth):
            for i in range(n):
                x, y = rnd.random() * (W + 400) - 200, rnd.random() * H * 0.75
                ell(c, x, y, size, size)
                c.set_source_rgba(1, 1, 1, 0.35 + 0.65 * abs(math.sin(t * (0.6 + rnd.random() * 2) + i)))
                c.fill()
    with Layer(c, pan, 0.06):
        glow(c, W * 0.25, H * 0.25, 380, "#7209B7", 0.35)
        glow(c, W * 0.7, H * 0.15, 320, "#4361EE", 0.3)
    with Layer(c, pan, 0.18):
        ell(c, W * 0.95, H * 0.3, 230, 230)
        fs(c, "#F28482")
        c.save()
        ell(c, W * 0.95, H * 0.3, 230, 230)
        c.clip()
        for k in range(5):
            ln(c, [(W * 0.6, H * 0.2 + k * 70), (W * 1.3, H * 0.24 + k * 70)], 26, (1, 1, 1, 0.12))
        ell(c, W * 0.95 + 120, H * 0.3 + 60, 230, 230)
        c.set_source_rgba(0, 0, 0, 0.3)
        c.fill()
        c.restore()
    with Layer(c, pan, 0.5):
        c.move_to(-300, H * 0.62)
        c.curve_to(W * 0.2, H * 0.57, W * 0.8, H * 0.58, W + 300, H * 0.63)
        c.line_to(W + 300, H + 10)
        c.line_to(-300, H + 10)
        c.close_path()
        fs(c, "#ADB5BD", 4)
        for cx_, cy_, r in ((0.15, 0.66, 60), (0.62, 0.64, 40), (0.88, 0.72, 80), (0.3, 0.86, 120), (0.78, 0.93, 90)):
            ell(c, W * cx_, H * cy_, r, r * 0.32)
            fs(c, "#868E96", 3)
            ell(c, W * cx_, H * cy_ - r * 0.06, r * 0.8, r * 0.2)
            fs(c, "#9AA1A9")


def bg_ocean(c, W, H, t, rnd, pan):
    vgrad(c, 0, 0, W, H, "#4CC9F0", "#03256C")
    with Layer(c, pan, 0.05):
        for i in range(6):
            x = W * (i * 0.2) + 40 * math.sin(t * 0.4 + i)
            poly(c, [(x, 0), (x + 80, 0), (x + 260, H * 0.7), (x + 150, H * 0.7)], (1, 1, 1, 0.05))
    with Layer(c, pan, 0.15):
        for i in range(5):
            ell(c, -100 + i * 300, H * 0.6, 200, 120)
            setc(c, mix("#1E6091", "#4CC9F0", 0.4))
            c.fill()
    with Layer(c, pan, 0.3):
        for i in range(6):
            x = ((t * (60 + i * 15) + i * 300) % (W + 400)) - 200
            y = H * (0.16 + 0.06 * i)
            s = 0.6 + (i % 3) * 0.35
            col = ("#FFB703", "#FB8500", "#F72585")[i % 3]
            c.save()
            c.translate(x, y + 10 * math.sin(t * 2 + i))
            c.scale(s, s)
            ell(c, 0, 0, 34, 18)
            fs(c, col, 3)
            poly(c, [(-30, 0), (-52, -16), (-52, 16)], col, 3)
            ell(c, 16, -4, 4, 4)
            fs(c, INK)
            c.restore()
    with Layer(c, pan, 0.5):
        c.move_to(-300, H * 0.62)
        c.curve_to(W * 0.3, H * 0.58, W * 0.7, H * 0.64, W + 300, H * 0.6)
        c.line_to(W + 300, H + 10)
        c.line_to(-300, H + 10)
        c.close_path()
        fs(c, "#E9D8A6", 4)
        for j in range(5):
            yy = H * (0.66 + 0.06 * j * (1 + j * 0.15))
            ln(c, [(-300, yy), (W * 0.3, yy - 10), (W + 300, yy)], 3, "#D4B483")
        for i in range(16):
            bx = (i * 173) % W + 10 * math.sin(t * 2 + i)
            by = H - ((t * (70 + i * 6) + i * 140) % H)
            ell(c, bx, by, 8 + i % 4 * 3, 8 + i % 4 * 3)
            c.set_source_rgba(1, 1, 1, 0.5)
            c.set_line_width(3)
            c.stroke()
    with Layer(c, pan, 1.4):
        for i, x0 in enumerate((-20, 60, W - 60, W + 10)):
            pts = [(x0 + 30 * math.sin(t * 1.5 + k * 0.6 + i), H + 10 - k * 90) for k in range(9)]
            ln(c, pts, 34, "#1B4332")
            ln(c, pts, 22, "#2D6A4F")


def bg_night(c, W, H, t, rnd, pan):
    hz = H * 0.55
    vgrad(c, 0, 0, W, hz, "#0B132B", "#3A506B")
    with Layer(c, pan, 0.04):
        for i in range(80):
            x, y = rnd.random() * (W + 300) - 150, rnd.random() * hz * 0.75
            ell(c, x, y, 2.2, 2.2)
            c.set_source_rgba(1, 1, 1, 0.4 + 0.6 * abs(math.sin(t + i)))
            c.fill()
        glow(c, W * 0.78, H * 0.12, 200, "#F8F3D4", 0.35)
        ell(c, W * 0.78, H * 0.12, 64, 64)
        fs(c, "#F8F3D4")
    with Layer(c, pan, 0.12):
        x = -200
        while x < W + 200:
            bw, bh = rnd.randint(60, 110), rnd.randint(100, 280)
            c.rectangle(x, hz - bh, bw, bh)
            fs(c, "#1C2541")
            for wy in range(int(hz - bh + 20), int(hz - 20), 34):
                if rnd.random() < 0.35:
                    c.rectangle(x + 15, wy, 14, 16)
                    fs(c, "#FFD166")
            x += bw + 6
    with Layer(c, pan, 0.35):
        poly(c, [(-300, hz), (W + 300, hz), (W + 300, H + 10), (-300, H + 10)], "#22333B")
        for i, x in enumerate((W * 0.03, W * 0.64)):
            box(c, (x, hz - 220, 300, 260), (40, -30), ("#5C677D", "#7D8597")[i], lw=3)
            poly(c, [(x - 20, hz - 220), (x + 150, hz - 330), (x + 320, hz - 220)], "#33415C", 3)
            for k in range(2):
                glow(c, x + 75 + k * 140, hz - 135, 90, "#FFD166", 0.25)
                rrect(c, x + 40 + k * 140, hz - 170, 70, 70, 4)
                fs(c, "#FFD166", 3)
        poly(c, [(W / 2 - 20, hz), (W / 2 + 20, hz), (W * 0.9, H + 10), (W * 0.1, H + 10)], "#495057")
    with Layer(c, pan, 0.7):
        x = W * 0.86
        poly(c, [(x - 10, H * 0.42), (x + 10, H * 0.42), (x + 160, H * 0.8), (x - 160, H * 0.8)], (1, 0.9, 0.5, 0.12))
        ln(c, [(x, H * 0.82), (x, H * 0.42)], 12, "#212529")
        ell(c, x, H * 0.42, 22, 14)
        fs(c, "#FFE066", 3)
    with Layer(c, pan, 1.5):
        for i in range(-1, 9):
            rrect(c, i * 150, H * 0.88, 40, 260, 10)
            fs(c, "#3E2723", 4)
        ln(c, [(-100, H * 0.92), (W + 100, H * 0.92)], 18, "#4E342E")


def bg_desert(c, W, H, t, rnd, pan):
    hz = H * 0.52
    with Layer(c, pan, 0.03):
        vgrad(c, -200, 0, W + 400, hz, "#FF9E00", "#FFE8B5")
        glow(c, W * 0.25, H * 0.13, 260, "#FFF3C4", 0.8)
        ell(c, W * 0.25, H * 0.13, 80, 80)
        fs(c, "#FFF3C4")
    with Layer(c, pan, 0.1):
        c.move_to(-300, hz)
        c.curve_to(W * 0.2, hz - 90, W * 0.5, hz - 20, W + 300, hz - 70)
        c.line_to(W + 300, hz + 40)
        c.line_to(-300, hz + 40)
        c.close_path()
        fs(c, "#F6D8AE")
    with Layer(c, pan, 0.22):
        for px, ph, col in ((0.72, 380, "#E9A44C"), (0.98, 260, "#DDA15E"), (0.42, 210, "#DDA15E")):
            poly(c, [(W * px - ph, hz + 20), (W * px, hz + 20 - ph), (W * px + ph, hz + 20)], col, 4)
            poly(c, [(W * px, hz + 20 - ph), (W * px + ph, hz + 20), (W * px + ph * 0.3, hz + 20)], (0, 0, 0, 0.13))
    with Layer(c, pan, 0.5):
        c.move_to(-300, hz + 30)
        c.curve_to(W * 0.3, hz + 90, W * 0.6, hz - 10, W + 300, hz + 60)
        c.line_to(W + 300, H + 10)
        c.line_to(-300, H + 10)
        c.close_path()
        fs(c, "#F2CC8F", 4)
        for j in range(5):
            yy = H * (0.66 + 0.065 * j)
            ln(c, [(-300, yy), (W * 0.5, yy - 25), (W + 300, yy + 5)], 3, "#E0B573")
        x = W * 0.88
        rrect(c, x - 25, H * 0.46, 50, 260, 25)
        fs(c, "#52B788", 4)
        rrect(c, x + 22, H * 0.52, 60, 26, 13)
        fs(c, "#52B788", 4)
        rrect(c, x + 58, H * 0.46, 26, 80, 13)
        fs(c, "#52B788", 4)
    with Layer(c, pan, 1.5):
        ell(c, -20, H + 20, 260, 140)
        fs(c, "#BC8A5F", 4)
        ell(c, W + 40, H + 40, 220, 150)
        fs(c, "#A47148", 4)


def bg_volcano(c, W, H, t, rnd, pan):
    hz = H * 0.56
    with Layer(c, pan, 0.03):
        vgrad(c, -200, 0, W + 400, hz, "#9D0208", "#FFBA08")
    with Layer(c, pan, 0.1):
        c.move_to(-300, hz)
        for i in range(8):
            c.line_to(-300 + i * 230 + 115, hz - 120 - (i * 41) % 90)
            c.line_to(-300 + (i + 1) * 230, hz - 20)
        c.line_to(W + 300, hz)
        c.close_path()
        fs(c, "#6A040F")
    with Layer(c, pan, 0.25):
        vx = W * 0.55
        for i in range(7):
            k = (t * 0.22 + i / 7) % 1
            ell(c, vx + 40 * math.sin(i + t), hz - 600 - k * 600, 70 + k * 120, 55 + k * 90)
            c.set_source_rgba(0.25, 0.22, 0.22, 0.75 * (1 - k))
            c.fill()
        poly(c, [(vx - 520, hz + 20), (vx - 110, hz - 620), (vx + 110, hz - 620), (vx + 520, hz + 20)], "#3C2A21", 5)
        glow(c, vx, hz - 620, 260, "#FF4800", 0.6)
        pts = [(vx - 110, hz - 620)]
        for k in range(7):
            pts.append((vx - 110 + k * 36, hz - 620 + (40 + 25 * math.sin(t * 3 + k)) * (k % 2)))
        pts.append((vx + 110, hz - 620))
        poly(c, pts, "#FF4800", 3)
        ln(c, [(vx - 30, hz - 600), (vx - 80, hz - 400), (vx - 60, hz - 200)], 14, "#FF6D00")
    with Layer(c, pan, 0.5):
        poly(c, [(-300, hz + 10), (W + 300, hz + 10), (W + 300, H + 10), (-300, H + 10)], "#3E2723")
        for i in range(6):
            x = (i * 211) % W
            a = 0.5 + 0.5 * abs(math.sin(t * 2 + i))
            ln(c, [(x, H * 0.7 + i * 40), (x + 80, H * 0.72 + i * 40), (x + 140, H * 0.7 + i * 42)], 6, hx("#FF6D00", a))
    with Layer(c, pan, 1.5):
        ell(c, -10, H + 10, 240, 150)
        fs(c, "#2B1D16", 4)
        ell(c, W + 30, H + 30, 260, 170)
        fs(c, "#2B1D16", 4)


def bg_beach(c, W, H, t, rnd, pan):
    hz = H * 0.46
    with Layer(c, pan, 0.03):
        vgrad(c, -200, 0, W + 400, hz, "#48CAE4", "#CAF0F8")
        ell(c, W * 0.15, H * 0.1, 66, 66)
        fs(c, "#FFE066")
    with Layer(c, pan, 0.1):
        vgrad(c, -300, hz, W + 600, H * 0.18, "#0096C7", "#48CAE4")
        ell(c, W * 0.8, hz, 160, 40)
        fs(c, "#52B788")
        for j in range(5):
            yy = hz + 30 + j * 30
            off = 40 * math.sin(t * 1.5 + j)
            ln(c, [(-200 + off, yy), (W * 0.3 + off, yy - 4), (W + 200 + off, yy)], 3, (1, 1, 1, 0.5))
    with Layer(c, pan, 0.5):
        wave = 14 * math.sin(t * 1.4)
        c.move_to(-300, H * 0.62 + wave)
        c.curve_to(W * 0.3, H * 0.6 + wave, W * 0.7, H * 0.64 + wave, W + 300, H * 0.61 + wave)
        c.line_to(W + 300, H + 10)
        c.line_to(-300, H + 10)
        c.close_path()
        fs(c, "#FFE8B5")
        ln(c, [(-300, H * 0.62 + wave), (W * 0.5, H * 0.615 + wave), (W + 300, H * 0.61 + wave)], 10, (1, 1, 1, 0.8))
        x = W * 0.84
        ln(c, [(x, H * 0.75), (x - 20, H * 0.5)], 7)
        c.move_to(x - 200, H * 0.53)
        c.curve_to(x - 150, H * 0.43, x + 120, H * 0.43, x + 160, H * 0.5)
        c.close_path()
        fs(c, "#EF476F", 4)
        poly(c, [(W * 0.06, H * 0.73), (W * 0.3, H * 0.73), (W * 0.34, H * 0.79), (W * 0.02, H * 0.79)], "#118AB2", 3)
    with Layer(c, pan, 1.5):
        for i in range(4):
            c.save()
            c.translate(W + 40, -40)
            c.rotate(1.6 + i * 0.35 + 0.04 * math.sin(t * 1.2 + i))
            c.move_to(0, 0)
            c.curve_to(120, -60, 320, -40, 460, 0)
            c.curve_to(320, 30, 120, 40, 0, 0)
            fs(c, "#2D6A4F", 4)
            c.restore()


ARKA_PLANLAR = {"bedroom": bg_bedroom, "kitchen": bg_kitchen, "classroom": bg_classroom, "lab": bg_lab,
                "street": bg_street, "park": bg_park, "space": bg_space, "ocean": bg_ocean,
                "night": bg_night, "desert": bg_desert, "volcano": bg_volcano, "beach": bg_beach}
ESKI_AD = {"room": "bedroom", "city": "street"}


# ============================================================ nesneler
def prop(c, kind, x, y, s, t):
    c.save()
    c.translate(x, y + 5 * math.sin(t * 1.0))
    c.scale(s, s)
    glow(c, 0, 0, 120, "#FFFFFF", 0.22)
    if kind == "earth":
        ell(c, 0, 0, 60, 60)
        fs(c, "#4EA8DE", 3)
        c.save()
        ell(c, 0, 0, 60, 60)
        c.clip()
        off = (t * 20) % 240
        for k in (-240, 0):
            for dx, dy, rx, ry in ((-30, -15, 26, 18), (25, 10, 22, 30), (-5, 35, 18, 10), (60, -30, 20, 14)):
                ell(c, dx + off + k, dy, rx, ry)
                fs(c, "#52B788")
        ell(c, 25, 20, 60, 60)
        c.set_source_rgba(0, 0, 0, 0.18)
        c.fill()
        c.restore()
        ell(c, 0, 0, 60, 60)
        setc(c, INK)
        c.set_line_width(3)
        c.stroke()
    elif kind == "moon":
        ell(c, 0, 0, 50, 50)
        fs(c, "#E5E5E5", 3)
        for dx, dy, r in ((-15, -10, 10), (18, 12, 8), (5, -25, 6)):
            ell(c, dx, dy, r, r)
            fs(c, "#C4C4C4")
    elif kind == "sun":
        for k in range(12):
            a = k * math.pi / 6 + t * 0.4
            ln(c, [(66 * math.cos(a), 66 * math.sin(a)), (86 * math.cos(a), 86 * math.sin(a))], 7, "#FFB703")
        ell(c, 0, 0, 55, 55)
        fs(c, "#FFD60A", 3)
    elif kind == "rocket":
        c.rotate(0.35)
        f = 1 + 0.25 * math.sin(t * 30)
        poly(c, [(-12, 40), (0, 40 + 34 * f), (12, 40)], "#FF9F1C", 2)
        rrect(c, -18, -40, 36, 82, 18)
        fs(c, "#F1FAEE", 3)
        c.move_to(-18, -20)
        c.curve_to(-18, -60, 18, -60, 18, -20)
        fs(c, "#E63946", 3)
        ell(c, 0, 0, 9, 9)
        fs(c, "#A8DADC", 3)
    elif kind == "plane":
        c.translate(((t * 160) % 600) - 300, 0)
        rrect(c, -70, -12, 140, 24, 12)
        fs(c, "#F8F9FA", 3)
        poly(c, [(-10, 0), (20, 40), (35, 40), (20, 0)], "#457B9D", 3)
        poly(c, [(-60, -10), (-72, -36), (-58, -36), (-45, -10)], "#457B9D", 3)
    elif kind == "clock":
        ell(c, 0, 0, 55, 55)
        fs(c, "#FFFFFF", 5)
        for k in range(12):
            a = k * math.pi / 6
            ln(c, [(46 * math.sin(a), -46 * math.cos(a)), (40 * math.sin(a), -40 * math.cos(a))], 3)
        ln(c, [(0, 0), (38 * math.sin(t * 6), -38 * math.cos(t * 6))], 4, "#E63946")
        ln(c, [(0, 0), (26 * math.sin(t * 0.5), -26 * math.cos(t * 0.5))], 5)
    elif kind == "lightning":
        a = 0.6 + 0.4 * abs(math.sin(t * 12))
        poly(c, [(10, -70), (-25, 5), (2, 5), (-12, 70), (30, -15), (5, -15)], hx("#FFD60A", a), 3)
    elif kind == "phone":
        c.rotate(0.15 * math.sin(t * 2))
        rrect(c, -32, -60, 64, 120, 12)
        fs(c, "#22223B", 3)
        rrect(c, -26, -50, 52, 96, 6)
        fs(c, "#8ECAE6")
        for k in range(3):
            rrect(c, -18, -40 + k * 28, 36, 18, 5)
            fs(c, (1, 1, 1, 0.85))
    elif kind == "car":
        c.translate(((t * 120) % 500) - 250, 0)
        rrect(c, -80, -20, 160, 40, 14)
        fs(c, "#E63946", 3)
        poly(c, [(-45, -20), (-25, -50), (30, -50), (50, -20)], "#A8DADC", 3)
        for wx in (-48, 48):
            ell(c, wx, 22, 18, 18)
            fs(c, "#2B2D42", 3)
    elif kind == "atom":
        for k in range(3):
            c.save()
            c.rotate(k * math.pi / 3 + t * 0.6)
            ell(c, 0, 0, 70, 24)
            setc(c, "#4CC9F0")
            c.set_line_width(5)
            c.stroke()
            a = t * 3 + k * 2
            ell(c, 70 * math.cos(a), 24 * math.sin(a), 7, 7)
            fs(c, "#F72585")
            c.restore()
        ell(c, 0, 0, 16, 16)
        fs(c, "#FFD60A", 3)
    elif kind == "brain":
        ell(c, 0, 0, 62, 48)
        fs(c, "#FFAFCC", 3)
        for k in range(4):
            ln(c, [(-45 + k * 25, -30), (-35 + k * 25, -5), (-48 + k * 25, 20)], 3, "#E5989B")
        ln(c, [(0, -46), (0, 46)], 3, "#E5989B")
    elif kind == "money":
        for k in range(3):
            c.save()
            c.translate(-30 + k * 30, -10 + 8 * math.sin(t * 3 + k))
            c.rotate(-0.2 + k * 0.2)
            rrect(c, -40, -22, 80, 44, 4)
            fs(c, "#80B918", 3)
            ell(c, 0, 0, 12, 12)
            fs(c, "#55A630", 2)
            c.restore()
    elif kind == "heart":
        c.scale(3, 3)
        c.move_to(0, 12)
        c.curve_to(-24, -6, -12, -27, 0, -12)
        c.curve_to(12, -27, 24, -6, 0, 12)
        fs(c, "#FF4D6D", 1.2)
    c.restore()


NESNELER = ("earth", "moon", "sun", "rocket", "plane", "clock", "lightning", "phone", "car", "atom",
            "brain", "money", "heart")


def draw_bed(c, x, g, S, before=True, t=0):
    c.save()
    c.translate(x, g)
    c.scale(S, S)
    if before:
        box(c, (-64, -34, 128, 22), (0, -8), "#FFFFFF", lw=2)
        rrect(c, -68, -46, 9, 46, 3)
        fs(c, "#8D5B3B", 2)
        rrect(c, 58, -26, 8, 26, 3)
        fs(c, "#8D5B3B", 2)
        rrect(c, -60, -50, 26, 14, 7)
        fs(c, "#E0E7FF", 2)
    else:
        b = 0.8 * math.sin(t * 1.4)
        c.move_to(-14, -56 - b)
        c.curve_to(10, -64 - b, 50, -62 - b, 66, -48)
        c.line_to(66, -14)
        c.line_to(-14, -14)
        c.close_path()
        fs(c, "#4361EE", 2)
        for k in range(3):
            ln(c, [(2 + k * 22, -58 - b), (2 + k * 22, -16)], 1.2, "#3A0CA3")
        draw_effect(c, "zzz", 1, -58, t)
    c.restore()


# ============================================================ sahne zaman çizelgesi
VARSAYILAN_POZ = {"neutral": "idle", "happy": "explain", "excited": "cheer", "shocked": "hands_up",
                  "worried": "facepalm", "thinking": "think", "sad": "idle", "angry": "hips", "smug": "hips",
                  "scared": "hands_up", "sleepy": "idle"}
HAREKET_POZ = {"run": "idle", "sleep": "idle", "fly_away": "hands_up", "spin": "hands_up", "look_up": "idle",
               "shiver": "facepalm", "wave": "wave", "point": "point", "shrug": "shrug", "hands_up": "hands_up",
               "think": "think", "hips": "hips", "cheer": "cheer", "facepalm": "facepalm", "explain": "explain",
               "hug": "hug", "love": "hug"}
EFEKT = {"shocked": "!", "thinking": "?", "worried": "sweat", "excited": "sparkle", "scared": "sweat"}
HAREKETLER = ("idle", "walk_in", "walk", "run", "jump", "float", "spin", "fly_away", "sleep", "look_up", "shiver",
              "shake", "wave", "point", "shrug", "hands_up", "think", "hips", "cheer", "facepalm", "explain", "hug",
              "love")


def normalize_scene(sc):
    sc["arka_plan"] = ESKI_AD.get(sc.get("arka_plan"), sc.get("arka_plan"))
    if sc["arka_plan"] not in ARKA_PLANLAR:
        sc["arka_plan"] = "bedroom"
    if sc.get("nesne") not in NESNELER:
        sc["nesne"] = None
    if sc.get("kamera") not in ("push_in", "punch", "static", "pan"):
        sc["kamera"] = "push_in"
    chars = sc.get("karakterler")
    if not isinstance(chars, list) or not chars:
        chars = [{"tip": "hero", "ifade": sc.get("ifade", "neutral"), "hareket": sc.get("hareket", "idle")}]
        ik = sc.get("ikinci")
        if isinstance(ik, dict):
            chars.append({"tip": ik.get("tip"), "ifade": ik.get("ifade", "happy"), "hareket": "idle"})
    out, seen = [], set()
    for ch in chars[:3]:
        if not isinstance(ch, dict):
            continue
        tip = ch.get("tip") if ch.get("tip") in KARAKTERLER else "hero"
        if tip in seen:
            continue
        seen.add(tip)
        out.append({"tip": tip, "ifade": ch.get("ifade") if ch.get("ifade") in IFADELER else "neutral",
                    "hareket": ch.get("hareket") if ch.get("hareket") in HAREKETLER else "idle"})
    sc["karakterler"] = out or [{"tip": "hero", "ifade": "neutral", "hareket": "idle"}]
    return sc


SLOTS = {1: [(0.5, 0.0)], 2: [(0.3, 0.0), (0.72, 0.1)], 3: [(0.27, 0.0), (0.75, 0.06), (0.52, 0.6)]}


def char_state(ch, slot, n_chars, W, H, S, t, gt, blinks, nesne, i_char):
    tip, expr, act = ch["tip"], ch["ifade"], ch["hareket"]
    fx, z = slot
    g = lerp(H * 0.775, H * 0.655, z)
    s = S * lerp(1.0, 0.62, z)
    x0 = W * fx
    facing = 1 if (n_chars == 1 or fx < 0.5) else -1
    x, leg, bob, lean, jump, spin, swing = x0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
    eyes_force, fx_list, under = None, [], None
    stride = 26 * s                        # bir adım döngüsünde alınan yol (px): ayak kaymasın
    if act in ("walk_in", "walk"):
        dur = 1.8
        start = -W * 0.18 if fx <= 0.5 else W * 1.18
        if t < dur:
            x = lerp(start, x0, t / dur)          # sabit hız
            v = abs(x0 - start) / dur
            ph = 2 * math.pi * (x - start) / stride
            leg, swing = 26 * math.sin(ph), 16 * math.sin(ph)
            bob = -1.0 * abs(math.sin(ph))
            facing = 1 if start < x0 else -1
    elif act == "run":
        ph = t * 14
        leg, bob, swing, lean = 36 * math.sin(ph), -1.6 * abs(math.sin(ph)), 32 * math.sin(ph), 8
        fx_list.append(("speed", 1))
    elif act == "jump":
        ph = (t % 1.3) / 1.3
        jump = -18 * s * math.sin(math.pi * ph / 0.4) if ph < 0.4 else 0
        leg = 10 if ph < 0.4 else 0
    elif act == "float":
        jump = -8 * s * (1 + math.sin(t * 1.2))
        lean = 5 * math.sin(t * 0.9)
    elif act == "spin":
        spin = (t * 240) % 360
        jump = -10 * s
    elif act == "fly_away":
        k = max(0.0, t - 0.6)
        x = x0 + (k ** 1.6) * W * 0.5
        jump = -k * 18 * s
        spin = k * 200
        lean = -10 * ease(t / 0.6)
        if k > 0:
            fx_list.append(("speed", 1))
    elif act == "sleep":
        eyes_force, lean, jump, x, bob = 0.04, -90, -46 * s, x0 + 40 * s, 0
        under = "bed"
    elif act == "shiver":
        fx_list.append(("sweat", 1))
    elif act == "love":
        fx_list.append(("heart", 1))
    if act != "sleep":
        bob += 0.35 * math.sin(gt * 1.8 + i_char)
    pose = HAREKET_POZ.get(act, VARSAYILAN_POZ.get(expr, "idle"))
    k = ease(t / 0.3)
    (l0, r0), (l1, r1) = POZLAR["idle"], POZLAR[pose]
    wig = 4 * math.sin(gt * 1.6 + i_char) if pose == "explain" else 0
    wav = 25 * math.sin(gt * 10) if pose == "wave" else 0
    arms = ((lerp(l0[0], l1[0], k) + wig * 0.5 + swing, lerp(l0[1], l1[1], k)),
            (lerp(r0[0], r1[0], k) - wig - swing, lerp(r0[1], r1[1], k) + wav))
    blink = 1.0
    for b in blinks:
        d = t - b - i_char * 0.7
        if 0 <= d < 0.14:
            blink = abs(d - 0.07) / 0.07
    if eyes_force is not None:
        blink = eyes_force
    if act == "look_up":
        look = (0.2 * math.sin(gt), -1.0)
    elif n_chars > 1:
        look = (0.8, 0.0)
    else:
        look = (0.3 * math.sin(gt * 0.7), -0.7 if nesne else 0.1)
    effects = ([(EFEKT[expr], t)] if expr in EFEKT and act != "sleep" else []) + fx_list
    return dict(tip=tip, z=z, g=g, under=under, x0=x0, st=dict(
        x=x, y=g + jump, s=s, facing=facing, expr=expr, arms=arms, eyes_open=blink, look=look, leg=leg,
        bob=bob, lean=lean, spin=spin, effects=effects, t=gt))


def vignette(c, W, H):
    g = cairo.RadialGradient(W / 2, H * 0.45, min(W, H) * 0.45, W / 2, H * 0.45, max(W, H) * 0.8)
    g.add_color_stop_rgba(0, 0, 0, 0, 0)
    g.add_color_stop_rgba(1, 0, 0, 0, 0.35)
    c.rectangle(0, 0, W, H)
    c.set_source(g)
    c.fill()


def scene_frames(sc, W, H, idx):
    sc = normalize_scene(sc)
    n = max(1, int(round(sc["sure"] * FPS)))
    seed = 1000 + idx * 17
    bg = ARKA_PLANLAR[sc["arka_plan"]]
    nesne, kamera, chars = sc["nesne"], sc["kamera"], sc["karakterler"]
    S = W * 0.0042
    br = random.Random(seed + 5)
    blinks, tt = [], br.uniform(0.6, 2.0)
    while tt < sc["sure"] + 2:
        blinks.append(tt)
        tt += br.uniform(1.8, 4.2)
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    c = cairo.Context(surf)
    pan_dir = 1 if idx % 2 == 0 else -1
    for f in range(n):
        t = f / FPS
        gt = sc.get("t0", 0) + t
        c.save()
        pan = 0                                   # sabit kamera: titreme, zoom, kayma yok
        bg(c, W, H, gt, random.Random(seed), pan)
        if nesne:
            with Layer(c, pan, 0.6):
                prop(c, nesne, W * 0.5, H * 0.3, W / 820, gt)
        states = [char_state(ch, SLOTS[len(chars)][i], len(chars), W, H, S, t, gt, blinks, nesne, i)
                  for i, ch in enumerate(chars)]
        for stt in sorted(states, key=lambda s_: -s_["z"]):
            with Layer(c, pan, 1.0 - 0.4 * stt["z"]):
                st = stt["st"]
                if stt["under"] == "bed":
                    draw_bed(c, stt["x0"], stt["g"], st["s"], True, gt)
                else:
                    lift = min(1.0, abs(st["y"] - stt["g"]) / (30 * st["s"]))
                    shadow(c, st["x"], stt["g"] + 2, 15 * st["s"] * KARAKTERLER[stt["tip"]]["scale"] * (1 - 0.4 * lift),
                           3.2 * st["s"], 0.25 * (1 - 0.6 * lift))
                draw_character(c, stt["tip"], st)
                if stt["under"] == "bed":
                    draw_bed(c, stt["x0"], stt["g"], st["s"], False, gt)
        c.restore()
        vignette(c, W, H)
        surf.flush()
        yield bytes(surf.get_data())


def render(sahneler, cikti, ass=None, W=1080, H=1920, muzik=None):
    tmp = tempfile.mkdtemp()
    parcalar = []
    for i, sc in enumerate(sahneler):
        p = os.path.join(tmp, f"a{i}.wav")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(sc["ses_dosya"]), "-af",
                        f"apad,atrim=0:{sc['sure']:.3f}", "-ar", "44100", "-ac", "2", p], check=True)
        parcalar.append(p)
    liste = os.path.join(tmp, "l.txt")
    with open(liste, "w") as f:
        f.writelines(f"file '{p}'\n" for p in parcalar)
    ses = os.path.join(tmp, "ses.wav")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", liste, "-c", "copy", ses],
                   check=True)
    toplam = sum(sc["sure"] for sc in sahneler)
    girdiler = ["-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", ses]
    vf = "format=yuv420p" + (f",subtitles={ass}" if ass else "")
    if muzik:
        girdiler += ["-stream_loop", "-1", "-i", str(muzik)]
        fc = (f"[0:v]{vf}[v];[2:a]volume=0.10,afade=t=out:st={max(toplam - 1.5, 0):.2f}:d=1.5[m];"
              f"[1:a][m]amix=inputs=2:duration=first:dropout_transition=0,loudnorm=I=-14:TP=-1.5[a]")
    else:
        fc = f"[0:v]{vf}[v];[1:a]loudnorm=I=-14:TP=-1.5[a]"
    cmd = ["ffmpeg", "-y", "-v", "error", *girdiler, "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
           "-t", f"{toplam:.3f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(cikti)]
    pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t0 = 0.0
    for i, sc in enumerate(sahneler):
        sc["t0"] = t0
        for fr in scene_frames(sc, W, H, i):
            pr.stdin.write(fr)
        t0 += sc["sure"]
    pr.stdin.close()
    if pr.wait() != 0:
        raise RuntimeError("ffmpeg animasyon kodlaması başarısız")
    return toplam
