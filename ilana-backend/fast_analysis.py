#!/usr/bin/env python3
"""
Fast Analysis Module - Optimized for Sub-15s Response Times

Provides lightweight protocol analysis for interactive selections using:
- Up to 15000 chars (full protocol sections)
- Fast Azure model (gpt-4o-mini by default)
- Lightweight RAG: Pinecone + PubMedBERT (top 3 exemplars, 2s timeout)
- Domain-expert ICH-GCP prompts with regulatory guidance
- Aggressive timeouts and caching

For deep analysis with full RAG stack + citations, use background job queue.
"""

import os
import re
import time
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from difflib import SequenceMatcher
import asyncio

# Step 4: Import prompt optimization utilities
from prompt_optimizer import build_fast_prompt, track_token_usage, count_tokens_precise

# Step 6: Import enhanced cache manager
from cache_manager import get_cached, set_cached

# Step 7: Import metrics collector
from metrics_collector import record_request

# Step 8: Import lightweight RAG for fast path
from fast_rag import get_fast_exemplars

# Step 9: Import rule-based compliance engine
from compliance_rules import run_compliance_checks

# Step 10: Import suggestion validator (Phase 2A)
from suggestion_validator import validate_suggestions_batch

logger = logging.getLogger(__name__)

# Configuration - Premium Quality (GPT-4o)
# CRITICAL: Azure OpenAI requires deployment name, not model name!
AZURE_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT") or os.getenv("ANALYSIS_FAST_MODEL", "gpt-4o-deployment")
FAST_MODEL = AZURE_DEPLOYMENT  # Use deployment name for Azure OpenAI compatibility
FAST_TIMEOUT_MS = int(os.getenv("SIMPLE_PROMPT_TIMEOUT_MS", "40000"))  # 40 second timeout - Azure OpenAI can be slow
FAST_MAX_TOKENS = int(os.getenv("FAST_MAX_TOKENS", "2000"))  # Increased for detailed regulatory citations
FAST_TEMPERATURE = 0.2  # Low temperature for consistent regulatory citations
SELECTION_CHUNK_THRESHOLD = int(os.getenv("SELECTION_CHUNK_THRESHOLD", "15000"))  # 15000 chars = full protocol sections


# Old cache functions removed in Step 6 - now using cache_manager


def _calculate_text_overlap(text1: str, text2: str) -> float:
    """
    Calculate text overlap percentage between two strings

    Uses character-level comparison to detect if two suggestions
    are targeting the same text (e.g., rule-based and AI both
    flagging "subjects" → "participants")

    Args:
        text1: First text string
        text2: Second text string

    Returns:
        Overlap ratio (0.0 to 1.0)
    """
    if not text1 or not text2:
        return 0.0

    # Normalize: lowercase, strip whitespace
    t1 = text1.lower().strip()
    t2 = text2.lower().strip()

    # Calculate character overlap using set intersection
    set1 = set(t1)
    set2 = set(t2)

    intersection = len(set1 & set2)
    union = len(set1 | set2)

    if union == 0:
        return 0.0

    # Jaccard similarity for character sets
    jaccard = intersection / union

    # Also check substring containment (one text contains the other)
    if t1 in t2 or t2 in t1:
        return max(jaccard, 0.8)  # Boost score if one contains the other

    return jaccard


def _deduplicate_ai_suggestions(
    ai_suggestions: List[Dict[str, Any]],
    request_id: str
) -> List[Dict[str, Any]]:
    """
    Deduplicate AI suggestions that have identical or highly similar original text.

    When the LLM returns multiple issues pointing to the same text (but with different
    categories/severities), merge them into a single suggestion with the highest severity.

    Args:
        ai_suggestions: List of AI-generated issue dicts
        request_id: Request tracking ID

    Returns:
        Deduplicated list with one suggestion per unique text
    """
    if not ai_suggestions:
        return []

    # Group by normalized text
    text_groups: Dict[str, List[Dict[str, Any]]] = {}

    for sugg in ai_suggestions:
        text = sugg.get("text", "").strip().lower()
        if not text:
            continue

        # Normalize whitespace for comparison
        normalized = " ".join(text.split())

        if normalized not in text_groups:
            text_groups[normalized] = []
        text_groups[normalized].append(sugg)

    # For each group, keep only the highest severity suggestion
    severity_order = {"critical": 0, "major": 1, "minor": 2, "advisory": 3}
    deduplicated = []
    duplicates_removed = 0

    for normalized_text, group in text_groups.items():
        if len(group) == 1:
            deduplicated.append(group[0])
        else:
            # Multiple suggestions for same text - keep highest severity
            sorted_group = sorted(
                group,
                key=lambda s: severity_order.get(s.get("severity", "minor"), 2)
            )
            best = sorted_group[0]
            duplicates_removed += len(group) - 1

            # Log the merge
            logger.info(
                f"🔄 [{request_id}] Merged {len(group)} duplicate AI suggestions "
                f"for text: '{best.get('text', '')[:50]}...' → keeping {best.get('severity')} severity"
            )

            deduplicated.append(best)

    if duplicates_removed > 0:
        logger.info(
            f"🔍 [{request_id}] AI deduplication: Removed {duplicates_removed} duplicate AI issues "
            f"(same text, different severity/category)"
        )

    return deduplicated


