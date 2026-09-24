from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class MindMapNode(BaseModel):
    """Model for a single node in the mind map."""
    key: int = Field(description="Unique identifier for the node")
    text: str = Field(description="Text content of the node")
    parent: Optional[int] = Field(default=None, description="Parent node key (None for root)")
    brush: Optional[str] = Field(default=None, description="Color/brush for the node")
    dir: Optional[str] = Field(default=None, description="Direction from parent (left/right)")
    loc: Optional[str] = Field(default=None, description="Location coordinates for the node")

class MindMap(BaseModel):
    """Model for complete mind map structure compatible with GoJS."""
    nodeDataArray: List[MindMapNode] = Field(description="Array of all nodes in the mind map")
    
    class Config:
        json_schema_extra = {
            "example": {
                "nodeDataArray": [
                    {"key": 0, "text": "Main Topic", "loc": "0 0"},
                    {"key": 1, "parent": 0, "text": "Subtopic 1", "brush": "skyblue", "dir": "right"},
                    {"key": 2, "parent": 0, "text": "Subtopic 2", "brush": "darkseagreen", "dir": "left"}
                ]
            }
        }

class MindMapResponse(BaseModel):
    """Response model for mind map generation including metadata."""
    class_: str = Field(default="go.TreeModel", alias="class", description="GoJS model class")
    nodeDataArray: List[MindMapNode] = Field(description="Array of all nodes in the mind map")
    
    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "class": "go.TreeModel",
                "nodeDataArray": [
                    {"key": 0, "text": "Main Topic", "loc": "0 0"},
                    {"key": 1, "parent": 0, "text": "Subtopic 1", "brush": "skyblue", "dir": "right"}
                ]
            }
        }
