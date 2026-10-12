#!/usr/bin/env python3
"""Write an example score ("Morning Walk", C major, 96 bpm) as JSON for score_to_midi.py.

Writing the song as code keeps it editable: change a chord list or a melody bar and rebuild.

  python example_score.py            -> example-score.json
  python score_to_midi.py example-score.json --events example-events.json
"""
import json
from pathlib import Path

PAD = {"C": ["C4", "E4", "G4"], "Am": ["A3", "C4", "E4"], "F": ["F3", "A3", "C4"], "G": ["G3", "B3", "D4"]}
ROOT = {"C": "C2", "Am": "A1", "F": "F1", "G": "G1"}
FIFTH = {"C": "G2", "Am": "E2", "F": "C2", "G": "D2"}

INTRO = ["C", "Am", "F", "G"]
VERSE = ["C", "Am", "F", "G", "C", "Am", "F", "G"]
OUTRO = ["F", "G", "C", "C"]
SECTIONS = [("Intro", INTRO), ("Verse", VERSE), ("Outro", OUTRO)]

# Melody: one string of "pitch:beats" per 4-beat bar
VERSE_MEL = [
    "E5:1 G5:1 E5:0.5 D5:0.5 C5:1",
    "C5:1 E5:1 A4:2",
    "F5:1 E5:0.5 D5:0.5 C5:1 A4:1",
    "B4:1 D5:1 G4:2",
    "E5:1 G5:1 A5:0.5 G5:0.5 E5:1",
    "C5:1 E5:1 A4:2",
    "A4:0.5 C5:0.5 F5:1 E5:1 D5:1",
    "D5:1 B4:1 C5:2",
]
OUTRO_MEL = ["A4:1 C5:1 F5:2", "G5:2 D5:2", "[C5,E5,G5]:4", "rest:4"]


def bars(text_bars):
    return [tok for bar in text_bars for tok in bar.split()]


def chord(c, beats):
    return f"[{','.join(PAD[c])}]:{beats}"


lead, keys, bass, drums = [], [], [], []
for name, prog in SECTIONS:
    if name == "Intro":
        lead += ["rest:4"] * len(prog)
    elif name == "Verse":
        lead += bars(VERSE_MEL)
    else:
        lead += bars(OUTRO_MEL)
    for i, c in enumerate(prog):
        last = name == "Outro" and i == len(prog) - 1
        if last:
            keys.append("rest:4"); bass.append("rest:4"); drums.append("rest:4")
            continue
        keys += [chord(c, 2), chord(c, 1), chord(c, 1)]
        bass += [f"{ROOT[c]}:1.5", f"{ROOT[c]}:0.5", f"{FIFTH[c]}:2"]
        if name == "Intro" and i < 2:
            drums += ["closed_hat:1"] * 4
        else:
            first = i == 0
            drums += [f"{'[kick,crash]' if first else 'kick'}:1", "[snare,closed_hat]:1", "kick:0.5", "closed_hat:0.5", "[snare,closed_hat]:1"]

spec = {
    "title": "Morning Walk",
    "bpm": 96,
    "time_signature": "4/4",
    "key": "C major",
    "parts": [
        {"name": "Lead", "instrument": "flute", "dynamic": "f", "mix": {"reverb": "30%", "pan": 0.1}, "notes": lead},
        {"name": "Keys", "instrument": "electric piano", "dynamic": "mp", "mix": {"pan": -0.25, "reverb": "20%"}, "notes": keys},
        {"name": "Bass", "instrument": "electric bass", "dynamic": "mf", "notes": bass},
        {"name": "Drums", "is_percussion": True, "dynamic": "mf", "notes": drums},
    ],
}

out = Path(__file__).with_name("example-score.json")
out.write_text(json.dumps(spec, indent=1))
print(out, {p["name"]: len(p["notes"]) for p in spec["parts"]})
