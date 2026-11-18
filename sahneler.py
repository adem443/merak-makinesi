"""
Sahne kurucu: senaryodaki mekân tarifini (JSON) kodla çizilmiş, keskin bir arka plana çevirir.

Mekân biçimleri:
  {"tip": "ic",  "duvar": renk, "zemin": wood|tile|carpet|concrete|metal, "pencere": day|night|none,
   "esyalar": [iç eşya adları]}
  {"tip": "dis", "gok": day|sunset|night|storm|dawn, "uzak": uzak manzara, "zemin": zemin türü,
   "hava": none|rain|snow|fog, "esyalar": [dış eşya adları]}
  {"tip": "ozel", "ad": stomach|blood|brain|cells|orbit|airplane|cave|mars|moon|...hazır mekânlar}
"""
import math
import random

import cairo

from animasyon import (INK, ARKA_PLANLAR, Layer, box, ell, fs, glow, hx, ln, mix, poly, potted_plant,
                       room_shell, rrect, setc, subquad, vgrad, window)

# ============================================================ iç mekân eşyaları
# Her fonksiyon (c, x, y, k, t): x = orta, y = tabanın zemine değdiği nokta (duvar eşyalarında merkez),
# k = ölçek (1 = arka duvar önü).


def i_bed(c, x, y, k, t):
    box(c, (x - 170 * k, y - 90 * k, 340 * k, 70 * k), (0, -30 * k), "#4CC9F0", lw=3)
    rrect(c, x - 180 * k, y - 190 * k, 26 * k, 190 * k, 8)
    fs(c, "#8D5B3B", 3)
    rrect(c, x - 150 * k, y - 140 * k, 90 * k, 40 * k, 16)
    fs(c, "#FFFFFF", 3)
    ln(c, [(x - 160 * k, y - 20 * k), (x - 160 * k, y)], 8)
    ln(c, [(x + 160 * k, y - 20 * k), (x + 160 * k, y)], 8)


def i_hospital_bed(c, x, y, k, t):
    box(c, (x - 170 * k, y - 100 * k, 340 * k, 50 * k), (0, -26 * k), "#F1F3F5", lw=3)
    rrect(c, x - 150 * k, y - 145 * k, 90 * k, 34 * k, 14)
    fs(c, "#FFFFFF", 3)
    rrect(c, x - 30 * k, y - 125 * k, 190 * k, 30 * k, 10)
    fs(c, "#A9D6E5", 3)
    for xx in (-180, 172):
        ln(c, [(x + xx * k, y - 190 * k), (x + xx * k, y)], 7, "#ADB5BD")
    ln(c, [(x - 180 * k, y - 190 * k), (x - 180 * k + 0.1, y - 190 * k)], 12, "#ADB5BD")
    for xx in (-150, 150):
        ell(c, x + xx * k, y - 8 * k, 12 * k, 12 * k)
        fs(c, "#495057", 3)


def i_heart_monitor(c, x, y, k, t):
    ln(c, [(x, y), (x, y - 180 * k)], 8, "#6C757D")
    ln(c, [(x - 50 * k, y), (x + 50 * k, y)], 8, "#6C757D")
    rrect(c, x - 90 * k, y - 330 * k, 180 * k, 150 * k, 12)
    fs(c, "#212529", 4)
    pts = []
    for i in range(30):
        xx = x - 75 * k + i * 5 * k
        ph = (i * 0.21 - t * 1.4) % 1.0
        yy = y - 255 * k - (60 * k if 0.45 < ph < 0.5 else (-25 * k if 0.5 <= ph < 0.55 else 0))
        pts.append((xx, yy))
    ln(c, pts, 4, "#38B000")
    ell(c, x + 65 * k, y - 310 * k, 7 * k, 7 * k)
    fs(c, "#FF4D6D" if int(t * 2) % 2 else "#7A1F2B")


def i_iv_stand(c, x, y, k, t):
    ln(c, [(x, y), (x, y - 330 * k)], 6, "#ADB5BD")
    ln(c, [(x - 40 * k, y), (x + 40 * k, y)], 6, "#ADB5BD")
    ln(c, [(x - 30 * k, y - 330 * k), (x + 30 * k, y - 330 * k)], 6, "#ADB5BD")
    rrect(c, x - 2 * k, y - 320 * k, 44 * k, 70 * k, 12)
    fs(c, hx("#CAF0F8", 0.9), 3)
    ln(c, [(x + 20 * k, y - 250 * k), (x + 30 * k, y - 120 * k)], 3, "#90E0EF")


def i_sofa(c, x, y, k, t):
    rrect(c, x - 190 * k, y - 170 * k, 380 * k, 100 * k, 30)
    fs(c, "#E76F51", 3)
    rrect(c, x - 200 * k, y - 100 * k, 400 * k, 80 * k, 24)
    fs(c, "#F4A261", 3)
    for xx in (-215, 175):
        rrect(c, x + xx * k, y - 140 * k, 40 * k, 120 * k, 18)
        fs(c, "#E76F51", 3)
    ln(c, [(x, y - 100 * k), (x, y - 25 * k)], 3, "#E76F51")


def i_tv(c, x, y, k, t):
    box(c, (x - 160 * k, y - 80 * k, 320 * k, 80 * k), (0, -20 * k), "#6D4C41", lw=3)
    rrect(c, x - 170 * k, y - 300 * k, 340 * k, 200 * k, 10)
    fs(c, "#212529", 4)
    rrect(c, x - 155 * k, y - 287 * k, 310 * k, 174 * k, 4)
    g = cairo.LinearGradient(0, y - 287 * k, 0, y - 113 * k)
    g.add_color_stop_rgba(0, *hx("#4CC9F0"))
    g.add_color_stop_rgba(1, *hx("#7209B7"))
    c.set_source(g)
    c.fill()
    glow(c, x, y - 200 * k, 260 * k, "#4CC9F0", 0.15)


def i_desk_computer(c, x, y, k, t):
    box(c, (x - 170 * k, y - 140 * k, 340 * k, 26 * k), (0, -26 * k), "#B5651D", lw=3)
    for xx in (-155, 145):
        ln(c, [(x + xx * k, y - 114 * k), (x + xx * k, y)], 9)
    rrect(c, x - 90 * k, y - 300 * k, 180 * k, 120 * k, 8)
    fs(c, "#212529", 4)
    rrect(c, x - 80 * k, y - 290 * k, 160 * k, 100 * k, 4)
    fs(c, "#90E0EF")
    for i in range(3):
        ln(c, [(x - 65 * k, y - 270 * k + i * 25 * k), (x + (10 + 15 * ((i + int(t * 2)) % 3)) * k, y - 270 * k + i * 25 * k)],
           5, (1, 1, 1, 0.9))
    ln(c, [(x, y - 180 * k), (x, y - 166 * k)], 10)
    rrect(c, x - 60 * k, y - 172 * k, 120 * k, 12 * k, 4)
    fs(c, "#495057", 2)


def i_bookshelf(c, x, y, k, t):
    rrect(c, x - 110 * k, y - 360 * k, 220 * k, 360 * k, 6)
    fs(c, "#8D5B3B", 4)
    rnd = random.Random(int(x))
    for r in range(4):
        yy = y - 350 * k + r * 88 * k
        ln(c, [(x - 100 * k, yy + 82 * k), (x + 100 * k, yy + 82 * k)], 5, "#5C3D2E")
        xx = x - 95 * k
        while xx < x + 85 * k:
            w = rnd.randint(14, 26) * k
            h = rnd.randint(50, 76) * k
            rrect(c, xx, yy + 80 * k - h, w, h, 2)
            fs(c, rnd.choice(["#E63946", "#457B9D", "#F4A261", "#2A9D8F", "#8338EC", "#FFB703"]), 2)
            xx += w + 3 * k


