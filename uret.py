#!/usr/bin/env python3
"""
MERAK MAKİNESİ — Tam otomatik, ücretsiz animasyonlu YouTube Shorts üretim hattı.

Akış:  konu seç → senaryo (Gemini / Groq, ücretsiz) → sahne görselleri
       (Pollinations / Cloudflare, ücretsiz) → seslendirme (edge-tts, ücretsiz)
       → Ken Burns animasyonu + kelime kelime altyazı + müzik (ffmpeg)
       → Telegram'a gönder ve/veya YouTube'a zamanlanmış yükle.

Tüm ayarlar ortam değişkenleriyle (GitHub Secrets) verilir. Bkz. README.md
"""
import asyncio, json, math, os, random, re, subprocess, sys, time, urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

KOK = Path(__file__).resolve().parent
CIKTI = KOK / "cikti"
GECICI = CIKTI / "gecici"
W, H, FPS = 1080, 1920, 30

# ---------------------------------------------------------------- ayarlar
ENV = os.environ.get
DIL = (ENV("DIL") or "en").strip()          # en | tr
SES = ENV("SES") or {"tr": "tr-TR-AhmetNeural", "en": "en-US-AndrewNeural"}[DIL]
SES_HIZI = ENV("SES_HIZI", "+12%")
GEMINI_KEY, GEMINI_MODEL = ENV("GEMINI_API_KEY"), (ENV("GEMINI_MODEL") or "gemini-flash-latest")
GROQ_KEY, GROQ_MODEL = ENV("GROQ_API_KEY"), ENV("GROQ_MODEL", "llama-3.3-70b-versatile")
POLL_TOKEN = ENV("POLLINATIONS_TOKEN")
CF_ID, CF_TOKEN = ENV("CF_ACCOUNT_ID"), ENV("CF_API_TOKEN")
TG_TOKEN, TG_CHAT = ENV("TELEGRAM_BOT_TOKEN"), ENV("TELEGRAM_CHAT_ID")
YT_CID, YT_SECRET, YT_REFRESH = ENV("YT_CLIENT_ID"), ENV("YT_CLIENT_SECRET"), ENV("YT_REFRESH_TOKEN")
YT_GIZLILIK = ENV("YT_GIZLILIK", "private")    # private + yayin saati = zamanlanmış
YT_GECIKME_SAAT = float(ENV("YT_GECIKME_SAAT", "4"))  # onay için bekleme süresi
ELLE_KONU = (ENV("KONU") or "").strip()
GORSEL_STILI = ENV("GORSEL_STILI") or (
    "3D animated movie still, Pixar style, soft cinematic lighting, vibrant colors, "
    "expressive characters, highly detailed, depth of field, vertical 9:16 composition, "
    "no text, no letters, no watermark")


def log(*a):
    print(time.strftime("[%H:%M:%S]"), *a, flush=True)


def calistir(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("Komut hatası:\n" + " ".join(map(str, cmd)) + "\n" + r.stderr[-2000:])
    return r.stdout


def sure(dosya):
    return float(calistir(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                           "-of", "csv=p=0", str(dosya)]).strip())


# ---------------------------------------------------------------- 1) konu
def konu_sec():
    kullanilan = json.loads((KOK / "kullanilan.json").read_text("utf-8")) \
        if (KOK / "kullanilan.json").exists() else []
    if ELLE_KONU:
        return ELLE_KONU, kullanilan
    havuz = [s.strip() for s in (KOK / "konular.txt").read_text("utf-8").splitlines()
             if s.strip() and not s.startswith("#")]
    kalan = [k for k in havuz if k not in kullanilan]
    if kalan:
        return kalan[0], kullanilan
    log("Konu havuzu bitti, yapay zekâdan yeni konu isteniyor…")
    istem = (f"Generate ONE new, highly curiosity-driving YouTube Shorts topic in "
             f"{'Turkish' if DIL == 'tr' else 'English'} for an animated 'what if / how does it work / "
             f"weird true history' channel. Must not be any of: {kullanilan[-60:]}. "
             f'Return JSON: {{"konu": "..."}}')
    return llm_json(istem)["konu"], kullanilan


