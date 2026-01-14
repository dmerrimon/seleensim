"""
Document Processor for Hybrid Document Intelligence

Processes full protocol documents on add-in load:
- Section detection (objectives, eligibility, endpoints, statistics, safety, schedule)
- Smart chunking with overlap
- PubMedBERT embedding generation
- Pinecone indexing in document-specific namespace

Usage:
    Called automatically by /api/document-context/process endpoint

    from document_processor import process_document
    result = await process_document(text, fingerprint, request_id)
"""

import os
import re
import asyncio
import logging
import hashlib
import time
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Import existing infrastructure
from fast_rag import get_pubmedbert_embedding, _init_pinecone, _pinecone_index

# Configuration
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "")
DOCUMENT_NAMESPACE_PREFIX = "doc_"

# Chunking parameters (match protocol_indexer.py)
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
MAX_CHUNKS_PER_DOCUMENT = 200


@dataclass
class ProtocolSection:
    """Represents a detected protocol section"""
    section_type: str
    title: str
    content: str
    start_index: int
    end_index: int


@dataclass
class DocumentChunk:
    """Represents a chunk ready for indexing"""
    chunk_id: str
    section_type: str
    section_title: str
    chunk_index: int
    total_chunks: int
    text: str
    embedding: Optional[List[float]] = None


@dataclass
class DocumentContext:
    """Complete processed document context"""
    fingerprint: str
    namespace: str
    sections: Dict[str, List[str]]  # section_type -> list of text chunks
    section_summaries: Dict[str, str]  # section_type -> summary
    total_chunks: int
    processing_time_ms: int
    conflicts: List[Dict] = field(default_factory=list)
    timeline: Optional[Any] = None  # Timeline object from timeline_parser.py


# Section detection patterns (order matters - more specific patterns first)
SECTION_PATTERNS = {
    "objectives": [
        r"(?im)^(?:\d+\.?\s*)?(?:study\s+)?objectives?\s*$",
        r"(?im)^(?:\d+\.?\s*)?primary\s+objectives?\s*$",
        r"(?im)^(?:\d+\.?\s*)?secondary\s+objectives?\s*$",
        r"(?im)^\#{1,3}\s*(?:study\s+)?objectives?",
        r"(?im)purpose\s+(?:of\s+)?(?:the\s+)?study",
    ],
    "eligibility": [
        r"(?im)^(?:\d+\.?\s*)?eligibility\s+criteria\s*$",
        r"(?im)^(?:\d+\.?\s*)?inclusion\s+criteria\s*$",
        r"(?im)^(?:\d+\.?\s*)?exclusion\s+criteria\s*$",
        r"(?im)^(?:\d+\.?\s*)?inclusion\s+and\s+exclusion",
        r"(?im)^\#{1,3}\s*eligibility",
        r"(?im)^\#{1,3}\s*(?:inclusion|exclusion)\s+criteria",
        r"(?im)subject\s+selection",
        r"(?im)patient\s+(?:selection|population)",
    ],
    "endpoints": [
        r"(?im)^(?:\d+\.?\s*)?(?:study\s+)?endpoints?\s*$",
        r"(?im)^(?:\d+\.?\s*)?primary\s+endpoints?\s*$",
        r"(?im)^(?:\d+\.?\s*)?secondary\s+endpoints?\s*$",
        r"(?im)^\#{1,3}\s*(?:study\s+)?endpoints?",
        r"(?im)^(?:\d+\.?\s*)?outcome\s+measures?\s*$",
        r"(?im)efficacy\s+(?:endpoints?|assessments?)",
    ],
    "statistics": [
        r"(?im)^(?:\d+\.?\s*)?statistical\s+(?:analysis|methods?|considerations?)\s*$",
        r"(?im)^(?:\d+\.?\s*)?sample\s+size\s*$",
        r"(?im)^\#{1,3}\s*statistical",
        r"(?im)^(?:\d+\.?\s*)?data\s+analysis\s*$",
        r"(?im)analysis\s+populations?",
        r"(?im)power\s+(?:calculation|analysis)",
    ],
    "safety": [
        r"(?im)^(?:\d+\.?\s*)?safety\s*$",
        r"(?im)^(?:\d+\.?\s*)?(?:adverse\s+)?(?:events?|reactions?)\s*$",
        r"(?im)^\#{1,3}\s*safety",
        r"(?im)safety\s+(?:monitoring|assessments?|reporting)",
        r"(?im)^(?:\d+\.?\s*)?SAE\s+reporting",
        r"(?im)pharmacovigilance",
    ],
    "schedule": [
        r"(?im)^(?:\d+\.?\s*)?(?:study\s+)?schedule\s*$",
        r"(?im)^(?:\d+\.?\s*)?visit\s+schedule\s*$",
        r"(?im)^\#{1,3}\s*(?:study\s+)?schedule",
        r"(?im)schedule\s+of\s+(?:assessments?|events?|activities)",
        r"(?im)time\s+and\s+events?",
        r"(?im)study\s+procedures?\s+(?:by\s+)?visit",
    ],
    "demographics": [
        r"(?im)^(?:\d+\.?\s*)?demographics?\s*$",
        r"(?im)^\#{1,3}\s*demographics?",
        r"(?im)baseline\s+characteristics",
        r"(?im)subject\s+demographics",
    ],
}

