# Template Generation System — Architecture Overview

This document explains how the system is structured, how data flows through it, and how to extend it safely. It complements the top-level README.

## High-level goals

- Generate educational artifacts from textual content:
  - Question banks (with goal-based mode)
  - Worksheets
  - Summaries
  - Mind maps (GoJS-compatible JSON)
- Provide both single-run CLI and bulk-processing modes
- Store results in MongoDB for later retrieval/analysis

## Components and responsibilities

- Entry points
  - `main.py`: Single-run CLI. Reads content from a file, invokes `TemplateGenerator`, prints and optionally saves JSON.
  - `bulk_generator.py`: Orchestrates fetching many documents from an API and produces templates in bulk, persisting to MongoDB.

- Orchestrator
  - `generators/template_generator.py` (class `TemplateGenerator`):
    - Validates config (`Settings.validate_config()`)
    - Holds a shared LLM client (`langchain_openai.ChatOpenAI`)
    - Shares LLM with the `ContentProcessor`
    - Instantiates templates for all supported types
    - Performs content preprocessing and analysis
    - Auto-detects language and sets it on the chosen template
    - Dynamically selects an LLM model (math vs. non-math) and reapplies it to all subcomponents
    - Provides convenience wrappers (`generate_question_bank`, `generate_goal_based_questions`, `generate_worksheet`, `generate_summary`, `generate_mindmap`)

- Content analysis
  - `processors/content_processor.py` (class `ContentProcessor`):
    - Preprocesses content (whitespace normalization, encoding)
    - Uses LLM to analyze the content and produce:
      - language, complexity, subject area, key topics, math signals, etc.
    - Can generate learning goals when not provided, in Arabic or English

- Templates (all extend `template/base_template.py`):
  - `template/question_template.py` (`QuestionTemplate`):
    - Generates question banks
    - Enables enhanced thinking/math reasoning when math content is detected
    - Provides normalization for numeric formatting and optional worked-solution metadata
  - `template/goal_based_template.py` (`GoalBasedTemplate`):
    - Wraps goal-first workflow
    - If goals are missing, uses `ContentProcessor.generate_learning_goals`
    - Produces both a goal-oriented structure (goals, mapping, questions_by_goal) and a backward-compatible flattened structure
  - `template/worksheet_template.py` (`WorksheetTemplate`):
    - Creates classroom-friendly worksheet sections (goals, applications, vocabulary, teacher guidelines)
  - `template/summary_template.py` (`SummaryTemplate`):
    - Produces opening/summary/ending
  - `template/mindmap_template.py` (`MindMapTemplate`):
    - Generates a GoJS-compatible JSON mind map
    - Supports single-pass and multi-pass (chunk + merge) modes
    - Defers color/direction/depth rules to a shared post-processor

- Mind map post-processing
  - `utils/mindmap_postprocess.py`:
    - Adds/normalizes `brush` (color by depth) and `dir` (balanced left/right), ensures root `loc`
    - Prunes by depth (`MINDMAP_MAX_DEPTH`) and filters example/story nodes when enabled
    - Deduplicates repeated nodes under the same parent (in multi-pass merges)

- Data clients
  - `clients/api_client.py` (`DocumentAPIClient`): Fetches paginated documents and individual documents by UUID.
  - `clients/mongo_client.py` (`MongoDBClient`): Stores results in `ai.{questions,worksheets,summaries,mindmaps}`; reads lesson goals from `ien.lessonplangoals`.

- Batch processing
  - `processors/batch_processor.py` (`BatchProcessor`):
    - Drives per-document generation across template types
    - Pulls learning goals (DB first; AI-generated fallback)
    - Persists results; tracks per-type success/failure statistics

- Configuration
  - `config/settings.py` (`Settings`):
    - OpenAI model, temperature, language defaults
    - Question defaults and difficulty levels
    - Mind map parameters (multi-pass, chunk size, colors, pruning, exclusion)

- Utilities
  - `utils/language_detector.py`, `utils/validators.py`: Language detection and validation helpers

## Data flow (single-run)

1. CLI (`main.py`) loads text content
2. `TemplateGenerator.generate_template()`
   - Validates inputs
   - Preprocesses and analyzes content (`ContentProcessor`)
   - Sets template language and chooses LLM model
   - Invokes the template’s `generate()` (or goal-based wrapper)
   - Returns JSON + `_metadata`
3. CLI prints result and/or saves JSON

## Data flow (bulk)

1. `bulk_generator.py` initializes `DocumentAPIClient`, `MongoDBClient`, `TemplateGenerator`
2. `BatchProcessor.process_all_documents()`
   - Paginates over documents
   - For each document: fetches goals; if absent, generates them via `ContentProcessor`
   - Generates selected template types; stores results in MongoDB

## Mind map generation notes

- The LLM focuses on content structure: keys, parent, text (root may include `loc`).
- Post-processing enforces style and constraints (colors, left/right balance, depth, pruning, dedup).
- Multi-pass mode splits content, generates partial maps, merges, and then post-processes.
- Output format is GoJS-ready: `{ "class": "go.TreeModel", "nodeDataArray": [...] }`.

See docs/MINDMAP_SMART_WORKFLOW.md for prompts, parameters, and post-processing details.

## Error handling and resilience

- Network/API retries: `clients/api_client.py` uses `tenacity` for transient errors.
- Safer JSON parsing for mind maps via `json_repair` and fallbacks.
- Goal generation has LLM-based and heuristic fallbacks.
- Bulk runner has dry-run mode and per-step exceptions with counters.

## Extending the system

- Add a new template:
  1. Create `template/<new>_template.py` extending `BaseTemplate` with `generate()` and `get_prompt_template()`
  2. Register it inside `TemplateGenerator.__init__` under `self.templates`
  3. Add prompts in `prompts/<lang>/<new>_prompts.py`
  4. Wire any new models or validators if needed

- Add a new storage target:
  - Extend `MongoDBClient` with a new `store_*` method and call it from `BatchProcessor`.

- Support additional languages:
  - Add prompt files and update `Settings.SUPPORTED_LANGUAGES`
  - Ensure `LanguageDetector` can detect it or add a configuration switch

## Contracts (I/O shapes)

- Question bank (traditional): keys `multiple_choice`, `short_answer`, `complete`, `true_false`
- Goal-based questions: additional keys `learning_goals`, `goal_question_mapping`, `questions_by_goal`, `_goal_based_metadata`
- Worksheet: keys `goals`, `applications`, `vocabulary`, `teacher_guidelines`
- Summary: keys `opening`, `summary`, `ending`
- Mind map: keys `class`, `nodeDataArray[]` with nodes having `key`, `text`, optional `parent`, `brush`, `dir`, `loc`

## Quality gates

- Unit tests: `tests/test_mindmap_parsing.py` validates JSON repair/clean
- Run demos under `example/` to sanity-check end-to-end behaviors

