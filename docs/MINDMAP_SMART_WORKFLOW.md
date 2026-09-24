# Mind Map Smart Workflow

This document details the two-phase approach, configuration, prompts, and post-processing used by `MindMapTemplate`.

## Why two phases?

- Let the LLM focus on content fidelity and structure (topic hierarchy)
- Apply deterministic, consistent visuals and constraints in code
- Reduce costs and improve consistency across maps

## Phase 1 — AI generation

The LLM returns:
- `key` (unique integer identifiers)
- `parent` (parent node key; `None` for root)
- `text` (short noun phrases)
- `loc` (root only, optional)

It does NOT need to set `brush` or `dir` — these are set later.

### Language-aware prompts

Prompts live in:
- `prompts/arabic/mindmap_prompts.py`
- `prompts/english/mindmap_prompts.py`

They instruct the model to:
- Produce valid JSON only (no Markdown/code fences)
- Keep node text concise (~≤6 words when possible)
- Focus strictly on relevant concepts
- Avoid examples/stories/scenarios unless they are truly central
- Maintain a hierarchical tree suitable for GoJS

### Enhanced thinking (optional)

- When `Settings.MINDMAP_ENHANCED_THINKING` is true and a planning prompt exists, the system runs a lightweight “planning phase” before the main generation to improve structure.

## Phase 2 — System enhancement (post-processing)

Implemented by `utils/mindmap_postprocess.py` and invoked by `MindMapTemplate`:

- Enforces `class = "go.TreeModel"`
- Colors by depth: `Settings.MINDMAP_COLORS`
- Direction balancing: distributes main branches left/right by subtree weight and propagates `dir` down the subtree
- Pruning:
  - Depth limit via `Settings.MINDMAP_MAX_DEPTH` (root=0)
  - Example/story node filtering via `Settings.MINDMAP_EXCLUDE_EXAMPLES`
- Root location: ensures root has `loc: "0 0"`
- Deduplication in merges: repeated `text` under the same parent can be dropped when `Settings.MINDMAP_DEDUPLICATE_NODES` is enabled
- Max nodes: enforced by `Settings.MINDMAP_MAX_NODES`

The post-processor is idempotent and safe — running multiple times yields stable results.

## Multi-pass generation for long content

When `Settings.MINDMAP_MULTI_PASS` is enabled and content exceeds `Settings.MINDMAP_CHUNK_SIZE_CHARS`:
- The content is split into overlapping chunks (`MINDMAP_CHUNK_OVERLAP_CHARS`)
- A partial mind map is generated for each chunk
- A synthetic root is introduced and partial roots are attached as main branches
- Deduplication by parent+normalized text reduces duplicates
- The merged map is post-processed as above

This enables wide coverage without overloading the model context.

## Output format (GoJS TreeModel)

```json
{
  "class": "go.TreeModel",
  "nodeDataArray": [
    {"key": 0, "text": "Main Topic", "loc": "0 0"},
    {"key": 1, "parent": 0, "text": "Subtopic", "brush": "turquoise", "dir": "right"}
  ]
}
```

## Configuration reference

Environment variables (via `Settings`):

- `MINDMAP_ENHANCED_THINKING` (bool)
- `MINDMAP_MAX_NODES` (int)
- `MINDMAP_MULTI_PASS` (bool)
- `MINDMAP_CHUNK_SIZE_CHARS` (int)
- `MINDMAP_CHUNK_OVERLAP_CHARS` (int)
- `MINDMAP_DEDUPLICATE_NODES` (bool)
- `MINDMAP_MAX_DEPTH` (int; -1 disables pruning)
- `MINDMAP_EXCLUDE_EXAMPLES` (bool)
- `MINDMAP_COLORS` (array of CSS color names)

## Tips

- Prefer concise node text; long sentences clutter the canvas
- Use 4–7 main branches where possible to keep a balanced visual
- If your content contains many examples/stories, keep `MINDMAP_EXCLUDE_EXAMPLES=true` for a more professional map

## Testing

- `tests/test_mindmap_parsing.py` verifies JSON cleaning/repair
- For end-to-end checks, use CLI in `main.py`:
  - `python main.py mindmap content.txt`

