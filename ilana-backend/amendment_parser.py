"""
Amendment Parser (Layer 3: Risk Prediction)

Parses protocol amendment sections to extract:
- Modification descriptions and rationales
- Old text → New text pairs
- Affected protocol sections
- Amendment categories

Used by amendment_miner.py to build risk patterns from historical data.
"""

import re
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class TextChange:
    """Represents an old text → new text change"""
    old_text: str
    new_text: str
    section: str  # e.g., "Synopsis", "Section 6.1", "Eligibility"
    change_type: str  # "addition", "deletion", "modification"


@dataclass
class Modification:
    """Represents a single modification within an amendment"""
    modification_number: int
    title: str
    rationale: str
    affected_sections: List[str]
    text_changes: List[TextChange] = field(default_factory=list)
    category: str = "other"  # eligibility, dosing, endpoints, safety, schedule, statistics, administrative


@dataclass
class Amendment:
    """Represents a protocol amendment"""
    amendment_number: int
    date: Optional[str]
    version: Optional[str]
    modifications: List[Modification] = field(default_factory=list)
    overview: str = ""


@dataclass
class ProtocolAmendments:
    """All amendments for a single protocol"""
    protocol_id: str
    total_versions: int
    amendments: List[Amendment] = field(default_factory=list)


# Section patterns for categorization
SECTION_CATEGORIES = {
    "eligibility": [
        r"inclusion", r"exclusion", r"eligib", r"criteria",
        r"population", r"subject selection"
    ],
    "dosing": [
        r"dose", r"dosing", r"dosage", r"formulation", r"administration",
        r"drug.*supply", r"treatment.*assignment"
    ],
    "endpoints": [
        r"endpoint", r"outcome", r"efficacy", r"primary.*variable",
        r"secondary.*variable", r"measure"
    ],
    "safety": [
        r"safety", r"adverse", r"sae", r"toxicity", r"monitoring",
        r"discontinuation", r"withdrawal"
    ],
    "schedule": [
        r"schedule", r"visit", r"assessment", r"procedure",
        r"study.*design", r"duration"
    ],
    "statistics": [
        r"statistic", r"analysis", r"sample.*size", r"power",
        r"itt", r"per.*protocol", r"interim"
    ],
    "administrative": [
        r"typo", r"typing", r"correction", r"clarification",
        r"terminology", r"minor", r"editorial"
    ]
}


def categorize_modification(title: str, rationale: str, affected_sections: List[str]) -> str:
    """
    Categorize a modification based on its title, rationale, and affected sections.

    Returns: Category string (eligibility, dosing, endpoints, safety, schedule, statistics, administrative, other)
    """
    # Combine all text for analysis
    combined_text = f"{title} {rationale} {' '.join(affected_sections)}".lower()

    # Check each category's patterns
    category_scores = {}
    for category, patterns in SECTION_CATEGORIES.items():
        score = sum(1 for p in patterns if re.search(p, combined_text, re.IGNORECASE))
        if score > 0:
            category_scores[category] = score

    # Return highest scoring category, or "other" if none match
    if category_scores:
        return max(category_scores, key=category_scores.get)
    return "other"


def extract_amendment_sections(text: str) -> List[Tuple[int, str]]:
    """
    Find all amendment sections (Section 15.x) in the protocol text.

    Returns: List of (amendment_number, section_text) tuples
    """
    amendments = []

    # Pattern for amendment section headers
    # Matches: "15.1 Amendment 1", "15.2 Amendment 2", etc.
    pattern = r'(15\.(\d+)\s+Amendment\s+(\d+).*?)(?=15\.\d+\s+Amendment|\Z)'

    matches = re.finditer(pattern, text, re.DOTALL | re.IGNORECASE)

    for match in matches:
        section_text = match.group(1)
        amendment_num = int(match.group(3))
        amendments.append((amendment_num, section_text))

    return amendments


