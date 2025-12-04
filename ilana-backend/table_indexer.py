"""
Protocol Table Indexer for Ilana AI

Extracts tables from clinical protocol PDFs and indexes them into Pinecone
for cross-reference validation during protocol analysis.

Usage:
    python table_indexer.py --index-pdfs
    python table_indexer.py --index-pdfs --dry-run
    python table_indexer.py --index-pdfs --document-type sap
    python table_indexer.py --single-pdf /path/to/protocol.pdf
    python table_indexer.py --verify
    python table_indexer.py --stats
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

import pdfplumber

# Conditional imports for full indexing mode
EMBEDDING_AVAILABLE = False
try:
    from pinecone import Pinecone
    from sentence_transformers import SentenceTransformer
    EMBEDDING_AVAILABLE = True
except ImportError:
    pass

# Configuration
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = "protocol-intelligence-768"
TABLES_NAMESPACE = "protocol-tables"

# PDF directories
PDF_BASE_DIR = Path(__file__).parent.parent / "data" / "data" / "protocol_pdfs"
PROTOCOLS_DIR = PDF_BASE_DIR / "protocols"
SAPS_DIR = PDF_BASE_DIR / "saps"
ICFS_DIR = PDF_BASE_DIR / "icfs"

# Embedding model (same as used for protocols)
EMBEDDING_MODEL = "microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract"

# Table type classification patterns
TABLE_TYPE_PATTERNS = {
    "objectives": {
        "header_keywords": ["objective", "aim", "purpose", "goal"],
        "content_keywords": ["primary", "secondary", "exploratory", "tertiary"],
    },
    "endpoints": {
        "header_keywords": ["endpoint", "outcome", "measure", "variable"],
        "content_keywords": ["primary", "secondary", "efficacy", "safety", "os", "pfs", "orr"],
    },
    "schedule": {
        "header_keywords": ["visit", "week", "day", "schedule", "procedure", "assessment", "time"],
        "content_keywords": ["screening", "baseline", "follow-up", "end of study", "eot"],
    },
    "statistics": {
        "header_keywords": ["analysis", "statistical", "method", "population", "hypothesis"],
        "content_keywords": ["itt", "per-protocol", "sensitivity", "subgroup", "interim", "sample size"],
    },
    "safety": {
        "header_keywords": ["adverse", "ae", "sae", "safety", "event", "toxicity"],
        "content_keywords": ["serious", "related", "grade", "ctcae", "severity", "causality"],
    },
    "eligibility": {
        "header_keywords": ["inclusion", "exclusion", "criteria", "eligibility"],
        "content_keywords": ["must", "cannot", "prior", "history", "age", "diagnosis"],
    },
    "demographics": {
        "header_keywords": ["demographic", "baseline", "characteristic", "patient"],
        "content_keywords": ["age", "sex", "gender", "race", "weight", "bmi"],
    },
}


class TableIndexer:
    """Extract and index protocol tables into Pinecone"""

    def __init__(self, dry_run: bool = False, extract_only: bool = False):
        """
        Initialize Pinecone connection and embedding model

        Args:
            dry_run: If True, extract tables but don't upsert to Pinecone
            extract_only: If True, only extract tables (no embeddings needed)
        """
        self.dry_run = dry_run
        self.extract_only = extract_only
        self.model = None
        self.pc = None
        self.index = None

        if extract_only:
            print("🔧 Extract-only mode - skipping Pinecone and embeddings")
            print("✅ Initialization complete\n")
            return

        if not EMBEDDING_AVAILABLE:
            raise ImportError(
                "Embedding libraries not available. Install with:\n"
                "  pip install sentence-transformers pinecone\n"
                "Or use --extract-only mode to just extract tables."
            )

        if not dry_run:
            if not PINECONE_API_KEY:
                raise ValueError("PINECONE_API_KEY environment variable not set")

            print("🔧 Initializing Pinecone connection...")
            self.pc = Pinecone(api_key=PINECONE_API_KEY)
            self.index = self.pc.Index(PINECONE_INDEX_NAME)
        else:
            print("🔧 Dry run mode - skipping Pinecone connection")

        print("🧠 Loading PubMedBERT embedding model...")
        self.model = SentenceTransformer(EMBEDDING_MODEL)
        print("✅ Initialization complete\n")

    def create_embedding(self, text: str) -> List[float]:
        """Generate 768-dimensional embedding using PubMedBERT"""
        # Truncate text if too long (PubMedBERT has 512 token limit)
        if len(text) > 4000:
            text = text[:4000]
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    def parse_filename(self, filename: str) -> Tuple[str, str]:
        """
        Parse protocol filename to extract document type and protocol ID

        Args:
            filename: PDF filename (e.g., "Prot_001.pdf", "Prot_SAP_000-2.pdf")

        Returns:
            Tuple of (document_type, protocol_id)
        """
        name = filename.replace('.pdf', '').replace('.PDF', '')

        if 'SAP_ICF' in name:
            doc_type = 'sap_icf'
            # Extract ID after SAP_ICF_
            match = re.search(r'SAP_ICF_(.+)', name)
            protocol_id = match.group(1) if match else name
        elif 'SAP' in name:
            doc_type = 'sap'
            # Extract ID after SAP_
            match = re.search(r'SAP_(.+)', name)
            protocol_id = match.group(1) if match else name
        elif 'ICF' in name:
            doc_type = 'icf'
            # Extract ID after ICF_
            match = re.search(r'ICF_(.+)', name)
            protocol_id = match.group(1) if match else name
        else:
            doc_type = 'protocol'
            # Extract ID after Prot_
            match = re.search(r'Prot_(.+)', name)
            protocol_id = match.group(1) if match else name

        return doc_type, protocol_id

    def extract_tables(self, pdf_path: Path) -> List[Dict[str, Any]]:
        """
        Extract all tables from a PDF using pdfplumber

        Args:
            pdf_path: Path to PDF file

        Returns:
            List of table dictionaries with structure info
        """
        tables = []

        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    page_tables = page.extract_tables()

                    for table_idx, table_data in enumerate(page_tables):
                        if not table_data or len(table_data) < 2:
                            # Skip tables with no data or only headers
                            continue

                        # First row is typically headers
                        headers = [str(cell or '').strip() for cell in table_data[0]]

                        # Skip if all headers are empty
                        if not any(headers):
                            continue

                        # Remaining rows are data
                        rows = []
                        for row in table_data[1:]:
                            cleaned_row = [str(cell or '').strip() for cell in row]
                            if any(cleaned_row):  # Skip entirely empty rows
                                rows.append(cleaned_row)

                        if not rows:
                            continue

                        tables.append({
                            "page": page_num,
                            "table_index": table_idx,
                            "headers": headers,
                            "rows": rows,
                            "row_count": len(rows),
                            "column_count": len(headers),
                        })

        except Exception as e:
            print(f"   ❌ Error extracting tables from {pdf_path.name}: {e}")

        return tables

    def classify_table_type(self, table: Dict[str, Any]) -> Tuple[str, float]:
        """
        Classify table type based on headers and content

        Args:
            table: Table dictionary with headers and rows

        Returns:
            Tuple of (table_type, confidence)
        """
        headers_text = ' '.join(table['headers']).lower()

        # Flatten first 3 rows for content analysis
        content_sample = []
        for row in table['rows'][:3]:
            content_sample.extend(row)
        content_text = ' '.join(content_sample).lower()

        combined_text = headers_text + ' ' + content_text

        scores = {}

        for table_type, patterns in TABLE_TYPE_PATTERNS.items():
            score = 0

            # Header keywords have higher weight (2 points each)
            for keyword in patterns['header_keywords']:
                if keyword in headers_text:
                    score += 2

            # Content keywords (1 point each)
            for keyword in patterns['content_keywords']:
                if keyword in combined_text:
                    score += 1

            scores[table_type] = score

        # Find highest scoring type
        if not scores or max(scores.values()) == 0:
            return "unknown", 0.0

        best_type = max(scores, key=scores.get)
        max_score = scores[best_type]

        # Calculate confidence (normalize by potential max score)
        max_possible = len(TABLE_TYPE_PATTERNS[best_type]['header_keywords']) * 2 + \
                       len(TABLE_TYPE_PATTERNS[best_type]['content_keywords'])
        confidence = min(max_score / max_possible, 1.0) if max_possible > 0 else 0.0

        return best_type, round(confidence, 2)

    def create_table_embedding_text(self, table: Dict[str, Any], table_type: str) -> str:
        """
        Create text representation of table for embedding

        Args:
            table: Table dictionary
            table_type: Classified table type

        Returns:
            Text string suitable for embedding
        """
        parts = []

        # Add table type context
        parts.append(f"Table Type: {table_type}")

        # Add headers
        headers = table['headers']
        parts.append(f"Columns: {', '.join(headers)}")

        # Add row content (limit to first 5 rows for embedding)
        for i, row in enumerate(table['rows'][:5], 1):
            # Create header: value pairs
            row_text = ' | '.join(f"{h}: {v}" for h, v in zip(headers, row) if v)
            if row_text:
                parts.append(f"Row {i}: {row_text}")

        if len(table['rows']) > 5:
            parts.append(f"... and {len(table['rows']) - 5} more rows")

        return '\n'.join(parts)

    def create_full_table_text(self, table: Dict[str, Any]) -> str:
        """
        Create full text representation of table for storage

        Args:
            table: Table dictionary

        Returns:
            Full text representation
        """
        lines = []
        headers = table['headers']

        # Header row
        lines.append(' | '.join(headers))
        lines.append('-' * len(lines[0]))

        # Data rows
        for row in table['rows']:
            lines.append(' | '.join(row))

        return '\n'.join(lines)

    def choose_embedding_strategy(self, table: Dict[str, Any]) -> str:
        """
        Choose embedding granularity based on table size

        Args:
            table: Table dictionary

        Returns:
            Strategy: "table_only", "table_plus_chunks", or "table_plus_rows"
        """
        row_count = table['row_count']

        if row_count <= 5:
            return "table_only"
        elif row_count <= 15:
            return "table_plus_chunks"
        else:
            return "table_plus_rows"

    def create_vectors_for_table(
        self,
        table: Dict[str, Any],
        pdf_file: str,
        doc_type: str,
        protocol_id: str,
        global_table_idx: int
    ) -> List[Dict[str, Any]]:
        """
        Create embedding vectors for a single table

        Args:
            table: Table dictionary
            pdf_file: Source PDF filename
            doc_type: Document type (protocol, sap, icf)
            protocol_id: Protocol identifier
            global_table_idx: Global table index within PDF

        Returns:
            List of vectors ready for Pinecone upsert
        """
        vectors = []

        # Classify table type
        table_type, confidence = self.classify_table_type(table)

        # Base metadata
        base_metadata = {
            "pdf_file": pdf_file,
            "document_type": doc_type,
            "protocol_id": protocol_id,
            "table_index": global_table_idx,
            "table_page": table['page'],
            "table_type": table_type,
            "table_type_confidence": confidence,
            "row_count": table['row_count'],
            "column_count": table['column_count'],
            "headers": json.dumps(table['headers']),
            "indexed_at": datetime.utcnow().isoformat(),
        }

        # Choose embedding strategy
        strategy = self.choose_embedding_strategy(table)

        # Create table-level embedding (always)
        embedding_text = self.create_table_embedding_text(table, table_type)
        full_text = self.create_full_table_text(table)

        table_metadata = {
            **base_metadata,
            "text": full_text[:500],  # Preview
            "full_text": full_text[:40000],  # Full content (Pinecone limit)
            "embedding_scope": "table",
        }

        table_id = f"tbl_{doc_type}_{protocol_id}_{global_table_idx}"
        embedding = self.create_embedding(embedding_text)

        vectors.append({
            "id": table_id,
            "values": embedding,
            "metadata": table_metadata,
        })

        # Add row-level embeddings for large tables
        if strategy == "table_plus_rows":
            headers = table['headers']
            for row_idx, row in enumerate(table['rows']):
                row_text = f"[{table_type}] " + ' | '.join(
                    f"{h}: {v}" for h, v in zip(headers, row) if v
                )

                row_metadata = {
                    **base_metadata,
                    "text": row_text[:500],
                    "full_text": row_text,
                    "embedding_scope": "row",
                    "row_index": row_idx,
                }

                row_id = f"tbl_{doc_type}_{protocol_id}_{global_table_idx}_row_{row_idx}"
                row_embedding = self.create_embedding(row_text)

                vectors.append({
                    "id": row_id,
                    "values": row_embedding,
                    "metadata": row_metadata,
                })

        elif strategy == "table_plus_chunks":
            # Create 3-row chunks
            headers = table['headers']
            chunk_size = 3

            for chunk_idx in range(0, len(table['rows']), chunk_size):
                chunk_rows = table['rows'][chunk_idx:chunk_idx + chunk_size]
                chunk_lines = []

                for row in chunk_rows:
                    row_text = ' | '.join(f"{h}: {v}" for h, v in zip(headers, row) if v)
                    chunk_lines.append(row_text)

                chunk_text = f"[{table_type}]\n" + '\n'.join(chunk_lines)

                chunk_metadata = {
                    **base_metadata,
                    "text": chunk_text[:500],
                    "full_text": chunk_text,
                    "embedding_scope": "chunk",
                    "chunk_index": chunk_idx // chunk_size,
                }

                chunk_id = f"tbl_{doc_type}_{protocol_id}_{global_table_idx}_chunk_{chunk_idx // chunk_size}"
                chunk_embedding = self.create_embedding(chunk_text)

                vectors.append({
                    "id": chunk_id,
                    "values": chunk_embedding,
                    "metadata": chunk_metadata,
                })

        return vectors

    def process_pdf(self, pdf_path: Path) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Process a single PDF and extract all table vectors

        Args:
            pdf_path: Path to PDF file

        Returns:
            Tuple of (vectors, stats_dict)
        """
        vectors = []
        stats = {
            "tables_found": 0,
            "vectors_created": 0,
            "table_types": {},
            "errors": [],
        }

        doc_type, protocol_id = self.parse_filename(pdf_path.name)

        try:
            tables = self.extract_tables(pdf_path)
            stats["tables_found"] = len(tables)

            # In extract-only mode, just classify tables without creating embeddings
            if self.extract_only:
                for global_idx, table in enumerate(tables):
                    table_type, confidence = self.classify_table_type(table)
                    stats["table_types"][table_type] = stats["table_types"].get(table_type, 0) + 1
                return vectors, stats

            for global_idx, table in enumerate(tables):
                try:
                    table_vectors = self.create_vectors_for_table(
                        table, pdf_path.name, doc_type, protocol_id, global_idx
                    )
                    vectors.extend(table_vectors)

                    # Track table types
                    table_type = table_vectors[0]["metadata"]["table_type"] if table_vectors else "unknown"
                    stats["table_types"][table_type] = stats["table_types"].get(table_type, 0) + 1

                except Exception as e:
                    stats["errors"].append(f"Table {global_idx}: {str(e)}")

            stats["vectors_created"] = len(vectors)

        except Exception as e:
            stats["errors"].append(f"PDF processing: {str(e)}")

        return vectors, stats

    def index_pdfs(
        self,
        pdf_dir: Optional[Path] = None,
        document_type: str = "all",
        batch_size: int = 50
    ) -> Dict[str, Any]:
        """
        Index all PDFs from the specified directory

        Args:
            pdf_dir: Directory containing PDFs (defaults to PDF_BASE_DIR)
            document_type: Filter by type: "protocol", "sap", "icf", or "all"
            batch_size: Number of vectors to upsert per batch

        Returns:
            Summary statistics
        """
        if pdf_dir is None:
            pdf_dir = PDF_BASE_DIR

        # Collect PDF files based on document type filter
        pdf_files = []

        if document_type in ["all", "protocol"]:
            if PROTOCOLS_DIR.exists():
                pdf_files.extend(PROTOCOLS_DIR.glob("*.pdf"))

        if document_type in ["all", "sap"]:
            if SAPS_DIR.exists():
                pdf_files.extend(SAPS_DIR.glob("*.pdf"))

        if document_type in ["all", "icf"]:
            if ICFS_DIR.exists():
                pdf_files.extend(ICFS_DIR.glob("*.pdf"))

        pdf_files = sorted(pdf_files)
        total_pdfs = len(pdf_files)

        print(f"📚 Indexing Protocol Tables...")
        print(f"   Source: {pdf_dir}")
        print(f"   Document type filter: {document_type}")
        print(f"   Found {total_pdfs} PDFs to process")
        print(f"   Namespace: {TABLES_NAMESPACE}")
        print(f"   Dry run: {self.dry_run}\n")

        if total_pdfs == 0:
            print("❌ No PDF files found")
            return {"error": "No PDFs found"}

        # Process all PDFs
        all_vectors = []
        total_stats = {
            "pdfs_processed": 0,
            "pdfs_with_tables": 0,
            "total_tables": 0,
            "total_vectors": 0,
            "table_types": {},
            "errors": [],
        }

        for idx, pdf_path in enumerate(pdf_files, 1):
            print(f"   [{idx}/{total_pdfs}] Processing {pdf_path.name}...")

            vectors, stats = self.process_pdf(pdf_path)

            if vectors:
                all_vectors.extend(vectors)

            # Count PDFs with tables based on tables_found, not vectors
            if stats["tables_found"] > 0:
                total_stats["pdfs_with_tables"] += 1

            total_stats["pdfs_processed"] += 1
            total_stats["total_tables"] += stats["tables_found"]
            total_stats["total_vectors"] += stats["vectors_created"]

            # Merge table type counts
            for ttype, count in stats["table_types"].items():
                total_stats["table_types"][ttype] = total_stats["table_types"].get(ttype, 0) + count

            # Collect errors
            if stats["errors"]:
                for err in stats["errors"]:
                    total_stats["errors"].append(f"{pdf_path.name}: {err}")

            # Print progress every 10 files
            if idx % 10 == 0:
                print(f"   ✅ Processed {idx}/{total_pdfs} PDFs, {len(all_vectors)} vectors so far")

        # Upsert to Pinecone if not dry run
        if not self.dry_run and all_vectors:
            print(f"\n📤 Upserting {len(all_vectors)} vectors to Pinecone...")

            for i in range(0, len(all_vectors), batch_size):
                batch = all_vectors[i:i + batch_size]
                self.index.upsert(vectors=batch, namespace=TABLES_NAMESPACE)
                print(f"   ✅ Upserted batch {i // batch_size + 1} ({len(batch)} vectors)")

            print(f"✅ Successfully indexed {len(all_vectors)} vectors to namespace '{TABLES_NAMESPACE}'")
        elif self.dry_run:
            print(f"\n🔍 Dry run complete - would have indexed {len(all_vectors)} vectors")

        # Print summary
        print("\n" + "=" * 60)
        print("📊 INDEXING SUMMARY")
        print("=" * 60)
        print(f"   PDFs processed: {total_stats['pdfs_processed']}")
        print(f"   PDFs with tables: {total_stats['pdfs_with_tables']}")
        print(f"   Total tables extracted: {total_stats['total_tables']}")
        print(f"   Total vectors created: {total_stats['total_vectors']}")
        print(f"\n   Table types found:")
        for ttype, count in sorted(total_stats["table_types"].items(), key=lambda x: -x[1]):
            print(f"      {ttype}: {count}")

        if total_stats["errors"]:
            print(f"\n   ⚠️  Errors ({len(total_stats['errors'])}):")
            for err in total_stats["errors"][:10]:
                print(f"      - {err}")
            if len(total_stats["errors"]) > 10:
                print(f"      ... and {len(total_stats['errors']) - 10} more")

        print("=" * 60)

        return total_stats

    def verify_indexing(self) -> Dict[str, Any]:
        """
        Verify indexing by running test queries

        Returns:
            Verification results
        """
        if self.dry_run:
            print("❌ Cannot verify in dry run mode")
            return {"error": "Dry run mode"}

        print("🔍 Verifying table indexing...\n")

        # Get namespace stats
        stats = self.index.describe_index_stats()
        namespace_stats = stats.namespaces.get(TABLES_NAMESPACE, {})
        vector_count = namespace_stats.vector_count if hasattr(namespace_stats, 'vector_count') else 0

        print(f"   Namespace: {TABLES_NAMESPACE}")
        print(f"   Vector count: {vector_count}\n")

        # Run test queries
        test_queries = [
            ("primary endpoint overall survival", "endpoints"),
            ("inclusion criteria age", "eligibility"),
            ("visit schedule week 12", "schedule"),
            ("statistical analysis population", "statistics"),
        ]

        results = {"vector_count": vector_count, "queries": []}

        for query_text, expected_type in test_queries:
            print(f"   Query: '{query_text}'")

            embedding = self.create_embedding(query_text)

            query_results = self.index.query(
                vector=embedding,
                namespace=TABLES_NAMESPACE,
                top_k=3,
                include_metadata=True,
            )

            matches = []
            for match in query_results.matches:
                matches.append({
                    "id": match.id,
                    "score": round(match.score, 3),
                    "table_type": match.metadata.get("table_type", "unknown"),
                    "pdf_file": match.metadata.get("pdf_file", "unknown"),
                })

            results["queries"].append({
                "query": query_text,
                "expected_type": expected_type,
                "matches": matches,
            })

            if matches:
                best = matches[0]
                print(f"   ✅ Best match: {best['pdf_file']} (type: {best['table_type']}, score: {best['score']})")
            else:
                print(f"   ⚠️  No matches found")
            print()

        return results

    def get_stats(self) -> Dict[str, Any]:
        """Get index statistics"""
        if self.dry_run:
            print("❌ Cannot get stats in dry run mode")
            return {"error": "Dry run mode"}

        stats = self.index.describe_index_stats()

        print("📊 Index Statistics\n")
        print(f"   Total vectors: {stats.total_vector_count}")
        print(f"\n   Namespaces:")

        for ns_name, ns_stats in stats.namespaces.items():
            count = ns_stats.vector_count if hasattr(ns_stats, 'vector_count') else 0
            print(f"      {ns_name or '(default)'}: {count} vectors")

        return {
            "total_vectors": stats.total_vector_count,
            "namespaces": {
                k: v.vector_count if hasattr(v, 'vector_count') else 0
                for k, v in stats.namespaces.items()
            },
        }


