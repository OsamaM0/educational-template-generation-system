# OpenAI API Budget Analysis - Template Generation System

## 🔍 Executive Summary

This document analyzes all OpenAI API calls in your codebase and ranks them by their budget impact. The system uses **OpenAI API calls** extensively for generating educational content.

---

## 📊 API Consumption Ranking (Highest to Lowest Impact)

### 🥇 **1. MIND MAP GENERATION - HIGHEST COST**
**Impact Level:** ⭐⭐⭐⭐⭐ (VERY HIGH)

**Location:** `template/mindmap_template.py`

**Why It's Expensive:**
1. **Multi-Pass Processing**: When enabled (`MINDMAP_MULTI_PASS=true`), long content is split into chunks and each chunk makes a separate API call
2. **Multiple API Calls Per Document**: 
   - Planning phase call (if `MINDMAP_ENHANCED_THINKING=true`)
   - Generation call for each chunk
   - For a 5000-character document with 1800-char chunks = **3-4 API calls per document**
3. **Large Context Windows**: Each call includes full educational content
4. **Complex JSON Output**: Generates structured GoJS mind map data

**Code Evidence:**
```python
# Multi-pass chunking in mindmap_template.py
if Settings.MINDMAP_MULTI_PASS and len(content) > Settings.MINDMAP_CHUNK_SIZE_CHARS:
    chunks = self._chunk_text(content, Settings.MINDMAP_CHUNK_SIZE_CHARS, ...)
    for idx, ch in enumerate(chunks):
        mm = self._generate_single_pass(ch)  # API CALL PER CHUNK
        partial_maps.append(mm)

# Enhanced thinking adds another API call
if use_planning:
    _ = planning_chain.invoke({"context": docs})  # EXTRA API CALL
response = main_chain.invoke({"context": docs})  # MAIN API CALL
```

**Configuration Impact:**
- `MINDMAP_MULTI_PASS=true` → Multiple calls per document
- `MINDMAP_ENHANCED_THINKING=true` → Doubles the calls (planning + generation)
- `MINDMAP_CHUNK_SIZE_CHARS=1800` → Smaller = more chunks = more calls

**Cost Estimation (per document):**
- Single-pass: **1-2 API calls**
- Multi-pass (5000 chars): **3-5 API calls**
- With enhanced thinking: **6-10 API calls**

---

### 🥈 **2. QUESTION GENERATION - HIGH COST**
**Impact Level:** ⭐⭐⭐⭐ (HIGH)

**Location:** `template/question_template.py`

**Why It's Expensive:**
1. **Math-Enhanced Processing**: When mathematical content is detected, additional reasoning is applied
2. **Multiple Question Types**: Generates 4 types (multiple choice, short answer, complete, true/false)
3. **Goal-Based Generation**: In goal-based mode, generates questions FOR EACH GOAL separately
4. **Large Output Tokens**: Must generate detailed questions with solutions, outlines, and metadata

**Code Evidence:**
```python
# In question_template.py - Math reasoning adds overhead
if use_math_thinking:
    prompt_template = self.get_math_thinking_prompt_template(self.language)
    # More complex prompts = more tokens

# In goal_based_template.py - MULTIPLE API CALLS
for goal in goals:
    goal_specific_questions = self._generate_questions_for_single_goal(
        content, goal, ...
    )  # API CALL PER GOAL

# For 5 goals = 5 separate API calls!
```

**Configuration Impact:**
- More goals → More API calls (1 call per goal in goal-based mode)
- Math content → Larger prompts and outputs (solution_outline, worked_solution)
- Question counts → More output tokens

**Cost Estimation (per document):**
- Standard mode: **1 API call**
- Goal-based with 5 goals: **5 API calls**
- Math-enhanced: **+30% token cost per call**

---

### 🥉 **3. CONTENT ANALYSIS - MODERATE-HIGH COST**
**Impact Level:** ⭐⭐⭐⭐ (HIGH - RUNS FOR EVERY TEMPLATE)

**Location:** `processors/content_processor.py`

**Why It's Critical:**
1. **Runs Before Every Template Generation**: Called once per document to detect subject, math content, etc.
2. **Large Context Window**: Sends full content for analysis
3. **Structured JSON Output**: Requires detailed analysis with multiple fields

