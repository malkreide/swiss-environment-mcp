"""
Strukturiertes Logging für swiss-environment-mcp (Audit OBS-003 / OBS-004).

Wichtig: Logs gehen **ausschliesslich nach stderr**. Bei stdio-Transport ist
stdout für das JSON-RPC-Protokoll reserviert — jede Ausgabe nach stdout würde
den Protokoll-Stream korrumpieren (Audit OBS-004, kritisch).

JSON-Renderer + ISO-Timestamp + Log-Level → maschinenlesbar für SIEM/Log-Aggregation.
"""

import logging
import sys

import structlog

_configured = False


def configure_logging(level: int = logging.INFO) -> None:
    """Konfiguriert structlog idempotent (mehrfacher Aufruf ist sicher)."""
    global _configured
    if _configured:
        return
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        # stderr — niemals stdout (OBS-004)
        logger_factory=structlog.WriteLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )
    _configured = True


def get_logger(**initial_values: object) -> structlog.stdlib.BoundLogger:
    """Liefert einen gebundenen Logger mit optionalem Initial-Kontext."""
    return structlog.get_logger(**initial_values)
