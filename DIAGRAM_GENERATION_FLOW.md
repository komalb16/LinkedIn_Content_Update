# Trending Topic → Diagram: Visual Process Flow

## Complete Workflow

```
┌─────────────────────────────────────────────────────────────────────┐
│  TRENDING TOPIC DETECTION                                           │
│  (HackerNews / Reddit API)                                          │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Input: Topic Title + ID + Source                                   │
│  Example:                                                            │
│  - title: "Claude 3.5 Sonnet Context Extended to 200K"             │
│  - id: "trending-claude-context-200k-a1b2c3"                       │
│  - source: "HackerNews"                                             │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
    ┌───────────────────┐   ┌──────────────────────┐
    │ DEDUPLICATION     │   │ LLM POST GENERATION  │
    ├───────────────────┤   │ (OpenAI)             │
    │ Check cache:      │   │ 8-10 seconds         │
    │ Posted before?    │   │ Generates content    │
    │ YES → SKIP        │   │ + structure          │
    │ NO → CONTINUE ✓   │   └──────────┬───────────┘
    └──────────────────────────────────┘
                           │
                           ▼
    ┌──────────────────────────────────────────────────────────────┐
    │  STEP 1: EXTRACT KEYWORDS FROM TOPIC                        │
    ├──────────────────────────────────────────────────────────────┤
    │  From title: "Claude 3.5 Sonnet Context Extended to 200K"   │
    │  Keywords extracted: [claude, sonnet, context, extended]    │
    └────────────────┬───────────────────────────────────────────┘
                     │
    ┌────────────────┴────────────────┐
    ▼                                 ▼
    ┌──────────────────────────┐     ┌──────────────────────────┐
    │ STEP 2A: CATEGORY DETECT │     │ STEP 2B: STYLE ASSIGN   │
    ├──────────────────────────┤     ├──────────────────────────┤
    │ Check keywords against:  │     │ MD5 hash:               │
    │ - AI: LLM, RAG, Claude   │     │ MD5("id|title") →      │
    │ - Cloud: Docker, K8s     │     │ 0xf7a3e2c... % 23      │
    │ - Security: Zero Trust   │     │ = 6 (ORBIT STYLE) ✓    │
    │ - Career: Skills, Job    │     │                        │
    │                          │     │ DETERMINISTIC:         │
    │ MATCHED: AI ✓            │     │ Same topic = Style #6  │
    │ PALETTE:                 │     │ Different topics =     │
    │ [#7C3AED, #2563EB, ...]  │     │ Different styles ✓     │
    └──────────────┬───────────┘     └─────────────┬──────────┘
                   │                              │
                   └──────────────┬───────────────┘
                                  ▼
    ┌──────────────────────────────────────────────────────────────┐
    │  STEP 3: VALIDATE STYLE                                      │
    ├──────────────────────────────────────────────────────────────┤
    │  Is style #6 in DISABLED_STYLES? NO ✓                        │
    │  Is style function available? YES ✓                          │
    │  Proceed to generation ✓                                     │
    └────────────────┬───────────────────────────────────────────┘
                     │
    ┌────────────────┴────────────────┐
    ▼                                 ▼
    ┌──────────────────────────┐     ┌──────────────────────────┐
    │ STEP 4A: PREPARE DATA    │     │ STEP 4B: LOAD FUNCTION  │
    ├──────────────────────────┤     ├──────────────────────────┤
    │ Colors: AI palette       │     │ STYLES[6] =             │
    │ Title: "Claude 3.5..."   │     │ _style_orbit()          │
    │ ID: "trending-claude..." │     │                        │
    │ Structure: {            │     │ Function ready ✓        │
    │   sections: [...]       │     │                        │
    │ }                       │     │                        │
    └──────────────┬───────────┘     └─────────────┬──────────┘
                   │                              │
                   └──────────────┬───────────────┘
                                  ▼
    ┌──────────────────────────────────────────────────────────────┐
    │  STEP 5: GENERATE SVG DIAGRAM                                │
    ├──────────────────────────────────────────────────────────────┤
    │  _style_orbit(                                               │
    │    topic_id = "trending-claude-context-200k-a1b2c3"         │
    │    topic_name = "Claude 3.5 Sonnet Context Extended..."     │
    │    C = ["#7C3AED", "#2563EB", #059669", ...]               │
    │    structure = {sections: [...]}                           │
    │  )                                                          │
    │                                                            │
    │  PROCESS:                                                  │
    │  1. Create SVG canvas (1200x840)                           │
    │  2. Draw central "Claude 3.5" circle (color #1)           │
    │  3. Draw 3 satellite bubbles (colors #2-4)                │
    │  4. Add section labels from structure                     │
    │  5. Add animations (SVG + CSS)                            │
    │  6. Add header, footer, copyright                         │
    │  7. Return complete SVG string ✓                          │
    └────────────────┬───────────────────────────────────────────┘
                     │
                     ▼
    ┌──────────────────────────────────────────────────────────────┐
    │  STEP 6: VALIDATE SVG                                        │
    ├──────────────────────────────────────────────────────────────┤
    │  Success? YES ✓                                              │
    │  Size OK? YES (7-12 KB) ✓                                    │
    │  Valid XML? YES ✓                                            │
    │  Ready to use ✓                                              │
    └────────────────┬───────────────────────────────────────────┘
                     │
    ┌────────────────┴────────────────┐
    ▼                                 ▼
    ┌──────────────────────────┐     ┌──────────────────────────┐
    │ STEP 7A: SAVE TO CACHE   │     │ STEP 7B: CREATE VARIANTS │
    ├──────────────────────────┤     ├──────────────────────────┤
    │ Update cache file:       │     │ Variant 1: Original     │
    │ .trending_topics_cache   │     │ (colors: AI palette)    │
    │ .json:                   │     │                        │
    │ {                       │     │ Variant 2: Muted       │
    │   id: "trending-..."    │     │ (colors: -20% sat)     │
    │   title: "Claude 3.5.." │     │                        │
    │   style: 6              │     │ Variant 3: High Contrast│
    │   category: "AI"        │     │ (colors: +20% sat)     │
    │   posted_at: <now>      │     │                        │
    │   diagram_hash: "abc.." │     │ A/B Testing Ready ✓    │
    │ }                       │     │                        │
    │                        │     │                        │
    │ Prevents duplicate ✓    │     │                        │
    └─────────┬──────────────┘     └─────────────┬──────────┘
              │                                 │
              └──────────────┬──────────────────┘
                             ▼
    ┌──────────────────────────────────────────────────────────────┐
    │  STEP 8: POST TO LINKEDIN                                    │
    ├──────────────────────────────────────────────────────────────┤
    │  With LLM-generated post content:                            │
    │                                                              │
    │  "📌 Claude 3.5 Sonnet - 200K Context                        │
    │                                                              │
    │  Just tried the new 200K context window... [content]        │
    │                                                              │
    │  [DIAGRAM EMBEDDED: Orbit style, AI colors] ✓               │
    │                                                              │
    │  3 A/B variants ready for testing ✓                          │
    │                                                              │
    │  #Claude #AI #LLM"                                          │
    └────────────────┬───────────────────────────────────────────┘
                     │
                     ▼
    ┌──────────────────────────────────────────────────────────────┐
    │  ✅ DONE!                                                     │
    ├──────────────────────────────────────────────────────────────┤
    │  Trending topic fully processed:                             │
    │  ✓ Deduplication checked                                     │
    │  ✓ Category auto-detected                                    │
    │  ✓ Style deterministically assigned                          │
    │  ✓ SVG diagram generated locally                             │
    │  ✓ 3 A/B variants created                                    │
    │  ✓ Posted to LinkedIn with engagement tracking              │
    │  ✓ Cached to prevent duplicates                              │
    │                                                              │
    │  TOTAL TIME: ~14 seconds                                     │
    │  COST: ~$0.015                                               │
    │  INTERNET NEEDED: Only for APIs (not diagrams)               │
    └──────────────────────────────────────────────────────────────┘
```

