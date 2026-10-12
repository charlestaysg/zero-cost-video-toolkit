#!/usr/bin/env python3
"""Turn a JSON score into a standard MIDI file (no dependencies).

Usage:
  python score_to_midi.py score.json [-o song.mid] [--wav song.wav --soundfont some.sf2]

Open the .mid in GarageBand, Logic, MuseScore or any DAW to pick instruments and export audio.
--wav renders it directly with FluidSynth (brew install fluid-synth) and a General MIDI soundfont.

Because the score is the timing truth, you can also derive exact beat and note times from it
for animation (see --events).

Score format (see example_score.py):
{
  "title": "Morning Walk", "bpm": 96, "time_signature": "4/4",
  "parts": [
    {"name": "Lead", "instrument": "flute", "dynamic": "mf", "mix": {"pan": 0.2, "reverb": "30%"},
     "notes": ["C5:1", "E5:0.5", "rest:0.5", "[C4,E4,G4]:2"]},
    {"name": "Drums", "is_percussion": true, "notes": ["kick:0.5", "closed_hat:0.5", "[kick,crash]:1"]}
  ]
}
Each note is "pitch:beats" (C4 = middle C, sharps C#4, flats Bb3), "[p1,p2,...]:beats" for a chord,
or "rest:beats". Percussion parts use drum names (see DRUMS). Set "program" (0-127, General MIDI)
when an instrument name is not in INSTRUMENTS.
"""
import argparse
import json
import os
import re
import shutil
import struct
import subprocess
import sys

TPB = 480  # ticks per beat
INSTRUMENTS = {
    "piano": 0, "bright piano": 1, "electric piano": 4, "harpsichord": 6, "celesta": 8, "glockenspiel": 9,
    "music box": 10, "vibraphone": 11, "marimba": 12, "xylophone": 13, "organ": 16, "accordion": 21,
    "nylon guitar": 24, "ukulele": 24, "acoustic guitar": 25, "electric guitar": 27, "muted guitar": 28,
    "acoustic bass": 32, "electric bass": 33, "synth bass": 38, "violin": 40, "cello": 42, "strings": 48,
    "pizzicato": 45, "harp": 46, "choir": 52, "trumpet": 56, "trombone": 57, "french horn": 60, "brass": 61,
    "sax": 65, "clarinet": 71, "flute": 73, "recorder": 74, "pan flute": 75, "whistle": 78,
    "synth lead": 80, "square lead": 80, "saw lead": 81, "pad": 88, "warm pad": 89, "steel drums": 114,
}
DRUMS = {
    "kick": 36, "rim": 37, "snare": 38, "clap": 39, "low_tom": 45, "closed_hat": 42, "pedal_hat": 44,
    "open_hat": 46, "mid_tom": 47, "high_tom": 50, "crash": 49, "ride": 51, "tambourine": 54,
    "cowbell": 56, "shaker": 70, "woodblock": 76,
}
DYNAMICS = {"ppp": 16, "pp": 33, "p": 49, "mp": 64, "mf": 80, "f": 96, "ff": 112, "fff": 127}
PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def pitch(name):
    m = re.fullmatch(r"([A-Ga-g])([#b]?)(-?\d)", name.strip())
    if not m:
        raise ValueError(f"bad pitch {name!r}")
    n = PC[m.group(1).upper()] + {"#": 1, "b": -1, "": 0}[m.group(2)]
    return 12 * (int(m.group(3)) + 1) + n


def parse_note(tok, perc):
    """'C4:1' -> ([60], 1.0); '[C4,E4]:2' -> ([60, 64], 2.0); 'rest:1' -> ([], 1.0)."""
    body, _, beats = tok.rpartition(":")
    if not body:
        raise ValueError(f"bad note {tok!r}; expected 'pitch:beats'")
    names = body[1:-1].split(",") if body.startswith("[") else [body]
    keys = []
    for nm in (x.strip() for x in names):
        if nm == "rest":
            continue
        if perc:
            if nm not in DRUMS:
                raise ValueError(f"unknown drum {nm!r}; known: {', '.join(DRUMS)}")
            keys.append(DRUMS[nm])
        else:
            keys.append(pitch(nm))
    return keys, float(beats)


def vlq(n):
    out = [n & 0x7F]
    n >>= 7
    while n:
        out.append((n & 0x7F) | 0x80)
        n >>= 7
    return bytes(reversed(out))


