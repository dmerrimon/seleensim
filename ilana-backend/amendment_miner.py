"""
Amendment Miner (Layer 3: Risk Prediction)

Processes all amended protocols to build risk patterns database.
Extracts patterns from amendments to predict which protocol language
is at high risk of requiring changes.

Usage:
    python amendment_miner.py --sample 100       # Process 100 protocols for testing
    python amendment_miner.py --all              # Process all protocols
    python amendment_miner.py --output patterns.json
"""

import os
import json
import re
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
import argparse

from amendment_parser import (
    parse_protocol_file,
    ProtocolAmendments,
    get_amendment_statistics
)

logger = logging.getLogger(__name__)

# Default paths
DEFAULT_PROTOCOLS_DIR = Path(__file__).parent.parent / "data" / "data" / "anonymized_texts"
DEFAULT_OUTPUT_FILE = Path(__file__).parent / "amendment_risk_patterns.json"


@dataclass
class RiskPattern:
    """A mined risk pattern with statistics"""
    pattern: str                    # Regex pattern
    pattern_readable: str           # Human-readable description
    category: str                   # eligibility, dosing, endpoints, etc.
    amendment_count: int            # How many times this pattern led to amendments
    total_occurrences: int          # How many times this pattern appears in all protocols
    amendment_frequency: float      # amendment_count / total_occurrences
    risk_level: str                 # high, medium, low
    typical_change: str             # Common type of change made
    example_original: str           # Example original text
    example_amended: str            # Example amended text
    source_protocols: List[str]     # Protocol IDs where this pattern was found


# Known high-risk patterns based on ICH-GCP and common amendment reasons
SEED_PATTERNS = {
    "eligibility": [
        {
            "pattern": r"\badequate\s+(?:renal|liver|hepatic|cardiac|bone\s+marrow)\s+function\b",
            "pattern_readable": "adequate [organ] function",
            "typical_change": "Added specific numeric thresholds (e.g., eGFR ≥60, AST/ALT ≤2.5× ULN)"
        },
        {
            "pattern": r"\bnormal\s+(?:renal|liver|hepatic|cardiac|laboratory|lab)\s+(?:function|values?)\b",
            "pattern_readable": "normal [organ] function/values",
            "typical_change": "Replaced with specific reference ranges"
        },
        {
            "pattern": r"\bappropriate\s+(?:for|to)\s+(?:study|treatment|enrollment)\b",
            "pattern_readable": "appropriate for [study/treatment]",
            "typical_change": "Specified objective criteria for appropriateness"
        },
        {
            "pattern": r"\bacceptable\s+(?:organ|cardiac|renal|liver)\s+function\b",
            "pattern_readable": "acceptable [organ] function",
            "typical_change": "Added measurable thresholds"
        },
        {
            "pattern": r"(?:ecog|who)\s+(?:performance\s+status|ps)\s*[≤<]\s*\d",
            "pattern_readable": "ECOG/WHO performance status criteria",
            "typical_change": "Modified threshold or added exceptions"
        },
        {
            "pattern": r"\blife\s+expectancy\s*(?:of)?\s*(?:at\s+least|>|≥)?\s*\d+\s*(?:weeks?|months?)\b",
            "pattern_readable": "life expectancy requirement",
            "typical_change": "Adjusted duration or clarified assessment method"
        }
    ],
    "dosing": [
        {
            "pattern": r"\bdose\s+(?:may|can|might)\s+be\s+(?:adjusted|modified|reduced)\b",
            "pattern_readable": "dose may be adjusted",
            "typical_change": "Pre-specified dose modification rules"
        },
        {
            "pattern": r"\bas\s+(?:needed|required|appropriate)\s+(?:for|based\s+on)\b",
            "pattern_readable": "as needed/required dosing",
            "typical_change": "Added specific criteria for dose changes"
        },
        {
            "pattern": r"\bstarting\s+dose\s+(?:of)?\s*\d+\s*(?:mg|mcg|g)\b",
            "pattern_readable": "starting dose specification",
            "typical_change": "Modified starting dose or added weight-based dosing"
        }
    ],
    "endpoints": [
        {
            "pattern": r"\bendpoint\s+will\s+be\s+(?:measured|assessed|evaluated)\b",
            "pattern_readable": "endpoint will be measured",
            "typical_change": "Specified exact measurement method and timepoint"
        },
        {
            "pattern": r"\bresponse\s+(?:will\s+be|to\s+be)\s+(?:assessed|evaluated|determined)\b",
            "pattern_readable": "response will be assessed",
            "typical_change": "Added RECIST criteria version and measurement timing"
        },
        {
            "pattern": r"\bprimary\s+(?:endpoint|outcome)\s*(?:is|:)?\s*(?:the)?\s*\w+\b",
            "pattern_readable": "primary endpoint definition",
            "typical_change": "Clarified operational definition and analysis method"
        }
    ],
    "safety": [
        {
            "pattern": r"\bsae\s+(?:will\s+be|should\s+be|must\s+be)\s+reported\b",
            "pattern_readable": "SAE reporting language",
            "typical_change": "Added 24-hour timeline and specific reporting procedures"
        },
        {
            "pattern": r"\bmonitoring\s+(?:will|may|should)\s+(?:be|include)\b",
            "pattern_readable": "monitoring language",
            "typical_change": "Specified monitoring frequency and parameters"
        },
        {
            "pattern": r"\bdiscontinue\s+(?:treatment|study\s+drug)\s+(?:if|when)\b",
            "pattern_readable": "discontinuation criteria",
            "typical_change": "Added specific toxicity grades and recovery requirements"
        }
    ],
    "statistics": [
        {
            "pattern": r"\banalysis\s+(?:may|will|can)\s+(?:include|be\s+performed|use)\b",
            "pattern_readable": "analysis method language",
            "typical_change": "Pre-specified all statistical methods in SAP"
        },
        {
            "pattern": r"\bif\s+(?:deemed\s+)?appropriate\b",
            "pattern_readable": "if [deemed] appropriate",
            "typical_change": "Removed conditional language, pre-specified approach"
        },
        {
            "pattern": r"\bsample\s+size\s+(?:of)?\s*(?:approximately)?\s*\d+\b",
            "pattern_readable": "sample size specification",
            "typical_change": "Updated power calculation or added interim analysis"
        }
    ],
    "schedule": [
        {
            "pattern": r"\bvisit\s+(?:windows?|timing)\s+(?:of|:)?\s*(?:approximately|about)?\s*\d+",
            "pattern_readable": "visit window specification",
            "typical_change": "Added explicit ± day tolerances"
        },
        {
            "pattern": r"\bassessments?\s+(?:at|on)\s+(?:day|week)\s+\d+\b",
            "pattern_readable": "assessment timing",
            "typical_change": "Added visit windows and rescheduling procedures"
        }
    ]
}


