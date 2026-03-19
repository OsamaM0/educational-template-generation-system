from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from langchain_openai import ChatOpenAI
from config.settings import Settings

class BaseTemplate(ABC):
    """Abstract base class for all template types."""
    
    def __init__(self, model: Optional[ChatOpenAI] = None):
        """Initialize the template with a language model."""
        self.model = model or ChatOpenAI(
            temperature=Settings.TEMPERATURE,
            model=Settings.NON_MATH_MODEL
        )
        self.language = None
        
    @abstractmethod
    def generate(self, content: str, goals: list = None, **kwargs) -> Dict[str, Any]:
        """
        Generate template content based on input.
        
        Args:
            content: The educational content to base the template on
            goals: Learning goals (optional)
            **kwargs: Additional parameters specific to template type
            
        Returns:
            Dict containing the generated template
        """
        pass
    
    @abstractmethod
    def get_prompt_template(self, language: str) -> str:
        """
        Get the appropriate prompt template for the given language.
        
        Args:
            language: Language code ('arabic' or 'english')
            
        Returns:
            Formatted prompt template string
        """
        pass
    
    def set_language(self, language: str):
        """Set the language for the template."""
        if language in Settings.SUPPORTED_LANGUAGES:
            self.language = language
        else:
            raise ValueError(f"Unsupported language: {language}")
    
    def validate_input(self, content: str, **kwargs) -> bool:
        """Validate input parameters."""
        if not content or not content.strip():
            raise ValueError("Content cannot be empty")
        return True
