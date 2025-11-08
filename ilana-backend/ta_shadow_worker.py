"""
TA Shadow Worker - Asynchronous TA pipeline processing for comparison studies
Runs TA-enhanced pipeline in the background without affecting user responses
"""

import asyncio
import json
import time
import uuid
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List
from concurrent.futures import ThreadPoolExecutor
import logging
from difflib import SequenceMatcher

# Create logger
logger = logging.getLogger(__name__)

class TAShadowWorker:
    """Shadow worker for TA pipeline processing"""
    
    def __init__(self):
        self.shadow_dir = Path("shadow")
        self.shadow_dir.mkdir(exist_ok=True)
        
        # Rate limiting
        self.max_per_minute = int(os.getenv("SHADOW_MAX_PER_MIN", "30"))
        self.shadow_requests = {}
        self.shadow_lock = threading.Lock()
        
        # Thread pool for async processing
        self.executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="shadow_worker")
        
        logger.info(f"🔮 TA Shadow Worker initialized - max {self.max_per_minute} requests/min")
        
    def check_shadow_rate_limit(self) -> bool:
        """Check if shadow processing is within rate limits"""
        with self.shadow_lock:
            now = time.time()
            minute_ago = now - 60
            
            # Clean old entries
            self.shadow_requests = {
                timestamp: count for timestamp, count in self.shadow_requests.items()
                if timestamp > minute_ago
            }
            
            # Count current minute requests
            current_count = sum(self.shadow_requests.values())
            
            if current_count >= self.max_per_minute:
                logger.warning(f"🔮 Shadow rate limit exceeded: {current_count}/{self.max_per_minute}")
                return False
                
            # Record this request
            minute_bucket = int(now // 60) * 60
            self.shadow_requests[minute_bucket] = self.shadow_requests.get(minute_bucket, 0) + 1
            
            return True
    
    async def process_shadow_request(self, request_payload: Dict[str, Any], simple_output: Dict[str, Any]) -> None:
        """
        Process TA shadow request asynchronously
        
        Args:
            request_payload: Original request data  
            simple_output: Output from simple pipeline
        """
        if not self.check_shadow_rate_limit():
            logger.info("🔮 Shadow request skipped due to rate limiting")
            return
            
        request_id = str(uuid.uuid4())
        logger.info(f"🔮 Starting shadow TA processing: {request_id}")
        
        # Submit to thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            self.executor, 
            self._process_shadow_sync, 
            request_id, 
            request_payload, 
            simple_output
        )
    
    def _process_shadow_sync(self, request_id: str, request_payload: Dict[str, Any], simple_output: Dict[str, Any]) -> None:
        """Synchronous shadow processing in thread pool"""
        start_time = time.time()
        
        try:
            # Extract text from request
            text = request_payload.get("text", "")
            if not text.strip():
                logger.warning(f"🔮 Shadow {request_id}: Empty text, skipping")
                return
            
            # Run TA pipeline
            ta_output = self._run_ta_pipeline(text)
            
            # Calculate similarity score
            similarity_score = self._calculate_similarity(simple_output, ta_output)
            
            # Prepare shadow result
            shadow_result = {
                "request_id": request_id,
                "simple_output": simple_output,
                "ta_output": ta_output,
                "similarity_score": similarity_score,
                "latency_ms": int((time.time() - start_time) * 1000),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "request_metadata": {
                    "text_length": len(text),
                    "text_preview": text[:100] + "..." if len(text) > 100 else text,
                    "simple_suggestion_count": len(simple_output.get("suggestions", [])),
                    "ta_suggestion_count": len(ta_output.get("suggestions", []))
                }
            }
            
            # Save to file
            self._save_shadow_result(request_id, shadow_result)
            
            logger.info(f"🔮 Shadow {request_id} completed - similarity: {similarity_score:.3f}, latency: {shadow_result['latency_ms']}ms")
            
        except Exception as e:
            logger.error(f"🔮 Shadow {request_id} failed: {e}")
            # Save error result
            error_result = {
                "request_id": request_id,
                "simple_output": simple_output,
                "ta_output": {"error": str(e)},
                "similarity_score": 0.0,
                "latency_ms": int((time.time() - start_time) * 1000),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": True
            }
            self._save_shadow_result(request_id, error_result)
    
    def _run_ta_pipeline(self, text: str) -> Dict[str, Any]:
        """Run the complete TA pipeline"""
        try:
            # Import here to avoid circular imports
            from main import fast_ta_classifier, query_vector_db, get_regulatory_guidelines, generate_ta_aware_rewrite
            
            # Step 1: TA classification
            ta_result = asyncio.run(fast_ta_classifier(text))
            ta = ta_result["therapeutic_area"]
            
            # Step 2: Query vector DB
            exemplars = asyncio.run(query_vector_db(text, ta, "general"))
            
            # Step 3: Get regulatory guidelines  
            guidelines = get_regulatory_guidelines(ta)
            
            # Step 4: Generate TA-aware rewrite
            rewrite_result = asyncio.run(generate_ta_aware_rewrite(
                text, ta, "general", exemplars, guidelines
            ))
            
            # Format as shadow output
            return {
                "ta_classification": ta_result,
                "exemplars_found": len(exemplars),
                "guidelines_applied": len(guidelines),
                "rewrite": rewrite_result,
                "suggestions": [
                    {
                        "id": f"ta_shadow_{int(time.time())}",
                        "type": "ta_enhanced",
                        "original_text": text[:100],
                        "improved_text": rewrite_result["improved"][:100],
                        "confidence": ta_result["confidence"],
                        "therapeutic_area": ta
                    }
                ]
            }
            
        except Exception as e:
            logger.error(f"🔮 TA pipeline error: {e}")
            return {
                "error": str(e),
                "ta_classification": {"therapeutic_area": "unknown", "confidence": 0.0},
                "exemplars_found": 0,
                "guidelines_applied": 0,
                "suggestions": []
            }
    
    def _calculate_similarity(self, simple_output: Dict[str, Any], ta_output: Dict[str, Any]) -> float:
        """Calculate similarity score between simple and TA outputs"""
        try:
            # Extract suggestion texts for comparison
            simple_suggestions = simple_output.get("suggestions", [])
            ta_suggestions = ta_output.get("suggestions", [])
            
            if not simple_suggestions or not ta_suggestions:
                return 0.0
            
            # Compare first suggestion texts
            simple_text = ""
            ta_text = ""
            
            if simple_suggestions:
                simple_text = str(simple_suggestions[0].get("suggestion", ""))
            
            if ta_suggestions:
                ta_text = str(ta_suggestions[0].get("improved_text", ""))
            
            if not simple_text or not ta_text:
                return 0.0
                
            # Use SequenceMatcher for similarity
            similarity = SequenceMatcher(None, simple_text.lower(), ta_text.lower()).ratio()
            return round(similarity, 3)
            
        except Exception as e:
            logger.warning(f"🔮 Similarity calculation failed: {e}")
            return 0.0
    
    def _save_shadow_result(self, request_id: str, result: Dict[str, Any]) -> None:
        """Save shadow result to file"""
        try:
            file_path = self.shadow_dir / f"{request_id}.json"
            with open(file_path, 'w') as f:
                json.dump(result, f, indent=2, default=str)
            logger.debug(f"🔮 Shadow result saved: {file_path}")
            
        except Exception as e:
            logger.error(f"🔮 Failed to save shadow result {request_id}: {e}")
    
    def get_shadow_samples(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get shadow samples for admin API"""
        try:
            shadow_files = list(self.shadow_dir.glob("*.json"))
            shadow_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            
            samples = []
            for file_path in shadow_files[:limit]:
                try:
                    with open(file_path, 'r') as f:
                        sample = json.load(f)
                        # Add file metadata
                        sample["file_size"] = file_path.stat().st_size
                        sample["file_modified"] = datetime.fromtimestamp(
                            file_path.stat().st_mtime, tz=timezone.utc
                        ).isoformat()
                        samples.append(sample)
                except Exception as e:
                    logger.warning(f"🔮 Failed to read shadow file {file_path}: {e}")
                    continue
            
            logger.info(f"🔮 Retrieved {len(samples)} shadow samples")
            return samples
            
        except Exception as e:
            logger.error(f"🔮 Failed to get shadow samples: {e}")
            return []
    
    def get_shadow_stats(self) -> Dict[str, Any]:
        """Get shadow processing statistics"""
        try:
            shadow_files = list(self.shadow_dir.glob("*.json"))
            total_files = len(shadow_files)
            
            if total_files == 0:
                return {
                    "total_samples": 0,
                    "avg_similarity": 0.0,
                    "avg_latency_ms": 0,
                    "error_count": 0,
                    "success_rate": 0.0
                }
            
            similarities = []
            latencies = []
            error_count = 0
            
            for file_path in shadow_files[-100:]:  # Last 100 for stats
                try:
                    with open(file_path, 'r') as f:
                        sample = json.load(f)
                        
                    if sample.get("error"):
                        error_count += 1
                    else:
                        similarities.append(sample.get("similarity_score", 0.0))
                        latencies.append(sample.get("latency_ms", 0))
                        
                except Exception:
                    continue
            
            return {
                "total_samples": total_files,
                "avg_similarity": round(sum(similarities) / len(similarities), 3) if similarities else 0.0,
                "avg_latency_ms": int(sum(latencies) / len(latencies)) if latencies else 0,
                "error_count": error_count,
                "success_rate": round((len(similarities) / max(len(similarities) + error_count, 1)) * 100, 1),
                "rate_limit": f"{sum(self.shadow_requests.values())}/{self.max_per_minute}/min"
            }
            
        except Exception as e:
            logger.error(f"🔮 Failed to get shadow stats: {e}")
            return {"error": str(e)}

# Global shadow worker instance
shadow_worker = TAShadowWorker()

# Async helper for integration
async def submit_shadow_request(request_payload: Dict[str, Any], simple_output: Dict[str, Any]) -> None:
    """Submit shadow request asynchronously"""
    try:
        await shadow_worker.process_shadow_request(request_payload, simple_output)
    except Exception as e:
        logger.error(f"🔮 Shadow submission failed: {e}")

# Direct access functions for admin API
def get_shadow_samples(limit: int = 50) -> List[Dict[str, Any]]:
    """Get shadow samples for admin endpoint"""
    return shadow_worker.get_shadow_samples(limit)

def get_shadow_stats() -> Dict[str, Any]:
    """Get shadow statistics for admin endpoint"""
    return shadow_worker.get_shadow_stats()