def track(events):
    """events: list of (tick, bytes). Returns an MTrk chunk."""
    data, last = b"", 0
    for tick, msg in sorted(events, key=lambda e: (e[0], e[1][0] & 0xF0 != 0x80)):
        data += vlq(tick - last) + msg
        last = tick
    data += vlq(0) + b"\xFF\x2F\x00"
    return b"MTrk" + struct.pack(">I", len(data)) + data


def meta(kind, payload):
    return bytes([0xFF, kind]) + vlq(len(payload)) + payload


def build(score):
    bpm = float(score.get("bpm", 120))
    num, den = (int(x) for x in score.get("time_signature", "4/4").split("/"))
    tempo = [(0, meta(0x51, struct.pack(">I", int(60_000_000 / bpm))[1:])),
             (0, meta(0x58, bytes([num, den.bit_length() - 1, 24, 8]))),
             (0, meta(0x03, score.get("title", "score").encode()))]
    tracks, events_out, ch_next = [track(tempo)], [], 0
    for part in score["parts"]:
        perc = bool(part.get("is_percussion"))
        if perc:
            ch = 9
        else:
            ch = ch_next if ch_next != 9 else 10
            ch_next = ch + 1
        prog = part.get("program", INSTRUMENTS.get(str(part.get("instrument", "piano")).lower(), 0))
        vel = DYNAMICS.get(part.get("dynamic", "mf"), 80)
        ev = [(0, meta(0x03, part.get("name", "part").encode()))]
        if not perc:
            ev.append((0, bytes([0xC0 | ch, prog])))
        mix = part.get("mix", {})
        if "pan" in mix:
            ev.append((0, bytes([0xB0 | ch, 10, max(0, min(127, round(64 + 63 * float(mix["pan"]))))])))
        if "reverb" in mix:
            ev.append((0, bytes([0xB0 | ch, 91, round(127 * float(str(mix["reverb"]).rstrip("%")) / 100)])))
        beat = 0.0
        for tok in part["notes"]:
            keys, beats = parse_note(tok, perc)
            on = round(beat * TPB)
            off = on + max(1, round((0.1 if perc else beats * 0.95) * TPB))
            for k in keys:
                ev += [(on, bytes([0x90 | ch, k, vel])), (off, bytes([0x80 | ch, k, 0]))]
                events_out.append({"part": part.get("name"), "beat": round(beat, 4), "time": round(beat * 60 / bpm, 4), "key": k, "beats": beats})
            beat += beats
        tracks.append(track(ev))
        print(f"  {part.get('name', 'part'):16} {len(part['notes']):4} notes  {beat:6.1f} beats  ch {ch + 1}  {'drums' if perc else 'program ' + str(prog)}")
    header = b"MThd" + struct.pack(">IHHH", 6, 1, len(tracks), TPB)
    return header + b"".join(tracks), events_out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("score")
    ap.add_argument("-o", "--out", help="Output .mid (default: next to the score)")
    ap.add_argument("--events", help="Also write every note's beat and time in seconds to this JSON file")
    ap.add_argument("--wav", help="Render to WAV with FluidSynth")
    ap.add_argument("--soundfont", default=os.environ.get("SOUNDFONT"), help="General MIDI .sf2 for --wav (or env SOUNDFONT)")
    args = ap.parse_args()

    score = json.load(open(args.score, encoding="utf-8"))
    out = args.out or os.path.splitext(args.score)[0] + ".mid"
    print(f"{score.get('title', 'score')}: {score.get('bpm', 120)} bpm, {score.get('time_signature', '4/4')}")
    data, events = build(score)
    open(out, "wb").write(data)
    print("wrote", out)
    if args.events:
        json.dump({"bpm": score.get("bpm", 120), "notes": events}, open(args.events, "w"), indent=1)
        print("wrote", args.events)
    if args.wav:
        if not shutil.which("fluidsynth"):
            sys.exit("fluidsynth not found (brew install fluid-synth)")
        if not args.soundfont:
            sys.exit("--wav needs --soundfont path/to/general-midi.sf2")
        subprocess.run(["fluidsynth", "-ni", "-g", "0.5", "-r", "48000", "-F", args.wav, args.soundfont, out], check=True)
        print("wrote", args.wav)


if __name__ == "__main__":
    main()
