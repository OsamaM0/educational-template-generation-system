# 📊 OpenAI API Call Flow Visualization

## 🔄 Processing Flow Per Document

```
┌─────────────────────────────────────────────────────────────┐
│                    DOCUMENT PROCESSING                       │
│                   (Per Single Document)                      │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
        ┌──────────────────────────────────────┐
        │  1. CONTENT ANALYSIS (REQUIRED)      │  ◄── 1 API call
        │  └─ Detect: language, subject,       │      ⭐⭐⭐⭐
        │     math content, complexity          │
        └──────────────────────────────────────┘
                            │
                            ▼
        ┌──────────────────────────────────────┐
        │  2. LEARNING GOALS GENERATION        │  ◄── 0-1 API call
        │  └─ If no goals in DB, generate      │      ⭐⭐⭐
        │     3-7 goals from content            │      (only if needed)
        └──────────────────────────────────────┘
                            │
                ┌───────────┴───────────┐
                │                       │
                ▼                       ▼
    ┌─────────────────────┐   ┌─────────────────────┐
    │  3. SUMMARY         │   │  4. WORKSHEET       │
    │  └─ Generate        │   │  └─ Goals, vocab,   │
    │     opening,        │   │     applications,   │  ◄── 1 API call each
    │     summary,        │   │     guidelines      │      ⭐⭐ / ⭐⭐⭐
    │     ending          │   │                     │
    └─────────────────────┘   └─────────────────────┘
                │                       │
                └───────────┬───────────┘
                            │
                            ▼
        ┌──────────────────────────────────────┐
        │  5. QUESTIONS (GOAL-BASED MODE)      │
        │                                       │
        │  ┌─────────────────────────────────┐ │
        │  │ For Goal 1: "Understanding..."  │ │  ◄── API call #1
        │  └─────────────────────────────────┘ │      ⭐⭐⭐⭐
        │  ┌─────────────────────────────────┐ │
        │  │ For Goal 2: "Application..."    │ │  ◄── API call #2
        │  └─────────────────────────────────┘ │      ⭐⭐⭐⭐
        │  ┌─────────────────────────────────┐ │
        │  │ For Goal 3: "Analysis..."       │ │  ◄── API call #3
        │  └─────────────────────────────────┘ │      ⭐⭐⭐⭐
        │  ┌─────────────────────────────────┐ │
        │  │ For Goal 4: "Evaluation..."     │ │  ◄── API call #4
        │  └─────────────────────────────────┘ │      ⭐⭐⭐⭐
        │  ┌─────────────────────────────────┐ │
        │  │ For Goal 5: "Creation..."       │ │  ◄── API call #5
        │  └─────────────────────────────────┘ │      ⭐⭐⭐⭐
        │                                       │
        │  Total: 1-7 API calls (1 per goal)   │
        └──────────────────────────────────────┘
                            │
                            ▼
        ┌──────────────────────────────────────┐
        │  6. MIND MAP (MULTI-PASS MODE)       │
        │                                       │
        │  ┌─────────────────────────────────┐ │
        │  │ Planning Phase (if enhanced)    │ │  ◄── API call #1 (optional)
        │  └─────────────────────────────────┘ │      ⭐⭐⭐
        │  ┌─────────────────────────────────┐ │
        │  │ Chunk 1 (chars 0-1800)          │ │  ◄── API call #2
        │  │ └─ Planning + Generation        │ │      ⭐⭐⭐⭐⭐
        │  └─────────────────────────────────┘ │
        │  ┌─────────────────────────────────┐ │
        │  │ Chunk 2 (chars 1550-3350)       │ │  ◄── API call #3
        │  │ └─ Planning + Generation        │ │      ⭐⭐⭐⭐⭐
        │  └─────────────────────────────────┘ │
        │  ┌─────────────────────────────────┐ │
        │  │ Chunk 3 (chars 3100-5000)       │ │  ◄── API call #4
        │  │ └─ Planning + Generation        │ │      ⭐⭐⭐⭐⭐
        │  └─────────────────────────────────┘ │
        │                                       │
        │  Total: 3-10 API calls (chunked)     │
        └──────────────────────────────────────┘
                            │
                            ▼
        ┌──────────────────────────────────────┐
        │      TOTAL PER DOCUMENT:              │
        │                                       │
        │  Current Config: 12-15 API calls      │
        │  Optimized Config: 6-8 API calls      │
        │                                       │
        │  Savings: 40-60%                      │
        └──────────────────────────────────────┘
```

