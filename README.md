# How to Buy USDT with MoonPay: customer tutorial video

A 3-minute, 1080p English tutorial for customers who are new to crypto. It
shows how to buy USDT with [MoonPay](https://www.moonpay.com) and send it
straight to the wallet address you gave them, on the **BNB Smart Chain
(BEP-20)** network. It has a voice-over, captions burned into the picture,
soft background music and animated phone screens.

| File | What it is |
| --- | --- |
| [`output/how-to-buy-usdt.mp4`](output/how-to-buy-usdt.mp4) | The video (1920×1080, 30 fps, H.264 + AAC) |
| [`output/how-to-buy-usdt.srt`](output/how-to-buy-usdt.srt) | Subtitles, e.g. for YouTube (lets viewers auto-translate) |
| [`output/thumbnail.png`](output/thumbnail.png) | Title frame, usable as a thumbnail |

**راهنمای فارسی:** فایل ویدیو در پوشه‌ی `output` است (`how-to-buy-usdt.mp4`).
ویدیو به زبان انگلیسی است و به مشتری یاد می‌دهد با MoonPay، تتر (USDT) را روی شبکه‌ی
BNB Smart Chain (BEP-20) بخرد و مستقیم به آدرس کیف پولی که شما داده‌اید بفرستد. زیرنویس
انگلیسی روی تصویر هست. فایل `srt` جداگانه هم هست که اگر ویدیو را در یوتیوب بگذارید،
مشتری می‌تواند ترجمه‌ی خودکار زیرنویس را روشن کند. صفحه‌های اپ در ویدیو ساده‌شده‌اند و
ظاهر واقعی MoonPay ممکن است کمی فرق کند. برای تغییر متن گوینده، فایل `script.json` را
ویرایش کنید و `./build.sh` را دوباره اجرا کنید.

## Chapters

Paste these into a YouTube description to get chapters:

```
0:00 Introduction
0:14 What is USDT?
0:34 What you'll need
0:51 Step 1: Open your MoonPay account
1:06 Step 2: Verify your identity
1:23 Step 3: Choose USDT on BNB Smart Chain (BEP-20)
1:44 Step 4: Paste our wallet address
2:05 Step 5: Pay and confirm
2:31 Safety tips
2:52 Recap
```

## What the video covers

1. **What USDT is**: a stablecoin designed to stay close to 1 US dollar
2. **What you need**: a phone or computer, a valid ID, a payment method and the wallet address you sent
3. **Open a MoonPay account** on moonpay.com or the official app, with email and a code
4. **Verify identity** (first time only): personal details, a photo of the ID and a selfie
5. **Choose USDT on BNB Smart Chain (BEP-20)**, then enter the amount
6. **Paste the wallet address**: never type it, check `0x` and the first and last characters, and don't create a new wallet at checkout
7. **Pay and confirm** with a card, Apple Pay, Google Pay or PayPal; if the card is declined, top up the MoonPay Balance first
8. **Safety tips**: official site or app only, always use the latest address, double-check the network and address, never share codes

The video is not affiliated with MoonPay. The app screens are simplified
illustrations, and the amounts and fees are examples. The video says this in
its closing frame.

The previous version of the video showed a generic exchange (account, 2FA, KYC,
deposit, buy, withdraw). It is in the git history at commit `280d114`.

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
node tools/render.cjs --stills 12,60,130    # quick PNG previews of single moments
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
