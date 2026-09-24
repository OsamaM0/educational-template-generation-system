ENGLISH_MINDMAP_PROMPTS = {
    "main_template": """You are an educational structuring expert. Produce a professional, concise mind map (not verbose) in GoJS-compatible JSON from the provided lesson content.

⚠️ CRITICAL: Output ONLY valid JSON. No explanations, no markdown, no code fences. Begin with {{ and end with }}.

Objective: Highlight only core conceptual pillars directly relevant to the lesson title. Ignore and exclude:
- Lengthy narrative examples, stories, scenarios
- Repetitive phrasing or filler
- Side topics that don't advance the central concept
- Minor statistics, external references, anecdotal context

Depth Policy: Maximum hierarchy depth = 3 levels (root + level-1 + optional level-2). Do NOT create deeper chains. Drop overly granular fragments.

Balance: Provide 4–7 main branches (children of root) when content allows. Each main branch may have up to 2–4 concise subnodes.

Node Text Rules:
- Short (≈ up to 6 words)
- Noun phrase or concise concept label (no full sentences)
- No numbering, bullets, decorative symbols, examples

Filter out any node whose text would revolve around: example, for example, e.g., case study, story, scenario, illustration, experiment (and their paraphrases).

Minimal structural example (format only):
{{
    "class": "go.TreeModel",
    "nodeDataArray": [
        {{"key":0, "text":"Main Topic", "loc":"0 0"}},
        {{"key":1, "parent":0, "text":"Core Axis"}},
        {{"key":11, "parent":1, "text":"Sub Idea"}},
        {{"key":2, "parent":0, "text":"Another Axis"}}
    ]
}}

Concise Instructions:
1. Extract only essential, title-aligned conceptual groupings.
2. Summarize—don't reproduce prose or examples.
3. Enforce depth limit (no grandchildren of level-2).
4. Keep within branch and sub-branch count limits.
5. Fields allowed: key, parent, text, loc (root only loc = "0 0").
6. Do NOT add brush or dir (system will append them).
7. Return valid JSON only.

Analyze the text and build the map under these constraints:
{context}"""
    ,
    "planning_template": """First produce a brief planning outline (not JSON) including:
1) Root title.
2) 4–7 logically ordered main branches (short phrases).
3) For each branch: 2–4 key sub-concepts (no examples, no stories).
4) Confirmation that no depth will exceed level-2.

Then output ONLY the final GoJS JSON:
- Unique numeric keys
- parent = null for root only
- loc only for root = "0 0"
- Enforce depth limit (root -> branch -> sub)
- No brush or dir

Text:
{context}
"""
}