---

## Decision Tree: How System Analyzes Topic

```
┌─ New Trending Topic Arrives ─┐
│ "Claude 3.5 Sonnet Context"  │
└──────────────┬───────────────┘
               │
        ┌──────┴──────┐
        ▼             ▼
    ┌─────────────────────────────────────────┐
    │  STEP 1: KEYWORD EXTRACTION             │
    │  Split title into tokens:               │
    │  [claude, 3, 5, sonnet, context, etc]  │
    └──────────────┬──────────────────────────┘
                   │
        ┌──────────┴──────────┐
        ▼                     ▼
    ┌──────────────┐    ┌──────────────────────┐
    │ STEP 2A:     │    │ STEP 2B:             │
    │ CATEGORIZE   │    │ EXTRACT DESCRIPTIVE  │
    │              │    │ FEATURES             │
    │ Check against│    │                      │
    │ keyword sets:│    │ From title:          │
    │              │    │ - Main topic         │
    │ AI_KEYWORDS: │    │ - Technical terms    │
    │ llm, rag,    │    │ - Version/release    │
    │ claude,      │    │ - Performance metric │
    │ agent,       │    │ - Capability add     │
    │ genai, etc   │    │                      │
    │              │    │ Result: Structured   │
    │ MATCHED: ✓   │    │ data for diagram     │
    │ Category: AI │    │ generation           │
    └──────┬───────┘    └──────────┬───────────┘
           │                       │
           └───────────┬───────────┘
                       ▼
    ┌──────────────────────────────────────────┐
    │ STEP 3: SELECT COLOR PALETTE             │
    │                                          │
    │ AI Category Matched ✓                    │
    │ Apply Palette:                           │
    │  #7C3AED (Purple)                       │
    │  #2563EB (Blue)                         │
    │  #059669 (Green)                        │
    │  #D97706 (Orange)                       │
    │  #DB2777 (Pink)                         │
    │  #0891B2 (Cyan)                         │
    └──────────────┬───────────────────────────┘
                   │
    ┌──────────────┴──────────────┐
    ▼                             ▼
    ┌────────────────────┐   ┌──────────────────────┐
    │ STEP 4A:           │   │ STEP 4B:             │
    │ HASH-BASED         │   │ STYLE VARIATION      │
    │ STYLE SELECTION    │   │                      │
    │                    │   │ Base style + random  │
    │ MD5 hash of        │   │ variation from       │
    │ topic_id|topic_name│   │ nearby styles        │
    │                    │   │                      │
    │ f7a3e2c...        │   │ 70% chance: use base │
    │ % 23 = 6           │   │ 30% chance: use      │
    │                    │   │ adjacent style       │
    │ Result: Style #6   │   │                      │
    │ (ORBIT) ✓          │   │ Final: Style #6 ✓    │
    └────────────┬───────┘   └──────────┬──────────┘
                 │                      │
                 └──────────┬───────────┘
                            ▼
    ┌──────────────────────────────────────────────┐
    │ STEP 5: EXECUTE DIAGRAM GENERATION           │
    │                                              │
    │ Call: STYLES[6](                             │
    │   topic_id: "trending-claude-context-200k",  │
    │   topic_name: "Claude 3.5 Sonnet...",       │
    │   colors: [#7C3AED, #2563EB, ...],          │
    │   structure: {subtitle, sections}            │
    │ )                                            │
    │                                              │
    │ Execute _style_orbit() function:             │
    │ 1. Create SVG container                      │
    │ 2. Draw central circle (color[0])           │
    │ 3. Draw 3 satellite circles (colors[1-3])   │
    │ 4. Add text labels                           │
    │ 5. Add connecting lines                      │
    │ 6. Add animations                            │
    │ 7. Add footer + copyright                    │
    │ 8. Return complete SVG                       │
    │                                              │
    │ Result: Valid SVG ✓                          │
    └────────────────┬─────────────────────────────┘
                     │
                     ▼
    ┌──────────────────────────────────────────────┐
    │ STEP 6: FALLBACK STRATEGY                    │
    │                                              │
    │ If any error occurs:                         │
    │ - Function crashed? Use Card Grid (#7)       │
    │ - Invalid SVG? Return backup                 │
    │ - Missing data? Use defaults                 │
    │                                              │
    │ Result: Always return valid diagram ✓        │
    └────────────────┬─────────────────────────────┘
                     │
                     ▼
    ┌──────────────────────────────────────────────┐
    │ STEP 7: A/B VARIANT GENERATION               │
    │                                              │
    │ Variant #1 (Control):                        │
    │   Use original colors as-is                  │
    │                                              │
    │ Variant #2 (Muted):                          │
    │   Reduce saturation -20%                     │
    │   Increase brightness +10%                   │
    │                                              │
    │ Variant #3 (High Contrast):                  │
    │   Increase saturation +20%                   │
    │   Decrease brightness -10%                   │
    │                                              │
    │ All 3 ready to test ✓                        │
    └────────────────┬─────────────────────────────┘
                     │
                     ▼
    ┌──────────────────────────────────────────────┐
    │ ✅ SUCCESS!                                  │
    │                                              │
    │ Trending topic fully processed:              │
    │ • Categorized: AI ✓                          │
    │ • Palette selected: AI colors ✓              │
    │ • Style assigned: Orbit (#6) ✓               │
    │ • Diagram generated: SVG ✓                   │
    │ • Variants created: 3x ✓                     │
    │ • Ready to post: YES ✓                       │
    └──────────────────────────────────────────────┘
```

