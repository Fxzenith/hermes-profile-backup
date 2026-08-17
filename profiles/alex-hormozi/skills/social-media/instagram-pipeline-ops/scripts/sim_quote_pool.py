#!/usr/bin/env python3
"""No-repeat/determinism simulation for the Instagram quote pool.

Usage:
    python3 sim_quote_pool.py <repo_root> [scratch_state.json] [selections]

Runs quote_pool over consecutive days (morning + evening slots) against a
SCRATCH state file — the production logs/quote_pool_state.json is never
touched (audit log is redirected to scratch as well). Default: 100
selections (50 days). Exits 0 if:
  - the two slots never collide on the same day,
  - the first POOL_SIZE assignments are all distinct (no repeat before
    exhaustion),
  - after recycle, no card repeats back-to-back across the day boundary,
  - re-picking an already-assigned (date, slot) returns the same card with no
    new history entry (determinism),
  - every assignment records a selection reason ("why").
"""
import json
import sys
import tempfile
from pathlib import Path


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) not in (1, 2, 3):
        print(__doc__)
        return 2
    repo = Path(args[0]).resolve()
    sys.path.insert(0, str(repo / "scripts"))

    import quote_pool as qp
    import cron_post  # noqa: F401 (provides TEMPLATES)

    tmpdir = Path(tempfile.mkdtemp(prefix="qp_sim_"))
    scratch = Path(args[1]) if len(args) >= 2 and args[1] else tmpdir / "state.json"
    scratch.unlink(missing_ok=True)
    qp.STATE_FILE = scratch
    qp.LOG_FILE = tmpdir / "quote_pool.log"  # keep sim noise out of prod audit
    qp.set_templates(cron_post.TEMPLATES)
    pool_size = len(qp._POOL)

    selections = int(args[2]) if len(args) >= 3 and args[2] else 100
    days = (selections + 1) // 2  # 2 slots/day; round up

    seen_m, seen_e = [], []
    for d in range(days):
        day = f"2026-09-{d + 1:02d}"
        m = qp.pick("morning", day)["id"]
        e = qp.pick("evening", day)["id"]
        assert m != e, f"same-day collision on {day}: {m} == {e}"
        seen_m.append(m)
        seen_e.append(e)

    picks = [x for pair in zip(seen_m, seen_e) for x in pair][:selections]
    assert len(picks) == selections, f"expected {selections} picks, got {len(picks)}"
    first = picks[:pool_size]
    assert len(set(first)) == pool_size, \
        f"repeat before exhaustion: {first} (pool={pool_size})"
    # After recycle: no back-to-back repeat across the evening->morning boundary.
    for prev_e, next_m in zip(seen_e, seen_m[1:]):
        assert prev_e != next_m, f"back-to-back repeat: {prev_e}"

    # Determinism: re-picking an assigned (date, slot) must be stable & history-free.
    state = qp.load_state()
    hist_len = len(state["history"])
    again = qp.pick("morning", "2026-09-01")["id"]
    assert again == seen_m[0], "re-pick returned a different card!"
    assert len(qp.load_state()["history"]) == hist_len, "re-pick added history!"

    # Every assignment records why it was chosen.
    whys = {h.get("why", "") for h in state["history"]}
    assert whys and "" not in whys, "some history entries lack a selection reason"

    log_lines = qp.LOG_FILE.read_text().splitlines()
    assert len(log_lines) == len(state["history"]), \
        f"audit log lines ({len(log_lines)}) != history entries ({len(state['history'])})"

    print(f"PASS: {selections} selections over {days} days, pool={pool_size} cards")
    print(f"  first {pool_size} picks all distinct (no repeat before exhaustion)")
    print(f"  no same-day collision, no back-to-back repeat, deterministic re-pick")
    print(f"  {len(state['history'])} assignments, all with a 'why' reason")
    print(f"  audit log: {qp.LOG_FILE}")
    for line in log_lines[:8]:
        print(f"    {line}")
    if len(log_lines) > 8:
        print(f"    … ({len(log_lines) - 8} more lines)")
    scratch.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())