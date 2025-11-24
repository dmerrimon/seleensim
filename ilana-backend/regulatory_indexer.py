"""
Regulatory Knowledge Base Indexer for Ilana AI

Indexes FDA guidance documents and ICH requirements into Pinecone
for regulatory citation retrieval during protocol analysis.

Usage:
    python regulatory_indexer.py --index-fda
    python regulatory_indexer.py --index-ich
    python regulatory_indexer.py --index-all
"""

import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Any
import asyncio

from pinecone import Pinecone, ServerlessSpec
from sentence_transformers import SentenceTransformer

# Configuration
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = "protocol-intelligence-768"
REGULATORY_NAMESPACE = "regulatory-guidance"
FDA_CHUNKS_DIR = Path(__file__).parent.parent / "data" / "data" / "fda_guidance_chunks"
ICH_REQUIREMENTS_FILE = Path(__file__).parent.parent / "data" / "data" / "ich_e6_requirements.json"

# Embedding model (same as used for protocols)
EMBEDDING_MODEL = "microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract"


class RegulatoryIndexer:
    """Index regulatory documents into Pinecone for RAG retrieval"""

    def __init__(self):
        """Initialize Pinecone connection and embedding model"""
        if not PINECONE_API_KEY:
            raise ValueError("PINECONE_API_KEY environment variable not set")

        print("🔧 Initializing Pinecone connection...")
        self.pc = Pinecone(api_key=PINECONE_API_KEY)
        self.index = self.pc.Index(PINECONE_INDEX_NAME)

        print("🧠 Loading PubMedBERT embedding model...")
        self.model = SentenceTransformer(EMBEDDING_MODEL)
        print("✅ Initialization complete\n")

    def create_embedding(self, text: str) -> List[float]:
        """Generate 768-dimensional embedding using PubMedBERT"""
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    def index_fda_guidance(self, batch_size: int = 50):
        """
        Index FDA guidance chunks into Pinecone regulatory namespace

        Args:
            batch_size: Number of vectors to upsert per batch
        """
        print("📚 Indexing FDA Guidance Documents...")
        print(f"   Source: {FDA_CHUNKS_DIR}")
        print(f"   Namespace: {REGULATORY_NAMESPACE}\n")

        if not FDA_CHUNKS_DIR.exists():
            print(f"❌ FDA chunks directory not found: {FDA_CHUNKS_DIR}")
            return

        chunk_files = sorted(FDA_CHUNKS_DIR.glob("fda_guidance_chunk_*.json"))
        total_chunks = len(chunk_files)

        print(f"📄 Found {total_chunks} FDA guidance chunks")

        vectors_to_upsert = []
        indexed_count = 0

        for idx, chunk_file in enumerate(chunk_files, 1):
            try:
                with open(chunk_file, 'r') as f:
                    chunk = json.load(f)

                # Extract guidance text
                text = chunk.get("text", "")
                if not text:
                    print(f"⚠️  Skipping {chunk_file.name}: No text content")
                    continue

                # Generate embedding
                embedding = self.create_embedding(text)

                # Prepare metadata for Pinecone
                metadata = {
                    "text": text[:1000],  # Pinecone metadata size limit
                    "full_text": text,  # For retrieval
                    "title": chunk.get("title", ""),
                    "section": chunk.get("section_heading", ""),
                    "source": "FDA Guidance",
                    "document_type": chunk.get("document_type", "fda_guidance"),
                    "tags": ",".join(chunk.get("tags", [])),
                    "jurisdiction": chunk.get("jurisdiction", "US"),
                    "regulatory_weight": chunk.get("regulatory_weight", "mandatory"),
                    "chunk_id": chunk.get("id", "")
                }

                # Add to batch
                vectors_to_upsert.append({
                    "id": f"reg_fda_{chunk.get('id', idx)}",
                    "values": embedding,
                    "metadata": metadata
                })

                # Upsert in batches
                if len(vectors_to_upsert) >= batch_size:
                    self.index.upsert(
                        vectors=vectors_to_upsert,
                        namespace=REGULATORY_NAMESPACE
                    )
                    indexed_count += len(vectors_to_upsert)
                    print(f"   ✅ Indexed {indexed_count}/{total_chunks} chunks...")
                    vectors_to_upsert = []

            except Exception as e:
                print(f"❌ Error processing {chunk_file.name}: {e}")
                continue

        # Upsert remaining vectors
        if vectors_to_upsert:
            self.index.upsert(
                vectors=vectors_to_upsert,
                namespace=REGULATORY_NAMESPACE
            )
            indexed_count += len(vectors_to_upsert)

        print(f"\n✅ Successfully indexed {indexed_count} FDA guidance chunks")
        print(f"   Namespace: {REGULATORY_NAMESPACE}\n")

    def index_ich_requirements(self):
        """
        Index ICH E6 requirements into Pinecone regulatory namespace
        """
        print("📚 Indexing ICH E6 Requirements...")
        print(f"   Source: {ICH_REQUIREMENTS_FILE}")
        print(f"   Namespace: {REGULATORY_NAMESPACE}\n")

        if not ICH_REQUIREMENTS_FILE.exists():
            print(f"❌ ICH requirements file not found: {ICH_REQUIREMENTS_FILE}")
            return

        with open(ICH_REQUIREMENTS_FILE, 'r') as f:
            ich_data = json.load(f)

        vectors_to_upsert = []

        # Process each ICH requirement
        for idx, requirement in enumerate(ich_data, 1):
            try:
                # Extract text from requirement
                text = requirement.get("requirement_text", "")
                section = requirement.get("section", "")
                title = requirement.get("title", "")

                if not text:
                    continue

                # Generate embedding
                embedding = self.create_embedding(text)

                # Prepare metadata
                metadata = {
                    "text": text[:1000],
                    "full_text": text,
                    "title": title,
                    "section": section,
                    "source": "ICH E6(R3)",
                    "document_type": "ich_gcp",
                    "tags": "ich,gcp,regulatory",
                    "jurisdiction": "International",
                    "regulatory_weight": "mandatory",
                    "ich_section": section
                }

                vectors_to_upsert.append({
                    "id": f"reg_ich_{section.replace('.', '_')}_{idx}",
                    "values": embedding,
                    "metadata": metadata
                })

            except Exception as e:
                print(f"❌ Error processing ICH requirement {idx}: {e}")
                continue

        if vectors_to_upsert:
            self.index.upsert(
                vectors=vectors_to_upsert,
                namespace=REGULATORY_NAMESPACE
            )
            print(f"✅ Successfully indexed {len(vectors_to_upsert)} ICH requirements")
        else:
            print("⚠️  No ICH requirements indexed")

        print(f"   Namespace: {REGULATORY_NAMESPACE}\n")

    def verify_indexing(self):
        """Verify that regulatory documents were indexed correctly"""
        print("🔍 Verifying regulatory indexing...")

        stats = self.index.describe_index_stats()

        if REGULATORY_NAMESPACE in stats.get("namespaces", {}):
            ns_stats = stats["namespaces"][REGULATORY_NAMESPACE]
            vector_count = ns_stats.get("vector_count", 0)
            print(f"✅ Found {vector_count} vectors in {REGULATORY_NAMESPACE} namespace")

            # Test query
            print("\n🧪 Testing regulatory query...")
            test_query = "pre-specification of statistical analysis plan"
            test_embedding = self.create_embedding(test_query)

            results = self.index.query(
                vector=test_embedding,
                namespace=REGULATORY_NAMESPACE,
                top_k=3,
                include_metadata=True
            )

            if results.matches:
                print(f"   Found {len(results.matches)} relevant regulatory documents:")
                for idx, match in enumerate(results.matches, 1):
                    metadata = match.metadata
                    print(f"\n   {idx}. {metadata.get('source', 'Unknown')}")
                    print(f"      Section: {metadata.get('section', 'N/A')}")
                    print(f"      Score: {match.score:.3f}")
                    print(f"      Preview: {metadata.get('text', '')[:100]}...")
            else:
                print("   ⚠️  No results found (query might be too specific)")
        else:
            print(f"❌ Namespace {REGULATORY_NAMESPACE} not found in index")

        print("\n✅ Verification complete\n")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Index regulatory documents into Pinecone")
    parser.add_argument("--index-fda", action="store_true", help="Index FDA guidance documents")
    parser.add_argument("--index-ich", action="store_true", help="Index ICH requirements")
    parser.add_argument("--index-all", action="store_true", help="Index all regulatory documents")
    parser.add_argument("--verify", action="store_true", help="Verify indexing")
    parser.add_argument("--batch-size", type=int, default=50, help="Batch size for upserting (default: 50)")

    args = parser.parse_args()

    if not any([args.index_fda, args.index_ich, args.index_all, args.verify]):
        parser.print_help()
        sys.exit(1)

    indexer = RegulatoryIndexer()

    if args.index_all or args.index_fda:
        indexer.index_fda_guidance(batch_size=args.batch_size)

    if args.index_all or args.index_ich:
        indexer.index_ich_requirements()

    if args.verify or args.index_all:
        indexer.verify_indexing()


if __name__ == "__main__":
    main()
