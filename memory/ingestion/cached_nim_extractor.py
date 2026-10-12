"""Versioned real-extraction cache, with validated migration of genuine legacy responses."""

import hashlib
import json
import os
import tempfile
from pathlib import Path
from memory.ingestion.extractor import (
    BaseExtractor,
    canonicalize_entities,
    validate_extraction,
)
from memory.ingestion.nim_extractor import NIMExtractor


class CachedNIMExtractor(BaseExtractor):
    def __init__(self, cache_dir=None, delegate=None, **nim_kwargs):
        self.delegate = delegate if delegate is not None else NIMExtractor(**nim_kwargs)
        if getattr(self.delegate, "is_mock", None) is not False:
            raise ValueError("Real extraction caches cannot wrap a mock extractor.")
        self.cache_dir = Path(
            cache_dir or os.getenv("NIM_CACHE_DIR", "data/extraction_cache")
        )
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @property
    def is_mock(self):
        return False

    def _cache_path(self, text, context):
        identity = dict(
            version=2,
            model=self.delegate.model,
            endpoint=self.delegate.base_url,
            text=text,
            context=context or "",
        )
        key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        return self.cache_dir / ("nim_v2_" + key + ".json")

    def _validated(self, raw):
        if raw.get("is_mock") is not False or any(
            e.get("id") == "ent_memory" for e in raw.get("entities", [])
        ):
            raise ValueError("Cache entry lacks genuine extraction provenance.")
        return validate_extraction(
            canonicalize_entities(raw),
            extractor_name=raw.get("extractor_name", "nim:" + self.delegate.model),
            is_mock=False,
        ).to_dict()

    def _write(self, path, value):
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                dir=self.cache_dir,
                prefix="extraction_",
                suffix=".tmp",
                encoding="utf-8",
                delete=False,
            ) as stream:
                temporary = Path(stream.name)
                json.dump(value, stream, ensure_ascii=False, allow_nan=False)
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(path)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()

    def extract_entities_and_relations(self, text, context=None):
        path = self._cache_path(text, context)
        if path.exists():
            # Corrupt cache entries are reported; they do not silently trigger a billable retry.
            return self._validated(json.loads(path.read_text(encoding="utf-8")))
        if self.delegate.base_url.rstrip("/") == "https://integrate.api.nvidia.com/v1":
            key = hashlib.sha256(
                f"{self.delegate.model}\x00{text}\x00{context or ''}".encode()
            ).hexdigest()
            legacy = self.cache_dir / (
                self.delegate.model.replace("/", "_") + "_" + key + ".json"
            )
            if legacy.resolve().parent == self.cache_dir.resolve() and legacy.exists():
                value = self._validated(json.loads(legacy.read_text(encoding="utf-8")))
                self._write(path, value)
                return value
        value = self._validated(
            self.delegate.extract_entities_and_relations(text, context)
        )
        self._write(path, value)
        return value

    def judge_answer_quality(self, query, context, answer, ground_truth=""):
        return self.delegate.judge_answer_quality(query, context, answer, ground_truth)

    def detect_contradiction(self, text1, text2):
        return self.delegate.detect_contradiction(text1, text2)

    def detect_supersession(self, old_text, new_text):
        return self.delegate.detect_supersession(old_text, new_text)

    def extract_skills(self, episode_texts):
        return self.delegate.extract_skills(episode_texts)
