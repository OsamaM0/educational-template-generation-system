from typing import Dict, Any, List
from typing import Tuple, Set, Callable, Optional
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.documents import Document
import json
import re
import logging
from json_repair import repair_json

# Optional faster JSON library
try:  # pragma: no cover - optional dependency
    import orjson  # type: ignore
except ImportError:  # pragma: no cover
    orjson = None  # type: ignore

from template.base_template import BaseTemplate
from prompts.arabic.mindmap_prompts import ARABIC_MINDMAP_PROMPTS
from prompts.english.mindmap_prompts import ENGLISH_MINDMAP_PROMPTS
from models.mindmap_models import MindMapResponse
from config.settings import Settings
from utils.mindmap_postprocess import post_process_mindmap

logger = logging.getLogger(__name__)

class MindMapTemplate(BaseTemplate):
    """Template for generating mind maps."""
    
    def __init__(self, model):
        super().__init__(model)
        self.prompt_templates = {
            "arabic": ARABIC_MINDMAP_PROMPTS,
            "english": ENGLISH_MINDMAP_PROMPTS
        }
    
    def get_prompt_template(self, language: str) -> str:
        """Get the appropriate prompt template for the given language."""
        return self.prompt_templates.get(language, self.prompt_templates["english"])["main_template"]
    
    def get_planning_template(self, language: str) -> str:
        """Get the planning prompt for enhanced thinking."""
        prompts = self.prompt_templates.get(language, self.prompt_templates["english"])
        return prompts.get("planning_template")
    
    _CODE_BLOCK_JSON_RE = re.compile(r'```json\s*|```', re.IGNORECASE)
    _FIRST_JSON_OBJECT_RE = re.compile(r'(\{.*\})', re.DOTALL)

    def clean_and_parse_json(self, response_text: str) -> Dict[str, Any]:
        """Optimized JSON cleaning & parsing with early exits.

        Performance notes:
        - Avoid repeated regex compilation (precompiled class attrs)
        - Minimize expensive repair_json/orjson calls (only when necessary)
        - Fast path returns ASAP for already valid JSON
        - Fallback sequence: direct -> whitespace normalized -> repair -> repair(normalized)
        """
        snippet = (response_text or "")[:200]
        logger.debug(f"Original response (truncated): {snippet}...")

        text = self._CODE_BLOCK_JSON_RE.sub('', response_text or '').strip()

        # Narrow to first JSON-like block if extra explanation exists
        m = self._FIRST_JSON_OBJECT_RE.search(text)
        if m:
            text = m.group(1)

        # Trim outside braces just in case
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1 and end > start:
            text = text[start:end+1]
        text_stripped = text.strip()

        # Fast path 1: direct parse (orjson > json)
        try:
            if orjson:  # pragma: no cover
                return orjson.loads(text_stripped)  # type: ignore
            return json.loads(text_stripped)
        except Exception:
            pass

        # Prepare normalized variant (single spaces)
        normalized = re.sub(r'\s+', ' ', text_stripped)
        if normalized != text_stripped:
            try:
                if orjson:  # pragma: no cover
                    return orjson.loads(normalized)  # type: ignore
                return json.loads(normalized)
            except Exception:
                pass

        # Attempt repair on original
        try:
            repaired = repair_json(text_stripped)
            try:
                if orjson:  # pragma: no cover
                    return orjson.loads(repaired)  # type: ignore
                return json.loads(repaired)
            except Exception:
                # If repair returns but still fails, continue to normalized repair
                pass
        except Exception as e:  # pragma: no cover
            logger.debug(f"repair_json original failed: {e}")

        # Attempt repair on normalized form
        try:
            repaired_norm = repair_json(normalized)
            if orjson:  # pragma: no cover
                return orjson.loads(repaired_norm)  # type: ignore
            return json.loads(repaired_norm)
        except Exception as e:
            logger.error(f"All JSON parsing strategies failed: {e}; text excerpt={text_stripped[:500]}")
            raise ValueError("Unable to parse response as valid JSON") from e
    
    def generate(self, content: str, goals: List[str] = None, **kwargs) -> Dict[str, Any]:
        """
        Generate a mind map based on the provided content.
        
        Args:
            content: The educational content to create a mind map from
            goals: Learning goals (not used in mind map generation but kept for compatibility)
            **kwargs: Additional parameters
            
        Returns:
            Dictionary containing the mind map in GoJS format
        """
        # Validate input
        self.validate_input(content)
        
        
        # Clean the content
        content = content.strip()
        
        content = self._sanitize_content(content)

        # If multi-pass is enabled and content is long, split into chunks and merge
        if Settings.MINDMAP_MULTI_PASS and len(content) > Settings.MINDMAP_CHUNK_SIZE_CHARS:
            logger.debug("Using multi-pass chunking for long content")
            chunks = self._chunk_text(content, Settings.MINDMAP_CHUNK_SIZE_CHARS, Settings.MINDMAP_CHUNK_OVERLAP_CHARS)
            partial_maps: List[Dict[str, Any]] = []
            for idx, ch in enumerate(chunks):
                logger.debug(f"Generating partial mind map for chunk {idx+1}/{len(chunks)} size={len(ch)}")
                mm = self._generate_single_pass(ch)
                if not mm:
                    continue
                partial_maps.append(mm)
            if not partial_maps:
                return None
            merged = self._merge_mindmaps(partial_maps)
            merged = self._post_process_mindmap(merged)
           
            return merged
        
        # Single pass generation
        return self._generate_single_pass(content)


    def _post_process_mindmap(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Delegate to shared utility for post-processing."""
        return post_process_mindmap(data)

    # ---- New helpers for multi-pass generation ----
    def _sanitize_content(self, content: str) -> str:
        content = (content or "").strip()
        # Filter out problematic characters
        content = re.sub(r'[\uf000-\uf8ff]', '', content)
        # Normalize whitespace
        content = " ".join(content.split())
        return content

    def _chunk_text(self, text: str, size: int, overlap: int) -> List[str]:
        if size <= 0:
            return [text]
        chunks: List[str] = []
        start = 0
        n = len(text)
        while start < n:
            end = min(n, start + size)
            # Try to end at a sentence boundary within the window
            window = text[start:end]
            last_period = max(window.rfind('.'), window.rfind('!'), window.rfind('?'), window.rfind('\n'))
            if last_period != -1 and (start + last_period + 1) - start > size * 0.6:
                end = start + last_period + 1
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            if end >= n:
                break
            start = max(0, end - max(0, overlap))
        return chunks

    def _generate_single_pass(self, content: str) -> Dict[str, Any]:
        # Get the prompt template for the detected language
        prompt_template = self.get_prompt_template(self.language)
        use_planning = Settings.MINDMAP_ENHANCED_THINKING and bool(self.get_planning_template(self.language))

        # Create the prompt(s)
        if use_planning:
            planning_prompt = ChatPromptTemplate.from_template(self.get_planning_template(self.language))
            main_prompt = ChatPromptTemplate.from_template(prompt_template)
        else:
            main_prompt = ChatPromptTemplate.from_template(prompt_template)

        # Create chain(s) (cached per language & planning usage; rebuilt on model swap)
        cache_key = (self.language, use_planning)
        if not hasattr(self, '_chain_cache'):
            self._chain_cache: Dict[Tuple[Optional[str], bool], Any] = {}
        cached = self._chain_cache.get(cache_key)
        if cached is None or cached[0] is not self.model:
            cached = (self.model, create_stuff_documents_chain(llm=self.model, prompt=main_prompt))
            self._chain_cache[cache_key] = cached
        main_chain = cached[1]
        docs = [Document(page_content=content)]

        try:
            logger.debug(f"Generating mind map (single-pass) for content: {content[:100]}...")
            if use_planning:
                try:
                    # Planning chain is lighter; cache separately
                    p_cache_key = (self.language, 'planning')
                    p_cached = self._chain_cache.get(p_cache_key)
                    if p_cached is None or p_cached[0] is not self.model:
                        p_cached = (self.model, create_stuff_documents_chain(llm=self.model, prompt=planning_prompt))
                        self._chain_cache[p_cache_key] = p_cached
                    planning_chain = p_cached[1]
                    _ = planning_chain.invoke({"context": docs})
                except Exception as e:
                    logger.debug(f"Planning phase failed/ignored: {e}")

            response = main_chain.invoke({"context": docs})
            logger.debug(f"Raw API response: {str(response)[:200]}...")
            mind_map_data = self.clean_and_parse_json(response)
            mind_map_data = self._post_process_mindmap(mind_map_data)

            if "nodeDataArray" not in mind_map_data:
                raise ValueError("Invalid mind map structure: missing nodeDataArray")
            if "class" not in mind_map_data:
                mind_map_data["class"] = "go.TreeModel"
            return mind_map_data
        except Exception as e:
            logger.error(f"Error in single-pass generation: {e}")
            return None
    def _merge_mindmaps(self, maps: List[Dict[str, Any]]) -> Dict[str, Any]:
        # Combine multiple mind maps into a single GoJS tree model
        merged: Dict[str, Any] = {"class": "go.TreeModel", "nodeDataArray": []}
        # Collect roots and children
        all_nodes: List[Dict[str, Any]] = []
        for m in maps:
            nodes = m.get("nodeDataArray") if isinstance(m, dict) else None
            if isinstance(nodes, list):
                all_nodes.extend([n for n in nodes if isinstance(n, dict)])
        if not all_nodes:
            return merged

        # Heuristic: create a single synthetic root and attach each map's root as a main branch
        # Don't assign brush here - let post-processing handle it
        synthetic_root = {"key": 0, "text": "\u062e\u0631\u064a\u0637\u0629 \u0634\u0627\u0645\u0644\u0629" if self.language == "arabic" else "Comprehensive Mind Map", "loc": "0 0"}
        merged_nodes: List[Dict[str, Any]] = [synthetic_root]

        # Determine next key and remap keys to keep unique
        next_key = 1
        # Group by parent=None to find roots per map (original)
        roots: List[Dict[str, Any]] = []
        for m in maps:
            nodes = m.get("nodeDataArray") if isinstance(m, dict) else None
            if not isinstance(nodes, list):
                continue
            for n in nodes:
                if n.get("parent") is None:
                    roots.append(n)

        # Map old->new keys across all nodes
        key_map: Dict[Tuple[int, int], int] = {}
        # To deduplicate by parent/text
        seen_by_parent_text: Set[Tuple[int, str]] = set()

        # Helper: normalize text for deduplication
        def norm_text(t: Any) -> str:
            s = str(t or "")
            s = re.sub(r"\s+", " ", s).strip().lower()
            return s

        # Assign main branches for each map's root under synthetic root
        for idx, m in enumerate(maps):
            nodes = m.get("nodeDataArray") if isinstance(m, dict) else None
            if not isinstance(nodes, list) or not nodes:
                continue
            # Find root
            root = None
            for n in nodes:
                if n.get("parent") is None:
                    root = n
                    break
            if root is None:
                continue
            # Create a branch node representing this chunk
            branch_key = next_key; next_key += 1
            chunk_title = root.get("text") or (f"Chunk {idx+1}")
            # Don't assign dir and brush here - let post-processing handle it
            branch = {"key": branch_key, "parent": 0, "text": chunk_title}
            if (0, norm_text(chunk_title)) not in seen_by_parent_text or not Settings.MINDMAP_DEDUPLICATE_NODES:
                merged_nodes.append(branch)
                seen_by_parent_text.add((0, norm_text(chunk_title)))
            # Build adjacency for this map
            children: Dict[Any, List[Dict[str, Any]]] = {}
            for n in nodes:
                children.setdefault(n.get("parent"), []).append(n)
            # Remap subtree under this branch
            stack = [(root, branch_key)]
            while stack:
                orig_node, new_parent = stack.pop()
                # Skip the original root since we represented it as branch
                if orig_node is root:
                    for ch in children.get(orig_node.get("key"), []):
                        stack.append((ch, branch_key))
                    continue
                new_key = next_key; next_key += 1
                # Only copy key, parent, and text - let post-processing add brush and dir
                new_node = {
                    "key": new_key,
                    "parent": new_parent,
                    "text": orig_node.get("text")
                }
                parent_text_key = (new_parent, norm_text(new_node.get("text")))
                if Settings.MINDMAP_DEDUPLICATE_NODES and parent_text_key in seen_by_parent_text:
                    # skip duplicate under same parent
                    pass
                else:
                    merged_nodes.append(new_node)
                    seen_by_parent_text.add(parent_text_key)
                    for ch in children.get(orig_node.get("key"), []):
                        stack.append((ch, new_key))

        # Enforce max nodes
        if len(merged_nodes) > Settings.MINDMAP_MAX_NODES:
            merged_nodes = merged_nodes[:Settings.MINDMAP_MAX_NODES]

        merged["nodeDataArray"] = merged_nodes
        return merged
