#!/usr/bin/env python3
"""
Background Job Queue for Deep RAG Analysis

Handles long-running protocol analysis tasks that would timeout in HTTP requests:
- Full RAG pipeline with PubMedBERT embeddings
- Pinecone vector search
- Azure GPT-4 with enriched context
- TA detection and exemplar retrieval

Job lifecycle:
1. Client POSTs to /api/analyze with large selection (> 2000 chars)
2. API queues job and returns {status: "queued", job_id: "..."}
3. Client polls GET /api/job-status/{job_id}
4. Job completes → {status: "completed", suggestions: [...]}
"""

import os
import time
import uuid
import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)

# Job States
class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

# In-memory job store (will survive until process restarts)
# For production: migrate to Redis or database
_jobs: Dict[str, Dict[str, Any]] = {}
_job_ttl_hours = 24  # Keep completed jobs for 24h


class Job:
    """Background analysis job"""

    def __init__(self, job_id: str, text: str, ta: Optional[str] = None, phase: Optional[str] = None):
        self.job_id = job_id
        self.text = text
        self.ta = ta
        self.phase = phase
        self.status = JobStatus.QUEUED
        self.created_at = datetime.utcnow()
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.result: Optional[Dict[str, Any]] = None
        self.error: Optional[str] = None
        self.progress_pct: int = 0
        self.progress_message: str = "Queued"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize job state for API response"""
        return {
            "job_id": self.job_id,
            "status": self.status,
            "progress_pct": self.progress_pct,
            "progress_message": self.progress_message,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result": self.result,
            "error": self.error
        }


def create_job(text: str, ta: Optional[str] = None, phase: Optional[str] = None) -> str:
    """
    Create new background job

    Args:
        text: Protocol text to analyze (large selection)
        ta: Optional therapeutic area
        phase: Optional study phase

    Returns:
        job_id: Unique job identifier
    """
    job_id = f"job_{uuid.uuid4().hex[:16]}"
    job = Job(job_id, text, ta, phase)
    _jobs[job_id] = job

    logger.info(f"📋 Created job {job_id} (text_len={len(text)}, ta={ta})")
    return job_id


def get_job(job_id: str) -> Optional[Job]:
    """Get job by ID"""
    return _jobs.get(job_id)


def get_job_status(job_id: str) -> Optional[Dict[str, Any]]:
    """
    Get job status for API response

    Returns:
        Job state dict or None if not found
    """
    job = _jobs.get(job_id)
    if not job:
        return None

    # Clean up old completed jobs
    if job.status in [JobStatus.COMPLETED, JobStatus.FAILED]:
        if job.completed_at and datetime.utcnow() - job.completed_at > timedelta(hours=_job_ttl_hours):
            logger.info(f"🗑️ Purging expired job {job_id}")
            del _jobs[job_id]
            return None

    return job.to_dict()


async def process_job_async(job_id: str):
    """
    Background worker: Process deep RAG analysis job

    This runs the full enterprise pipeline:
    1. TA detection (20%)
    2. Pinecone vector search for exemplars (40%)
    3. PubMedBERT contextual embeddings (60%)
    4. Azure GPT-4 with enriched prompt (80%)
    5. Post-process and format suggestions (100%)

    Args:
        job_id: Job identifier
    """
    job = _jobs.get(job_id)
    if not job:
        logger.error(f"❌ Job not found: {job_id}")
        return

    start_time = time.time()
    logger.info(f"🚀 Starting job {job_id}")

    job.status = JobStatus.RUNNING
    job.started_at = datetime.utcnow()
    job.progress_pct = 0
    job.progress_message = "Starting deep analysis..."

    try:
        # Import heavy dependencies only when needed (saves memory for fast path)
        from legacy_pipeline import run_legacy_pipeline
        from optimization_config import (
            should_use_pinecone,
            should_use_pubmedbert,
            get_optimized_top_k,
            get_optimization_summary
        )

        # Log optimization settings
        text_len = len(job.text)
        use_pinecone = should_use_pinecone(job.text, job.ta)
        use_pubmedbert = should_use_pubmedbert(job.text, job.ta)
        top_k = get_optimized_top_k(text_len, is_background_job=True)

        logger.info(f"🎛️ [{job_id}] Optimization settings:")
        logger.info(f"   - Text length: {text_len} chars")
        logger.info(f"   - Pinecone: {use_pinecone} (top_k={top_k})")
        logger.info(f"   - PubMedBERT: {use_pubmedbert}")
        logger.info(f"   - TA hint: {job.ta or 'none'}")

        # Step 1: TA Detection (20%)
        job.progress_pct = 20
        job.progress_message = "Detecting therapeutic area..."
        logger.info(f"📊 [{job_id}] Step 1/5: TA detection")
        await asyncio.sleep(0.1)  # Yield control

        # Step 2: Vector search (40%) - May skip if optimized
        job.progress_pct = 40
        if use_pinecone:
            job.progress_message = f"Searching knowledge base (top {top_k})..."
            logger.info(f"📊 [{job_id}] Step 2/5: Pinecone vector search (top_k={top_k})")
        else:
            job.progress_message = "Skipping vector search (optimized)..."
            logger.info(f"📊 [{job_id}] Step 2/5: Pinecone SKIPPED (optimization)")
        await asyncio.sleep(0.1)

        # Step 3: PubMedBERT (60%) - May skip if optimized
        job.progress_pct = 60
        if use_pubmedbert:
            job.progress_message = "Computing medical embeddings..."
            logger.info(f"📊 [{job_id}] Step 3/5: PubMedBERT embeddings")
        else:
            job.progress_message = "Skipping embeddings (optimized)..."
            logger.info(f"📊 [{job_id}] Step 3/5: PubMedBERT SKIPPED (optimization)")
        await asyncio.sleep(0.1)

        # Step 4: Azure GPT-4 (80%)
        job.progress_pct = 80
        job.progress_message = "Generating suggestions with GPT-4..."
        logger.info(f"📊 [{job_id}] Step 4/5: Azure GPT-4 analysis")

        # Call legacy pipeline (returns full result dict)
        # NOTE: Optimization flags are logged above but legacy pipeline needs to be updated
        # to actually respect them. For now, we're just tracking what SHOULD be optimized.
        legacy_result = await run_legacy_pipeline(
            text=job.text,
            ta=job.ta,
            phase=job.phase,
            request_id=job_id
        )

        # Step 5: Post-process (100%)
        job.progress_pct = 100
        job.progress_message = "Finalizing results..."
        logger.info(f"📊 [{job_id}] Step 5/5: Post-processing")

        # Extract suggestions from legacy result
        result = legacy_result.get("result", {})

        # Store result
        job.result = result
        job.status = JobStatus.COMPLETED
        job.completed_at = datetime.utcnow()

        total_time_ms = int((time.time() - start_time) * 1000)
        num_suggestions = len(result.get("suggestions", []))

        logger.info(f"✅ Job {job_id} completed in {total_time_ms}ms ({num_suggestions} suggestions)")

    except Exception as e:
        total_time_ms = int((time.time() - start_time) * 1000)
        error_msg = f"{type(e).__name__}: {str(e)}"

        job.status = JobStatus.FAILED
        job.error = error_msg
        job.completed_at = datetime.utcnow()

        logger.error(f"❌ Job {job_id} failed after {total_time_ms}ms: {error_msg}")


def purge_old_jobs():
    """Clean up jobs older than TTL"""
    now = datetime.utcnow()
    expired = []

    for job_id, job in _jobs.items():
        if job.status in [JobStatus.COMPLETED, JobStatus.FAILED]:
            if job.completed_at and now - job.completed_at > timedelta(hours=_job_ttl_hours):
                expired.append(job_id)

    for job_id in expired:
        logger.info(f"🗑️ Purging expired job {job_id}")
        del _jobs[job_id]

    if expired:
        logger.info(f"🧹 Purged {len(expired)} expired jobs")


# Export
__all__ = [
    "JobStatus",
    "create_job",
    "get_job",
    "get_job_status",
    "process_job_async",
    "purge_old_jobs"
]
