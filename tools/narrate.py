"""Generate the voice-over, the scene timeline and the subtitles.

Reads script.json, synthesises every sentence with Kokoro TTS, lays the clips
out on a timeline (scene lead-in, pauses, scene tail) and writes:

  build/narration.wav   mono voice-over track
  build/timeline.json   scene / cue / caption timings used by the renderer
  output/<name>.srt     subtitles
"""

import argparse
import hashlib
import json
import re
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parent.parent

# How the TTS should say words it would otherwise mispronounce.
PRONUNCIATION = [
    (r"\bUSDT\b", "U S D T"),
    (r"\bTRC-20\b", "T R C 20"),
    (r"\bERC-20\b", "E R C 20"),
    (r"\bBEP-20\b", "B E P 20"),
    (r"\bKYC\b", "K Y C"),
    (r"\bID\b", "I D"),
]

DEFAULT_LEAD = 0.8      # silence at the start of a scene, while titles animate in
DEFAULT_TAIL = 1.0      # silence at the end of a scene
DEFAULT_PAUSE = 0.45    # silence between cues
SENTENCE_GAP = 0.3      # silence between sentences of the same cue


def spoken(text):
    for pattern, replacement in PRONUNCIATION:
        text = re.sub(pattern, replacement, text)
    return text


def split_sentences(text):
    return [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s]


def split_caption(text, limit=72):
    """Split a sentence at the comma or colon nearest its middle until every
    part fits on one caption line."""
    if len(text) <= limit:
        return [text]
    cuts = [m.end() for m in re.finditer(r"[,:]\s", text)]
    if not cuts:
        return [text]
    cut = min(cuts, key=lambda i: abs(i - len(text) / 2))
    return split_caption(text[:cut].strip(), limit) + split_caption(text[cut:].strip(), limit)


def trim_silence(samples, threshold=0.01, pad=0.04, sr=24000):
    loud = np.flatnonzero(np.abs(samples) > threshold)
    if loud.size == 0:
        return samples
    start = max(0, loud[0] - int(pad * sr))
    end = min(len(samples), loud[-1] + int(pad * sr))
    return samples[start:end]


class Voice:
    def __init__(self, models, voice, speed, cache):
        self.models, self.voice, self.speed, self.cache = models, voice, speed, cache
        self.kokoro = None
        cache.mkdir(parents=True, exist_ok=True)

    def say(self, text):
        key = hashlib.sha1(f"{self.voice}|{self.speed}|{text}".encode()).hexdigest()[:16]
        path = self.cache / f"{key}.wav"
        if path.exists():
            samples, sr = sf.read(path, dtype="float32")
            return samples, sr
        if self.kokoro is None:
            from kokoro_onnx import Kokoro
            self.kokoro = Kokoro(str(self.models / "kokoro-v1.0.onnx"),
                                 str(self.models / "voices-v1.0.bin"))
        samples, sr = self.kokoro.create(spoken(text), voice=self.voice,
                                         speed=self.speed, lang="en-us")
        samples = trim_silence(np.asarray(samples, dtype="float32"), sr=sr)
        sf.write(path, samples, sr)
        return samples, sr


def srt_time(seconds):
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--script", default=ROOT / "script.json", type=Path)
    parser.add_argument("--models", default=ROOT / "models", type=Path)
    parser.add_argument("--build", default=ROOT / "build", type=Path)
    parser.add_argument("--srt", default=ROOT / "output" / "how-to-buy-usdt.srt", type=Path)
    args = parser.parse_args()

    script = json.loads(args.script.read_text())
    voice = Voice(args.models, script["voice"], script["speed"], args.build / "tts")

    sr = 24000
    clips = []          # (start_seconds, samples)
    scenes = []
    sentences = []
    t = 0.0
    for scene in script["scenes"]:
        start = t
        t += scene.get("lead", DEFAULT_LEAD)
        cues = []
        for cue in scene["cues"]:
            cue_start = t
            for i, sentence in enumerate(split_sentences(cue["text"])):
                if i:
                    t += SENTENCE_GAP
                samples, sr = voice.say(sentence)
                clips.append((t, samples))
                sentences.append({"start": round(t, 3), "end": round(t + len(samples) / sr, 3),
                                  "text": sentence})
                t += len(samples) / sr
            cues.append({"start": round(cue_start, 3), "end": round(t, 3), "text": cue["text"]})
            t += cue.get("pause", DEFAULT_PAUSE)
        t = cues[-1]["end"] + scene.get("tail", DEFAULT_TAIL)
        scenes.append({"id": scene["id"], "start": round(start, 3), "end": round(t, 3), "cues": cues})
        print(f"{scene['id']:<8} {start:7.2f}s - {t:7.2f}s")

    duration = round(t, 3)

    # Long sentences are shown in one-line chunks, timed by their share of the
    # characters. A caption stays up until the next one starts, unless the
    # silence is long.
    chunks = []
    for s in sentences:
        parts = split_caption(s["text"])
        total = sum(len(p) for p in parts)
        t0 = s["start"]
        for p in parts:
            t1 = t0 + (s["end"] - s["start"]) * len(p) / total
            chunks.append({"start": t0, "end": t1, "text": p})
            t0 = t1
    captions = []
    for i, c in enumerate(chunks):
        nxt = chunks[i + 1]["start"] if i + 1 < len(chunks) else duration
        end = nxt - 0.02 if nxt - c["end"] < 0.9 else c["end"] + 0.5
        captions.append({"start": round(c["start"] - 0.08, 3), "end": round(end, 3), "text": c["text"]})

    track = np.zeros(int(duration * sr) + sr, dtype="float32")
    for start, samples in clips:
        i = int(start * sr)
        track[i:i + len(samples)] += samples
    args.build.mkdir(parents=True, exist_ok=True)
    sf.write(args.build / "narration.wav", track[: int(duration * sr)], sr)

    timeline = {"title": script["title"], "duration": duration, "scenes": scenes, "captions": captions}
    (args.build / "timeline.json").write_text(json.dumps(timeline, indent=2))

    args.srt.parent.mkdir(parents=True, exist_ok=True)
    with open(args.srt, "w") as f:
        for i, c in enumerate(captions, 1):
            f.write(f"{i}\n{srt_time(c['start'])} --> {srt_time(c['end'])}\n{c['text']}\n\n")

    print(f"duration {duration:.2f}s, {len(captions)} captions")


if __name__ == "__main__":
    main()
