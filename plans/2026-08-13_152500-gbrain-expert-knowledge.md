# GBrain Expert Knowledge Extension Plan

**Goal:** Extend the existing GBrain system so Hermes can build and use structured knowledge profiles for influential experts, entrepreneurs, investors, creators, authors, and other sources of expertise, making GBrain the central knowledge layer for the system.

**Architecture:** This plan adds expert profile support as an additional layer on top of GBrain's existing schema (people/, companies/, concepts/, ideas/, projects/ directories), using GBrain's hybrid RAG search, embeddings, and knowledge graph capabilities rather than creating a separate database.

**Tech Stack:** GBrain CLI (`/root/.bun/bin/bun`), GBrain schema (people/, concepts/ directories), Hermes plugin integration, custom knowledge extraction pipeline

---
```

# GBrain Expert Knowledge Extension Implementation Plan

## Phase 1: Schema Extension

### Task 1.1: Add Expert Profiles to GBrain Storage
**Objective:** Extend GBrain's gbrain.yml to track expert profiles alongside existing categories.

**Modify `/root/gbrain/gbrain.yml`:**
```yaml
storage:
  db_tracked:
    - people/              # Existing: individual people
    - companies/           # Existing: companies
    - deals/               # Existing: deals
    - concepts/            # Existing: concepts
    - yc/                  # Existing: Y Combinator
    - ideas/               # Existing: ideas
    - projects/            # Existing: projects
    - experts/             # NEW: expert profiles (Alex Hormozi, Naval, etc.)

  db_only:
    - media/x/
    - media/articles/
    - meetings/transcripts/