class AmendmentMiner:
    """Mine amendment patterns from protocol corpus"""

    def __init__(self, protocols_dir: Path):
        self.protocols_dir = Path(protocols_dir)
        self.results = {
            "protocols_processed": 0,
            "protocols_with_amendments": 0,
            "total_amendments": 0,
            "total_modifications": 0,
            "category_counts": Counter(),
            "patterns": defaultdict(list),
            "high_risk_patterns": [],
            "medium_risk_patterns": [],
            "low_risk_patterns": []
        }

    def mine_single_protocol(self, filepath: Path) -> Optional[Dict]:
        """Process a single protocol file"""
        amendments = parse_protocol_file(filepath)
        if not amendments:
            return None

        stats = get_amendment_statistics(amendments)
        return {
            "filepath": str(filepath),
            "amendments": amendments,
            "stats": stats
        }

    def mine_all_protocols(self, limit: Optional[int] = None, workers: int = 4) -> Dict:
        """
        Mine all protocols in the directory.

        Args:
            limit: Maximum number of protocols to process (for testing)
            workers: Number of parallel workers

        Returns:
            Mining results with patterns and statistics
        """
        protocol_files = sorted(self.protocols_dir.glob("protocol_*.txt"))

        if limit:
            protocol_files = protocol_files[:limit]

        logger.info(f"Processing {len(protocol_files)} protocol files...")

        # Process protocols
        processed = 0
        with_amendments = 0
        all_stats = []

        for i, filepath in enumerate(protocol_files):
            try:
                result = self.mine_single_protocol(filepath)
                processed += 1

                if result:
                    with_amendments += 1
                    all_stats.append(result["stats"])

                    # Aggregate categories
                    for category, count in result["stats"]["categories"].items():
                        self.results["category_counts"][category] += count

                    self.results["total_amendments"] += result["stats"]["total_amendments"]
                    self.results["total_modifications"] += result["stats"]["total_modifications"]

                if (i + 1) % 500 == 0:
                    logger.info(f"Processed {i + 1}/{len(protocol_files)} protocols...")

            except Exception as e:
                logger.error(f"Error processing {filepath}: {e}")

        self.results["protocols_processed"] = processed
        self.results["protocols_with_amendments"] = with_amendments
        self.results["all_stats"] = all_stats

        logger.info(f"Processed {processed} protocols, {with_amendments} with amendments")
        logger.info(f"Total amendments: {self.results['total_amendments']}")
        logger.info(f"Total modifications: {self.results['total_modifications']}")
        logger.info(f"Category distribution: {dict(self.results['category_counts'])}")

        return self.results

    def scan_for_patterns(self, limit: Optional[int] = None) -> Dict[str, List[Dict]]:
        """
        Scan protocols for seed patterns and calculate frequencies.

        Returns:
            Pattern statistics with amendment frequencies
        """
        protocol_files = sorted(self.protocols_dir.glob("protocol_*.txt"))
        if limit:
            protocol_files = protocol_files[:limit]

        pattern_stats = defaultdict(lambda: {
            "occurrences": 0,
            "in_amended_protocols": 0,
            "example_contexts": []
        })

        logger.info(f"Scanning {len(protocol_files)} protocols for risk patterns...")

        # Track which protocols have amendments
        amended_protocol_ids = set()

        for filepath in protocol_files:
            try:
                text = filepath.read_text(encoding='utf-8', errors='ignore')
                protocol_id = filepath.stem
                has_amendments = "Amendment" in text

                if has_amendments:
                    amended_protocol_ids.add(protocol_id)

                # Check each seed pattern
                for category, patterns in SEED_PATTERNS.items():
                    for pattern_info in patterns:
                        pattern = pattern_info["pattern"]
                        matches = re.findall(pattern, text, re.IGNORECASE)

                        if matches:
                            key = f"{category}::{pattern}"
                            pattern_stats[key]["occurrences"] += 1

                            if has_amendments:
                                pattern_stats[key]["in_amended_protocols"] += 1

                            # Store example context
                            if len(pattern_stats[key]["example_contexts"]) < 3:
                                for match in matches[:1]:
                                    # Extract surrounding context
                                    match_obj = re.search(pattern, text, re.IGNORECASE)
                                    if match_obj:
                                        start = max(0, match_obj.start() - 100)
                                        end = min(len(text), match_obj.end() + 100)
                                        context = text[start:end].replace('\n', ' ').strip()
                                        pattern_stats[key]["example_contexts"].append({
                                            "protocol_id": protocol_id,
                                            "context": context,
                                            "match": match_obj.group(0)
                                        })

            except Exception as e:
                logger.error(f"Error scanning {filepath}: {e}")

        # Calculate amendment frequencies
        risk_patterns = []
        for key, stats in pattern_stats.items():
            category, pattern = key.split("::", 1)

            if stats["occurrences"] > 0:
                amendment_freq = stats["in_amended_protocols"] / stats["occurrences"]

                # Find the pattern info
                pattern_info = None
                for p in SEED_PATTERNS.get(category, []):
                    if p["pattern"] == pattern:
                        pattern_info = p
                        break

                if pattern_info:
                    # Determine risk level
                    if amendment_freq >= 0.7:
                        risk_level = "high"
                    elif amendment_freq >= 0.4:
                        risk_level = "medium"
                    else:
                        risk_level = "low"

                    risk_patterns.append({
                        "pattern": pattern,
                        "pattern_readable": pattern_info["pattern_readable"],
                        "category": category,
                        "occurrences": stats["occurrences"],
                        "in_amended_protocols": stats["in_amended_protocols"],
                        "amendment_frequency": round(amendment_freq, 3),
                        "risk_level": risk_level,
                        "typical_change": pattern_info["typical_change"],
                        "examples": stats["example_contexts"]
                    })

        # Sort by amendment frequency
        risk_patterns.sort(key=lambda x: x["amendment_frequency"], reverse=True)

        return {
            "total_protocols_scanned": len(protocol_files),
            "protocols_with_amendments": len(amended_protocol_ids),
            "patterns": risk_patterns
        }

    def generate_risk_patterns_json(self, pattern_results: Dict, output_path: Path) -> None:
        """
        Generate the risk patterns JSON file for real-time prediction.
        """
        high_risk = [p for p in pattern_results["patterns"] if p["risk_level"] == "high"]
        medium_risk = [p for p in pattern_results["patterns"] if p["risk_level"] == "medium"]
        low_risk = [p for p in pattern_results["patterns"] if p["risk_level"] == "low"]

        output = {
            "metadata": {
                "generated_from": str(self.protocols_dir),
                "protocols_scanned": pattern_results["total_protocols_scanned"],
                "protocols_with_amendments": pattern_results["protocols_with_amendments"],
                "total_patterns": len(pattern_results["patterns"])
            },
            "high_risk_patterns": high_risk,
            "medium_risk_patterns": medium_risk,
            "low_risk_patterns": low_risk,
            "categories": list(SEED_PATTERNS.keys())
        }

        with open(output_path, 'w') as f:
            json.dump(output, f, indent=2)

        logger.info(f"Generated risk patterns JSON: {output_path}")
        logger.info(f"  - High risk patterns: {len(high_risk)}")
        logger.info(f"  - Medium risk patterns: {len(medium_risk)}")
        logger.info(f"  - Low risk patterns: {len(low_risk)}")


