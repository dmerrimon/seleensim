"""
Document Context Cache for Hybrid Document Intelligence

Provides caching for:
- Document processing status (fingerprint -> status)
- Processed document contexts (fingerprint -> DocumentContext)
- Cross-section conflicts (fingerprint -> List[Conflict])

Uses LRU cache with 4-hour TTL for document contexts
"""

import os
import logging
import json
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from collections import OrderedDict

logger = logging.getLogger(__name__)

# Configuration
DOCUMENT_CACHE_TTL_HOURS = int(os.getenv("DOCUMENT_CACHE_TTL_HOURS", "4"))
MAX_DOCUMENT_CACHE_SIZE = int(os.getenv("MAX_DOCUMENT_CACHE_SIZE", "100"))

# Processing status constants
STATUS_PENDING = "pending"
STATUS_PROCESSING = "processing"
STATUS_PROCESSED = "processed"
STATUS_FAILED = "failed"


@dataclass
class DocumentCacheEntry:
    """Cache entry for document context"""
    fingerprint: str
    status: str
    namespace: Optional[str]
    sections_indexed: int
    conflicts_detected: int
    section_summaries: Dict[str, str]
    created_at: datetime
    expires_at: datetime
    processing_time_ms: int
    error_message: Optional[str] = None


class DocumentContextCache:
    """
    LRU cache for document contexts

    Stores processing status and results for quick retrieval
    """

    def __init__(self, max_size: int = MAX_DOCUMENT_CACHE_SIZE):
        self.max_size = max_size
        self._cache: OrderedDict[str, DocumentCacheEntry] = OrderedDict()
        self._conflicts: Dict[str, List[Dict]] = {}  # Separate store for conflicts
        self._timelines: Dict[str, Any] = {}  # Separate store for timeline graphs

        # Statistics
        self._stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "evictions": 0,
        }

    def get_status(self, fingerprint: str) -> Optional[Dict[str, Any]]:
        """
        Get document processing status

        Returns:
            Dict with status info or None if not found
        """
        if fingerprint not in self._cache:
            self._stats["misses"] += 1
            return None

        entry = self._cache[fingerprint]

        # Check expiration
        if datetime.now() > entry.expires_at:
            del self._cache[fingerprint]
            if fingerprint in self._conflicts:
                del self._conflicts[fingerprint]
            self._stats["misses"] += 1
            return None

        # Move to end (most recent)
        self._cache.move_to_end(fingerprint)
        self._stats["hits"] += 1

        return {
            "processed": entry.status == STATUS_PROCESSED,
            "status": entry.status,
            "namespace": entry.namespace,
            "sections_indexed": entry.sections_indexed,
            "conflicts_detected": entry.conflicts_detected,
            "processing_time_ms": entry.processing_time_ms,
            "last_processed": entry.created_at.isoformat(),
            "error": entry.error_message,
        }

    def set_processing(self, fingerprint: str) -> None:
        """Mark document as currently processing"""
        now = datetime.now()
        entry = DocumentCacheEntry(
            fingerprint=fingerprint,
            status=STATUS_PROCESSING,
            namespace=None,
            sections_indexed=0,
            conflicts_detected=0,
            section_summaries={},
            created_at=now,
            expires_at=now + timedelta(hours=DOCUMENT_CACHE_TTL_HOURS),
            processing_time_ms=0,
        )
        self._set_entry(fingerprint, entry)

    def set_processed(
        self,
        fingerprint: str,
        namespace: str,
        sections_indexed: int,
        conflicts_detected: int,
        section_summaries: Dict[str, str],
        processing_time_ms: int,
        conflicts: Optional[List[Dict]] = None,
        timeline: Optional[Any] = None,
    ) -> None:
        """
        Mark document as successfully processed

        Args:
            fingerprint: Document fingerprint
            namespace: Pinecone namespace used
            sections_indexed: Number of chunks indexed
            conflicts_detected: Number of cross-section conflicts
            section_summaries: Brief summaries per section
            processing_time_ms: Total processing time
            conflicts: List of detected conflicts
            timeline: Timeline graph object (from timeline_parser.py)
        """
        now = datetime.now()
        entry = DocumentCacheEntry(
            fingerprint=fingerprint,
            status=STATUS_PROCESSED,
            namespace=namespace,
            sections_indexed=sections_indexed,
            conflicts_detected=conflicts_detected,
            section_summaries=section_summaries,
            created_at=now,
            expires_at=now + timedelta(hours=DOCUMENT_CACHE_TTL_HOURS),
            processing_time_ms=processing_time_ms,
        )
        self._set_entry(fingerprint, entry)

        # Store conflicts separately
        if conflicts:
            self._conflicts[fingerprint] = conflicts

        # Store timeline separately
        if timeline:
            self._timelines[fingerprint] = timeline

        self._stats["sets"] += 1
        timeline_str = f", timeline: {len(timeline.visits)} visits" if timeline else ""
        logger.info(
            f"Cached document context: {fingerprint[:12]}... "
            f"({sections_indexed} chunks, {conflicts_detected} conflicts{timeline_str})"
        )

    def set_failed(self, fingerprint: str, error_message: str) -> None:
        """Mark document processing as failed"""
        now = datetime.now()
        entry = DocumentCacheEntry(
            fingerprint=fingerprint,
            status=STATUS_FAILED,
            namespace=None,
            sections_indexed=0,
            conflicts_detected=0,
            section_summaries={},
            created_at=now,
            expires_at=now + timedelta(hours=1),  # Shorter TTL for failures
            processing_time_ms=0,
            error_message=error_message,
        )
        self._set_entry(fingerprint, entry)

    def _set_entry(self, fingerprint: str, entry: DocumentCacheEntry) -> None:
        """Internal method to set cache entry with LRU eviction"""
        # Remove if exists (to update position)
        if fingerprint in self._cache:
            del self._cache[fingerprint]

        # Evict LRU if at capacity
        if len(self._cache) >= self.max_size:
            evicted_fp, _ = self._cache.popitem(last=False)
            if evicted_fp in self._conflicts:
                del self._conflicts[evicted_fp]
            if evicted_fp in self._timelines:
                del self._timelines[evicted_fp]
            self._stats["evictions"] += 1
            logger.debug(f"Evicted LRU document cache entry: {evicted_fp[:12]}...")

        self._cache[fingerprint] = entry

    def get_conflicts(self, fingerprint: str) -> List[Dict]:
        """Get cross-section conflicts for a document"""
        return self._conflicts.get(fingerprint, [])

    def get_timeline(self, fingerprint: str) -> Optional[Any]:
        """Get timeline graph for a document"""
        return self._timelines.get(fingerprint, None)

    def get_section_summaries(self, fingerprint: str) -> Dict[str, str]:
        """Get section summaries for a document"""
        if fingerprint in self._cache:
            return self._cache[fingerprint].section_summaries
        return {}

    def is_processing(self, fingerprint: str) -> bool:
        """Check if document is currently being processed"""
        if fingerprint in self._cache:
            return self._cache[fingerprint].status == STATUS_PROCESSING
        return False

    def clear(self) -> None:
        """Clear all cached entries"""
        self._cache.clear()
        self._conflicts.clear()
        self._timelines.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / total if total > 0 else 0

        return {
            "entries": len(self._cache),
            "max_size": self.max_size,
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "hit_rate": round(hit_rate * 100, 1),
            "sets": self._stats["sets"],
            "evictions": self._stats["evictions"],
            "conflicts_stored": len(self._conflicts),
            "timelines_stored": len(self._timelines),
        }