def i_fridge(c, x, y, k, t):
    rrect(c, x - 80 * k, y - 380 * k, 160 * k, 380 * k, 14)
    fs(c, "#F8F9FA", 4)
    ln(c, [(x - 80 * k, y - 250 * k), (x + 80 * k, y - 250 * k)], 3)
    rrect(c, x + 50 * k, y - 340 * k, 9 * k, 60 * k, 4)
    fs(c, "#ADB5BD", 2)
    rrect(c, x + 50 * k, y - 220 * k, 9 * k, 80 * k, 4)
    fs(c, "#ADB5BD", 2)


def i_stove(c, x, y, k, t):
    box(c, (x - 110 * k, y - 180 * k, 220 * k, 180 * k), (0, -24 * k), "#DEE2E6", top_fill="#343A40", lw=3)
    rrect(c, x - 80 * k, y - 130 * k, 160 * k, 90 * k, 6)
    fs(c, "#212529", 3)
    ell(c, x - 30 * k, y - 204 * k, 50 * k, 12 * k)
    fs(c, "#495057", 3)
    for i in range(3):
        kk = (t * 0.6 + i / 3) % 1
        ell(c, x - 30 * k + 12 * math.sin(t * 2 + i), y - 230 * k - kk * 140 * k, (14 + kk * 18) * k, (10 + kk * 14) * k)
        c.set_source_rgba(1, 1, 1, 0.55 * (1 - kk))
        c.fill()


def i_kitchen_counter(c, x, y, k, t):
    box(c, (x - 200 * k, y - 170 * k, 400 * k, 170 * k), (0, -24 * k), "#84A59D", top_fill="#EDEDE9", lw=3)
    for i in range(3):
        rrect(c, x - 185 * k + i * 128 * k, y - 150 * k, 116 * k, 130 * k, 6)
        setc(c, "#52796F")
        c.set_line_width(3)
        c.stroke()
    ell(c, x + 110 * k, y - 205 * k, 30 * k, 26 * k)
    fs(c, "#E63946", 3)


def i_dining_table(c, x, y, k, t):
    box(c, (x - 180 * k, y - 130 * k, 360 * k, 20 * k), (0, -40 * k), "#B5651D", lw=3)
    for xx in (-160, 150):
        ln(c, [(x + xx * k, y - 110 * k), (x + xx * k, y)], 9)
    ell(c, x - 60 * k, y - 155 * k, 34 * k, 10 * k)
    fs(c, "#FFFFFF", 3)
    rrect(c, x + 50 * k, y - 200 * k, 26 * k, 50 * k, 6)
    fs(c, hx("#A8DADC", 0.85), 3)


def i_lockers(c, x, y, k, t):
    for i in range(4):
        xx = x - 180 * k + i * 90 * k
        rrect(c, xx, y - 360 * k, 86 * k, 360 * k, 4)
        fs(c, ("#4361EE", "#4895EF")[i % 2], 3)
        for j in range(3):
            ln(c, [(xx + 20 * k, y - 330 * k + j * 12 * k), (xx + 66 * k, y - 330 * k + j * 12 * k)], 3, (0, 0, 0, 0.35))
        rrect(c, xx + 66 * k, y - 200 * k, 8 * k, 26 * k, 3)
        fs(c, "#DEE2E6", 2)


def i_toilet(c, x, y, k, t):
    rrect(c, x - 55 * k, y - 260 * k, 110 * k, 110 * k, 10)
    fs(c, "#F8F9FA", 3)
    ell(c, x, y - 120 * k, 80 * k, 34 * k)
    fs(c, "#FFFFFF", 3)
    poly(c, [(x - 45 * k, y - 110 * k), (x + 45 * k, y - 110 * k), (x + 30 * k, y), (x - 30 * k, y)], "#F1F3F5", 3)


def i_bathtub(c, x, y, k, t):
    rrect(c, x - 220 * k, y - 140 * k, 440 * k, 120 * k, 50)
    fs(c, "#FFFFFF", 4)
    rrect(c, x - 200 * k, y - 140 * k, 400 * k, 26 * k, 12)
    fs(c, "#90E0EF")
    for i in range(5):
        ell(c, x - 120 * k + i * 60 * k, y - 150 * k - 10 * math.sin(t * 2 + i), 22 * k, 18 * k)
        fs(c, (1, 1, 1, 0.95), 2)
    ln(c, [(x + 190 * k, y - 140 * k), (x + 190 * k, y - 230 * k), (x + 150 * k, y - 230 * k)], 7, "#ADB5BD")


def i_sink_mirror(c, x, y, k, t):
    rrect(c, x - 90 * k, y - 470 * k, 180 * k, 200 * k, 40)
    fs(c, "#CAF0F8", 4)
    ln(c, [(x - 40 * k, y - 430 * k), (x - 10 * k, y - 460 * k)], 6, (1, 1, 1, 0.8))
    box(c, (x - 110 * k, y - 210 * k, 220 * k, 210 * k), (0, -22 * k), "#ADB5BD", top_fill="#FFFFFF", lw=3)
    ln(c, [(x, y - 232 * k), (x, y - 262 * k), (x + 20 * k, y - 262 * k)], 6, "#868E96")


def i_lab_bench(c, x, y, k, t):
    box(c, (x - 200 * k, y - 150 * k, 400 * k, 150 * k), (0, -26 * k), "#ADB5BD", top_fill="#F8F9FA", lw=3)
    for i, col in enumerate(("#F72585", "#06D6A0", "#FFD166")):
        xx = x - 120 * k + i * 110 * k
        poly(c, [(xx - 25 * k, y - 176 * k), (xx - 10 * k, y - 250 * k), (xx + 10 * k, y - 250 * k),
                 (xx + 25 * k, y - 176 * k)], hx(col, 0.85), 3)
        kk = (t * 0.7 + i * 0.3) % 1
        ell(c, xx, y - 260 * k - kk * 60 * k, 6 * k, 6 * k)
        c.set_source_rgba(*hx(col, 0.7 * (1 - kk)))
        c.fill()


def i_microscope(c, x, y, k, t):
    box(c, (x - 120 * k, y - 140 * k, 240 * k, 20 * k), (0, -24 * k), "#B5651D", lw=3)
    for xx in (-105, 100):
        ln(c, [(x + xx * k, y - 120 * k), (x + xx * k, y)], 8)
    rrect(c, x - 50 * k, y - 175 * k, 100 * k, 18 * k, 6)
    fs(c, "#343A40", 3)
    ln(c, [(x + 20 * k, y - 170 * k), (x + 20 * k, y - 290 * k), (x - 20 * k, y - 330 * k)], 14, "#495057")
    ln(c, [(x - 20 * k, y - 330 * k), (x - 30 * k, y - 360 * k)], 18, "#212529")
    ln(c, [(x - 20 * k, y - 240 * k), (x - 20 * k, y - 205 * k)], 12, "#212529")


def i_server_rack(c, x, y, k, t):
    for j in range(2):
        xx = x - 130 * k + j * 140 * k
        rrect(c, xx, y - 400 * k, 120 * k, 400 * k, 6)
        fs(c, "#212529", 3)
        for r in range(10):
            yy = y - 385 * k + r * 38 * k
            rrect(c, xx + 10 * k, yy, 100 * k, 28 * k, 3)
            fs(c, "#343A40")
            on = (int(t * 6) + r + j * 3) % 4 != 0
            ell(c, xx + 95 * k, yy + 14 * k, 4 * k, 4 * k)
            fs(c, "#38B000" if on else "#FFB703")


