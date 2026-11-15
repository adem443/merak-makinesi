"""
Merak Makinesi — 2D karakter animasyon motoru (tamamen kodla çizilir, ücretsiz, yerel).

Her şey vektörel olarak Cairo ile her karede yeniden çizilir:
- Karakter iskeleti: göz kırpma, sese göre konuşan ağız, ifadeler, kol pozları,
  yürüme, zıplama, titreme, nefes alma.
- Arka planlar: oda, şehir, uzay, okyanus, laboratuvar, park, gece, volkan, çöl
  (bulut, yıldız, kabarcık, duman gibi hareketli öğelerle).
- Nesneler: dünya, ay, roket, uçak, saat, şimşek, telefon, araba, atom.
- Kamera: sabit, yavaş yakınlaşma, ani yakınlaşma.

Kullanım:  render(sahneler, cikti_mp4, ass_dosyasi)
sahne = {"ses_dosya", "sure", "arka_plan", "ifade", "hareket", "nesne", "kamera", "ikinci"}
"""
import math
import random
import subprocess

import cairo
import numpy as np

FPS = 30
INK = (0.11, 0.11, 0.16)


def hx(h, a=1.0):
    h = h.lstrip("#")
    return (int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255, a)


def ease(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def lerp(a, b, t):
    return a + (b - a) * t


# ============================================================ yardımcı çizim
def fill_stroke(c, fill, lw=None, stroke=INK):
    c.set_source_rgba(*fill)
    if lw:
        c.fill_preserve()
        c.set_source_rgba(*stroke) if len(stroke) == 4 else c.set_source_rgb(*stroke)
        c.set_line_width(lw)
        c.stroke()
    else:
        c.fill()


def rrect(c, x, y, w, h, r):
    c.new_sub_path()
    c.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    c.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    c.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    c.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    c.close_path()


def ellipse(c, x, y, rx, ry):
    c.save()
    c.translate(x, y)
    c.scale(max(rx, 0.01), max(ry, 0.01))
    c.arc(0, 0, 1, 0, 2 * math.pi)
    c.restore()


def line(c, pts, lw, col=INK, cap=cairo.LINE_CAP_ROUND):
    c.set_line_cap(cap)
    c.set_line_join(cairo.LINE_JOIN_ROUND)
    c.move_to(*pts[0])
    for p in pts[1:]:
        c.line_to(*p)
    c.set_source_rgba(*(col if len(col) == 4 else (*col, 1)))
    c.set_line_width(lw)
    c.stroke()


def vgrad(c, x, y, w, h, top, bottom):
    g = cairo.LinearGradient(0, y, 0, y + h)
    g.add_color_stop_rgba(0, *hx(top))
    g.add_color_stop_rgba(1, *hx(bottom))
    c.rectangle(x, y, w, h)
    c.set_source(g)
    c.fill()


# ============================================================ karakterler
KARAKTERLER = {
    # kahraman: ampul kafalı "Curio" — kanalın maskotu
    "hero": dict(head="#FFC94A", body="#3D5AFE", pants="#263046", shoes="#F4F4F4", extra="spark"),
    "friend": dict(head="#FF8FA3", body="#16B79A", pants="#2E2A3F", shoes="#FFD166", extra="bun"),
    "scientist": dict(head="#B9E3FF", body="#FFFFFF", pants="#4A4E69", shoes="#2B2D42", extra="glasses"),
    "kid": dict(head="#C7F464", body="#FF6B35", pants="#1D3557", shoes="#FFFFFF", extra="cap"),
}

# kol pozları: (üst kol açısı, dirsek açısı) — 0 = aşağı, + = dışa/yukarı
POZLAR = {
    "idle": ((12, 8), (12, 8)),
    "explain": ((28, 55), (40, 75)),
    "wave": ((12, 8), (150, 25)),
    "point": ((12, 8), (95, 0)),
    "shrug": ((48, 100), (48, 100)),
    "hands_up": ((160, 10), (160, 10)),
    "think": ((40, -100), (-20, -150)),
    "hips": ((40, -100), (40, -100)),
    "cheer": ((135, -20), (135, -20)),
    "facepalm": ((12, 8), (-15, -160)),
}

IFADELER = {
    # kaş açısı (+ = iç uç aşağı, kızgın), kaş yükseklik, göz bebeği ölçeği, ağız türü, göz yüksekliği
    "neutral": (0, 0, 1.0, "smile_soft", 1.0),
    "happy": (-6, 1.0, 1.0, "smile", 0.9),
    "excited": (-10, 2.0, 1.1, "grin", 1.05),
    "shocked": (-14, 3.5, 0.7, "o", 1.25),
    "worried": (-18, 1.5, 0.9, "frown_wave", 1.05),
    "thinking": (8, 0.5, 0.95, "flat", 0.9),
    "sad": (-20, 0.5, 1.0, "frown", 0.95),
    "angry": (22, -1.0, 0.85, "frown", 0.85),
    "smug": (10, 0.0, 1.0, "smirk", 0.75),
}


def arm_points(side, upper, elbow, sh):
    a1 = math.radians(upper)
    ex = sh[0] + side * 14 * math.sin(a1)
    ey = sh[1] + 14 * math.cos(a1)
    a2 = math.radians(upper + elbow)
    hx_ = ex + side * 13 * math.sin(a2)
    hy = ey + 13 * math.cos(a2)
    return (sh, (ex, ey), (hx_, hy))


def draw_character(c, kind, st):
    """st: x, y, s, facing, expr, arms(L,R), mouth, eyes_open, look, leg, bob, lean, effects"""
    p = KARAKTERLER[kind]
    c.save()
    c.translate(st["x"], st["y"])
    c.scale(st["s"] * st["facing"], st["s"])
    c.rotate(math.radians(st.get("lean", 0)))
    lw = 2.3
    bob = st.get("bob", 0)

    # gölge
    c.save()
    ellipse(c, 0, 0.5, 17 - abs(bob) * 0.6, 3.2)
    c.set_source_rgba(0, 0, 0, 0.16)
    c.fill()
    c.restore()

    # bacaklar
    leg = st.get("leg", 0)
    for side, ph in ((-1, 1), (1, -1)):
        hip = (side * 6, -14 + bob)
        ang = math.radians(leg * ph)
        foot = (hip[0] + 14 * math.sin(ang), hip[1] + 14 * math.cos(ang))
        line(c, [hip, foot], 6.5, INK)
        line(c, [hip, foot], 4.2, hx(p["pants"]))
        ellipse(c, foot[0] + 2.2, foot[1] - 0.3, 5.2, 3.0)
        fill_stroke(c, hx(p["shoes"]), lw * 0.8)

    # arka kol (sol)
    sh_l, sh_r = (-13, -46 + bob), (13, -46 + bob)
    (ul, el), (ur, er) = st["arms"]
    for side, sh, (u, e) in ((-1, sh_l, (ul, el)),):
        pts = arm_points(side, u, e, sh)
        line(c, pts, 7.2, INK)
        line(c, pts, 4.8, hx(p["body"]))
        ellipse(c, pts[2][0], pts[2][1], 3.6, 3.6)
        fill_stroke(c, hx(p["head"]), lw * 0.8)

    # gövde
    c.save()
    c.translate(0, bob)
    c.move_to(-12, -51)
    c.curve_to(-17, -40, -17, -22, -15, -12)
    c.line_to(15, -12)
    c.curve_to(17, -22, 17, -40, 12, -51)
    c.curve_to(5, -54, -5, -54, -12, -51)
    c.close_path()
    fill_stroke(c, hx(p["body"]), lw)
    if kind == "scientist":   # önlük yakası ve düğmeler
        line(c, [(-5, -51), (0, -40), (5, -51)], 1.6)
        for yy in (-34, -26, -18):
            ellipse(c, 0, yy, 1.1, 1.1)
            fill_stroke(c, INK)
    else:                      # kapüşon cebi
        rrect(c, -8, -27, 16, 8, 3)
        c.set_source_rgba(0, 0, 0, 0.12)
        c.fill()
        line(c, [(-3, -50), (-3, -41)], 1.3, (1, 1, 1, 0.8))
        line(c, [(3, -50), (3, -41)], 1.3, (1, 1, 1, 0.8))
    c.restore()

    # baş
    hy = -72 + bob * 1.2
    eo = st.get("eyes_open", 1.0)
    brow_a, brow_up, pup, mouth_kind, eye_h = IFADELER[st["expr"]]

    if p["extra"] == "spark":     # ampul kıvrımı + parıltı
        t = st.get("t", 0)
        line(c, [(0, hy - 22), (2, hy - 27), (-1.5, hy - 30), (1.5, hy - 33)], 2.2)
        glow = 0.5 + 0.5 * math.sin(t * 5)
        ellipse(c, 1.5, hy - 35, 3.2 + glow * 0.6, 3.2 + glow * 0.6)
        fill_stroke(c, hx("#FFF3B0"), 1.6)
    if p["extra"] == "bun":
        ellipse(c, 0, hy - 23, 7, 6)
        fill_stroke(c, hx("#7B2D43"), lw)
    ellipse(c, 0, hy, 22, 21.5)
    fill_stroke(c, hx(p["head"]), lw)
    # yanak
    for sx in (-13, 13):
        ellipse(c, sx, hy + 6, 3.8, 2.3)
        c.set_source_rgba(1, 0.45, 0.45, 0.28)
        c.fill()
    if p["extra"] == "cap":
        c.move_to(-21, hy - 6)
        c.curve_to(-20, hy - 26, 20, hy - 26, 21, hy - 6)
        c.close_path()
        fill_stroke(c, hx("#E63946"), lw)
        rrect(c, 8, hy - 9, 20, 5, 2.5)
        fill_stroke(c, hx("#E63946"), lw)
    if p["extra"] == "glasses":
        for sx in (-8, 8):  # gri saç tutamları
            pass
        line(c, [(-20, hy - 12), (-24, hy - 18)], 3, hx("#9AA0A6"))
        line(c, [(20, hy - 12), (24, hy - 18)], 3, hx("#9AA0A6"))

    # gözler
    lx, ly = st.get("look", (0, 0))
    for sx in (-8, 8):
        ey = hy - 2
        ry = 7.5 * eye_h * eo
        ellipse(c, sx, ey, 6.0, max(ry, 0.6))
        fill_stroke(c, (1, 1, 1, 1), lw * 0.75)
        if eo > 0.25:
            ellipse(c, sx + lx * 1.8, ey + ly * 1.8, 3.1 * pup, 3.1 * pup * min(1, eo * 1.3))
            fill_stroke(c, INK)
            ellipse(c, sx + lx * 1.8 + 1.0, ey + ly * 1.8 - 1.2, 0.9, 0.9)
            fill_stroke(c, (1, 1, 1, 1))
    if p["extra"] == "glasses":
        for sx in (-8, 8):
            ellipse(c, sx, hy - 2, 7.8, 7.8)
            c.set_source_rgba(*INK, 1)
            c.set_line_width(1.6)
            c.stroke()
        line(c, [(-0.5, hy - 3), (0.5, hy - 3)], 1.6)

    # kaşlar
    for side in (-1, 1):
        bx, by = side * 8, hy - 13 - brow_up
        a = math.radians(brow_a) * side
        dx, dy = 4.6 * math.cos(a), 4.6 * math.sin(a)
        line(c, [(bx - dx, by + dy), (bx + dx, by - dy)], 2.6)

    # ağız
    my = hy + 9
    m = st.get("mouth", 0.0)
    if m > 0.06:
        w = 6.8 - m * 1.2 if mouth_kind != "grin" else 8
        h = 1.6 + 6.2 * m
        if mouth_kind == "o":
            w, h = 4.2 + m, 4.5 + 4 * m
        ellipse(c, 0, my + h * 0.25, w, h)
        fill_stroke(c, hx("#6B1D2E"), lw * 0.8)
        if h > 3.5:
            c.save()
            ellipse(c, 0, my + h * 0.25, w, h)
            c.clip()
            ellipse(c, 0, my + h * 1.05, w * 0.7, h * 0.5)
            c.set_source_rgba(*hx("#FF7A8A"))
            c.fill()
            c.restore()
    else:
        if mouth_kind in ("smile", "smile_soft"):
            depth = 4.5 if mouth_kind == "smile" else 2.8
            c.move_to(-6, my)
            c.curve_to(-3, my + depth, 3, my + depth, 6, my)
            c.set_line_width(2.2)
            c.set_source_rgba(*INK, 1)
            c.stroke()
        elif mouth_kind == "grin":
            c.move_to(-8, my - 1)
            c.curve_to(-5, my + 8, 5, my + 8, 8, my - 1)
            c.close_path()
            fill_stroke(c, hx("#6B1D2E"), lw * 0.8)
            rrect(c, -6, my - 1, 12, 2.6, 1)
            fill_stroke(c, (1, 1, 1, 1))
        elif mouth_kind == "o":
            ellipse(c, 0, my + 1.5, 4.0, 5.0)
            fill_stroke(c, hx("#6B1D2E"), lw * 0.8)
        elif mouth_kind == "frown":
            c.move_to(-5.5, my + 3)
            c.curve_to(-2.5, my - 1.5, 2.5, my - 1.5, 5.5, my + 3)
            c.set_line_width(2.2)
            c.set_source_rgba(*INK, 1)
            c.stroke()
        elif mouth_kind == "frown_wave":
            line(c, [(-6, my + 2), (-3, my), (0, my + 2), (3, my), (6, my + 2)], 2.0)
        elif mouth_kind == "smirk":
            c.move_to(-5, my + 1)
            c.curve_to(-1, my + 2, 3, my + 1, 6, my - 2.5)
            c.set_line_width(2.2)
            c.set_source_rgba(*INK, 1)
            c.stroke()
        else:
            line(c, [(-4.5, my + 1), (4.5, my + 1)], 2.2)

    # ön kol (sağ)
    pts = arm_points(1, ur, er, sh_r)
    line(c, pts, 7.2, INK)
    line(c, pts, 4.8, hx(p["body"]))
    ellipse(c, pts[2][0], pts[2][1], 3.6, 3.6)
    fill_stroke(c, hx(p["head"]), lw * 0.8)

    # efektler (karakterin yanında)
    for ef, k in st.get("effects", []):
        draw_effect(c, ef, k, hy, st.get("t", 0))
    c.restore()


def draw_effect(c, ef, k, hy, t):
    if k <= 0:
        return
    if ef == "!":
        s = ease(k * 3) * (1 + 0.08 * math.sin(t * 18))
        c.save()
        c.translate(26, hy - 26)
        c.scale(s, s)
        c.rotate(0.2)
        rrect(c, -2.4, -14, 4.8, 13, 2.4)
        fill_stroke(c, hx("#FF3B30"), 1.6)
        ellipse(c, 0, 4, 2.6, 2.6)
        fill_stroke(c, hx("#FF3B30"), 1.6)
        c.restore()
    elif ef == "?":
        c.save()
        c.translate(27, hy - 24 + 2 * math.sin(t * 3))
        c.scale(ease(k * 3), ease(k * 3))
        c.select_font_face("DejaVu Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        c.set_font_size(20)
        c.move_to(-6, 6)
        c.text_path("?")
        fill_stroke(c, hx("#7C4DFF"), 1.5)
        c.restore()
    elif ef == "sweat":
        yy = hy - 10 + (t * 14) % 10
        c.move_to(23, yy - 6)
        c.curve_to(27, yy, 27, yy + 4, 23, yy + 4)
        c.curve_to(19, yy + 4, 19, yy, 23, yy - 6)
        fill_stroke(c, hx("#7FD3FF"), 1.4)
    elif ef == "sparkle":
        for i, (sx, sy) in enumerate(((-30, hy - 20), (30, hy - 28), (34, hy + 4))):
            r = 3 + 2 * abs(math.sin(t * 4 + i * 2))
            c.save()
            c.translate(sx, sy)
            c.move_to(0, -r * 2)
            for j in range(4):
                a = j * math.pi / 2
                c.line_to(r * 0.45 * math.cos(a + math.pi / 4), r * 0.45 * math.sin(a + math.pi / 4))
                c.line_to(r * 2 * math.cos(a + math.pi / 2), r * 2 * math.sin(a + math.pi / 2))
            c.close_path()
            fill_stroke(c, hx("#FFD60A"))
            c.restore()
    elif ef == "speed":
        for i in range(3):
            yy = -60 + i * 18
            line(c, [(-30, yy), (-44 - 6 * math.sin(t * 20 + i), yy)], 2, (*INK[:3], 0.5))


# ============================================================ arka planlar
def bg_room(c, W, H, t, g, rnd):
    c.rectangle(0, 0, W, g)
    c.set_source_rgba(*hx("#F6D9B8"))
    c.fill()
    c.rectangle(0, g - 70, W, 70)
    c.set_source_rgba(*hx("#E8C29C"))
    c.fill()
    c.rectangle(0, g, W, H - g)
    c.set_source_rgba(*hx("#B98B64"))
    c.fill()
    for i in range(0, int(W), 140):
        line(c, [(i, g), (i - 60, H)], 2, hx("#A97C57"))
    # pencere
    wx, wy, ww, wh = W * 0.56, H * 0.14, W * 0.32, H * 0.22
    rrect(c, wx, wy, ww, wh, 10)
    fill_stroke(c, hx("#FFFFFF"), 8)
    c.save()
    rrect(c, wx + 10, wy + 10, ww - 20, wh - 20, 4)
    c.clip()
    vgrad(c, wx, wy, ww, wh, "#7EC8FF", "#CDEBFF")
    cx = wx + ((t * 25) % (ww + 200)) - 100
    for dx, dy, r in ((0, 60, 34), (38, 50, 42), (78, 64, 30)):
        ellipse(c, cx + dx, wy + dy, r, r * 0.7)
        c.set_source_rgba(1, 1, 1, 0.95)
        c.fill()
    c.restore()
    line(c, [(wx + ww / 2, wy), (wx + ww / 2, wy + wh)], 6, hx("#FFFFFF"))
    line(c, [(wx, wy + wh / 2), (wx + ww, wy + wh / 2)], 6, hx("#FFFFFF"))
    for sx in (wx - 40, wx + ww - 10):
        rrect(c, sx, wy - 30, 50, wh + 70, 20)
        fill_stroke(c, hx("#F28B9B"), 3)
    # raf ve kitaplar
    sx, sy = W * 0.07, H * 0.2
    rrect(c, sx, sy, W * 0.36, 14, 4)
    fill_stroke(c, hx("#8D5B3B"), 3)
    x = sx + 14
    for col in ("#E63946", "#457B9D", "#F4A261", "#2A9D8F", "#8338EC", "#FFB703"):
        h = 60 + rnd.randint(0, 40)
        rrect(c, x, sy - h, 30, h, 4)
        fill_stroke(c, hx(col), 3)
        x += 36
    # çerçeve
    rrect(c, W * 0.1, H * 0.29, W * 0.2, H * 0.11, 6)
    fill_stroke(c, hx("#FFFFFF"), 6)
    c.save()
    rrect(c, W * 0.1 + 10, H * 0.29 + 10, W * 0.2 - 20, H * 0.11 - 20, 3)
    c.clip()
    vgrad(c, 0, H * 0.29, W, H * 0.11, "#9AD0EC", "#E0F2FB")
    c.move_to(W * 0.1, H * 0.4)
    c.line_to(W * 0.17, H * 0.32)
    c.line_to(W * 0.24, H * 0.38)
    c.line_to(W * 0.3, H * 0.33)
    c.line_to(W * 0.3, H * 0.4)
    c.close_path()
    c.set_source_rgba(*hx("#52B788"))
    c.fill()
    c.restore()


def sky_clouds(c, W, H, t, top, bottom, g, speed=20, n=4, rnd=None):
    vgrad(c, 0, 0, W, g, top, bottom)
    for i in range(n):
        y = H * (0.08 + 0.09 * i)
        x = ((t * speed * (1 + i * 0.3) + i * W * 0.37) % (W + 400)) - 200
        for dx, dy, r in ((0, 0, 50), (55, -18, 62), (115, 0, 46)):
            ellipse(c, x + dx, y + dy, r, r * 0.68)
            c.set_source_rgba(1, 1, 1, 0.92)
            c.fill()


def bg_park(c, W, H, t, g, rnd):
    sky_clouds(c, W, H, t, "#6EC6FF", "#E3F6FF", g)
    ellipse(c, W * 0.82, H * 0.12, 70, 70)
    fill_stroke(c, hx("#FFD166"))
    for hxp, hc, r in ((0.2, "#95D5B2", 520), (0.85, "#74C69D", 600)):
        ellipse(c, W * hxp, g + 80, r, 260)
        c.set_source_rgba(*hx(hc))
        c.fill()
    # ağaç
    tx = W * 0.12
    rrect(c, tx - 22, g - 330, 44, 330, 14)
    fill_stroke(c, hx("#8D5B3B"), 4)
    sway = 6 * math.sin(t * 1.3)
    for dx, dy, r in ((0, -400, 120), (-80, -330, 90), (85, -330, 95)):
        ellipse(c, tx + dx + sway, g + dy, r, r)
        fill_stroke(c, hx("#40916C"), 4)
    c.rectangle(0, g, W, H - g)
    c.set_source_rgba(*hx("#7BC96F"))
    c.fill()
    for i in range(30):
        x = (i * 97) % W
        line(c, [(x, g + 40 + (i * 53) % 300), (x + 6, g + 22 + (i * 53) % 300)], 4, hx("#5FAF55"))


def bg_city(c, W, H, t, g, rnd):
    sky_clouds(c, W, H, t, "#8FD3FF", "#FFE8D6", g, n=3)
    x = -20
    while x < W:
        bw = rnd.randint(140, 230)
        bh = rnd.randint(int(H * 0.2), int(H * 0.42))
        col = rnd.choice(["#5E6472", "#6C757D", "#495867", "#577590", "#4D5B6A"])
        c.rectangle(x, g - bh, bw, bh)
        fill_stroke(c, hx(col), 4)
        for wy in range(int(g - bh + 30), int(g - 40), 55):
            for wx in range(int(x + 22), int(x + bw - 30), 46):
                c.rectangle(wx, wy, 24, 30)
                c.set_source_rgba(*hx("#FFE29A" if rnd.random() < 0.4 else "#A9C4D9"))
                c.fill()
        x += bw + 12
    c.rectangle(0, g, W, H - g)
    c.set_source_rgba(*hx("#9AA5B1"))
    c.fill()
    c.rectangle(0, g + 120, W, H - g)
    c.set_source_rgba(*hx("#3F4A56"))
    c.fill()
    off = (t * 300) % 200
    for i in range(-1, int(W / 200) + 2):
        rrect(c, i * 200 - off, g + 250, 110, 16, 8)
        c.set_source_rgba(*hx("#FFD166"))
        c.fill()


def bg_space(c, W, H, t, g, rnd):
    vgrad(c, 0, 0, W, H, "#070B1F", "#1E2A5A")
    for i in range(120):
        x, y = rnd.random() * W, rnd.random() * g
        a = 0.4 + 0.6 * abs(math.sin(t * (0.8 + rnd.random() * 2) + i))
        ellipse(c, x, y, 2.4, 2.4)
        c.set_source_rgba(1, 1, 1, a)
        c.fill()
    ellipse(c, W * 0.85, H * 0.1, 46, 46)
    fill_stroke(c, hx("#F28482"))
    c.save()
    c.translate(W * 0.85, H * 0.1)
    c.rotate(-0.3)
    ellipse(c, 0, 0, 80, 16)
    c.set_source_rgba(*hx("#F6BD60"))
    c.set_line_width(6)
    c.stroke()
    c.restore()
    # ay yüzeyi
    c.move_to(0, g)
    c.curve_to(W * 0.3, g - 40, W * 0.7, g - 40, W, g)
    c.line_to(W, H)
    c.line_to(0, H)
    c.close_path()
    fill_stroke(c, hx("#B8BCC6"), 5)
    for cx_, cy_, r in ((0.15, 120, 50), (0.55, 260, 70), (0.85, 160, 40), (0.35, 420, 60)):
        ellipse(c, W * cx_, g + cy_, r, r * 0.35)
        fill_stroke(c, hx("#9EA3AE"), 3)


def bg_ocean(c, W, H, t, g, rnd):
    vgrad(c, 0, 0, W, H, "#4CC9F0", "#0B3C78")
    for i in range(5):
        x = W * (0.1 + i * 0.22) + 40 * math.sin(t * 0.5 + i)
        c.move_to(x, 0)
        c.line_to(x + 90, 0)
        c.line_to(x + 220, g)
        c.line_to(x + 120, g)
        c.close_path()
        c.set_source_rgba(1, 1, 1, 0.06)
        c.fill()
    for i in range(18):
        bx = (i * 173) % W + 10 * math.sin(t * 2 + i)
        by = H - ((t * (60 + i * 7) + i * 140) % H)
        ellipse(c, bx, by, 9 + i % 4 * 3, 9 + i % 4 * 3)
        c.set_source_rgba(1, 1, 1, 0.5)
        c.set_line_width(3)
        c.stroke()
    c.rectangle(0, g, W, H - g)
    c.set_source_rgba(*hx("#E9D8A6"))
    c.fill()
    for i, sx in enumerate((0.06, 0.16, 0.82, 0.93)):
        x0 = W * sx
        pts = []
        for k in range(9):
            pts.append((x0 + 22 * math.sin(t * 1.6 + k * 0.7 + i), g - k * 55))
        line(c, pts, 18, hx("#2D6A4F"))


def bg_lab(c, W, H, t, g, rnd):
    c.rectangle(0, 0, W, g)
    c.set_source_rgba(*hx("#E7EEF5"))
    c.fill()
    rrect(c, W * 0.08, H * 0.1, W * 0.5, H * 0.2, 10)
    fill_stroke(c, hx("#FFFFFF"), 8, hx("#8D99AE"))
    for i in range(4):
        y = H * 0.14 + i * 55
        line(c, [(W * 0.13, y), (W * (0.3 + 0.05 * i), y)], 6, hx("#3A86FF"))
    ellipse(c, W * 0.47, H * 0.2, 50, 50)
    c.set_source_rgba(*hx("#EF476F"))
    c.set_line_width(6)
    c.stroke()
    rrect(c, W * 0.64, H * 0.24, W * 0.3, 14, 4)
    fill_stroke(c, hx("#8D99AE"), 3)
    for i, col in enumerate(("#06D6A0", "#FFD166", "#EF476F")):
        x = W * 0.67 + i * 100
        c.move_to(x, H * 0.24)
        c.line_to(x + 10, H * 0.24 - 80)
        c.line_to(x + 40, H * 0.24 - 80)
        c.line_to(x + 50, H * 0.24)
        c.close_path()
        fill_stroke(c, hx(col, 0.85), 4)
        by = H * 0.24 - 90 - ((t * 40 + i * 30) % 60)
        ellipse(c, x + 25, by, 7, 7)
        c.set_source_rgba(*hx(col, 0.7))
        c.fill()
    c.rectangle(0, g, W, H - g)
    c.set_source_rgba(*hx("#C5D0DB"))
    c.fill()
    for i in range(0, int(W), 120):
        line(c, [(i, g), (i, H)], 3, hx("#AEBBC8"))


def bg_night(c, W, H, t, g, rnd):
    vgrad(c, 0, 0, W, g, "#0D1B2A", "#415A77")
    for i in range(70):
        x, y = rnd.random() * W, rnd.random() * g * 0.7
        ellipse(c, x, y, 2.2, 2.2)
        c.set_source_rgba(1, 1, 1, 0.4 + 0.6 * abs(math.sin(t + i)))
        c.fill()
    ellipse(c, W * 0.8, H * 0.12, 70, 70)
    fill_stroke(c, hx("#F8F3D4"))
    ellipse(c, W * 0.8 + 30, H * 0.12 - 15, 60, 60)
    c.set_source_rgba(*hx("#1B2C40"))
    c.fill()
    x = 0
    while x < W:
        bw = rnd.randint(160, 260)
        bh = rnd.randint(160, 300)
        c.rectangle(x, g - bh, bw, bh)
        fill_stroke(c, hx("#1B263B"), 3)
        c.move_to(x - 15, g - bh)
        c.line_to(x + bw / 2, g - bh - 90)
        c.line_to(x + bw + 15, g - bh)
        c.close_path()
        fill_stroke(c, hx("#0D1B2A"), 3)
        c.rectangle(x + bw / 2 - 25, g - bh + 50, 50, 50)
        c.set_source_rgba(*hx("#FFD166"))
        c.fill()
        x += bw + 30
    c.rectangle(0, g, W, H - g)
    c.set_source_rgba(*hx("#2D4739"))
    c.fill()


def bg_volcano(c, W, H, t, g, rnd):
    vgrad(c, 0, 0, W, g, "#FF7B54", "#FFD8A8")
    vx = W * 0.62
    for i in range(6):
        k = (t * 0.25 + i / 6) % 1
        ellipse(c, vx + 30 * math.sin(i + t), g - 700 - k * 600, 60 + k * 90, 50 + k * 70)
        c.set_source_rgba(0.35, 0.33, 0.33, 0.7 * (1 - k))
        c.fill()
    c.move_to(vx - 500, g)
    c.line_to(vx - 110, g - 680)
    c.line_to(vx + 110, g - 680)
    c.line_to(vx + 500, g)
    c.close_path()
    fill_stroke(c, hx("#6D4C41"), 6)
    c.move_to(vx - 110, g - 680)
    for k in range(6):
        c.line_to(vx - 110 + k * 44, g - 680 + (60 + 30 * math.sin(t * 3 + k)) * (k % 2))
    c.line_to(vx + 110, g - 680)
    c.close_path()
    fill_stroke(c, hx("#FF4800"), 4)
    c.rectangle(0, g, W, H - g)
    c.set_source_rgba(*hx("#4E342E"))
    c.fill()


def bg_desert(c, W, H, t, g, rnd):
    vgrad(c, 0, 0, W, g, "#FFB703", "#FFE8B5")
    ellipse(c, W * 0.2, H * 0.12, 80, 80)
    fill_stroke(c, hx("#FFF3C4"))
    for px, ph, col in ((0.62, 520, "#E9A44C"), (0.9, 360, "#D98E3B"), (0.38, 300, "#D98E3B")):
        c.move_to(W * px - ph, g)
        c.line_to(W * px, g - ph)
        c.line_to(W * px + ph, g)
        c.close_path()
        fill_stroke(c, hx(col), 5)
        c.move_to(W * px, g - ph)
        c.line_to(W * px + ph, g)
        c.line_to(W * px + ph * 0.25, g)
        c.close_path()
        c.set_source_rgba(0, 0, 0, 0.12)
        c.fill()
    c.rectangle(0, g, W, H - g)
    c.set_source_rgba(*hx("#F2CC8F"))
    c.fill()


ARKA_PLANLAR = {"room": bg_room, "park": bg_park, "city": bg_city, "space": bg_space, "ocean": bg_ocean,
                "lab": bg_lab, "night": bg_night, "volcano": bg_volcano, "desert": bg_desert}


# ============================================================ nesneler
def prop(c, kind, x, y, s, t):
    c.save()
    c.translate(x, y + 10 * math.sin(t * 1.8))
    c.scale(s, s)
    if kind == "earth":
        ellipse(c, 0, 0, 60, 60)
        fill_stroke(c, hx("#4EA8DE"), 3)
        c.save()
        ellipse(c, 0, 0, 60, 60)
        c.clip()
        off = (t * 20) % 240
        for k in (-240, 0):
            for dx, dy, rx, ry in ((-30, -15, 26, 18), (25, 10, 22, 30), (-5, 35, 18, 10), (60, -30, 20, 14)):
                ellipse(c, dx + off + k, dy, rx, ry)
                c.set_source_rgba(*hx("#52B788"))
                c.fill()
        c.restore()
        ellipse(c, 0, 0, 60, 60)
        c.set_source_rgba(*INK, 1)
        c.set_line_width(3)
        c.stroke()
    elif kind == "moon":
        ellipse(c, 0, 0, 50, 50)
        fill_stroke(c, hx("#E5E5E5"), 3)
        for dx, dy, r in ((-15, -10, 10), (18, 12, 8), (5, -25, 6)):
            ellipse(c, dx, dy, r, r)
            fill_stroke(c, hx("#C4C4C4"))
    elif kind == "rocket":
        c.rotate(0.35)
        f = 1 + 0.25 * math.sin(t * 30)
        c.move_to(-12, 40)
        c.line_to(0, 40 + 34 * f)
        c.line_to(12, 40)
        fill_stroke(c, hx("#FF9F1C"), 2)
        rrect(c, -18, -40, 36, 82, 18)
        fill_stroke(c, hx("#F1FAEE"), 3)
        c.move_to(-18, -20)
        c.curve_to(-18, -60, 18, -60, 18, -20)
        fill_stroke(c, hx("#E63946"), 3)
        ellipse(c, 0, 0, 9, 9)
        fill_stroke(c, hx("#A8DADC"), 3)
    elif kind == "plane":
        c.translate(((t * 160) % 600) - 300, 0)
        rrect(c, -70, -12, 140, 24, 12)
        fill_stroke(c, hx("#F8F9FA"), 3)
        c.move_to(-10, 0)
        c.line_to(20, 40)
        c.line_to(35, 40)
        c.line_to(20, 0)
        fill_stroke(c, hx("#457B9D"), 3)
        c.move_to(-60, -10)
        c.line_to(-72, -36)
        c.line_to(-58, -36)
        c.line_to(-45, -10)
        fill_stroke(c, hx("#457B9D"), 3)
    elif kind == "clock":
        ellipse(c, 0, 0, 55, 55)
        fill_stroke(c, hx("#FFFFFF"), 5)
        for k in range(12):
            a = k * math.pi / 6
            line(c, [(46 * math.sin(a), -46 * math.cos(a)), (40 * math.sin(a), -40 * math.cos(a))], 3)
        a1, a2 = t * 6, t * 0.5
        line(c, [(0, 0), (38 * math.sin(a1), -38 * math.cos(a1))], 4, hx("#E63946"))
        line(c, [(0, 0), (26 * math.sin(a2), -26 * math.cos(a2))], 5)
    elif kind == "lightning":
        a = 0.6 + 0.4 * abs(math.sin(t * 12))
        c.move_to(10, -70)
        c.line_to(-25, 5)
        c.line_to(2, 5)
        c.line_to(-12, 70)
        c.line_to(30, -15)
        c.line_to(5, -15)
        c.close_path()
        fill_stroke(c, hx("#FFD60A", a), 3)
    elif kind == "phone":
        c.rotate(0.15 * math.sin(t * 2))
        rrect(c, -32, -60, 64, 120, 12)
        fill_stroke(c, hx("#22223B"), 3)
        rrect(c, -26, -50, 52, 96, 6)
        c.set_source_rgba(*hx("#8ECAE6"))
        c.fill()
        for k in range(3):
            rrect(c, -18, -40 + k * 28, 36, 18, 5)
            c.set_source_rgba(1, 1, 1, 0.85)
            c.fill()
    elif kind == "car":
        c.translate(((t * 120) % 500) - 250, 0)
        rrect(c, -80, -20, 160, 40, 14)
        fill_stroke(c, hx("#E63946"), 3)
        c.move_to(-45, -20)
        c.line_to(-25, -50)
        c.line_to(30, -50)
        c.line_to(50, -20)
        fill_stroke(c, hx("#A8DADC"), 3)
        for wx in (-48, 48):
            ellipse(c, wx, 22, 18, 18)
            fill_stroke(c, hx("#2B2D42"), 3)
    elif kind == "atom":
        for k in range(3):
            c.save()
            c.rotate(k * math.pi / 3 + t * 0.6)
            ellipse(c, 0, 0, 70, 24)
            c.set_source_rgba(*hx("#4CC9F0"))
            c.set_line_width(5)
            c.stroke()
            a = t * 3 + k * 2
            ellipse(c, 70 * math.cos(a), 24 * math.sin(a), 7, 7)
            fill_stroke(c, hx("#F72585"))
            c.restore()
        ellipse(c, 0, 0, 16, 16)
        fill_stroke(c, hx("#FFD60A"), 3)
    c.restore()


NESNELER = ("earth", "moon", "rocket", "plane", "clock", "lightning", "phone", "car", "atom")


# ============================================================ ses → ağız
def mouth_track(audio_path, n_frames):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(audio_path), "-ac", "1", "-ar", "16000",
                          "-f", "s16le", "-"], capture_output=True, check=True).stdout
    a = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768
    hop = 16000 // FPS
    vals = []
    for i in range(n_frames):
        seg = a[i * hop:(i + 1) * hop]
        vals.append(float(np.sqrt(np.mean(seg ** 2))) if len(seg) else 0.0)
    v = np.array(vals)
    if v.max() > 0:
        v = v / (np.percentile(v[v > 0], 90) + 1e-6)
    out, prev = [], 0.0
    for x in v:
        x = min(1.0, max(0.0, (x - 0.12) / 0.75))
        x = 0.6 * x + 0.4 * prev
        prev = x
        out.append(0.0 if x < 0.1 else 0.35 if x < 0.4 else 0.7 if x < 0.75 else 1.0)
    return out


