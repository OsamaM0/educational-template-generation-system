from pydantic import BaseModel, Field
from typing import List, Dict, Optional

class VocabularyItem(BaseModel):
    """Model for vocabulary items."""
    term: str = Field(description="The vocabulary term")
    definition: str = Field(description="Definition or explanation of the term")

class LearningGoalWorksheet(BaseModel):
    """Model for learning goals in worksheets."""
    id: str = Field(description="Unique identifier for the goal")
    text: str = Field(description="The learning goal text")
    priority: Optional[int] = Field(default=1, description="Priority level (1=high, 2=medium, 3=low)")
    activities: List[str] = Field(default_factory=list, description="Activities specifically for this goal")
    assessment_methods: List[str] = Field(default_factory=list, description="How to assess this goal")

class Worksheet(BaseModel):
    """Model for worksheet template with enhanced goal-based structure."""
    # Traditional structure (for backward compatibility)
    goals: List[str] = Field(description="Learning goals for the worksheet")
    applications: List[str] = Field(description="Practical applications or activities")
    vocabulary: List[VocabularyItem] = Field(description="Key vocabulary terms and definitions")
    teacher_guidelines: List[str] = Field(description="Guidelines and tips for teachers")
    
    # Enhanced goal-based structure
    structured_goals: Optional[List[LearningGoalWorksheet]] = Field(
        default=None, 
        description="Detailed learning goals with associated activities"
    )
    goal_based_activities: Optional[Dict[str, List[str]]] = Field(
        default=None,
        description="Activities organized by goal ID: {goal_id: [activities]}"
    )
