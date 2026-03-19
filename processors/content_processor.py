import re
import json
from typing import List, Dict, Any, Optional
from utils.language_detector import LanguageDetector
from config.settings import Settings
from langchain_openai import ChatOpenAI

class ContentProcessor:
    """Processes educational content for template generation using AI-driven analysis."""

    def __init__(self, model: Optional[ChatOpenAI] = None):
        self.language_detector = LanguageDetector()
        # Use shared LLM if provided, else construct one from settings
        self.model = model or ChatOpenAI(
            api_key=Settings.OPENAI_API_KEY,
            model=Settings.NON_MATH_MODEL,
            temperature=Settings.TEMPERATURE,
        )
    
    def generate_learning_goals(self, content: str, language: Optional[str] = None, count: int = 5) -> List[str]:
        """
        Generate concise, high-quality learning goals from content using the LLM.

        Args:
            content: Source educational content
            language: Desired language for the goals (auto-detected if not provided)
            count: Target number of goals

        Returns:
            List of learning goal strings (length between 3 and 7 when possible)
        """
        if not language:
            language = self.language_detector.detect_language(content)

        # Constrain count between 3 and 7
        target = max(3, min(7, int(count or 5)))

        system_ar = (
            "أنت خبير مناهج تعليمية. أنشئ أهداف تعلم واضحة وقابلة للقياس ومناسبة للمحتوى. "
            "أعد إجابة بصيغة JSON فقط: {\"goals\":[\"goal1\",...]}. لا تُضِف أي نص آخر."
        )
        system_en = (
            "You are an expert curriculum designer. Create clear, measurable learning goals appropriate to the content. "
            "Respond ONLY as strict JSON: {\"goals\":[\"goal1\",...]}. No extra text."
        )
        system = system_ar if language == "arabic" else system_en

        prompt = (
            f"{system}\n"
            f"Count: {target}.\n"
            f"Content:\n{content}"
        )

        try:
            response = self.model.invoke(prompt)
            raw = getattr(response, "content", str(response))
            data = self._extract_json(raw)
            goals = []
            if isinstance(data, dict) and isinstance(data.get("goals"), list):
                goals = [g for g in data["goals"] if isinstance(g, str) and g.strip()]
        except Exception:
            goals = []

        # Minimal fallback using key topics if LLM parsing fails
        if not goals:
            analysis = self.analyze_content(content)
            topics = analysis.get("key_topics", [])
            if language == "arabic":
                goals = [f"يتعرف الطالب على موضوع: {t}" for t in topics[:target]]
            else:
                goals = [f"Students identify the topic: {t}" for t in topics[:target]]

        return goals[:target]
    
    def analyze_content(self, content: str) -> Dict[str, Any]:
        """
        Analyze content using the LLM to extract structured insights.

        The AI returns a JSON object with:
        language, word_count, character_count, estimated_reading_time,
        complexity_level, key_topics, is_mathematical, math_concepts,
        has_equations, has_numbers, subject_area.
        """
        # Basic metrics to assist/validate AI output
        detected_language = self.language_detector.detect_language(content)
        word_count = len(content.split())
        character_count = len(content)

        prompt = (
            "You are an expert educational content analyst.\n"
            "Analyze the following content and return ONLY a strict JSON object with these exact keys: \n"
            "language (\"arabic\" or \"english\"), word_count (int), character_count (int), "
            "estimated_reading_time (int, minutes), complexity_level (one of: simple, medium, complex), "
            "key_topics (array of 3-7 short keywords in the same language as the content, no markup), "
            "is_mathematical (boolean), math_concepts (array of up to 10 concise math terms, empty if not mathematical; do not include symbols or punctuation-only items), "
            "has_equations (boolean), has_numbers (boolean), subject_area (one of: mathematics, science, language, literature, history, general).\n\n"
            f"Hint language (from a detector): {detected_language}.\n"
            f"Raw word_count: {word_count}, character_count: {character_count}.\n"
            "Use your own judgment based on the content; don't echo the content.\n"
            "If the content is not about math, set is_mathematical=false and math_concepts=[].\n\n"
            "Content:\n" + content
        )

        try:
            response = self.model.invoke(prompt)
            raw = getattr(response, "content", str(response))
            data = self._extract_json(raw)
        except Exception:
            data = {}

        # Fallbacks and normalization
        def _get(key, default):
            return data[key] if isinstance(data, dict) and key in data else default

        language = _get("language", detected_language)
        result = {
            "language": language,
            "word_count": int(_get("word_count", word_count) or word_count),
            "character_count": int(_get("character_count", character_count) or character_count),
            "estimated_reading_time": int(_get("estimated_reading_time", self._estimate_reading_time(content, language))),
            "complexity_level": _get("complexity_level", self._assess_complexity(content)),
            "key_topics": _get("key_topics", self._extract_key_topics_fallback(content, language)),
            "is_mathematical": bool(_get("is_mathematical", self._has_equations(content) or self._has_numbers(content) and False)),
            "math_concepts": _get("math_concepts", []),
            "has_equations": bool(_get("has_equations", self._has_equations(content))),
            "has_numbers": bool(_get("has_numbers", self._has_numbers(content))),
            "subject_area": _get("subject_area", self._identify_subject_area_fallback(content, language)),
        }

        # Sanity: if not mathematical then clear concepts
        if not result["is_mathematical"]:
            result["math_concepts"] = []

        return result
    
    def preprocess_content(self, content: str) -> str:
        """
        Preprocess content for better template generation.
        
        Args:
            content: Raw content
            
        Returns:
            Preprocessed content
        """
        # Remove excessive whitespace
        content = " ".join(content.split())
        
        # Ensure proper encoding
        content = content.encode('utf-8', errors='ignore').decode('utf-8')
        
        return content.strip()
    
    def _estimate_reading_time(self, content: str, language: str) -> int:
        """Estimate reading time in minutes."""
        words = len(content.split())
        # Average reading speed: 200 words per minute for Arabic, 250 for English
        wpm = 200 if language == "arabic" else 250
        return max(1, round(words / wpm))
    
    def _assess_complexity(self, content: str) -> str:
        """Assess content complexity level."""
        word_count = len(content.split())
        avg_word_length = sum(len(word) for word in content.split()) / max(1, word_count)

        # Check for mathematical symbols and equations (ignore plain hyphen to avoid false positives)
        math_symbols = re.findall(r'[+*/=<>≤≥∑∏∫∂√π∞%]', content)
        has_equations = bool(re.search(r'[\w\u0621-\u064A]+\s*[=<>≤≥]\s*[\w\u0621-\u064A]+', content))

        base_complexity = 0
        if word_count < 100 and avg_word_length < 5:
            base_complexity = 1  # simple
        elif word_count < 300 and avg_word_length < 7:
            base_complexity = 2  # medium
        else:
            base_complexity = 3  # complex

        # Increase complexity for mathematical content
        if math_symbols or has_equations:
            base_complexity = min(3, base_complexity + 1)

        complexity_map = {1: "simple", 2: "medium", 3: "complex"}
        return complexity_map[base_complexity]
    
    def _extract_key_topics_fallback(self, content: str, language: str) -> List[str]:
        """Lightweight fallback to extract key topics if AI parsing fails."""
        words = content.split()
        common_words = {
            "arabic": {"في", "من", "إلى", "على", "عن", "مع", "هذا", "هذه", "التي", "الذي", "أن", "كان", "يكون"},
            "english": {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "is", "are", "was"},
        }
        stop_words = common_words.get(language, set())
        word_freq: Dict[str, int] = {}
        for word in words:
            word = word.strip(".,!?;:\"'()[]{}").lower()
            if len(word) > 3 and word not in stop_words:
                word_freq[word] = word_freq.get(word, 0) + 1
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        return [word for word, _ in sorted_words[:5]]
    
    # Removed rule-based math detection; rely on AI output. Keep minimal helpers for fallbacks only.
    
    # Removed rule-based concept extraction; rely on AI output.
    
    def _has_equations(self, content: str) -> bool:
        """Check if content contains mathematical equations."""
        equation_patterns = [
            r'[\w\u0621-\u064A]+\s*[=<>≤≥]\s*[\w\u0621-\u064A]+',  # x = y or inequalities (Arabic/English)
            r'\d+\s*[+\-*/×÷\^]\s*\d+',  # basic arithmetic
            r'[\w\u0621-\u064A]+\s*[<>≤≥]\s*[\w\u0621-\u064A]+',  # inequalities
            r'\w+\^\d+',  # exponents
            r'sqrt\(\w+\)',  # square roots
            r'log\(\w+\)',  # logarithms
        ]
        
        for pattern in equation_patterns:
            if re.search(pattern, content):
                return True
        
        return False
    
    def _has_numbers(self, content: str) -> bool:
        """Check if content contains numbers."""
        return bool(re.search(r'\d+', content))

    def _identify_subject_area_fallback(self, content: str, language: str) -> str:
        """Simple fallback subject area identification when AI output is unavailable."""
        content_lower = content.lower()
        indicators = {
            "mathematics": ["رياضيات", "معادلة", "جبر", "هندسة", "math", "algebra", "geometry", "equation"],
            "science": ["علوم", "فيزياء", "كيمياء", "أحياء", "science", "physics", "chemistry", "biology"],
            "language": ["لغة", "نحو", "صرف", "grammar", "language", "reading", "writing"],
            "literature": ["أدب", "شعر", "قصة", "رواية", "literature", "poetry", "novel", "story"],
            "history": ["تاريخ", "حضارة", "قرن", "history", "ancient", "modern", "century"],
        }
        scores: Dict[str, int] = {}
        for subject, inds in indicators.items():
            scores[subject] = sum(1 for ind in inds if re.search(rf'(?:^|\W){re.escape(ind)}(?:\W|$)', content_lower))
        scores = {k: v for k, v in scores.items() if v > 0}
        return max(scores, key=scores.get) if scores else "general"

    def _extract_json(self, text: str) -> Dict[str, Any]:
        """Extract the first valid JSON object from text."""
        try:
            return json.loads(text)
        except Exception:
            pass
        # Attempt to locate a JSON block
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            snippet = text[start : end + 1]
            try:
                return json.loads(snippet)
            except Exception:
                return {}
        return {}
