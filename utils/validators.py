from typing import Dict, Any, List
from config.settings import Settings

class InputValidator:
    """Utility class for validating user inputs."""
    
    @staticmethod
    def validate_template_type(template_type: str) -> bool:
        """Validate template type."""
        if template_type not in Settings.AVAILABLE_TEMPLATES:
            raise ValueError(f"Invalid template type: {template_type}. "
                           f"Available types: {Settings.AVAILABLE_TEMPLATES}")
        return True
    
    @staticmethod
    def validate_content(content: str) -> bool:
        """Validate content input."""
        if not content or not content.strip():
            raise ValueError("Content cannot be empty")
        
        if len(content.strip()) < 10:
            raise ValueError("Content is too short. Please provide more substantial content.")
            
        return True
    
    @staticmethod
    def validate_goals(goals: List[str]) -> bool:
        """Validate learning goals."""
        if goals is None:
            return True
            
        if not isinstance(goals, list):
            raise ValueError("Goals must be a list of strings")
            
        if not goals:
            return True
            
        for goal in goals:
            if not isinstance(goal, str) or not goal.strip():
                raise ValueError("Each goal must be a non-empty string")
                
        return True
    
    @staticmethod
    def validate_question_counts(question_counts: Dict[str, int]) -> bool:
        """Validate question counts configuration."""
        if question_counts is None:
            return True
            
        valid_types = ["multiple_choice", "short_answer", "complete", "true_false"]
        
        for q_type, count in question_counts.items():
            if q_type not in valid_types:
                raise ValueError(f"Invalid question type: {q_type}. "
                               f"Valid types: {valid_types}")
            
            if not isinstance(count, int) or count < 0:
                raise ValueError(f"Question count for {q_type} must be a non-negative integer")
                
            if count > 20:
                raise ValueError(f"Question count for {q_type} exceeds maximum (20)")
                
        return True
    
    @staticmethod
    def validate_difficulty_levels(difficulty_levels: List[int]) -> bool:
        """Validate difficulty levels."""
        if difficulty_levels is None:
            return True
            
        if not isinstance(difficulty_levels, list):
            raise ValueError("Difficulty levels must be a list of integers")
            
        for level in difficulty_levels:
            if not isinstance(level, int) or level not in [1, 2, 3]:
                raise ValueError("Difficulty levels must be integers between 1 and 3")
                
        return True
