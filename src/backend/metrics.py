"""
Black Vault — Performance metrics.
Tracks ingest and analysis times, error counts, and document volumes.
"""
import logging
import time
import functools
from typing import Callable

_logger = logging.getLogger(__name__)

# Contadores en memoria (se resetean al reiniciar el proceso)
_metrics: dict = {
    "docs_ingested": 0,
    "docs_analyzed": 0,
    "errors": 0,
    "total_ingest_time_ms": 0.0,
    "total_analysis_time_ms": 0.0,
}

# Stages válidos — amplía esta lista si añades más etapas
_VALID_STAGES = {"ingest", "analysis"}


def track_performance(stage: str) -> Callable:
    """
    Decorator that measures execution time and updates global metrics.

    Args:
        stage: One of 'ingest' or 'analysis'.

    Usage:
        @track_performance("ingest")
        def ingest_document(path: str) -> dict: ...

        @track_performance("analysis")
        def analyze_document(doc: dict) -> str: ...
    """
    if stage not in _VALID_STAGES:
        raise ValueError(f"Invalid stage '{stage}'. Must be one of: {_VALID_STAGES}")

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                elapsed_ms = (time.perf_counter() - start) * 1000

                if stage == "ingest":
                    _metrics["docs_ingested"] += 1
                    _metrics["total_ingest_time_ms"] += elapsed_ms
                elif stage == "analysis":
                    _metrics["docs_analyzed"] += 1
                    _metrics["total_analysis_time_ms"] += elapsed_ms

                _logger.debug("[METRIC] %s completed in %.2f ms", stage, elapsed_ms)
                return result

            except Exception as e:
                elapsed_ms = (time.perf_counter() - start) * 1000
                _metrics["errors"] += 1
                _logger.error(
                    "[METRIC] %s failed after %.2f ms: %s", stage, elapsed_ms, e
                )
                raise

        return wrapper
    return decorator


def get_metrics() -> dict:
    """
    Returns a snapshot of current performance metrics with derived averages.

    Example output:
        {
            'docs_ingested': 42,
            'docs_analyzed': 40,
            'errors': 2,
            'total_ingest_time_ms': 5649.3,
            'total_analysis_time_ms': 12300.1,
            'avg_ingest_time_ms': 134.5,
            'avg_analysis_time_ms': 307.5
        }
    """
    m = dict(_metrics)
    if m["docs_ingested"] > 0:
        m["avg_ingest_time_ms"] = round(m["total_ingest_time_ms"] / m["docs_ingested"], 2)
    if m["docs_analyzed"] > 0:
        m["avg_analysis_time_ms"] = round(m["total_analysis_time_ms"] / m["docs_analyzed"], 2)
    return m


def reset_metrics() -> None:
    """Resets all performance counters. Useful for testing or periodic reporting."""
    global _metrics
    _metrics = {k: (0 if isinstance(v, int) else 0.0) for k, v in _metrics.items()}
    _logger.info("[METRIC] Metrics reset.")