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
SENARYO_ISTEMI = """You are the head writer of a viral 2D-animated YouTube channel in the style of "The If Lab"
and Zack D. Films: punchy curiosity stories (what-if scenarios, how things work, bizarre-but-true history,
the human body). Write ONE vertical Short about this topic: "{konu}".

The video is a 2D cartoon. The star is CURIO, our mascot: a cheerful character with a round yellow
light-bulb head and a blue hoodie. Curio is the narrator AND the actor: he talks to the viewer
("you", "I") and acts out the story. Optional side characters: "friend" (pink-headed buddy),
"scientist" (glasses, lab coat), "kid" (red cap).

Rules:
- Narration language: {dil}. Natural, spoken, energetic, funny. Total 100-140 words (~45-55 seconds).
- Scene 1 is the HOOK: a shocking question or statement the viewer cannot scroll past (max 12 words).
- A mini story with tension, a surprising fact and a twist. Every claim must be factually accurate.
- No gore, no graphic injury, nothing distressing; family-safe.
- The last scene's narration must flow seamlessly back into the first sentence so the Short loops.
- {sahne_sayisi} scenes, 1-2 short sentences each. Change background, expression or action every scene.

For every scene choose ONLY from these values:
- "arka_plan": room | park | city | space | ocean | lab | night | volcano | desert
- "ifade" (Curio's face): neutral | happy | excited | shocked | worried | thinking | sad | angry | smug
- "hareket" (Curio's action): explain | wave | point | shrug | hands_up | think | hips | cheer |
  facepalm | walk_in | walk | jump | float | shake
- "nesne" (big animated object above Curio, or null): earth | moon | rocket | plane | clock |
  lightning | phone | car | atom | null
- "kamera": push_in | punch | static   (use "punch" for surprising moments)
- "ikinci": null, or {{"tip": "friend|scientist|kid", "ifade": "<one ifade value>"}} (max 2 scenes)

Return ONLY JSON with this schema:
{{"baslik": "catchy title in {dil}, max 70 chars, 1 emoji",
  "aciklama": "2-3 sentence description in {dil} + 3 hashtags",
  "etiketler": ["8-12 tags in {dil}"],
  "sahneler": [{{"metin": "narration", "arka_plan": "...", "ifade": "...", "hareket": "...",
                 "nesne": null, "kamera": "...", "ikinci": null}}]}}"""


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
    import animasyon as A
    for i, sh in enumerate(s["sahneler"]):
        if sh.get("arka_plan") not in A.ARKA_PLANLAR:
            sh["arka_plan"] = random.choice(list(A.ARKA_PLANLAR))
        if sh.get("ifade") not in A.IFADELER:
            sh["ifade"] = "neutral"
        if sh.get("nesne") not in A.NESNELER:
            sh["nesne"] = None
        if sh.get("kamera") not in ("push_in", "punch", "static"):
            sh["kamera"] = "punch" if i == 0 else "push_in"
        ik = sh.get("ikinci")
        if not (isinstance(ik, dict) and ik.get("tip") in A.KARAKTERLER and ik.get("tip") != "hero"):
            sh["ikinci"] = None
    s["konu"] = konu
    return s


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


PIPER_SES = {"en": "en_US-ryan-high", "tr": "tr_TR-dfki-medium"}


def _piper_yukle():
    """Yedek ses: Piper (açık kaynak, sunucuda yerel çalışır, internet servisi gerekmez)."""
    from piper import PiperVoice
    ad = ENV("PIPER_SES") or PIPER_SES[DIL]
    dil_kod, bolge_ad, kalite = ad.split("-")[0], ad.split("-")[1], ad.split("-")[2]
    klasor = KOK / "sesler"
    klasor.mkdir(exist_ok=True)
    taban = (f"https://huggingface.co/rhasspy/piper-voices/resolve/main/"
             f"{dil_kod.split('_')[0]}/{dil_kod}/{bolge_ad}/{kalite}/{ad}")
    for uzanti in (".onnx", ".onnx.json"):
        hedef = klasor / (ad + uzanti)
        if not hedef.exists() or hedef.stat().st_size < 1000:
            log(f"  Piper sesi indiriliyor: {ad}{uzanti}")
            r = requests.get(taban + uzanti, timeout=300)
            r.raise_for_status()
            hedef.write_bytes(r.content)
    return PiperVoice.load(str(klasor / (ad + ".onnx")))


def _piper_konus(ses, metin, wav):
    import wave
    from piper import SynthesisConfig
    with wave.open(str(wav), "wb") as wf:
        ses.synthesize_wav(metin, wf, syn_config=SynthesisConfig(length_scale=0.88))


def _kelime_zamanla(metin, d):
    """Zaman bilgisi yoksa kelimeleri uzunluklarına göre dağıt."""
    ks = metin.split()
    agirlik = [len(k) + 2 for k in ks]
    toplam, t, sonuc = sum(agirlik), 0.0, []
    for k, a in zip(ks, agirlik):
        dt = d * a / toplam
        sonuc.append((t, t + dt, k))
        t += dt
    return sonuc


def seslendir(s):
    sahneler = s["sahneler"]
    # 1) Önce Edge TTS (daha doğal ses). Tek sahne bile başarısız olursa tüm video Piper'a geçer
    #    ki videoda iki farklı ses olmasın.
    edge_ok = ENV("TTS", "").lower() != "piper"
    if edge_ok:
        for i, sahne in enumerate(sahneler):
            mp3 = GECICI / f"ses_{i:02d}.mp3"
            for deneme in range(2):
                try:
                    kel = asyncio.run(_tts(sahne["metin"], mp3))
                    break
                except Exception as e:
                    log("  Edge TTS hata:", str(e)[:100])
                    time.sleep(4)
            else:
                edge_ok = False
                break
            d = sure(mp3)
            sahne.update(ses_dosya=str(mp3), sure=d + 0.25,
                         kelimeler=kel or _kelime_zamanla(sahne["metin"], d))
    if edge_ok:
        log("Ses: Edge TTS")
        return
    # 2) Yedek: Piper
    log("Ses: Piper (yedek)")
    ses = _piper_yukle()
    for i, sahne in enumerate(sahneler):
        wav = GECICI / f"ses_{i:02d}.wav"
        _piper_konus(ses, sahne["metin"], wav)
        d = sure(wav)
        sahne.update(ses_dosya=str(wav), sure=d + 0.25, kelimeler=_kelime_zamanla(sahne["metin"], d))


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
Style: Ana,DejaVu Sans,78,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,7,3,2,70,70,370,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""" + "\n".join(satirlar) + "\n", "utf-8")


# ---------------------------------------------------------------- 6) animasyon
def montaj(s, cikti_mp4):
    import animasyon as A
    ass = GECICI / "altyazi.ass"
    altyazi_yaz(s, ass)
    muzikler = sorted((KOK / "muzik").glob("*.mp3")) if (KOK / "muzik").exists() else []
    return A.render(s["sahneler"], cikti_mp4, ass=ass, W=W, H=H,
                    muzik=random.choice(muzikler) if muzikler else None)


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