# Section relationships for cross-section analysis
SECTION_RELATIONSHIPS = {
    "objectives": ["endpoints", "statistics"],
    "eligibility": ["endpoints", "safety", "statistics"],
    "endpoints": ["objectives", "statistics", "schedule"],
    "statistics": ["endpoints", "objectives", "eligibility"],
    "safety": ["schedule", "eligibility"],
    "schedule": ["endpoints", "safety"],
    "demographics": ["eligibility", "statistics"],
}


def calculate_fingerprint(text: str) -> str:
    """
    Calculate document fingerprint for caching

    Uses first 5000 chars + length + last 2000 chars for quick identification
    """
    preview = text[:5000] + str(len(text)) + text[-2000:] if len(text) > 7000 else text
    return hashlib.sha256(preview.encode()).hexdigest()[:32]


def detect_sections(text: str) -> List[ProtocolSection]:
    """
    Detect protocol sections from document text

    Returns list of ProtocolSection objects with section type, content, and positions
    """
    sections = []
    lines = text.split('\n')

    current_section = None
    current_content = []
    current_start = 0
    char_position = 0

    for line_idx, line in enumerate(lines):
        line_stripped = line.strip()

        # Check if line matches any section pattern
        matched_type = None
        for section_type, patterns in SECTION_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, line_stripped):
                    matched_type = section_type
                    break
            if matched_type:
                break

        if matched_type:
            # Save previous section if exists
            if current_section and current_content:
                section_text = '\n'.join(current_content).strip()
                if len(section_text) > 50:  # Minimum meaningful content
                    sections.append(ProtocolSection(
                        section_type=current_section,
                        title=current_content[0] if current_content else current_section,
                        content=section_text,
                        start_index=current_start,
                        end_index=char_position
                    ))

            # Start new section
            current_section = matched_type
            current_content = [line]
            current_start = char_position
        elif current_section:
            # Add to current section
            current_content.append(line)

        char_position += len(line) + 1  # +1 for newline

    # Save final section
    if current_section and current_content:
        section_text = '\n'.join(current_content).strip()
        if len(section_text) > 50:
            sections.append(ProtocolSection(
                section_type=current_section,
                title=current_content[0] if current_content else current_section,
                content=section_text,
                start_index=current_start,
                end_index=char_position
            ))

    # If no sections detected, treat entire document as "general"
    if not sections and len(text.strip()) > 100:
        sections.append(ProtocolSection(
            section_type="general",
            title="Protocol Content",
            content=text,
            start_index=0,
            end_index=len(text)
        ))

    logger.info(f"Detected {len(sections)} sections: {[s.section_type for s in sections]}")
    return sections


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE) -> List[str]:
    """
    Split text into overlapping chunks with sentence boundary awareness

    Matches protocol_indexer.py chunking strategy
    """
    chunks = []
    start = 0
    text_length = len(text)

    while start < text_length:
        end = start + chunk_size

        # Try to break at sentence boundary
        if end < text_length:
            # Look for period followed by space or newline
            period_idx = text.rfind('. ', start, end)
            if period_idx != -1 and period_idx > start + chunk_size // 2:
                end = period_idx + 1

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        # Move start forward with overlap
        start = end - CHUNK_OVERLAP if end < text_length else text_length

    return chunks


