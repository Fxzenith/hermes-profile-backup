---
name: expert-knowledge
description: Use when the user references a known expert (Alex Hormozi, Naval Ravikant, Paul Graham, Charlie Munger, Elon Musk, or any expert stored in GBrain) and asks "what would X do / recommend / say" or wants to compare experts or consult an "expert council". Drives Expert Query Mode on top of GBrain.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [gbrain, experts, advisory, reasoning, knowledge]
    related_skills: [gbrain, grounded-citations]
---

# Expert Knowledge (GBrain Advisory Council)

Use GBrain as the **single source of truth** for expert knowledge. Do NOT build a
separate database. When the user names an expert or asks for an expert-style
recommendation, activate Expert Query Mode.

## When this skill applies

Trigger phrases / patterns:
- "What would <Expert> do / recommend / say about…"
- "How would <Expert> approach…"
- "Compare <Expert A> and <Expert B> on…"
- "Ask the expert council" / "Which expert's framework fits this problem?"
- "Research <Expert>'s views on <topic>"
- "Update <Expert>'s profile with this source"

If the named person is NOT in GBrain (`gbrain list --type person --tag expert`
returns nothing for them), either (a) say so and ask if the user wants to create
the profile, or (b) proceed as a normal reasoning task without expert framing.

## Core invariant (guardrails)

- Never fabricate expert opinions, quotes, sources, URLs, or timestamps.
- Every claim tied to an expert MUST trace to a GBrain `atom` page with a
  `source_*` field, or be explicitly labelled **[Inference — Hermes' application]**.
- Never impersonate: say "Based on Alex Hormozi's documented principles…", never
  "I am Alex Hormozi and I would…".
- Preserve contradictions: if two sources disagree, present both and label the
  context; do not silently overwrite.
- Distinguish **Direct Knowledge** (expert explicitly taught) from **Application**
  (you applying their framework to the user's situation).

## Mechanical steps (do these with the terminal, not from memory)

GBrain is the canonical store. Resolve experts and pull knowledge with the CLI:

```bash
# 1. List stored experts
gbrain list --type person --tag expert

# 2. Retrieve an expert's knowledge (keyword search; works without embeddings)
gbrain search "<topic or expert name>"
# or scoped to the expert namespace:
gbrain search "<topic>" | grep "experts/<expert-slug>/"

# 3. Read a specific knowledge atom
gbrain get "experts/<expert-slug>/<atom-slug>"
```

The `gbrain` binary is on PATH in this environment (`/root/.bun/bin/gbrain`,
symlinked from `/root/gbrain`). If not on PATH, use:
`cd /root/projects/gbrain && bun run src/cli.ts <command>`.

Expert slugs: `alex-hormozi`, `naval-ravikant`, `paul-graham`, `charlie-munger`,
`elon-musk`. Adding a new expert = create `experts/<slug>/profile` (type: person,
expert: true) plus `atom` pages for each principle/framework.

## Knowledge schema (frontmatter on each atom page)

```yaml
type: atom
subtype: extraction
expert: <Name>
topic: <Domain>              # Offers, Pricing, Startups, Investing…
ktype: <Framework|Principle|Strategy|Mental Model|Tactic|Process|Example|Warning|Common Mistake|Opinion|Observation|Definition>
principle: "<one-sentence core claim>"
explanation: "<concise explanation>"
application: "<how to apply it>"
source_title: "<verifiable source>"
source_type: book|video|podcast|article|interview
source_url: "<url or 'n/a'>"
tags: [offers, pricing, value]
confidence: High|Medium|Low
```

## Expert Query Mode — response format

When answering "What would X do about Y?":

1. **Retrieve** relevant atoms from GBrain (keyword search + read pages).
2. **State the expert's relevant frameworks** — label this section
   **Direct Knowledge** and cite the GBrain slug + source.
3. **Apply to the user's situation** — label this section
   **Application (Hermes' inference)**. Combine:
   `Expert Knowledge + User Situation + User Goals + Project Context`.
4. **Concrete next actions** for the user's specific case (not generic advice).
5. **Confidence** — if evidence is thin, say so; if contradictions exist, show them.

For **Multi-Expert / Council** questions, structure as:
- **<Expert A> Perspective** (Direct Knowledge + Application)
- **<Expert B> Perspective** (Direct Knowledge + Application)
- **Where They Agree**
- **Where They Differ**
- **Recommended Approach** (synthesis for the user's situation)

For **"Which expert fits this problem?"** — retrieve by relevance, not
popularity. Match the problem domain to each expert's `domains` field in their
GBrain profile, then synthesize.

## Adding / updating knowledge (continuous learning)

To ingest a new source about an expert (YouTube, book, article):

1. Process the source; extract principles/frameworks/strategies; drop filler.
2. Before storing, **dedupe**: `gbrain search "<principle>"` — if a near-identical
   atom exists, update it (add the new `source_*` line, raise `confidence` when
   repeatedly supported) instead of creating a duplicate.
3. Store each atom via:
   `gbrain put "experts/<slug>/<atom-slug>" --content "$(cat file.md)"`
4. If a new source **contradicts** an existing atom, add a new atom or a
   `## Contradictions` section on the existing page — never silently overwrite.
5. Profile page = index; link/reference its atoms.

Keep all knowledge inside GBrain. No second database.