def _deduplicate_suggestions(
    rule_suggestions: List[Dict[str, Any]],
    ai_suggestions: List[Dict[str, Any]],
    request_id: str
) -> List[Dict[str, Any]]:
    """
    Deduplicate rule-based and AI suggestions

    Strategy:
    - When rule-based and AI suggestions overlap (>70% text similarity),
      keep only the AI suggestion (better rationale, more context)
    - ALSO check category/type matching for rule-based placeholders
    - Keep all unique suggestions from both sources

    Args:
        rule_suggestions: List of rule-based issue dicts
        ai_suggestions: List of AI-generated issue dicts
        request_id: Request tracking ID

    Returns:
        Deduplicated list of suggestions (AI + unique rule-based)
    """
    OVERLAP_THRESHOLD = 0.7  # 70% text overlap = considered duplicate

    # Start with all AI suggestions (higher quality)
    deduplicated = ai_suggestions.copy()

    # Track which rule suggestions to keep
    unique_rule_suggestions = []
    duplicates_found = 0

    for rule_sugg in rule_suggestions:
        rule_text = rule_sugg.get("text", "")
        rule_type = rule_sugg.get("type", "")

        # Check if this rule suggestion overlaps with any AI suggestion
        is_duplicate = False

        for ai_sugg in ai_suggestions:
            ai_text = ai_sugg.get("text", "")
            ai_type = ai_sugg.get("type", "")

            # Method 1: Text overlap (for real text)
            overlap = _calculate_text_overlap(rule_text, ai_text)

            # Method 2: Category/type matching (for rule-based placeholders)
            # If rule-based uses placeholder like "[Rule-based detection: ...]",
            # check if both suggestions target the same category
            same_category = (rule_type == ai_type) and rule_type != ""
            is_rule_placeholder = rule_text.startswith("[Rule-based detection:")

            # Consider duplicate if either:
            # 1. High text overlap (>70%)
            # 2. Same category AND rule uses placeholder format
            if overlap >= OVERLAP_THRESHOLD or (same_category and is_rule_placeholder):
                # Duplicate found - AI suggestion already covers this
                is_duplicate = True
                duplicates_found += 1

                match_method = "text overlap" if overlap >= OVERLAP_THRESHOLD else "category match"
                overlap_str = f"{overlap:.2f}" if overlap >= OVERLAP_THRESHOLD else "N/A"
                logger.debug(
                    f"📍 [{request_id}] Deduplication: Skipping rule-based '{rule_type}' "
                    f"({match_method}: {overlap_str})"
                )
                break

        if not is_duplicate:
            # Unique rule-based suggestion - keep it
            unique_rule_suggestions.append(rule_sugg)

    # Add unique rule-based suggestions to final list
    deduplicated.extend(unique_rule_suggestions)

    if duplicates_found > 0:
        logger.info(
            f"🔍 [{request_id}] Deduplication: Removed {duplicates_found} duplicate rule-based issues, "
            f"kept {len(unique_rule_suggestions)} unique rule-based + {len(ai_suggestions)} AI suggestions"
        )

    return deduplicated


def _match_llm_text_to_original(llm_text: str, original_text: str, threshold: float = 0.8) -> str:
    """
    Find the best matching substring in original_text for the LLM's paraphrased text.
    Returns the verbatim substring from original_text if found, otherwise returns llm_text unchanged.

    This fixes the issue where LLM paraphrases text (changes punctuation, omits parentheticals,
    etc.) and the frontend can't find the exact text in the document.

    Uses sentence-level matching first, then sliding window with validation to avoid
    returning truncated fragments (e.g., unbalanced parentheses).

    Args:
        llm_text: The text returned by the LLM (may be paraphrased)
        original_text: The original selected text from the document
        threshold: Minimum similarity ratio to consider a match (default 0.8)

    Returns:
        The best matching substring from original_text, or llm_text if no good match found
    """
    if not llm_text or not original_text:
        return llm_text

    llm_text_clean = llm_text.strip()
    original_clean = original_text.strip()

    # 1. Exact match - return immediately
    if llm_text_clean in original_clean:
        start = original_clean.find(llm_text_clean)
        return original_clean[start:start + len(llm_text_clean)]

    # 2. Sentence-level matching (preferred - always returns complete sentences)
    sentences = re.split(r'(?<=[.!?])\s+', original_clean)
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        ratio = SequenceMatcher(None, llm_text_clean.lower(), sentence.lower()).ratio()
        if ratio > 0.75:  # Higher threshold for sentence-level match
            return sentence

    # 3. Sliding window fallback with validation
    # Only accept matches that have balanced parentheses/quotes
    best_match = None
    best_ratio = threshold

    words = original_clean.split()
    llm_word_count = len(llm_text_clean.split())

    for window_words in range(max(1, llm_word_count - 5), min(len(words) + 1, llm_word_count + 10)):
        for i in range(max(0, len(words) - window_words + 1)):
            candidate = ' '.join(words[i:i + window_words])

            # VALIDATION: Skip if unbalanced parentheses (prevents truncated fragments)
            if candidate.count('(') != candidate.count(')'):
                continue

            # VALIDATION: Skip if unbalanced quotes
            if candidate.count('"') % 2 != 0:
                continue

            ratio = SequenceMatcher(None, llm_text_clean.lower(), candidate.lower()).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = candidate

    # 4. Return best valid match, or fall back to LLM text (unchanged)
    return best_match if best_match else llm_text


def _extract_problematic_text_from_minimal_fix(minimal_fix: str, original_text: str) -> Optional[str]:
    """
    Extract the problematic text from a minimal_fix field.

    Parses patterns like:
    - "'may' → 'will'"
    - "'may be reassigned' → 'will be analyzed'"
    - "may → will"

    Returns the left side if it exists in original_text, else None.
    """
    if not minimal_fix:
        return None

    # Try to match quoted pattern: 'old' → 'new' or "old" → "new"
    match = re.match(r"['\"](.+?)['\"].*→", minimal_fix)
    if match:
        extracted = match.group(1).strip()
        if extracted.lower() in original_text.lower():
            return extracted

    # Try unquoted pattern: old → new
    if '→' in minimal_fix:
        left_side = minimal_fix.split('→')[0].strip().strip("'\"")
        if left_side and left_side.lower() in original_text.lower():
            return left_side

    return None


def _ensure_problematic_text(suggestions: List[Dict[str, Any]], original_selection: str) -> List[Dict[str, Any]]:
    """
    Ensure all suggestions have problematic_text populated for word-level highlighting.

    Fallback chain:
    1. Use existing problematic_text if valid (exists in document)
    2. Extract from minimal_fix if available
    3. Leave as-is (frontend will highlight full text field)
    """
    for suggestion in suggestions:
        problematic = suggestion.get('problematic_text')

        # Skip if already populated and exists in document
        if problematic and problematic.lower() in original_selection.lower():
            continue

        # Try to extract from minimal_fix
        minimal_fix = suggestion.get('minimal_fix')
        if minimal_fix:
            extracted = _extract_problematic_text_from_minimal_fix(minimal_fix, original_selection)
            if extracted:
                suggestion['problematic_text'] = extracted

        # Fallback: leave problematic_text as-is or null
        # Frontend will use full text field for highlighting

    return suggestions


