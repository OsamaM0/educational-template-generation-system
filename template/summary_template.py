from typing import Dict, Any, List
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.documents import Document
from template.base_template import BaseTemplate
from prompts.arabic.summary_prompts import ARABIC_SUMMARY_PROMPTS
from prompts.english.summary_prompts import ENGLISH_SUMMARY_PROMPTS

class SummaryTemplate(BaseTemplate):
    """Template for generating lesson summaries."""
    
    def generate(self, content: str, goals: List[str] = None, **kwargs) -> Dict[str, Any]:
        """
        Generate a lesson summary based on content.
        
        Args:
            content: Educational content
            goals: Learning goals (optional)
            
        Returns:
            Generated summary as dictionary
        """
        self.validate_input(content)
        
        # Get prompt template based on language
        prompt_template = self.get_prompt_template(self.language)
        
        # Create prompt
        prompt = ChatPromptTemplate.from_messages([
            ("system", prompt_template)
        ])
        
        # Create chain
        chain = create_stuff_documents_chain(self.model, prompt)
        
        # Convert content to documents
        docs = [Document(page_content=content)]
        
        # Generate summary
        result = chain.invoke({"context": docs})
        
        # Parse the result into the expected format
        # This is a simplified parser - you might want to use JsonOutputParser here too
        return self._parse_summary_result(result)
    
    def get_prompt_template(self, language: str) -> str:
        """Get the appropriate prompt template for the language."""
        if language == "arabic":
            return ARABIC_SUMMARY_PROMPTS["main_template"]
        elif language == "english":
            return ENGLISH_SUMMARY_PROMPTS["main_template"]
        else:
            return ARABIC_SUMMARY_PROMPTS["main_template"]  # Default to Arabic
    
    def _parse_summary_result(self, result: str) -> Dict[str, Any]:
        """Parse the summary result into structured format."""
        # Simple parsing - in production you might want to use JsonOutputParser
        lines = result.strip().split('\n')
        
        summary_dict = {
            "opening": "",
            "summary": "",
            "ending": ""
        }
        
        current_section = "summary"
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            if "افتتاحية" in line or "opening" in line.lower():
                current_section = "opening"
            elif "خلاصة" in line or "summary" in line.lower():
                current_section = "summary"
            elif "خاتمة" in line or "ending" in line.lower():
                current_section = "ending"
            else:
                if summary_dict[current_section]:
                    summary_dict[current_section] += " " + line
                else:
                    summary_dict[current_section] = line
        
        # If no sections found, put everything in summary
        if not any(summary_dict.values()):
            summary_dict["summary"] = result
            
        return summary_dict
