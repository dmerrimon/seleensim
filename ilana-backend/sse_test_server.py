#!/usr/bin/env python3
"""
Simple SSE Test Server for Ilana Job Streaming
Emits sample events for manual testing of the SSE functionality
"""

import asyncio
import json
import time
import uuid
import requests
from pathlib import Path

# Configuration
BASE_URL = "http://127.0.0.1:8000"
TEST_JOB_ID = "test-job-" + str(uuid.uuid4())[:8]

def emit_event(job_id: str, event_data: dict):
    """Send an event to the SSE server"""
    try:
        response = requests.post(
            f"{BASE_URL}/api/job/{job_id}/emit-event",
            json=event_data,
            timeout=5
        )
        if response.ok:
            print(f"✅ Emitted: {event_data['type']} - {response.json()}")
        else:
            print(f"❌ Failed to emit event: {response.status_code}")
    except Exception as e:
        print(f"❌ Error emitting event: {e}")

async def simulate_document_analysis(job_id: str):
    """Simulate a complete document analysis workflow"""
    print(f"🚀 Starting document analysis simulation for job: {job_id}")
    
    # Step 1: Initialize job
    emit_event(job_id, {
        "type": "progress",
        "processed": 0,
        "total": 100,
        "message": "Initializing document analysis"
    })
    
    await asyncio.sleep(1)
    
    # Step 2: Simulate chunking progress
    chunks = [
        "Introduction and Background",
        "Study Objectives",
        "Inclusion/Exclusion Criteria", 
        "Study Procedures",
        "Safety Monitoring",
        "Statistical Analysis",
        "Data Management",
        "Regulatory Compliance"
    ]
    
    suggestions_found = []
    
    for i, chunk_name in enumerate(chunks):
        progress = int((i + 1) / len(chunks) * 80)  # 80% for processing
        
        emit_event(job_id, {
            "type": "progress",
            "processed": progress,
            "total": 100,
            "message": f"Analyzing {chunk_name}..."
        })
        
        await asyncio.sleep(2)
        
        # Simulate finding suggestions in some chunks
        if i % 3 == 0:  # Every 3rd chunk has suggestions
            suggestion = {
                "id": f"suggestion_{i}",
                "type": "medical_terminology",
                "chunk": chunk_name,
                "text": f"patients in {chunk_name}",
                "suggestion": f"participants in {chunk_name}",
                "rationale": f"Use 'participants' instead of 'patients' per ICH-GCP guidelines for {chunk_name}",
                "confidence": 0.9,
                "position": {"start": i * 50, "end": i * 50 + 20}
            }
            
            suggestions_found.append(suggestion)
            
            emit_event(job_id, {
                "type": "suggestion",
                "suggestion": suggestion
            })
            
            await asyncio.sleep(0.5)
    
    # Step 3: Final processing
    emit_event(job_id, {
        "type": "progress", 
        "processed": 90,
        "total": 100,
        "message": "Finalizing analysis results..."
    })
    
    await asyncio.sleep(2)
    
    # Step 4: Complete the job
    emit_event(job_id, {
        "type": "complete",
        "job_id": job_id,
        "result": {
            "suggestions": suggestions_found,
            "metadata": {
                "chunks_processed": len(chunks),
                "suggestions_found": len(suggestions_found),
                "processing_time": 16.5,
                "model_version": "test-simulation-1.0",
                "analysis_mode": "document_chunked"
            }
        }
    })
    
    print(f"✅ Completed document analysis simulation for job: {job_id}")

async def simulate_error_scenario(job_id: str):
    """Simulate an analysis that encounters an error"""
    print(f"🚀 Starting error simulation for job: {job_id}")
    
    emit_event(job_id, {
        "type": "progress",
        "processed": 0,
        "total": 100,
        "message": "Starting analysis..."
    })
    
    await asyncio.sleep(1)
    
    emit_event(job_id, {
        "type": "progress",
        "processed": 25,
        "total": 100, 
        "message": "Processing document chunks..."
    })
    
    await asyncio.sleep(2)
    
    # Simulate error
    emit_event(job_id, {
        "type": "error",
        "error": "Document too large for processing",
        "code": "DOCUMENT_SIZE_EXCEEDED",
        "message": "Document exceeds maximum size limit of 50MB"
    })
    
    print(f"❌ Completed error simulation for job: {job_id}")