def main():
    parser = argparse.ArgumentParser(description="Mine amendment patterns from protocols")
    parser.add_argument("--sample", type=int, help="Process only N protocols for testing")
    parser.add_argument("--all", action="store_true", help="Process all protocols")
    parser.add_argument("--output", type=str, default=str(DEFAULT_OUTPUT_FILE),
                       help="Output JSON file path")
    parser.add_argument("--protocols-dir", type=str, default=str(DEFAULT_PROTOCOLS_DIR),
                       help="Directory containing protocol files")
    parser.add_argument("--scan-only", action="store_true",
                       help="Only scan for patterns, skip full mining")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    protocols_dir = Path(args.protocols_dir)
    if not protocols_dir.exists():
        logger.error(f"Protocols directory not found: {protocols_dir}")
        return

    miner = AmendmentMiner(protocols_dir)

    # Determine limit
    limit = args.sample if args.sample else (None if args.all else 100)

    if args.scan_only:
        # Only scan for patterns
        logger.info("Scanning for risk patterns...")
        pattern_results = miner.scan_for_patterns(limit=limit)

        print(f"\n=== Pattern Scan Results ===")
        print(f"Protocols scanned: {pattern_results['total_protocols_scanned']}")
        print(f"Protocols with amendments: {pattern_results['protocols_with_amendments']}")
        print(f"Patterns found: {len(pattern_results['patterns'])}")

        print(f"\n=== Top Risk Patterns ===")
        for p in pattern_results["patterns"][:10]:
            print(f"[{p['risk_level'].upper()}] {p['pattern_readable']}")
            print(f"    Category: {p['category']}")
            print(f"    Amendment frequency: {p['amendment_frequency']*100:.1f}%")
            print(f"    Occurrences: {p['occurrences']}")
            print()

        # Generate JSON
        output_path = Path(args.output)
        miner.generate_risk_patterns_json(pattern_results, output_path)

    else:
        # Full mining
        logger.info(f"Mining protocols (limit={limit})...")
        results = miner.mine_all_protocols(limit=limit)

        print(f"\n=== Mining Results ===")
        print(f"Protocols processed: {results['protocols_processed']}")
        print(f"Protocols with amendments: {results['protocols_with_amendments']}")
        print(f"Total amendments: {results['total_amendments']}")
        print(f"Total modifications: {results['total_modifications']}")
        print(f"\nCategory distribution:")
        for category, count in results['category_counts'].most_common():
            print(f"  {category}: {count}")

        # Also scan for patterns
        logger.info("\nScanning for risk patterns...")
        pattern_results = miner.scan_for_patterns(limit=limit)
        output_path = Path(args.output)
        miner.generate_risk_patterns_json(pattern_results, output_path)


if __name__ == "__main__":
    main()
