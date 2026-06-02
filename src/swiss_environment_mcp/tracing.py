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
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

_TRACING_ON = False
_F = TypeVar("_F", bound=Callable[..., Awaitable[Any]])


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


def trace_tool(fn: _F) -> _F:
    """Decorator: umhüllt einen Tool-Handler mit einem OTel-Span (Audit OBS-006).

    Wirkungslos, solange Tracing nicht aktiv ist (configure_tracing no-op).
    """

    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        if not _TRACING_ON:
            return await fn(*args, **kwargs)
        from opentelemetry import trace

        tracer = trace.get_tracer("swiss-environment-mcp")
        with tracer.start_as_current_span(f"mcp.tool.{fn.__name__}") as span:
            span.set_attribute("mcp.tool.name", fn.__name__)
            result = await fn(*args, **kwargs)
            span.set_attribute("mcp.tool.result.is_error", _looks_like_error(result))
            return result

    return wrapper  # type: ignore[return-value]
