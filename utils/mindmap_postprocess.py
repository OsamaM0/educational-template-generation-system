"""Mind map post-processing utilities.

This module provides a reusable function to normalize, trim, color, and balance
existing mind maps already stored in MongoDB. It is adapted from the original
MindMapTemplate._post_process_mindmap implementation so it can be applied to
legacy documents (reprocessing) without re-generating nodes via the LLM.

Design goals:
- Idempotent: running multiple times should not create drift
- Safe: never removes required keys/text fields if rebuild_parents=False
- Config-driven: uses Settings for depth, color, limits, exclusion flags
- Optional parent rebuild: can reconstruct missing parent relationships if
  provided with only key/text hierarchy (not default; requires external logic)
"""
from __future__ import annotations
from typing import Dict, Any, List, Set, Tuple
import logging
import re

from config.settings import Settings

logger = logging.getLogger(__name__)

__all__ = ["post_process_mindmap"]

def post_process_mindmap(data: Dict[str, Any]) -> Dict[str, Any]:
    """Improve balance, colors, and enforce safe limits. Output schema unchanged.

    This function expects a GoJS TreeModel-like dict with a nodeDataArray list of
    nodes shaped like: { key: <int|str>, text: <str>, parent?: <key>, dir?: str, brush?: str }

    The function will:
    - Ensure class is set
    - Optionally prune depth and example nodes (config)
    - Enforce max node count
    - Recompute depths and assign colors (brush) by depth
    - Rebalance left/right main branches from root using weighted heuristic
    - Ensure a loc on the root
    - Leave key/text/parent untouched except for pruning rules
    """
    try:
        if not isinstance(data, dict):
            return data
        nodes = data.get("nodeDataArray")
        if not isinstance(nodes, list) or not nodes:
            return data

        # 1) Enforce class
        data.setdefault("class", "go.TreeModel")

        # 2) Find root and build index
        root = None
        by_key = {}
        for n in nodes:
            if isinstance(n, dict):
                by_key[n.get("key")] = n
                if n.get("parent") is None:
                    root = n
        if root is None:
            return data

        # 3) Limit max nodes (preserve original order)
        if len(nodes) > Settings.MINDMAP_MAX_NODES:
            data["nodeDataArray"] = nodes[:Settings.MINDMAP_MAX_NODES]
            nodes = data["nodeDataArray"]
            by_key = {n.get("key"): n for n in nodes if isinstance(n, dict)}

        # Build children mapping
        children: Dict[Any, List[Dict[str, Any]]] = {}
        for n in nodes:
            children.setdefault(n.get("parent"), []).append(n)

        # Orphan pruning: remove any node whose parent key is missing (except root) including its descendants
        existing_keys = {n.get("key") for n in nodes if isinstance(n, dict)}
        # Identify orphan roots (parent not None and parent not in existing_keys)
        orphan_roots = [n for n in nodes if n.get("parent") is not None and n.get("parent") not in existing_keys]
        if orphan_roots:
            orphan_keys: Set[Any] = set()
            stack = list(orphan_roots)
            while stack:
                cur = stack.pop()
                k = cur.get("key")
                if k in orphan_keys:
                    continue
                orphan_keys.add(k)
                for ch in children.get(k, []):
                    stack.append(ch)
            if orphan_keys:
                nodes = [n for n in nodes if n.get("key") not in orphan_keys]
                data["nodeDataArray"] = nodes
                # Rebuild children after orphan removal
                children = {}
                for n in nodes:
                    children.setdefault(n.get("parent"), []).append(n)

        # Depth assignment helper
        def assign_depth(node, depth, visited):
            node["_depth"] = depth
            for ch in children.get(node.get("key"), []):
                if ch.get("key") in visited:
                    continue
                visited.add(ch.get("key"))
                assign_depth(ch, depth + 1, visited)
        assign_depth(root, 0, {root.get("key")})

        # 5) Enforce maximum depth & remove example/unrelated nodes (if depth limit enabled)
        unlimited_depth = Settings.MINDMAP_MAX_DEPTH < 0
        max_allowed_depth = max(0, Settings.MINDMAP_MAX_DEPTH) if not unlimited_depth else None
        example_keywords: List[str] = []
        if Settings.MINDMAP_EXCLUDE_EXAMPLES:
            example_keywords = [
                "مثال", "امثلة", "مثلاً", "مثل", "على سبيل المثال", "قصة", "حكاية", "سيناريو", "تجربة", "توضيح", "حالة",
                "قصص", "حكايات", "سيناريوهات", "تجارب", "توضيحات", "حالات",
                "example", "examples", "e.g.", "for example", "case", "example", "e.g", "scenario", "story", "illustration", "experiment", "case study"
            ]

        # Rebuild children mapping (fresh) for pruning logic
        children = {}
        for n in nodes:
            children.setdefault(n.get("parent"), []).append(n)

        to_keep: Set[Any] = set()
        def dfs_keep(node, depth):
            if not unlimited_depth and depth > max_allowed_depth:  # type: ignore[arg-type]
                return
            text_val = str(node.get("text") or "").strip().lower()
            if Settings.MINDMAP_EXCLUDE_EXAMPLES and any(kw in text_val for kw in example_keywords):
                return
            to_keep.add(node.get("key"))
            for ch in children.get(node.get("key"), []):
                dfs_keep(ch, depth + 1)
        dfs_keep(root, 0)

        if len(to_keep) != len(nodes) and not unlimited_depth:
            pruned = []
            for n in nodes:
                k = n.get("key")
                p = n.get("parent")
                if k in to_keep and (p is None or p in to_keep):
                    pruned.append(n)
            nodes = pruned
            data["nodeDataArray"] = nodes

        # Recompute children and depths after pruning
        children = {}
        for n in nodes:
            children.setdefault(n.get("parent"), []).append(n)
        assign_depth(root, 0, {root.get("key")})

        # 6) Color by depth
        colors = Settings.MINDMAP_COLORS
        for n in nodes:
            depth = max(0, min(n.get("_depth", 0), len(colors) - 1))
            n["brush"] = colors[depth]

        # 7) Direction balancing for main branches
        main_branches = children.get(root.get("key"), [])
        def count_descendants(node_key):
            cnt = 0
            for child in children.get(node_key, []):
                cnt += 1 + count_descendants(child.get("key"))
            return cnt
        branch_weights: List[Tuple[Dict[str, Any], int]] = []
        for branch in main_branches:
            weight = 1 + count_descendants(branch.get("key"))
            branch_weights.append((branch, weight))
        branch_weights.sort(key=lambda x: x[1], reverse=True)
        left_total = right_total = 0
        for branch, weight in branch_weights:
            if left_total <= right_total:
                branch["dir"] = "left"; left_total += weight
            else:
                branch["dir"] = "right"; right_total += weight
        def propagate_dir(node):
            for child in children.get(node.get("key"), []):
                child["dir"] = node.get("dir")
                propagate_dir(child)
        for b in main_branches:
            propagate_dir(b)

        # 8) Ensure root location
        if not root.get("loc"):
            root["loc"] = "0 0"

        # 9) Cleanup helper fields
        for n in nodes:
            n.pop("_depth", None)
            # Remove parent key entirely if it's None (root nodes)
            if n.get("parent", "__MISSING__") is None and "parent" in n:
                del n["parent"]

        return data
    except Exception as e:
        logger.debug(f"Post-process skipped due to error: {e}")
        return data
