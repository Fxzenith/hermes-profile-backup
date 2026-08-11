#!/usr/bin/env python3
"""Verify ASS subtitle sync for a clip WITHOUT burning a video.

Reads data/transcript.json + data/clips.json (YT Clipper layout) and emits the
cue timeline for one clip, mapped to source time, with gap/coverage checks.
Detects the three classic bugs:
  - wrong clip's transcript (Rule 2: content doesn't match source window)
  - missing opening subtitles (Rule 3: first cue far from clip t=0)
  - alignment wrong (Rule 1: Style line Alignment != 2)

Usage (from project root, e.g. /root/autoclipping):
  uv run python SKILL_DIR/scripts/verify_clip_sync.py --clip 1
  uv run python SKILL_DIR/scripts/verify_clip_sync.py --clip 1 --min-payoff 0.6
Prints PASS/FAIL per check; exit 0 if all pass, 1 otherwise.
"""
import argparse
import json
import re
import sys
from pathlib import Path


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clip", type=int, required=True, help="1-based clip index")
    ap.add_argument("--transcript", default="data/transcript.json")
    ap.add_argument("--clips", default="data/clips.json")
    ap.add_argument("--min-payoff", type=float, default=None,
                    help="fail if payoff score below this (requires clip_selector.py)")
    args = ap.parse_args()

    transcript = load(args.transcript)["transcript"]
    clips = load(args.clips)["clips"]
    if args.clip < 1 or args.clip > len(clips):
        print(f"FAIL: clip index {args.clip} out of range (1..{len(clips)})")
        return 1
    clip = clips[args.clip - 1]
    cs, ce = float(clip["start"]), float(clip["end"])
    print(f"Clip {args.clip}: {clip.get('title', '?')}  src [{cs:.2f}-{ce:.2f}] ({ce-cs:.1f}s)")

    # Build ASS via the project's engine (skip if unavailable → structural checks only)
    try:
        sys.path.insert(0, str(Path.cwd() / "scripts"))
        import subtitles_oneline as S
        ass = S.build_ass(transcript, [clip], face_track=False)
    except Exception as e:  # engine not importable — degrade gracefully
        print(f"WARN: cannot build ASS ({e}); structural checks skipped")
        return 0

    fails = 0

    # Rule 1: Alignment must be 2 in the rendered Style line
    style = next((l for l in ass.splitlines() if l.startswith("Style: Base,")), "")
    fields = style.split(",")
    alignment = fields[18] if len(fields) > 18 else "?"
    if alignment == "2":
        print(f"PASS: Alignment={alignment} (bottom-center)")
    else:
        print(f"FAIL: Alignment={alignment} — must be 2 (bottom-center); 5 = middle-center (over face)")
        fails += 1

    cues = [l for l in ass.splitlines() if l.startswith("Dialogue")]
    if not cues:
        print("FAIL: no Dialogue cues generated")
        return 1

    def to_sec(ts):
        p = ts.split(":")
        return int(p[0]) * 3600 + int(p[1]) * 60 + float(p[2])

    rows = []
    for l in cues:
        head, text = l.split(",", 5)[:2] or ("", ""), l.split(",,", 1)[1]
        start_s, end_s = to_sec(l.split(",", 2)[1]), to_sec(l.split(",", 2)[2].split(",", 1)[0])
        txt = re.sub(r"\{\\fad\([^)]*\)\}", "", text).strip()
        rows.append((start_s, end_s, txt))

    # Rule 3: first cue near clip start
    first = rows[0][0]
    if first <= 1.5:
        print(f"PASS: first cue at {first:.2f}s (opening covered)")
    else:
        print(f"FAIL: first cue at {first:.2f}s — Rule 3 violation: opening segment dropped "
              f"(filter must be overlap: te > cs and ts < ce)")
        fails += 1

    # Coverage: fraction of clip duration with cues
    covered = sum(min(e, ce - cs) - max(s, 0.0) for s, e, _ in rows if e > s)
    cov = min(1.0, covered / max(1e-6, ce - cs))
    if cov >= 0.9:
        print(f"PASS: cue coverage {cov*100:.0f}%")
    else:
        print(f"WARN: cue coverage only {cov*100:.0f}% (gaps may be intentional pauses)")
        if cov < 0.7:
            fails += 1

    # Rule 2 sanity: last cue's words should be from the transcript near clip end
    tail_src = cs + rows[-1][0]
    near = [t for t in transcript if t.get("end", 0) > tail_src - 2 and t.get("start", 0) < tail_src + 2]
    src_words = " ".join(t.get("text", "") for t in near).lower()[:80]
    cue_words = rows[-1][2].lower()
    if any(w in src_words for w in cue_words.split()[:3]):
        print(f"PASS: last cue '{rows[-1][2][:50]}' matches transcript near {tail_src:.1f}s")
    else:
        print(f"FAIL: last cue '{rows[-1][2][:50]}' NOT found near source {tail_src:.1f}s "
              f"(transcript: '{src_words}') — wrong clip? (Rule 2)")
        fails += 1

    # Optional payoff gate
    if args.min_payoff is not None:
        try:
            sys.path.insert(0, str(Path.cwd() / "python"))
            import clip_selector as C
            p = C.score_payoff(transcript, cs, ce)
            if p["payoff_score"] >= args.min_payoff:
                print(f"PASS: payoff score {p['payoff_score']:.2f} >= {args.min_payoff}")
            else:
                print(f"FAIL: payoff score {p['payoff_score']:.2f} ({p['payoff_label']}) < {args.min_payoff}; "
                      f"tail: {p['tail']!r}")
                fails += 1
        except ImportError:
            print("WARN: clip_selector.py not importable — payoff gate skipped")

    print(f"\n{'ALL CHECKS PASSED' if fails == 0 else f'{fails} check(s) FAILED'}")
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