def i_shop_shelf(c, x, y, k, t):
    rrect(c, x - 200 * k, y - 320 * k, 400 * k, 320 * k, 6)
    fs(c, "#DEE2E6", 4)
    rnd = random.Random(int(x) + 3)
    for r in range(4):
        yy = y - 310 * k + r * 78 * k
        ln(c, [(x - 190 * k, yy + 72 * k), (x + 190 * k, yy + 72 * k)], 5, "#868E96")
        xx = x - 185 * k
        while xx < x + 160 * k:
            w = rnd.randint(28, 42) * k
            h = rnd.randint(40, 62) * k
            rrect(c, xx, yy + 70 * k - h, w, h, 4)
            fs(c, rnd.choice(["#E63946", "#FFB703", "#2A9D8F", "#3A86FF", "#FB5607", "#8338EC"]), 2)
            xx += w + 6 * k


def i_cash_counter(c, x, y, k, t):
    box(c, (x - 170 * k, y - 150 * k, 340 * k, 150 * k), (0, -22 * k), "#FB8500", top_fill="#FFE8D6", lw=3)
    box(c, (x + 30 * k, y - 230 * k, 110 * k, 58 * k), (0, -14 * k), "#495057", lw=3)
    rrect(c, x + 45 * k, y - 220 * k, 80 * k, 26 * k, 3)
    fs(c, "#38B000")


def i_wardrobe(c, x, y, k, t):
    rrect(c, x - 120 * k, y - 400 * k, 240 * k, 400 * k, 8)
    fs(c, "#A47148", 4)
    ln(c, [(x, y - 390 * k), (x, y - 10 * k)], 3)
    for xx in (-16, 10):
        rrect(c, x + xx * k, y - 230 * k, 6 * k, 40 * k, 3)
        fs(c, "#FFD166", 2)


def i_washing_machine(c, x, y, k, t):
    rrect(c, x - 90 * k, y - 220 * k, 180 * k, 220 * k, 12)
    fs(c, "#F8F9FA", 4)
    ell(c, x, y - 100 * k, 58 * k, 58 * k)
    fs(c, "#ADB5BD", 4)
    c.save()
    ell(c, x, y - 100 * k, 46 * k, 46 * k)
    c.clip()
    ell(c, x, y - 100 * k, 46 * k, 46 * k)
    fs(c, "#90E0EF")
    a = t * 6
    ell(c, x + 20 * k * math.cos(a), y - 100 * k + 20 * k * math.sin(a), 16 * k, 10 * k)
    fs(c, "#F72585")
    c.restore()


def i_plant(c, x, y, k, t):
    potted_plant(c, x, y - 40 * k, 1.1 * k, t)


def i_lamp(c, x, y, k, t):
    glow(c, x, y - 330 * k, 200 * k, "#FFE066", 0.4)
    ln(c, [(x, y), (x, y - 300 * k)], 7)
    ln(c, [(x - 40 * k, y), (x + 40 * k, y)], 8)
    poly(c, [(x - 40 * k, y - 360 * k), (x + 40 * k, y - 360 * k), (x + 60 * k, y - 290 * k),
             (x - 60 * k, y - 290 * k)], "#FFD166", 3)


def i_door(c, x, y, k, t):
    rrect(c, x - 90 * k, y - 400 * k, 180 * k, 400 * k, 6)
    fs(c, "#8D5B3B", 4)
    rrect(c, x - 70 * k, y - 380 * k, 140 * k, 160 * k, 6)
    setc(c, "#6D4C41")
    c.set_line_width(4)
    c.stroke()
    ell(c, x + 60 * k, y - 200 * k, 9 * k, 9 * k)
    fs(c, "#FFD166", 2)


def i_telescope(c, x, y, k, t):
    for a in (-0.35, 0.0, 0.35):
        ln(c, [(x, y - 150 * k), (x + 160 * k * math.sin(a), y)], 6)
    c.save()
    c.translate(x, y - 160 * k)
    c.rotate(-0.6)
    rrect(c, -40 * k, -30 * k, 220 * k, 60 * k, 20)
    fs(c, "#3A86FF", 3)
    rrect(c, 160 * k, -38 * k, 40 * k, 76 * k, 10)
    fs(c, "#212529", 3)
    c.restore()


def i_piano(c, x, y, k, t):
    box(c, (x - 170 * k, y - 300 * k, 340 * k, 300 * k), (0, -20 * k), "#212529", lw=3)
    rrect(c, x - 160 * k, y - 170 * k, 320 * k, 40 * k, 3)
    fs(c, "#FFFFFF", 2)
    for i in range(14):
        ln(c, [(x - 160 * k + i * 23 * k, y - 170 * k), (x - 160 * k + i * 23 * k, y - 130 * k)], 1.5)
        if i % 7 not in (2, 6):
            rrect(c, x - 152 * k + i * 23 * k, y - 170 * k, 12 * k, 24 * k, 1)
            fs(c, INK)


# duvar eşyaları: merkez (x, y)
def w_window_day(c, x, y, k, t):
    window(c, x - 130 * k, y - 110 * k, 260 * k, 220 * k, t)


def w_window_night(c, x, y, k, t):
    window(c, x - 130 * k, y - 110 * k, 260 * k, 220 * k, t, night=True)


def w_painting(c, x, y, k, t):
    rrect(c, x - 110 * k, y - 80 * k, 220 * k, 160 * k, 6)
    fs(c, "#C9A227", 6)
    c.save()
    rrect(c, x - 96 * k, y - 66 * k, 192 * k, 132 * k, 3)
    c.clip()
    vgrad(c, x - 100 * k, y - 70 * k, 200 * k, 140 * k, "#90E0EF", "#CAF0F8")
    poly(c, [(x - 100 * k, y + 70 * k), (x - 30 * k, y - 20 * k), (x + 20 * k, y + 30 * k), (x + 60 * k, y - 10 * k),
             (x + 100 * k, y + 70 * k)], "#52B788")
    ell(c, x + 50 * k, y - 40 * k, 16 * k, 16 * k)
    fs(c, "#FFD166")
    c.restore()


def w_clock(c, x, y, k, t):
    ell(c, x, y, 60 * k, 60 * k)
    fs(c, "#FFFFFF", 5)
    for i in range(12):
        a = i * math.pi / 6
        ln(c, [(x + 50 * k * math.sin(a), y - 50 * k * math.cos(a)), (x + 44 * k * math.sin(a), y - 44 * k * math.cos(a))], 3)
    ln(c, [(x, y), (x + 42 * k * math.sin(t * 2), y - 42 * k * math.cos(t * 2))], 3, "#E63946")
    ln(c, [(x, y), (x + 28 * k * math.sin(t * 0.2), y - 28 * k * math.cos(t * 0.2))], 5)


def w_chalkboard(c, x, y, k, t):
    rrect(c, x - 260 * k, y - 120 * k, 520 * k, 240 * k, 8)
    fs(c, "#2D6A4F", 10, "#8D5B3B")
    for i in range(3):
        ln(c, [(x - 220 * k, y - 70 * k + i * 55 * k), (x + (-40 + 50 * i) * k, y - 70 * k + i * 55 * k)], 5, (1, 1, 1, 0.85))
    ell(c, x + 150 * k, y, 45 * k, 45 * k)
    setc(c, (1, 1, 1, 0.85))
    c.set_line_width(5)
    c.stroke()


def w_whiteboard(c, x, y, k, t):
    rrect(c, x - 250 * k, y - 120 * k, 500 * k, 240 * k, 8)
    fs(c, "#FFFFFF", 6, "#8D99AE")
    pts = [(x - 200 * k + i * 30 * k, y + 60 * k - (i ** 1.4) * 6 * k) for i in range(13)]
    ln(c, pts, 5, "#3A86FF")
    ln(c, [(x - 210 * k, y + 70 * k), (x + 200 * k, y + 70 * k)], 3, "#495057")
    ln(c, [(x - 210 * k, y + 70 * k), (x - 210 * k, y - 90 * k)], 3, "#495057")


