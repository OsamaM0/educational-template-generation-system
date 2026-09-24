import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Settings:
    """Configuration settings for the template generation system."""
    
    # OpenRouter Configuration (OpenAI-compatible API)
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
    OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

    # Model routing: math content -> MATH_MODEL, everything else -> NON_MATH_MODEL
    NON_MATH_MODEL = os.getenv("LLM_MODEL_NORMAL", "z-ai/glm-5.3-flash")    # Z.ai: GLM 5.3 Flash
    MATH_MODEL = os.getenv("LLM_MODEL_MATH", "xiaomi/mimo-v2.6-pro")        # Xiaomi: MiMo-V2.6-Pro
    TEMPERATURE = float(os.getenv("TEMPERATURE", "0.7"))
    
    # Language Configuration
    SUPPORTED_LANGUAGES = ["arabic", "english"]
    DEFAULT_LANGUAGE = "arabic"
    
    # Question Configuration
    DEFAULT_QUESTION_COUNTS = {
        "multiple_choice": 5,
        "short_answer": 3,
        "complete": 2,
        "true_false": 3
    }
    
    DIFFICULTY_LEVELS = [1, 2, 3]  # Easy, Medium, Hard
    
    # Template Configuration
    AVAILABLE_TEMPLATES = ["questions", "worksheet", "summary", "goal_based_questions", "mindmap"]

    # Mind Map Configuration
    MINDMAP_ENHANCED_THINKING = os.getenv("MINDMAP_ENHANCED_THINKING", "true").lower() in ["1", "true", "yes"]
    MINDMAP_MAX_NODES = int(os.getenv("MINDMAP_MAX_NODES", "120"))
    # Multi-pass generation to cover long content
    MINDMAP_MULTI_PASS = os.getenv("MINDMAP_MULTI_PASS", "true").lower() in ["1", "true", "yes"]
    MINDMAP_CHUNK_SIZE_CHARS = int(os.getenv("MINDMAP_CHUNK_SIZE_CHARS", "1800"))
    MINDMAP_CHUNK_OVERLAP_CHARS = int(os.getenv("MINDMAP_CHUNK_OVERLAP_CHARS", "250"))
    # Deduplicate nodes across chunks using normalized text per parent
    MINDMAP_DEDUPLICATE_NODES = os.getenv("MINDMAP_DEDUPLICATE_NODES", "true").lower() in ["1", "true", "yes"]
    # Maximum allowed depth (root=0). Set to -1 for unlimited depth.
    MINDMAP_MAX_DEPTH = int(os.getenv("MINDMAP_MAX_DEPTH", "-1"))
    # Remove / ignore example or narrative style nodes
    MINDMAP_EXCLUDE_EXAMPLES = os.getenv("MINDMAP_EXCLUDE_EXAMPLES", "true").lower() in ["1", "true", "yes"]
    # Colors by depth (0=root, 1=main branches, 2=subtopics, 3+ deeper)
    MINDMAP_COLORS = [
        "gold",            # root
        "turquoise",         # depth 1
        "lavender",    # depth 2
        "aqua",   # depth 3
        "lightcoral",      # depth 4
        "lightsteelblue",  # depth 5
        "plum",            # depth 6
        "lightpink"        # depth 7+
    ]
    
    @classmethod
    def validate_config(cls):
        """Validate that required configuration is present."""
        if not cls.OPENROUTER_API_KEY:
            raise ValueError("OPENROUTER_API_KEY environment variable is required")
        return True