async def simulate_quick_job(job_id: str):
    """Simulate a quick job that completes fast"""
    print(f"🚀 Starting quick job simulation for job: {job_id}")
    
    for i in range(0, 101, 20):
        emit_event(job_id, {
            "type": "progress",
            "processed": i,
            "total": 100,
            "message": f"Processing... {i}%"
        })
        await asyncio.sleep(0.5)
    
    emit_event(job_id, {
        "type": "suggestion",
        "suggestion": {
            "id": "quick_suggestion_1",
            "type": "compliance",
            "text": "patient",
            "suggestion": "participant",
            "rationale": "ICH-GCP compliance",
            "confidence": 0.95
        }
    })
    
    await asyncio.sleep(0.5)
    
    emit_event(job_id, {
        "type": "complete",
        "job_id": job_id,
        "result": {
            "suggestions": [{"id": "quick_suggestion_1", "type": "compliance"}],
            "metadata": {"processing_time": 3.0}
        }
    })
    
    print(f"✅ Completed quick job simulation for job: {job_id}")

def create_test_job(job_id: str):
    """Create a test job directory"""
    job_dir = Path("jobs") / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    
    # Create initial job metadata
    with open(job_dir / "metadata.json", "w") as f:
        json.dump({
            "job_id": job_id,
            "created_at": time.time(),
            "status": "running",
            "type": "test_simulation"
        }, f, indent=2)
    
    print(f"📁 Created test job directory: {job_dir}")

async def main():
    """Main test runner"""
    print("🧪 SSE Test Server - Ilana Job Streaming")
    print("=" * 50)
    
    while True:
        print("\nSelect a test scenario:")
        print("1. Document analysis simulation (16 seconds)")
        print("2. Error scenario simulation (4 seconds)")
        print("3. Quick job simulation (3 seconds)")
        print("4. Custom job ID")
        print("5. Exit")
        
        choice = input("\nEnter choice (1-5): ").strip()
        
        if choice == "5":
            print("👋 Goodbye!")
            break
        
        if choice == "4":
            custom_job_id = input("Enter custom job ID: ").strip()
            if custom_job_id:
                job_id = custom_job_id
            else:
                job_id = "custom-" + str(uuid.uuid4())[:8]
        else:
            job_id = f"test-{choice}-" + str(uuid.uuid4())[:8]
        
        # Create test job
        create_test_job(job_id)
        
        print(f"\n🔗 SSE Stream URL: {BASE_URL}/api/stream-job/{job_id}/events")
        print(f"📊 Job Status URL: {BASE_URL}/api/job-status/{job_id}")
        print(f"🆔 Job ID: {job_id}")
        
        input("\nPress Enter to start simulation (open the URLs above in browser/curl)...")
        
        try:
            if choice == "1":
                await simulate_document_analysis(job_id)
            elif choice == "2":
                await simulate_error_scenario(job_id)
            elif choice == "3":
                await simulate_quick_job(job_id)
            else:
                print("Invalid choice, running document analysis...")
                await simulate_document_analysis(job_id)
                
        except KeyboardInterrupt:
            print("\n⏹️ Simulation interrupted")
        except Exception as e:
            print(f"❌ Simulation error: {e}")
        
        print(f"\n✅ Simulation complete for job: {job_id}")
        print("Check the SSE stream to see the events!")

if __name__ == "__main__":
    print("Starting SSE Test Server...")
    print("Make sure the main Ilana server is running on port 8000")
    
    # Quick connectivity test
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.ok:
            print("✅ Main server is running")
        else:
            print("⚠️ Main server responded but might have issues")
    except Exception as e:
        print(f"❌ Cannot connect to main server: {e}")
        print("Please start the main server first: python3 -m uvicorn main:app --reload")
        exit(1)
    
    asyncio.run(main())