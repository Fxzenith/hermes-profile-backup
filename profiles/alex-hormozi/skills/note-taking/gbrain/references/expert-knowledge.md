# Expert Profiles in GBrain (Advisory Council pattern)

Store structured expert knowledge as GBrain pages — do NOT build a separate
expert DB. Two page types:

## 1. Expert index page (`person` type)
Slug: `experts/<slug>/profile`, e.g. `experts/alex-hormozi/profile`.
Frontmatter:
```yaml
---
type: person
expert: true
name: Alex Hormozi
domains: [Offers, Sales, Marketing, Business, Entrepreneurship, Pricing]
sources: ["Book: $100M Offers (2021)", "YouTube: Acquisition.com"]
profile: >- short bio
---
```
Body = index; link to the atom pages below. The `experts/` category must be
registered in `gbrain.yml` under `storage.db_tracked` (already added).

## 2. Knowledge atoms (`atom` type)
Slug: `experts/<slug>/<kebab-topic>`. One principle/framework per page.
Frontmatter (the contract Hermes retrieves on):
```yaml
---
type: atom
subtype: extraction
expert: Alex Hormozi
topic: Offers
ktype: Framework|Principle|Strategy|Mental Model|Tactic|Process|Example|Warning|Common Mistake|Opinion|Observation|Definition
principle: "one-line statement"
explanation: "..."
application: "..."
source_title: "..."
source_type: book|video|podcast|article|interview
source_url: "..."
tags: [offers, pricing]
confidence: High|Medium|Low
---
```
`ktype` = knowledge category. `confidence` rises as more sources support it.

## Storage
```bash
gbrain put experts/alex-hormozi/profile --content "$(cat page.md)"
gbrain put experts/alex-hormozi/offer-equation --content "$(cat atom.md)"
```
`auto_links` will flag unresolved `sources` names — harmless; they are prose
references, not pages to link.

## Retrieval (this box: embeddings NOT generated)
`gbrain query` (hybrid/semantic) returns "No results" because the configured
embedding model (`nvidia:llama-nemotron-embed-vl-1b-v2`) needs `NVIDIA_API_KEY`,
unset here, so `gbrain embed --all` aborts. **Use `gbrain search` (tsvector
keyword) instead** — works headless, zero keys:
```bash
gbrain search "Hormozi offer pricing"
```
Returns `[score] slug -- title`. Then `gbrain get <slug>` for full content.

## Expert Query Mode (Hermes behavior)
When the user names an expert + a problem:
1. `gbrain search "<expert> <topic>"` → relevant atom slugs.
2. `gbrain get` each → read `principle`/`explanation`/`application`/`confidence`/`source_*`.
3. Apply to the user's situation. Label clearly:
   - **Direct knowledge**: expert explicitly taught (cite `source_title`).
   - **Application/Inference**: Hermes' reasoning from the principle.
4. Never impersonate ("I am Alex Hormozi…"). Never fabricate sources/quotes.
5. Multi-expert: search each, compare agree/differ, synthesize.

## Deduplication / continuous learning
Before `put`, `gbrain search` for the same principle. If found, `gbrain get` +
`put` the updated version (add source, raise `confidence`). Contradictions: keep
both, record context — do not silently overwrite.
