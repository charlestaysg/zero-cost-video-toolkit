#!/usr/bin/env python3
"""Generate a vocal song (or instrumental-style track) with the Mureka API.

Paid API: each song is charged to your Mureka account. Check Mureka's terms before you publish.

API key lookup order (the key is never written to disk by this script):
  1. MUREKA_API_KEY environment variable
  2. macOS Keychain generic password, service "mureka-api-key" by default
     (add it once with: security add-generic-password -a "$USER" -s mureka-api-key -w)
     Use another service name with --keychain-service or MUREKA_KEYCHAIN_SERVICE.

Examples:
  # Your lyrics ([Verse]/[Chorus] markers help) + style direction
  python mureka_song.py --lyrics lyrics.txt --prompt "upbeat acoustic pop, hand claps, 110 bpm" --gender male

  # Two takes to choose from (charged per song)
  python mureka_song.py --lyrics lyrics.txt --prompt "mandarin pop ballad" --n 2

  # No lyrics: describe the song and let Mureka write it
  python mureka_song.py --describe "a bright summer love song with a catchy chorus" --styles pop,folk

  # Extend an existing song (any mp3/m4a under 10 MB,) from 0:45
  # with new sections; --lyrics holds only the lines to add
  python mureka_song.py --extend-audio song.mp3 --extend-at 45000 --lyrics new-sections.txt --model mureka-8

Output: <out-dir>/<title>-<timestamp>[-N].mp3 (default out/music), plus a .json with the task
result (includes per-line and per-word lyric timestamps, useful for lyric videos).
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

BASE = "https://api.mureka.ai"
MODELS = ["auto", "mureka-7.6", "mureka-o2", "mureka-8", "mureka-9", "mureka-9.5"]
DONE = {"succeeded", "failed", "timeouted", "cancelled"}


def get_api_key(service):
    key = os.environ.get("MUREKA_API_KEY")
    if key:
        return key.strip()
    try:
        out = subprocess.run(
            ["security", "find-generic-password", "-s", service, "-w"],
            capture_output=True, text=True, check=True,
        )
        return out.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        sys.exit("No API key. Set MUREKA_API_KEY or add Keychain item '%s'." % service)


def call(method, path, key, body=None):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode("utf-8") if body is not None else None,
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        sys.exit("HTTP %s on %s: %s" % (e.code, path, e.read().decode("utf-8", "replace")[:1000]))


def upload_audio(path, key):
    """POST /v1/files/upload (multipart, purpose=audio) -> file id."""
    boundary = "----mureka%d" % int(time.time() * 1000)
    with open(path, "rb") as f:
        data = f.read()
    ctype = "audio/mp4" if path.lower().endswith(".m4a") else "audio/mpeg"
    body = b"".join([
        ("--%s\r\nContent-Disposition: form-data; name=\"purpose\"\r\n\r\naudio\r\n" % boundary).encode(),
        ("--%s\r\nContent-Disposition: form-data; name=\"file\"; filename=\"%s\"\r\nContent-Type: %s\r\n\r\n"
         % (boundary, os.path.basename(path), ctype)).encode(),
        data,
        ("\r\n--%s--\r\n" % boundary).encode(),
    ])
    req = urllib.request.Request(
        BASE + "/v1/files/upload", data=body, method="POST",
        headers={"Authorization": "Bearer " + key, "Content-Type": "multipart/form-data; boundary=" + boundary},
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            return json.loads(resp.read().decode("utf-8"))["id"]
    except urllib.error.HTTPError as e:
        sys.exit("HTTP %s on upload: %s" % (e.code, e.read().decode("utf-8", "replace")[:1000]))


def download(url, path):
    req = urllib.request.Request(url, headers={"User-Agent": "mureka-song.py"})
    with urllib.request.urlopen(req, timeout=300) as resp, open(path, "wb") as f:
        f.write(resp.read())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--lyrics", help="Path to a lyrics file (max 5000 chars)")
    src.add_argument("--describe", help="Prompt-to-song: describe the song, Mureka writes lyrics")
    ap.add_argument("--prompt", help="Music/vocal direction for --lyrics (max 1024 chars)")
    ap.add_argument("--styles", help="Comma-separated styles for --describe (pop,rock,jazz,r&b,edm,ambient,folk,latin,k-pop,j-pop,house,gospel,lo-fi)")
    ap.add_argument("--gender", choices=["female", "male"], help="Preferred vocal gender (--lyrics only)")
    ap.add_argument("--model", default="mureka-9.5", choices=MODELS, help="Default mureka-9.5 (newest)")
    ap.add_argument("--n", type=int, default=1, choices=[1, 2, 3], help="Number of takes (charged per song, default 1)")
    ap.add_argument("--title", default="song", help="Used in the output filename")
    ap.add_argument("--format", default="mp3", choices=["mp3", "flac", "wav"], help="Download format")
    ap.add_argument("--extend-audio", help="Extend this mp3/m4a (<10 MB) instead of generating; needs --lyrics and --extend-at")
    ap.add_argument("--extend-at", type=int, help="Extend from this point in ms (mureka-7.6: 8000-420000)")
    ap.add_argument("--extend-type", default="tail", choices=["tail", "head"], help="mureka-8 only (default tail)")
    ap.add_argument("--out-dir", default="out/music", help="Where to save the songs (default out/music)")
    ap.add_argument("--keychain-service", default=os.environ.get("MUREKA_KEYCHAIN_SERVICE", "mureka-api-key"),
                    help="macOS Keychain service holding the key (default mureka-api-key)")
    ap.add_argument("--dry-run", action="store_true", help="Print the request body and exit")
    args = ap.parse_args()

    if args.extend_audio:
        if not args.lyrics or args.extend_at is None:
            sys.exit("--extend-audio needs --lyrics and --extend-at")
        if args.model not in ("mureka-7.6", "mureka-8"):
            sys.exit("Extend supports --model mureka-7.6 or mureka-8")
        with open(args.lyrics, encoding="utf-8") as f:
            lyrics = f.read().strip()
        path = "/v1/song/extend"
        body = {"lyrics": lyrics, "extend_at": args.extend_at, "model": args.model}
        if args.model == "mureka-8":
            body["extend_type"] = args.extend_type
    elif args.lyrics:
        with open(args.lyrics, encoding="utf-8") as f:
            lyrics = f.read().strip()
        if not lyrics:
            sys.exit("Lyrics file is empty")
        path = "/v1/song/generate"
        body = {"lyrics": lyrics, "model": args.model, "n": args.n}
        if args.prompt:
            body["prompt"] = args.prompt
        if args.gender:
            body["gender"] = args.gender
    else:
        path = "/v1/song/easy-generate"
        body = {"prompt": args.describe, "model": args.model, "n": args.n}
        if args.styles:
            body["styles"] = [s.strip() for s in args.styles.split(",") if s.strip()]

    if args.dry_run:
        print("POST " + path)
        print(json.dumps(body, indent=2, ensure_ascii=False))
        return

    key = get_api_key(args.keychain_service)
    if args.extend_audio:
        body["upload_audio_id"] = upload_audio(args.extend_audio, key)
        print("Uploaded %s -> %s" % (os.path.basename(args.extend_audio), body["upload_audio_id"]), file=sys.stderr)
    task = call("POST", path, key, body)
    task_id = task.get("id")
    if not task_id:
        sys.exit("No task id in response: %s" % task)
    print("Task %s (%s) submitted, polling..." % (task_id, task.get("model")), file=sys.stderr)

    start, last = time.time(), None
    while task.get("status") not in DONE:
        if time.time() - start > 900:
            sys.exit("Gave up after 15 min; task %s still %s" % (task_id, task.get("status")))
        time.sleep(8)
        task = call("GET", "/v1/song/query/%s" % task_id, key)
        if task.get("status") != last:
            last = task.get("status")
            print("  status: %s" % last, file=sys.stderr)

    if task["status"] != "succeeded":
        sys.exit("Task %s %s: %s" % (task_id, task["status"], task.get("failed_reason", "")))

    slug = re.sub(r"[^a-z0-9]+", "-", args.title.lower()).strip("-") or "song"
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = args.out_dir
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.join(out_dir, "%s-%s" % (slug, stamp))

    with open(base + ".json", "w", encoding="utf-8") as f:
        json.dump(task, f, indent=2, ensure_ascii=False)

    url_field = {"mp3": "url", "flac": "flac_url", "wav": "wav_url"}[args.format]
    choices = task.get("choices") or []
    for c in choices:
        url = c.get(url_field) or c.get("url")
        ext = args.format if c.get(url_field) else "mp3"
        suffix = "" if len(choices) == 1 else "-%d" % (c.get("index", 0) + 1)
        out = "%s%s.%s" % (base, suffix, ext)
        download(url, out)
        secs = (c.get("duration") or 0) // 1000
        print("%s  (%d:%02d)" % (out, secs // 60, secs % 60))


if __name__ == "__main__":
    main()