def main():
    parser = argparse.ArgumentParser(
        description="Index protocol tables into Pinecone",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python table_indexer.py --index-pdfs                      # Index all PDFs
    python table_indexer.py --index-pdfs --dry-run            # Extract but don't upload
    python table_indexer.py --index-pdfs --extract-only       # Just extract, no embeddings
    python table_indexer.py --index-pdfs --document-type sap  # SAPs only
    python table_indexer.py --single-pdf /path/to/file.pdf    # Single file
    python table_indexer.py --verify                          # Test queries
    python table_indexer.py --stats                           # Show stats
        """
    )

    # Actions
    parser.add_argument("--index-pdfs", action="store_true",
                        help="Extract and index tables from all PDFs")
    parser.add_argument("--single-pdf", type=Path,
                        help="Process a single PDF file")
    parser.add_argument("--verify", action="store_true",
                        help="Verify indexing with test queries")
    parser.add_argument("--stats", action="store_true",
                        help="Show index statistics")

    # Options
    parser.add_argument("--dry-run", action="store_true",
                        help="Extract tables but don't upsert to Pinecone")
    parser.add_argument("--extract-only", action="store_true",
                        help="Only extract tables (no embeddings/Pinecone needed)")
    parser.add_argument("--document-type", choices=["protocol", "sap", "icf", "all"],
                        default="all",
                        help="Filter by document type (default: all)")
    parser.add_argument("--batch-size", type=int, default=50,
                        help="Batch size for upserting (default: 50)")

    args = parser.parse_args()

    # Validate at least one action is specified
    if not any([args.index_pdfs, args.single_pdf, args.verify, args.stats]):
        parser.print_help()
        sys.exit(1)

    # Initialize indexer
    indexer = TableIndexer(dry_run=args.dry_run, extract_only=args.extract_only)

    if args.index_pdfs:
        indexer.index_pdfs(
            document_type=args.document_type,
            batch_size=args.batch_size,
        )

    elif args.single_pdf:
        if not args.single_pdf.exists():
            print(f"❌ File not found: {args.single_pdf}")
            sys.exit(1)

        vectors, stats = indexer.process_pdf(args.single_pdf)
        print(f"\n📊 Results for {args.single_pdf.name}:")
        print(f"   Tables found: {stats['tables_found']}")
        print(f"   Vectors created: {stats['vectors_created']}")
        print(f"   Table types: {stats['table_types']}")

        if not args.dry_run and vectors:
            indexer.index.upsert(vectors=vectors, namespace=TABLES_NAMESPACE)
            print(f"   ✅ Indexed {len(vectors)} vectors")

    elif args.verify:
        indexer.verify_indexing()

    elif args.stats:
        indexer.get_stats()


if __name__ == "__main__":
    main()
