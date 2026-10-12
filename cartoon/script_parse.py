"""Shared parser for cartoon scripts.

A script is a markdown file with one section per scene:

    ## S1 — Scene title
    Narration text. {Caption text|spoken text} lets the captions and the voice differ.

Lines starting with ">" are notes and are ignored. Text before the first "## S" heading is ignored.
In dialogue scripts each line is "NAME: text" or "PAUSE".
"""
import re

SCENE_RE = re.compile(r"^## (S\d+)\s*[—–-]+\s*(.*?)\n(.*?)(?=^## |\Z)", re.S | re.M)
CHUNK_RE = re.compile(r"(?:\{[^}]*\}|\S)+")       # whitespace-separated chunks; {...} groups stay whole
BRACE_RE = re.compile(r"\{([^|}]*)\|([^}]*)\}")
SPEAKER_RE = re.compile(r"^([A-Z][A-Z0-9_]*):\s*(.*)$")


def norm(s):
    """Lower-case and strip everything except letters and digits (matches the JS `nrm`)."""
    return re.sub(r"[^a-z0-9]", "", s.lower())


def caption_text(s):
    return BRACE_RE.sub(lambda m: m.group(1), s)


def spoken_text(s):
    return BRACE_RE.sub(lambda m: m.group(2), s)


def units(text):
    """Split text into (caption_chunk, spoken_chunk) pairs, one per whitespace-separated chunk."""
    return [(caption_text(c), spoken_text(c)) for c in CHUNK_RE.findall(text)]


def _body_lines(body):
    return [l.strip() for l in body.strip().splitlines() if l.strip() and not l.strip().startswith(">")]


def parse(path, dialogue=False):
    """Return a list of scenes: {"id", "title", "lines": [{"who", "text"}]}.

    Narration scenes have one line with who=None. Dialogue lines keep the speaker name;
    PAUSE lines become {"who": "PAUSE", "text": ""}.
    """
    src = open(path, encoding="utf-8").read()
    scenes = []
    for sid, title, body in SCENE_RE.findall(src):
        lines = []
        if dialogue:
            for raw in _body_lines(body):
                if raw == "PAUSE":
                    lines.append({"who": "PAUSE", "text": ""})
                    continue
                m = SPEAKER_RE.match(raw)
                if not m:
                    raise SystemExit(f"{sid}: expected 'NAME: text' or PAUSE, got: {raw}")
                lines.append({"who": m.group(1), "text": m.group(2).strip()})
        else:
            lines.append({"who": None, "text": " ".join(_body_lines(body))})
        scenes.append({"id": sid, "title": title.strip(), "lines": lines})
    if not scenes:
        raise SystemExit(f"No '## S1 — Title' sections found in {path}")
    return scenes
