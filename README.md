# How to Buy USDT: customer tutorial video

A 3½-minute, 1080p English tutorial for customers. It explains what USDT is and
walks through buying it step by step, with safety tips along the way. It has a
voice-over, captions burned into the picture, soft background music and
animated phone screens.

| File | What it is |
| --- | --- |
| [`output/how-to-buy-usdt.mp4`](output/how-to-buy-usdt.mp4) | The video (1920×1080, 30 fps, H.264 + AAC) |
| [`output/how-to-buy-usdt.srt`](output/how-to-buy-usdt.srt) | Subtitles, e.g. for YouTube (lets viewers auto-translate) |
| [`output/thumbnail.png`](output/thumbnail.png) | Title frame, usable as a thumbnail |

**راهنمای فارسی:** فایل ویدیو در پوشه‌ی `output` است (`how-to-buy-usdt.mp4`).
زبان ویدیو انگلیسی است و زیرنویس انگلیسی روی تصویر دارد. فایل `srt` جداگانه هم
هست که اگر ویدیو را در یوتیوب بگذارید، مشتری می‌تواند ترجمه‌ی خودکار زیرنویس را
روشن کند. صفحه‌های اپلیکیشن در ویدیو نمونه هستند و به هیچ صرافی خاصی تعلق ندارند
(اسم اپ «Your Exchange» است). برای تغییر متن گوینده، فایل `script.json` را ویرایش
کنید و `./build.sh` را دوباره اجرا کنید.

## Chapters

Paste these into a YouTube description to get chapters:

```
0:00 Introduction
0:12 What is USDT?
0:30 What you'll need
0:44 Step 1: Create an account
1:06 Step 2: Secure your account (2FA)
1:23 Step 3: Verify your identity (KYC)
1:40 Step 4: Add funds
1:57 Step 5: Buy USDT
2:18 Step 6: Send to another wallet (optional)
2:50 Golden safety rules
3:13 Recap
```

## What the video covers

1. **What USDT is**: a stablecoin designed to stay close to 1 US dollar
2. **What you need**: a phone or computer, a valid ID and a payment method
3. **Create an account** on a trusted, licensed exchange, using only the official app or website
4. **Secure the account** with two-factor authentication (2FA)
5. **Verify identity (KYC)** with a photo of the ID and a selfie
6. **Add funds** by bank transfer or card, checking fees and the final amount
7. **Buy USDT**, reviewing the amount received and the fee before confirming
8. **Send to another wallet (optional)**: paste the address, pick the matching network (TRC-20 / ERC-20 / BEP-20) and send a small test amount first
9. **Safety rules**: never share passwords, 2FA codes or recovery phrases; "guaranteed profit" is a scam; double-check address and network

The app screens are generic examples (a made-up app called "Your Exchange") and
do not belong to any real exchange. The amounts are examples too. The video ends
with a short disclaimer: educational only, not financial advice.

## Changing the video

Everything is generated from source, so you can change the wording, the voice
or the screens and rebuild:

- **Narration and captions**: `script.json`. Each scene has `cues`, which are
  the sentences the voice reads. Captions and timing follow automatically.
- **Voice**: `voice` in `script.json` (for example `af_heart`, `af_bella`,
  `am_michael`, `bf_emma`, `bm_george`) and `speed`.
- **Visuals**: `src/video.html` and `src/style.css`. Animations are tied to the
  narration with attributes such as `data-in="c2@0.5"` ("halfway through
  sentence 2 of this scene"); the full list is at the top of `src/engine.js`.

### Setup

Needs Python 3.10+, Node 18+ and ffmpeg.

```bash
pip install -r requirements.txt
npm install && npx playwright install chromium

# Kokoro text-to-speech model (~350 MB)
mkdir -p models
curl -L -o models/kokoro-v1.0.onnx https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
curl -L -o models/voices-v1.0.bin  https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
```

### Build

```bash
./build.sh                                  # full video, takes about 15 minutes
node tools/render.cjs --stills 9,60,130     # quick PNG previews of single moments
```

The build works in three stages:

1. `tools/narrate.py` turns every sentence into speech, lays the sentences out
   on a timeline and writes the subtitles.
2. `tools/render.cjs` opens `src/video.html` in headless Chromium and captures
   it frame by frame. Each frame is a pure function of time, so the output is
   frame-exact.
3. `tools/mix.py` generates the background music and the tap and success
   sounds, mixes them under the voice and normalises the result to −16 LUFS.
   `ffmpeg` then muxes the audio with the video.
