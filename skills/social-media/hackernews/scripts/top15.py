#!/usr/bin/env python3
"""Fetch the top N trending stories on Hacker News via Composio and print them formatted.

Default N is 15; pass an integer argument to override (e.g. `top15.py 3` for top 3).

Uses `composio execute HACKERNEWS_GET_TOP_STORIES` for the ranked ID list,
then `composio execute HACKERNEWS_GET_ITEM` per story. Requires the Composio
CLI at $HOME/.composio/composio and a logged-in session (composio whoami).
"""
import json
import os
import subprocess
import sys
import time

COMPOSIO = os.path.expanduser("~/.composio/composio")
DEFAULT_TOP_N = 15  # stories when no count argument is given
CALL_TIMEOUT = 60  # seconds per composio execute


def run_exec(slug: str, data: dict) -> dict:
    """Run `composio execute` and parse the JSON payload (tolerates banner prose)."""
    proc = subprocess.run(
        [COMPOSIO, "execute", slug, "-d", json.dumps(data)],
        capture_output=True,
        text=True,
        timeout=CALL_TIMEOUT,
    )
    out = proc.stdout
    idx = out.find("{")
    if idx == -1:
        raise RuntimeError(f"no JSON in output for {slug}: {out[:200]} stderr={proc.stderr[:200]}")
    parsed = json.loads(out[idx:])
    if not parsed.get("successful"):
        raise RuntimeError(f"{slug} failed: {json.dumps(parsed)[:300]}")
    return parsed.get("data", parsed)


def main() -> int:
    if not os.path.exists(COMPOSIO):
        print(f"ERROR: Composio CLI not found at {COMPOSIO}", file=sys.stderr)
        return 1

    top_n = DEFAULT_TOP_N
    if len(sys.argv) > 1:
        raw = sys.argv[1]
        if not raw.isdigit():
            print(f"ERROR: invalid count '{raw}' - pass a number 1-500 (e.g. /hackernews 5)", file=sys.stderr)
            return 1
        top_n = int(raw)
        if top_n < 1:
            print("ERROR: count must be at least 1", file=sys.stderr)
            return 1
        if top_n > 500:
            print(f"note: HN returns at most 500 stories; clamping {top_n} -> 500", file=sys.stderr)
            top_n = 500

    top = run_exec("HACKERNEWS_GET_TOP_STORIES", {"print": "pretty"})
    ids = top.get("story_ids") or top.get("stories") or []
    if not ids:
        print(f"ERROR: no story IDs returned: {json.dumps(top)[:300]}", file=sys.stderr)
        return 1
    ids = ids[:top_n]

    stories = []
    for rank, sid in enumerate(ids, 1):
        try:
            item = run_exec("HACKERNEWS_GET_ITEM", {"id": sid})
            stories.append(
                {
                    "rank": rank,
                    "title": item.get("title") or f"(untitled story {sid})",
                    "url": item.get("url") or f"https://news.ycombinator.com/item?id={sid}",
                    "points": item.get("score"),
                    "comments": item.get("descendants"),
                    "by": item.get("by"),
                    "type": item.get("type"),
                }
            )
        except Exception as exc:  # keep going; one bad story shouldn't kill the list
            stories.append(
                {"rank": rank, "title": f"(fetch failed for id {sid})", "url": f"https://news.ycombinator.com/item?id={sid}", "points": None, "comments": None, "by": None, "error": str(exc)}
            )
        time.sleep(0.3)

    # machine-readable copy for any downstream use
    with open(os.path.expanduser(f"~/.hermes/skills/social-media/hackernews/scripts/last_top{top_n}.json"), "w") as fh:
        json.dump(stories, fh, indent=2)

    for s in stories:
        pts = s.get("points")
        cmts = s.get("comments")
        by = s.get("by") or "?"
        rank = s["rank"]
        if s.get("error"):
            print(f"#{rank} ERROR: {s['title']} ({s['error']})")
        else:
            print(f"#{rank} [{pts}pts, {cmts} comments] {s['title']} | {s['url']} | by {by}")
    return 0


if __name__ == "__main__":
    sys.exit(main())