from typing import Dict, Any, List, Optional, Tuple
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
import uuid
import json
from template.base_template import BaseTemplate
from template.question_template import QuestionTemplate
from template.worksheet_template import WorksheetTemplate
from models.question_models import QuestionBank, LearningGoal, GoalQuestionMapping
from models.worksheet_models import Worksheet, LearningGoalWorksheet
from config.settings import Settings

class GoalBasedTemplate(BaseTemplate):
    """Template for generating goal-based educational content."""
    
    def __init__(self, model=None):
        super().__init__(model)
        self.question_template = QuestionTemplate(model)
        self.worksheet_template = WorksheetTemplate(model)
    
    def generate(self, content: str, goals: Optional[List[str]] = None, **kwargs) -> Dict[str, Any]:
        """
        Required implementation of abstract method from BaseTemplate.
        This method delegates to generate_goal_based_questions.
        """
        return self.generate_goal_based_questions(content, goals, **kwargs)
    
    def get_prompt_template(self, language: str) -> str:
        """
        Required implementation of abstract method from BaseTemplate.
        Returns a basic template since this class uses composition with other templates.
        """
        if language == "arabic":
            return """
أنشئ أسئلة تعليمية مبنية على الأهداف التعليمية المحددة.

المحتوى التعليمي:
{content}

الأهداف التعليمية:
{goals}

تعليمات التنسيق:
{format_instructions}
"""
        else:
            return """
Create educational questions based on specified learning goals.

Educational Content:
{content}

Learning Goals:
{goals}

Formatting Instructions:
{format_instructions}
"""
    
    def generate_goal_based_questions(self, content: str, goals: Optional[List[str]] = None, 
                                    question_counts: Dict[str, int] = None, 
                                    difficulty_levels: List[int] = None,
                                    content_analysis: Dict[str, Any] = None, 
                                    **kwargs) -> Dict[str, Any]:
        """
        Generate questions organized by learning goals.
        
        Handles two scenarios:
        1. Goals provided: Generate questions for each goal
        2. No goals: First generate worksheet with goals, then generate questions
        
        Args:
            content: Educational content
            goals: Optional list of learning goals
            question_counts: Number of each question type to generate
            difficulty_levels: Difficulty levels to include
            content_analysis: Analysis of the content
            
        Returns:
            Goal-based question bank with clear goal-question mapping
        """
        # Set defaults
        if question_counts is None:
            question_counts = Settings.DEFAULT_QUESTION_COUNTS
        if difficulty_levels is None:
            difficulty_levels = Settings.DIFFICULTY_LEVELS
        
        # Scenario 1: Goals provided
        if goals and len(goals) > 0:
            print("📋 Scenario 1: Using provided goals")
            structured_goals = self._create_structured_goals(goals)
            result = self._generate_questions_for_goals(
                content, structured_goals, question_counts, 
                difficulty_levels, content_analysis
            )
        else:
            # Scenario 2: No goals - generate worksheet first to extract goals
            print("📋 Scenario 2: No goals provided - generating worksheet with goals first")
            worksheet_result = None
            try:
                worksheet_result = self.worksheet_template.generate(content)
            except Exception as gen_exc:
                # Fail soft – continue with default goals later
                try:
                    print(f"⚠️  Worksheet generation failed while extracting goals: {gen_exc}")
                except Exception:
                    pass

            # Defensive normalization – ensure we always have a dict structure
            if worksheet_result is None:
                worksheet_result = {"goals": [], "_warning": "worksheet_generation_returned_none"}
            elif not isinstance(worksheet_result, dict):
                worksheet_result = {"goals": [], "_warning": "worksheet_generation_invalid_type"}
            
            # Extract goals from worksheet
            try:
                extracted_goals = worksheet_result.get('goals', []) if isinstance(worksheet_result, dict) else []
            except Exception:
                extracted_goals = []
            if not extracted_goals:
                # Fallback to default goals
                extracted_goals = self._generate_default_goals(content, content_analysis)
                if isinstance(worksheet_result, dict):
                    worksheet_result.setdefault('_fallbacks', {})['used_default_goals'] = True
                try:
                    print(f"🔁 Fallback: Using {len(extracted_goals)} default goals")
                except Exception:
                    pass
            
            print(f"✅ Generated {len(extracted_goals)} goals from content")
            structured_goals = self._create_structured_goals(extracted_goals)
            
            # Now generate questions for the extracted goals
            result = self._generate_questions_for_goals(
                content, structured_goals, question_counts, 
                difficulty_levels, content_analysis
            )
            
            # Include worksheet information in the result
            result["_generated_worksheet"] = worksheet_result
        
        return result
    
    def _create_structured_goals(self, goals: List[str]) -> List[LearningGoal]:
        """Convert simple goal strings to structured LearningGoal objects."""
        structured_goals = []
        for i, goal_text in enumerate(goals):
            goal = LearningGoal(
                id=f"goal_{i+1}",
                text=goal_text.strip(),
                priority=1 if i < 2 else 2,  # First 2 goals are high priority
                cognitive_level=self._determine_cognitive_level(goal_text)
            )
            structured_goals.append(goal)
        return structured_goals
    
    def _determine_cognitive_level(self, goal_text: str) -> str:
        """Determine the cognitive level based on goal text."""
        goal_lower = goal_text.lower()
        
        # Arabic cognitive level keywords
        if any(word in goal_lower for word in ['يحلل', 'يقيم', 'ينقد', 'يقارن']):
            return 'analyze'
        elif any(word in goal_lower for word in ['يطبق', 'يستخدم', 'يحل', 'ينفذ']):
            return 'apply'
        elif any(word in goal_lower for word in ['يفهم', 'يشرح', 'يفسر', 'يوضح']):
            return 'understand'
        elif any(word in goal_lower for word in ['يذكر', 'يسمي', 'يعدد', 'يحدد']):
            return 'remember'
        elif any(word in goal_lower for word in ['ينشئ', 'يصمم', 'يبتكر', 'يؤلف']):
            return 'create'
        
        # English cognitive level keywords
        elif any(word in goal_lower for word in ['analyze', 'evaluate', 'critique', 'compare']):
            return 'analyze'
        elif any(word in goal_lower for word in ['apply', 'use', 'solve', 'implement']):
            return 'apply'
        elif any(word in goal_lower for word in ['understand', 'explain', 'interpret', 'clarify']):
            return 'understand'
        elif any(word in goal_lower for word in ['remember', 'list', 'identify', 'define']):
            return 'remember'
        elif any(word in goal_lower for word in ['create', 'design', 'develop', 'compose']):
            return 'create'
        
        return 'understand'  # Default
    
    def _generate_questions_for_goals(self, content: str, goals: List[LearningGoal], 
                                    question_counts: Dict[str, int], 
                                    difficulty_levels: List[int],
                                    content_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Generate questions for each goal individually."""
        all_questions = {
            'multiple_choice': [],
            'short_answer': [],
            'complete': [],
            'true_false': []
        }

        goal_question_mapping: List[GoalQuestionMapping] = []
        questions_by_goal: Dict[str, Any] = {}

        # Calculate questions per goal
        total_goals = len(goals)
        questions_per_goal = self._distribute_questions_per_goal(question_counts, total_goals)

        print(f"🎯 Generating questions for {total_goals} goals:")

        any_enhanced_thinking = False
        for goal in goals:
            print(f"   • {goal.text[:60]}...")

            # Generate questions specifically for this goal
            goal_specific_questions = self._generate_questions_for_single_goal(
                content, goal, questions_per_goal, difficulty_levels, content_analysis
            )

            # Track questions by goal
            questions_by_goal[goal.id] = goal_specific_questions

            # Capture thinking metadata summary
            try:
                meta = goal_specific_questions.get('_thinking_metadata') if isinstance(goal_specific_questions, dict) else None
                if isinstance(meta, dict) and meta.get('enhanced_reasoning'):
                    any_enhanced_thinking = True
            except Exception:
                pass

            # Add goal information to each question
            for question_type, questions in goal_specific_questions.items():
                # Skip metadata keys
                if question_type.startswith('_'):
                    continue
                for question in questions:
                    question['target_goal'] = goal.text
                    question['goal_id'] = goal.id
                    all_questions[question_type].append(question)

            # Create mapping entry
            mapping = GoalQuestionMapping(
                goal_id=goal.id,
                goal_text=goal.text,
                question_count=sum(len(qs) for qtype, qs in goal_specific_questions.items() if not qtype.startswith('_')),
                question_types={qtype: len(qs) for qtype, qs in goal_specific_questions.items() if not qtype.startswith('_')}
            )
            goal_question_mapping.append(mapping)

        # Create the result
        result: Dict[str, Any] = {
            'multiple_choice': all_questions['multiple_choice'],
            'short_answer': all_questions['short_answer'],
            'complete': all_questions['complete'],
            'true_false': all_questions['true_false'],
            'learning_goals': [goal.dict() for goal in goals],
            'goal_question_mapping': [mapping.dict() for mapping in goal_question_mapping],
            'questions_by_goal': questions_by_goal,
            '_goal_based_metadata': {
                'total_goals': total_goals,
                'total_questions': sum(len(qs) for qs in all_questions.values()),
                'questions_per_goal_distribution': questions_per_goal,
                'scenario': 'goals_provided' if len(goals) > 0 else 'goals_generated'
            }
        }

        # Surface a summary flag for enhanced thinking usage across goals
        result.setdefault('_thinking_summary', {})['enhanced_reasoning_used'] = bool(any_enhanced_thinking)

        return result
    
    def _distribute_questions_per_goal(self, question_counts: Dict[str, int], total_goals: int) -> Dict[str, int]:
        """Return the full question counts for each goal (not distributed)."""
        if total_goals == 0:
            return question_counts
        
        # Return the full question counts for each goal
        # This means each goal will have the specified number of questions
        return question_counts.copy()
    
    def _generate_questions_for_single_goal(self, content: str, goal: LearningGoal, 
                                          questions_per_goal: Dict[str, int],
                                          difficulty_levels: List[int],
                                          content_analysis: Dict[str, Any]) -> Dict[str, List]:
        """Generate questions for a single specific goal."""
        
        # Create goal-focused content
        goal_focused_content = self._create_goal_focused_content(content, goal)
        
        # Generate questions using the enhanced question template
        result = None
        try:
            result = self.question_template.generate(
                content=goal_focused_content,
                goals=[goal.text],
                question_counts=questions_per_goal,
                difficulty_levels=difficulty_levels,
                content_analysis=content_analysis
            )
        except Exception as gen_exc:
            try:
                print(f"⚠️  Goal-specific question generation failed for {goal.id}: {gen_exc}")
            except Exception:
                pass
        # Normalize None / unexpected types to empty dict for downstream .get usage
        if result is None or not isinstance(result, dict):
            result = {
                'multiple_choice': [],
                'short_answer': [],
                'complete': [],
                'true_false': [],
                '_thinking_metadata': {'enhanced_reasoning': False, 'normalized_empty': True}
            }
        
        # Extract just the questions and preserve thinking metadata at goal level
        thinking_meta = result.get('_thinking_metadata') if isinstance(result, dict) else None
        return {
            'multiple_choice': result.get('multiple_choice', []),
            'short_answer': result.get('short_answer', []),
            'complete': result.get('complete', []),
            'true_false': result.get('true_false', []),
            '_thinking_metadata': thinking_meta
        }
    
    def _create_goal_focused_content(self, content: str, goal: LearningGoal) -> str:
        """Create content that emphasizes the specific learning goal."""
        goal_emphasis = ""
        
        if self.language == "arabic":
            goal_emphasis = f"""

التركيز على الهدف التعليمي المحدد:
🎯 {goal.text}

مستوى التفكير المطلوب: {self._get_arabic_cognitive_level(goal.cognitive_level)}

يجب أن تركز الأسئلة المتولدة بشكل خاص على تحقيق هذا الهدف التعليمي.

"""
        else:
            goal_emphasis = f"""

Focus on the specific learning goal:
🎯 {goal.text}

Required cognitive level: {goal.cognitive_level}

Generated questions should specifically focus on achieving this learning goal.

"""
        
        return content + goal_emphasis
    
    def _get_arabic_cognitive_level(self, cognitive_level: str) -> str:
        """Get Arabic translation of cognitive levels."""
        mapping = {
            'remember': 'التذكر',
            'understand': 'الفهم',
            'apply': 'التطبيق',
            'analyze': 'التحليل',
            'evaluate': 'التقييم',
            'create': 'الإبداع'
        }
        return mapping.get(cognitive_level, 'الفهم')
    
    def _generate_default_goals(self, content: str, content_analysis: Dict[str, Any]) -> List[str]:
        """Generate default learning goals if none provided."""
        if self.language == "arabic":
            default_goals = [
                "يفهم الطالب المفاهيم الأساسية في المحتوى",
                "يطبق الطالب المعلومات المكتسبة في سياقات مختلفة",
                "يحلل الطالب العلاقات بين العناصر المختلفة"
            ]
        else:
            default_goals = [
                "Students understand the basic concepts in the content",
                "Students apply acquired information in different contexts",
                "Students analyze relationships between different elements"
            ]
        
        # Add subject-specific goals if available
        if content_analysis and content_analysis.get('is_mathematical'):
            if self.language == "arabic":
                default_goals.extend([
                    "يحل الطالب المسائل الرياضية باستخدام الطرق المناسبة",
                    "يتحقق الطالب من صحة الحلول الرياضية"
                ])
            else:
                default_goals.extend([
                    "Students solve mathematical problems using appropriate methods",
                    "Students verify the correctness of mathematical solutions"
                ])
        
        return default_goals
    
    def print_goal_based_result(self, result: Dict[str, Any]):
        """Print goal-based results in a formatted way."""
        print("\n🎯 GOAL-BASED QUESTION GENERATION RESULTS")
        print("=" * 60)
        
        # Print metadata
        metadata = result.get('_goal_based_metadata', {})
        print(f"📊 Total Goals: {metadata.get('total_goals', 0)}")
        print(f"📝 Total Questions: {metadata.get('total_questions', 0)}")
        print(f"🔄 Scenario: {metadata.get('scenario', 'unknown')}")
        
        # Print goals
        goals = result.get('learning_goals', [])
        print(f"\n🎯 LEARNING GOALS:")
        for i, goal in enumerate(goals, 1):
            print(f"   {i}. [{goal['id']}] {goal['text']}")
            print(f"      Priority: {goal['priority']}, Cognitive Level: {goal['cognitive_level']}")
        
        # Print goal-question mapping
        mappings = result.get('goal_question_mapping', [])
        print(f"\n📋 GOAL-QUESTION MAPPING:")
        for mapping in mappings:
            print(f"   🎯 {mapping['goal_text'][:50]}...")
            print(f"      Questions: {mapping['question_count']} total")
            question_types = mapping['question_types']
            print(f"      Types: MC({question_types.get('multiple_choice', 0)}), "
                  f"SA({question_types.get('short_answer', 0)}), "
                  f"Comp({question_types.get('complete', 0)}), "
                  f"TF({question_types.get('true_false', 0)})")
            print()
        
        # Print sample questions by goal
        questions_by_goal = result.get('questions_by_goal', {})
        print(f"\n📝 SAMPLE QUESTIONS BY GOAL:")
        for goal_id, goal_questions in questions_by_goal.items():
            goal_info = next((g for g in goals if g['id'] == goal_id), {})
            print(f"\n   🎯 {goal_info.get('text', goal_id)}")
            
            for question_type, questions in goal_questions.items():
                if questions:
                    print(f"      📋 {question_type.replace('_', ' ').title()}:")
                    for i, q in enumerate(questions[:2], 1):  # Show first 2 questions
                        print(f"         {i}. {q.get('question', '')[:80]}...")
                    if len(questions) > 2:
                        print(f"         ... and {len(questions) - 2} more")
        
        # Print generated worksheet if available
        if '_generated_worksheet' in result:
            print(f"\n📄 GENERATED WORKSHEET GOALS:")
            worksheet = result['_generated_worksheet']
            for i, goal in enumerate(worksheet.get('goals', []), 1):
                print(f"   {i}. {goal}")
