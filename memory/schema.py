"""Shared record fields; additional metadata cannot replace these values."""

RESERVED_FIELDS = {
    "memory_id",
    "text",
    "entity_ids",
    "valid_from",
    "valid_until",
    "importance",
    "timestamp",
}


def validate_metadata(metadata):
    if metadata is not None and not isinstance(metadata, dict):
        raise ValueError("Metadata must be a dictionary.")
    conflicts = RESERVED_FIELDS.intersection(metadata or {})
    if conflicts:
        raise ValueError(
            f"Metadata cannot overwrite record fields: {sorted(conflicts)}"
        )
