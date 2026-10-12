#!/usr/bin/env python3
"""Mix the soundtrack: narration clips at their scene starts, a music bed ducked under the voice,
optional quiz sound effects, loudness normalised to -16 LUFS.

Usage:
  python mix.py --audio ../out/audio                         # synthesised pad as the music bed
  python mix.py --audio ../out/audio --music theme.wav       # your own track (looped to length)
  python mix.py --audio ../out/audio --music a.wav b.wav     # several tracks, crossfaded, then looped
  python mix.py --audio ../out/audio --no-music
  python mix.py --audio ../out/audio --quiz-sfx              # ticks during each PAUSE + a chime after it

Reads timeline.json (written by timings.py) so the audio lines up with the film.
Writes <audio>/narration.wav and <audio>/final_mix.wav (48 kHz stereo).
"""
import argparse
import json
import os
import subprocess

# Four gentle chords (C, Am, F, G), 8 s each, as sine partials; low-passed into a soft pad.
CHORDS = [[261.63, 329.63, 392.0], [220.0, 261.63, 329.63], [174.61, 220.0, 261.63], [196.0, 246.94, 293.66]]


def ff(*args):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--audio", default="out/audio", help="Folder with s<n>.wav and timeline.json")
    ap.add_argument("--music", nargs="+", help="Music file(s) for the bed; default is a synthesised pad")
    ap.add_argument("--no-music", action="store_true")
    ap.add_argument("--music-volume", type=float, default=None, help="Bed level before ducking (pad 0.5, tracks 0.55)")
    ap.add_argument("--quiz-sfx", action="store_true", help="Countdown ticks and a reveal chime for PAUSE lines (needs lines.json)")
    ap.add_argument("--lufs", type=float, default=-16.0, help="Target loudness (default -16)")
    args = ap.parse_args()

    D = args.audio
    tl = json.load(open(os.path.join(D, "timeline.json")))
    starts, TOT = tl["starts"], tl["total"]
    n = len(starts)

    # 1. narration: each clip delayed to its scene start
    ins, f = [], []
    for i, s in enumerate(starts):
        ins += ["-i", os.path.join(D, f"s{i + 1}.wav")]
        ms = int(round(s * 1000))
        f.append(f"[{i}:a]aresample=48000,adelay={ms}|{ms},apad[a{i}]")
    f.append("".join(f"[a{i}]" for i in range(n)) + f"amix=inputs={n}:normalize=0:duration=longest,atrim=0:{TOT}[out]")
    narration = os.path.join(D, "narration.wav")
    ff(*ins, "-filter_complex", ";".join(f), "-map", "[out]", "-ac", "1", narration)

    layers = [narration]

    # 2. music bed
    if not args.no_music:
        bed = os.path.join(D, "music_bed.wav")
        if args.music:
            vol = args.music_volume if args.music_volume is not None else 0.55
            tracks = args.music * 2 if len(args.music) == 1 else args.music
            ins, chain, prev = [], "", "[0:a]"
            for tr in tracks:
                ins += ["-i", tr]
            for k in range(1, len(tracks)):
                chain += f"{prev}[{k}:a]acrossfade=d=4:c1=tri:c2=tri[x{k}];"
                prev = f"[x{k}]"
            chain += (f"{prev}aresample=48000,aloop=loop=-1:size=2e9,atrim=0:{TOT},"
                      f"afade=t=in:d=2,afade=t=out:st={TOT - 4:.2f}:d=4,volume={vol}[m]")
            ff(*ins, "-filter_complex", chain, "-map", "[m]", "-ac", "2", bed)
        else:
            vol = args.music_volume if args.music_volume is not None else 0.5
            expr = [f"(between(mod(t,32),{k * 8},{k * 8 + 8})*(" + "+".join(f"sin(2*PI*{fr}*t)+0.5*sin(2*PI*{fr / 2}*t)" for fr in c) + "))"
                    for k, c in enumerate(CHORDS)]
            e = "0.05*(" + "+".join(expr) + ")*(0.75+0.25*sin(2*PI*0.2*t))"
            ff("-f", "lavfi", "-i", f"aevalsrc='{e}':s=48000:d={TOT}",
               "-af", f"lowpass=f=900,afade=t=in:d=3,afade=t=out:st={TOT - 4:.2f}:d=4,volume={vol}", bed)
        layers.append(bed)

    # 3. quiz sound effects: a tick each second of every PAUSE, a two-note chime at the reveal
    sfx_count = 0
    if args.quiz_sfx:
        lines = json.load(open(os.path.join(D, "lines.json")))
        fx = []
        for i, L in enumerate(lines.values()):
            for l in L:
                if l["who"] != "PAUSE":
                    continue
                for s in range(int(l["end"] - l["start"])):
                    ms = int(round((starts[i] + l["start"] + s) * 1000))
                    fx.append(f"sine=sample_rate=48000:f=1400:d=0.06,volume=0.5,afade=t=out:st=0.03:d=0.03,adelay={ms}|{ms},apad")
                ms = int(round((starts[i] + l["end"]) * 1000))
                fx.append(f"sine=sample_rate=48000:f=880:d=0.5,volume=0.35,afade=t=out:st=0.05:d=0.45,adelay={ms}|{ms},apad")
                fx.append(f"sine=sample_rate=48000:f=1320:d=0.45,volume=0.25,afade=t=out:st=0.05:d=0.4,adelay={ms + 120}|{ms + 120},apad")
        if fx:
            sfx = os.path.join(D, "sfx.wav")
            graph = ";".join(f"{x}[f{k}]" for k, x in enumerate(fx)) + ";" + "".join(f"[f{k}]" for k in range(len(fx))) + f"amix=inputs={len(fx)}:normalize=0,atrim=0:{TOT}[fx]"
            ff("-filter_complex", graph, "-map", "[fx]", "-t", f"{TOT}", sfx)
            layers.append(sfx)
            sfx_count = len(fx)

    # 4. duck the music under the voice, add effects, normalise
    ins = sum((["-i", p] for p in layers), [])
    if len(layers) == 1:
        graph = f"[0:a]aresample=48000,loudnorm=I={args.lufs}:TP=-1.5:LRA=11[o]"
    else:
        rest = "".join(f"[{k}:a]" for k in range(2, len(layers)))
        graph = ("[0:a]aresample=48000,asplit=2[v][sc];[1:a][sc]sidechaincompress=threshold=0.02:ratio=8:attack=20:release=400[duck];"
                 f"[v][duck]{rest}amix=inputs={len(layers)}:normalize=0:duration=first,loudnorm=I={args.lufs}:TP=-1.5:LRA=11[o]")
    out = os.path.join(D, "final_mix.wav")
    ff(*ins, "-filter_complex", graph, "-map", "[o]", "-ar", "48000", "-ac", "2", out)
    print("scene starts", starts, "total", TOT, "s", f"sfx events {sfx_count}" if args.quiz_sfx else "")
    print("wrote", out)


if __name__ == "__main__":
    main()
