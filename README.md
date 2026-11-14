# 🎬 Merak Makinesi — Otomatik Animasyonlu Shorts Fabrikası

Her gün kendi kendine 3D animasyon tarzında, İngilizce seslendirmeli, kelime kelime altyazılı bir
YouTube Short üretir ve telefonuna (Telegram) gönderir. Bilgisayar gerekmez, tamamen ücretsizdir.

```
konular.txt → Gemini (senaryo) → Pollinations (görseller) → edge-tts (ses)
           → ffmpeg (kamera hareketi + altyazı + müzik) → Telegram'a video → sen paylaşırsın
```

## Telefondan kurulum (yaklaşık 20 dakika)

### 1. GitHub deposu
1. github.com'da ücretsiz hesap aç → sağ üst **+ → New repository** → adı `merak-makinesi`, **Private** seç → Create.
2. **Add file → Upload files** ile şu dosyaları yükle: `uret.py`, `konular.txt`, `requirements.txt`, `kullanilan.json`, `README.md`.
3. **Add file → Create new file** → dosya adı kutusuna tam olarak `.github/workflows/uret.yml` yaz,
   `uret.yml` içeriğini yapıştır → Commit.
4. (İsteğe bağlı) `muzik/` klasörüne telifsiz müzik mp3'leri yükle (YouTube Ses Kitaplığı'ndan indir).
   Klasör boşsa video sadece seslendirmeyle çıkar.

### 2. Ücretsiz anahtarlar
| Anahtar | Nereden | Zorunlu mu |
|---|---|---|
| `GEMINI_API_KEY` | aistudio.google.com → **Get API key** | Evet (veya Groq) |
| `GROQ_API_KEY` | console.groq.com → API Keys | Yedek, önerilir |
| `TELEGRAM_BOT_TOKEN` | Telegram'da **@BotFather** → `/newbot` | Evet |
| `TELEGRAM_CHAT_ID` | Botuna "merhaba" yaz, sonra tarayıcıda `https://api.telegram.org/bot<TOKEN>/getUpdates` aç → `"chat":{"id": ...}` | Evet |
| `POLLINATIONS_TOKEN` | auth.pollinations.ai (ücretsiz kayıt, limitleri artırır) | Hayır |
| `CF_ACCOUNT_ID` + `CF_API_TOKEN` | Cloudflare → Workers AI (günlük ücretsiz kota, görsel yedeği) | Hayır |

Depoda **Settings → Secrets and variables → Actions → New repository secret** ile her birini ekle.
(Kanal varsayılan olarak İngilizce. Türkçe kanal için **Variables** sekmesinde `DIL` = `tr` ekle.)

### 3. İlk test
**Actions** sekmesi → *Merak Makinesi - Short uret* → **Run workflow** → (istersen konu yaz) → Run.
~5–8 dakika sonra video Telegram'a gelir. Ayrıca çalıştırmanın sayfasında *Artifacts* altından indirilebilir.

### 4. Her gün
Sistem her gün **13:30 ve 16:30**'da (TR) kendiliğinden çalışır. Video Telegram'a düşünce:
izle → beğendiysen kaydet → YouTube uygulaması → **+ → Short** → mesajdaki başlığı yapıştır → Paylaş.
En iyi paylaşım saati ABD öğleden sonrası: Türkiye saatiyle **20:00–23:00**.
YouTube'un yükleme ekranında **"Değiştirilmiş veya yapay içerik"** kutusunu işaretle.

## YouTube'a otomatik yükleme (ileri seviye — dikkat!)
Kod, YouTube Data API ile zamanlanmış yüklemeyi destekler (`YT_CLIENT_ID`, `YT_CLIENT_SECRET`,
`YT_REFRESH_TOKEN`). **Ancak** Google, denetimden (audit) geçmemiş API projelerinden yüklenen
tüm videoları kalıcı olarak *gizli* kilitler ve bu kilit itiraz edilemez. Bu yüzden:
1. Önce Google Cloud'da YouTube API Services **Audit and Quota Extension** formunu doldur (ücretsiz).
2. Onay gelmeden bu üç secret'ı **ekleme**. Onaydan sonra eklersen video, yayından
   `YT_GECIKME_SAAT` (varsayılan 4) saat önce gizli+zamanlanmış yüklenir; beğenmezsen silersin.

## Ayarlar
- **Konular:** `konular.txt` — her satır bir video, üstten sırayla. Bitince yapay zekâ yeni konu bulur.
- **Saat / sıklık:** `uret.yml` içindeki `cron` satırları (UTC). Günde 1–2 video yeterli; fazlası
  YouTube'un "seri üretim içerik" kuralına takılma riskini artırır.
- **Ses:** `SES` değişkeni (varsayılan `en-US-AndrewNeural`; ör. `en-US-AvaNeural` kadın sesi, `en-GB-RyanNeural` İngiliz aksanı).
- **Görsel stili:** `GORSEL_STILI` değişkeni (ör. anime, kil animasyon, 2D çizgi film).
