# GBrain Advisor Bot — gotchas (verified 2026-08-17)

## 1. gbrain needs PATH
gbrain is a bun CLI installed at `~/.bun/bin`. Always inject into subprocess env:
```python
env = dict(os.environ)
env["PATH"] = os.path.expanduser("~/.bun/bin") + ":" + env.get("PATH","")
```

## 2. gbrain query output format
A query prints scored, prefixed lines:
```
[2.0000] experts/alex-hormozi/closer-framework -- expert: Alex Hormozi
subtype: framework
principle: CLOSER: the 6-part sales-call script structure
```
Extract slug (NOT the score):
```bash
gbrain query "$q" --limit 8 2>/dev/null \
  | grep 'experts/alex-hormozi/' \
  | sed -E 's/^\[[^]]*\] +//' \
  | awk '{print $1}'
```

## 3. Hybrid search misses generic prompts
"email sequence for a coaching offer" returns nothing. Fan out over framework
vocabulary and merge top results:
```bash
for d in offer "lead magnet" sales pricing value "three pillar pitch" \
         "closer framework" "cta formula" focus; do
  gbrain query "$d" --limit 4 2>/dev/null | grep 'experts/alex-hormozi/'
done | sed -E 's/^\[[^]]*\] +//' | awk '{print $1}' | sort -u | head -6
```

## 4. UPGRADE_AVAILABLE banner
gbrain may print `UPGRADE_AVAILABLE 0.42.59.0 -> 0.46.12.3` to stdout. Filter by
grepping the slug prefix so the banner never enters the parsed slug list.

## 5. Free model latency
hy3-free via OpenCode Zen is slow: a 3-email draft took 3–5 min. Set
`requests.post(..., timeout=180)` and run long prompts with terminal
`background=true, notify_on_complete=true`. A foreground call hit the 150s/300s
cap and timed out.

## 6. Cross-profile write guard
Editing another profile's files from `default` raises a soft guard. Pass
`cross_profile=True` to write_file, or use terminal. The target profile's own
sessions auto-supply its `.env` keys (so a bot in profile X uses X's
`OPENCODE_ZEN_API_KEY` without manual export).

## 7. Slash command = skill name
A profile skill's `name` becomes its `/slash` trigger. Name it `hormozi`
(not `hormozi-advisor`) so `/hormozi` fires. If a rename isn't picked up, the
skills prompt snapshot may need a rebuild on next launch.

## 8. Key identity mismatch trap
The profile `.env` may hold a DIFFERENT valid key than the one the user pasted
this session. Always compare key tails before assuming "it's using the key I
gave." To force a specific key, rewrite the `^OPENCODE_ZEN_API_KEY=` line in
`<profile>/.env`.
