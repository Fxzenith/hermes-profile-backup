# gbrain capture / ingest pitfalls (verified)

Compiled from a live re-ingest that failed twice. Use this instead of guessing.

## Failure transcript (what NOT to do)

Task: ingest 11 pages (10 `concept` + 1 `atom`) for the Hormozi expert notes under
`experts/alex-hormozi/`.

**Mistake A — tight bash loop, `--quiet`:**
```bash
for slug in "${!pages[@]}"; do
  gbrain capture --file "$f" --slug "$slug" --type "$typ" --quiet 2>/dev/null
done
```
Result: `--quiet` swallowed the returned slug; loop ran so fast the daemon raced the
writes. Later `gbrain get` → `page_not_found` for 10/11.

**Mistake B — wrong separator + twin + cascade delete:**
A loop built slugs with underscores (`experts_alex-hormozi_ci-niche-down`) instead of
slashes (`experts/alex-hormozi/ci-niche-down`). Both file bodies were identical, so
they shared a content_hash. After the real slash-slug pages were captured, the
underscore twins were `gbrain delete`d to "clean up" — and **deleting the underscore
twin cascade-deleted the slash-slug sibling** (same content_hash). Result: pages
vanished in pairs.

**Symptom that gives it away:** `capture` says `status: created_or_updated`, but a
later `gbrain get` says `page_not_found`. `gbrain list` / `gbrain search` also showed
only 1 of 11 — misleading, because list/search have page-size/sort limits that hide
fresh pages; `get` is the ground-truth check.

## What actually worked (reproducible)

1. Write each page to a file first (so the body is fixed and identical per slug — but
   use ONE canonical slug, never a twin).
2. Capture each slug in its OWN terminal call (no loop), e.g.:
   ```bash
   export PATH="$HOME/.bun/bin:$PATH"; cd /root/gbrain
   gbrain capture --file /root/ci_pages/experts_alex-hormozi_ci-niche-down.md \
     --slug "experts/alex-hormozi/ci-niche-down" --type concept
   ```
3. Verify each in a SEPARATE call (do not delete anything between capture and verify):
   ```bash
   gbrain get "experts/alex-hormozi/ci-niche-down"   # expect frontmatter + body
   ```
4. If `get` reports missing, re-capture that one slug and re-`get`. Retry is cheap and
   reliable; the isolated single capture is the stable unit.
5. Only after ALL `get`s pass, clean up helper files. Do NOT `gbrain delete` any slug
   you want to keep, and never delete a slug that shares a content_hash with a keeper.

## Slug separator rule for THIS brain
Slash slugs: `experts/<expert>/<kebab-slug>`. Underscores create separate pages that
can collide on content_hash and cascade-delete. Match the existing namespace exactly.

## Frontmatter note for expert atoms
Use `knowledge_basis: direct` (expert explicitly taught) or `application` (Hermes'
inference) on expert pages — makes the Direct-Knowledge-vs-Application invariant
machine-readable per page. Convention + retrieval workflow: `references/expert-knowledge.md`.
