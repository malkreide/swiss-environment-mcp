"""
OpenTelemetry-Tracing für swiss-environment-mcp (Audit OBS-006).

Tracing ist **opt-in**: Es wird nur aktiviert, wenn ein OTLP-Endpoint via
`OTEL_EXPORTER_OTLP_ENDPOINT` gesetzt ist UND das optionale `otel`-Extra
installiert ist (`pip install '.[otel]'`). Andernfalls sind `configure_tracing`
und der `trace_tool`-Decorator wirkungslos (kein Overhead, keine harte Dependency).

Pro Tool-Call wird ein Span `mcp.tool.<name>` mit den Attributen `mcp.tool.name`
und `mcp.tool.result.is_error` erzeugt. Backend-HTTP-Calls (httpx) werden via
Auto-Instrumentation zu Child-Spans. Es werden **keine** sensitiven Daten
(Argumente, Inhalte, Tokens) in Span-Attribute geschrieben.
"""

import functools
import os
import uuid
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

import structlog

from .logging_setup import get_logger

_TRACING_ON = False
_F = TypeVar("_F", bound=Callable[..., Awaitable[Any]])

_obs_logger = get_logger(component="tools")


def configure_tracing() -> None:
    """Initialisiert TracerProvider + OTLP-Exporter + httpx-Instrumentierung.

    No-op, wenn kein OTLP-Endpoint gesetzt ist oder das otel-Extra fehlt.
    """
    global _TRACING_ON
    if not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        return  # otel-Extra nicht installiert -> stiller No-op

    resource = Resource.create(
        {
            "service.name": os.environ.get("OTEL_SERVICE_NAME", "swiss-environment-mcp"),
            "deployment.environment": os.environ.get("OTEL_ENVIRONMENT", "production"),
        }
    )
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)
    HTTPXClientInstrumentor().instrument()
    _TRACING_ON = True


def _looks_like_error(result: Any) -> bool:
    return isinstance(result, str) and result.lstrip().startswith(("Fehler", "⚠️"))


async def _run_traced(fn: _F, args: Any, kwargs: Any) -> Any:
    """Führt den Handler aus — mit OTel-Span, falls Tracing aktiv ist."""
    if not _TRACING_ON:
        return await fn(*args, **kwargs)
    from opentelemetry import trace

    tracer = trace.get_tracer("swiss-environment-mcp")
    with tracer.start_as_current_span(f"mcp.tool.{fn.__name__}") as span:
        span.set_attribute("mcp.tool.name", fn.__name__)
        result = await fn(*args, **kwargs)
        span.set_attribute("mcp.tool.result.is_error", _looks_like_error(result))
        return result


def trace_tool(fn: _F) -> _F:
    """Decorator: Observability-Hülle um einen Tool-Handler (Audit OBS-003/OBS-006).

    Immer aktiv (unabhängig vom OTel-Endpoint):
      - bindet eine Correlation-ID (`request_id`) + `tool` in den Log-Kontext,
        sodass alle Logs eines Tool-Calls — auch die Warnung aus
        `_handle_tool_error` — korrelierbar sind;
      - loggt `tool_invoked` (info), `tool_succeeded` (info, mit `is_error`) bzw.
        `tool_failed` (error, mit Exception-Info).
    Zusätzlich, nur bei gesetztem OTLP-Endpoint: ein `mcp.tool.<name>`-Span.
    """

    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        request_id = uuid.uuid4().hex[:12]
        with structlog.contextvars.bound_contextvars(request_id=request_id, tool=fn.__name__):
            _obs_logger.info("tool_invoked", tool=fn.__name__)
            try:
                result = await _run_traced(fn, args, kwargs)
            except Exception:
                # tool_failed → error-Stufe; Detail (Typ/Text) strukturiert, kein
                # Leak ans LLM (die Fehlermaskierung passiert in _handle_tool_error
                # bzw. beim ToolError-Raise). exc_info für den Server-Log/SIEM.
                _obs_logger.error("tool_failed", tool=fn.__name__, exc_info=True)
                raise
            _obs_logger.info("tool_succeeded", tool=fn.__name__, is_error=_looks_like_error(result))
            return result

    return wrapper  # type: ignore[return-value]