# Singleton instance
_document_cache: Optional[DocumentContextCache] = None


def get_document_cache() -> DocumentContextCache:
    """Get singleton document cache instance"""
    global _document_cache
    if _document_cache is None:
        _document_cache = DocumentContextCache()
        logger.info("Initialized document context cache")
    return _document_cache


# Convenience functions
def get_document_status(fingerprint: str) -> Optional[Dict[str, Any]]:
    """Get document processing status from cache"""
    return get_document_cache().get_status(fingerprint)


def set_document_processing(fingerprint: str) -> None:
    """Mark document as processing"""
    get_document_cache().set_processing(fingerprint)


def set_document_processed(
    fingerprint: str,
    namespace: str,
    sections_indexed: int,
    conflicts_detected: int,
    section_summaries: Dict[str, str],
    processing_time_ms: int,
    conflicts: Optional[List[Dict]] = None,
    timeline: Optional[Any] = None,
) -> None:
    """Mark document as processed and cache results"""
    get_document_cache().set_processed(
        fingerprint=fingerprint,
        namespace=namespace,
        sections_indexed=sections_indexed,
        conflicts_detected=conflicts_detected,
        section_summaries=section_summaries,
        processing_time_ms=processing_time_ms,
        conflicts=conflicts,
        timeline=timeline,
    )


def set_document_failed(fingerprint: str, error_message: str) -> None:
    """Mark document processing as failed"""
    get_document_cache().set_failed(fingerprint, error_message)


def get_document_conflicts(fingerprint: str) -> List[Dict]:
    """Get cross-section conflicts for a document"""
    return get_document_cache().get_conflicts(fingerprint)


def get_document_timeline(fingerprint: str) -> Optional[Any]:
    """Get timeline graph for a document"""
    return get_document_cache().get_timeline(fingerprint)


def is_document_processing(fingerprint: str) -> bool:
    """Check if document is currently being processed"""
    return get_document_cache().is_processing(fingerprint)


# Export
__all__ = [
    "get_document_cache",
    "get_document_status",
    "set_document_processing",
    "set_document_processed",
    "set_document_failed",
    "get_document_conflicts",
    "get_document_timeline",
    "is_document_processing",
    "DocumentContextCache",
    "STATUS_PENDING",
    "STATUS_PROCESSING",
    "STATUS_PROCESSED",
    "STATUS_FAILED",
]
