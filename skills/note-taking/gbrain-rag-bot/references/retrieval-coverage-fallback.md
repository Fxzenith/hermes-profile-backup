# Retrieval coverage fallback (boxes without an embedding key)

## Why this exists
`gbrain query` is HYBRID (RRF + vector). It returns a note ONLY if that note has an
embedding. On this VPS `NVIDIA_API_KEY` is unset, so `gbrain embed --all` aborts and
embedding coverage sits at ~1%. Crucially, **`gbrain capture` saves the note but does
NOT auto-embed it** — so a note you just captured is invisible to `query` until someone
runs `gbrain embed` with a key.

Symptom we hit: a RAG bot whose pool mixed embedded (older) and un-embedded (newly
captured) notes returned only the embedded ones on `query`, silently dropping 15 of 17.
`gbrain search` (tsvector keyword) returns ALL notes with zero keys, but it also
misses some phrasings due to tokenization.

## The fix (validated this session)
Build the retrieval layer to merge THREE signals, not just `query`:

1. `gbrain query "<q>" --limit 12`  (hybrid — catches embedded notes)
2. `gbrain search "<q>"`             (keyword — catches un-embedded notes, no key)
3. A per-note canonical-phrase fallback list, guaranteeing reachability even when
   both engines miss (covers long/verbose queries and odd tokenization).

### Slug parsers (Python, against `gbrain` CLI stdout)
```python
import re, subprocess

def _gbrain(args):
    # run with PATH including ~/.bun/bin; strip the UPGRADE_AVAILABLE banner line
    ...

def _slugs_from(out, prefixes, limit=6):
    # query output: "[score] experts/<slug> -- ..."
    pat = re.compile("(?: " + "|".join(re.escape(p) for p in prefixes) + r")([A-Za-z0-9\-]+)")
    slugs = re.findall(pat, out)
    seen, res = set(), []
    for grp in slugs:
        for p in prefixes:
            full = p + grp
            if full in seen: continue
            if full in out:
                seen.add(full); res.append(full); break
        if len(res) >= limit: break
    return res

def _kw_slugs_from(out, prefixes, limit=6):
    # search output: "slug -- # Title"  (slug is the token before ' -- ')
    seen, res = set(), []
    for ln in out.splitlines():
        for p in prefixes:
            if p in ln:
                tok = ln.split(" -- ")[0].strip()
                if tok.startswith(p) and tok not in seen:
                    seen.add(tok); res.append(tok); break
        if len(res) >= limit: break
    return res

# Guaranteed-reachable canonical phrases per note (last resort):
EXPERT_FALLBACK_PHRASES = {
    "experts/alex-hormozi/leads-core-four": "Hormozi Leads Core Four Rule of 100",
    # ...one entry per note in the pool...
}
```

### retrieve() merge order
```python
slugs = []
slugs += _slugs_from(_gbrain(["query", q, "--limit", "12"]), prefixes, k)
slugs += _kw_slugs_from(_gbrain(["search", q]), prefixes, k)
# domain routing (optional) appends biased query+search for matched experts
# dedupe, keep first occurrence
# fallback sweep: for any note whose canonical phrase lexically matches q and not yet present, append
# if still empty: fan out over anchor vocabulary; then search(keyword-stripped q)
```

## Verification
After wiring this, test with a query that should hit a freshly-captured (un-embedded)
note. If it returns ONLY older notes, your `query`-only path is still in play — the
merge is the fix. Confirm via: `gbrain search "<canonical phrase>"` returns the slug
(even when `gbrain query "<phrase>"` returns "No results").

## When embeddings ARE available
Once `NVIDIA_API_KEY` is set and `gbrain embed --stale` runs, `query` coverage climbs
and the fallback becomes a safety net rather than a necessity. Keep the merge anyway —
it costs little and removes a whole class of silent-miss bugs.