# ---------------------------------------------------------------- 2) senaryo
SENARYO_ISTEMI = """You are the head writer of a viral animated YouTube Shorts channel in the style of
Zack D. Films: short, punchy, 3D-animated curiosity stories (what-if scenarios, how things work,
bizarre-but-true history, the human body). Write ONE Short about this topic: "{konu}".

Rules:
- Narration language: {dil}. Natural, spoken, energetic. Total 95-130 words (~40-50 seconds).
- Scene 1 is the HOOK: a shocking question or statement the viewer cannot scroll past (max 12 words).
- Use a concrete protagonist ("you" or a named character) and a mini story with tension and a twist.
- Every claim must be factually accurate. No gore, no graphic injury, nothing distressing; keep it family-safe.
- The last scene's narration must flow seamlessly back into the first sentence so the Short loops.
- {sahne_sayisi} scenes. Each scene: 1-2 short sentences of narration + an English image prompt.
- Image prompts: describe ONE clear, dramatic, cinematic moment; the main character must be described
  exactly as in "karakter" every time it appears. No text in images.
- Vary the structure: do not always start with "What if". Surprise the viewer.

Return ONLY JSON with this schema:
{{"baslik": "catchy title in {dil}, max 70 chars, 1 emoji",
  "aciklama": "2-3 sentence description in {dil} + 3 hashtags",
  "etiketler": ["8-12 tags in {dil}"],
  "karakter": "English visual description of the main recurring character (age, hair, clothes, colors)",
  "sahneler": [{{"metin": "narration", "gorsel": "English image prompt"}}]}}"""


def llm_json(istem):
    hatalar = []
    if GEMINI_KEY:
        # Yoğunluk (503/429) olursa sırayla diğer ücretsiz modelleri dener
        modeller = list(dict.fromkeys([GEMINI_MODEL, "gemini-flash-latest", "gemini-flash-lite-latest",
                                       "gemini-2.5-flash", "gemini-2.5-flash-lite"]))
        for tur in range(3):
            for model in modeller:
                try:
                    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
                           f"{model}:generateContent?key={GEMINI_KEY}")
                    r = requests.post(url, timeout=120, json={
                        "contents": [{"parts": [{"text": istem}]}],
                        "generationConfig": {"temperature": 1.0, "responseMimeType": "application/json"}})
                    if r.status_code in (400, 401, 403):
                        raise RuntimeError(f"Gemini anahtarı reddedildi ({r.status_code}): {r.text[:300]}")
                    r.raise_for_status()
                    metin = r.json()["candidates"][0]["content"]["parts"][0]["text"]
                    log(f"Senaryo modeli: {model}")
                    return json.loads(metin)
                except RuntimeError:
                    raise
                except Exception as e:
                    hatalar.append(f"Gemini {model}: {str(e)[:120]}")
                    time.sleep(3)
            time.sleep(20 * (tur + 1))
    if GROQ_KEY:
        try:
            r = requests.post("https://api.groq.com/openai/v1/chat/completions", timeout=120,
                              headers={"Authorization": f"Bearer {GROQ_KEY}"},
                              json={"model": GROQ_MODEL, "temperature": 1.0,
                                    "response_format": {"type": "json_object"},
                                    "messages": [{"role": "user", "content": istem}]})
            r.raise_for_status()
            return json.loads(r.json()["choices"][0]["message"]["content"])
        except Exception as e:
            hatalar.append(f"Groq: {e}")
    raise RuntimeError("Senaryo üretilemedi (anahtar yok veya servisler yoğun).\n" + "\n".join(hatalar[-6:]))


def senaryo_yaz(konu):
    s = llm_json(SENARYO_ISTEMI.format(konu=konu, dil="Turkish" if DIL == "tr" else "English",
                                       sahne_sayisi=random.choice([6, 7, 8])))
    assert s.get("sahneler"), "Senaryo boş geldi"
    s["konu"] = konu
    return s


