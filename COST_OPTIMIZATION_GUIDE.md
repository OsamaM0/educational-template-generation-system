# 💰 Quick Cost Optimization Guide

## 🎯 TL;DR - Reduce Costs by 50% in 5 Minutes

### The Problem
Your system makes **12-15 API calls per document**. For 100 documents = **1,300+ calls** = **$15-30**.

### The Solution
Apply these changes to reduce to **6-8 calls per document** = **$6-12** (50-60% savings).

---

## ⚡ 5-Minute Fix

### Step 1: Edit `.env` file (or environment variables)

```bash
# Add these lines or update existing ones:
MINDMAP_ENHANCED_THINKING=false
MINDMAP_MULTI_PASS=false
MINDMAP_CHUNK_SIZE_CHARS=5000
```

### Step 2: Run bulk generator with selective templates

```bash
# Skip mind maps for non-critical content
python bulk_generator.py --templates questions worksheets summaries --max-docs 100

# Or if you need mind maps, at least it won't use multi-pass
python bulk_generator.py --templates questions worksheets summaries mindmaps --max-docs 100
```

### Step 3 (Optional): Reduce question counts

Edit `processors/batch_processor.py` around line 200:

```python
# BEFORE (current):
questions_result = self.template_generator.generate_goal_based_questions(
    content=content,
    goals=goals,
    question_counts={
        "multiple_choice": 2,
        "short_answer": 2,
        "complete": 2,
        "true_false": 2
    },
    difficulty_levels=[1, 2]
)

# AFTER (optimized):
questions_result = self.template_generator.generate_goal_based_questions(
    content=content,
    goals=goals[:3],  # Limit to 3 goals instead of 5-7
    question_counts={
        "multiple_choice": 2,
        "short_answer": 1,  # Reduced
        "complete": 1,      # Reduced
        "true_false": 2
    },
    difficulty_levels=[1, 2]
)
```

---

## 📊 API Calls Breakdown (Per Document)

### Current Configuration (Expensive)
```
Content Analysis:        1 call   ⭐⭐⭐⭐
Learning Goals:          1 call   ⭐⭐⭐
Summary:                 1 call   ⭐⭐
Worksheet:               1 call   ⭐⭐⭐
Questions (5 goals):     5 calls  ⭐⭐⭐⭐⭐
Mind Map (multi-pass):   6 calls  ⭐⭐⭐⭐⭐⭐⭐⭐
                        ─────────
Total:                  15 calls  💰💰💰
```

### Optimized Configuration (Cheap)
```
Content Analysis:        1 call   ⭐⭐⭐⭐
Learning Goals:          1 call   ⭐⭐⭐
Summary:                 1 call   ⭐⭐
Worksheet:               1 call   ⭐⭐⭐
Questions (3 goals):     3 calls  ⭐⭐⭐
Mind Map (single-pass):  1 call   ⭐⭐⭐
                        ─────────
Total:                   8 calls  💰
SAVINGS:                 -47%     ✅
```

---

## 🎯 Feature-by-Feature Cost Analysis

### 🔴 Mind Map Generation - **HIGHEST COST**
**Current:** 3-10 calls per document  
**Why:** Multi-pass chunking + enhanced thinking

**Solutions:**
```bash
# Option 1: Single-pass only (1 call instead of 3-10)
MINDMAP_MULTI_PASS=false

# Option 2: Disable enhanced thinking (cuts calls by 50%)
MINDMAP_ENHANCED_THINKING=false

# Option 3: Skip mind maps for bulk processing
python bulk_generator.py --templates questions worksheets summaries
```

**Savings:** 60-80% reduction in mind map costs

---

### 🟠 Question Generation - **HIGH COST**
**Current:** 1-7 calls per document (depends on goal count)  
**Why:** Goal-based mode generates questions per goal

**Solutions:**
```python
# Option 1: Fewer goals (edit batch_processor.py line ~175)
goals = goals[:3]  # Limit to 3 goals

# Option 2: Use standard question generation instead of goal-based
questions = generator.generate_question_bank(
    content=content,
    goals=goals,
    question_counts={...}
)
# This uses 1 call instead of N calls (where N = number of goals)
```

**Savings:** 40-60% reduction in question costs

---

### 🟡 Content Analysis - **RUNS FOR EVERYTHING**
**Current:** 1 call per document  
**Why:** Needed to detect language, subject, math content

**Solutions:**
```python
# Cache analysis results (currently not cached)
# Add to template_generator.py:

def generate_template(self, ...):
    if not hasattr(self, '_cached_analysis'):
        self._cached_analysis = {}
    
    # Use cached analysis if available
    if content_hash not in self._cached_analysis:
        analysis = self.content_processor.analyze_content(content)
        self._cached_analysis[content_hash] = analysis
    else:
        analysis = self._cached_analysis[content_hash]
```

**Savings:** Minimal (1 call is reasonable), but caching prevents duplicate analyses

---

### 🟢 Other Templates - **LOW COST**
- Summary: 1 call (keep as is) ✅
- Worksheet: 1 call (keep as is) ✅
- Goals: 1 call when needed (use DB when possible) ✅

---

## 📈 Cost Comparison Table

| Scenario | Calls/Doc | 100 Docs | Est. Cost | Savings |
|----------|-----------|----------|-----------|---------|
| **Current (All Features)** | 15 | 1,500 | $20-30 | - |
| **Optimized (Recommended)** | 8 | 800 | $8-12 | 50-60% |
| **Minimal (Emergency)** | 4 | 400 | $4-6 | 70-80% |