def w_shelf_books(c, x, y, k, t):
    rrect(c, x - 170 * k, y + 30 * k, 340 * k, 14 * k, 4)
    fs(c, "#8D5B3B", 3)
    rnd = random.Random(int(x) + 7)
    xx = x - 160 * k
    while xx < x + 140 * k:
        w, h = rnd.randint(20, 32) * k, rnd.randint(55, 85) * k
        rrect(c, xx, y + 30 * k - h, w, h, 3)
        fs(c, rnd.choice(["#E63946", "#457B9D", "#F4A261", "#2A9D8F", "#8338EC"]), 2)
        xx += w + 4 * k


def w_screen(c, x, y, k, t):
    glow(c, x, y, 330 * k, "#4CC9F0", 0.2)
    rrect(c, x - 230 * k, y - 130 * k, 460 * k, 260 * k, 10)
    fs(c, "#1B263B", 5)
    pts = [(x - 200 * k + i * 20 * k, y + 50 * k * math.sin(i * 0.5 + t * 3)) for i in range(21)]
    ln(c, pts, 5, "#06D6A0")


def w_poster(c, x, y, k, t):
    rrect(c, x - 80 * k, y - 110 * k, 160 * k, 220 * k, 4)
    fs(c, "#FFFFFF", 3)
    ell(c, x, y - 20 * k, 45 * k, 45 * k)
    fs(c, "#FF006E")
    rrect(c, x - 55 * k, y + 50 * k, 110 * k, 16 * k, 4)
    fs(c, "#3A86FF")


def w_mirror(c, x, y, k, t):
    ell(c, x, y, 90 * k, 120 * k)
    fs(c, "#CAF0F8", 6, "#C9A227")
    ln(c, [(x - 40 * k, y - 40 * k), (x, y - 80 * k)], 6, (1, 1, 1, 0.8))


def w_map(c, x, y, k, t):
    rrect(c, x - 200 * k, y - 120 * k, 400 * k, 240 * k, 6)
    fs(c, "#A8DADC", 4)
    for dx, dy, rx, ry in ((-110, -30, 60, 40), (10, 10, 50, 70), (120, -40, 60, 30), (110, 60, 30, 20)):
        ell(c, x + dx * k, y + dy * k, rx * k, ry * k)
        fs(c, "#80B918")


IC_ZEMIN = {"wood": ("#B07D58", "#97664A"), "tile": ("#DEE2E6", "#CED4DA"), "carpet": ("#9D4EDD", "#8A3FC7"),
            "concrete": ("#ADB5BD", "#9AA1A9"), "metal": ("#8D99AE", "#7A8699")}
IC_DUVAR = {"white": "#F1F3F5", "cream": "#F3E9D2", "blue": "#BDE0FE", "green": "#D8F3DC", "pink": "#FFD6E0",
            "gray": "#CED4DA", "yellow": "#FFF3B0", "wood": "#C8A27C", "dark": "#495057", "orange": "#FFD8B1",
            "purple": "#E0C3FC"}
IC_ZEMIN_ESYA = {"bed": i_bed, "hospital_bed": i_hospital_bed, "heart_monitor": i_heart_monitor, "iv_stand": i_iv_stand,
                 "sofa": i_sofa, "tv": i_tv, "desk_computer": i_desk_computer, "bookshelf": i_bookshelf,
                 "fridge": i_fridge, "stove": i_stove, "kitchen_counter": i_kitchen_counter,
                 "dining_table": i_dining_table, "lockers": i_lockers, "toilet": i_toilet, "bathtub": i_bathtub,
                 "sink_mirror": i_sink_mirror, "lab_bench": i_lab_bench, "microscope": i_microscope,
                 "server_rack": i_server_rack, "shop_shelf": i_shop_shelf, "cash_counter": i_cash_counter,
                 "wardrobe": i_wardrobe, "washing_machine": i_washing_machine, "plant": i_plant, "lamp": i_lamp,
                 "door": i_door, "telescope": i_telescope, "piano": i_piano}
IC_DUVAR_ESYA = {"window": w_window_day, "window_night": w_window_night, "painting": w_painting, "clock": w_clock,
                 "chalkboard": w_chalkboard, "whiteboard": w_whiteboard, "shelf_books": w_shelf_books,
                 "screen": w_screen, "poster": w_poster, "mirror": w_mirror, "map": w_map}


def ic_mekan(spec):
    duvar = IC_DUVAR.get(spec.get("duvar"), "#F3E9D2")
    zemin, derz = IC_ZEMIN.get(spec.get("zemin"), IC_ZEMIN["wood"])
    yan = mix(duvar, "#000000", 0.1)
    tavan = mix(duvar, "#FFFFFF", 0.35)
    esyalar = [e for e in spec.get("esyalar", []) if e in IC_ZEMIN_ESYA or e in IC_DUVAR_ESYA][:6]
    if spec.get("pencere") == "day" and "window" not in esyalar:
        esyalar.insert(0, "window")
    elif spec.get("pencere") == "night" and "window_night" not in esyalar:
        esyalar.insert(0, "window_night")
    zemin_e = [e for e in esyalar if e in IC_ZEMIN_ESYA][:3]
    duvar_e = [e for e in esyalar if e in IC_DUVAR_ESYA][:3]

    def ciz(c, W, H, t, rnd, pan):
        with Layer(c, pan, 0.25):
            (L, T, R, B), lw_, rw_ = room_shell(c, W, H, duvar, yan, zemin, derz, tavan)
            if spec.get("zemin") == "tile":
                pass
            wx = {1: [0.5], 2: [0.3, 0.7], 3: [0.22, 0.5, 0.78]}
            for e, fx in zip(duvar_e, wx.get(len(duvar_e), [])):
                yy = T + (B - T) * (0.3 if zemin_e else 0.4)
                IC_DUVAR_ESYA[e](c, L + (R - L) * fx, yy, 1.0 if len(duvar_e) > 1 else 1.25, t)
            fxs = {1: [0.5], 2: [0.27, 0.73], 3: [0.18, 0.5, 0.82]}
            for e, fx in zip(zemin_e, fxs.get(len(zemin_e), [])):
                IC_ZEMIN_ESYA[e](c, L + (R - L) * fx, B + 12, 0.8 if len(zemin_e) == 3 else 1.0, t)
    return ciz


# ============================================================ dış mekân
GOK = {"day": ("#4DABF7", "#E7F5FF"), "sunset": ("#F25C54", "#FFD6A5"), "night": ("#0B132B", "#3A506B"),
       "storm": ("#343A40", "#868E96"), "dawn": ("#9D4EDD", "#FFC6FF")}
ZEMIN = {"grass": ("#74C365", "#5FAF55"), "sand": ("#F2CC8F", "#E0B573"), "snow": ("#F8F9FA", "#DEE2E6"),
         "road": ("#ADB5BD", "#495057"), "rock": ("#8D7B68", "#776655"), "dirt": ("#A47148", "#8D5B3B"),
         "lava": ("#3E2723", "#FF6D00"), "moon": ("#ADB5BD", "#868E96"), "mars": ("#C1440E", "#9A3412"),
         "ice": ("#D0F4FF", "#A9D6E5"), "water": ("#48CAE4", "#0096C7")}


