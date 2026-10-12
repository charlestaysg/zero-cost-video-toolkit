#!/usr/bin/env python3
"""Word timings: Whisper each scene clip, align it to the script, write render/words.js.

Usage:
  python timings.py script.example.md --audio ../out/audio [--words render/words.js]
                    [--title 5 --gap 1.2 --credits 12] [--dialogue] [--max-chars 90]

For every s<n>.wav listed in durations.json this:
  1. runs Whisper large-v3-turbo with word timestamps (skipped if s<n>_stt.json already exists;
     use --redo to force),
  2. aligns Whisper's words to the script's spoken words, so cues and captions use your own
     wording rather than what Whisper heard (unmatched words are interpolated),
  3. groups caption text (the caption half of {caption|spoken}) into sentence-sized captions,
  4. writes words.js for the film page and timeline.json for mix.py.

words.js defines:
  window.WORDS[i] = [[spoken_word, start, end, caption_word], ...]   scene i (0-based), seconds
  window.CAPS[i]  = [[start, end, "Caption text"], ...]
  window.AUDN     = [clip duration, ...]
  window.LINES    = {S1: [{who, start, end, text}, ...]} for dialogue, else null
  window.TL       = {title, gap, credits}

It also prints where Whisper heard something different from the script: a quick
pronunciation check. Read those lines before you render.
"""
import argparse
import difflib
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from script_parse import norm, parse, units  # noqa: E402

WHISPER = "openai/whisper-large-v3-turbo"  # the mlx-community/ copy fails with "Processor not found"
HERE = os.path.dirname(os.path.abspath(__file__))


def run_whisper(wav, out_base, model):
    cmd = [sys.executable, "-m", "mlx_audio.stt.generate", "--model", model, "--audio", wav,
           "--output-path", out_base, "--format", "json", "--language", "en",
           "--gen-kwargs", json.dumps({"word_timestamps": True})]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(out_base + ".json"):
        sys.exit(f"Whisper failed on {wav}:\n{r.stderr[-2000:]}")


def whisper_words(path):
    d = json.load(open(path))
    out = []
    for seg in d.get("segments", []):
        for w in seg.get("words", []):
            n = norm(w["word"])
            if n:
                out.append((n, float(w["start"]), float(w["end"]), w["word"].strip()))
    return out


def scene_tokens(scene):
    """Script tokens for one scene: dicts with spoken norm, caption norm, line index, unit index."""
    toks, unit_list = [], []
    for li, line in enumerate(scene["lines"]):
        if line["who"] == "PAUSE":
            continue
        for cap, spoken in units(line["text"]):
            ui = len(unit_list)
            unit_list.append({"cap": cap, "line": li})
            first = True
            for sp in spoken.split():
                n = norm(sp)
                if not n:
                    continue
                toks.append({"w": n, "cap": norm(cap) if first else "", "unit": ui, "line": li})
                first = False
    return toks, unit_list


def align(toks, heard, clip_len):
    """Give every script token a start/end from the Whisper words; interpolate the gaps."""
    sm = difflib.SequenceMatcher(None, [t["w"] for t in toks], [h[0] for h in heard], autojunk=False)
    times = [None] * len(toks)
    for a, b, size in sm.get_matching_blocks():
        for k in range(size):
            times[a + k] = (heard[b + k][1], heard[b + k][2])
    i = 0
    while i < len(toks):
        if times[i] is not None:
            i += 1
            continue
        j = i
        while j < len(toks) and times[j] is None:
            j += 1
        t0 = times[i - 1][1] if i > 0 else 0.0
        t1 = times[j][0] if j < len(toks) else clip_len
        step = max(t1 - t0, 0.0) / (j - i)
        for k in range(i, j):
            times[k] = (t0 + (k - i) * step, t0 + (k - i + 1) * step)
        i = j
    diffs = []
    for op, a0, a1, b0, b1 in sm.get_opcodes():
        if op != "equal":
            said = " ".join(t["w"] for t in toks[a0:a1]) or "(nothing)"
            got = " ".join(h[3] for h in heard[b0:b1]) or "(nothing)"
            diffs.append(f"script: {said!r:40} whisper heard: {got!r}")
    return times, diffs