---

## Performance Timeline

```
Timeline for single trending topic → diagram → post:

0ms    ├─ Trending topic detected
       │
2ms    ├─ Deduplication check (.trending_topics_cache.json)
       │  └─ Not posted before ✓
       │
4ms    ├─ Keyword extraction
       │  └─ Extract from title
       │
6ms    ├─ Category detection
       │  └─ Match against 50+ keywords
       │
8ms    ├─ Palette selection
       │  └─ Lookup category → colors
       │
10ms   ├─ MD5 hash calculation
       │  └─ topic_id | topic_name
       │
12ms   ├─ Style index computation
       │  └─ hash % 23 = 6 (ORBIT)
       │
14ms   ├─ Validate style exists
       │  └─ Yes, STYLES[6] available
       │
+8000ms├─ LLM post generation (PARALLEL, not in critical path)
       │
300ms  ├─ SVG diagram generation
       │  └─ _style_orbit() execution
       │
400ms  ├─ SVG validation
       │  └─ Check XML, size, structure
       │
450ms  ├─ Create A/B variants (3x)
       │  └─ Color modifications
       │
500ms  ├─ Update cache
       │  └─ Save to .trending_topics_cache.json
       │
+2000ms├─ Post to LinkedIn
       │
────────────────────────────────────────
Total: ~14 seconds (LLM generation is sequential, not in diagram path)
Diagram-only: ~500ms ✓ FAST!
```

