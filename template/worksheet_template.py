from typing import Dict, Any, List
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from template.base_template import BaseTemplate
from models.worksheet_models import Worksheet
from prompts.arabic.worksheet_prompts import ARABIC_WORKSHEET_PROMPTS
from prompts.english.worksheet_prompts import ENGLISH_WORKSHEET_PROMPTS

class WorksheetTemplate(BaseTemplate):
    """Template for generating worksheets."""
    
    def __init__(self, model=None):
        super().__init__(model)
        self.parser = JsonOutputParser(pydantic_object=Worksheet)
        
    def generate(self, content: str, goals: List[str] = None, **kwargs) -> Dict[str, Any]:
        """
        Generate a worksheet based on content and goals.
        
        Args:
            content: Educational content
            goals: Learning goals
            
        Returns:
            Generated worksheet as dictionary
        """
        self.validate_input(content)
        
        if goals is None:
            goals = []
            
        # Get prompt template based on language
        prompt_template = self.get_prompt_template(self.language)
        
        # Create prompt
        prompt = PromptTemplate(
            template=prompt_template,
            input_variables=["content", "goals"],
            partial_variables={"format_instructions": self.parser.get_format_instructions()}
        )
        
        # Create chain
        chain = prompt | self.model | self.parser
        
        # Generate worksheet
        result = chain.invoke({
            "content": content,
            "goals": "\n".join(goals) if goals else "تحقيق أهداف تعليمية عامة"
        })
        
        return result
    
    def get_prompt_template(self, language: str) -> str:
        """Get the appropriate prompt template for the language."""
        if language == "arabic":
            return ARABIC_WORKSHEET_PROMPTS["main_template"]
        elif language == "english":
            return ENGLISH_WORKSHEET_PROMPTS["main_template"]
        else:
            return ARABIC_WORKSHEET_PROMPTS["main_template"]  # Default to Arabic