def d_far(c, kind, W, H, hz, t, rnd, night):
    if kind in ("mountains", "snowy_mountains"):
        c.move_to(-300, hz)
        for i in range(9):
            pk = hz - 220 - (i * 67) % 160
            c.line_to(-300 + i * 220 + 110, pk)
            c.line_to(-300 + (i + 1) * 220, hz - 40)
        c.line_to(W + 300, hz)
        c.close_path()
        fs(c, "#5C677D" if night else "#8EA8C3")
        if kind == "snowy_mountains":
            for i in range(9):
                pk = hz - 220 - (i * 67) % 160
                cx_ = -300 + i * 220 + 110
                poly(c, [(cx_, pk), (cx_ - 45, pk + 60), (cx_ + 45, pk + 60)], "#FFFFFF")
    elif kind == "city":
        x = -200
        while x < W + 200:
            bw, bh = rnd.randint(60, 120), rnd.randint(120, 380)
            c.rectangle(x, hz - bh, bw, bh)
            fs(c, "#1C2541" if night else mix("#6C8EAD", "#FFFFFF", 0.25))
            for wy in range(int(hz - bh + 20), int(hz - 20), 36):
                for wx_ in range(int(x + 12), int(x + bw - 20), 28):
                    if rnd.random() < (0.45 if night else 0.3):
                        c.rectangle(wx_, wy, 14, 18)
                        fs(c, "#FFD166" if night else "#DDEBF7")
            x += bw + 6
    elif kind == "hills":
        for i, col in enumerate(("#95D5B2", "#74C69D")):
            ell(c, W * (0.2 + 0.6 * i), hz + 40, 650, 190)
            fs(c, mix(col, "#000000", 0.4) if night else col)
    elif kind == "forest":
        for row in range(2):
            for i in range(12):
                x = -100 + i * 110 + row * 55
                y0 = hz + row * 30
                poly(c, [(x - 55, y0), (x, y0 - 230 + row * 40), (x + 55, y0)],
                     "#1B4332" if (night or row == 0) else "#2D6A4F")
    elif kind == "sea":
        vgrad(c, -300, hz - 10, W + 600, 160, "#0096C7", "#48CAE4")
        for j in range(4):
            off = 40 * math.sin(t * 1.5 + j)
            ln(c, [(-200 + off, hz + 25 + j * 32), (W + 200 + off, hz + 25 + j * 32)], 3, (1, 1, 1, 0.5))
    elif kind == "pyramids":
        for px, ph in ((0.68, 380), (0.95, 260), (0.4, 210)):
            poly(c, [(W * px - ph, hz + 10), (W * px, hz + 10 - ph), (W * px + ph, hz + 10)], "#E9A44C", 4)
            poly(c, [(W * px, hz + 10 - ph), (W * px + ph, hz + 10), (W * px + ph * 0.3, hz + 10)], (0, 0, 0, 0.13))
    elif kind == "dunes":
        for i, col in enumerate(("#F6D8AE", "#EFC88B")):
            ell(c, W * (0.25 + 0.55 * i), hz + 30, 600, 150)
            fs(c, col)
    elif kind == "volcano":
        vx = W * 0.6
        for i in range(6):
            kk = (t * 0.22 + i / 6) % 1
            ell(c, vx + 30 * math.sin(i + t), hz - 450 - kk * 500, 60 + kk * 100, 45 + kk * 80)
            c.set_source_rgba(0.3, 0.27, 0.27, 0.7 * (1 - kk))
            c.fill()
        poly(c, [(vx - 420, hz + 10), (vx - 90, hz - 470), (vx + 90, hz - 470), (vx + 420, hz + 10)], "#3C2A21", 5)
        glow(c, vx, hz - 470, 200, "#FF4800", 0.6)
        poly(c, [(vx - 90, hz - 470), (vx + 90, hz - 470), (vx + 40, hz - 420), (vx - 40, hz - 420)], "#FF4800", 3)
    elif kind == "colosseum":
        cx_ = W * 0.5
        rrect(c, cx_ - 420, hz - 300, 840, 300, 10)
        fs(c, "#E9C46A", 4)
        for r in range(3):
            for i in range(10):
                rrect(c, cx_ - 395 + i * 80, hz - 280 + r * 95, 50, 70, 25)
                fs(c, "#B08968", 2)
    elif kind == "ice":
        for i in range(6):
            x = -100 + i * 230
            poly(c, [(x, hz), (x + 60, hz - 160 - (i * 37) % 80), (x + 170, hz - 60), (x + 200, hz)], "#CAF0F8", 3)
    elif kind == "farm":
        rrect(c, W * 0.55, hz - 220, 260, 220, 6)
        fs(c, "#C1121F", 4)
        poly(c, [(W * 0.55 - 20, hz - 220), (W * 0.55 + 130, hz - 330), (W * 0.55 + 280, hz - 220)], "#780000", 4)
        rrect(c, W * 0.55 + 90, hz - 120, 80, 120, 4)
        fs(c, "#FFFFFF", 3)
        for i in range(8):
            ln(c, [(-100 + i * 80, hz + 20), (-80 + i * 80, hz + 100)], 4, "#E9C46A")


