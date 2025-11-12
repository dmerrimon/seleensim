"""
Job Store module for managing job state persistence.

Provides a durable, file-backed job store with defensive error handling.
Supports both legacy directory-based jobs (with events.log) and simple JSON files.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
import uuid

logger = logging.getLogger(__name__)


class JobStore:
    """
    File-backed job store for durable job state management.

    Supports two storage formats:
    1. Simple: {job_id}.json - single file with job data
    2. Event-based: {job_id}/events.log - directory with event stream

    All operations are defensive with proper error handling and logging.
    """

    def __init__(self, base_dir: str = "jobs"):
        """
        Initialize JobStore with base directory.

        Args:
            base_dir: Base directory for job storage (default: "jobs")
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"📁 JobStore initialized with base_dir: {self.base_dir}")

    def _validate_job_id(self, job_id: str) -> bool:
        """
        Validate job_id is a valid UUID.

        Args:
            job_id: Job ID to validate

        Returns:
            True if valid UUID, False otherwise
        """
        try:
            uuid.UUID(job_id)
            return True
        except (ValueError, AttributeError, TypeError):
            return False

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve job data by ID.

        Checks both simple JSON files and event-based directories.

        Args:
            job_id: Job ID to retrieve

        Returns:
            Job data dict or None if not found

        Job data structure:
            {
                "job_id": str,
                "status": str ("queued"|"running"|"completed"|"failed"),
                "created_at": str (ISO timestamp),
                "updated_at": str (ISO timestamp),
                "result": dict (optional, for completed jobs),
                "error_message": str (optional, for failed jobs),
                "progress": float (optional, 0-100),
                "payload": dict (optional, original request data)
            }
        """
        if not self._validate_job_id(job_id):
            logger.warning(f"⚠️ Invalid job_id format: {job_id}")
            return None

        # Try simple JSON file first
        json_file = self.base_dir / f"{job_id}.json"
        if json_file.exists():
            try:
                with open(json_file, 'r') as f:
                    job_data = json.load(f)
                    logger.info(f"✅ Loaded job {job_id} from JSON file")
                    return job_data
            except Exception as e:
                logger.error(f"❌ Error loading job {job_id} from JSON: {e}")
                # Continue to check event-based format

        # Try event-based directory
        job_dir = self.base_dir / job_id
        if job_dir.is_dir():
            try:
                job_data = self._load_from_events(job_id)
                if job_data:
                    logger.info(f"✅ Loaded job {job_id} from events")
                    return job_data
            except Exception as e:
                logger.error(f"❌ Error loading job {job_id} from events: {e}")

        # Job not found
        logger.info(f"ℹ️ Job {job_id} not found (checked both JSON and events)")
        return None

    def _load_from_events(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Load job data from event-based directory structure.

        Args:
            job_id: Job ID

        Returns:
            Job data dict or None if not found
        """
        job_dir = self.base_dir / job_id
        events_file = job_dir / "events.log"

        if not events_file.exists():
            return None

        events = []
        try:
            with open(events_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        events.append(json.loads(line))
        except Exception as e:
            logger.error(f"❌ Error reading events for job {job_id}: {e}")
            return None

        if not events:
            return None

        # Build job data from events
        status = "running"
        progress = 0
        result = None
        error_message = None
        created_at = events[0].get('timestamp') if events else datetime.utcnow().isoformat()
        updated_at = events[-1].get('timestamp') if events else datetime.utcnow().isoformat()

        # Determine status from latest event
        if events:
            latest_event = events[-1]
            event_type = latest_event.get('type')

            if event_type == 'complete':
                status = "completed"
                result = latest_event.get('result')
                progress = 100
            elif event_type == 'progress':
                processed = latest_event.get('processed', 0)
                total = max(latest_event.get('total', 1), 1)
                progress = (processed / total) * 100
            elif event_type == 'error':
                status = "failed"
                error_message = latest_event.get('message', 'Unknown error')
            elif event_type == 'start':
                status = "running"
                progress = 0

        return {
            "job_id": job_id,
            "status": status,
            "created_at": created_at,
            "updated_at": updated_at,
            "result": result,
            "error_message": error_message,
            "progress": progress,
            "events_count": len(events)
        }

    def store_job(self, job: Dict[str, Any]) -> bool:
        """
        Store or create a new job.

        Args:
            job: Job data dict (must include 'job_id')

        Returns:
            True if stored successfully, False otherwise

        Expected job structure:
            {
                "job_id": str (required),
                "status": str (default: "queued"),
                "payload": dict (optional),
                "created_at": str (auto-generated if missing),
                "updated_at": str (auto-generated if missing)
            }
        """
        job_id = job.get('job_id')
        if not job_id:
            logger.error("❌ Cannot store job without job_id")
            return False

        if not self._validate_job_id(job_id):
            logger.error(f"❌ Invalid job_id format: {job_id}")
            return False

        # Add timestamps if missing
        now = datetime.utcnow().isoformat()
        if 'created_at' not in job:
            job['created_at'] = now
        if 'updated_at' not in job:
            job['updated_at'] = now
        if 'status' not in job:
            job['status'] = 'queued'

        # Store as simple JSON file
        json_file = self.base_dir / f"{job_id}.json"
        try:
            with open(json_file, 'w') as f:
                json.dump(job, f, indent=2)
            logger.info(f"✅ Stored job {job_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Error storing job {job_id}: {e}")
            return False

    def update_job(self, job_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update existing job with new data.

        Args:
            job_id: Job ID to update
            updates: Dict of fields to update

        Returns:
            True if updated successfully, False otherwise
        """
        if not self._validate_job_id(job_id):
            logger.error(f"❌ Invalid job_id format: {job_id}")
            return False

        # Load existing job
        job = self.get_job(job_id)
        if not job:
            logger.warning(f"⚠️ Cannot update non-existent job {job_id}")
            return False

        # Apply updates
        job.update(updates)
        job['updated_at'] = datetime.utcnow().isoformat()

        # Store updated job
        return self.store_job(job)

    def list_jobs(self, status: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        List jobs, optionally filtered by status.

        Args:
            status: Filter by status (optional)
            limit: Maximum number of jobs to return

        Returns:
            List of job data dicts
        """
        jobs = []

        # Scan for JSON files
        try:
            json_files = list(self.base_dir.glob("*.json"))
            for json_file in json_files[:limit]:
                try:
                    with open(json_file, 'r') as f:
                        job = json.load(f)
                        if status is None or job.get('status') == status:
                            jobs.append(job)
                except Exception as e:
                    logger.warning(f"⚠️ Error loading job from {json_file}: {e}")
        except Exception as e:
            logger.error(f"❌ Error listing jobs: {e}")

        return jobs[:limit]

    def delete_job(self, job_id: str) -> bool:
        """
        Delete a job (both JSON file and event directory if exists).

        Args:
            job_id: Job ID to delete

        Returns:
            True if deleted successfully, False otherwise
        """
        if not self._validate_job_id(job_id):
            logger.error(f"❌ Invalid job_id format: {job_id}")
            return False

        deleted = False

        # Delete JSON file if exists
        json_file = self.base_dir / f"{job_id}.json"
        if json_file.exists():
            try:
                json_file.unlink()
                logger.info(f"✅ Deleted job JSON file {job_id}")
                deleted = True
            except Exception as e:
                logger.error(f"❌ Error deleting job JSON file {job_id}: {e}")

        # Delete event directory if exists
        job_dir = self.base_dir / job_id
        if job_dir.is_dir():
            try:
                import shutil
                shutil.rmtree(job_dir)
                logger.info(f"✅ Deleted job directory {job_id}")
                deleted = True
            except Exception as e:
                logger.error(f"❌ Error deleting job directory {job_id}: {e}")

        return deleted


# Global JobStore instance
_job_store = None


def get_job_store(base_dir: str = "jobs") -> JobStore:
    """
    Get or create global JobStore instance.

    Args:
        base_dir: Base directory for job storage

    Returns:
        JobStore instance
    """
    global _job_store
    if _job_store is None:
        _job_store = JobStore(base_dir=base_dir)
    return _job_store
