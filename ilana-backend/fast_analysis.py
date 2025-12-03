#!/usr/bin/env python3
"""
Fast Analysis Module - Optimized for Sub-15s Response Times

Provides lightweight protocol analysis for interactive selections using:
- Up to 10000 chars (full protocol sections)
- Fast Azure model (gpt-4o-mini by default)
- Lightweight RAG: Pinecone + PubMedBERT (top 3 exemplars, 2s timeout)
- Domain-expert ICH-GCP prompts with regulatory guidance
- Aggressive timeouts and caching

For deep analysis with full RAG stack + citations, use background job queue.
"""

import os
import time
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import asyncio

# Step 4: Import prompt optimization utilities
from prompt_optimizer import build_fast_prompt, track_token_usage

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
SELECTION_CHUNK_THRESHOLD = int(os.getenv("SELECTION_CHUNK_THRESHOLD", "10000"))  # 10000 chars = full protocol sections


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


async def analyze_fast(
    text: str,
    ta: Optional[str] = None,
    phase: Optional[str] = None,
    request_id: Optional[str] = None,
    is_table: bool = False  # New parameter for table detection
) -> Dict[str, Any]:
    """
    Fast synchronous analysis for protocol sections

    Target: < 15 seconds total (typically 3-8s for uncached)

    Args:
        text: Selected protocol text (up to 10000 chars = full sections)
        ta: Optional therapeutic area
        phase: Optional study phase
        request_id: Request tracking ID

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

    logger.info(f"⚡ Fast analysis start: {req_id} (text_len={len(text)})")

    # Timing breakdown
    timings = {
        "preprocess_ms": 0,
        "rule_engine_ms": 0,
        "rag_ms": 0,
        "azure_ms": 0,
        "validation_ms": 0,  # Phase 2A
        "postprocess_ms": 0,
        "total_ms": 0
    }

    try:
        # 1. Preprocess: Trim text if needed
        preprocess_start = time.time()

        if len(text) > SELECTION_CHUNK_THRESHOLD:
            logger.warning(f"⚠️ Text exceeds fast threshold ({len(text)} > {SELECTION_CHUNK_THRESHOLD})")
            # Take first SELECTION_CHUNK_THRESHOLD chars
            trimmed_text = text[:SELECTION_CHUNK_THRESHOLD]
        else:
            trimmed_text = text

        # 1a. Run rule-based compliance checks (< 1ms, deterministic)
        rule_engine_start = time.time()
        rule_issues = []

        try:
            rule_issues = run_compliance_checks(trimmed_text)
            if rule_issues:
                logger.info(f"🔍 [{req_id}] Rule engine found {len(rule_issues)} issues")
        except Exception as e:
            logger.warning(f"⚠️ [{req_id}] Rule engine failed: {e}")

        timings["rule_engine_ms"] = int((time.time() - rule_engine_start) * 1000)

        # Check cache (Step 6: Enhanced cache manager)
        cached_result = get_cached(
            text=trimmed_text,
            model=FAST_MODEL,
            ta=ta,
            phase=phase,
            analysis_type="fast"
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
            # Only fetch RAG if Pinecone/PubMedBERT are enabled
            enable_rag = os.getenv("ENABLE_PINECONE_INTEGRATION", "true").lower() == "true"

            if enable_rag:
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
        prompt_data = build_fast_prompt(trimmed_text, ta, rag_results)

        # 3a. Enhance prompt for table data if detected
        if is_table:
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

        # 5b-1. Deduplicate: Remove rule-based issues that overlap with AI suggestions
        suggestions = _deduplicate_suggestions(rule_suggestions, ai_suggestions, req_id)

        # Track deduplication stats
        dedup_stats = {
            "rule_based_total": len(rule_suggestions),
            "ai_total": len(ai_suggestions),
            "deduplicated_total": len(suggestions),
            "duplicates_removed": len(rule_suggestions) + len(ai_suggestions) - len(suggestions)
        }

        # 5b-2. DISABLED: Grouping removed per user request - show individual cards like Grammarly
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
        timings["postprocess_ms"] = int((time.time() - postprocess_start) * 1000)
        timings["total_ms"] = int((time.time() - start_time) * 1000)

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
        set_cached(
            text=trimmed_text,
            model=FAST_MODEL,
            result=result,
            ta=ta,
            phase=phase,
            analysis_type="fast"
        )

        # Emit performance warning if slow
        if timings["total_ms"] > 12000:
            logger.warning(f"⚠️ Slow fast analysis: {timings['total_ms']}ms (target: <15000ms)")

        logger.info(
            f"✅ Fast analysis complete: {req_id} ({timings['total_ms']}ms, "
            f"{len(validated_suggestions)}/{len(suggestions)} validated, "
            f"{dedup_stats['duplicates_removed']} duplicates removed)"
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