**Code Evidence:**
```python
# In content_processor.py - analyze_content()
def analyze_content(self, content: str) -> Dict[str, Any]:
    prompt = (
        "You are an expert educational content analyst.\n"
        "Analyze the following content and return ONLY a strict JSON object..."
        f"Content:\n{content}"  # FULL CONTENT SENT
    )
    response = self.model.invoke(prompt)  # API CALL

# Called in template_generator.py BEFORE generation
content_analysis = self.content_processor.analyze_content(preprocessed_content)
```

**Cost Estimation (per document):**
- **1 API call per document** (but runs for EVERY template type)
- Medium input tokens + small output tokens

---

### 4️⃣ **4. LEARNING GOALS GENERATION - MODERATE COST**
**Impact Level:** ⭐⭐⭐ (MODERATE)

**Location:** `processors/content_processor.py`

**Why It Costs:**
1. **Called When No Goals Exist**: Generates 3-7 learning goals from content
2. **Sends Full Content**: Large input tokens
3. **Used in Worksheets & Questions**: Called during batch processing

**Code Evidence:**
```python
# In content_processor.py
def generate_learning_goals(self, content: str, language: Optional[str] = None, count: int = 5):
    prompt = f"{system}\nCount: {target}.\nContent:\n{content}"
    response = self.model.invoke(prompt)  # API CALL

# Called in batch_processor.py when no DB goals
if not goals:
    goals = self.template_generator.content_processor.generate_learning_goals(content, count=5)
```