# ---------------------------------------------------------------- 3) görseller
def gorsel_uret(istem, hedef, tohum):
    tam = f"{istem}. {GORSEL_STILI}"
    # a) Pollinations (anahtarsız çalışır; token varsa limit yükselir)
    for deneme in range(4):
        try:
            url = ("https://image.pollinations.ai/prompt/" + urllib.parse.quote(tam) +
                   f"?width={W}&height={H}&seed={tohum}&model=flux&nologo=true&enhance=false")
            bas = {"Authorization": f"Bearer {POLL_TOKEN}"} if POLL_TOKEN else {}
            r = requests.get(url, headers=bas, timeout=180)
            if r.ok and r.headers.get("content-type", "").startswith("image") and len(r.content) > 20000:
                hedef.write_bytes(r.content)
                return
            log(f"  Pollinations {r.status_code}, tekrar deneniyor…")
        except Exception as e:
            log("  Pollinations hata:", e)
        time.sleep(15 * (deneme + 1))
    # b) Cloudflare Workers AI (günlük ücretsiz kota)
    if CF_ID and CF_TOKEN:
        import base64
        r = requests.post(
            f"https://api.cloudflare.com/client/v4/accounts/{CF_ID}/ai/run/@cf/black-forest-labs/flux-1-schnell",
            headers={"Authorization": f"Bearer {CF_TOKEN}"}, json={"prompt": tam, "steps": 8}, timeout=180)
        r.raise_for_status()
        hedef.write_bytes(base64.b64decode(r.json()["result"]["image"]))
        return
    raise RuntimeError("Görsel üretilemedi (Pollinations yanıt vermedi, Cloudflare ayarlı değil).")


def gorselleri_uret(s):
    tohum = random.randint(1, 10**6)          # aynı videoda tutarlı stil için ortak tohum
    karakter = s.get("karakter", "")
    for i, sahne in enumerate(s["sahneler"]):
        hedef = GECICI / f"sahne_{i:02d}.jpg"
        istem = sahne["gorsel"]
        if karakter and "character" not in istem.lower():
            istem += f". Main character: {karakter}"
        log(f"Görsel {i + 1}/{len(s['sahneler'])}")
        gorsel_uret(istem, hedef, tohum + i)
        sahne["gorsel_dosya"] = str(hedef)
        time.sleep(3)


# ---------------------------------------------------------------- 4) ses
async def _tts(metin, mp3):
    import edge_tts
    try:
        c = edge_tts.Communicate(metin, SES, rate=SES_HIZI, boundary="WordBoundary")
    except TypeError:                                # eski edge-tts sürümleri
        c = edge_tts.Communicate(metin, SES, rate=SES_HIZI)
    kelimeler = []
    with open(mp3, "wb") as f:
        async for p in c.stream():
            if p["type"] == "audio":
                f.write(p["data"])
            elif p["type"] == "WordBoundary":
                kelimeler.append((p["offset"] / 1e7, (p["offset"] + p["duration"]) / 1e7, p["text"]))
    return kelimeler


def seslendir(s):
    for i, sahne in enumerate(s["sahneler"]):
        mp3 = GECICI / f"ses_{i:02d}.mp3"
        for deneme in range(3):
            try:
                kel = asyncio.run(_tts(sahne["metin"], mp3))
                break
            except Exception as e:
                log("  TTS hata, tekrar:", e)
                time.sleep(5)
        else:
            raise RuntimeError("Seslendirme başarısız")
        d = sure(mp3)
        if not kel:                                  # zaman bilgisi gelmezse eşit dağıt
            ks = sahne["metin"].split()
            kel = [(d * j / len(ks), d * (j + 1) / len(ks), k) for j, k in enumerate(ks)]
        sahne.update(ses_dosya=str(mp3), sure=d + 0.25, kelimeler=kel)


# ---------------------------------------------------------------- 5) altyazı
def tr_buyuk(m):
    return m.replace("i", "İ").replace("ı", "I").upper() if DIL == "tr" else m.upper()


