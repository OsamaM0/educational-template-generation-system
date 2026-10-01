"""Every setting comes from the environment. No credential has a default."""
import os
from dataclasses import dataclass, field

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:          # python-dotenv is optional
    pass


def _env(name, default=None):
    v = os.getenv(name)
    return v if v not in (None, "") else default


@dataclass
class Settings:
    # --- content ------------------------------------------------------------
    # Summary text and worksheet goals live beside the question bank in Mongo.
    content_max_chars: int = field(default_factory=lambda: int(_env("KP_CONTENT_MAX_CHARS", "12000")))

    # --- mongo ----------------------------------------------------------------
    mongo_uri: str = field(default_factory=lambda: _env("KP_MONGO_URI") or _env("MONGODB_URI"))
    mongo_db: str = field(default_factory=lambda: _env("KP_MONGO_DB", "ai"))
    col_questions: str = field(default_factory=lambda: _env("KP_COL_QUESTIONS", "questions"))
    col_worksheets: str = field(default_factory=lambda: _env("KP_COL_WORKSHEETS", "worksheets"))
    col_summaries: str = field(default_factory=lambda: _env("KP_COL_SUMMARIES", "summaries"))
    col_knowledge: str = field(default_factory=lambda: _env("KP_COL_KNOWLEDGE", "knowledge_productions"))

    # --- OpenRouter through the OpenAI-compatible interface -------------------
    # OPENAI_* names remain fallbacks so existing deployments keep working.
    llm_api_key: str = field(default_factory=lambda: _env("OPENROUTER_API_KEY", _env("OPENAI_API_KEY")))
    llm_base_url: str = field(default_factory=lambda: _env(
        "OPENROUTER_BASE_URL", _env("OPENAI_BASE_URL", _env("OPENAI_API_BASE", "https://openrouter.ai/api/v1"))))
    # OpenRouter recommends these attribution headers.
    llm_referer: str = field(default_factory=lambda: _env("OPENROUTER_REFERER", _env("OPENAI_REFERER")))
    llm_title: str = field(default_factory=lambda: _env("OPENROUTER_TITLE", _env("OPENAI_TITLE", "Edu Knowledge Production")))
    # Steps A (topics) and B (project) are the creative, constraint-heavy ones.
    model_creative: str = field(default_factory=lambda: _env(
        "KP_MODEL_CREATIVE", _env("LLM_MODEL_MATH", _env("OPENAI_MODEL_MATH", "xiaomi/mimo-v2.6-pro"))))
    # Step C (linking questions) is mechanical and repaired by the validator.
    model_link: str = field(default_factory=lambda: _env(
        "KP_MODEL_LINK", _env("LLM_MODEL_NORMAL", _env("OPENAI_MODEL_NORMAL", "z-ai/glm-5.3-flash"))))
    price_model_math: str = field(default_factory=lambda: _env("LLM_MODEL_MATH", "xiaomi/mimo-v2.6-pro"))
    price_model_normal: str = field(default_factory=lambda: _env("LLM_MODEL_NORMAL", "z-ai/glm-5.3-flash"))
    temperature: float = field(default_factory=lambda: float(_env("TEMPERATURE", "0.7")))
    reasoning_effort: str = field(default_factory=lambda: _env("KP_REASONING_EFFORT", "medium"))
    # Moderate hidden-token use so structured replies have room to finish.
    # Use "provider" to restore a model's default reasoning behavior.
    creative_reasoning_effort: str = field(default_factory=lambda: _env("KP_CREATIVE_REASONING_EFFORT", "low"))
    # Question display adaptation needs a smaller reasoning budget than authorship.
    link_reasoning_effort: str = field(default_factory=lambda: _env("KP_LINK_REASONING_EFFORT", "low"))
    max_repairs: int = field(default_factory=lambda: int(_env("KP_MAX_REPAIRS", "2")))
    request_timeout: float = field(default_factory=lambda: float(_env("KP_REQUEST_TIMEOUT", "180")))
    # Cap on output tokens per call. The SDK defaults to 16384, which OpenRouter
    # bills against your balance upfront. 0 = leave unset (SDK default).
    max_tokens: int = field(default_factory=lambda: int(_env("KP_MAX_TOKENS", "6000")))
    # One bounded retry when a reply is truncated; set equal to max_tokens to disable.
    max_retry_tokens: int = field(default_factory=lambda: int(_env("KP_MAX_RETRY_TOKENS", "12000")))
    # USD per 1M tokens. The shared prices remain fallbacks for older deployments.
    price_in: float = field(default_factory=lambda: float(_env("KP_PRICE_INPUT_PER_M", "0")))
    price_cached: float | None = field(default_factory=lambda: (
        float(_env("KP_PRICE_CACHED_PER_M")) if _env("KP_PRICE_CACHED_PER_M") is not None else None))
    price_out: float = field(default_factory=lambda: float(_env("KP_PRICE_OUTPUT_PER_M", "0")))
    price_math_in: float = field(default_factory=lambda: float(_env(
        "LLM_MODEL_MATH_INPUT_1M", _env("KP_PRICE_INPUT_PER_M", "0"))))
    price_math_out: float = field(default_factory=lambda: float(_env(
        "LLM_MODEL_MATH_OUTPUT_1M", _env("KP_PRICE_OUTPUT_PER_M", "0"))))
    price_normal_in: float = field(default_factory=lambda: float(_env(
        "LLM_MODEL_NORMAL_INPUT_1M", _env("KP_PRICE_INPUT_PER_M", "0"))))
    price_normal_out: float = field(default_factory=lambda: float(_env(
        "LLM_MODEL_NORMAL_OUTPUT_1M", _env("KP_PRICE_OUTPUT_PER_M", "0"))))

    # Optional practice cap for new resources; zero questions is always valid.
    max_questions: int = field(default_factory=lambda: int(_env("KP_MAX_QUESTIONS", "3")))
    # Legacy replay mechanics only; new production does not require stages.
    min_stages: int = 4
    max_stages: int = 8
    edition_year: int = field(default_factory=lambda: int(_env("KP_EDITION_YEAR", "2026")))

    def prices_for_model(self, model):
        """Return input, cached input, and output prices for the model used."""
        if model == self.price_model_math:
            incoming, outgoing = self.price_math_in, self.price_math_out
        elif model == self.price_model_normal:
            incoming, outgoing = self.price_normal_in, self.price_normal_out
        else:
            incoming, outgoing = self.price_in, self.price_out
        cached = incoming if self.price_cached is None else self.price_cached
        return incoming, cached, outgoing

    # Python-level compatibility for integrations that accessed the previous
    # attribute names directly. New code should use llm_*.
    @property
    def openai_api_key(self):
        return self.llm_api_key

    @openai_api_key.setter
    def openai_api_key(self, value):
        self.llm_api_key = value

    @property
    def openai_base_url(self):
        return self.llm_base_url

    @openai_base_url.setter
    def openai_base_url(self, value):
        self.llm_base_url = value

    @property
    def openai_referer(self):
        return self.llm_referer

    @openai_referer.setter
    def openai_referer(self, value):
        self.llm_referer = value

    @property
    def openai_title(self):
        return self.llm_title

    @openai_title.setter
    def openai_title(self, value):
        self.llm_title = value