def chunk_section(section: ProtocolSection) -> List[DocumentChunk]:
    """
    Chunk a protocol section into DocumentChunk objects
    """
    text_chunks = chunk_text(section.content)

    document_chunks = []
    for idx, text in enumerate(text_chunks):
        chunk = DocumentChunk(
            chunk_id=f"{section.section_type}_{idx:03d}",
            section_type=section.section_type,
            section_title=section.title[:100],
            chunk_index=idx,
            total_chunks=len(text_chunks),
            text=text
        )
        document_chunks.append(chunk)

    return document_chunks


async def embed_chunks(chunks: List[DocumentChunk], request_id: str) -> List[DocumentChunk]:
    """
    Generate PubMedBERT embeddings for all chunks

    Processes in batches to avoid rate limits
    """
    embedded_chunks = []
    batch_size = 3  # Reduced from 10 to avoid HuggingFace rate limits

    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]

        # Process batch in parallel
        tasks = [
            get_pubmedbert_embedding(chunk.text, f"{request_id}_chunk_{chunk.chunk_id}")
            for chunk in batch
        ]
        embeddings = await asyncio.gather(*tasks)

        for chunk, embedding in zip(batch, embeddings):
            if embedding:
                chunk.embedding = embedding
                embedded_chunks.append(chunk)
            else:
                logger.warning(f"Failed to embed chunk {chunk.chunk_id}")

        # Small delay between batches to avoid rate limits
        if i + batch_size < len(chunks):
            await asyncio.sleep(0.5)  # Increased from 0.1s to give rate limiter time to reset

    return embedded_chunks


async def index_document_chunks(
    chunks: List[DocumentChunk],
    fingerprint: str,
    request_id: str
) -> Tuple[str, int]:
    """
    Index document chunks into Pinecone with document-specific namespace

    Returns:
        Tuple of (namespace, indexed_count)
    """
    if not _init_pinecone():
        logger.error(f"[{request_id}] Pinecone not available for document indexing")
        return "", 0

    namespace = f"{DOCUMENT_NAMESPACE_PREFIX}{fingerprint[:16]}"

    vectors = []
    for chunk in chunks:
        if not chunk.embedding:
            continue

        vector_id = f"{namespace}_{chunk.chunk_id}"

        vectors.append({
            "id": vector_id,
            "values": chunk.embedding,
            "metadata": {
                "document_fingerprint": fingerprint,
                "section_type": chunk.section_type,
                "section_title": chunk.section_title,
                "chunk_index": chunk.chunk_index,
                "total_chunks": chunk.total_chunks,
                "text": chunk.text[:500],  # Preview
                "full_text": chunk.text,
            }
        })

    # Batch upsert
    batch_size = 100
    indexed_count = 0

    for i in range(0, len(vectors), batch_size):
        batch = vectors[i:i + batch_size]
        try:
            _pinecone_index.upsert(vectors=batch, namespace=namespace)
            indexed_count += len(batch)
            logger.info(f"[{request_id}] Indexed batch {i//batch_size + 1}: {len(batch)} vectors")
        except Exception as e:
            logger.error(f"[{request_id}] Failed to index batch: {e}")

    logger.info(f"[{request_id}] Indexed {indexed_count} chunks to namespace '{namespace}'")
    return namespace, indexed_count


def extract_section_summaries(sections: List[ProtocolSection]) -> Dict[str, str]:
    """
    Extract brief summaries from each section (first 500 chars)

    Used for cross-section context injection
    """
    summaries = {}
    for section in sections:
        # Get first 500 chars, try to end at sentence
        summary = section.content[:500]
        period_idx = summary.rfind('. ')
        if period_idx > 200:
            summary = summary[:period_idx + 1]
        summaries[section.section_type] = summary

    return summaries


