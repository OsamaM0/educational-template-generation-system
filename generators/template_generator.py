from typing import Dict, Any, List, Optional
from langchain_openai import ChatOpenAI

from config.settings import Settings
from processors.content_processor import ContentProcessor
from template.question_template import QuestionTemplate
from template.worksheet_template import WorksheetTemplate
from template.summary_template import SummaryTemplate
from template.goal_based_template import GoalBasedTemplate
from template.mindmap_template import MindMapTemplate
from utils.validators import InputValidator
from utils.language_detector import LanguageDetector

class TemplateGenerator:
    """Main orchestrator for generating educational templates."""
    
    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        """
        Initialize the template generator.
        
        Args:
            api_key: OpenAI API key (optional, can use environment variable)
            model_name: Model name to use (optional, uses settings default)
        """
        # Validate configuration
        Settings.validate_config()
        
        # Initialize language model
        self.model = ChatOpenAI(
            api_key=api_key or Settings.OPENAI_API_KEY,
            model=model_name or Settings.NON_MATH_MODEL,
            temperature=Settings.TEMPERATURE
        )
        
    # Initialize components (share the LLM with the content processor)
        self.content_processor = ContentProcessor(self.model)
        self.language_detector = LanguageDetector()
        self.validator = InputValidator()
        
        # Initialize template instances
        self.templates = {
            "questions": QuestionTemplate(self.model),
            "worksheet": WorksheetTemplate(self.model),
            "summary": SummaryTemplate(self.model),
            "goal_based_questions": GoalBasedTemplate(self.model),
            "mindmap": MindMapTemplate(self.model)
        }

    def _select_model_name(self, content_analysis: Dict[str, Any]) -> str:
        """Choose model name based on whether the content is mathematical."""
        try:
            is_math = bool(
                content_analysis.get("is_mathematical")
                or content_analysis.get("subject_area") == "mathematics"
                or content_analysis.get("has_equations")
            )
        except Exception:
            is_math = False
        return Settings.MATH_MODEL if is_math else Settings.NON_MATH_MODEL

    def _apply_model_to_components(self, model_name: str):
        """Instantiate a ChatOpenAI with the given model and apply it to all components."""
        new_model = ChatOpenAI(
            api_key=Settings.OPENAI_API_KEY,
            model=model_name,
            temperature=Settings.TEMPERATURE
        )
        # Update main reference
        self.model = new_model
        # Update content processor for future analyses
        try:
            self.content_processor.model = new_model
        except Exception:
            pass
        # Update templates and any nested templates/tools
        for key, tpl in self.templates.items():
            try:
                tpl.model = new_model
                # If question template, reset math agent so it rebinds to new model lazily
                if isinstance(tpl, QuestionTemplate):
                    try:
                        tpl.math_agent = None
                    except Exception:
                        pass
                # GoalBasedTemplate holds nested templates
                if isinstance(tpl, GoalBasedTemplate):
                    try:
                        tpl.question_template.model = new_model
                        # reset nested question template math agent as well
                        try:
                            tpl.question_template.math_agent = None
                        except Exception:
                            pass
                        tpl.worksheet_template.model = new_model
                    except Exception:
                        pass
                # MindMapTemplate is straightforward
                if isinstance(tpl, MindMapTemplate):
                    try:
                        tpl.model = new_model
                    except Exception:
                        pass
            except Exception:
                pass
    
    def generate_template(self, template_type: str, content: str, 
                         goals: Optional[List[str]] = None, **kwargs) -> Dict[str, Any]:
        """
        Generate a template based on the specified type and content.
        
        Args:
            template_type: Type of template ('questions', 'worksheet', 'summary', 'goal_based_questions')
            content: Educational content
            goals: Learning goals (optional)
            **kwargs: Additional parameters specific to template type
            
        Returns:
            Generated template as dictionary
        """
        # Validate inputs
        self.validator.validate_template_type(template_type)
        self.validator.validate_content(content)
        self.validator.validate_goals(goals)
        
        # Apply defaults early for questions templates so validation never sees None
        if template_type in ["questions", "goal_based_questions"]:
            if kwargs.get("question_counts") is None:
                kwargs["question_counts"] = Settings.DEFAULT_QUESTION_COUNTS
            if kwargs.get("difficulty_levels") is None:
                kwargs["difficulty_levels"] = Settings.DIFFICULTY_LEVELS
            # Now validate
            self.validator.validate_question_counts(kwargs.get("question_counts"))
            self.validator.validate_difficulty_levels(kwargs.get("difficulty_levels"))
        
        # Process content
        processed_content = self.content_processor.preprocess_content(content)
        content_analysis = self.content_processor.analyze_content(processed_content)
        
        # Detect language and set template language
        detected_language = content_analysis["language"]
        template = self.templates[template_type]
        template.set_language(detected_language)

        # Dynamically select model based on math detection and apply it
        selected_model_name = self._select_model_name(content_analysis)
        self._apply_model_to_components(selected_model_name)

        # Enforce difficulty levels based on math/non-math for question generation
        if template_type in ["questions", "goal_based_questions"]:
            is_math = bool(
                content_analysis.get("is_mathematical")
                or content_analysis.get("subject_area") == "mathematics"
                or content_analysis.get("has_equations")
            )
            effective_difficulties: List[int] = [1] if is_math else [1, 2]
            kwargs["difficulty_levels"] = effective_difficulties
        
        # Generate template
        try:
            if template_type == "goal_based_questions":
                result = template.generate_goal_based_questions(
                    processed_content, 
                    goals, 
                    content_analysis=content_analysis,
                    **kwargs
                )
            else:
                result = template.generate(
                    processed_content, 
                    goals, 
                    content_analysis=content_analysis,
                    **kwargs
                )
            
            # Add metadata
            result["_metadata"] = {
                "template_type": template_type,
                "language": detected_language,
                "content_analysis": content_analysis,
                "selected_model": selected_model_name,
                "generation_params": {
                    "goals": goals,
                    **kwargs
                }
            }
            
            return result
            
        except Exception as e:
            # Provide richer context, especially for common NoneType attribute errors
            err_type = type(e).__name__
            hint = ""
            if "NoneType" in err_type or "'NoneType' object has no attribute" in str(e):
                hint = (" | Hint: A sub-template likely returned None (e.g., worksheet while extracting goals). "
                        "Defensive fallbacks were added; please retry. If persists, inspect worksheet_template.generate().")
            raise RuntimeError(f"Template generation failed: {err_type}: {str(e)}{hint}") from e
    
    def generate_question_bank(self, content: str, goals: Optional[List[str]] = None,
                              question_counts: Optional[Dict[str, int]] = None,
                              difficulty_levels: Optional[List[int]] = None) -> Dict[str, Any]:
        """
        Convenience method for generating question banks.
        
        Args:
            content: Educational content
            goals: Learning goals
            question_counts: Number of each question type to generate
            difficulty_levels: Difficulty levels to include
            
        Returns:
            Generated question bank
        """
        return self.generate_template(
            template_type="questions",
            content=content,
            goals=goals,
            question_counts=question_counts or Settings.DEFAULT_QUESTION_COUNTS,
            difficulty_levels=difficulty_levels or Settings.DIFFICULTY_LEVELS
        )
    
    def generate_goal_based_questions(self, content: str, goals: Optional[List[str]] = None,
                                    question_counts: Optional[Dict[str, int]] = None,
                                    difficulty_levels: Optional[List[int]] = None) -> Dict[str, Any]:
        """
        Convenience method for generating goal-based question banks.
        
        Args:
            content: Educational content
            goals: Learning goals (optional - will be generated if not provided)
            question_counts: Number of each question type to generate
            difficulty_levels: Difficulty levels to include
            
        Returns:
            Generated goal-based question bank with clear goal-question mapping
        """
        return self.generate_template(
            template_type="goal_based_questions",
            content=content,
            goals=goals,
            question_counts=question_counts or Settings.DEFAULT_QUESTION_COUNTS,
            difficulty_levels=difficulty_levels or Settings.DIFFICULTY_LEVELS
        )
    
    def generate_worksheet(self, content: str, goals: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Convenience method for generating worksheets.
        
        Args:
            content: Educational content
            goals: Learning goals
            
        Returns:
            Generated worksheet
        """
        return self.generate_template(
            template_type="worksheet",
            content=content,
            goals=goals
        )
    
    def generate_summary(self, content: str) -> Dict[str, Any]:
        """
        Convenience method for generating summaries.
        
        Args:
            content: Educational content
            
        Returns:
            Generated summary
        """
        return self.generate_template(
            template_type="summary",
            content=content
        )
    
    def generate_mindmap(self, content: str) -> Dict[str, Any]:
        """
        Convenience method for generating mind maps.
        
        Args:
            content: Educational content
            
        Returns:
            Generated mind map in GoJS format
        """
        return self.generate_template(
            template_type="mindmap",
            content=content
        )
    
    def get_supported_templates(self) -> List[str]:
        """Get list of supported template types."""
        return list(self.templates.keys())
    
    def get_content_analysis(self, content: str) -> Dict[str, Any]:
        """Get analysis of content without generating templates."""
        processed_content = self.content_processor.preprocess_content(content)
        return self.content_processor.analyze_content(processed_content)
