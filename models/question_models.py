from pydantic import BaseModel, Field
from typing import List, Optional, Dict

class MultipleChoiceQuestion(BaseModel):
    """Model for multiple choice questions."""
    question: str = Field(description="The question text")
    choices: List[str] = Field(description="List of answer choices")
    answer_key: int = Field(description="Index of the correct answer (0-based)")
    difficulty: Optional[int] = Field(default=1, description="Difficulty level (1-3)")
    target_goal: Optional[str] = Field(default=None, description="The specific learning goal this question targets")
    goal_id: Optional[str] = Field(default=None, description="Unique identifier for the learning goal")
    # For math-only runs: a concise 2-4 step outline of how to reach the answer (policy-safe, no chain-of-thought)
    solution_outline: Optional[str] = Field(default=None, description="Concise steps (2-4) outlining the solution approach for math questions")
    # For math-only runs: brief, structured calculation summary (not internal reasoning)
    worked_solution: Optional[Dict[str, str]] = Field(
        default=None,
        description="Structured short solution with keys: formula, substitution, result"
    )

class ShortAnswerQuestion(BaseModel):
    """Model for short answer questions."""
    question: str = Field(description="The question text")
    answer: str = Field(description="Sample answer or answer guidelines")
    difficulty: Optional[int] = Field(default=1, description="Difficulty level (1-3)")
    target_goal: Optional[str] = Field(default=None, description="The specific learning goal this question targets")
    goal_id: Optional[str] = Field(default=None, description="Unique identifier for the learning goal")
    solution_outline: Optional[str] = Field(default=None, description="Concise steps (2-4) outlining the solution approach for math questions")
    worked_solution: Optional[Dict[str, str]] = Field(default=None, description="Structured short solution with keys: formula, substitution, result")

class CompleteQuestion(BaseModel):
    """Model for completion questions."""
    question: str = Field(description="The incomplete sentence with blanks")
    answer: str = Field(description="The text that completes the sentence")
    difficulty: Optional[int] = Field(default=1, description="Difficulty level (1-3)")
    target_goal: Optional[str] = Field(default=None, description="The specific learning goal this question targets")
    goal_id: Optional[str] = Field(default=None, description="Unique identifier for the learning goal")
    solution_outline: Optional[str] = Field(default=None, description="Concise steps (2-4) outlining the solution approach for math questions")
    worked_solution: Optional[Dict[str, str]] = Field(default=None, description="Structured short solution with keys: formula, substitution, result")

class TrueFalseQuestion(BaseModel):
    """Model for true/false questions."""
    question: str = Field(description="The question text")
    choices: List[str] = Field(default=["صح", "خطأ"], description="True/False choices")
    answer_key: int = Field(description="Index of the correct answer (0 for true, 1 for false)")
    difficulty: Optional[int] = Field(default=1, description="Difficulty level (1-3)")
    target_goal: Optional[str] = Field(default=None, description="The specific learning goal this question targets")
    goal_id: Optional[str] = Field(default=None, description="Unique identifier for the learning goal")
    solution_outline: Optional[str] = Field(default=None, description="Concise steps (2-4) outlining the solution approach for math questions")
    worked_solution: Optional[Dict[str, str]] = Field(default=None, description="Structured short solution with keys: formula, substitution, result")

class LearningGoal(BaseModel):
    """Model for learning goals."""
    id: str = Field(description="Unique identifier for the goal")
    text: str = Field(description="The learning goal text")
    priority: Optional[int] = Field(default=1, description="Priority level (1=high, 2=medium, 3=low)")
    cognitive_level: Optional[str] = Field(default="understand", description="Bloom's taxonomy level")

class GoalQuestionMapping(BaseModel):
    """Model for mapping questions to goals."""
    goal_id: str = Field(description="Goal identifier")
    goal_text: str = Field(description="Goal text")
    question_count: int = Field(description="Number of questions for this goal")
    question_types: Dict[str, int] = Field(description="Count of each question type for this goal")

class QuestionBank(BaseModel):
    """Complete question bank model with goal-based organization."""
    # Traditional structure (for backward compatibility)
    multiple_choice: List[MultipleChoiceQuestion] = Field(default_factory=list)
    short_answer: List[ShortAnswerQuestion] = Field(default_factory=list)
    complete: List[CompleteQuestion] = Field(default_factory=list)
    true_false: List[TrueFalseQuestion] = Field(default_factory=list)
    
    # Goal-based organization
    learning_goals: List[LearningGoal] = Field(default_factory=list, description="List of learning goals")
    goal_question_mapping: List[GoalQuestionMapping] = Field(default_factory=list, description="Mapping of goals to questions")
    
    # Questions organized by goals
    questions_by_goal: Optional[Dict[str, Dict[str, List]]] = Field(
        default=None, 
        description="Questions organized by goal ID: {goal_id: {question_type: [questions]}}"
    )
