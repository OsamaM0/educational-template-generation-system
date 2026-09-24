from langdetect import detect, DetectorFactory
from typing import Optional
import re

# Set seed for consistent results
DetectorFactory.seed = 0

class LanguageDetector:
    """Utility class for detecting content language."""
    
    @staticmethod
    def detect_language(text: str) -> str:
        """
        Detect the primary language of the given text.
        
        Args:
            text: Text to analyze
            
        Returns:
            Language code ('arabic' or 'english')
        """
        if not text or not text.strip():
            return "arabic"  # Default to Arabic
            
        try:
            # Clean text for better detection
            cleaned_text = LanguageDetector._clean_text(text)
            
            # Use langdetect
            detected = detect(cleaned_text)
            
            # Map language codes
            if detected == 'ar':
                return "arabic"
            elif detected in ['en']:
                return "english"
            else:
                # Fall back to character-based detection
                return LanguageDetector._detect_by_characters(cleaned_text)
                
        except Exception:
            # Fall back to character-based detection
            return LanguageDetector._detect_by_characters(text)
    
    @staticmethod
    def _clean_text(text: str) -> str:
        """Clean text for better language detection."""
        # Remove numbers, punctuation, and extra whitespace
        cleaned = re.sub(r'[0-9\s\-_+=.,!?;:"()[\]{}]+', ' ', text)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned
    
    @staticmethod
    def _detect_by_characters(text: str) -> str:
        """Detect language based on character analysis."""
        arabic_chars = 0
        english_chars = 0
        
        for char in text:
            if '\u0600' <= char <= '\u06FF' or '\u0750' <= char <= '\u077F':
                arabic_chars += 1
            elif 'a' <= char.lower() <= 'z':
                english_chars += 1
        
        total_chars = arabic_chars + english_chars
        
        if total_chars == 0:
            return "arabic"  # Default to Arabic
            
        arabic_ratio = arabic_chars / total_chars
        
        return "arabic" if arabic_ratio > 0.3 else "english"
    
    @staticmethod
    def is_arabic(text: str) -> bool:
        """Check if text is primarily in Arabic."""
        return LanguageDetector.detect_language(text) == "arabic"
    
    @staticmethod
    def is_english(text: str) -> bool:
        """Check if text is primarily in English."""
        return LanguageDetector.detect_language(text) == "english"