---

## 🔥 Hot Spots (Highest API Usage)

### 🥇 Mind Map (Multi-Pass) - 3-10 calls
```
Document: "Long educational content about photosynthesis..." (5000 chars)
          │
          ├─► Chunk 1 (0-1800): Planning + Generation = 2 calls
          ├─► Chunk 2 (1550-3350): Planning + Generation = 2 calls
          └─► Chunk 3 (3100-5000): Planning + Generation = 2 calls
          
Total: 6 API calls just for mind map!
Cost: ⭐⭐⭐⭐⭐⭐⭐⭐
```

### 🥈 Questions (Goal-Based) - 1-7 calls
```
Goals: ["Understanding concepts", "Application", "Analysis", "Evaluation", "Creation"]
       │
       ├─► Goal 1: Generate questions = 1 call
       ├─► Goal 2: Generate questions = 1 call
       ├─► Goal 3: Generate questions = 1 call
       ├─► Goal 4: Generate questions = 1 call
       └─► Goal 5: Generate questions = 1 call

Total: 5 API calls for questions!
Cost: ⭐⭐⭐⭐⭐
```

---

## 💡 Optimization Comparison

### BEFORE (Current):
```
Document → [Analysis] → [Goals] → [Summary] → [Worksheet] → [Questions×5] → [MindMap×6]
           1 call      1 call    1 call      1 call        5 calls        6 calls
           
           Total: 15 API calls
           Cost per document: ~$0.15-0.30
           100 documents: ~$15-30
```

### AFTER (Optimized):
```
Document → [Analysis] → [Goals] → [Summary] → [Worksheet] → [Questions×3] → [MindMap×1]
           1 call      1 call    1 call      1 call        3 calls        1 call
           
           Total: 8 API calls
           Cost per document: ~$0.08-0.12
           100 documents: ~$8-12
           
           💰 SAVINGS: 47% (7 fewer calls per document)
```

---

## 🎯 Bulk Processing (100 Documents)

### Current Configuration
```
┌────────────────────────────────────────────────┐
│             BULK PROCESSING                    │
│            (100 Documents)                     │
└────────────────────────────────────────────────┘
                    │
    ┌───────────────┴───────────────┐
    │                               │
    ▼                               ▼
Document #1              ...    Document #100
├─ Analysis (1)                 ├─ Analysis (1)
├─ Goals (1)                    ├─ Goals (1)
├─ Summary (1)                  ├─ Summary (1)
├─ Worksheet (1)                ├─ Worksheet (1)
├─ Questions (5)                ├─ Questions (5)
└─ MindMap (6)                  └─ MindMap (6)
   ───────────                     ───────────
   Total: 15 calls                 Total: 15 calls

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GRAND TOTAL: 1,500 API calls
ESTIMATED COST: $20-30
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Optimized Configuration
```
┌────────────────────────────────────────────────┐
│        OPTIMIZED BULK PROCESSING               │
│            (100 Documents)                     │
└────────────────────────────────────────────────┘
                    │
    ┌───────────────┴───────────────┐
    │                               │
    ▼                               ▼
Document #1              ...    Document #100
├─ Analysis (1)                 ├─ Analysis (1)
├─ Goals (1)                    ├─ Goals (1)
├─ Summary (1)                  ├─ Summary (1)
├─ Worksheet (1)                ├─ Worksheet (1)
├─ Questions (3)                ├─ Questions (3)
└─ MindMap (1)                  └─ MindMap (1)
   ───────────                     ───────────
   Total: 8 calls                  Total: 8 calls

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GRAND TOTAL: 800 API calls
ESTIMATED COST: $8-12
SAVINGS: ~$12-18 (53%)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 🔍 Detailed Call Breakdown

