# gbrain query — output format & parsing recipes

`gbrain query "<q>" --limit N` prints one block per hit:

```
[2.0000] experts/alex-hormozi/closer-framework -- expert: Alex Hormozi
subtype: framework
principle: CLOSER: the 6-part sales-call script structure
co...
[0.6156] test -- # Test Brain
```

Gotchas that bite parsers:
1. **Leading `[score]` prefix** — the line starts with `[2.0000]`, NOT the slug.
   - `grep '^experts/` matches nothing.
   - `awk '{print $1}'` captures the score, not the slug.
2. **`UPGRADE_AVAILABLE 0.42.59.0 -> 0.46.12.3` banner** is printed to stdout on every
   `gbrain` invocation. Filter it before parsing: `2>/dev/null` (upgrade line goes to stderr
   in recent versions) or `grep -v UPGRADE_AVAILABLE`.

## Extract slugs for a given expert prefix

```bash
gbrain query "<q>" --limit 8 2>/dev/null \
  | grep 'experts/alex-hormozi/' \
  | sed -E 's/^\[[^]]*\] +//' \
  | awk '{print $1}'
```

Result: `experts/alex-hormozi/closer-framework` (the slug, field 1 after stripping score).

## Fan-out for generic prompts (no lexical match)

```bash
for d in offer "lead magnet" sales pricing value "three pillar pitch" "closer framework" "cta formula"; do
  gbrain query "$d" --limit 6 2>/dev/null \
    | grep 'experts/alex-hormozi/' \
    | sed -E 's/^\[[^]]*\] +//' \
    | awk '{print $1}'
done | sort -u | head -6
```

## Read a note's full text

```bash
gbrain get experts/alex-hormozi/closer-framework
```

## Export all notes of an expert to a single bundle (for hosted/Portal bots)

```bash
export PATH="$HOME/.bun/bin:$PATH"
gbrain export --slug-prefix experts/alex-hormozi --dir /tmp/hb
cat /tmp/hb/experts/alex-hormozi/*.md > /root/hormozi_bot/bot_pack/hormozi_knowledge.md
```

Note: `gbrain export` may pull a few extra pages outside the prefix — check the
`experts/alex-hormozi/` subdir only when bundling.