# ============================================================ sahne zaman çizelgesi
VARSAYILAN_POZ = {"neutral": "explain", "happy": "explain", "excited": "cheer", "shocked": "hands_up",
                  "worried": "facepalm", "thinking": "think", "sad": "idle", "angry": "hips", "smug": "hips"}
HAREKET_POZ = {"wave": "wave", "point": "point", "shrug": "shrug", "hands_up": "hands_up", "think": "think",
               "hips": "hips", "cheer": "cheer", "facepalm": "facepalm", "explain": "explain"}
EFEKT = {"shocked": "!", "thinking": "?", "worried": "sweat", "excited": "sparkle"}


def scene_frames(sc, W, H, idx):
    """Bir sahnenin karelerini üretir (cairo ImageSurface verisi)."""
    n = max(1, int(round(sc["sure"] * FPS)))
    rnd_seed = 1000 + idx * 17
    mouth = mouth_track(sc["ses_dosya"], n)
    expr = sc.get("ifade", "neutral") if sc.get("ifade") in IFADELER else "neutral"
    act = sc.get("hareket", "idle")
    bg = ARKA_PLANLAR.get(sc.get("arka_plan"), bg_room)
    nesne = sc.get("nesne") if sc.get("nesne") in NESNELER else None
    ikinci = sc.get("ikinci") if isinstance(sc.get("ikinci"), dict) else None
    if ikinci and ikinci.get("tip") not in KARAKTERLER:
        ikinci = None
    kamera = sc.get("kamera", "push_in")
    g = H * 0.72
    tall = H > W
    S = (W * 0.0068 if tall else H * 0.0062) * (0.82 if ikinci else 1.0)
    pose_name = HAREKET_POZ.get(act, VARSAYILAN_POZ.get(expr, "explain"))
    blink_rng = random.Random(rnd_seed + 5)
    blinks, tt = [], blink_rng.uniform(0.6, 2.0)
    while tt < sc["sure"] + 1:
        blinks.append(tt)
        tt += blink_rng.uniform(1.8, 4.2)

    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    c = cairo.Context(surf)
    hero_x_target = W * (0.32 if ikinci else 0.5)
    for f in range(n):
        t = f / FPS
        gt = sc.get("t0", 0) + t
        c.save()
        # kamera
        if kamera == "punch":
            z = 1.0 + 0.18 * ease(t / 0.18) - 0.06 * ease((t - 0.18) / 0.5)
        elif kamera == "static":
            z = 1.0
        else:
            z = 1.0 + 0.07 * (t / max(sc["sure"], 0.1))
        fy = g - 380 * S / 7
        c.translate(W / 2, fy)
        c.scale(z, z)
        c.translate(-W / 2, -fy)
        if act == "shake" or (expr == "shocked" and t < 0.45):
            c.translate(8 * math.sin(t * 70), 4 * math.cos(t * 55))
        bg(c, W, H, gt, g, random.Random(rnd_seed))
        if nesne:
            px = W * (0.5 if not ikinci else 0.5)
            py = H * 0.2 if tall else H * 0.28
            prop(c, nesne, px, py, (W if tall else H) / 560, gt)

        # kahraman durumu
        x, leg, bob, lean, jump = hero_x_target, 0.0, 0.0, 0.0, 0.0
        if act == "walk_in":
            k = ease(t / 1.2)
            x = lerp(-W * 0.25, hero_x_target, k)
            if t < 1.2:
                leg = 28 * math.sin(t * 13)
                bob = -1.2 * abs(math.sin(t * 13))
        elif act == "walk":
            leg = 26 * math.sin(t * 11)
            bob = -1.2 * abs(math.sin(t * 11))
            x = hero_x_target + 40 * math.sin(t * 0.8)
        elif act == "jump":
            ph = (t % 1.1) / 1.1
            jump = -60 * S / 7 * math.sin(math.pi * min(1, ph / 0.45)) if ph < 0.45 else 0
            leg = 12 if ph < 0.45 else 0
        elif act == "float":
            jump = -40 * S / 7 * (1 + math.sin(t * 1.6))
            lean = 8 * math.sin(t * 1.1)
        bob += 0.6 * math.sin(gt * 2.4)
        talking = mouth[f] > 0
        # poz: başta nötrden hedef poza geçiş + konuşurken hafif jest
        k = ease(t / 0.3)
        (l0, r0), (l1, r1) = POZLAR["idle"], POZLAR[pose_name]
        wig = 8 * math.sin(gt * 3.1) if talking and pose_name in ("explain", "idle") else 0
        wav = 25 * math.sin(gt * 10) if pose_name == "wave" else 0
        arms = ((lerp(l0[0], l1[0], k) + wig * 0.5, lerp(l0[1], l1[1], k)),
                (lerp(r0[0], r1[0], k) - wig, lerp(r0[1], r1[1], k) + wav))
        blink = 1.0
        for b in blinks:
            d = t - b
            if 0 <= d < 0.14:
                blink = abs(d - 0.07) / 0.07
        look = (0.6 if ikinci else 0.25 * math.sin(gt * 0.7), -0.3 if nesne else 0.1)
        effects = [(EFEKT[expr], t)] if expr in EFEKT else []
        if act in ("walk_in", "walk") and t < 1.2:
            effects.append(("speed", 1))
        draw_character(c, "hero", dict(x=x, y=g + jump, s=S, facing=1, expr=expr, arms=arms,
                                       mouth=mouth[f], eyes_open=blink, look=look, leg=leg, bob=bob,
                                       lean=lean, effects=effects, t=gt))
        if ikinci:
            e2 = ikinci.get("ifade", "happy") if ikinci.get("ifade") in IFADELER else "happy"
            p2 = POZLAR[VARSAYILAN_POZ.get(e2, "idle")]
            b2 = 1.0
            for b in blinks:
                d = t - b - 0.9
                if 0 <= d < 0.14:
                    b2 = abs(d - 0.07) / 0.07
            draw_character(c, ikinci["tip"], dict(
                x=W * 0.72, y=g, s=S, facing=-1, expr=e2, arms=p2, mouth=0.0, eyes_open=b2,
                look=(0.6, 0), leg=0, bob=0.6 * math.sin(gt * 2.2 + 1), effects=[(EFEKT[e2], t)] if e2 in EFEKT else [],
                t=gt))
        c.restore()
        surf.flush()
        yield bytes(surf.get_data())


def render(sahneler, cikti, ass=None, W=1080, H=1920, muzik=None):
    import tempfile, os
    tmp = tempfile.mkdtemp()
    # sesleri birleştir (sahne süresine göre doldurulmuş)
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
