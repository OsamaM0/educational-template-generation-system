from typing import Dict, Any, List
from utils.language_detector import LanguageDetector

class PromptBuilder:
    """Builds dynamic prompts based on content and requirements."""
    
    def __init__(self):
        self.language_detector = LanguageDetector()
    
    def build_question_prompt(self, content: str, goals: List[str], 
                            question_counts: Dict[str, int], 
                            difficulty_levels: List[int]) -> Dict[str, str]:
        """
        Build a comprehensive prompt for question generation.
        
        Args:
            content: Educational content
            goals: Learning goals
            question_counts: Number of each question type
            difficulty_levels: Difficulty levels to include
            
        Returns:
            Dictionary with prompt components
        """
        language = self.language_detector.detect_language(content)
        
        prompt_components = {
            "language": language,
            "content_summary": self._summarize_content(content),
            "goals_formatted": self._format_goals(goals, language),
            "question_distribution": self._format_question_distribution(question_counts, language),
            "difficulty_guidance": self._format_difficulty_guidance(difficulty_levels, language)
        }
        
        return prompt_components
    
    def build_worksheet_prompt(self, content: str, goals: List[str]) -> Dict[str, str]:
        """Build prompt for worksheet generation."""
        language = self.language_detector.detect_language(content)
        
        return {
            "language": language,
            "content_summary": self._summarize_content(content),
            "goals_formatted": self._format_goals(goals, language),
            "worksheet_sections": self._get_worksheet_sections(language)
        }
    
    def build_summary_prompt(self, content: str) -> Dict[str, str]:
        """Build prompt for summary generation."""
        language = self.language_detector.detect_language(content)
        
        return {
            "language": language,
            "content_length": len(content.split()),
            "summary_structure": self._get_summary_structure(language)
        }
    
    def _summarize_content(self, content: str, max_words: int = 100) -> str:
        """Create a brief summary of content for prompt context."""
        words = content.split()
        if len(words) <= max_words:
            return content
        
        # Take first portion of content
        summary = " ".join(words[:max_words])
        return summary + "..."
    
    def _format_goals(self, goals: List[str], language: str) -> str:
        """Format learning goals for prompts."""
        if not goals:
            if language == "arabic":
                return "تحقيق أهداف تعليمية عامة مناسبة للمحتوى"
            else:
                return "Achieve general educational objectives appropriate for the content"
        
        if language == "arabic":
            formatted = "الأهداف التعليمية:\n"
        else:
            formatted = "Learning Objectives:\n"
            
        for i, goal in enumerate(goals, 1):
            formatted += f"{i}. {goal}\n"
            
        return formatted.strip()
    
    def _format_question_distribution(self, question_counts: Dict[str, int], language: str) -> str:
        """Format question count requirements."""
        if language == "arabic":
            type_names = {
                "multiple_choice": "أسئلة اختيار من متعدد",
                "short_answer": "أسئلة إجابة قصيرة",
                "complete": "أسئلة إكمال",
                "true_false": "أسئلة صح/خطأ"
            }
            header = "توزيع الأسئلة المطلوب:"
        else:
            type_names = {
                "multiple_choice": "Multiple Choice Questions",
                "short_answer": "Short Answer Questions",
                "complete": "Completion Questions",
                "true_false": "True/False Questions"
            }
            header = "Required Question Distribution:"
        
        formatted = header + "\n"
        for q_type, count in question_counts.items():
            type_name = type_names.get(q_type, q_type)
            formatted += f"- {type_name}: {count}\n"
            
        return formatted.strip()
    
    def _format_difficulty_guidance(self, difficulty_levels: List[int], language: str) -> str:
        """Format difficulty level guidance."""
        if language == "arabic":
            level_names = {1: "سهل", 2: "متوسط", 3: "صعب"}
            header = "مستويات الصعوبة المطلوبة:"
        else:
            level_names = {1: "Easy", 2: "Medium", 3: "Hard"}
            header = "Required Difficulty Levels:"
        
        formatted = header + "\n"
        for level in difficulty_levels:
            level_name = level_names.get(level, str(level))
            formatted += f"- المستوى {level} ({level_name})\n" if language == "arabic" else f"- Level {level} ({level_name})\n"
            
        return formatted.strip()
    
    def _get_worksheet_sections(self, language: str) -> str:
        """Get worksheet section requirements."""
        if language == "arabic":
            return """أقسام ورقة العمل المطلوبة:
1. الأهداف التعليمية
2. التطبيقات العملية
3. المفردات الأساسية
4. إرشادات للمعلم"""
        else:
            return """Required Worksheet Sections:
1. Learning Goals
2. Practical Applications
3. Key Vocabulary
4. Teacher Guidelines"""
    
    def _get_summary_structure(self, language: str) -> str:
        """Get summary structure requirements."""
        if language == "arabic":
            return """هيكل الملخص المطلوب:
1. افتتاحية: مقدمة جذابة
2. خلاصة: النقاط الرئيسية
3. خاتمة: ربط وتلخيص"""
        else:
            return """Required Summary Structure:
1. Opening: Engaging introduction
2. Summary: Key points
3. Ending: Connection and conclusion"""