### Template: Mind Map (Multi-Pass + Enhanced Thinking)
```
                    INPUT: 5000 character document
                            │
                            ▼
                    ┌──────────────┐
                    │ Check Length │
                    └──────────────┘
                            │
                ┌───────────┴───────────┐
                │ > 1800 chars?         │
                └───────────────────────┘
                      │YES        │NO
                      ▼           ▼
          ┌────────────────┐   Single Pass
          │  Multi-Pass    │   (1 call)
          └────────────────┘
                │
                ├─► Split into chunks
                │   Chunk 1: 0-1800
                │   Chunk 2: 1550-3350
                │   Chunk 3: 3100-5000
                │
                └─► Process Each Chunk:
                    ┌────────────────────────┐
                    │ Enhanced Thinking ON?  │
                    └────────────────────────┘
                         │YES        │NO
                         ▼           ▼
                    ┌─────────┐   ┌─────────┐
                    │Planning │   │Generate │
                    │API call │   │API call │
                    └─────────┘   └─────────┘
                         │           │
                         └─────┬─────┘
                               ▼
                          ┌─────────┐
                          │Generate │
                          │API call │
                          └─────────┘

    Total Calls: 
    - Single-pass: 1 call
    - Single-pass + planning: 2 calls
    - Multi-pass (3 chunks): 3 calls
    - Multi-pass + planning: 6 calls (2 per chunk)
```

### Template: Questions (Goal-Based)
```
                    INPUT: Content + 5 Goals
                            │
                            ▼
                    ┌──────────────┐
                    │ Goal-Based?  │
                    └──────────────┘
                      │YES        │NO
                      ▼           ▼
          ┌────────────────┐   Standard Mode
          │  Per-Goal      │   (1 call total)
          │  Generation    │
          └────────────────┘
                │
                └─► For Each Goal:
                    ┌─────────────────────┐
                    │ Goal 1: Understand  │──► API call #1
                    └─────────────────────┘
                    ┌─────────────────────┐
                    │ Goal 2: Apply       │──► API call #2
                    └─────────────────────┘
                    ┌─────────────────────┐
                    │ Goal 3: Analyze     │──► API call #3
                    └─────────────────────┘
                    ┌─────────────────────┐
                    │ Goal 4: Evaluate    │──► API call #4
                    └─────────────────────┘
                    ┌─────────────────────┐
                    │ Goal 5: Create      │──► API call #5
                    └─────────────────────┘

    Total Calls: 
    - Standard mode: 1 call
    - Goal-based (5 goals): 5 calls
    - Savings with 3 goals: 3 calls (40% reduction)
```

---

## 📊 Cost Matrix (Per Document)

### Feature Combinations Cost Table

| Mind Map | Questions | Total Calls | Relative Cost |
|----------|-----------|-------------|---------------|
| Single-pass | Standard (1) | 6 | $0.06-0.12 ⭐⭐ |
| Single-pass | Goal-based (3) | 8 | $0.08-0.16 ⭐⭐⭐ |
| Single-pass | Goal-based (5) | 10 | $0.10-0.20 ⭐⭐⭐⭐ |
| Multi-pass | Standard (1) | 8 | $0.08-0.16 ⭐⭐⭐ |
| Multi-pass | Goal-based (3) | 10 | $0.10-0.20 ⭐⭐⭐⭐ |
| Multi-pass | Goal-based (5) | 12 | $0.12-0.24 ⭐⭐⭐⭐⭐ |
| Multi-pass + Enhanced | Goal-based (5) | 15 | $0.15-0.30 ⭐⭐⭐⭐⭐⭐ |

*(Assumes: Analysis=1, Goals=1, Summary=1, Worksheet=1)*

---

## 🎯 Token Usage Estimation