```

**Step 1:** Edit `/root/gbrain/gbrain.yml` to add `experts/` to `db_tracked`

**Step 2:** Verify gbrain recognizes the new category

**Step 3:** Test with `gbrain people` to ensure structure intact

### Task 1.2: Create Expert Profile Directory Structure
**Objective:** Establish the directory format for expert knowledge.

**Create directory structure:**
```
/root/gbrain/experts/
├── alex-hormozi/          # Expert 1
│   ├── principles/
│   ├── frameworks/
│   ├── strategies/
│   ├── mental-models/
│   ├── examples/
│   ├── warnings/
│   └── metadata.json
├── naval-ravikant/        # Expert 2
│   ├── principles/
│   ├── frameworks/
│   └── ...
├── paul-graham/          # Expert 3
└── ...                    # Future experts
```

**Step 1:** Run `mkdir -p /root/gbrain/experts/alex-hormozi/principles /root/gbrain/experts/alex-hormozi/frameworks /root/gbrain/experts/alex-hormozi/strategies /root/gbrain/experts/alex-hormozi/mental-models /root/gbrain/experts/alex-hormozi/examples /root/gbrain/experts/alex-hormozi/warnings`

**Step 2:** Repeat for initial experts (Naval, Paul Graham, Charlie Munger)

**Step 3:** Verify directory structure created

---

## Phase 2: Knowledge Extraction & Structuring

### Task 2.1: Design Knowledge Item Schema
**Objective:** Define the structure for each knowledge entry within expert profiles.

**Schema format (JSON within .md files or gbrain items):**
```json
{
  "expert": "Alex Hormozi",
  "topic": "Offers",
  "type": "Framework",
  "principle": "Increase the value of an offer relative to its perceived cost.",
  "explanation": "[concise explanation of the principle]",
  "application": "[how this principle can be applied]",
  "source": "Alex Hormozi - YouTube video title",
  "source_url": "https://...",
  "timestamp": "12:34",
  "tags": ["offers", "pricing", "value", "sales"],
  "confidence": "High",
  "related": ["pricing-strategy", "value-prop"]
}
```

**Step 1:** Create a template file format for knowledge items

**Step 2:** Design how GBrain will store these (as separate markdown files in expert directories, or as structured entries in GBrain's database)

**Step 3:** Test that GBrain can read and search these items

### Task 2.2: Implement Knowledge Extraction Pipeline
**Objective:** Process raw content through the extraction pipeline.

**Pipeline steps:**
```
Raw Content
↓
1. Identify expert source
2. Extract principles, frameworks, strategies
3. Remove filler/repetition
4. Categorize by type (Principle, Framework, Mental Model, Strategy, Tactic, Process, Example, Warning, Common Mistake, Opinion, Observation, Definition)
5. Structure with metadata (expert, topic, type, source, tags, confidence)
6. Store in GBrain experts/ directory
7. Preserve source reference
```

**Step 1:** Create extraction script that takes YouTube transcript or article

**Step 2:** Implement principle/framework identification logic

**Step 3:** Add categorization by knowledge type

**Step 4:** Structure output with all metadata fields

**Step 5:** Store in appropriate expert directory

### Task 2.3: Add Deduplication Logic
**Objective:** Prevent duplicate knowledge entries.

**Dedup algorithm:**
1. When adding new knowledge, search GBrain experts/ for similar principles
2. Check if principle already exists (same or very similar wording)
3. If exists: update existing knowledge, add new source reference, increase confidence
4. If contradicts: store difference, record context, allow Hermes to explain variation
5. Use cosine similarity on embeddings or text matching

**Step 1:** Implement search against existing principles before adding

**Step 2:** Create update logic for existing entries

**Step 3:** Add contradiction handling

**Step 4:** Test with duplicate principle scenarios

---

## Phase 3: Source Traceability

### Task 3.1: Implement Source Metadata Storage
**Objective:** Ensure all knowledge is traceable to its source.

**Required metadata for each knowledge item:**
- Source title
- Source type (YouTube, book, podcast, interview, article)
- URL (when available)
- Publication date (when available)
- Timestamp (when available from source)
- Relevant section/topic

**Step 1:** Design source metadata format

**Step 2:** Extract from available sources during knowledge processing

**Step 3:** Store alongside each knowledge item

**Step 4:** Verify search can return source information

### Task 3.2: Add Source Verification
**Objective:** Prevent fabricated sources.

**Guardrails:**
- Never fabricate sources, URLs, timestamps or quotes
- Only store sources that can be verified
- Primary/first-hand sources preferred
- Source references must remain attached to knowledge

**Step 1:** Implement source validation checks

**Step 2:** Add warnings for unverifiable sources

**Step 3:** Test source traceability flow

---

## Phase 4: Expert Query Mode

### Task 4.1: Implement Expert Query Detection
**Objective:** Detect when user mentions an expert and activate Expert Query Mode.

**Trigger patterns:**
- "What would Alex Hormozi do..."
- "How would Alex Hormozi approach..."
- "What would Naval recommend..."
- "Compare Alex Hormozi with Naval..."
- "Which expert's framework is most relevant..."

**Step 1:** Create query detection logic that scans for expert names

**Step 2:** Map expert names to GBrain profiles

**Step 3:** Activate expert search when trigger detected

### Task 4.2: Search GBrain for Relevant Knowledge
**Objective:** Retrieve expert's relevant knowledge.

**Search logic:**
1. Identify the expert from user query
2. Search GBrain experts/<expert>/ for relevant topics
3. Match user's problem to expert's domains/topics
4. Retrieve principles/frameworks relevant to the problem

**Step 1:** Implement topic matching between user problem and expert knowledge

**Step 2:** Retrieve relevant principles with confidence scores

**Step 3:** Filter by relevance to user's specific situation

### Task 4.3: Apply Principles to User's Situation
**Objective:** Apply expert principles to user's context.

**Application flow:**
1. Understand user's actual situation (product, problem, goals)
2. Map expert principles to user's context
3. Distinguish between:
   - Direct knowledge: something expert explicitly stated
   - Application/inference: Hermes applying expert's principles to user's situation
4. Never present inference as what expert explicitly said

**Step 1:** Extract user's situation from query

**Step 2:** Map expert principles to situation components

**Step 3:** Generate practical recommendations

**Step 4:** Clearly label what's direct knowledge vs. Hermes' application

### Task 4.4: Multi-Expert Comparison
**Objective:** Support comparing multiple experts.

**Flow:**
1. Identify all experts mentioned or relevant
2. Retrieve knowledge from each expert
3. Analyze similarities and differences
4. Synthesize recommendations

**Step 1:** Retrieve Hormozi knowledge
**Step 2:** Retrieve Naval knowledge
**Step 3:** Analyze both approaches
**Step 4:** Identify where they agree/differ
**Step 5:** Provide synthesis based on user's situation

---

## Phase 5: Expert Council & relevance

### Task 5.1: Expert Council Functionality
**Objective:** Allow GBrain to function as an Expert Council.

**Command support:**
- "Which expert's framework should I use for this problem?"
- "Ask the expert council."
- "Research Alex Hormozi's views on pricing."

**Step 1:** Implement expert selection logic based on problem type

**Step 2:** Map problems to relevant experts:
- SaaS pricing → Alex Hormozi
- Startup product-market fit → Paul Graham
- Leverage/scalable businesses → Naval
- Investing/mental models → Charlie Munger

**Step 3:** Retrieve relevant knowledge from selected experts

**Step 4:** Synthesize and provide recommendations

### Task 5.2: Relevance-Based Expert Selection
**Objective:** Select experts based on relevance, not popularity.

**Relevance mapping (examples only):**
- SaaS pricing → Alex Hormozi (offers/monetization expertise)
- Startup product-market fit → Paul Graham (product/customer development)
- Leverage/wealth creation → Naval (specific knowledge, labor leverage)
- Investing/mental models → Charlie Munger (mental models, investing)

**Step 1:** Use actual GBrain knowledge to determine relevance

**Step 2:** Don't retrieve expert just because they're stored

**Step 3:** Match problem to expert's actual stored knowledge areas

---

## Phase 6: Personal Context Integration

### Task 6.1: Integrate User's Situation
**Objective:** Combine expert knowledge with user's context.

**Integration formula:**
```
Expert Knowledge + My Situation + My Goals + Relevant Project Context = Practical Recommendation
```

**Step 1:** Extract user's situation from query

**Step 2:** Retrieve relevant expert knowledge from GBrain

**Step 3:** Consider user's goals and project context

**Step 4:** Generate tailored recommendation

**Step 5:** Do not give generic advice - must be specific to user's situation

### Task 6.2: Example Integration
**Example:** "What would Alex Hormozi recommend I do with My Trading Compass?"

**Steps:**
1. Retrieve Alex Hormozi's business principles from GBrain
2. Extract existing information about My Trading Compass
3. Identify current problem user is facing
4. Apply Hormozi's principles specifically to trading/compass product
5. Give concrete next actions specific to the product

---

## Phase 7: Commands & UX

### Task 7.1: Implement Natural Language Commands
**Objective:** Support commands like:
- "Add this to Alex Hormozi's knowledge."
- "Research Alex Hormozi's views on pricing."
- "What would Alex Hormozi do?"
- "Ask the expert council."
- "Compare Hormozi and Naval on this."
- "What does my expert knowledge say about this?"
- "Which expert has the strongest framework for this problem?"
- "Update Alex Hormozi's profile with this source."

**Step 1:** Map each command to GBrain operations

**Step 2:** Implement command parsing

**Step 3:** Test each command works

### Task 7.2: Design User Experience
**Objective:** Ensure Hermes never fabricates expert opinions.

**Guardrails enforcement:**
- Never say "I am Alex Hormozi and I would..."
- Always say "Based on Alex Hormozi's documented principles..."
- Or "Applying the principles in Alex Hormozi's teachings..."
- Never invent opinions, quotes, experiences or beliefs
- Clearly distinguish source-backed knowledge from Hermes' inference
- Assign confidence levels (High/Medium/Low)
- When confidence low, communicate uncertainty

**Step 1:** Implement output formatting that distinguishes knowledge types

**Step 2:** Add confidence indicators

**Step 3:** Test all UX flow

---

## Phase 8: Continuous Learning

### Task 8.1: Implement Knowledge Improvement Pipeline
**Objective:** Make the knowledge base improve over time.

**Continuous learning cycle:**
```
New Source → Extract Knowledge → Compare Against Existing GBrain Knowledge → Deduplicate → Update Existing Knowledge → Add New Knowledge → Attach Source
```

**Step 1:** When new content processed, search existing GBrain for similar knowledge

**Step 2:** If similar exists: update, add source, increase confidence

**Step 3:** If new principle: add as new entry with source

**Step 4:** Run periodically or on new content ingestion

### Task 8.2: Test Improvement Over Time
**Objective:** Verify knowledge base grows in usefulness.

**Step 1:** Add new expert source

**Step 2:** Verify deduplication works

**Step 3:** Verify confidence increases with multiple sources

**Step 4:** Test that old knowledge isn't lost

---

## Verification Checklist

- [ ] GBrain gbrain.yml updated with experts/ category
- [ ] Expert profile directories created (alex-hormozi, naval, etc.)
- [ ] Knowledge item schema designed and testable
- [ ] Knowledge extraction pipeline functional
- [ ] Deduplication logic working (no duplicate principles)
- [ ] Source metadata stored for all knowledge items
- [ ] Expert query mode triggered by expert name mentions
- [ ] Principles applied to user's situation (not impersonation)
- [ ] Multi-expert comparison working
- [ ] Relevance-based expert selection (not popularity)
- [ ] Personal context integration working
- [ ] Natural language commands functional
- [ ] Confidence levels assigned and communicated
- [ ] Continuous learning pipeline operational
- [ ] No fabricated sources, quotes, or opinions
- [ ] Clear distinction between direct knowledge and Hermes' inference

---