def ass_zaman(t):
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def altyazi_yaz(s, ass):
    satirlar = []
    ofset = 0.0
    for sahne in s["sahneler"]:
        kel = sahne["kelimeler"]
        for j in range(0, len(kel), 3):              # 3'er kelimelik parçalar
            grup = kel[j:j + 3]
            bas = ofset + grup[0][0]
            son = ofset + (kel[j + 3][0] if j + 3 < len(kel) else sahne["sure"])
            metin = " ".join(g[2] for g in grup)
            # ilk kelime sarı vurgulu → göz takibi artar
            parca = metin.split(" ", 1)
            vurgulu = r"{\c&H00E5FF&}" + tr_buyuk(parca[0]) + r"{\c&HFFFFFF&}" + \
                      (" " + tr_buyuk(parca[1]) if len(parca) > 1 else "")
            satirlar.append(f"Dialogue: 0,{ass_zaman(bas)},{ass_zaman(son)},Ana,,0,0,0,,"
                            r"{\fscx80\fscy80\t(0,90,\fscx100\fscy100)}" + vurgulu)
        ofset += sahne["sure"]
    ass.write_text(f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Ana,DejaVu Sans,86,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,7,3,2,80,80,620,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""" + "\n".join(satirlar) + "\n", "utf-8")


# ---------------------------------------------------------------- 6) montaj
def hareket(i, kare):
    """Her sahneye farklı kamera hareketi → şablon hissini kırar."""
    secenekler = [
        f"z='min(1+0.0012*on,1.18)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'",            # yakınlaş
        f"z='max(1.18-0.0012*on,1)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'",            # uzaklaş
        f"z='1.15':x='(iw-iw/zoom)*on/{kare}':y='ih/2-(ih/zoom/2)'",                         # sağa kay
        f"z='1.15':x='(iw-iw/zoom)*(1-on/{kare})':y='ih/2-(ih/zoom/2)'",                     # sola kay
        f"z='1.15':x='iw/2-(iw/zoom/2)':y='(ih-ih/zoom)*(1-on/{kare})'",                     # yukarı kay
    ]
    return secenekler[0] if i == 0 else random.choice(secenekler)


def sahne_klibi(i, sahne):
    kare = math.ceil(sahne["sure"] * FPS)
    klip = GECICI / f"klip_{i:02d}.mp4"
    vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
          f"scale={W * 2}:{H * 2},zoompan={hareket(i, kare)}:d={kare}:s={W}x{H}:fps={FPS},"
          f"eq=saturation=1.12:contrast=1.04,format=yuv420p")
    calistir(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", sahne["gorsel_dosya"],
              "-i", sahne["ses_dosya"], "-filter_complex", f"[0:v]{vf}[v];[1:a]apad,aresample=44100[a]",
              "-map", "[v]", "-map", "[a]", "-t", f"{sahne['sure']:.3f}", "-r", str(FPS),
              "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "160k",
              "-ar", "44100", "-ac", "2", str(klip)])
    return klip


def montaj(s, cikti_mp4):
    klipler = [sahne_klibi(i, sh) for i, sh in enumerate(s["sahneler"])]
    liste = GECICI / "liste.txt"
    liste.write_text("".join(f"file '{k}'\n" for k in klipler))
    ham = GECICI / "ham.mp4"
    calistir(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(liste),
              "-c", "copy", str(ham)])
    ass = GECICI / "altyazi.ass"
    altyazi_yaz(s, ass)
    toplam = sure(ham)
    muzikler = sorted((KOK / "muzik").glob("*.mp3")) if (KOK / "muzik").exists() else []
    vf = f"subtitles={ass}"
    if muzikler:
        muzik = random.choice(muzikler)
        calistir(["ffmpeg", "-y", "-loglevel", "error", "-i", str(ham), "-stream_loop", "-1",
                  "-i", str(muzik), "-filter_complex",
                  f"[0:v]{vf}[v];[1:a]volume=0.12,afade=t=out:st={max(toplam - 1.5, 0):.2f}:d=1.5[m];"
                  f"[0:a][m]amix=inputs=2:duration=first:dropout_transition=0,loudnorm=I=-14:TP=-1.5[a]",
                  "-map", "[v]", "-map", "[a]", "-t", f"{toplam:.3f}", "-c:v", "libx264",
                  "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "192k",
                  "-movflags", "+faststart", str(cikti_mp4)])
    else:
        calistir(["ffmpeg", "-y", "-loglevel", "error", "-i", str(ham), "-vf", vf,
                  "-af", "loudnorm=I=-14:TP=-1.5", "-c:v", "libx264", "-preset", "veryfast",
                  "-crf", "20", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(cikti_mp4)])
    return toplam


# ---------------------------------------------------------------- 7) yayın
def telegram_gonder(mp4, s, not_=""):
    if not (TG_TOKEN and TG_CHAT):
        return
    baslik = f"🎬 {s['baslik']}\n\n{s['aciklama']}\n\n{not_}"[:1000]
    with open(mp4, "rb") as f:
        r = requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendVideo", timeout=300,
                          data={"chat_id": TG_CHAT, "caption": baslik, "supports_streaming": "true"},
                          files={"video": (mp4.name, f, "video/mp4")})
    log("Telegram:", r.status_code, r.text[:200])


def telegram_mesaj(metin):
    if TG_TOKEN and TG_CHAT:
        requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", timeout=60,
                      data={"chat_id": TG_CHAT, "text": metin[:4000]})


def youtube_yukle(mp4, s):
    if not (YT_CID and YT_SECRET and YT_REFRESH):
        return None
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    kimlik = Credentials(None, refresh_token=YT_REFRESH, client_id=YT_CID, client_secret=YT_SECRET,
                         token_uri="https://oauth2.googleapis.com/token")
    yt = build("youtube", "v3", credentials=kimlik, cache_discovery=False)
    durum = {"privacyStatus": YT_GIZLILIK, "selfDeclaredMadeForKids": False,
             "containsSyntheticMedia": True}
    if YT_GIZLILIK == "private" and YT_GECIKME_SAAT > 0:
        yayin = datetime.now(timezone.utc) + timedelta(hours=YT_GECIKME_SAAT)
        durum["publishAt"] = yayin.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    govde = {"snippet": {"title": (s["baslik"] + " #shorts")[:100],
                         "description": s["aciklama"] + "\n\n#shorts",
                         "tags": s.get("etiketler", [])[:15], "categoryId": "27",
                         "defaultLanguage": DIL, "defaultAudioLanguage": DIL},
             "status": durum}
    istek = yt.videos().insert(part="snippet,status", body=govde,
                               media_body=MediaFileUpload(str(mp4), chunksize=-1, resumable=True))
    yanit = None
    while yanit is None:
        _, yanit = istek.next_chunk()
    return yanit["id"], durum.get("publishAt")


# ---------------------------------------------------------------- ana akış
def main():
    GECICI.mkdir(parents=True, exist_ok=True)
    konu, kullanilan = konu_sec()
    log("Konu:", konu)
    s = senaryo_yaz(konu)
    log("Başlık:", s["baslik"])
    gorselleri_uret(s)
    seslendir(s)
    damga = datetime.now().strftime("%Y%m%d_%H%M")
    mp4 = CIKTI / f"short_{damga}.mp4"
    toplam = montaj(s, mp4)
    log(f"Video hazır: {mp4.name} ({toplam:.1f} sn)")
    (CIKTI / f"short_{damga}.json").write_text(
        json.dumps({k: v for k, v in s.items()}, ensure_ascii=False, indent=2), "utf-8")

    not_ = ""
    try:
        sonuc = youtube_yukle(mp4, s)
        if sonuc:
            vid, ne_zaman = sonuc
            not_ = (f"✅ YouTube'a yüklendi: https://youtu.be/{vid}\n"
                    f"⏰ Yayın: {ne_zaman or 'hemen'} (UTC). Beğenmezsen YouTube Studio'dan sil.")
    except Exception as e:
        not_ = f"⚠️ YouTube yüklemesi başarısız: {e}"
        log(not_)
    if not not_:
        not_ = "📲 YouTube uygulamasından Short olarak paylaş (başlık ve açıklama yukarıda)."
    telegram_gonder(mp4, s, not_)

    if not ELLE_KONU or konu not in kullanilan:
        kullanilan.append(konu)
        (KOK / "kullanilan.json").write_text(json.dumps(kullanilan, ensure_ascii=False, indent=1), "utf-8")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        telegram_mesaj(f"❌ Merak Makinesi hata verdi:\n{e}")
        raise