def d_item(c, kind, x, y, k, t, night):
    if kind == "tree":
        rrect(c, x - 22 * k, y - 300 * k, 44 * k, 300 * k, 14)
        fs(c, "#8D5B3B", 4)
        sw = 5 * math.sin(t * 1.2 + x)
        for dx, dy, r in ((-75, -330, 95), (80, -320, 100), (0, -400, 130)):
            ell(c, x + (dx + sw) * k, y + dy * k, r * k, r * k)
            fs(c, "#2D6A4F" if dx else "#40916C", 4)
    elif kind == "pine":
        rrect(c, x - 16 * k, y - 80 * k, 32 * k, 80 * k, 8)
        fs(c, "#6D4C41", 3)
        for i in range(3):
            w, yy = (150 - i * 35) * k, y - (60 + i * 110) * k
            poly(c, [(x - w, yy), (x, yy - 170 * k), (x + w, yy)], "#2D6A4F", 4)
    elif kind == "palm":
        ln(c, [(x, y), (x + 30 * k, y - 200 * k), (x + 70 * k, y - 400 * k)], 22 * k, "#8D5B3B")
        for i in range(6):
            c.save()
            c.translate(x + 70 * k, y - 400 * k)
            c.rotate(i * math.pi / 3 + 0.05 * math.sin(t + i))
            c.move_to(0, 0)
            c.curve_to(60 * k, -40 * k, 140 * k, -30 * k, 200 * k, 10 * k)
            c.curve_to(140 * k, 0, 60 * k, 10 * k, 0, 0)
            fs(c, "#2D6A4F", 3)
            c.restore()
    elif kind == "cactus":
        rrect(c, x - 26 * k, y - 280 * k, 52 * k, 280 * k, 26)
        fs(c, "#52B788", 4)
        rrect(c, x + 20 * k, y - 210 * k, 60 * k, 26 * k, 13)
        fs(c, "#52B788", 4)
        rrect(c, x + 56 * k, y - 270 * k, 26 * k, 86 * k, 13)
        fs(c, "#52B788", 4)
    elif kind == "house":
        box(c, (x - 160 * k, y - 230 * k, 320 * k, 230 * k), (40 * k, -30 * k), "#F4A261", lw=4)
        poly(c, [(x - 185 * k, y - 230 * k), (x, y - 380 * k), (x + 185 * k, y - 230 * k)], "#9C6644", 4)
        rrect(c, x - 30 * k, y - 120 * k, 60 * k, 120 * k, 4)
        fs(c, "#6D4C41", 3)
        for xx in (-110, 60):
            rrect(c, x + xx * k, y - 190 * k, 50 * k, 50 * k, 4)
            fs(c, "#FFD166" if night else "#BDE0FE", 3)
    elif kind == "car":
        rrect(c, x - 140 * k, y - 80 * k, 280 * k, 60 * k, 20)
        fs(c, "#E63946", 4)
        poly(c, [(x - 80 * k, y - 80 * k), (x - 50 * k, y - 130 * k), (x + 50 * k, y - 130 * k), (x + 90 * k, y - 80 * k)],
             "#A8DADC", 4)
        for xx in (-85, 85):
            ell(c, x + xx * k, y - 20 * k, 30 * k, 30 * k)
            fs(c, "#2B2D42", 4)
    elif kind == "streetlamp":
        if night:
            poly(c, [(x - 10 * k, y - 400 * k), (x + 10 * k, y - 400 * k), (x + 160 * k, y), (x - 160 * k, y)],
                 (1, 0.9, 0.5, 0.12))
        ln(c, [(x, y), (x, y - 400 * k)], 12 * k, "#343A40")
        ell(c, x, y - 405 * k, 26 * k, 16 * k)
        fs(c, "#FFE066", 3)
    elif kind == "rock":
        ell(c, x, y - 40 * k, 110 * k, 60 * k)
        fs(c, "#868E96", 4)
        ell(c, x - 30 * k, y - 60 * k, 40 * k, 20 * k)
        fs(c, "#ADB5BD")
    elif kind == "fence":
        for i in range(-3, 4):
            rrect(c, x + i * 60 * k - 12 * k, y - 140 * k, 24 * k, 140 * k, 6)
            fs(c, "#A47148", 3)
        ln(c, [(x - 200 * k, y - 100 * k), (x + 200 * k, y - 100 * k)], 10 * k, "#8D5B3B")
    elif kind == "tent":
        poly(c, [(x - 170 * k, y), (x, y - 220 * k), (x + 170 * k, y)], "#FB8500", 4)
        poly(c, [(x - 40 * k, y), (x, y - 120 * k), (x + 40 * k, y)], "#6D4C41", 3)
    elif kind == "campfire":
        for a in (-0.5, 0.5):
            ln(c, [(x - 60 * k * math.cos(a), y - 5 * k), (x + 60 * k * math.cos(a), y - 25 * k)], 14 * k, "#6D4C41")
        f = 1 + 0.15 * math.sin(t * 12)
        glow(c, x, y - 60 * k, 220 * k, "#FF9E00", 0.4)
        poly(c, [(x - 40 * k, y - 20 * k), (x - 10 * k, y - 120 * k * f), (x + 10 * k, y - 70 * k),
                 (x + 25 * k, y - 140 * k * f), (x + 45 * k, y - 20 * k)], "#FF6D00", 3)
    elif kind == "snowman":
        for r, yy in ((70, -70), (52, -180), (38, -265)):
            ell(c, x, y + yy * k, r * k, r * k)
            fs(c, "#FFFFFF", 4)
        poly(c, [(x, y - 262 * k), (x + 40 * k, y - 255 * k), (x, y - 250 * k)], "#FB8500", 2)
        rrect(c, x - 40 * k, y - 330 * k, 80 * k, 30 * k, 4)
        fs(c, "#212529", 3)
    elif kind == "igloo":
        c.move_to(x - 170 * k, y)
        c.curve_to(x - 170 * k, y - 220 * k, x + 170 * k, y - 220 * k, x + 170 * k, y)
        c.close_path()
        fs(c, "#F1F3F5", 4)
        for i in range(1, 4):
            ln(c, [(x - 160 * k, y - i * 45 * k), (x + 160 * k, y - i * 45 * k)], 3, "#ADB5BD")
        c.move_to(x - 45 * k, y)
        c.curve_to(x - 45 * k, y - 90 * k, x + 45 * k, y - 90 * k, x + 45 * k, y)
        c.close_path()
        fs(c, "#495057", 3)
    elif kind == "flag":
        ln(c, [(x, y), (x, y - 360 * k)], 8 * k, "#ADB5BD")
        wv = 10 * math.sin(t * 4)
        poly(c, [(x, y - 360 * k), (x + 160 * k, y - 340 * k + wv), (x + 160 * k, y - 260 * k + wv), (x, y - 280 * k)],
             "#E63946", 3)
    elif kind == "sign":
        ln(c, [(x, y), (x, y - 220 * k)], 10 * k, "#6D4C41")
        rrect(c, x - 110 * k, y - 300 * k, 220 * k, 90 * k, 8)
        fs(c, "#FFD166", 4)
        poly(c, [(x - 20 * k, y - 275 * k), (x + 20 * k, y - 255 * k), (x - 20 * k, y - 235 * k)], INK)
    elif kind == "bench":
        box(c, (x - 140 * k, y - 80 * k, 280 * k, 24 * k), (24 * k, -16 * k), "#B5651D", lw=3)
        for xx in (-120, 120):
            ln(c, [(x + xx * k, y - 56 * k), (x + xx * k, y)], 8 * k)
    elif kind == "column":
        for xx in (-150, 0, 150):
            rrect(c, x + xx * k - 30 * k, y - 380 * k, 60 * k, 380 * k, 4)
            fs(c, "#F1E3D3", 3)
        rrect(c, x - 200 * k, y - 420 * k, 400 * k, 44 * k, 4)
        fs(c, "#E9D8C4", 3)
    elif kind == "rocket":
        c.save()
        c.translate(x, y)
        c.scale(k, k)
        poly(c, [(-60, 0), (-35, -90), (35, -90), (60, 0)], "#ADB5BD", 3)
        rrect(c, -40, -420, 80, 340, 40)
        fs(c, "#F1FAEE", 4)
        c.move_to(-40, -360)
        c.curve_to(-40, -470, 40, -470, 40, -360)
        fs(c, "#E63946", 4)
        ell(c, 0, -300, 20, 20)
        fs(c, "#A8DADC", 3)
        c.restore()
    elif kind == "windmill":
        poly(c, [(x - 50 * k, y), (x - 25 * k, y - 300 * k), (x + 25 * k, y - 300 * k), (x + 50 * k, y)], "#F1E3D3", 4)
        for i in range(4):
            a = t * 1.5 + i * math.pi / 2
            ln(c, [(x, y - 300 * k), (x + 180 * k * math.cos(a), y - 300 * k + 180 * k * math.sin(a))], 18 * k, "#ADB5BD")
    elif kind == "crater":
        ell(c, x, y - 10 * k, 160 * k, 40 * k)
        fs(c, (0, 0, 0, 0.25), 3)
    elif kind == "satellite_dish":
        ln(c, [(x, y), (x, y - 150 * k)], 12 * k, "#868E96")
        c.save()
        c.translate(x, y - 180 * k)
        c.rotate(-0.5)
        c.move_to(-110 * k, 0)
        c.curve_to(-80 * k, 90 * k, 80 * k, 90 * k, 110 * k, 0)
        c.close_path()
        fs(c, "#F8F9FA", 4)
        c.restore()


DIS_ESYA = ("tree", "pine", "palm", "cactus", "house", "car", "streetlamp", "rock", "fence", "tent", "campfire",
            "snowman", "igloo", "flag", "sign", "bench", "column", "rocket", "windmill", "crater", "satellite_dish")
UZAK = ("mountains", "snowy_mountains", "city", "hills", "forest", "sea", "pyramids", "dunes", "volcano",
        "colosseum", "ice", "farm", "none")


