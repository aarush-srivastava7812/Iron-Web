"""Extraction and ingestion interfaces with optional hosted clients."""

from importlib import import_module

_EXPORTS = {
    "BaseExtractor": ("memory.ingestion.extractor", "BaseExtractor"),
    "ExtractionResult": ("memory.ingestion.extractor", "ExtractionResult"),
    "ExtractedEntity": ("memory.ingestion.extractor", "ExtractedEntity"),
    "ExtractedRelation": ("memory.ingestion.extractor", "ExtractedRelation"),
    "ExtractedTemporal": ("memory.ingestion.extractor", "ExtractedTemporal"),
    "validate_extraction": ("memory.ingestion.extractor", "validate_extraction"),
    "NIMExtractor": ("memory.ingestion.nim_extractor", "NIMExtractor"),
    "CachedNIMExtractor": (
        "memory.ingestion.cached_nim_extractor",
        "CachedNIMExtractor",
    ),
    "IngestionPipeline": ("memory.ingestion.pipeline", "IngestionPipeline"),
}
__all__ = list(_EXPORTS)


def __getattr__(name):
    if name not in _EXPORTS:
        raise AttributeError(name)
    module, attribute = _EXPORTS[name]
    value = getattr(import_module(module), attribute)
    globals()[name] = value
    return value