def captions(toks, times, unit_list, clip_len, max_chars):
    """Group units into sentence-sized captions; each starts at its first spoken word."""
    groups, cur = [], []
    for ui, u in enumerate(unit_list):
        if cur and (u["line"] != unit_list[cur[-1]]["line"]):
            groups.append(cur)
            cur = []
        cur.append(ui)
        text = " ".join(unit_list[x]["cap"] for x in cur)
        ends_sentence = u["cap"].rstrip("\"'”’)").endswith((".", "?", "!", ":"))
        if ends_sentence and len(text) >= max_chars * 0.45 or len(text) >= max_chars:
            groups.append(cur)
            cur = []
    if cur:
        groups.append(cur)
    caps, last_end = [], []
    for g in groups:
        ks = [k for k, t in enumerate(toks) if t["unit"] in g]
        if not ks:
            continue
        caps.append([round(times[ks[0]][0], 3), None, " ".join(unit_list[u]["cap"] for u in g)])
        last_end.append(times[ks[-1]][1])
    for k, c in enumerate(caps):
        nxt = caps[k + 1][0] - 0.12 if k + 1 < len(caps) else clip_len - 0.05
        c[1] = round(min(nxt, last_end[k] + 1.0), 3)  # don't hold a caption through a long pause
    return caps


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("script")
    ap.add_argument("--audio", default="out/audio", help="Folder with s<n>.wav and durations.json")
    ap.add_argument("--words", default=os.path.join(HERE, "render", "words.js"), help="Output JS file")
    ap.add_argument("--model", default=WHISPER)
    ap.add_argument("--dialogue", action="store_true", help="Script uses NAME: lines (tts_dialogue.py)")
    ap.add_argument("--title", type=float, default=5.0, help="Title card length, s (default 5)")
    ap.add_argument("--gap", type=float, default=1.2, help="Pause after each scene, s (default 1.2)")
    ap.add_argument("--credits", type=float, default=12.0, help="Credits length, s (default 12)")
    ap.add_argument("--max-chars", type=int, default=90, help="Rough caption length limit")
    ap.add_argument("--redo", action="store_true", help="Re-run Whisper even if *_stt.json exists")
    args = ap.parse_args()

    durations = json.load(open(os.path.join(args.audio, "durations.json")))
    scenes = {s["id"]: s for s in parse(args.script, dialogue=args.dialogue)}
    lines_path = os.path.join(args.audio, "lines.json")
    lines = json.load(open(lines_path)) if args.dialogue and os.path.exists(lines_path) else None

    WORDS, CAPS, AUDN = [], [], []
    for sid, clip_len in durations.items():
        if sid not in scenes:
            sys.exit(f"{sid} is in durations.json but not in {args.script}")
        base = os.path.join(args.audio, f"{sid.lower()}_stt")
        if args.redo or not os.path.exists(base + ".json"):
            print(f"{sid}: running Whisper...", flush=True)
            run_whisper(os.path.join(args.audio, f"{sid.lower()}.wav"), base, args.model)
        heard = whisper_words(base + ".json")
        toks, unit_list = scene_tokens(scenes[sid])
        times, diffs = align(toks, heard, clip_len)
        print(f"{sid}: {len(toks)} script words, {len(heard)} heard, {len(diffs)} differences")
        for d in diffs:
            print("   ", d)
        WORDS.append([[t["w"], round(a, 3), round(b, 3), t["cap"]] for t, (a, b) in zip(toks, times)])
        CAPS.append(captions(toks, times, unit_list, clip_len, args.max_chars))
        AUDN.append(clip_len)

    starts, t = [], args.title
    for d in AUDN:
        starts.append(round(t, 3))
        t += d + args.gap
    total = round(t + args.credits, 3)
    TL = {"title": args.title, "gap": args.gap, "credits": args.credits}
    os.makedirs(os.path.dirname(os.path.abspath(args.words)), exist_ok=True)
    with open(args.words, "w", encoding="utf-8") as f:
        f.write("// Generated by timings.py. Do not edit by hand.\n")
        f.write("window.WORDS=" + json.dumps(WORDS, ensure_ascii=False) + ";\n")
        f.write("window.CAPS=" + json.dumps(CAPS, ensure_ascii=False) + ";\n")
        f.write("window.AUDN=" + json.dumps(AUDN) + ";\n")
        f.write("window.LINES=" + json.dumps(lines, ensure_ascii=False) + ";\n")
        f.write("window.TL=" + json.dumps(TL) + ";\n")
    tl = dict(TL, starts=starts, total=total, durations=durations)
    json.dump(tl, open(os.path.join(args.audio, "timeline.json"), "w"), indent=1)
    print(f"wrote {args.words} and timeline.json; scene starts {starts}, total {total} s")


if __name__ == "__main__":
    main()
