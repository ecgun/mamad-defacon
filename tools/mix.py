"""Mix the soundtrack: voice-over + generated background music + UI sound effects.

Reads build/narration.wav, build/timeline.json and build/events.json (written by
the renderer) and writes build/audio.wav, loudness-normalised to -16 LUFS.
"""

import argparse
import json
import re
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy import signal

ROOT = Path(__file__).resolve().parent.parent
SR = 48000
rng = np.random.default_rng(7)


def hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def place(track, clip, t):
    """Add a (n, 2) clip into a (N, 2) track at time t (seconds)."""
    i = int(round(t * SR))
    if i >= len(track):
        return
    j = min(len(track), i + len(clip))
    track[max(i, 0):j] += clip[max(-i, 0):j - i]


def stereo(mono, pan=0.0):
    return np.stack([mono * np.sqrt(0.5 * (1 - pan)), mono * np.sqrt(0.5 * (1 + pan))], axis=1)


def reverb(x, seconds=2.4, decay=0.55, wet=0.3):
    n = int(seconds * SR)
    t = np.arange(n) / SR
    sos = signal.butter(2, 5000, "low", fs=SR, output="sos")
    ir = np.stack([signal.sosfilt(sos, rng.standard_normal(n)) * np.exp(-t / decay) for _ in range(2)], axis=1)
    ir /= np.sqrt((ir ** 2).sum(axis=0))
    tail = np.stack([signal.fftconvolve(x[:, c], ir[:, c])[: len(x)] for c in range(2)], axis=1)
    return x * (1 - wet) + tail * wet


# ---------------------------------------------------------------- music

def music(duration):
    bpm = 88
    beat = 60 / bpm
    chord_len = 8 * beat
    # Cmaj7 - G6 - Am7 - Fmaj7, voiced for smooth movement; roots in the bass.
    progression = [
        (36, [52, 55, 59, 64]),
        (43, [50, 55, 59, 64]),
        (45, [52, 55, 60, 64]),
        (41, [53, 57, 60, 64]),
    ]
    n = int(duration * SR) + SR
    pad = np.zeros((n, 2))
    arp = np.zeros((n, 2))
    bass = np.zeros((n, 2))

    release = 2.0
    seg_t = np.arange(int((chord_len + release) * SR)) / SR
    attack = np.clip(seg_t / 1.4, 0, 1) ** 2 * (3 - 2 * np.clip(seg_t / 1.4, 0, 1))
    tail = np.where(seg_t > chord_len, np.exp(-(seg_t - chord_len) / 0.6), 1.0)
    pad_env = attack * tail

    pluck_t = np.arange(int(0.9 * SR)) / SR
    pluck_env = np.exp(-pluck_t / 0.16) * np.clip(pluck_t / 0.004, 0, 1)
    pattern = [0, 2, 1, 3, 2, 1, 3, 2]

    k = 0
    start = 0.0
    while start < duration:
        root, notes = progression[k % len(progression)]
        # pad: two slightly detuned sines per note, spread left/right
        for m in notes:
            f = hz(m)
            for ch, detune in ((0, -0.0014), (1, 0.0016)):
                ph = rng.uniform(0, 2 * np.pi)
                v = np.sin(2 * np.pi * f * (1 + detune) * seg_t + ph) + 0.18 * np.sin(4 * np.pi * f * seg_t + ph)
                place(pad, np.stack([v * pad_env * (ch == 0), v * pad_env * (ch == 1)], axis=1), start)
        # bass: soft pulse every half bar
        for h in range(4):
            bt = np.arange(int(2 * beat * SR)) / SR
            benv = np.clip(bt / 0.03, 0, 1) * (0.45 + 0.55 * np.exp(-bt / 0.5)) * np.exp(-np.maximum(bt - 2 * beat + 0.15, 0) / 0.05)
            v = (np.sin(2 * np.pi * hz(root) * bt) + 0.25 * np.sin(4 * np.pi * hz(root) * bt)) * benv
            place(bass, stereo(v), start + h * 2 * beat)
        # arpeggio: eighth notes over the chord, an octave up
        if start >= 4 * beat:
            for e in range(16):
                m = notes[pattern[e % 8]] + 12
                v = (np.sin(2 * np.pi * hz(m) * pluck_t) + 0.3 * np.sin(4 * np.pi * hz(m) * pluck_t)) * pluck_env
                place(arp, stereo(v, pan=0.35 if e % 2 else -0.35), start + e * beat / 2)
        start += chord_len
        k += 1

    sos = signal.butter(2, 2200, "low", fs=SR, output="sos")
    pad = signal.sosfilt(sos, pad, axis=0)
    sos = signal.butter(2, 260, "low", fs=SR, output="sos")
    bass = signal.sosfilt(sos, bass, axis=0)

    # ping-pong echo on the arpeggio
    d = int(0.75 * beat * SR)
    echo = np.zeros_like(arp)
    echo[d:, 0] += 0.35 * arp[:-d, 1]
    echo[d:, 1] += 0.35 * arp[:-d, 0]
    arp = arp + echo

    mix = reverb(0.11 * pad + 0.06 * arp, wet=0.35) + 0.22 * bass
    mix = mix[: int(duration * SR)]
    t = np.arange(len(mix)) / SR
    fade = np.clip(t / 2.0, 0, 1) * np.clip((duration - t) / 3.5, 0, 1)
    return mix * fade[:, None]


