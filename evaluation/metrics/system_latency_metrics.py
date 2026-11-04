"""
System Infrastructure, Latency, and Throughput Metrics.

Measures:
- Latency Percentiles (p50, p90, p95, p99, mean, std)
- Throughput (tokens/sec, chunks/sec)
- Asynchronous Celery Task Reliability & Execution Success Rate
"""

from typing import Any, Dict, List
import math


def compute_latency_percentiles(latencies_ms: List[float]) -> Dict[str, float]:
    """
    Compute statistical distribution of execution latencies in milliseconds.
    """
    if not latencies_ms:
        return {"p50": 0.0, "p90": 0.0, "p95": 0.0, "p99": 0.0, "mean": 0.0, "std": 0.0}

    sorted_lat = sorted(latencies_ms)
    n = len(sorted_lat)

    def percentile(p: float) -> float:
        idx = int(math.ceil(p * n)) - 1
        return sorted_lat[max(0, min(idx, n - 1))]

    mean_val = sum(sorted_lat) / n
    variance = sum((x - mean_val) ** 2 for x in sorted_lat) / n
    std_val = math.sqrt(variance)

    return {
        "count": n,
        "mean_ms": round(mean_val, 2),
        "std_ms": round(std_val, 2),
        "p50_ms": round(percentile(0.50), 2),
        "p90_ms": round(percentile(0.90), 2),
        "p95_ms": round(percentile(0.95), 2),
        "p99_ms": round(percentile(0.99), 2),
        "min_ms": round(sorted_lat[0], 2),
        "max_ms": round(sorted_lat[-1], 2),
    }


def compute_throughput(total_tokens_or_words: int, total_duration_sec: float) -> float:
    """Compute tokens or words processed per second."""
    if total_duration_sec <= 0:
        return 0.0
    return round(total_tokens_or_words / total_duration_sec, 2)