---

## Data Flow: No Internet for Diagrams

```
┌─────────────────────────────────────────────────────────────┐
│  INTERNET ACCESS NEEDED (APIs)                              │
├─────────────────────────────────────────────────────────────┤
│  ✓ HackerNews API  ─→ Fetch trending topics                │
│  ✓ Reddit API      ─→ Fetch trending topics                │
│  ✓ OpenAI API      ─→ Generate post content & structure    │
│  ✓ LinkedIn API    ─→ Post to LinkedIn                     │
└──────────────────────────────────┬──────────────────────────┘
                                   │
                    ┌──────────────┐
                    ▼              ▼
        ┌──────────────────┐  ┌──────────────────────────┐
        │ Trending Topic   │  │ Post Content + Structure │
        │ + Title + URL    │  │ + LLM Analysis          │
        └────────┬─────────┘  └──────────┬───────────────┘
                 │                       │
                 └───────────┬───────────┘
                             ▼
    ┌────────────────────────────────────────────────────────┐
    │  PURE PYTHON (NO INTERNET NEEDED) ✓                   │
    ├────────────────────────────────────────────────────────┤
    │                                                        │
    │  diagram_generator.py:make_diagram()                   │
    │  ├─ Input: topic_name, topic_id, structure           │
    │  ├─ Process:                                           │
    │  │  1. get_pal() → keyword matching → colors          │
    │  │  2. MD5 hash → style index                         │
    │  │  3. STYLES[idx]() → generate SVG                   │
    │  │  4. Return SVG string                              │
    │  └─ Output: Complete SVG (no downloads needed)        │
    │                                                        │
    │  All colors, shapes, animations = hardcoded in code   │
    │  No external image downloads                          │
    │  No API calls to diagram services                     │
    │                                                        │
    └────────────────────────┬───────────────────────────────┘
                             │
                    ┌────────┴────────┐
                    ▼                 ▼
        ┌──────────────────┐  ┌──────────────────────────┐
        │ Generated SVG    │  │ 3 A/B Variants          │
        │ (local storage)  │  │ (local storage)          │
        └──────────┬───────┘  └──────────┬───────────────┘
                   │                      │
                   └──────────┬───────────┘
                              ▼
        ┌────────────────────────────────────────────────┐
        │  Ready for LinkedIn Post                       │
        │  ✓ Diagram generated (local)                   │
        │  ✓ Content ready (from LLM)                    │
        │  ✓ A/B variants ready (from local)            │
        │  └─ Now post to LinkedIn (API)                 │
        └────────────────────────────────────────────────┘
```