def weather(c, kind, W, H, t, rnd):
    if kind == "rain":
        c.set_source_rgba(0.75, 0.85, 1, 0.6)
        c.set_line_width(3)
        for i in range(90):
            x = (i * 97 + t * 260) % (W + 200) - 100
            y = (i * 211 + t * 1300) % (H + 100) - 50
            c.move_to(x, y)
            c.line_to(x - 12, y + 40)
        c.stroke()
    elif kind == "snow":
        for i in range(110):
            x = (i * 131 + 30 * math.sin(t + i)) % W
            y = (i * 173 + t * (90 + i % 5 * 20)) % (H + 40) - 20
            ell(c, x, y, 4 + i % 3 * 2, 4 + i % 3 * 2)
            c.set_source_rgba(1, 1, 1, 0.9)
            c.fill()
    elif kind == "fog":
        for i in range(5):
            x = ((t * 25 * (1 + i * 0.2) + i * 300) % (W + 800)) - 400
            ell(c, x, H * (0.45 + 0.08 * i), 420, 60)
            c.set_source_rgba(1, 1, 1, 0.22)
            c.fill()


def dis_mekan(spec):
    gok = spec.get("gok") if spec.get("gok") in GOK else "day"
    uzak = spec.get("uzak") if spec.get("uzak") in UZAK else "hills"
    zemin = spec.get("zemin") if spec.get("zemin") in ZEMIN else "grass"
    hava = spec.get("hava") if spec.get("hava") in ("rain", "snow", "fog") else None
    esyalar = [e for e in spec.get("esyalar", []) if e in DIS_ESYA][:4]
    night = gok in ("night", "storm")
    if gok == "storm" and not hava:
        hava = "rain"

    def ciz(c, W, H, t, rnd, pan):
        hz = H * 0.56
        top, bot = GOK[gok]
        vgrad(c, 0, 0, W, hz + 20, top, bot)
        if gok == "night":
            for i in range(70):
                x, y = rnd.random() * W, rnd.random() * hz * 0.7
                ell(c, x, y, 2.2, 2.2)
                c.set_source_rgba(1, 1, 1, 0.4 + 0.6 * abs(math.sin(t + i)))
                c.fill()
            glow(c, W * 0.78, H * 0.12, 200, "#F8F3D4", 0.35)
            ell(c, W * 0.78, H * 0.12, 60, 60)
            fs(c, "#F8F3D4")
        elif gok in ("day", "sunset", "dawn"):
            sx, sy = (W * 0.8, H * 0.11) if gok == "day" else (W * 0.5, hz - 60)
            glow(c, sx, sy, 230, "#FFF3BF", 0.7)
            ell(c, sx, sy, 70, 70)
            fs(c, "#FFE066" if gok == "day" else "#FFB703")
            for i in range(3):
                x = ((t * 15 * (1 + i * 0.3) + i * 400) % (W + 500)) - 250
                for dx, dy, r in ((0, 0, 44), (50, -15, 56), (106, 0, 40)):
                    ell(c, x + dx, H * (0.07 + 0.07 * i) + dy, r, r * 0.65)
                    c.set_source_rgba(1, 1, 1, 0.9)
                    c.fill()
        else:   # fırtına bulutları + şimşek
            for i in range(6):
                ell(c, i * 220 - 50, H * 0.08 + (i % 2) * 50, 200, 90)
                fs(c, "#495057")
            if int(t * 1.3) % 4 == 0 and (t * 1.3) % 1 < 0.12:
                c.rectangle(0, 0, W, H)
                c.set_source_rgba(1, 1, 1, 0.35)
                c.fill()
        if uzak != "none":
            d_far(c, uzak, W, H, hz, t, random.Random(7), night)
        z1, z2 = ZEMIN[zemin]
        if zemin == "water":
            vgrad(c, 0, hz, W, H - hz, z1, z2)
        else:
            c.rectangle(-10, hz, W + 20, H - hz + 10)
            fs(c, mix(z1, "#000000", 0.35) if night else z1)
            for j in range(6):
                yy = hz + (H - hz) * ((j + 1) / 7) ** 1.5
                ln(c, [(-20, yy), (W * 0.5, yy - 12), (W + 20, yy)], 3, mix(z2, "#000000", 0.3) if night else z2)
        if zemin == "road":
            vx = W / 2
            poly(c, [(vx - 25, hz), (vx + 25, hz), (W * 0.95, H + 10), (W * 0.05, H + 10)], "#495057")
            for j in range(7):
                k0, k1 = (j / 7) ** 2, ((j + 0.45) / 7) ** 2
                y0, y1 = hz + (H - hz) * k0, hz + (H - hz) * k1
                poly(c, [(vx - 2 - 14 * k0, y0), (vx + 2 + 14 * k0, y0), (vx + 2 + 14 * k1, y1), (vx - 2 - 14 * k1, y1)],
                     "#FFD43B")
        if zemin in ("moon", "mars"):
            for cx_, cy_, r in ((0.15, 0.66, 60), (0.62, 0.64, 40), (0.88, 0.72, 80), (0.3, 0.88, 110)):
                ell(c, W * cx_, H * cy_, r, r * 0.3)
                fs(c, (0, 0, 0, 0.18), 3)
        if zemin == "lava":
            for i in range(6):
                x = (i * 211) % W
                a = 0.5 + 0.5 * abs(math.sin(t * 2 + i))
                ln(c, [(x, H * 0.7 + i * 40), (x + 80, H * 0.72 + i * 40), (x + 140, H * 0.7 + i * 42)], 6,
                   hx("#FF6D00", a))
        # eşyalar: arka sıra (ufka yakın, küçük) ve yanlar
        yer = [(0.12, 0.0), (0.88, 0.0), (0.3, 0.55), (0.72, 0.55)]
        for e, (fx, z) in zip(esyalar, yer):
            y = hz + (H * 0.68 - hz) * (1 - z) + 10
            kk = 1.0 - 0.45 * z
            d_item(c, e, W * fx, y, kk, t, night)
        if hava:
            weather(c, hava, W, H, t, rnd)
        if night:
            c.rectangle(0, 0, W, H)
            c.set_source_rgba(0.05, 0.08, 0.2, 0.18)
            c.fill()
    return ciz


# ============================================================ özel mekânlar
def o_stomach(c, W, H, t, rnd, pan):
    vgrad(c, 0, 0, W, H, "#9D174D", "#F472B6")
    for i in range(7):
        y = H * (0.05 + i * 0.09)
        c.move_to(-50, y)
        for j in range(8):
            c.curve_to(j * 160 + 40, y - 40 + 10 * math.sin(t + i), j * 160 + 120, y + 40, (j + 1) * 160, y)
        setc(c, (1, 1, 1, 0.12))
        c.set_line_width(14)
        c.stroke()
    lvl = H * 0.66 + 10 * math.sin(t * 1.5)
    c.move_to(-20, lvl)
    for i in range(12):
        c.line_to(i * 100 + 50, lvl + 14 * math.sin(t * 2 + i))
    c.line_to(W + 20, H + 10)
    c.line_to(-20, H + 10)
    c.close_path()
    fs(c, "#B5E48C", 4)
    for i in range(14):
        bx = (i * 151) % W
        by = H - ((t * (40 + i * 5) + i * 90) % (H - lvl + 40))
        ell(c, bx, by, 10 + i % 3 * 5, 10 + i % 3 * 5)
        c.set_source_rgba(1, 1, 1, 0.5)
        c.set_line_width(3)
        c.stroke()


def o_blood(c, W, H, t, rnd, pan):
    vgrad(c, 0, 0, W, H, "#7F1D1D", "#DC2626")
    for i in range(16):
        x = ((t * (90 + i * 12) + i * 211) % (W + 300)) - 150
        y = H * (0.08 + (i * 0.061) % 0.85)
        r = 50 + (i % 4) * 14
        ell(c, x, y, r, r * 0.7)
        fs(c, "#EF4444", 4, "#7F1D1D")
        ell(c, x, y, r * 0.45, r * 0.3)
        fs(c, "#B91C1C")
    c.rectangle(0, H * 0.72, W, H * 0.3)
    c.set_source_rgba(0.5, 0.05, 0.05, 0.35)
    c.fill()