async def process_document(
    text: str,
    fingerprint: str,
    request_id: str = "unknown",
    skip_indexing: bool = False
) -> DocumentContext:
    """
    Main document processing pipeline

    Args:
        text: Full protocol document text
        fingerprint: Pre-calculated document fingerprint
        request_id: Request tracking ID
        skip_indexing: If True, skip Pinecone indexing (for testing)

    Returns:
        DocumentContext with processed document information
    """
    start_time = time.time()
    logger.info(f"[{request_id}] Starting document processing ({len(text):,} chars)")

    # 1. Detect sections
    sections = detect_sections(text)
    logger.info(f"[{request_id}] Detected {len(sections)} sections")

    # 2. Chunk all sections
    all_chunks = []
    sections_dict = {}

    for section in sections:
        section_chunks = chunk_section(section)
        all_chunks.extend(section_chunks)
        sections_dict[section.section_type] = [c.text for c in section_chunks]

    # Limit total chunks
    if len(all_chunks) > MAX_CHUNKS_PER_DOCUMENT:
        logger.warning(f"[{request_id}] Truncating chunks from {len(all_chunks)} to {MAX_CHUNKS_PER_DOCUMENT}")
        all_chunks = all_chunks[:MAX_CHUNKS_PER_DOCUMENT]

    logger.info(f"[{request_id}] Created {len(all_chunks)} chunks")

    # 3. Generate embeddings
    embedded_chunks = await embed_chunks(all_chunks, request_id)
    logger.info(f"[{request_id}] Generated embeddings for {len(embedded_chunks)} chunks")

    # 4. Index to Pinecone
    namespace = f"{DOCUMENT_NAMESPACE_PREFIX}{fingerprint[:16]}"
    indexed_count = 0

    if not skip_indexing and embedded_chunks:
        namespace, indexed_count = await index_document_chunks(
            embedded_chunks, fingerprint, request_id
        )

    # 5. Extract section summaries
    section_summaries = extract_section_summaries(sections)

    # 6. Parse timeline from schedule section (if available)
    timeline_graph = None
    if "schedule" in sections_dict:
        try:
            from timeline_parser import parse_timeline
            schedule_text = " ".join(sections_dict["schedule"])
            timeline_graph = parse_timeline(schedule_text, request_id)
            if timeline_graph:
                logger.info(f"[{request_id}] Parsed timeline: {len(timeline_graph.visits)} visits, "
                           f"{len(timeline_graph.conditional_visits)} conditional, "
                           f"confidence={timeline_graph.parse_confidence:.2f}")
                if timeline_graph.warnings:
                    logger.warning(f"[{request_id}] Timeline parse warnings: {timeline_graph.warnings}")
        except Exception as e:
            logger.warning(f"[{request_id}] Timeline parsing failed: {e}")
            timeline_graph = None  # Graceful degradation

    processing_time_ms = int((time.time() - start_time) * 1000)
    logger.info(f"[{request_id}] Document processing complete in {processing_time_ms}ms")

    return DocumentContext(
        fingerprint=fingerprint,
        namespace=namespace,
        sections=sections_dict,
        section_summaries=section_summaries,
        total_chunks=indexed_count,
        processing_time_ms=processing_time_ms,
        conflicts=[],  # Will be populated by cross_section_engine
        timeline=timeline_graph  # NEW: Add timeline graph
    )


async def get_document_sections(
    namespace: str,
    section_types: List[str],
    limit_per_section: int = 3,
    request_id: str = "unknown"
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Retrieve indexed sections from a document namespace

    Args:
        namespace: Document-specific Pinecone namespace
        section_types: List of section types to retrieve
        limit_per_section: Max chunks per section
        request_id: Request tracking ID

    Returns:
        Dict mapping section_type to list of chunk metadata
    """
    if not _init_pinecone():
        logger.warning(f"[{request_id}] Pinecone not available")
        return {}

    results = {}

    for section_type in section_types:
        try:
            # Query by section type filter
            # Note: Pinecone doesn't support direct metadata filtering in query
            # We'll fetch and filter client-side
            query_result = _pinecone_index.query(
                vector=[0.0] * 768,  # Dummy vector
                top_k=50,
                namespace=namespace,
                include_metadata=True,
                filter={"section_type": {"$eq": section_type}}
            )

            chunks = []
            for match in query_result.matches[:limit_per_section]:
                chunks.append({
                    "text": match.metadata.get("full_text", match.metadata.get("text", "")),
                    "section_title": match.metadata.get("section_title", ""),
                    "chunk_index": match.metadata.get("chunk_index", 0),
                })

            if chunks:
                results[section_type] = chunks

        except Exception as e:
            logger.warning(f"[{request_id}] Failed to retrieve {section_type}: {e}")

    return results


# Export main functions
__all__ = [
    "process_document",
    "detect_sections",
    "calculate_fingerprint",
    "get_document_sections",
    "DocumentContext",
    "ProtocolSection",
    "SECTION_RELATIONSHIPS",
]