### Input Tokens (per call):
```
Analysis:      ~1000-2000 tokens (full content)
Goals:         ~800-1500 tokens
Summary:       ~1000-2000 tokens
Worksheet:     ~1500-2500 tokens
Questions:     ~1500-3000 tokens (per goal)
Mind Map:      ~1000-2000 tokens (per chunk)
```

### Output Tokens (per call):
```
Analysis:      ~200-400 tokens (JSON)
Goals:         ~100-200 tokens
Summary:       ~300-500 tokens
Worksheet:     ~400-800 tokens
Questions:     ~500-1000 tokens (per goal)
Mind Map:      ~800-1500 tokens (per chunk, JSON)
```

### Total per Document (15 calls):
```
Input:  ~20,000-30,000 tokens
Output: ~6,000-10,000 tokens
Total:  ~26,000-40,000 tokens

At $0.001/1K tokens = $0.026-0.040 per document
For 100 docs = $2.60-4.00 (input only)

Plus output tokens = Total $5-10 per 100 docs (minimum)
With GPT-5 for math = $20-30 per 100 docs (maximum)
```

---

## 🔧 Quick Toggle Reference

### Environment Variables Impact:
```
┌─────────────────────────────────────────────────────────┐
│                   COST CONTROL PANEL                    │
└─────────────────────────────────────────────────────────┘

MINDMAP_MULTI_PASS
├─ true:  3-10 calls per doc  ⭐⭐⭐⭐⭐
└─ false: 1 call per doc      ⭐⭐      (-60% cost)

MINDMAP_ENHANCED_THINKING
├─ true:  2× calls            ⭐⭐⭐⭐
└─ false: 1× calls            ⭐⭐      (-50% cost)

MINDMAP_CHUNK_SIZE_CHARS
├─ 1800:  More chunks         ⭐⭐⭐⭐⭐
└─ 5000:  Fewer chunks        ⭐⭐⭐    (-30% cost)

Goal Count
├─ 7:     7 calls             ⭐⭐⭐⭐⭐⭐
├─ 5:     5 calls             ⭐⭐⭐⭐⭐
└─ 3:     3 calls             ⭐⭐⭐    (-40% cost)

Question Counts
├─ Full:  More output tokens  ⭐⭐⭐⭐
└─ Half:  Fewer tokens        ⭐⭐      (-30% cost)
```

---

## 🚨 Warning Signs You're Spending Too Much

1. **Processing 100 docs costs > $20**
   - Solution: Disable `MINDMAP_MULTI_PASS` and `MINDMAP_ENHANCED_THINKING`

2. **Single document takes > 20 API calls**
   - Solution: Reduce goal count to 3, use single-pass mind maps

3. **Mind map generation takes > 30 seconds**
   - Solution: Increase `MINDMAP_CHUNK_SIZE_CHARS` or disable multi-pass

4. **Token usage > 40K per document**
   - Solution: Reduce question counts, skip mind maps for some docs

---

## ✅ Best Practices Summary

```
┌────────────────────────────────────────────────────────┐
│              COST OPTIMIZATION CHECKLIST               │
├────────────────────────────────────────────────────────┤
│ ✓ Set MINDMAP_MULTI_PASS=false for docs < 3000 chars  │
│ ✓ Set MINDMAP_ENHANCED_THINKING=false (save 50%)      │
│ ✓ Limit goals to 3-4 per document                     │
│ ✓ Use --skip-existing in bulk processing              │
│ ✓ Reduce question counts by 30-40%                    │
│ ✓ Monitor API usage with logging                      │
│ ✓ Use cheaper model (gpt-4o-mini) for non-math        │
│ ✓ Cache content analysis results                      │
│ ✓ Process in batches with selective templates         │
│ ✓ Test with 10 docs before scaling to 100+            │
└────────────────────────────────────────────────────────┘
```

---

**Pro Tip:** Start with the minimal configuration, then gradually add features based on quality requirements and budget!

---

**Last Updated:** October 21, 2025