---

## Comparison: Scheduled vs Trending Topics

```
┌──────────────────────┬──────────────────┬──────────────────┐
│ Aspect               │ Scheduled Topics │ Trending Topics  │
├──────────────────────┼──────────────────┼──────────────────┤
│ Topic Source         │ topics_config.json│ HackerNews/Reddit│
│ Style Allocation     │ Pre-defined       │ Auto-hash        │
│ Colors Selection     │ Hardcoded per   │ Keyword-based    │
│                      │ topic            │ detection        │
│ Diagram Generation   │ Same code        │ Same code ✓      │
│ Pre-allocated Styles │ NOT needed       │ NOT needed ✓     │
│ Internet Diagrams    │ NO               │ NO ✓             │
│ Time to post         │ 15 sec           │ ~14 sec          │
│ Cost per post        │ $0.015           │ $0.015           │
│ Failure risk         │ Low              │ Low ✓            │
│ A/B Testing          │ Yes              │ Yes ✓            │
│ Deduplication        │ topics_config    │ cache file ✓     │
└──────────────────────┴──────────────────┴──────────────────┘
```

---

## Key Takeaways ✅

1. **No pre-allocation needed** - Any trending topic auto-gets a style hash 0-22
2. **No internet diagrams** - Everything generated in Python locally
3. **Deterministic but diverse** - Same topic always gets same style, different topics look different
4. **Color auto-detection** - Keywords → category → palette (AI, Cloud, Security, Career)
5. **Automatic fallback** - If style fails, uses Card Grid (always works)
6. **Same pipeline** - Trending topics use exact same diagram_generator.py as scheduled topics
7. **Fast** - Diagram generation only ~300ms, negligible overhead
8. **Zero cost** - No paid APIs for diagram generation

**Result**: ✅ Trending topics integrate seamlessly, automatically get beautiful unique diagrams, powered by deterministic hashing + local SVG generation.

