#!/usr/bin/env python3
"""Voice a multi-character dialogue script with Kokoro-82M, one voice per character.

Usage:
  python tts_dialogue.py script.dialogue.example.md --out ../out/audio \
      --voice MEI=bf_emma:b --voice BEN=am_michael:a [--speed 0.95]

Script lines are "NAME: text" or "PAUSE". Each --voice maps NAME to a Kokoro voice and an
optional language code (a=US English, b=UK English; defaults to the voice's first letter).

Writes <out>/s<n>.wav, durations.json and lines.json (who speaks when, per scene).
"""
import argparse
import json
import os
import sys

import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from script_parse import caption_text, parse, spoken_text  # noqa: E402

SR = 24000
MODEL = "mlx-community/Kokoro-82M-bf16"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("script")
    ap.add_argument("--out", default="out/audio")
    ap.add_argument("--voice", action="append", default=[], metavar="NAME=voice[:lang]", help="Repeat for each character")
    ap.add_argument("--speed", type=float, default=0.95)
    ap.add_argument("--gap", type=float, default=0.32, help="Silence between lines in seconds (default 0.32)")
    ap.add_argument("--pause", type=float, default=3.0, help="Length of a PAUSE line in seconds (default 3)")
    ap.add_argument("--model", default=MODEL)
    args = ap.parse_args()

    voices = {}
    for v in args.voice:
        name, _, spec = v.partition("=")
        voice, _, lang = spec.partition(":")
        if not name or not voice:
            sys.exit(f"Bad --voice {v!r}; use NAME=voice[:lang]")
        voices[name.strip().upper()] = (voice, lang or voice[0])

    scenes = parse(args.script, dialogue=True)
    missing = {l["who"] for s in scenes for l in s["lines"] if l["who"] != "PAUSE"} - set(voices)
    if missing:
        sys.exit("No --voice given for: " + ", ".join(sorted(missing)))

    from mlx_audio.tts.utils import load_model

    os.makedirs(args.out, exist_ok=True)
    model = load_model(args.model)
    dur, lines = {}, {}
    for sc in scenes:
        buf, t, L = [], 0.0, []
        for line in sc["lines"]:
            if line["who"] == "PAUSE":
                buf.append(np.zeros(int(args.pause * SR), np.float32))
                L.append({"who": "PAUSE", "start": round(t, 3), "end": round(t + args.pause, 3)})
                t += args.pause
                continue
            voice, lang = voices[line["who"]]
            text = spoken_text(line["text"])
            a = np.concatenate([np.array(r.audio) for r in model.generate(text=text, voice=voice, speed=args.speed, lang_code=lang)]).astype(np.float32)
            L.append({"who": line["who"], "start": round(t, 3), "end": round(t + len(a) / SR, 3), "text": caption_text(line["text"])})
            buf += [a, np.zeros(int(args.gap * SR), np.float32)]
            t += len(a) / SR + args.gap
        audio = np.concatenate(buf)
        sf.write(os.path.join(args.out, f"{sc['id'].lower()}.wav"), audio, SR)
        dur[sc["id"]] = round(len(audio) / SR, 3)
        lines[sc["id"]] = L
        print(sc["id"], dur[sc["id"]], "s", flush=True)
    json.dump(dur, open(os.path.join(args.out, "durations.json"), "w"), indent=1)
    json.dump(lines, open(os.path.join(args.out, "lines.json"), "w"), indent=1)
    print("wrote durations.json and lines.json in", args.out)


if __name__ == "__main__":
    main()
