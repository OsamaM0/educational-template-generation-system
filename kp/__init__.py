"""kp — knowledge production (الإنتاج المعرفي) generator.

lesson id → summary + worksheet goals + questions (MongoDB ``ai``)
→ each goal becomes a titled topic with selected questions → OpenRouter builds one product per topic through the OpenAI-compatible API → validated
→ stored in ai.knowledge_productions, which the renderer reads directly.
"""
PROMPT_VERSION = "kp-prompts-6-goal-first-production"
SCHEMA_VERSION = "3.0.0"
