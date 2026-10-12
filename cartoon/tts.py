#!/usr/bin/env python3
"""Narrate each scene of a script with Kokoro-82M (offline, via MLX-Audio).

Usage:
  python tts.py script.example.md --out ../out/audio [--voice af_heart] [--speed 0.9]

Writes <out>/s1.wav, s2.wav, ... (24 kHz mono) and <out>/durations.json.
Speed 0.9 is roughly 160 words a minute. The voice says the spoken half of {caption|spoken}.
"""
import argparse
import json
import os
import sys

import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from script_parse import parse, spoken_text  # noqa: E402

SR = 24000
MODEL = "mlx-community/Kokoro-82M-bf16"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("script")
    ap.add_argument("--out", default="out/audio", help="Output folder (default out/audio)")
    ap.add_argument("--voice", default="af_heart", help="Kokoro voice (default af_heart)")
    ap.add_argument("--speed", type=float, default=0.9, help="Speaking speed (default 0.9)")
    ap.add_argument("--lang", help="Kokoro language code; defaults to the voice's first letter (a=US, b=UK)")
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--only", help="Comma-separated scene ids to redo, e.g. S2,S3")
    args = ap.parse_args()

    from mlx_audio.tts.utils import load_model

    os.makedirs(args.out, exist_ok=True)
    scenes = parse(args.script)
    only = {s.strip().upper() for s in args.only.split(",")} if args.only else None
    dur_path = os.path.join(args.out, "durations.json")
    info = json.load(open(dur_path)) if only and os.path.exists(dur_path) else {}
    lang = args.lang or args.voice[0]
    model = load_model(args.model)
    for sc in scenes:
        sid = sc["id"]
        if only and sid not in only:
            continue
        text = spoken_text(sc["lines"][0]["text"])
        chunks = [np.array(r.audio) for r in model.generate(text=text, voice=args.voice, speed=args.speed, lang_code=lang)]
        audio = np.concatenate(chunks).astype(np.float32)
        sf.write(os.path.join(args.out, f"{sid.lower()}.wav"), audio, SR)
        info[sid] = round(len(audio) / SR, 3)
        print(sid, info[sid], "s", flush=True)
        if info[sid] > 28:
            print(f"  warning: {sid} is over 28 s; Whisper may invent words at the 30 s boundary. Consider splitting it.")
    info = {k: info[k] for k in sorted(info, key=lambda s: int(s[1:]))}
    json.dump(info, open(dur_path, "w"), indent=1)
    print("wrote", dur_path)


if __name__ == "__main__":
    main()