def o_brain(c, W, H, t, rnd, pan):
    vgrad(c, 0, 0, W, H, "#1E1B4B", "#4C1D95")
    pts = [(rnd.random() * W, rnd.random() * H * 0.7) for _ in range(18)]
    for i, (x, y) in enumerate(pts):
        for j in (1, 3):
            x2, y2 = pts[(i + j) % len(pts)]
            ln(c, [(x, y), (x2, y2)], 3, (0.75, 0.55, 1, 0.35))
        a = 0.5 + 0.5 * abs(math.sin(t * 3 + i))
        glow(c, x, y, 40, "#C4B5FD", 0.5 * a)
        ell(c, x, y, 12, 12)
        fs(c, "#E9D5FF")
    c.rectangle(0, H * 0.7, W, H * 0.3)
    fs(c, "#3B0764")


def o_cells(c, W, H, t, rnd, pan):
    vgrad(c, 0, 0, W, H, "#D9F99D", "#86EFAC")
    for i in range(10):
        x = (i * 271 + 20 * math.sin(t * 0.6 + i)) % W
        y = (i * 389) % int(H * 0.7)
        r = 90 + (i % 3) * 30
        ell(c, x, y, r, r * 0.85)
        fs(c, hx("#FFFFFF", 0.5), 4, "#16A34A")
        ell(c, x + 10, y - 5, r * 0.3, r * 0.3)
        fs(c, "#7C3AED", 3)


def o_orbit(c, W, H, t, rnd, pan):
    vgrad(c, 0, 0, W, H, "#03071E", "#0B132B")
    for i in range(120):
        ell(c, rnd.random() * W, rnd.random() * H, 2, 2)
        c.set_source_rgba(1, 1, 1, 0.4 + 0.6 * abs(math.sin(t + i)))
        c.fill()
    cx_, cy_, r = W / 2, H * 1.05, W * 0.95
    glow(c, cx_, cy_, r * 1.12, "#4CC9F0", 0.5)
    ell(c, cx_, cy_, r, r)
    fs(c, "#1E6091")
    c.save()
    ell(c, cx_, cy_, r, r)
    c.clip()
    off = (t * 15) % 600
    for k_ in (-600, 0, 600):
        for dx, dy, rx, ry in ((-300, -800, 260, 120), (150, -880, 200, 90), (420, -760, 220, 140)):
            ell(c, cx_ + dx + off + k_, cy_ + dy, rx, ry)
            fs(c, "#52B788")
    c.restore()


def o_airplane(c, W, H, t, rnd, pan):
    c.rectangle(0, 0, W, H)
    fs(c, "#E9ECEF")
    c.move_to(0, H * 0.06)
    c.curve_to(W * 0.3, -H * 0.02, W * 0.7, -H * 0.02, W, H * 0.06)
    c.line_to(W, 0)
    c.line_to(0, 0)
    c.close_path()
    fs(c, "#F8F9FA", 3)
    for side in (0, 1):
        for i in range(3):
            x = (W * 0.08 if side == 0 else W * 0.78) + 0
            y = H * (0.18 + i * 0.12)
            rrect(c, x, y, 110, 140, 50)
            fs(c, "#FFFFFF", 4)
            c.save()
            rrect(c, x + 14, y + 14, 82, 112, 40)
            c.clip()
            vgrad(c, x, y, 110, 140, "#4DABF7", "#E7F5FF")
            ell(c, x + 55 + ((t * 40 + i * 30) % 160) - 80, y + 70, 30, 18)
            fs(c, (1, 1, 1, 0.95))
            c.restore()
    poly(c, [(W * 0.3, H * 0.6), (W * 0.7, H * 0.6), (W + 50, H), (-50, H)], "#4361EE")
    for row in range(3):
        y = H * (0.5 + row * 0.12)
        k = 0.7 + row * 0.25
        for side in (-1, 1):
            x = W / 2 + side * (180 + row * 110)
            rrect(c, x - 70 * k, y - 160 * k, 140 * k, 200 * k, 26)
            fs(c, "#3A86FF", 4)
            rrect(c, x - 60 * k, y - 160 * k, 120 * k, 40 * k, 14)
            fs(c, "#F1F3F5", 3)


def o_cave(c, W, H, t, rnd, pan):
    c.rectangle(0, 0, W, H)
    fs(c, "#3F3A36")
    glow(c, W * 0.5, H * 0.5, W * 0.8, "#FFB703", 0.25)
    for i in range(9):
        x = i * 140 - 40
        poly(c, [(x, -10), (x + 70, 220 + (i * 53) % 160), (x + 140, -10)], "#57534E", 3)
    c.move_to(-20, H * 0.62)
    c.curve_to(W * 0.3, H * 0.58, W * 0.7, H * 0.64, W + 20, H * 0.6)
    c.line_to(W + 20, H + 10)
    c.line_to(-20, H + 10)
    c.close_path()
    fs(c, "#57534E", 4)
    for i, x in enumerate((W * 0.15, W * 0.85)):
        poly(c, [(x - 60, H * 0.68), (x, H * 0.5 - i * 40), (x + 60, H * 0.68)], "#78716C", 3)
    for i in range(5):
        x, y = W * (0.1 + i * 0.2), H * (0.25 + (i % 2) * 0.1)
        a = 0.5 + 0.5 * abs(math.sin(t * 2 + i))
        glow(c, x, y, 60, "#90E0EF", 0.35 * a)
        poly(c, [(x - 14, y + 20), (x, y - 30), (x + 14, y + 20)], "#90E0EF", 2)


def o_mars(c, W, H, t, rnd, pan):
    return dis_mekan({"gok": "sunset", "uzak": "mountains", "zemin": "mars", "esyalar": ["rock", "flag"]})(c, W, H, t, rnd, pan)


def o_moon(c, W, H, t, rnd, pan):
    ARKA_PLANLAR["space"](c, W, H, t, rnd, pan)


OZEL = {"stomach": o_stomach, "blood": o_blood, "brain": o_brain, "cells": o_cells, "orbit": o_orbit,
        "airplane": o_airplane, "cave": o_cave, "mars": o_mars, "moon": o_moon}
OZEL.update({k: v for k, v in ARKA_PLANLAR.items()})


def mekan_cizici(spec):
    """Mekân tarifinden çizim fonksiyonu döndürür; tanınmazsa None."""
    if not isinstance(spec, dict):
        return None
    tip = spec.get("tip")
    if tip == "ic":
        return ic_mekan(spec)
    if tip == "dis":
        return dis_mekan(spec)
    if tip == "ozel" and spec.get("ad") in OZEL:
        return OZEL[spec["ad"]]
    return None


ISTEM_SOZLUGU = f"""- INDOOR place: {{"tip": "ic", "duvar": {"|".join(IC_DUVAR)}, "zemin": {"|".join(IC_ZEMIN)},
   "pencere": day|night|none, "esyalar": up to 5 of [{", ".join(list(IC_ZEMIN_ESYA) + list(IC_DUVAR_ESYA))}]}}
- OUTDOOR place: {{"tip": "dis", "gok": {"|".join(GOK)}, "uzak": {"|".join(UZAK)}, "zemin": {"|".join(ZEMIN)},
   "hava": none|rain|snow|fog, "esyalar": up to 4 of [{", ".join(DIS_ESYA)}]}}
- SPECIAL place: {{"tip": "ozel", "ad": stomach (inside the body) | blood (inside a blood vessel) | brain (neurons) |
   cells (microscope view) | orbit (Earth from space) | airplane (inside a plane cabin) | cave | mars | moon |
   bedroom | kitchen | classroom | lab | street | park | space | ocean (underwater) | night | desert | volcano | beach}}"""
