#!/usr/bin/env python3
"""
Metrics Collector for Step 7: Telemetry & Profiling

Provides comprehensive observability through:
- Performance metrics (latency, throughput, percentiles)
- Request tracing with correlation IDs
- Error tracking and categorization  
- Business metrics (suggestions, cache hits, tokens)
- Prometheus-compatible metrics export
- Performance profiling and bottleneck detection

Enables data-driven optimization decisions
"""

import os
import time
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from collections import defaultdict
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

# Configuration
ENABLE_METRICS = os.getenv("ENABLE_METRICS", "true").lower() == "true"
MAX_TRACES = int(os.getenv("MAX_TRACES", "1000"))

# Global metrics storage
_metrics = {
    "requests": {"total": 0, "fast_path": 0, "deep_path": 0, "errors": 0},
    "latency": {"fast_path": [], "deep_path": [], "cache_lookup": [], "azure_call": []},
    "suggestions": {"total_generated": 0, "avg_per_request": 0.0},
    "cache": {"hits": 0, "misses": 0, "hit_rate": 0.0},
    "tokens": {"total_input": 0, "total_output": 0, "total_cost_usd": 0.0},
    "errors": {"by_type": defaultdict(int), "by_endpoint": defaultdict(int), "recent": []}
}

# Request traces
_traces: List[Dict[str, Any]] = []


@dataclass
class RequestTrace:
    request_id: str
    endpoint: str
    method: str
    timestamp: datetime
    duration_ms: int
    status_code: int
    path_type: str
    cache_hit: bool
    suggestions_count: int
    tokens_used: int
    error: Optional[str]
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result['timestamp'] = self.timestamp.isoformat()
        return result


def record_request(
    request_id: str,
    endpoint: str,
    duration_ms: int = 0,
    status_code: int = 200,
    path_type: str = "fast",
    cache_hit: bool = False,
    suggestions_count: int = 0,
    tokens_used: int = 0,
    error: Optional[str] = None,
    **metadata
):
    if not ENABLE_METRICS:
        return

    trace = RequestTrace(
        request_id=request_id,
        endpoint=endpoint,
        method="POST",
        timestamp=datetime.utcnow(),
        duration_ms=duration_ms,
        status_code=status_code,
        path_type=path_type,
        cache_hit=cache_hit,
        suggestions_count=suggestions_count,
        tokens_used=tokens_used,
        error=error,
        metadata=metadata
    )

    _traces.append(trace.to_dict())
    if len(_traces) > MAX_TRACES:
        _traces.pop(0)

    _metrics["requests"]["total"] += 1
    if path_type == "fast":
        _metrics["requests"]["fast_path"] += 1
        _metrics["latency"]["fast_path"].append(duration_ms)
    else:
        _metrics["requests"]["deep_path"] += 1
        _metrics["latency"]["deep_path"].append(duration_ms)

    if error:
        _metrics["requests"]["errors"] += 1

    if cache_hit:
        _metrics["cache"]["hits"] += 1
    else:
        _metrics["cache"]["misses"] += 1

    _metrics["suggestions"]["total_generated"] += suggestions_count
    _metrics["tokens"]["total_input"] += tokens_used

    # Update derived metrics
    total_cache = _metrics["cache"]["hits"] + _metrics["cache"]["misses"]
    if total_cache > 0:
        _metrics["cache"]["hit_rate"] = (_metrics["cache"]["hits"] / total_cache) * 100

    if _metrics["requests"]["total"] > 0:
        _metrics["suggestions"]["avg_per_request"] = (
            _metrics["suggestions"]["total_generated"] / _metrics["requests"]["total"]
        )


def calculate_percentiles(values: List[float], percentiles: List[int] = [50, 90, 95, 99]) -> Dict[str, float]:
    if not values:
        return {f"p{p}": 0.0 for p in percentiles}

    sorted_values = sorted(values)
    result = {}

    for p in percentiles:
        index = int(len(sorted_values) * (p / 100))
        if index >= len(sorted_values):
            index = len(sorted_values) - 1
        result[f"p{p}"] = round(sorted_values[index], 2)

    return result


def get_performance_metrics() -> Dict[str, Any]:
    metrics = {"latency_percentiles": {}, "throughput": {}, "performance_targets": {}}

    for operation, values in _metrics["latency"].items():
        if values:
            metrics["latency_percentiles"][operation] = calculate_percentiles(values)
        else:
            metrics["latency_percentiles"][operation] = {"p50": 0, "p90": 0, "p95": 0, "p99": 0}

    total = _metrics["requests"]["total"]
    if total > 0:
        metrics["throughput"]["fast_path_pct"] = round((_metrics["requests"]["fast_path"] / total) * 100, 2)
        metrics["throughput"]["deep_path_pct"] = round((_metrics["requests"]["deep_path"] / total) * 100, 2)

    fast_p = metrics["latency_percentiles"].get("fast_path", {})
    metrics["performance_targets"]["fast_path_p95_ms"] = fast_p.get("p95", 0)
    metrics["performance_targets"]["meets_target_10s"] = fast_p.get("p95", float('inf')) <= 10000

    return metrics


def get_all_metrics() -> Dict[str, Any]:
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "requests": _metrics["requests"].copy(),
        "performance": get_performance_metrics(),
        "cache": _metrics["cache"].copy(),
        "suggestions": _metrics["suggestions"].copy(),
        "tokens": _metrics["tokens"].copy(),
        "errors": {
            "total": _metrics["requests"]["errors"],
            "error_rate_pct": round(
                (_metrics["requests"]["errors"] / max(1, _metrics["requests"]["total"])) * 100, 2
            )
        }
    }


def export_prometheus() -> str:
    lines = []
    lines.append(f'ilana_requests_total{{path="fast"}} {_metrics["requests"]["fast_path"]}')
    lines.append(f'ilana_requests_total{{path="deep"}} {_metrics["requests"]["deep_path"]}')
    lines.append(f'ilana_cache_hit_rate {_metrics["cache"]["hit_rate"]}')
    lines.append(f'ilana_tokens_total{{type="input"}} {_metrics["tokens"]["total_input"]}')

    perf = get_performance_metrics()
    for op, percentiles in perf["latency_percentiles"].items():
        for p_name, p_val in percentiles.items():
            lines.append(f'ilana_latency_{op}_{p_name} {p_val}')

    return "\n".join(lines)


logger.info("📊 Metrics collector loaded (Step 7)")


__all__ = ["record_request", "get_all_metrics", "get_performance_metrics", "export_prometheus"]
