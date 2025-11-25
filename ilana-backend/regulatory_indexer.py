"""
Regulatory Knowledge Base Indexer for Ilana AI

Indexes FDA guidance documents and ICH requirements into Pinecone
for regulatory citation retrieval during protocol analysis.

Usage:
    python regulatory_indexer.py --index-fda
    python regulatory_indexer.py --index-ich-json
    python regulatory_indexer.py --index-ich-pdfs
    python regulatory_indexer.py --index-all
"""

import json
import os
import sys
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple
import asyncio

from pinecone import Pinecone, ServerlessSpec
from sentence_transformers import SentenceTransformer

# Configuration
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = "protocol-intelligence-768"
REGULATORY_NAMESPACE = "regulatory-guidance"
FDA_CHUNKS_DIR = Path(__file__).parent.parent / "data" / "data" / "fda_guidance_chunks"
ICH_REQUIREMENTS_FILE = Path(__file__).parent.parent / "data" / "data" / "ich_e6_requirements.json"
ICH_PDFS_DIR = Path(__file__).parent.parent / "data" / "data" / "ICH"

# Embedding model (same as used for protocols)
EMBEDDING_MODEL = "microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract"

# PDF chunking parameters
CHUNK_SIZE = 800  # Target characters per chunk
CHUNK_OVERLAP = 200  # Overlap between chunks to preserve context


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

    def extract_guideline_name(self, filename: str) -> Tuple[str, str]:
        """
        Extract ICH guideline ID and title from filename

        Args:
            filename: PDF filename

        Returns:
            Tuple of (guideline_id, title)
        """
        # Extract guideline ID (e.g., E8, E9, E3)
        match = re.search(r'ich[-_]?([a-z]\d+(?:[_-]?r\d+)?)', filename.lower())
        if match:
            guideline_id = match.group(1).upper().replace('_', '-')
        else:
            guideline_id = "ICH"

        # Clean up title from filename
        title = filename.replace('.pdf', '').replace('_en', '').replace('-', ' ')
        title = re.sub(r'ich\s+[a-z]\d+\s*r?\d*\s*', '', title, flags=re.IGNORECASE)
        title = ' '.join(title.split())  # Normalize whitespace

        return guideline_id, title

    def chunk_text_smart(self, text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
        """
        Intelligently chunk text preserving paragraph and sentence boundaries

        Args:
            text: Text to chunk
            chunk_size: Target characters per chunk
            overlap: Overlap between chunks

        Returns:
            List of text chunks
        """
        # Split by double newlines (paragraphs) first
        paragraphs = re.split(r'\n\s*\n', text)

        chunks = []
        current_chunk = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # If adding this paragraph exceeds chunk size, finalize current chunk
            if current_chunk and len(current_chunk) + len(para) > chunk_size:
                chunks.append(current_chunk.strip())

                # Start new chunk with overlap from previous chunk
                if overlap > 0 and len(current_chunk) > overlap:
                    current_chunk = current_chunk[-overlap:] + "\n\n" + para
                else:
                    current_chunk = para
            else:
                if current_chunk:
                    current_chunk += "\n\n" + para
                else:
                    current_chunk = para

        # Add final chunk
        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks

    def extract_section_number(self, text: str) -> str:
        """
        Extract section number from text chunk

        Args:
            text: Text chunk

        Returns:
            Section number if found, empty string otherwise
        """
        # Look for patterns like "5.7", "Section 3.1.2", "3.4 Statistical Methods"
        patterns = [
            r'(?:Section\s+)?(\d+(?:\.\d+)*)\s+[A-Z]',  # "Section 5.7 Statistical" or "5.7 Statistical"
            r'^(\d+(?:\.\d+)*)\s*[:\-]',  # "5.7:" or "5.7-"
        ]

        for pattern in patterns:
            match = re.search(pattern, text[:200])  # Check first 200 chars
            if match:
                return match.group(1)

        return ""

    def index_ich_pdfs(self, batch_size: int = 50):
        """
        Index ICH guideline PDFs into Pinecone regulatory namespace

        Args:
            batch_size: Number of vectors to upsert per batch
        """
        print("📚 Indexing ICH Guideline PDFs...")
        print(f"   Source: {ICH_PDFS_DIR}")
        print(f"   Namespace: {REGULATORY_NAMESPACE}\n")

        if not ICH_PDFS_DIR.exists():
            print(f"❌ ICH PDFs directory not found: {ICH_PDFS_DIR}")
            return

        # Check if pypdf is available
        try:
            from pypdf import PdfReader
        except ImportError:
            print("❌ pypdf library not found. Installing...")
            import subprocess
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pypdf"])
            from pypdf import PdfReader

        pdf_files = sorted(ICH_PDFS_DIR.glob("*.pdf"))
        total_pdfs = len(pdf_files)

        print(f"📄 Found {total_pdfs} ICH guideline PDFs")

        vectors_to_upsert = []
        indexed_count = 0
        total_chunks = 0

        for pdf_idx, pdf_file in enumerate(pdf_files, 1):
            try:
                print(f"\n📖 Processing {pdf_file.name} ({pdf_idx}/{total_pdfs})...")

                # Extract guideline metadata
                guideline_id, title = self.extract_guideline_name(pdf_file.name)

                # Read PDF
                reader = PdfReader(str(pdf_file))
                full_text = ""

                for page in reader.pages:
                    try:
                        page_text = page.extract_text()
                        if page_text:
                            full_text += page_text + "\n\n"
                    except Exception as e:
                        print(f"   ⚠️  Error extracting page: {e}")
                        continue

                if not full_text.strip():
                    print(f"   ⚠️  No text extracted from {pdf_file.name}, skipping")
                    continue

                # Clean up text
                full_text = re.sub(r'\n{3,}', '\n\n', full_text)  # Remove excessive newlines
                full_text = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f]', '', full_text)  # Remove control chars

                # Chunk the text
                chunks = self.chunk_text_smart(full_text)
                print(f"   📄 Created {len(chunks)} chunks")

                # Create vectors for each chunk
                for chunk_idx, chunk_text in enumerate(chunks, 1):
                    # Generate embedding
                    embedding = self.create_embedding(chunk_text)

                    # Extract section number if present
                    section = self.extract_section_number(chunk_text)

                    # Prepare metadata
                    metadata = {
                        "text": chunk_text[:1000],  # Pinecone metadata size limit
                        "full_text": chunk_text,
                        "title": title,
                        "section": section if section else f"Chunk {chunk_idx}",
                        "source": f"ICH {guideline_id}",
                        "document_type": "ich_guideline",
                        "tags": f"ich,{guideline_id.lower()},regulatory",
                        "jurisdiction": "International",
                        "regulatory_weight": "mandatory",
                        "guideline_id": guideline_id,
                        "chunk_index": chunk_idx,
                        "total_chunks": len(chunks)
                    }

                    # Add to batch
                    vectors_to_upsert.append({
                        "id": f"reg_ich_{guideline_id.lower().replace('.', '_')}_chunk_{chunk_idx}",
                        "values": embedding,
                        "metadata": metadata
                    })

                    total_chunks += 1

                    # Upsert in batches
                    if len(vectors_to_upsert) >= batch_size:
                        self.index.upsert(
                            vectors=vectors_to_upsert,
                            namespace=REGULATORY_NAMESPACE
                        )
                        indexed_count += len(vectors_to_upsert)
                        print(f"   ✅ Indexed {indexed_count}/{total_chunks} chunks...")
                        vectors_to_upsert = []

                print(f"   ✅ Completed {pdf_file.name}: {len(chunks)} chunks")

            except Exception as e:
                print(f"❌ Error processing {pdf_file.name}: {e}")
                import traceback
                traceback.print_exc()
                continue

        # Upsert remaining vectors
        if vectors_to_upsert:
            self.index.upsert(
                vectors=vectors_to_upsert,
                namespace=REGULATORY_NAMESPACE
            )
            indexed_count += len(vectors_to_upsert)

        print(f"\n✅ Successfully indexed {indexed_count} chunks from {total_pdfs} ICH guideline PDFs")
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
    parser.add_argument("--index-ich-json", action="store_true", help="Index ICH E6 requirements (JSON)")
    parser.add_argument("--index-ich-pdfs", action="store_true", help="Index ICH guideline PDFs (E1-E10, E2 series)")
    parser.add_argument("--index-all", action="store_true", help="Index all regulatory documents (FDA + ICH JSON + ICH PDFs)")
    parser.add_argument("--verify", action="store_true", help="Verify indexing")
    parser.add_argument("--batch-size", type=int, default=50, help="Batch size for upserting (default: 50)")

    args = parser.parse_args()

    if not any([args.index_fda, args.index_ich_json, args.index_ich_pdfs, args.index_all, args.verify]):
        parser.print_help()
        sys.exit(1)

    indexer = RegulatoryIndexer()

    if args.index_all or args.index_fda:
        indexer.index_fda_guidance(batch_size=args.batch_size)

    if args.index_all or args.index_ich_json:
        indexer.index_ich_requirements()

    if args.index_all or args.index_ich_pdfs:
        indexer.index_ich_pdfs(batch_size=args.batch_size)

    if args.verify or args.index_all:
        indexer.verify_indexing()


if __name__ == "__main__":
    main()