### Minimal Configuration (Emergency Budget):
```bash
# Only generate summaries and basic questions
python bulk_generator.py --templates summaries questions --max-docs 100

# In batch_processor.py, use standard questions (not goal-based)
questions = self.template_generator.generate_question_bank(
    content=content,
    goals=goals,
    question_counts={"multiple_choice": 2, "short_answer": 1}
)
```

---

## 🔧 Environment Variables Cheat Sheet

```bash
# Copy this to your .env file for optimized costs:

# OpenAI API Key (required)
OPENAI_API_KEY=your_key_here

# Models (cheaper model for non-math)
OPENAI_MODEL_NORMAL=gpt-4o-mini
OPENAI_MODEL_MATH=gpt-5
TEMPERATURE=0.7

# Mind Map Optimization (IMPORTANT!)
MINDMAP_ENHANCED_THINKING=false      # 50% reduction
MINDMAP_MULTI_PASS=false             # 60% reduction
MINDMAP_MAX_NODES=80                 # Smaller output
MINDMAP_CHUNK_SIZE_CHARS=5000        # Larger chunks = fewer calls

# Processing
MINDMAP_DEDUPLICATE_NODES=true
MINDMAP_MAX_DEPTH=4
MINDMAP_EXCLUDE_EXAMPLES=true
```

---

## 💡 Smart Processing Strategies

### Strategy 1: Prioritized Processing
Process high-value content with all features, low-value with minimal features:

```bash
# Important curriculum content (full features)
python bulk_generator.py --uuid important-doc-uuid --templates questions worksheets summaries mindmaps

# Supplementary content (minimal features)
python bulk_generator.py --templates summaries questions --max-docs 100
```

### Strategy 2: Batch Optimization
Use `--skip-existing` to avoid regenerating content:

```bash
python bulk_generator.py --skip-existing --templates questions worksheets summaries mindmaps
```

### Strategy 3: Staged Generation
Generate templates in stages to spread cost:

```bash
# Week 1: Generate summaries and worksheets
python bulk_generator.py --templates summaries worksheets --max-docs 100

# Week 2: Generate questions
python bulk_generator.py --templates questions --max-docs 100 --skip-existing

# Week 3: Generate mind maps (most expensive)
python bulk_generator.py --templates mindmaps --max-docs 100 --skip-existing
```

---

## 🎯 Recommended Configurations

### Production (Balanced)
```bash
MINDMAP_ENHANCED_THINKING=false
MINDMAP_MULTI_PASS=true
MINDMAP_CHUNK_SIZE_CHARS=3000
# Goals: 3-4 per document
# Question counts: standard (2 per type)
```
**Cost:** $10-15 per 100 docs

### Development/Testing
```bash
MINDMAP_ENHANCED_THINKING=false
MINDMAP_MULTI_PASS=false
# Goals: 2-3 per document
# Question counts: minimal (1-2 per type)
```
**Cost:** $5-8 per 100 docs

### Premium (Full Features)
```bash
MINDMAP_ENHANCED_THINKING=true
MINDMAP_MULTI_PASS=true
MINDMAP_CHUNK_SIZE_CHARS=1800
# Goals: 5-7 per document
# Question counts: full (5+ per type)
```
**Cost:** $20-30 per 100 docs

---

## 📊 Monitor Your Usage

Add this to track costs in real-time:

```python
# Add to bulk_generator.py or batch_processor.py

import time

class CostTracker:
    def __init__(self):
        self.call_count = 0
        self.start_time = time.time()
        self.by_template = {}
    
    def log_call(self, template_type):
        self.call_count += 1
        self.by_template[template_type] = self.by_template.get(template_type, 0) + 1
    
    def print_summary(self):
        elapsed = time.time() - self.start_time
        print(f"\n💰 API Usage Summary:")
        print(f"   Total Calls: {self.call_count}")
        print(f"   Duration: {elapsed:.1f}s")
        print(f"   Calls by Template:")
        for template, count in self.by_template.items():
            print(f"      {template}: {count} calls")
        print(f"   Estimated Cost: ${self.call_count * 0.01:.2f} - ${self.call_count * 0.02:.2f}")

# Usage:
tracker = CostTracker()
# Before each API call:
tracker.log_call("mindmap")
# At the end:
tracker.print_summary()
```

---

## ✅ Action Checklist

- [ ] Update `.env` with optimized settings
- [ ] Test with small batch (10 docs) first
- [ ] Monitor API call counts
- [ ] Compare output quality
- [ ] Scale up if acceptable
- [ ] Set up cost monitoring
- [ ] Review monthly API usage

---

## 🆘 Emergency Cost Controls

If you're over budget:

1. **Immediate:** Set `MINDMAP_MULTI_PASS=false`
2. **Short-term:** Skip mind maps: `--templates questions worksheets summaries`
3. **Medium-term:** Reduce goals to 2-3 per document
4. **Long-term:** Cache analysis results and implement request pooling

---

## 📞 Quick Reference

| Action | Command/Setting | Impact |
|--------|----------------|---------|
| Disable multi-pass | `MINDMAP_MULTI_PASS=false` | -60% mind map cost |
| Disable enhanced thinking | `MINDMAP_ENHANCED_THINKING=false` | -50% mind map cost |
| Fewer goals | `goals[:3]` in code | -40% question cost |
| Skip mind maps | `--templates questions worksheets summaries` | -30% total cost |
| Reduce questions | Modify question_counts | -20% question cost |

---

**Remember:** Always test changes with a small batch first to ensure output quality meets your requirements!

---

**Last Updated:** October 21, 2025