# ---------------------------------------------------------------- sound effects

def sfx_tap():
    t = np.arange(int(0.06 * SR)) / SR
    sos = signal.butter(2, 1500, "high", fs=SR, output="sos")
    noise = signal.sosfilt(sos, rng.standard_normal(len(t))) * np.exp(-t / 0.003)
    tone = np.sin(2 * np.pi * 1700 * t) * np.exp(-t / 0.015)
    return stereo(0.5 * noise + 0.6 * tone) * 0.16


def sfx_tick():
    t = np.arange(int(0.25 * SR)) / SR
    a = np.sin(2 * np.pi * 1320 * t) * np.exp(-t / 0.05)
    b = np.zeros_like(t)
    o = int(0.07 * SR)
    b[o:] = np.sin(2 * np.pi * 1980 * t[: len(t) - o]) * np.exp(-t[: len(t) - o] / 0.07)
    return stereo(a + b) * 0.09


def sfx_success():
    t = np.arange(int(1.4 * SR)) / SR
    out = np.zeros_like(t)
    for i, m in enumerate([84, 88, 91]):  # C6 E6 G6
        o = int(i * 0.075 * SR)
        tt = t[: len(t) - o]
        f = hz(m)
        out[o:] += (np.sin(2 * np.pi * f * tt) + 0.12 * np.sin(2 * np.pi * 2.76 * f * tt)) * np.exp(-tt / 0.35)
    return stereo(out) * 0.075


def sfx_whoosh():
    n = int(0.9 * SR)
    t = np.arange(n) / SR
    sos = signal.butter(2, [300, 2500], "band", fs=SR, output="sos")
    noise = signal.sosfilt(sos, rng.standard_normal(n))
    env = np.where(t < 0.45, (t / 0.45) ** 2, np.exp(-(t - 0.45) / 0.12))
    return stereo(noise * env) * 0.05


# ---------------------------------------------------------------- ducking

def duck_curve(voice, depth=0.62):
    """1 where there is no speech, (1 - depth) under speech, with smooth ramps."""
    hop = SR // 100
    frames = len(voice) // hop + 1
    level = np.array([np.abs(voice[i * hop:(i + 1) * hop]).max(initial=0) for i in range(frames)])
    active = (level > 0.02).astype(float)
    # hold through the short gaps between words and sentences
    active = np.convolve(active, np.ones(35), mode="same") > 0
    g = np.zeros(frames)
    cur = 0.0
    for i, a in enumerate(active):
        target = 1.0 if a else 0.0
        cur += (target - cur) * (0.25 if target > cur else 0.04)
        g[i] = cur
    g = np.interp(np.arange(len(voice)) / hop, np.arange(frames), g)
    return 1 - depth * g


def loudnorm(src, dst):
    af = "loudnorm=I=-16:TP=-1.5:LRA=11"
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(src), "-af", af + ":print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True, check=True)
    m = json.loads(re.search(r"\{[^{}]*\}\s*$", r.stderr).group(0))
    af2 = (f"{af}:measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}"
           f":measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-af", af2, "-ar", str(SR), "-c:a", "pcm_s16le", str(dst)],
                   check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", default=ROOT / "build", type=Path)
    parser.add_argument("--no-music", action="store_true")
    parser.add_argument("--no-sfx", action="store_true")
    args = parser.parse_args()

    timeline = json.loads((args.build / "timeline.json").read_text())
    events = json.loads((args.build / "events.json").read_text())
    duration = timeline["duration"]
    n = int(duration * SR)

    voice, sr = sf.read(args.build / "narration.wav", dtype="float64")
    voice = signal.resample_poly(voice, SR, sr)[:n]
    voice = np.pad(voice, (0, n - len(voice)))
    voice *= 0.5 / np.percentile(np.abs(voice[np.abs(voice) > 0.01]), 99)

    mix = stereo(voice, 0) * np.sqrt(2)

    if not args.no_music:
        # Sit the music 16 dB under the voice, and another ~8 dB lower under speech.
        bg = music(duration)
        rms = lambda x: np.sqrt(np.mean(x ** 2))
        bg *= rms(voice[np.abs(voice) > 0.01]) * 10 ** (-16 / 20) / rms(bg[SR * 3:-SR * 4])
        mix += bg * duck_curve(voice)[:, None]

    if not args.no_sfx:
        fx = np.zeros((n, 2))
        tap, tick, success, whoosh = sfx_tap(), sfx_tick(), sfx_success(), sfx_whoosh()
        for t in events["taps"]:
            place(fx, tap, t)
        for e in events["sfx"]:
            place(fx, {"tick": tick, "success": success}[e["name"]], e["t"])
        for s in events["scenes"][1:]:
            place(fx, whoosh, s["start"] - 0.45)
        mix += reverb(fx, seconds=1.2, decay=0.25, wet=0.18)

    peak = np.abs(mix).max()
    if peak > 0.98:
        mix *= 0.98 / peak
    raw = args.build / "mix_raw.wav"
    sf.write(raw, mix.astype(np.float32), SR, subtype="FLOAT")
    loudnorm(raw, args.build / "audio.wav")
    print(f"wrote {args.build / 'audio.wav'} ({duration:.1f}s)")


if __name__ == "__main__":
    main()
