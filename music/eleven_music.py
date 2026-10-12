#!/usr/bin/env python3
"""Generate a song with the ElevenLabs Music API.

Paid API: usage is charged to your ElevenLabs account. Check ElevenLabs' music terms before you publish.

API key lookup order (the key is never written to disk by this script):
  1. ELEVENLABS_API_KEY environment variable
  2. macOS Keychain generic password, service "elevenlabs-api-key" by default
     (add it once with: security add-generic-password -a "$USER" -s elevenlabs-api-key -w)
     Use another service name with --keychain-service or ELEVENLABS_KEYCHAIN_SERVICE.

Examples:
  # Style prompt only (model writes its own lyrics, or none)
  python eleven_music.py --prompt "upbeat acoustic pop about a morning walk" --seconds 60

  # Your own lyrics: sections marked [Verse], [Chorus] ... in a text file
  python eleven_music.py --lyrics lyrics.txt --style "acoustic pop, warm male vocals, 110 bpm" --seconds 90

  # Instrumental bed for a video
  python eleven_music.py --prompt "calm corporate piano, light percussion" --seconds 45 --instrumental

Output goes to <out-dir>/<title>-<timestamp>.mp3 (default out/music) unless --out is given.
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

API_URL = "https://api.elevenlabs.io/v1/music"
MIN_MS, MAX_CHUNK_MS, MAX_TOTAL_MS = 3000, 120000, 600000


def get_api_key(service):
    key = os.environ.get("ELEVENLABS_API_KEY")
    if key:
        return key.strip()
    try:
        out = subprocess.run(
            ["security", "find-generic-password", "-s", service, "-w"],
            capture_output=True, text=True, check=True,
        )
        return out.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        sys.exit("No API key. Set ELEVENLABS_API_KEY or add Keychain item '%s'." % service)


def parse_sections(text):
    """Split lyrics on [Section] headers -> list of (header, [lines])."""
    sections, header, lines = [], None, []
    for raw in text.splitlines():
        line = raw.strip()
        m = re.match(r"^\[(.+)\]$", line)
        if m:
            if header or lines:
                sections.append((header or "Verse", lines))
            header, lines = m.group(1), []
        elif line:
            lines.append(line)
    if header or lines:
        sections.append((header or "Verse", lines))
    return sections


def build_plan(sections, style, total_ms):
    per = max(MIN_MS, min(MAX_CHUNK_MS, total_ms // max(1, len(sections))))
    styles = [s.strip() for s in style.split(",") if s.strip()] if style else []
    chunks = []
    for header, lines in sections:
        chunks.append({
            "text": "[%s]\n%s" % (header, "\n".join(lines)) if lines else "[%s]" % header,
            "duration_ms": per,
            "positive_styles": styles,
        })
    return {"chunks": chunks}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--prompt", help="Free-text description of the song")
    src.add_argument("--lyrics", help="Path to a lyrics file with [Section] headers")
    ap.add_argument("--style", default="", help="Comma-separated styles (used with --lyrics)")
    ap.add_argument("--seconds", type=int, default=60, help="Target length in seconds (default 60)")
    ap.add_argument("--instrumental", action="store_true", help="Force instrumental (with --prompt)")
    ap.add_argument("--model", default="music_v2_5", help="music_v2_5 (default), music_v2, music_v1")
    ap.add_argument("--title", default="song", help="Used in the output filename")
    ap.add_argument("--out", help="Output .mp3 path")
    ap.add_argument("--out-dir", default="out/music", help="Folder used when --out is not given (default out/music)")
    ap.add_argument("--keychain-service", default=os.environ.get("ELEVENLABS_KEYCHAIN_SERVICE", "elevenlabs-api-key"),
                    help="macOS Keychain service holding the key (default elevenlabs-api-key)")
    ap.add_argument("--dry-run", action="store_true", help="Print the request body and exit")
    args = ap.parse_args()

    total_ms = max(MIN_MS, min(MAX_TOTAL_MS, args.seconds * 1000))
    body = {"model_id": args.model}
    if args.prompt:
        body["prompt"] = args.prompt
        body["music_length_ms"] = total_ms
        if args.instrumental:
            body["force_instrumental"] = True
    else:
        with open(args.lyrics, encoding="utf-8") as f:
            sections = parse_sections(f.read())
        if not sections:
            sys.exit("No lyrics found in %s" % args.lyrics)
        body["composition_plan"] = build_plan(sections, args.style, total_ms)

    if args.dry_run:
        print(json.dumps(body, indent=2))
        return

    slug = re.sub(r"[^a-z0-9]+", "-", args.title.lower()).strip("-") or "song"
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    out = args.out or os.path.join(args.out_dir, "%s-%s.mp3" % (slug, stamp))
    os.makedirs(os.path.dirname(out), exist_ok=True)

    req = urllib.request.Request(
        API_URL + "?output_format=mp3_44100_128",
        data=json.dumps(body).encode("utf-8"),
        headers={"xi-api-key": get_api_key(args.keychain_service), "Content-Type": "application/json"},
        method="POST",
    )
    print("Generating (%ds, %s)... this can take a minute." % (total_ms // 1000, args.model), file=sys.stderr)
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            audio = resp.read()
            song_id = resp.headers.get("song-id") or resp.headers.get("x-song-id")
    except urllib.error.HTTPError as e:
        sys.exit("HTTP %s: %s" % (e.code, e.read().decode("utf-8", "replace")[:1000]))

    with open(out, "wb") as f:
        f.write(audio)
    print(out)
    if song_id:
        print("song id: %s" % song_id, file=sys.stderr)


if __name__ == "__main__":
    main()