def _group_suggestions_by_text(
    suggestions: List[Dict[str, Any]],
    request_id: str
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """
    Group suggestions that target the same or very similar original text

    Strategy:
    - Use existing _calculate_text_overlap() to find similar "text" fields
    - When multiple suggestions target same text (>70% similarity):
      - Create ONE grouped suggestion with multiple sub-issues
      - Use highest-confidence suggestion as primary improved text
      - Preserve all rationales/recommendations as sub-points
      - Use highest severity from group

    Args:
        suggestions: List of deduplicated suggestions
        request_id: Request tracking ID

    Returns:
        (grouped_suggestions, stats_dict)
    """
    GROUPING_THRESHOLD = 0.7  # 70% text overlap = group together

    if len(suggestions) <= 1:
        # No grouping needed
        return suggestions, {"groups_created": 0, "suggestions_grouped": 0}

    # Track which suggestions have been grouped
    grouped_indices = set()
    grouped_suggestions = []
    groups_created = 0
    suggestions_grouped = 0

    for i, suggestion in enumerate(suggestions):
        if i in grouped_indices:
            continue  # Already part of a group

        # Find all suggestions that overlap with this one
        group = [suggestion]
        group_indices = [i]

        for j in range(i + 1, len(suggestions)):
            if j in grouped_indices:
                continue

            other = suggestions[j]
            overlap = _calculate_text_overlap(
                suggestion.get("text", ""),
                other.get("text", "")
            )

            if overlap >= GROUPING_THRESHOLD:
                group.append(other)
                group_indices.append(j)
                grouped_indices.add(j)

        # If group has multiple suggestions, create grouped suggestion
        if len(group) > 1:
            # Mark all as grouped
            for idx in group_indices:
                grouped_indices.add(idx)

            # Find suggestion with highest confidence
            best_suggestion = max(group, key=lambda s: s.get("confidence", 0.0))

            # Find highest severity
            severity_order = ["critical", "major", "minor", "advisory"]
            severities = [s.get("severity", "minor") for s in group]
            highest_severity = min(severities, key=lambda s: severity_order.index(s) if s in severity_order else 999)

            # Create grouped suggestion
            grouped_sugg = {
                "id": f"{request_id}_group_{groups_created + 1}",
                "text": best_suggestion.get("text", ""),  # Use best suggestion's original text
                "suggestion": best_suggestion.get("suggestion", ""),  # Use best suggestion's improved text
                "rationale": f"Multiple issues found ({len(group)} total). See sub-issues below for details.",
                "confidence": best_suggestion.get("confidence", 0.8),
                "type": "grouped",
                "severity": highest_severity,
                "recommendation": "Review all sub-issues and address each concern.",
                "source": best_suggestion.get("source", "llm"),
                "grouped": True,
                "sub_issues": [
                    {
                        "id": s.get("id", ""),
                        "type": s.get("type", ""),
                        "severity": s.get("severity", "minor"),
                        "rationale": s.get("rationale", ""),
                        "recommendation": s.get("recommendation", ""),
                        "confidence": s.get("confidence", 0.8)
                    }
                    for s in group
                ]
            }

            grouped_suggestions.append(grouped_sugg)
            groups_created += 1
            suggestions_grouped += len(group)

            logger.info(
                f"📦 [{request_id}] Grouped {len(group)} suggestions into group_{groups_created}: "
                f"types=[{', '.join([s.get('type', 'unknown') for s in group])}]"
            )

        else:
            # Single suggestion - keep as is
            grouped_suggestions.append(suggestion)

    stats = {
        "groups_created": groups_created,
        "suggestions_grouped": suggestions_grouped,
        "total_before_grouping": len(suggestions),
        "total_after_grouping": len(grouped_suggestions)
    }

    if groups_created > 0:
        logger.info(
            f"📦 [{request_id}] Grouping complete: {groups_created} groups created, "
            f"{suggestions_grouped} suggestions consolidated, "
            f"{len(suggestions)} → {len(grouped_suggestions)} total cards"
        )

    return grouped_suggestions, stats


async def _analyze_oversized_selection(
    text: str,
    section: Optional[str] = None,
    ta: Optional[str] = None,
    phase: Optional[str] = None,
    request_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Quick analysis for oversized selections (>15000 chars).

    Runs only fast layers (Layer 1 + Layer 3) without RAG/LLM to avoid timeouts.
    Returns immediately with available results and guidance message.

    Args:
        text: Full selected text (any size)
        section: Optional protocol section
        ta: Optional therapeutic area
        phase: Optional study phase
        request_id: Request tracking ID

    Returns:
        Response with selection_too_large flag and quick analysis results
    """
    start_time = time.time()
    req_id = request_id or f"oversized_{int(time.time() * 1000)}"

    logger.warning(
        f"⚠️ [{req_id}] Oversized selection: {len(text)} chars > {SELECTION_CHUNK_THRESHOLD} limit. "
        f"Running quick analysis only (Layer 1 + 3)."
    )

    suggestions = []

    # Layer 1: Run rule-based compliance checks (fast, <10ms)
    rule_start = time.time()
    try:
        rule_issues = run_compliance_checks(text, section=section)
        for rule_issue in rule_issues:
            suggestions.append({
                "id": rule_issue.get("id"),
                "text": rule_issue.get("original_text"),
                "suggestion": rule_issue.get("improved_text"),
                "rationale": rule_issue.get("rationale"),
                "confidence": rule_issue.get("confidence"),
                "type": rule_issue.get("category"),
                "severity": rule_issue.get("severity"),
                "recommendation": rule_issue.get("recommendation"),
                "source": "rule_engine"
            })
        logger.info(f"✅ [{req_id}] Layer 1 (rules): {len(rule_issues)} issues found")
    except Exception as e:
        logger.warning(f"⚠️ [{req_id}] Rule engine failed: {e}")
    rule_ms = int((time.time() - rule_start) * 1000)

    # Layer 3: Run amendment risk prediction (fast, <50ms)
    amendment_start = time.time()
    try:
        from amendment_risk import predict_amendment_risk, format_risk_for_suggestion
        risk_predictions = predict_amendment_risk(text, section=section, min_risk_level="medium", max_results=5)
        for pred in risk_predictions:
            risk = format_risk_for_suggestion(pred)
            suggestions.append({
                "id": risk.get("id"),
                "text": risk.get("original_text"),
                "suggestion": risk.get("improved_text"),
                "rationale": risk.get("rationale"),
                "confidence": risk.get("confidence"),
                "type": risk.get("category"),
                "severity": risk.get("severity"),
                "recommendation": risk.get("recommendation"),
                "source": "amendment_risk",
                "amendment_risk": risk.get("amendment_risk")
            })
        logger.info(f"✅ [{req_id}] Layer 3 (amendment risk): {len(risk_predictions)} patterns found")
    except ImportError:
        logger.debug("Amendment risk module not available")
    except Exception as e:
        logger.warning(f"⚠️ [{req_id}] Amendment risk failed: {e}")
    amendment_ms = int((time.time() - amendment_start) * 1000)

    total_ms = int((time.time() - start_time) * 1000)

    logger.info(
        f"✅ [{req_id}] Quick analysis complete: {total_ms}ms "
        f"({len(suggestions)} suggestions from Layer 1 + 3)"
    )

    return {
        "status": "fast",
        "request_id": req_id,
        "suggestions": suggestions,
        "selection_too_large": True,
        "char_count": len(text),
        "char_limit": SELECTION_CHUNK_THRESHOLD,
        "message": (
            f"Selection exceeds {SELECTION_CHUNK_THRESHOLD:,} characters ({len(text):,} selected). "
            f"Showing quick analysis only. For deeper AI-powered analysis, select a smaller section."
        ),
        "metadata": {
            "rule_engine_ms": rule_ms,
            "amendment_risk_ms": amendment_ms,
            "total_ms": total_ms,
            "model": None,  # No LLM used
            "cache_hit": False,
            "text_length": len(text),
            "trimmed": False,
            "timestamp": datetime.utcnow().isoformat(),
            "rule_issues_count": len([s for s in suggestions if s.get("source") == "rule_engine"]),
            "amendment_risk_count": len([s for s in suggestions if s.get("source") == "amendment_risk"]),
            "llm_issues_count": 0,
            "rag_exemplars": 0,
            "rag_enabled": False,
            "deep_analysis_available": False
        }
    }


async def analyze_fast(
    text: str,
    ta: Optional[str] = None,
    phase: Optional[str] = None,
    section: Optional[str] = None,  # Section-aware validation (Layer 2)
    request_id: Optional[str] = None,
    is_table: bool = False,  # New parameter for table detection
    document_namespace: Optional[str] = None,  # Document intelligence namespace
    use_templates: bool = True  # Week 5: A/B testing flag for template injection
) -> Dict[str, Any]:
    """
    Fast synchronous analysis for protocol sections

    Target: < 15 seconds total (typically 3-8s for uncached)

    Note: Trial model (14-day trial) provides full features for all users.
    Feature gating removed - all analysis capabilities are enabled.

    Args:
        text: Selected protocol text (up to 15000 chars = full sections)
        ta: Optional therapeutic area
        phase: Optional study phase
        section: Optional protocol section (eligibility, endpoints, statistics, etc.)
        request_id: Request tracking ID
        is_table: Whether the selection is table data
        document_namespace: Optional Pinecone namespace for document context
        use_templates: Whether to inject suggestion templates into prompt (default: True). Set to False for A/B testing.

    Returns:
        {
            "status": "fast",
            "request_id": str,
            "suggestions": [{"id", "text", "suggestion", "rationale", "confidence", "type"}],
            "metadata": {"latency_ms", "model", "cache_hit", ...}
        }
    """
    start_time = time.time()
    req_id = request_id or f"fast_{int(time.time() * 1000)}"

    # Full features enabled for all users (14-day trial model)
    # No tier-based feature gating - all capabilities active during trial
    enable_rag = True
    enable_amendment_risk = True
    enable_table_analysis = True
    enable_document_intelligence = True

    logger.info(f"⚡ Fast analysis start: {req_id} (text_len={len(text)})")

    # Timing breakdown
    timings = {
        "preprocess_ms": 0,
        "rule_engine_ms": 0,
        "amendment_risk_ms": 0,  # Layer 3: Risk Prediction
        "rag_ms": 0,
        "azure_ms": 0,
        "validation_ms": 0,  # Phase 2A
        "postprocess_ms": 0,
        "total_ms": 0
    }

    try:
        # 1. Preprocess: Check text size and handle oversized selections
        preprocess_start = time.time()

        if len(text) > SELECTION_CHUNK_THRESHOLD:
            # Hybrid strategy: Return quick analysis (Layer 1 + 3 only) for oversized selections
            logger.warning(f"⚠️ Text exceeds fast threshold ({len(text)} > {SELECTION_CHUNK_THRESHOLD})")
            return await _analyze_oversized_selection(
                text=text,
                section=section,
                ta=ta,
                phase=phase,
                request_id=req_id
            )

        # Text is within limits - proceed with full analysis
        trimmed_text = text

        # 1a. Run rule-based compliance checks (< 1ms, deterministic)
        rule_engine_start = time.time()
        rule_issues = []

        try:
            # Pass section for section-aware severity/confidence overrides (Layer 2)
            rule_issues = run_compliance_checks(trimmed_text, section=section)
            if rule_issues:
                logger.info(f"🔍 [{req_id}] Rule engine found {len(rule_issues)} issues (section={section or 'general'})")
        except Exception as e:
            logger.warning(f"⚠️ [{req_id}] Rule engine failed: {e}")

        timings["rule_engine_ms"] = int((time.time() - rule_engine_start) * 1000)

        # 1b. Run amendment risk prediction (Layer 3: Risk Prediction) - TIER GATED
        amendment_risk_start = time.time()
        amendment_risks = []

        if enable_amendment_risk:
            try:
                from amendment_risk import predict_amendment_risk, format_risk_for_suggestion
                risk_predictions = predict_amendment_risk(trimmed_text, section=section, min_risk_level="medium", max_results=3)
                if risk_predictions:
                    amendment_risks = [format_risk_for_suggestion(pred) for pred in risk_predictions]
                    logger.info(f"⚠️ [{req_id}] Amendment risk: {len(amendment_risks)} patterns detected (section={section or 'general'})")
            except ImportError as e:
                logger.warning(f"⚠️ [{req_id}] Amendment risk import failed: {e}")
            except Exception as e:
                logger.warning(f"⚠️ [{req_id}] Amendment risk prediction failed: {e}")
        # Amendment risk is always enabled during trial

        timings["amendment_risk_ms"] = int((time.time() - amendment_risk_start) * 1000)

        # 1c. Retrieve document context and cross-section conflicts (Document Intelligence) - TIER GATED
        document_context_start = time.time()
        document_context = None
        timeline = None  # Phase 4: Timeline for schedule-aware prompts
        cross_section_conflicts = []

        if document_namespace and enable_document_intelligence:
            try:
                from document_cache import get_document_conflicts, get_document_cache
                from cross_section_engine import get_relevant_conflicts

                # Get document cache
                cache = get_document_cache()
                fingerprint = document_namespace.replace("doc_", "")

                # Get section summaries for context
                if fingerprint in cache._cache:
                    section_summaries = cache._cache[fingerprint].section_summaries
                    # Build related section context for prompt injection
                    from document_processor import SECTION_RELATIONSHIPS
                    related_sections = SECTION_RELATIONSHIPS.get(section, [])
                    document_context = {
                        "section_summaries": {k: v for k, v in section_summaries.items() if k in related_sections},
                        "current_section": section,
                    }
                    logger.info(f"📄 [{req_id}] Retrieved document context: {list(document_context['section_summaries'].keys())}")

                # Get timeline for this document (Phase 4: Timeline-aware prompts)
                timeline = cache.get_timeline(fingerprint) if hasattr(cache, 'get_timeline') else None
                if timeline:
                    logger.info(f"📅 [{req_id}] Retrieved timeline: {len(timeline.visits) if hasattr(timeline, 'visits') else 0} visits")

                # Get relevant cross-section conflicts for this section
                all_conflicts = get_document_conflicts(fingerprint)
                if all_conflicts:
                    cross_section_conflicts = get_relevant_conflicts(section or "general", all_conflicts)
                    logger.info(f"🔀 [{req_id}] Retrieved {len(cross_section_conflicts)} relevant cross-section conflicts")

            except ImportError as e:
                logger.debug(f"Document intelligence modules not available: {e}")
            except Exception as e:
                logger.warning(f"⚠️ [{req_id}] Document context retrieval failed: {e}")

        timings["document_context_ms"] = int((time.time() - document_context_start) * 1000)

        # Check cache (Step 6: Enhanced cache manager)
        # Week 5: Add variant to cache key for A/B testing
        cache_variant = "no_templates" if not use_templates else None
        cached_result = get_cached(
            text=trimmed_text,
            model=FAST_MODEL,
            ta=ta,
            phase=phase,
            analysis_type="fast",
            variant=cache_variant
        )

        if cached_result:
            total_ms = int((time.time() - start_time) * 1000)
            cached_result["metadata"]["cache_hit"] = True
            cached_result["metadata"]["total_ms"] = total_ms
            logger.info(f"✅ Returning cached result: {req_id}")

            # Step 7: Record cache hit metrics
            record_request(
                request_id=req_id,
                endpoint="/api/analyze",
                duration_ms=total_ms,
                status_code=200,
                path_type="fast",
                cache_hit=True,
                suggestions_count=len(cached_result.get("suggestions", [])),
                tokens_used=0,  # No tokens used for cache hits
                error=None,
                text_length=len(text),
                model=FAST_MODEL
            )

            return cached_result

        timings["preprocess_ms"] = int((time.time() - preprocess_start) * 1000)

        # 2. Fetch RAG exemplars + regulatory citations (lightweight, 2s timeout, graceful degradation)
        rag_start = time.time()
        rag_results = {'exemplars': [], 'regulatory': []}

        try:
            # Only fetch RAG if Pinecone/PubMedBERT are enabled (full features during trial)
            rag_enabled = os.getenv("ENABLE_PINECONE_INTEGRATION", "true").lower() == "true" and enable_rag

            if rag_enabled:
                logger.info(f"🔍 [{req_id}] Fetching RAG exemplars + regulatory citations...")
                rag_results = await get_fast_exemplars(trimmed_text, req_id)

                exemplar_count = len(rag_results.get('exemplars', []))
                regulatory_count = len(rag_results.get('regulatory', []))

                if exemplar_count > 0 or regulatory_count > 0:
                    logger.info(f"✅ [{req_id}] Retrieved {exemplar_count} exemplars + {regulatory_count} regulatory citations")
                else:
                    logger.info(f"ℹ️ [{req_id}] No RAG results (degraded mode)")
            else:
                logger.info(f"ℹ️ [{req_id}] RAG disabled in configuration")

        except Exception as e:
            logger.warning(f"⚠️ [{req_id}] RAG failed, continuing without: {type(e).__name__}: {e}")

        timings["rag_ms"] = int((time.time() - rag_start) * 1000)

        # 3. Build optimized prompt with RAG (exemplars + regulatory citations) (Step 4 + Step 8)
        # Pass section for section-aware prompts (Layer 2)
        # Pass document_context for document intelligence (Layer 5)
        prompt_data = build_fast_prompt(
            trimmed_text,
            ta,
            rag_results,
            section=section,
            document_context=document_context,
            timeline=timeline,  # Phase 4: Timeline-aware prompts
            use_templates=use_templates  # Week 5: A/B testing
        )

        # 3a. Enhance prompt for table data if detected (full features during trial)
        if is_table and enable_table_analysis:
            logger.info(f"📊 [{req_id}] Enhancing prompt for table analysis")
            table_instructions = """

IMPORTANT: The text you are analyzing is from a protocol TABLE (tab-separated columns).

Additional Table Analysis Tasks:
1. **Identify Table Type**: Determine if this is an objectives table, endpoints table, study schedule, adverse events table, or other protocol table type.
2. **Column-by-Column Analysis**: Validate each column for completeness and ICH-GCP compliance.
3. **Row-by-Row Analysis**: Check each row for missing data, vague language, or compliance issues.
4. **Structural Validation**:
   - Identify missing columns (e.g., objectives table missing "Statistical Method" column)
   - Check for empty cells that should contain data
   - Verify column headers align with ICH-GCP requirements for this table type
5. **Location-Specific Suggestions**: Format ALL suggestions with row/column references:
   - Example: "Row 2, Description column: [original text] → [improved text]"
   - Example: "Table structure: Missing 'Time Point' column (required per ICH E9)"

For each suggestion, specify:
- **location**: "Row X, Column Y" or "Table structure" or "Column headers"
- Your normal fields (text, suggestion, rationale, confidence, type, severity)

Table-Specific ICH-GCP Rules:
- **Objectives tables** must include: Objective Type, Description, Endpoint, Statistical Method
- **Endpoints tables** must include: Endpoint, Type (Primary/Secondary), Time Point, Analysis Method
- All table cells must have operational definitions (ICH E9 Section 2.2)
- Empty cells in data columns require justification or completion
"""
            # Append table instructions to user prompt
            prompt_data["user"] = prompt_data["user"] + table_instructions

            # Recount tokens after adding table instructions
            user_tokens_with_table = count_tokens_precise(prompt_data["user"], "gpt-4o-mini")
            total_tokens_with_table = prompt_data["tokens"]["system"] + user_tokens_with_table

            # Update token counts
            prompt_data["tokens"]["user"] = user_tokens_with_table
            prompt_data["tokens"]["total_input"] = total_tokens_with_table

            # Check if we exceeded budget after adding table instructions
            budget = prompt_data["tokens"]["budget"]
            if total_tokens_with_table > budget:
                logger.warning(
                    f"⚠️ [{req_id}] Table instructions pushed prompt over budget: "
                    f"{total_tokens_with_table} > {budget} tokens (excess: {total_tokens_with_table - budget})"
                )
                # Note: We allow exceeding budget for table analysis to preserve quality
                # Azure OpenAI will handle this gracefully as long as it's within model limits
            else:
                logger.info(
                    f"✅ [{req_id}] Table instructions added successfully. "
                    f"New token count: {total_tokens_with_table}/{budget}"
                )
        # Table analysis is always enabled during trial

        # Log token budget info
        token_info = prompt_data["tokens"]
        logger.info(
            f"📊 [{req_id}] Prompt tokens: {token_info['total_input']} "
            f"(budget: {token_info['budget']}, system: {token_info['system']}, user: {token_info['user']})"
        )

        # 4. Call Azure OpenAI with circuit breaker + retry + timeout
        azure_start = time.time()

        from resilience import get_circuit_breaker, retry_with_backoff, with_timeout

        circuit_breaker = get_circuit_breaker("azure_openai")

        try:
            # Wrap in circuit breaker → retry → timeout (Step 5)
            # Use optimized prompts from prompt_data (Step 4)
            suggestion_data, actual_tokens = await circuit_breaker.call_async(
                retry_with_backoff,
                with_timeout,
                _call_azure_fast,
                FAST_TIMEOUT_MS / 1000.0,
                prompt_data["system"],
                prompt_data["user"],
                req_id,
                max_retries=2  # Fast path: only 2 retries (not 3)
            )
        except asyncio.TimeoutError:
            logger.error(f"⏱️ Azure timeout after {FAST_TIMEOUT_MS}ms: {req_id}")
            raise Exception(f"Analysis timeout after {FAST_TIMEOUT_MS}ms")

        timings["azure_ms"] = int((time.time() - azure_start) * 1000)

        # Track token usage (Step 4)
        track_token_usage(
            "fast_path",
            actual_tokens.get("prompt_tokens", token_info["total_input"]),
            actual_tokens.get("completion_tokens", token_info["expected_output"])
        )

        # 5. Postprocess: Format response (handles new issues array format)
        postprocess_start = time.time()

        rule_suggestions = []
        ai_suggestions = []

        # 5a. Collect rule-based issues
        for rule_issue in rule_issues:
            rule_suggestions.append({
                "id": rule_issue.get("id"),
                "text": rule_issue.get("original_text"),
                "suggestion": rule_issue.get("improved_text"),
                "rationale": rule_issue.get("rationale"),
                "confidence": rule_issue.get("confidence"),
                "type": rule_issue.get("category"),
                "severity": rule_issue.get("severity"),
                "recommendation": rule_issue.get("recommendation"),
                "source": "rule_engine"
            })

        # 5a-1. Add amendment risk predictions (Layer 3: Risk Prediction)
        for risk in amendment_risks:
            rule_suggestions.append({
                "id": risk.get("id"),
                "text": risk.get("original_text"),
                "suggestion": risk.get("improved_text"),
                "rationale": risk.get("rationale"),
                "confidence": risk.get("confidence"),
                "type": risk.get("category"),
                "severity": risk.get("severity"),
                "recommendation": risk.get("recommendation"),
                "source": "amendment_risk",
                "amendment_risk": risk.get("amendment_risk")  # Include risk metadata
            })

        # 5b. Collect LLM-generated issues
        # New format: {"issues": [...]}
        logger.info(f"🔍 [{req_id}] Azure response keys: {list(suggestion_data.keys()) if suggestion_data else 'EMPTY'}")
        logger.info(f"🔍 [{req_id}] Has 'issues' key: {('issues' in suggestion_data) if suggestion_data else False}")

        if suggestion_data and "issues" in suggestion_data:
            issues = suggestion_data.get("issues", [])
            logger.info(f"✅ [{req_id}] Found {len(issues)} AI issues from Azure")
            for idx, issue in enumerate(issues[:10]):  # Limit to 10 issues max
                # Map new schema to frontend format
                ai_suggestions.append({
                    "id": issue.get("id", f"{req_id}_fast_{idx+1}"),
                    "text": issue.get("original_text", ""),
                    "suggestion": issue.get("improved_text", ""),
                    "rationale": issue.get("rationale", ""),
                    "confidence": issue.get("confidence", 0.8),
                    "type": issue.get("category", "clarity"),  # category -> type mapping
                    "severity": issue.get("severity", "minor"),
                    "recommendation": issue.get("recommendation", ""),
                    "source": "llm"
                })
        # Legacy format fallback: single issue object
        elif suggestion_data and suggestion_data.get("original_text"):
            ai_suggestions.append({
                "id": f"{req_id}_fast_1",
                "text": suggestion_data.get("original_text", ""),
                "suggestion": suggestion_data.get("improved_text", ""),
                "rationale": suggestion_data.get("rationale", ""),
                "confidence": suggestion_data.get("confidence", 0.8),
                "type": suggestion_data.get("type", "clarity"),
                "source": "llm"
            })

        # 5b-0. FIRST: Deduplicate within AI suggestions (same text, different severity/category)
        ai_suggestions = _deduplicate_ai_suggestions(ai_suggestions, req_id)

        # 5b-1. THEN: Deduplicate rule-based issues that overlap with AI suggestions
        suggestions = _deduplicate_suggestions(rule_suggestions, ai_suggestions, req_id)

        # Track deduplication stats
        dedup_stats = {
            "rule_based_total": len(rule_suggestions),
            "ai_total": len(ai_suggestions),
            "deduplicated_total": len(suggestions),
            "duplicates_removed": len(rule_suggestions) + len(ai_suggestions) - len(suggestions)
        }

        # 5b-2. TEXT MATCHING: Correct LLM paraphrased text against original selection
        # This ensures original_text contains verbatim document text for highlighting/replacing
        text_corrections = 0
        for suggestion in suggestions:
            if suggestion.get("source") == "llm" and suggestion.get("text"):
                corrected_text = _match_llm_text_to_original(
                    suggestion["text"],
                    trimmed_text  # original selected text from API payload
                )
                if corrected_text != suggestion["text"]:
                    logger.debug(
                        f"📝 [{req_id}] Corrected LLM text: "
                        f"'{suggestion['text'][:50]}...' -> '{corrected_text[:50]}...'"
                    )
                    suggestion["text"] = corrected_text
                    text_corrections += 1

        if text_corrections > 0:
            logger.info(f"📝 [{req_id}] Text matching: Corrected {text_corrections} LLM suggestions against original text")

        # 5b-2.5. PROBLEMATIC TEXT EXTRACTION: Ensure problematic_text is populated for word-level highlighting
        # Extracts from minimal_fix field when LLM doesn't provide it
        suggestions = _ensure_problematic_text(suggestions, trimmed_text)

        # 5b-2.75. POST-PROCESS VALIDATION: Filter suggestions that don't match selected text
        # FIX: Prevents LLM from generating suggestions based on document context instead of selection
        validated_suggestions = []
        discarded_count = 0
        for suggestion in suggestions:
            original_text = suggestion.get("text", "")
            # Only validate LLM suggestions (rule-based are guaranteed to match)
            if suggestion.get("source") == "llm" and original_text:
                if original_text in trimmed_text:
                    validated_suggestions.append(suggestion)
                else:
                    discarded_count += 1
                    logger.warning(
                        f"⚠️ [{req_id}] Discarding suggestion - original_text not in selection: "
                        f"'{original_text[:100]}...'"
                    )
            else:
                # Keep rule-based suggestions and LLM suggestions without text
                validated_suggestions.append(suggestion)

        if discarded_count > 0:
            logger.info(
                f"🔍 [{req_id}] Post-validation: Discarded {discarded_count} suggestions "
                f"that referenced text outside selection (likely from document context)"
            )

        suggestions = validated_suggestions

        # 5b-3. DISABLED: Grouping removed per user request - show individual cards like Grammarly
        # suggestions, grouping_stats = _group_suggestions_by_text(suggestions, req_id)
        grouping_stats = {
            "groups_created": 0,
            "suggestions_grouped": 0,
            "total_before_grouping": len(suggestions),
            "total_after_grouping": len(suggestions)
        }

        # 5c. Validate suggestions (Phase 2A: Backend validator)
        validation_start = time.time()
        validation_result = validate_suggestions_batch(suggestions)

        # Use only accepted suggestions
        validated_suggestions = validation_result["accepted"]
        rejected_suggestions = validation_result["rejected"]

        logger.info(
            f"📊 [{req_id}] Validation: {validation_result['stats']['accepted']}/{validation_result['stats']['total']} accepted, "
            f"{validation_result['stats']['rejected']} rejected"
        )

        if rejected_suggestions:
            logger.warning(
                f"⚠️ [{req_id}] Rejected suggestions: "
                f"{[s.get('_rejection_reason') for s in rejected_suggestions[:3]]}"
            )

        timings["validation_ms"] = int((time.time() - validation_start) * 1000)

        # 5c-2. Score suggestion specificity (Week 3: Contextual Intelligence)
        scoring_start = time.time()
        entities = prompt_data.get("entities")  # Entities extracted in build_fast_prompt()
        enhancement_stats = None  # Week 7: Track enhancement results

        if entities:
            try:
                from suggestion_specificity_scorer import (
                    score_suggestion_specificity,
                    classify_specificity,
                    detect_generic_phrases
                )

                # Score each validated suggestion
                for suggestion in validated_suggestions:
                    score = score_suggestion_specificity(suggestion, entities)
                    suggestion["specificity_score"] = score
                    suggestion["specificity_level"] = classify_specificity(score)
                    suggestion["generic_phrases"] = detect_generic_phrases(
                        suggestion.get("improved_text", "")
                    )

                logger.info(f"✨ [{req_id}] Scored {len(validated_suggestions)} suggestions for specificity")

                # Week 7 Phase 1: Enhance generic suggestions with protocol entities
                # DISABLED 2026-01-11: Testing showed 0% enhancement rate on real protocols
                # Patterns don't match actual LLM output. Keeping code for potential future use.
                # See: /tmp/test_5_protocols.py results
                #
                # try:
                #     from suggestion_enhancer import enhance_suggestions_batch, get_enhancement_summary
                #
                #     # Enhance suggestions below specificity threshold
                #     enhancement_result = enhance_suggestions_batch(
                #         validated_suggestions,
                #         entities,
                #         threshold=0.4  # Only enhance generic/partially specific suggestions
                #     )
                #
                #     # Replace with enhanced suggestions
                #     validated_suggestions = enhancement_result["suggestions"]
                #     enhancement_stats = enhancement_result["stats"]
                #
                #     # Log enhancement results
                #     if enhancement_stats["enhanced_count"] > 0:
                #         logger.info(
                #             f"🔧 [{req_id}] Enhanced {enhancement_stats['enhanced_count']} "
                #             f"suggestions (avg improvement: +{enhancement_stats['avg_improvement']:.3f})"
                #         )
                #     else:
                #         logger.info(f"🔧 [{req_id}] No suggestions enhanced (all specific or no matching patterns)")
                #
                # except ImportError:
                #     logger.warning("suggestion_enhancer module not available, skipping enhancement")
                # except Exception as e:
                #     logger.error(f"Error enhancing suggestions: {e}")

            except ImportError:
                logger.warning("suggestion_specificity_scorer module not available, skipping specificity scoring")
            except Exception as e:
                logger.error(f"Error scoring suggestion specificity: {e}")
        else:
            # No entities extracted - mark all as generic (score 0.0)
            for suggestion in validated_suggestions:
                suggestion["specificity_score"] = 0.0
                suggestion["specificity_level"] = "generic"
                suggestion["generic_phrases"] = []

        timings["scoring_ms"] = int((time.time() - scoring_start) * 1000)

        # 5d. Add cross-section conflicts (Document Intelligence)
        # These are already validated by the cross_section_engine, so add them directly
        if cross_section_conflicts:
            logger.info(f"🔀 [{req_id}] Adding {len(cross_section_conflicts)} cross-section conflicts to suggestions")
            # Prepend cross-section conflicts so they appear first (most important)
            validated_suggestions = cross_section_conflicts + validated_suggestions

        timings["postprocess_ms"] = int((time.time() - postprocess_start) * 1000)
        timings["total_ms"] = int((time.time() - start_time) * 1000)

        # Calculate specificity metrics for metadata
        specificity_metrics = {}
        if validated_suggestions:
            total_suggestions = len(validated_suggestions)
            scores = [s.get("specificity_score", 0.0) for s in validated_suggestions]
            avg_score = sum(scores) / total_suggestions if total_suggestions > 0 else 0.0

            specificity_metrics = {
                "avg_score": round(avg_score, 3),
                "highly_specific_count": sum(
                    1 for s in validated_suggestions
                    if s.get("specificity_level") == "highly_specific"
                ),
                "partially_specific_count": sum(
                    1 for s in validated_suggestions
                    if s.get("specificity_level") == "partially_specific"
                ),
                "generic_count": sum(
                    1 for s in validated_suggestions
                    if s.get("specificity_level") == "generic"
                ),
                "entities_extracted": sum(len(v) for v in entities.values()) if entities else 0
            }

        # Build result
        result = {
            "status": "fast",
            "request_id": req_id,
            "suggestions": validated_suggestions,  # Phase 2A: Use validated suggestions only
            "metadata": {
                **timings,
                "model": FAST_MODEL,
                "cache_hit": False,
                "text_length": len(text),
                "trimmed": len(text) > SELECTION_CHUNK_THRESHOLD,
                "timestamp": datetime.utcnow().isoformat(),
                # Step 9: Rule engine info
                "rule_issues_count": len(rule_issues),
                "llm_issues_count": len(suggestions) - len(rule_issues),
                # Phase 2B: Deduplication stats
                "deduplication": dedup_stats,
                # Phase 2B: Grouping stats
                "grouping": grouping_stats,
                # Phase 2A: Validation stats
                "validation": validation_result["stats"],
                "validation_warnings": validation_result["warnings"],
                # Step 8: RAG info
                "rag_exemplars": len(rag_results.get('exemplars', [])),
                "rag_enabled": len(rag_results.get('exemplars', [])) > 0,
                # Document Intelligence info
                "document_context_enabled": document_context is not None,
                "cross_section_conflicts_count": len(cross_section_conflicts),
                # Week 3: Specificity metrics
                "specificity": specificity_metrics if specificity_metrics else None,
                "enhancement": enhancement_stats if enhancement_stats else None,  # Week 7: Enhancement stats
                # Step 4: Token usage tracking
                "tokens": {
                    "prompt": actual_tokens.get("prompt_tokens", token_info["total_input"]),
                    "completion": actual_tokens.get("completion_tokens", token_info["expected_output"]),
                    "total": actual_tokens.get("total_tokens", 0),
                    "budget": token_info["budget"]
                }
            }
        }

        # Cache successful result (Step 6: Enhanced cache manager)
        # Week 5: Add variant to cache key for A/B testing
        set_cached(
            text=trimmed_text,
            model=FAST_MODEL,
            result=result,
            ta=ta,
            phase=phase,
            analysis_type="fast",
            variant=cache_variant
        )

        # Emit performance warning if slow
        if timings["total_ms"] > 12000:
            logger.warning(f"⚠️ Slow fast analysis: {timings['total_ms']}ms (target: <15000ms)")

        # Log specificity metrics
        specificity_log = ""
        if specificity_metrics:
            specificity_log = (
                f", specificity: avg={specificity_metrics['avg_score']:.3f} "
                f"(highly_specific={specificity_metrics['highly_specific_count']}, "
                f"generic={specificity_metrics['generic_count']})"
            )

        logger.info(
            f"✅ Fast analysis complete: {req_id} ({timings['total_ms']}ms, "
            f"{len(validated_suggestions)}/{len(suggestions)} validated, "
            f"{dedup_stats['duplicates_removed']} duplicates removed{specificity_log})"
        )

        # Step 7: Record metrics
        record_request(
            request_id=req_id,
            endpoint="/api/analyze",
            duration_ms=timings["total_ms"],
            status_code=200,
            path_type="fast",
            cache_hit=False,
            suggestions_count=len(suggestions),
            tokens_used=actual_tokens.get("total_tokens", 0),
            error=None,
            text_length=len(text),
            model=FAST_MODEL
        )

        return result

    except Exception as e:
        total_ms = int((time.time() - start_time) * 1000)
        logger.error(f"❌ Fast analysis failed: {req_id} ({total_ms}ms) - {type(e).__name__}: {e}")

        # Step 7: Record error metrics
        record_request(
            request_id=req_id,
            endpoint="/api/analyze",
            duration_ms=total_ms,
            status_code=500,
            path_type="fast",
            cache_hit=False,
            suggestions_count=0,
            tokens_used=0,
            error=f"{type(e).__name__}: {str(e)}",
            text_length=len(text),
            model=FAST_MODEL
        )

        # Return error response
        return {
            "status": "error",
            "request_id": req_id,
            "suggestions": [],
            "metadata": {
                **timings,
                "total_ms": total_ms,
                "error": str(e),
                "model": FAST_MODEL
            }
        }


async def _call_azure_fast(system_prompt: str, user_prompt: str, request_id: str) -> Tuple[Dict[str, Any], Dict[str, int]]:
    """
    Call Azure OpenAI with fast model and optimized prompts (Step 4)

    Args:
        system_prompt: System message (optimized)
        user_prompt: User message (optimized)
        request_id: Request tracking ID

    Returns:
        Tuple of (parsed JSON response, token usage dict)
    """
    import json
    from openai import AsyncAzureOpenAI

    # Get Azure credentials (support both naming conventions)
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    azure_key = os.getenv("AZURE_OPENAI_API_KEY") or os.getenv("AZURE_OPENAI_KEY")

    if not azure_endpoint or not azure_key:
        raise ValueError("Azure OpenAI credentials not configured")

    client = AsyncAzureOpenAI(
        api_key=azure_key,
        api_version="2024-08-01-preview",
        azure_endpoint=azure_endpoint
    )

    try:
        response = await client.chat.completions.create(
            model=FAST_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": user_prompt
                }
            ],
            max_tokens=FAST_MAX_TOKENS,
            temperature=FAST_TEMPERATURE,
            response_format={"type": "json_object"}
        )

        content = response.choices[0].message.content

        # Extract token usage (Step 4)
        token_usage = {
            "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
            "completion_tokens": response.usage.completion_tokens if response.usage else 0,
            "total_tokens": response.usage.total_tokens if response.usage else 0
        }

        # Parse JSON response
        try:
            result = json.loads(content)
            return result, token_usage
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON parse error: {e}\nContent: {content}")
            return {}, token_usage

    except Exception as e:
        logger.error(f"❌ Azure call failed: {request_id} - {type(e).__name__}: {e}")
        logger.error(f"❌ Full error details: {repr(e)}")
        import traceback
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        raise


# Export main function
__all__ = ["analyze_fast", "SELECTION_CHUNK_THRESHOLD"]
