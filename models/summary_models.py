from pydantic import BaseModel, Field

class LessonSummary(BaseModel):
    """Model for lesson summary template."""
    opening: str = Field(description="Introduction or opening statement for the lesson")
    summary: str = Field(description="Main summary of the lesson content")
    ending: str = Field(description="Conclusion or closing statement")
