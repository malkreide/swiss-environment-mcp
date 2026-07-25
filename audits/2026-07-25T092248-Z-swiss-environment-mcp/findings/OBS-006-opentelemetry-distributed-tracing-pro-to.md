## Finding: OBS-006 — OpenTelemetry Distributed Tracing pro Tool-Call

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `OBS-006` (Check-Status: partial) |
| **PDF-Reference** | Anhang B10 |
| **Audit-Datum** | 2026-07-25 |
| **Auditor** | Claude (mcp-audit-Skill, Run 2026-07-25T092248-Z) |

### Observed Behavior

Die Tracing-Implementierung selbst ist vollständig und sauber (Decorator auf allen 18 Tools, Auto-Instrumentation, PII-freie Spans, Env-basierte Konfiguration), aber sie ist im tatsächlichen Deployment nicht aktivierbar: das Docker-Image enthält das otel-Extra nicht und kein Manifest setzt den OTLP-Endpoint. Code-ready, deployment-inaktiv → partial.

Lücken im Detail:
- OTel-SDK ist nicht installiert im ausgelieferten Artefakt: Dockerfile:24 installiert das Wheel ohne [otel]-Extra — im Container bleibt configure_tracing selbst mit gesetztem OTLP-Endpoint ein stiller No-op (ImportError-Pfad tracing.py:39-40).
- Kein OTEL_EXPORTER_OTLP_ENDPOINT/OTEL_SERVICE_NAME in den Deployment-Manifesten (render.yaml, docker-compose.yml, Dockerfile) — Tracing ist im Cloud-Deployment faktisch inaktiv.
- Span-Attribut mcp.user.id fehlt (mangels Auth existiert keine User-Identity — nachvollziehbar, aber Kriterium formal unerfüllt).

### Expected Behavior

Siehe Pass Criteria in `checks/OBS-006.md` (OpenTelemetry Distributed Tracing pro Tool-Call).

### Evidence

- src/swiss_environment_mcp/tracing.py:24-52 — configure_tracing: TracerProvider mit Resource (service.name via OTEL_SERVICE_NAME, deployment.environment via OTEL_ENVIRONMENT), BatchSpanProcessor + OTLP-HTTP-Exporter, Aktivierung nur bei gesetztem OTEL_EXPORTER_OTLP_ENDPOINT (Env-konfigurierbar, nichts hardcoded)
- src/swiss_environment_mcp/tracing.py:51 — HTTPXClientInstrumentor().instrument(): Backend-API-Calls (httpx) werden automatisch zu Child-Spans
- src/swiss_environment_mcp/tracing.py:59-78 — trace_tool-Decorator: Span 'mcp.tool.<name>' mit Attributen mcp.tool.name und mcp.tool.result.is_error; keine Args/Inhalte/Tokens in Span-Attributen (Docstring tracing.py:9-12, grep set_attribute → nur name/is_error)
- src/swiss_environment_mcp/server.py — @trace_tool auf allen 18 Tools (grep-Count 18/18, inkl. neuem env_bathing_water server.py:1481), aktiviert via configure_tracing() in server.py:76
- pyproject.toml:39-43 — otel-Extra (opentelemetry-sdk, otlp-proto-http-Exporter, instrumentation-httpx) als optionale Dependency

### Risk Description

Severity medium gemäss Katalog; Profil-Kontext: read-only Public-Open-Data-Server ohne Auth, Single-Instance-Cloud-Deployment. Offen — Behebung gemäss Remediation.

### Remediation

Dockerfile auf 'pip install .[otel]' umstellen (oder otel-Extra ins Default-Set heben) und OTEL_EXPORTER_OTLP_ENDPOINT/OTEL_SERVICE_NAME als dokumentierte Env-Vars in render.yaml/docker-compose.yml aufnehmen — sonst bleibt Tracing im Cloud-Deployment faktisch inaktiv.

### Effort Estimate

S
