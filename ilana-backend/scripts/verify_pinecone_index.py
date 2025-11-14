#!/usr/bin/env python3
"""
Pinecone Index Verification Script
Verifies that the production Pinecone index has the expected 53,848 vectors
"""

import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from pinecone import Pinecone


def verify_pinecone_index():
    """Verify Pinecone index configuration and vector count"""

    # Load environment variables
    load_dotenv()

    # Get configuration
    api_key = os.getenv("PINECONE_API_KEY")
    environment = os.getenv("PINECONE_ENVIRONMENT", "gcp-starter")
    index_name = os.getenv("PINECONE_INDEX_NAME", "protocol-intelligence-768")

    print("=" * 60)
    print("🔍 Pinecone Index Verification")
    print("=" * 60)
    print(f"Environment: {environment}")
    print(f"Index Name: {index_name}")
    print()

    # Check API key
    if not api_key:
        print("❌ PINECONE_API_KEY not found in environment")
        print("   Please set PINECONE_API_KEY in your .env file")
        return False

    print(f"✅ API Key: {'*' * 8}{api_key[-4:]}")
    print()

    try:
        # Initialize Pinecone (using Pinecone 6.0+ API)
        print("🔄 Connecting to Pinecone...")
        pc = Pinecone(api_key=api_key)

        # Check if index exists
        indexes = pc.list_indexes()
        index_names = [idx.name for idx in indexes]
        print(f"📋 Available indexes: {', '.join(index_names)}")
        print()

        if index_name not in index_names:
            print(f"❌ Index '{index_name}' not found")
            print(f"   Available: {index_names}")
            return False

        print(f"✅ Index '{index_name}' exists")
        print()

        # Get index stats
        print("🔄 Fetching index statistics...")
        index = pc.Index(index_name)
        stats = index.describe_index_stats()

        # Display stats (Pinecone 6.0+ returns dict)
        print("📊 Index Statistics:")
        dimension = stats.get('dimension', stats['dimension']) if isinstance(stats, dict) else stats.dimension
        total_vectors = stats.get('total_vector_count', stats['total_vector_count']) if isinstance(stats, dict) else stats.total_vector_count
        print(f"   Dimension: {dimension}")
        print(f"   Total Vectors: {total_vectors:,}")
        print()

        # Check vector count
        expected_count = 53_848
        actual_count = total_vectors

        if actual_count == expected_count:
            print(f"✅ Vector count matches expected: {actual_count:,} vectors")
            return True
        elif actual_count > expected_count:
            print(f"⚠️  Vector count higher than expected:")
            print(f"   Expected: {expected_count:,}")
            print(f"   Actual: {actual_count:,}")
            print(f"   Difference: +{actual_count - expected_count:,}")
            print()
            print("   This is OK - index may have been updated with more data")
            return True
        else:
            print(f"⚠️  Vector count lower than expected:")
            print(f"   Expected: {expected_count:,}")
            print(f"   Actual: {actual_count:,}")
            print(f"   Missing: {expected_count - actual_count:,}")
            print()
            print("   WARNING: Some vectors may be missing")
            return False

    except Exception as e:
        print(f"❌ Error connecting to Pinecone: {e}")
        print(f"   Type: {type(e).__name__}")
        return False


def test_query():
    """Test a sample query to verify index is working"""

    print("\n" + "=" * 60)
    print("🧪 Testing Sample Query")
    print("=" * 60)

    try:
        # Load environment
        load_dotenv()
        api_key = os.getenv("PINECONE_API_KEY")
        environment = os.getenv("PINECONE_ENVIRONMENT", "gcp-starter")
        index_name = os.getenv("PINECONE_INDEX_NAME", "protocol-intelligence-768")

        # Initialize (using Pinecone 6.0+ API)
        pc = Pinecone(api_key=api_key)
        index = pc.Index(index_name)

        # Create a dummy query vector (768 dimensions for PubMedBERT)
        import numpy as np
        query_vector = np.random.random(768).tolist()

        print("🔄 Querying index with random vector...")
        results = index.query(
            vector=query_vector,
            top_k=5,
            include_metadata=True
        )

        # Pinecone 6.0+ returns dict
        matches = results.get('matches', results['matches']) if isinstance(results, dict) else results.matches
        print(f"✅ Query successful! Found {len(matches)} results")
        print()

        # Display sample results
        for i, match in enumerate(matches, 1):
            match_id = match.get('id', match['id']) if isinstance(match, dict) else match.id
            match_score = match.get('score', match['score']) if isinstance(match, dict) else match.score
            match_metadata = match.get('metadata', match.get('metadata', {})) if isinstance(match, dict) else (match.metadata if hasattr(match, 'metadata') else {})

            print(f"Result {i}:")
            print(f"  ID: {match_id}")
            print(f"  Score: {match_score:.4f}")
            if match_metadata:
                print(f"  Metadata: {list(match_metadata.keys())}")
            print()

        return True

    except Exception as e:
        print(f"❌ Query test failed: {e}")
        return False


if __name__ == "__main__":
    print()

    # Run verification
    index_ok = verify_pinecone_index()

    if index_ok:
        # Run query test
        query_ok = test_query()

        if query_ok:
            print("=" * 60)
            print("✅ All checks passed! Pinecone is ready for production")
            print("=" * 60)
            sys.exit(0)
        else:
            print("=" * 60)
            print("⚠️  Index exists but query test failed")
            print("=" * 60)
            sys.exit(1)
    else:
        print("=" * 60)
        print("❌ Verification failed")
        print("=" * 60)
        sys.exit(1)
