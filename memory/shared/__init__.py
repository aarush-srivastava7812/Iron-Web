"""Authenticated shared-memory service layered over the existing memory engine."""

from memory.shared.service import SharedMemoryService, Principal, PendingMemory

__all__ = ["SharedMemoryService", "Principal", "PendingMemory"]
