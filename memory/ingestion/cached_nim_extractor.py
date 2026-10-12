"""Disk-cached wrapper around the real NVIDIA NIM extractor.

Every extraction result is cached by (model, text, context) hash so re-runs of
downstream stages (graph build, ablation modes, rerank tuning) never re-hit the
NIM API. Cache entries are written atomically and are clearly marked
is_mock=False: cached real extraction is real extraction, not mock output.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional

from memory.ingestion.extractor import BaseExtractor
from memory.ingestion.nim_extractor import NIMExtractor


DEFAULT_CACHE_DIR = os.path.join("data", "extraction_cache")


class CachedNIMExtractor(BaseExtractor):
    """
    Real NIM extractor with a transparent on-disk cache.

    - cache hit  -> returns the stored real NIM response (no API call)
    - cache miss -> calls NIM, stores the raw result, returns it
    """

    def __init__(
        self,
        cache_dir: Optional[str] = None,
        delegate: Optional[NIMExtractor] = None,
        **nim_kwargs,
    ):
        self.delegate = delegate or NIMExtractor(**nim_kwargs)
        self.cache_dir = Path(cache_dir or os.getenv("NIM_CACHE_DIR", DEFAULT_CACHE_DIR))
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @property
    def is_mock(self) -> bool:
        return False

    def _cache_path(self, text: str, context: Optional[str]) -> Path:
        key = hashlib.sha256(
            f"{self.delegate.model}\x00{text}\x00{context or ''}".encode("utf-8")
        ).hexdigest()
        return self.cache_dir / f"{self.delegate.model.replace('/', '_')}_{key}.json"

    def extract_entities_and_relations(
        self,
        text: str,
        context: Optional[str] = None
    ) -> Dict[str, Any]:
        path = self._cache_path(text, context)
        if path.exists():
            try:
                cached = json.loads(path.read_text(encoding="utf-8"))
                if cached.get("is_mock") is False:
                    return cached
            except Exception:
                pass  # corrupt cache entry -> re-extract
        result = self.delegate.extract_entities_and_relations(text, context)
        # Only cache meaningful extractions.  A result consisting solely of the
        # validation fallback entity ("ent_memory") with no relations usually
        # means the model call failed transiently - re-extract next time
        # instead of poisoning the cache.
        has_real_entity = any(e.get("id") != "ent_memory" for e in result.get("entities", []))
        if has_real_entity or result.get("relations"):
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
            tmp.replace(path)
        return result

    def judge_answer_quality(
        self,
        query: str,
        context: str,
        answer: str,
        ground_truth: str = ""
    ) -> Dict[str, float]:
        return self.delegate.judge_answer_quality(query, context, answer, ground_truth)

    def detect_contradiction(self, text1: str, text2: str) -> Dict[str, Any]:
        return self.delegate.detect_contradiction(text1, text2)

    def detect_supersession(self, old_text: str, new_text: str) -> Dict[str, Any]:
        return self.delegate.detect_supersession(old_text, new_text)

    def extract_skills(self, episode_texts: List[str]) -> List[Dict[str, Any]]:
        return self.delegate.extract_skills(episode_texts)