def extract_date_from_amendment(section_text: str) -> Optional[str]:
    """Extract amendment date from section text"""
    # Pattern: "Date of amendment: 31 Oct 2013"
    date_pattern = r'Date\s+of\s+amendment[:\s]+([A-Za-z0-9\s,]+\d{4})'
    match = re.search(date_pattern, section_text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def extract_modifications(section_text: str) -> List[Modification]:
    """
    Extract individual modifications from an amendment section.

    Parses:
    - Modification number and title
    - Rationale
    - Affected sections
    - Old text / New text pairs
    """
    modifications = []

    # Pattern for modification blocks
    # Matches: "Modification 1: Use of a further drug formulation"
    mod_pattern = r'Modification\s+(\d+)[:\s]+([^\n]+)'

    # Find all modification headers
    mod_headers = list(re.finditer(mod_pattern, section_text, re.IGNORECASE))

    for i, header_match in enumerate(mod_headers):
        mod_num = int(header_match.group(1))
        mod_title = header_match.group(2).strip()

        # Extract text until next modification or end of section
        start_pos = header_match.end()
        if i + 1 < len(mod_headers):
            end_pos = mod_headers[i + 1].start()
        else:
            end_pos = len(section_text)

        mod_text = section_text[start_pos:end_pos]

        # Extract rationale
        rationale = ""
        rationale_match = re.search(
            r'Rationale\s+for\s+(?:introducing\s+)?Modification\s*\d*[:\s]+(.+?)(?=List\s+of\s+all|Modification\s+\d|$)',
            mod_text, re.DOTALL | re.IGNORECASE
        )
        if rationale_match:
            rationale = rationale_match.group(1).strip()
            # Clean up rationale text
            rationale = re.sub(r'\s+', ' ', rationale)
            rationale = rationale[:500]  # Limit length

        # Extract affected sections
        affected_sections = []
        sections_match = re.search(
            r'List\s+of\s+all\s+CSP\s+sections\s+affected.*?[:\s]+((?:[-•]\s*Section[\s\d.]+\n?)+)',
            mod_text, re.DOTALL | re.IGNORECASE
        )
        if sections_match:
            sections_text = sections_match.group(1)
            affected_sections = re.findall(r'Section\s+([\d.]+)', sections_text)

        # Categorize the modification
        category = categorize_modification(mod_title, rationale, affected_sections)

        # Extract text changes (Old text / New text pairs)
        text_changes = extract_text_changes(mod_text)

        modifications.append(Modification(
            modification_number=mod_num,
            title=mod_title,
            rationale=rationale,
            affected_sections=affected_sections,
            text_changes=text_changes,
            category=category
        ))

    return modifications


def extract_text_changes(mod_text: str) -> List[TextChange]:
    """
    Extract Old text → New text pairs from modification text.

    Looks for patterns like:
    - "Old text: ... New text: ..."
    - Strikethrough (crossed out) text
    - Underlined (added) text
    """
    changes = []

    # Pattern 1: Explicit Old text / New text blocks
    pattern = r'Old\s+text[:\s]*(.+?)New\s+text[:\s]*(.+?)(?=Old\s+text|Modification|$)'
    matches = re.finditer(pattern, mod_text, re.DOTALL | re.IGNORECASE)

    for match in matches:
        old_text = match.group(1).strip()
        new_text = match.group(2).strip()

        # Clean up text
        old_text = re.sub(r'\s+', ' ', old_text)[:1000]
        new_text = re.sub(r'\s+', ' ', new_text)[:1000]

        # Determine section from context
        section = "Unknown"
        section_match = re.search(r'Section\s+([\d.]+)', mod_text[:match.start()])
        if section_match:
            section = f"Section {section_match.group(1)}"

        # Determine change type
        change_type = "modification"
        if len(old_text) < 10 or old_text.lower() in ["...", "n/a", "-"]:
            change_type = "addition"
        elif len(new_text) < 10 or new_text.lower() in ["...", "n/a", "-"]:
            change_type = "deletion"

        changes.append(TextChange(
            old_text=old_text,
            new_text=new_text,
            section=section,
            change_type=change_type
        ))

    return changes


def parse_protocol_amendments(protocol_text: str, protocol_id: str = "unknown") -> ProtocolAmendments:
    """
    Main entry point: Parse all amendments from a protocol document.

    Args:
        protocol_text: Full text of the protocol document
        protocol_id: Identifier for the protocol

    Returns:
        ProtocolAmendments object with all parsed amendments
    """
    result = ProtocolAmendments(
        protocol_id=protocol_id,
        total_versions=1,
        amendments=[]
    )

    # Extract version count from cover page
    version_match = re.search(r'Version\s+(\d+(?:\.\d+)?)', protocol_text[:2000])
    if version_match:
        try:
            result.total_versions = int(float(version_match.group(1)))
        except ValueError:
            pass

    # Find all amendment sections
    amendment_sections = extract_amendment_sections(protocol_text)

    for amendment_num, section_text in amendment_sections:
        # Extract date
        date = extract_date_from_amendment(section_text)

        # Extract overview
        overview = ""
        overview_match = re.search(
            r'Overview\s+of\s+changes[:\s]*(.+?)(?=Modification\s+\d|Changes\s+to\s+the\s+protocol|$)',
            section_text, re.DOTALL | re.IGNORECASE
        )
        if overview_match:
            overview = re.sub(r'\s+', ' ', overview_match.group(1).strip())[:500]

        # Extract modifications
        modifications = extract_modifications(section_text)

        amendment = Amendment(
            amendment_number=amendment_num,
            date=date,
            version=None,
            modifications=modifications,
            overview=overview
        )

        result.amendments.append(amendment)

    return result


def parse_protocol_file(filepath: Path) -> Optional[ProtocolAmendments]:
    """
    Parse amendments from a protocol file.

    Args:
        filepath: Path to the protocol text file

    Returns:
        ProtocolAmendments or None if parsing fails
    """
    try:
        protocol_id = filepath.stem  # e.g., "protocol_000001"
        text = filepath.read_text(encoding='utf-8', errors='ignore')

        # Check if this protocol has amendments
        if 'Amendment' not in text:
            return None

        return parse_protocol_amendments(text, protocol_id)

    except Exception as e:
        logger.error(f"Failed to parse {filepath}: {e}")
        return None


def get_amendment_statistics(amendments: ProtocolAmendments) -> Dict:
    """
    Generate statistics for a protocol's amendments.
    """
    stats = {
        "protocol_id": amendments.protocol_id,
        "total_versions": amendments.total_versions,
        "total_amendments": len(amendments.amendments),
        "total_modifications": sum(len(a.modifications) for a in amendments.amendments),
        "categories": {},
        "has_eligibility_changes": False,
        "has_dosing_changes": False,
        "has_endpoint_changes": False,
        "has_safety_changes": False
    }

    for amendment in amendments.amendments:
        for mod in amendment.modifications:
            stats["categories"][mod.category] = stats["categories"].get(mod.category, 0) + 1

            if mod.category == "eligibility":
                stats["has_eligibility_changes"] = True
            elif mod.category == "dosing":
                stats["has_dosing_changes"] = True
            elif mod.category == "endpoints":
                stats["has_endpoint_changes"] = True
            elif mod.category == "safety":
                stats["has_safety_changes"] = True

    return stats


# CLI for testing
if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) > 1:
        filepath = Path(sys.argv[1])
        if filepath.exists():
            result = parse_protocol_file(filepath)
            if result:
                print(f"\n=== Protocol: {result.protocol_id} ===")
                print(f"Total versions: {result.total_versions}")
                print(f"Total amendments: {len(result.amendments)}")

                for amendment in result.amendments:
                    print(f"\n--- Amendment {amendment.amendment_number} ({amendment.date}) ---")
                    print(f"Overview: {amendment.overview[:200]}...")
                    print(f"Modifications: {len(amendment.modifications)}")

                    for mod in amendment.modifications:
                        print(f"  [{mod.category.upper()}] {mod.title}")
                        print(f"    Rationale: {mod.rationale[:150]}...")
                        print(f"    Affected sections: {', '.join(mod.affected_sections[:5])}")
                        print(f"    Text changes: {len(mod.text_changes)}")

                stats = get_amendment_statistics(result)
                print(f"\n=== Statistics ===")
                print(f"Categories: {stats['categories']}")
            else:
                print("No amendments found in protocol")
        else:
            print(f"File not found: {filepath}")
    else:
        print("Usage: python amendment_parser.py <protocol_file.txt>")
