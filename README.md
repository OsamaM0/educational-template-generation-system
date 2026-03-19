# TahderPlus — Educational Template Generation System

An AI-powered educational content generation platform that transforms lesson documents into structured question banks, worksheets, summaries, and mind maps. Built for the **TahderPlus** e-learning ecosystem with first-class **Arabic** and **English** bilingual support.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Quick Start](#quick-start)
- [Template Types](#template-types)
  - [Question Bank](#1-question-bank)
  - [Goal-Based Questions](#2-goal-based-questions)
  - [Worksheet](#3-worksheet)
  - [Summary](#4-summary)
  - [Mind Map](#5-mind-map)
- [CLI Usage](#cli-usage)
  - [Single Document](#single-document-mainpy)
  - [Bulk Processing](#bulk-processing-bulk_generatorpy)
- [Python API](#python-api)
- [Output Structures](#output-structures)
- [Mind Map Advanced Configuration](#mind-map-advanced-configuration)
- [Math-Aware Reasoning](#math-aware-reasoning)
- [Project Structure](#project-structure)
- [Dependencies](#dependencies)
- [Mind Map Reprocessing](#mind-map-reprocessing)

---

## Overview

The system ingests educational lesson content (plain text or fetched from a REST API), analyzes it with AI, and produces five types of structured educational materials:

| Template | Description |
|----------|-------------|
| **Question Bank** | Multiple choice, short answer, completion, and true/false questions |
| **Goal-Based Questions** | Questions aligned to specific learning goals with Bloom's taxonomy levels |
| **Worksheet** | Structured lesson worksheet with goals, vocabulary, activities, and teacher guidelines |
| **Summary** | Lesson summary with opening, body, and closing sections |
| **Mind Map** | Hierarchical concept map in GoJS-compatible JSON format |

The pipeline automatically detects language (Arabic/English), identifies whether content is mathematical, selects the appropriate AI model, and structures output using Pydantic schemas for guaranteed validity.

---

## Architecture

```
┌──────────────────┐       ┌──────────────────┐
│  Document REST   │       │     MongoDB      │
│   API Server     │       │  (ien + ai DBs)  │
└────────┬─────────┘       └────────┬─────────┘
         │  fetch documents          │  read goals / store results
         ▼                           ▼
┌──────────────────┐       ┌──────────────────┐
│ DocumentAPIClient│       │  MongoDBClient   │
└────────┬─────────┘       └────────┬─────────┘
         │                           │
         └─────────┬─────────────────┘
                   ▼
          ┌─────────────────┐
          │ BatchProcessor  │   (orchestrates per-document pipeline)
          └────────┬────────┘
                   ▼
          ┌─────────────────────┐
          │  TemplateGenerator  │   (main orchestrator)
          │  ├─ ContentProcessor│   (AI content analysis)
          │  ├─ LanguageDetector│   (Arabic / English)
          │  └─ InputValidator  │   (input validation)
          └────────┬────────────┘
                   │ delegates to
     ┌─────────────┼────────────────────────┐
     │             │             │           │           │
┌────┴────┐  ┌────┴─────┐  ┌───┴───┐  ┌────┴────┐  ┌───┴──────┐
│Question │  │GoalBased │  │Work-  │  │Summary  │  │MindMap   │
│Template │  │Template  │  │sheet  │  │Template │  │Template  │
│(+Math)  │  │          │  │       │  │         │  │(chunked) │
└─────────┘  └──────────┘  └───────┘  └─────────┘  └──────────┘
     │             │
     └─────────────┴── Prompt Templates (Arabic & English)
                         + Pydantic Models → Structured JSON Output
```

### Data Flow (Batch Processing)

For each document the pipeline runs in order:

1. **Fetch** — Document content retrieved from REST API
2. **Analyze** — `ContentProcessor` detects language, subject area, math presence, complexity
3. **Model Select** — `gpt-5` for mathematical content, `gpt-4o-mini` for everything else
4. **Generate Summary** → stored in `ai.summaries`
5. **Resolve Goals** → from MongoDB (`ien.lessonplangoals`) or AI-generated
6. **Generate Worksheet** → stored in `ai.worksheets` (may refine goals)
7. **Generate Goal-Based Questions** → stored in `ai.questions`
8. **Generate Mind Map** → stored in `ai.mindmaps`

---

## Features

- **Bilingual (Arabic-first)** — Every prompt, fallback message, and output exists in both Arabic and English
- **Math-Aware Model Routing** — Automatically selects a stronger model for mathematical/scientific content
- **Goal-Based Pedagogy** — Questions organized per learning goal with Bloom's taxonomy cognitive levels
- **Multi-Pass Mind Maps** — Long content is chunked, independently mapped, then merged with deduplication
- **Robust JSON Parsing** — 4-stage fallback: direct parse → normalization → `json-repair` → combined
- **Structured Output** — Pydantic models + `JsonOutputParser` guarantee schema-valid LLM responses
- **Idempotent Storage** — MongoDB upserts prevent duplicates; `--skip-existing` avoids reprocessing
- **Thread-Safe Batch Processing** — Parallel workers with lock-protected statistics
- **Graceful Degradation** — AI failures fall back to rule-based methods for language detection, goal generation, and subject analysis
- **Configurable Difficulty** — Three difficulty levels with automatic math-aware policies (easy-only for math)

---

## Prerequisites

- **Python 3.10+**
- **OpenAI API Key** (with access to `gpt-4o-mini` and optionally `gpt-5`)
- **MongoDB** (optional — required only for bulk processing and goal storage)
- **Document API server** (optional — required only for bulk processing)

---

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd template_generation

# Install dependencies
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```env
# Required
OPENAI_API_KEY=sk-...

# Optional — Model selection
OPENAI_MODEL_NORMAL=gpt-4o-mini     # for non-math content
OPENAI_MODEL_MATH=gpt-5             # for mathematical content
TEMPERATURE=0.7

# Optional — MongoDB (for bulk processing)
MONGODB_URI=mongodb://localhost:27017

# Optional — Document API (for bulk processing)
DOCUMENT_API_BASE_URL=http://65.109.31.94:8080
```

---

## Configuration

All configuration is centralized in `config/settings.py` and loaded from environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | — | **Required.** Your OpenAI API key |
| `OPENAI_MODEL_NORMAL` | `gpt-4o-mini` | Model for non-mathematical content |
| `OPENAI_MODEL_MATH` | `gpt-5` | Model for mathematical/scientific content |
| `TEMPERATURE` | `0.7` | LLM sampling temperature |
| `DEFAULT_LANGUAGE` | `arabic` | Default language (`arabic` or `english`) |
| `MINDMAP_MULTI_PASS` | `true` | Enable multi-pass chunking for long content |
| `MINDMAP_CHUNK_SIZE_CHARS` | `1800` | Characters per chunk in multi-pass mode |
| `MINDMAP_CHUNK_OVERLAP_CHARS` | `250` | Overlap between chunks |
| `MINDMAP_DEDUPLICATE_NODES` | `true` | Deduplicate nodes by text under same parent |
| `MINDMAP_MAX_NODES` | `120` | Maximum nodes in final mind map |
| `MINDMAP_MAX_DEPTH` | `3` | Maximum tree depth (root = 0) |
| `MINDMAP_EXCLUDE_EXAMPLES` | `true` | Filter out example/story nodes |

Default question counts: **5** MC, **3** short answer, **2** completion, **3** true/false.  
Difficulty levels: **1** (easy), **2** (medium), **3** (hard).

---

## Quick Start

### Generate a Question Bank from a File

```bash
python main.py questions lesson.txt --goals "Students understand fractions" --mc 5 --sa 3 --tf 4 -o output.json
```

### Generate All Templates in Python

```python
from generators.template_generator import TemplateGenerator

generator = TemplateGenerator()

content = "Your educational lesson content here..."

# Question bank
questions = generator.generate_question_bank(content=content, goals=["Goal 1", "Goal 2"])

# Worksheet
worksheet = generator.generate_worksheet(content=content, goals=["Goal 1"])

# Summary
summary = generator.generate_summary(content=content)

# Mind map
mindmap = generator.generate_mindmap(content=content)

# Goal-based questions
goal_questions = generator.generate_goal_based_questions(content=content, goals=["Goal 1", "Goal 2"])
```

---

## Template Types

### 1. Question Bank

Generates a bank of diverse question types from lesson content.

**Question types:** Multiple Choice, Short Answer, Completion (fill-in-the-blank), True/False

Each question includes: question text, answer, difficulty level (1–3), and target goal alignment. Multiple choice questions include 4 choices and a 0-based answer key.

```python
result = generator.generate_template(
    template_type="questions",
    content="your lesson content",
    goals=["Goal 1", "Goal 2"],
    question_counts={"multiple_choice": 5, "short_answer": 3, "complete": 2, "true_false": 4},
    difficulty_levels=[1, 2, 3]
)
```

### 2. Goal-Based Questions

An enhanced question generation mode that organizes every question under a specific learning goal with Bloom's taxonomy cognitive level tagging.

**Two scenarios:**

| Scenario | Input | Behavior |
|----------|-------|----------|
| Goals provided | `goals=["...", "..."]` | Classifies goals by cognitive level, generates questions per goal |
| No goals | `goals=None` | Generates a worksheet first to extract goals, then generates questions |

```python
# Scenario 1: Goals provided
result = generator.generate_goal_based_questions(
    content="Geometry lesson about triangles...",
    goals=["Understand triangle types", "Apply Pythagorean theorem"],
    question_counts={"multiple_choice": 6, "short_answer": 4, "complete": 2, "true_false": 2}
)

# Scenario 2: Auto-generate goals
result = generator.generate_goal_based_questions(
    content="Physics lesson about motion and force...",
    goals=None
)
```

**Cognitive levels** (Bloom's taxonomy): remember, understand, apply, analyze, evaluate, create — detected from keywords in both Arabic and English.

### 3. Worksheet

Generates a structured lesson worksheet containing:
- Learning goals
- Practical applications
- Vocabulary with definitions
- Teacher guidelines
- Optional: structured goals with activities and assessment methods

```python
worksheet = generator.generate_template(template_type="worksheet", content="...", goals=["..."])
```

### 4. Summary

Generates a three-part lesson summary:
- **Opening** — engaging introduction
- **Summary** — core content distillation
- **Ending** — closure and takeaway

```python
summary = generator.generate_template(template_type="summary", content="...")
```

### 5. Mind Map

Generates a hierarchical concept map in **GoJS TreeModel** format, ready for frontend visualization.

**Key capabilities:**
- Multi-pass chunking for long content (sentence-boundary aware)
- Automatic merge and deduplication across chunks
- Depth-limited tree with configurable max depth
- Balanced left/right branch distribution
- Depth-based color assignment
- Example/story node filtering

```python
mindmap = generator.generate_template(template_type="mindmap", content="...")
# Returns: {"class": "go.TreeModel", "nodeDataArray": [...]}
```

---

## CLI Usage

### Single Document (`main.py`)

```bash
python main.py <template_type> <content_file> [options]
```

**Template types:** `questions` | `goal_based_questions` | `worksheet` | `summary` | `mindmap`

| Flag | Description |
|------|-------------|
| `--goals "G1" "G2"` | Learning goals (space-separated) |
| `--mc N` | Number of multiple choice questions (default: 3) |
| `--sa N` | Number of short answer questions (default: 2) |
| `--comp N` | Number of completion questions (default: 2) |
| `--tf N` | Number of true/false questions (default: 2) |
| `--difficulty 1 2 3` | Difficulty levels to include |
| `-o FILE` / `--output FILE` | Save result as JSON |
| `--thinking` | Enable enhanced thinking for math content |
| `--demo` | Run mathematical reasoning demo |

**Examples:**

```bash
# Questions with goals
python main.py questions lesson.txt --goals "Understand fractions" "Apply division" --mc 5 --sa 3

# Goal-based questions (auto-generate goals)
python main.py goal_based_questions lesson.txt --mc 6 --sa 4

# Worksheet
python main.py worksheet lesson.txt --goals "Goal 1" "Goal 2"

# Summary saved to file
python main.py summary lesson.txt -o summary.json

# Mind map
python main.py mindmap lesson.txt -o mindmap.json
```

### Bulk Processing (`bulk_generator.py`)

Process all documents from the REST API and store results in MongoDB:

```bash
python bulk_generator.py [options]
```

| Flag | Description |
|------|-------------|
| `--max-docs N` | Maximum documents to process |
| `--page-size N` | API page size |
| `--start-page N` | Start from this page |
| `--templates T1 T2` | Template types to generate |
| `--skip-existing` | Skip documents already processed |
| `--workers N` | Parallel workers (default: 1 = sequential) |
| `--uuid UUID` | Process a single document by UUID |
| `--test-connection` | Test API and MongoDB connectivity |
| `--stats` | Show current collection statistics |
| `--dry-run` | Fetch and analyze without generating |

**Examples:**

```bash
# Process all documents, skip already-done
python bulk_generator.py --skip-existing

# Process a single document
python bulk_generator.py --uuid "abc123-def456"

# Generate only summaries and mindmaps
python bulk_generator.py --templates summary mindmap --max-docs 50

# Test connectivity
python bulk_generator.py --test-connection

# Parallel processing with 4 workers
python bulk_generator.py --workers 4 --skip-existing
```

---

## Python API

### `TemplateGenerator` — Main Entry Point

```python
from generators.template_generator import TemplateGenerator

generator = TemplateGenerator()

# Universal method
result = generator.generate_template(
    template_type="questions",       # questions | goal_based_questions | worksheet | summary | mindmap
    content="...",
    goals=["..."],                   # optional
    question_counts={...},           # optional, for question types
    difficulty_levels=[1, 2, 3]      # optional
)

# Convenience methods
generator.generate_question_bank(content, goals, question_counts, difficulty_levels)
generator.generate_goal_based_questions(content, goals, question_counts)
generator.generate_worksheet(content, goals)
generator.generate_summary(content)
generator.generate_mindmap(content)
```

Every result dict includes a `_metadata` key with language, content analysis, and model information.

---

## Output Structures

### Question Bank

```json
{
  "multiple_choice": [
    {
      "question": "What is 2 + 2?",
      "choices": ["3", "4", "5", "6"],
      "answer_key": 1,
      "difficulty": 1,
      "target_goal": "Understand addition"
    }
  ],
  "short_answer": [{ "question": "...", "answer": "...", "difficulty": 1 }],
  "complete": [{ "question": "...", "answer": "...", "difficulty": 1 }],
  "true_false": [{ "question": "...", "answer": true, "difficulty": 1 }],
  "_metadata": { "language": "english", "content_analysis": { "..." } }
}
```

### Goal-Based Questions

```json
{
  "learning_goals": [
    { "id": "goal_1", "text": "...", "priority": 1, "cognitive_level": "understand" }
  ],
  "goal_question_mapping": [
    {
      "goal_id": "goal_1",
      "goal_text": "...",
      "question_count": 4,
      "question_types": { "multiple_choice": 2, "short_answer": 1, "complete": 1, "true_false": 0 }
    }
  ],
  "questions_by_goal": {
    "goal_1": { "multiple_choice": ["..."], "short_answer": ["..."] }
  },
  "multiple_choice": ["..."],
  "short_answer": ["..."],
  "_goal_based_metadata": {
    "total_goals": 3,
    "total_questions": 14,
    "scenario": "goals_provided",
    "questions_per_goal_distribution": {}
  }
}
```

### Worksheet

```json
{
  "goals": ["Goal 1", "Goal 2"],
  "applications": ["Application 1"],
  "vocabulary": [{ "term": "Fraction", "definition": "A part of a whole" }],
  "teacher_guidelines": ["Guideline 1"],
  "structured_goals": ["..."],
  "goal_based_activities": ["..."]
}
```

### Summary

```json
{
  "opening": "Engaging introduction...",
  "summary": "Core lesson content...",
  "ending": "Closing statement..."
}
```

### Mind Map (GoJS TreeModel)

```json
{
  "class": "go.TreeModel",
  "nodeDataArray": [
    { "key": 0, "text": "Main Topic", "loc": "0 0" },
    { "key": 1, "parent": 0, "text": "Branch 1", "brush": "skyblue", "dir": "right" },
    { "key": 2, "parent": 0, "text": "Branch 2", "brush": "skyblue", "dir": "left" },
    { "key": 3, "parent": 1, "text": "Sub-topic", "brush": "darkseagreen", "dir": "right" }
  ]
}
```

---

## Mind Map Advanced Configuration

### Smart Two-Phase Generation

1. **AI Phase** — The LLM generates the semantic structure: `key`, `parent`, `text`
2. **Post-Processing Phase** — System assigns visual properties: `brush` (color by depth), `dir` (balanced left/right), `loc` (root position)

This yields higher quality content structure while ensuring consistent visual styling.

### Multi-Pass Chunking

For long content, the generator:
1. Splits text at sentence boundaries into overlapping chunks
2. Generates a partial mind map per chunk
3. Merges all maps under a synthetic root node
4. Deduplicates nodes by normalized text under the same parent
5. Applies depth pruning and visual properties

### Professional Mode

| Variable | Default | Effect |
|----------|---------|--------|
| `MINDMAP_MAX_DEPTH` | `3` | Prune nodes deeper than this (root = 0) |
| `MINDMAP_EXCLUDE_EXAMPLES` | `true` | Remove example/story/scenario nodes (Arabic + English keywords) |
| `MINDMAP_MAX_NODES` | `120` | Cap total nodes in the output |

Post-processing automatically:
1. Prunes nodes beyond max depth
2. Filters example/story nodes
3. Assigns depth-based colors from a configurable palette
4. Balances left/right distribution using weighted descendant counts

---

## Math-Aware Reasoning

The system automatically detects mathematical content and applies special handling:

- **Model upgrade** — Routes to `gpt-5` (or configured math model) for higher reasoning accuracy
- **Chain-of-thought prompts** — Structured 5-step reasoning: understand → identify → plan → execute → verify
- **Solution fields** — Math questions include `solution_outline` (2–4 step plan) and `worked_solution` (formula → substitution → result → verification)
- **Difficulty policy** — Math content is restricted to easy difficulty only for accuracy
- **Math tools** — SymPy for symbolic equation solving, numexpr for safe numeric evaluation
- **Bilingual** — Chain-of-thought templates available in both Arabic and English

---

## Project Structure

```
template_generation/
├── main.py                      # CLI: single document generation
├── bulk_generator.py            # CLI: batch processing with API + MongoDB
├── requirements.txt             # Python dependencies
│
├── config/
│   ├── settings.py              # Central configuration (env vars)
│   └── api_config.py            # API configuration (reserved)
│
├── clients/
│   ├── api_client.py            # REST API client (document fetching)
│   └── mongo_client.py          # MongoDB client (goals + results storage)
│
├── generators/
│   └── template_generator.py    # Main orchestrator (model selection, routing)
│
├── processors/
│   ├── batch_processor.py       # Bulk document pipeline orchestrator
│   ├── content_processor.py     # AI content analysis + goal generation
│   └── prompt_builder.py        # Dynamic bilingual prompt assembly
│
├── template/
│   ├── base_template.py         # Abstract base class for all templates
│   ├── question_template.py     # Question bank generation (+ math agent)
│   ├── goal_based_template.py   # Goal-centric question generation
│   ├── worksheet_template.py    # Worksheet generation
│   ├── summary_template.py      # Summary generation
│   └── mindmap_template.py      # Mind map generation (multi-pass)
│
├── models/
│   ├── question_models.py       # Pydantic: questions, goals, mappings
│   ├── worksheet_models.py      # Pydantic: worksheet structure
│   ├── summary_models.py        # Pydantic: lesson summary
│   ├── mindmap_models.py        # Pydantic: GoJS-compatible mind map
│   └── storage_models.py        # Pydantic: MongoDB documents + stats
│
├── prompts/
│   ├── arabic/                  # Arabic prompt templates
│   │   ├── question_prompts.py
│   │   ├── worksheet_prompts.py
│   │   ├── summary_prompts.py
│   │   └── mindmap_prompts.py
│   └── english/                 # English prompt templates
│       ├── question_prompts.py
│       ├── worksheet_prompts.py
│       ├── summary_prompts.py
│       └── mindmap_prompts.py
│
├── tools/
│   └── math_reasoning.py        # SymPy solver, numexpr calculator, CoT prompts
│
├── utils/
│   ├── language_detector.py     # Arabic/English detection (langdetect + fallback)
│   ├── mindmap_postprocess.py   # Idempotent mind map post-processing
│   ├── subject_analyzer.py      # Subject analysis (reserved)
│   └── validators.py            # Input validation
│
├── example/                     # Example scripts and demos
│   ├── complete_example.py
│   ├── enhanced_math_demo.py
│   ├── goal_based_demo.py
│   ├── usage_examples.py
│   └── view_data.py
│
├── tests/
│   └── test_mindmap_parsing.py  # Mind map parsing tests
│
└── docs/
    ├── ARCHITECTURE.md          # Detailed architecture documentation
    └── MINDMAP_SMART_WORKFLOW.md # Mind map workflow documentation
```

---

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `langchain` | 0.3.21 | LLM orchestration framework |
| `langchain-openai` | 0.3.32 | OpenAI integration for LangChain |
| `langchain-core` | 0.3.75 | Core LangChain abstractions |
| `pydantic` | 2.7.4 | Data validation and structured LLM output |
| `openai` | 1.106.1 | OpenAI API client |
| `python-dotenv` | 1.0.0 | Environment variable loading from `.env` |
| `langdetect` | 1.0.9 | Language detection |
| `sympy` | 1.12 | Symbolic math (equation solving) |
| `numexpr` | 2.11.0 | Safe numeric expression evaluation |
| `pymongo` | 4.14.0 | MongoDB driver |
| `requests` | 2.31.0 | HTTP client for document API |
| `tqdm` | 4.66.1 | Progress bars for batch processing |
| `tenacity` | 8.2.3 | Retry logic with exponential backoff |
| `json-repair` | 0.50.0 | Malformed JSON repair from LLM output |
| `orjson` | *(optional)* | Faster JSON parsing |

---

## Mind Map Reprocessing

Retrofit existing mind maps in MongoDB with the latest post-processing (colors, direction balancing, depth pruning) **without re-generating via the LLM**.

```bash
# Dry run — preview changes without modifying the database
python reprocess_mindmaps.py --limit 10

# Apply changes
python reprocess_mindmaps.py --apply

# Filter by content
python reprocess_mindmaps.py --apply --filename chemistry
python reprocess_mindmaps.py --apply --contains-text الطاقة
python reprocess_mindmaps.py --apply --custom-id 652fa1c4b3...
```

| Flag | Description |
|------|-------------|
| `--apply` | Persist changes (omit for dry run) |
| `--limit N` | Process only first N documents |
| `--filename SUBSTR` | Filter by filename substring |
| `--custom-id ID` | Filter by exact custom_id |
| `--contains-text T` | Filter by node text content |

Reprocessing is **idempotent** — running multiple times produces identical results. Each run updates audit metadata (`reprocessed_at`, `reprocess_runs`, `reprocess_changes`).

---

## License

*Add your license here.*