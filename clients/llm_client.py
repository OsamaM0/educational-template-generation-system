"""
Chat model factory routed through OpenRouter.

Every LLM call in the pipeline (analysis, goals, summaries, worksheets,
questions, mind maps) goes through `create_chat_model` so the provider,
credentials and model routing live in a single place.

Model routing:
- Mathematical content  -> Settings.MATH_MODEL      (Xiaomi: MiMo-V2.6-Pro)
- Everything else       -> Settings.NON_MATH_MODEL  (Z.ai: GLM 5.3 Flash)
"""
from typing import Optional

from langchain_openai import ChatOpenAI

from config.settings import Settings


def create_chat_model(
    model_name: Optional[str] = None,
    temperature: Optional[float] = None,
    api_key: Optional[str] = None,
) -> ChatOpenAI:
    """Create an OpenAI-compatible chat client pointing at OpenRouter.

    Args:
        model_name: OpenRouter model id (defaults to Settings.NON_MATH_MODEL)
        temperature: Sampling temperature (defaults to Settings.TEMPERATURE)
        api_key: OpenRouter API key (defaults to Settings.OPENROUTER_API_KEY)

    Returns:
        ChatOpenAI client configured for OpenRouter
    """
    return ChatOpenAI(
        api_key=api_key or Settings.OPENROUTER_API_KEY,
        base_url=Settings.OPENROUTER_BASE_URL,
        model=model_name or Settings.NON_MATH_MODEL,
        temperature=Settings.TEMPERATURE if temperature is None else temperature,
    )
