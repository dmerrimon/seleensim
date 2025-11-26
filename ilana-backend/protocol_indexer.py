"""
Protocol Indexer for Ilana AI

Indexes clinical protocol exemplars into Pinecone for RAG retrieval
during protocol analysis.

Usage:
    python protocol_indexer.py --index-all
    python protocol_indexer.py --index-batch 0 1000  # Index first 1000
    python protocol_indexer.py --check-status
"""

import os
import sys
import argparse
from pathlib import Path
from typing import List, Dict
import time

from pinecone import Pinecone
from sentence_transformers import SentenceTransformer

# Configuration
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = "protocol-intelligence-768"
PROTOCOL_NAMESPACE = ""  # Default namespace for protocol exemplars
PROTOCOLS_DIR = Path(__file__).parent.parent / "data" / "data" / "anonymized_texts"

# Embedding model (must match regulatory indexer)
EMBEDDING_MODEL = "microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract"

# Chunking parameters
CHUNK_SIZE = 1000  # Characters per chunk
CHUNK_OVERLAP = 200  # Overlap for context preservation


class ProtocolIndexer:
    """Index clinical protocol exemplars into Pinecone"""

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

    def chunk_text(self, text: str, chunk_size: int = CHUNK_SIZE) -> List[str]:
        """
        Split text into overlapping chunks for better context preservation

        Args:
            text: Full protocol text
            chunk_size: Target size per chunk in characters

        Returns:
            List of text chunks with overlap
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

    def index_protocols(self, start_idx: int = 0, end_idx: int = None, batch_size: int = 100):
        """
        Index protocol files into Pinecone default namespace

        Args:
            start_idx: Starting protocol index (0-based)
            end_idx: Ending protocol index (None = all remaining)
            batch_size: Number of vectors to upsert per batch
        """
        print("📚 Indexing Clinical Protocol Exemplars...")
        print(f"   Source: {PROTOCOLS_DIR}")
        print(f"   Namespace: {PROTOCOL_NAMESPACE or '(default)'}\n")

        if not PROTOCOLS_DIR.exists():
            print(f"❌ Protocols directory not found: {PROTOCOLS_DIR}")
            return

        protocol_files = sorted(PROTOCOLS_DIR.glob("protocol_*.txt"))
        total_protocols = len(protocol_files)

        if end_idx is None:
            end_idx = total_protocols

        protocol_files = protocol_files[start_idx:end_idx]

        print(f"📄 Processing protocols {start_idx:,} to {end_idx:,} (total: {total_protocols:,})")
        print(f"   Files to process: {len(protocol_files):,}\n")

        vectors_to_upsert = []
        indexed_count = 0
        chunk_count = 0
        start_time = time.time()

        for file_idx, protocol_file in enumerate(protocol_files, start=start_idx):
            try:
                # Read protocol text
                with open(protocol_file, 'r', encoding='utf-8') as f:
                    text = f.read()

                if not text.strip():
                    print(f"⚠️  Skipping {protocol_file.name}: Empty file")
                    continue

                # Split into chunks
                chunks = self.chunk_text(text)

                # Index each chunk
                for chunk_idx, chunk in enumerate(chunks):
                    # Generate embedding
                    embedding = self.create_embedding(chunk)

                    # Create unique ID
                    vector_id = f"protocol_{file_idx:06d}_chunk_{chunk_idx:03d}"

                    # Prepare metadata
                    metadata = {
                        "type": "protocol_exemplar",
                        "protocol_id": file_idx,
                        "protocol_file": protocol_file.name,
                        "chunk_index": chunk_idx,
                        "total_chunks": len(chunks),
                        "text": chunk[:500],  # Store first 500 chars for quick preview
                        "char_count": len(chunk)
                    }

                    vectors_to_upsert.append({
                        "id": vector_id,
                        "values": embedding,
                        "metadata": metadata
                    })

                    chunk_count += 1

                    # Batch upsert when batch size reached
                    if len(vectors_to_upsert) >= batch_size:
                        self.index.upsert(
                            vectors=vectors_to_upsert,
                            namespace=PROTOCOL_NAMESPACE
                        )
                        indexed_count += len(vectors_to_upsert)

                        # Progress update
                        elapsed = time.time() - start_time
                        rate = indexed_count / elapsed if elapsed > 0 else 0
                        print(f"✅ Indexed {indexed_count:,} chunks from {file_idx - start_idx + 1:,} protocols ({rate:.1f} chunks/sec)")

                        vectors_to_upsert = []

            except Exception as e:
                print(f"❌ Error processing {protocol_file.name}: {e}")
                continue

        # Upsert remaining vectors
        if vectors_to_upsert:
            self.index.upsert(
                vectors=vectors_to_upsert,
                namespace=PROTOCOL_NAMESPACE
            )
            indexed_count += len(vectors_to_upsert)

        elapsed = time.time() - start_time
        print(f"\n✅ Indexing complete!")
        print(f"   Protocols processed: {file_idx - start_idx + 1:,}")
        print(f"   Total chunks indexed: {indexed_count:,}")
        print(f"   Time elapsed: {elapsed/60:.1f} minutes")
        print(f"   Average rate: {indexed_count/elapsed:.1f} chunks/second")

    def check_status(self):
        """Check current indexing status in Pinecone"""
        print("📊 Checking Pinecone Index Status...")

        stats = self.index.describe_index_stats()

        print(f"\nIndex: {PINECONE_INDEX_NAME}")
        print(f"Total vectors: {stats.total_vector_count:,}")
        print(f"\nNamespaces:")

        for namespace, info in stats.namespaces.items():
            namespace_name = namespace if namespace else "(default - protocols)"
            print(f"  - {namespace_name}: {info.vector_count:,} vectors")


def main():
    parser = argparse.ArgumentParser(description="Index clinical protocols into Pinecone")
    parser.add_argument("--index-all", action="store_true", help="Index all protocols")
    parser.add_argument("--index-batch", nargs=2, type=int, metavar=("START", "END"),
                        help="Index protocols from START to END index")
    parser.add_argument("--check-status", action="store_true", help="Check current index status")
    parser.add_argument("--batch-size", type=int, default=100, help="Batch size for upserts (default: 100)")

    args = parser.parse_args()

    indexer = ProtocolIndexer()

    if args.check_status:
        indexer.check_status()
    elif args.index_all:
        indexer.index_protocols(batch_size=args.batch_size)
    elif args.index_batch:
        start, end = args.index_batch
        indexer.index_protocols(start_idx=start, end_idx=end, batch_size=args.batch_size)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
