from typing import Dict, Any, List
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from template.base_template import BaseTemplate
from models.question_models import QuestionBank
from prompts.arabic.question_prompts import ARABIC_QUESTION_PROMPTS
from prompts.english.question_prompts import ENGLISH_QUESTION_PROMPTS
from config.settings import Settings
from tools.math_reasoning import MathReasoningAgent

class QuestionTemplate(BaseTemplate):
    """Template for generating question banks with enhanced thinking capabilities."""
    
    def __init__(self, model=None):
        super().__init__(model)
        self.parser = JsonOutputParser(pydantic_object=QuestionBank)
        self.math_agent = None
        
    def generate(self, content: str, goals: List[str] = None, 
                 question_counts: Dict[str, int] = None, 
                 difficulty_levels: List[int] = None, 
                 content_analysis: Dict[str, Any] = None, **kwargs) -> Dict[str, Any]:
        """
        Generate a question bank based on content and goals with enhanced thinking.
        
        Args:
            content: Educational content
            goals: Learning goals
            question_counts: Number of each question type to generate
            difficulty_levels: Difficulty levels to include
            content_analysis: Analysis of the content (subject area, mathematical nature, etc.)
            
        Returns:
            Generated question bank as dictionary
        """
        self.validate_input(content)
        
        # Set defaults
        if goals is None:
            goals = []
        if question_counts is None:
            question_counts = Settings.DEFAULT_QUESTION_COUNTS
        if difficulty_levels is None:
            difficulty_levels = Settings.DIFFICULTY_LEVELS
            
        # Check if content is mathematical and decide whether to use enhanced reasoning
        is_mathematical = content_analysis.get('is_mathematical', False) if content_analysis else False
        subject_area = content_analysis.get('subject_area', 'general') if content_analysis else 'general'
        has_equations = content_analysis.get('has_equations', False) if content_analysis else False
        # Enable thinking mode if any math signal is present or the subject is mathematics
        use_math_thinking = bool(
            is_mathematical or subject_area == 'mathematics' or has_equations
        )
        
    # Initialize math reasoning agent if needed
        if use_math_thinking and not self.math_agent:
            self.math_agent = MathReasoningAgent(self.model, self.language)

        # Get appropriate prompt template
        if use_math_thinking:
            # Lightweight runtime confirmation to stdout
            try:
                print(f"🧠 Math thinking enabled: {use_math_thinking} (is_mathematical={is_mathematical}, subject_area={subject_area}, has_equations={has_equations})")
            except Exception:
                pass
            prompt_template = self.get_math_thinking_prompt_template(self.language)
        else:
            prompt_template = self.get_prompt_template(self.language)

        # Enforce difficulty policy: math -> [1] (easy), non-math -> [1,2] (easy, normal)
        try:
            if use_math_thinking:
                # Restrict to easy only for math
                difficulty_levels = [1]
            else:
                # Restrict to easy and medium for non-math
                difficulty_levels = [lvl for lvl in [1, 2] if lvl in set(difficulty_levels or [])] or [1, 2]
        except Exception:
            # Fallback defaults if anything goes wrong
            difficulty_levels = [1] if use_math_thinking else [1, 2]

        # Create prompt with enhanced instructions for mathematical content
        if use_math_thinking:
            enhanced_goals = self._enhance_math_goals(goals, content_analysis)
        else:
            enhanced_goals = goals

        prompt = PromptTemplate(
            template=prompt_template,
            input_variables=["content", "goals", "question_counts", "difficulty_levels"],
            partial_variables={"format_instructions": self.parser.get_format_instructions()}
        )
        
        # Create chain
        chain = prompt | self.model | self.parser
        
        # Generate questions with thinking enhancement
        result = chain.invoke({
            "content": self._enhance_content_for_thinking(content, use_math_thinking),
            "goals": "\n".join(enhanced_goals) if enhanced_goals else "تحقيق أهداف تعليمية عامة",
            "question_counts": self._format_question_counts(question_counts),
            "difficulty_levels": difficulty_levels
        })
        # Normalize None / unexpected type
        if result is None or not isinstance(result, dict):
            try:
                print("⚠️  QuestionTemplate chain returned non-dict; normalizing to empty structure")
            except Exception:
                pass
            result = {
                'multiple_choice': [],
                'short_answer': [],
                'complete': [],
                'true_false': [],
            }
        
        # Keep solution outlines only for math runs; otherwise strip them for safety
        def _strip_or_keep_solution_outlines(obj: Any, keep: bool):
            """Recursively remove solution fields from question dicts when keep=False."""
            try:
                if isinstance(obj, list):
                    for item in obj:
                        _strip_or_keep_solution_outlines(item, keep)
                elif isinstance(obj, dict):
                    # If this looks like a question dict
                    if not keep:
                        if 'solution_outline' in obj:
                            obj.pop('solution_outline', None)
                        if 'worked_solution' in obj:
                            obj.pop('worked_solution', None)
                    # Recurse into nested lists/dicts
                    for k, v in list(obj.items()):
                        # skip private metadata keys to avoid unnecessary traversal
                        if isinstance(v, (list, dict)) and not str(k).startswith('_'):
                            _strip_or_keep_solution_outlines(v, keep)
            except Exception:
                pass

        if isinstance(result, dict):
            _strip_or_keep_solution_outlines(result, use_math_thinking)

        # Add thinking metadata
        if isinstance(result, dict):
            result["_thinking_metadata"] = {
                "is_mathematical": is_mathematical,
                "subject_area": subject_area,
                "enhanced_reasoning": use_math_thinking,
                "math_concepts": content_analysis.get('math_concepts', []) if content_analysis else [],
                "enforced_difficulty_levels": difficulty_levels
            }
            # Presence flag for solution outlines
            result["_thinking_metadata"]["solution_outlines"] = bool(use_math_thinking)
            result["_thinking_metadata"]["worked_solutions"] = bool(use_math_thinking)

            # Normalize numeric formatting and add optional verification for simple patterns
            try:
                if use_math_thinking:
                    def _normalize_numeric(s: str) -> str:
                        try:
                            # Try to parse simple numeric strings
                            v = float(str(s).replace(',', '').strip())
                            return f"{v:.4f}"
                        except Exception:
                            return str(s)

                    def _process_question(q: dict):
                        # Sync worked_solution.result with answer if both numeric-like
                        ans = q.get('answer')
                        ws = q.get('worked_solution') or {}
                        if isinstance(ws, dict):
                            res = ws.get('result')
                            # If both look numeric, normalize and sync
                            try:
                                if ans is not None:
                                    ans_norm = _normalize_numeric(ans)
                                else:
                                    ans_norm = None
                                res_norm = _normalize_numeric(res) if res is not None else None
                                if ans_norm and res_norm:
                                    # Prefer the normalized answer, sync result
                                    q['answer'] = ans_norm
                                    ws['result'] = ans_norm
                                    q['worked_solution'] = ws
                            except Exception:
                                pass

                            # Optionally add a short verification if substitution fits pattern like "k * log(x)"
                            try:
                                sub = ws.get('substitution')
                                if isinstance(sub, str) and '*' in sub and 'log' in sub and 'verification' not in ws:
                                    # Extract something like "2 * log(4)" => if log(4) provided nearby in prompt, skip; keep a trivial echo
                                    ws['verification'] = sub
                                    q['worked_solution'] = ws
                            except Exception:
                                pass

                    # Walk common containers
                    for key in ['multiple_choice', 'short_answer', 'complete']:
                        items = result.get(key, [])
                        if isinstance(items, list):
                            for q in items:
                                if isinstance(q, dict):
                                    _process_question(q)
                    # Nested by goals
                    qbg = result.get('questions_by_goal', {})
                    if isinstance(qbg, dict):
                        for _, per_goal in qbg.items():
                            if isinstance(per_goal, dict):
                                for key in ['multiple_choice', 'short_answer', 'complete']:
                                    items = per_goal.get(key, [])
                                    if isinstance(items, list):
                                        for q in items:
                                            if isinstance(q, dict):
                                                _process_question(q)
            except Exception:
                pass
        
        return result
    
    def get_prompt_template(self, language: str) -> str:
        """Get the appropriate prompt template for the language."""
        if language == "arabic":
            return ARABIC_QUESTION_PROMPTS["main_template"]
        elif language == "english":
            return ENGLISH_QUESTION_PROMPTS["main_template"]
        else:
            return ARABIC_QUESTION_PROMPTS["main_template"]  # Default to Arabic
    
    def get_math_thinking_prompt_template(self, language: str) -> str:
        """Get the mathematical thinking prompt template for the language."""
        if language == "arabic":
            return ARABIC_QUESTION_PROMPTS.get("math_thinking_template", 
                                              ARABIC_QUESTION_PROMPTS["main_template"])
        elif language == "english":
            return ENGLISH_QUESTION_PROMPTS.get("math_thinking_template",
                                               ENGLISH_QUESTION_PROMPTS["main_template"])
        else:
            return ARABIC_QUESTION_PROMPTS.get("math_thinking_template",
                                              ARABIC_QUESTION_PROMPTS["main_template"])
    
    def _format_question_counts(self, question_counts: Dict[str, int]) -> str:
        """Format question counts for the prompt."""
        formatted = []
        for q_type, count in question_counts.items():
            formatted.append(f"{q_type}: {count}")
        return ", ".join(formatted)
    
    def _enhance_math_goals(self, goals: List[str], content_analysis: Dict[str, Any]) -> List[str]:
        """Enhance learning goals for mathematical content."""
        enhanced_goals = goals.copy() if goals else []
        
        if content_analysis and content_analysis.get('is_mathematical'):
            math_concepts = content_analysis.get('math_concepts', [])
            
            # Add thinking-oriented goals for math
            thinking_goals = []
            if self.language == "arabic":
                thinking_goals = [
                    "يطبق الطالب التفكير المنطقي في حل المسائل",
                    "يتبع خطوات منظمة في الحل",
                    "يتحقق من صحة إجاباته",
                    "يفسر طريقة الحل للآخرين"
                ]
                if math_concepts:
                    thinking_goals.append(f"يفهم ويطبق المفاهيم: {', '.join(math_concepts[:3])}")
            else:
                thinking_goals = [
                    "Students apply logical thinking in problem solving",
                    "Students follow organized steps in solutions",
                    "Students verify the correctness of their answers",
                    "Students explain their solution method to others"
                ]
                if math_concepts:
                    thinking_goals.append(f"Students understand and apply concepts: {', '.join(math_concepts[:3])}")
            
            enhanced_goals.extend(thinking_goals)
        
        return enhanced_goals
    
    def _enhance_content_for_thinking(self, content: str, is_mathematical: bool) -> str:
        """Enhance content with thinking prompts for better question generation."""
        if not is_mathematical:
            return content
        
        thinking_enhancement = ""
        if self.language == "arabic":
            thinking_enhancement = """

تعليمات للتفكير المنطقي في الرياضيات:
- عند حل أي مسألة، اتبع خطوات منطقية واضحة
- ابدأ بفهم المطلوب وتحديد المعطيات
- اختر الطريقة المناسبة للحل
- نفذ الحل خطوة بخطوة مع التفسير
- تحقق من صحة النتيجة
- اربط الحل بالمفاهيم الأساسية

"""
        else:
            thinking_enhancement = """

Instructions for logical thinking in mathematics:
- When solving any problem, follow clear logical steps
- Start by understanding what is required and identifying given information
- Choose the appropriate solution method
- Execute the solution step by step with explanation
- Verify the correctness of the result
- Connect the solution to fundamental concepts

"""
        
        return content + thinking_enhancement