**Cost Estimation:**
- **1 API call per document** (when goals don't exist in DB)
- Medium input + small output tokens

---

### 5️⃣ **5. WORKSHEET GENERATION - MODERATE COST**
**Impact Level:** ⭐⭐⭐ (MODERATE)

**Location:** `template/worksheet_template.py`

**Why It Costs:**
1. **Sends Full Content**: Large context window
2. **Generates Structured Output**: Applications, vocabulary, teacher guidelines
3. **Includes Goals Generation**: May extract/refine goals

**Code Evidence:**
```python
# In worksheet_template.py
def generate(self, content: str, goals: List[str] = None, **kwargs):
    chain = prompt | self.model | self.parser
    result = chain.invoke({
        "content": content,  # FULL CONTENT
        "goals": "\n".join(goals)
    })  # API CALL
```

**Cost Estimation:**
- **1 API call per document**
- Medium-large input + medium output tokens

---

### 6️⃣ **6. SUMMARY GENERATION - LOW-MODERATE COST**
**Impact Level:** ⭐⭐ (LOW-MODERATE)

**Location:** `template/summary_template.py`

**Why It's Cheaper:**
1. **Simple Output**: Just opening, summary, ending
2. **Single Pass**: No multi-pass or chunking
3. **No Complex Reasoning**: Straightforward summarization

**Code Evidence:**
```python
# In summary_template.py
def generate(self, content: str, goals: List[str] = None, **kwargs):
    chain = create_stuff_documents_chain(self.model, prompt)
    result = chain.invoke({"context": docs})  # API CALL (simple)
```

**Cost Estimation:**
- **1 API call per document**
- Medium input + small output tokens

---

## 📈 Bulk Processing Impact

**Location:** `bulk_generator.py` and `batch_processor.py`

**The Multiplier Effect:**

When processing documents in bulk, the cost multiplies:

```python
# In batch_processor.py - PER DOCUMENT:
# 1. Content Analysis: 1 API call
# 2. Goals Generation (if needed): 1 API call
# 3. Summary: 1 API call
# 4. Worksheet: 1 API call
# 5. Questions (goal-based with 5 goals): 5 API calls
# 6. Mind Map (multi-pass with 3 chunks): 3-6 API calls

# TOTAL PER DOCUMENT: 12-15 API calls minimum!
```

**For 100 Documents:**
- Minimum: **1,200-1,500 API calls**
- With all features enabled: **2,000+ API calls**

**Code Evidence:**
```python
# In batch_processor.py
ordered_types = ["summaries", "worksheets", "questions", "mindmaps"]

# Each document goes through ALL templates:
for document in documents:
    # 1. Summary
    summary_result = self.template_generator.generate_summary(content)
    
    # 2. Goals (if not in DB)
    goals = self.template_generator.content_processor.generate_learning_goals(content)
    
    # 3. Worksheet
    worksheet_result = self.template_generator.generate_worksheet(content, goals)
    
    # 4. Questions (MULTIPLE CALLS if goal-based)
    questions_result = self.template_generator.generate_goal_based_questions(content, goals)
    
    # 5. Mind Map (MULTIPLE CALLS if multi-pass)
    mindmap_result = self.template_generator.generate_mindmap(content)
```

---

## 💰 Cost Breakdown by Template Type

### Cost Ranking (per document):

| Rank | Template Type | API Calls | Relative Cost | Notes |
|------|--------------|-----------|---------------|-------|
| 1 | **Mind Map** | 3-10 | ⭐⭐⭐⭐⭐ | Multi-pass + enhanced thinking |
| 2 | **Questions (Goal-Based)** | 1-7 | ⭐⭐⭐⭐ | 1 call per goal |
| 3 | **Content Analysis** | 1 | ⭐⭐⭐⭐ | Runs for all templates |
| 4 | **Learning Goals** | 0-1 | ⭐⭐⭐ | Only when no DB goals |
| 5 | **Worksheet** | 1 | ⭐⭐⭐ | Moderate I/O |
| 6 | **Summary** | 1 | ⭐⭐ | Simple output |

---

## 🎯 Specific High-Cost Scenarios

### Scenario 1: Mathematical Content
**Extra Cost:** +30-50%

When content is detected as mathematical:
- Uses more expensive model (`gpt-5` vs `gpt-4o-mini`)
- Generates solution outlines and worked solutions
- Enhanced reasoning prompts (longer)

```python
# In generators/template_generator.py
def _select_model_name(self, content_analysis: Dict[str, Any]) -> str:
    if content_analysis.get('is_mathematical'):
        return Settings.MATH_MODEL  # gpt-5 (more expensive!)
    return Settings.NON_MATH_MODEL  # gpt-4o-mini
```

### Scenario 2: Long Documents with Mind Maps
**Extra Cost:** +200-400%

Long documents (>5000 chars) with multi-pass mind map generation:
- 3-5 chunks = 3-5 API calls
- Planning phase = +1 call per chunk
- Total: 6-10 calls just for mind map

### Scenario 3: Goal-Based Questions with Many Goals
**Extra Cost:** Linear with goal count

With 7 goals vs 3 goals:
- 7 API calls vs 3 API calls
- +133% increase

---

## 🔧 Configuration Settings Impact

### High-Impact Settings:

```python
# settings.py - THESE SETTINGS DRAMATICALLY AFFECT COST:

# 1. Mind Map Settings (HIGHEST IMPACT)
MINDMAP_MULTI_PASS = True          # ⚠️ Enables chunking = multiple calls
MINDMAP_ENHANCED_THINKING = True   # ⚠️ Doubles mind map calls
MINDMAP_CHUNK_SIZE_CHARS = 1800    # ⚠️ Smaller = more chunks

# 2. Model Selection (HIGH IMPACT)
MATH_MODEL = "gpt-5"               # ⚠️ More expensive for math content
NON_MATH_MODEL = "gpt-4o-mini"     # ✅ Cheaper for non-math

# 3. Question Settings (MODERATE IMPACT)
DEFAULT_QUESTION_COUNTS = {
    "multiple_choice": 5,           # More questions = more output tokens
    "short_answer": 3,
    "complete": 2,
    "true_false": 3
}
```

---

## 💡 Optimization Recommendations

### 🔴 **Critical - High Impact:**

1. **Disable Multi-Pass Mind Maps for Short Content**
   ```python
   # Set higher threshold or disable for documents < 3000 chars
   MINDMAP_MULTI_PASS = False  # or increase MINDMAP_CHUNK_SIZE_CHARS
   ```

2. **Disable Enhanced Thinking for Mind Maps**
   ```python
   MINDMAP_ENHANCED_THINKING = False  # Cuts mind map calls by 50%
   ```

3. **Reduce Goal Count for Questions**
   ```python
   # In batch_processor.py, generate fewer goals:
   goals = self.template_generator.content_processor.generate_learning_goals(content, count=3)  # Instead of 5
   ```

4. **Use Cached Content Analysis**
   ```python
   # Store analysis results and reuse across template types
   # Currently, analysis might run multiple times
   ```

### 🟠 **Moderate Impact:**

5. **Reduce Question Counts**
   ```python
   question_counts = {
       "multiple_choice": 2,  # Reduced from 5
       "short_answer": 1,     # Reduced from 3
       "complete": 1,         # Reduced from 2
       "true_false": 2        # Reduced from 3
   }
   ```

6. **Skip Existing Documents**
   ```python
   # Already implemented in batch_processor.py
   skip_existing = True  # Good! Prevents redundant API calls
   ```

7. **Use Standard Questions Instead of Goal-Based**
   ```python
   # Use generate_question_bank() instead of generate_goal_based_questions()
   # Saves 4-6 API calls per document
   ```

### 🟢 **Low Impact (Fine-Tuning):**

8. **Batch Process with Parallel Workers**
   ```python
   # Use multiple workers to speed up BUT this won't reduce API calls
   # Just faster processing
   --workers 3
   ```

9. **Lower Temperature**
   ```python
   TEMPERATURE = 0.3  # From 0.7 - slightly fewer output tokens
   ```

---

## 📊 Estimated Cost Savings

### Current Configuration (All Features Enabled):
- **Per Document:** 12-15 API calls
- **100 Documents:** ~1,300-1,500 calls
- **Estimated Cost:** $15-30 (depending on models and token counts)

### Optimized Configuration:
```python
MINDMAP_MULTI_PASS = False
MINDMAP_ENHANCED_THINKING = False
Goals: 3 instead of 5-7
Question counts: Reduced by 40%
```

- **Per Document:** 6-8 API calls
- **100 Documents:** ~600-800 calls
- **Estimated Cost:** $6-12
- **💰 Savings: ~50-60%**

---

## 🎯 Quick Action Items

**To immediately reduce costs by 40-50%:**

1. Edit `config/settings.py`:
   ```python
   MINDMAP_ENHANCED_THINKING = False  # Remove planning phase
   MINDMAP_MULTI_PASS = False  # Single-pass only
   ```

2. Edit `batch_processor.py`:
   ```python
   # Line ~175 - Reduce goals
   goals = self.template_generator.content_processor.generate_learning_goals(content, count=3)
   
   # Line ~200 - Reduce questions
   question_counts={
       "multiple_choice": 2,
       "short_answer": 1,
       "complete": 1,
       "true_false": 2
   }
   ```

3. For non-critical content, skip mind maps:
   ```bash
   python bulk_generator.py --templates questions worksheets summaries
   # Skip mindmaps entirely
   ```

---

## 📌 Summary Table

| Feature | API Calls/Doc | Cost Impact | Optimization |
|---------|--------------|-------------|--------------|
| Mind Map (Multi-pass) | 3-10 | ⭐⭐⭐⭐⭐ | Disable or single-pass |
| Questions (Goal-based) | 1-7 | ⭐⭐⭐⭐ | Fewer goals or standard mode |
| Content Analysis | 1 | ⭐⭐⭐⭐ | Cache results |
| Worksheet | 1 | ⭐⭐⭐ | Keep as is |
| Goals Generation | 0-1 | ⭐⭐⭐ | Use DB goals |
| Summary | 1 | ⭐⭐ | Keep as is |

**Total (Current):** 12-15 calls/doc  
**Total (Optimized):** 6-8 calls/doc  
**Potential Savings:** 40-60%

---

## 🔍 Code Locations Reference

| Component | File | Line(s) | Description |
|-----------|------|---------|-------------|
| Mind Map Multi-Pass | `template/mindmap_template.py` | 136-155 | Chunking and multi-pass logic |
| Mind Map Planning | `template/mindmap_template.py` | 206-214 | Enhanced thinking phase |
| Question Goal Loop | `template/goal_based_template.py` | 104-115 | Per-goal question generation |
| Content Analysis | `processors/content_processor.py` | 32-125 | AI-driven content analysis |
| Goals Generation | `processors/content_processor.py` | 15-30 | AI-generated learning goals |
| Batch Processing | `processors/batch_processor.py` | 155-250 | Per-document template generation |
| Model Selection | `generators/template_generator.py` | 55-61 | Math vs non-math model switching |

---

## 📈 Monitoring Recommendations

Add logging to track API usage:

```python
# Add to template_generator.py
import time

class APICallTracker:
    def __init__(self):
        self.calls = []
    
    def log_call(self, template_type, tokens_used, duration):
        self.calls.append({
            'type': template_type,
            'tokens': tokens_used,
            'duration': duration,
            'timestamp': time.time()
        })
    
    def get_summary(self):
        return {
            'total_calls': len(self.calls),
            'total_tokens': sum(c['tokens'] for c in self.calls),
            'by_type': {t: len([c for c in self.calls if c['type'] == t]) for t in set(c['type'] for c in self.calls)}
        }
```

---

**Last Updated:** October 21, 2025  
**Analyzer:** GitHub Copilot
