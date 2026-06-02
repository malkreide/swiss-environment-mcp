# MCP-Server Audit-Report — `swiss-environment-mcp`

**Audit-Datum:** 
**Skill-Version:** 1.0.0
**Catalog-Version:** ?

---

## 1. Executive Summary

Server `swiss-environment-mcp` wurde gegen 44 anwendbare Best-Practice-Checks geprüft. 38 bestanden, 6 Findings dokumentiert (0 critical, 2 high, 4 medium, 0 low). Production-Readiness: NICHT erreicht — blockierend: SDK-004.

**Production-Readiness:** NO

---

## 2. Profil-Snapshot

| Feld | Wert |
|---|---|
| Server-Name | `swiss-environment-mcp` |
| Audit-Datum | ? |
| Skill-Version | 1.0.0 |
| Catalog-Version | ? |
| transport | `dual` |
| auth_model | `none` |
| data_class | `Public Open Data` |
| write_capable | `False` |
| deployment | `['local-stdio', 'Render', 'Docker', 'Railway']` |
| uses_sampling | `False` |
| tools_make_external_requests | `True` |
| stadt_zuerich_context | `False` |
| schulamt_context | `False` |
| data_source.is_swiss_open_data | `True` |

---

## 3. Applicability

### Status pro Kategorie

| Kategorie | Pass | Fail | Partial | Todo | N/A |
|---|---|---|---|---|---|
| ARCH | 10 | 0 | 1 | 0 | 0 |
| CH | 1 | 0 | 0 | 0 | 0 |
| OBS | 4 | 1 | 0 | 0 | 0 |
| OPS | 3 | 0 | 0 | 0 | 0 |
| SCALE | 4 | 0 | 1 | 0 | 0 |
| SDK | 2 | 1 | 1 | 0 | 0 |
| SEC | 14 | 0 | 1 | 0 | 0 |
| **Total** | **38** | **2** | **4** | **0** | **0** |

---

## 4. Findings-Übersicht

_Policy: `fail-or-partial`_

| ID | Category | Severity | Status |
|---|---|---|---|
| SDK-004 | SDK | high | fail |
| SEC-005 | SEC | high | partial |
| ARCH-012 | ARCH | medium | partial |
| OBS-006 | OBS | medium | fail |
| SCALE-006 | SCALE | medium | partial |
| SDK-002 | SDK | medium | partial |

**Gesamt:** 6 Findings

---

## 5. Detail-Findings

### ARCH-012

## Finding: ARCH-012 — protocolVersion-Pinning + CHANGELOG + SDK-Update-Disziplin

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status (Check)** | ⚠️ PARTIAL |
| **Status (Finding)** | open |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `ARCH-012` |
| **PDF-Reference** | Anhang A9 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |

### Kontext (Check-Description)

Die MCP-Spec hat in 13 Monaten vier Major-Updates erlebt (2024-11, 2025-03, 2025-06, 2025-11). Das ist eine ungewöhnlich hohe Velocity für einen Industriestandard. Konkrete Folgen für Server-Maintainer:

1. **Tool Annotations** kamen erst 2025-03-26
2. **OAuth Resource Server** mit RFC 8707 wurde erst 2025-06-18 verpflichtend
3.

### Observed Behavior

Belege aus Code/Konfiguration des auditierten Servers:

- Dependabot aktiv (monatlich) + bereits gemergte Action-Update-PRs (#9-#12)
- README-Sektion 'MCP Protocol Version & Maintenance' + Update-Policy (#8)
- CHANGELOG Keep-a-Changelog + Tool-Snapshot-Disziplin

### Gaps gegenüber Pass-Criteria

- Kein expliziter protocolVersion-Pin im Code (vom MCP-SDK ausgehandelt; SDK-Version ist der Pin) — dokumentiert, aber nicht code-seitig fixiert

### Remediation (aus Katalog-Check ARCH-012)

### Schritt 1: protocolVersion pinnen

```diff
+ from importlib.metadata import version

  mcp = FastMCP(
      name="zh-education-mcp",
+     protocol_version="2025-06-18",
  )
```

### Schritt 2: CHANGELOG initialisieren

Wenn nicht vorhanden, mit Template starten und retroaktiv Major-Versionen dokumentieren (mindestens letzte 3).

### Schritt 3: Dependabot konfigurieren

```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "monthly"
    open-pull-requests-limit: 5
```

### Schritt 4: Quartalsweise Spec-Review

Im Audit-Tracker (Notion) oder GitHub Issues ein recurring Reminder für quartalsweise Spec-Velocity-Review:

- Was hat sich an der MCP-Spec geändert seit letztem Release?
- Welche Server müssen ihre `protocolVersion` aktualisieren?
- Gibt es Compliance-relevante Spec-Änderungen?

### Effort Estimate

S — < 1 Tag pro Server. Pinning + CHANGELOG-Template + Dependabot-Setup.

### Verification After Fix

- Re-Audit von `ARCH-012` mit `mcp-audit-skill` (gleicher catalog_hash)
- Ziel-Status: `pass`


### OBS-006

## Finding: OBS-006 — OpenTelemetry Distributed Tracing pro Tool-Call

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status (Check)** | ❌ FAIL |
| **Status (Finding)** | open |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `OBS-006` |
| **PDF-Reference** | Anhang B10 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |

### Kontext (Check-Description)

OBS-005 deckt Audit-Logs für SIEM-Integration ab — Security-fokussiert.

### Observed Behavior

Belege aus Code/Konfiguration des auditierten Servers:

- Als geplante Verbesserung in docs/roadmap.md vermerkt (#8)

### Gaps gegenüber Pass-Criteria

- Kein OpenTelemetry/OTLP/Tracing implementiert — unverändert offen seit Erstaudit

### Remediation (aus Katalog-Check OBS-006)

### Schritt 1: SDK-Installation

```toml
# pyproject.toml
[project.dependencies]
"opentelemetry-api" = "^1.21"
"opentelemetry-sdk" = "^1.21"
"opentelemetry-exporter-otlp" = "^1.21"
"opentelemetry-instrumentation-httpx" = "^0.42b0"
```

### Schritt 2: Setup-Modul

```python
# src/server_name/observability.py
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.resources import Resource
# ...

def setup_tracing():
    resource = Resource.create({
        "service.name": os.environ.get("OTEL_SERVICE_NAME", "schulamt-mcp"),
        "deployment.environment": os.environ.get("ENVIRONMENT", "development"),
    })
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)
    HTTPXClientInstrumentor().instrument()
```

### Schritt 3: Decorator anwenden

`@traced_tool` als Standard auf alle Tool-Decorators stacken.

### Schritt 4: OTLP-Backend wählen

Für Schulamt-Kontext: Datadog (DSG-konform mit `DD_SITE=datadoghq.eu`), Grafana Tempo (selbst-gehostet, OpenBao-Compatible), oder Honeycomb (EU-Region).

### Effort Estimate

M — 1–3 Tage. SDK-Setup + Decorator + Backend-Konfiguration + Tests.

### Verification After Fix

- Re-Audit von `OBS-006` mit `mcp-audit-skill` (gleicher catalog_hash)
- Ziel-Status: `pass`


### SCALE-006

## Finding: SCALE-006 — Resource-Limits per Container (Memory, CPU, FDs)

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status (Check)** | ⚠️ PARTIAL |
| **Status (Finding)** | open |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `SCALE-006` |
| **PDF-Reference** | Sec 5.3 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |

### Kontext (Check-Description)

Ohne explizite Resource-Limits kann ein einzelner MCP-Server-Bug das ganze System destabilisieren: ein Memory-Leak frisst die Host-Ressourcen, ein File-Descriptor-Leak öffnet Tausende dangling Connections, ein CPU-bound Query starvt nachbar-Pods. In Multi-Tenant-Cloud-Umgebungen (Railway, Render, K8s) müssen Memory, CPU, FDs explizit gedeckelt werden.

Faustregeln für MCP-Server: 256 MB – 1 GB RAM (je nach Daten-Cache), 0.5–1 CPU, FD-Limit 1024 (Standard reicht meistens). Bei Hybrid-Servern mit lokalem Dump-Cache eher 1–2 GB RAM einplanen.

### Observed Behavior

Belege aus Code/Konfiguration des auditierten Servers:

- render.yaml plan: starter; Resource-Limit-Strategie in docs/scaling.md dokumentiert (#8); httpx-Timeouts gesetzt

### Gaps gegenüber Pass-Criteria

- Keine harten Memory/CPU-Limits in render.yaml/Docker explizit gesetzt — nur dokumentiert

### Remediation (aus Katalog-Check SCALE-006)

Für Railway: in der Web-UI unter Project Settings → Resources die Limits setzen.

Für Docker-Compose-Production:

```yaml
services:
  mcp:
    image: malkreide/mcp-server:v0.1.0
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '0.5'
    ulimits:
      nofile:
        soft: 4096
        hard: 8192
```

### Effort Estimate

S — < 1 Tag pro Server.

### Verification After Fix

- Re-Audit von `SCALE-006` mit `mcp-audit-skill` (gleicher catalog_hash)
- Ziel-Status: `pass`


### SDK-002

## Finding: SDK-002 — Pydantic v2 / TypedDict / Dataclass als Tool-Returns

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status (Check)** | ⚠️ PARTIAL |
| **Status (Finding)** | open |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `SDK-002` |
| **PDF-Reference** | Sec 3.1 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |

### Kontext (Check-Description)

FastMCP wraps Tool-Returns automatisch in MCP-konformes Format — aber nur, wenn der Return-Typ strukturiert ist. Bei plain `dict` oder `str` muss FastMCP raten, welche Felder optional sind, welche Validierungen gelten, was passiert wenn Schema-Mismatches auftreten. Bei Pydantic-`BaseModel`, `TypedDict` oder `@dataclass` ist alles explizit und typgeprüft.

Konkrete Vorteile:

1. **Automatische Schema-Generierung:** FastMCP exponiert das Output-Schema im `tools/list`-Manifest. Das LLM weiss damit, was es erwarten kann, und kann Folge-Calls präziser planen.
2.

### Observed Behavior

Belege aus Code/Konfiguration des auditierten Servers:

- Typisierter ResponseEnvelope (source/provenance/count/match_type/results/note, Literal) im JSON-Modus von env_nabel_stations/env_hydro_stations (#7)

### Gaps gegenüber Pass-Criteria

- Tools geben weiterhin str zurück (Markdown-Default); Envelope nur im JSON-Pfad und nicht für alle Such-/Listen-Tools (z.B. env_bafu_datasets hat keinen JSON-Modus)

### Remediation (aus Katalog-Check SDK-002)

```diff
+ from pydantic import BaseModel, Field
+ from typing import Literal
+
+ class SearchResponse(BaseModel):
+     source: str = Field(default="DataSource Name — CC BY 4.0")
+     provenance: Literal["live_api", "cached", "weekly_dump"]
+     results: list[dict]
+     count: int

  @mcp.tool()
- async def search(query: str):
-     results = await api.search(query)
-     return {"results": results, "count": len(results)}
+ async def search(query: str, ctx) -> SearchResponse:
+     results = await api.search(query)
+     return SearchResponse(
+         provenance="live_api",
+         results=results,
+         count=len(results),
+     )
```

### Effort Estimate

S — < 1 Tag. Pro Tool 5–15 Minuten Refactoring + Tests.

### Verification After Fix

- Re-Audit von `SDK-002` mit `mcp-audit-skill` (gleicher catalog_hash)
- Ziel-Status: `pass`


### SDK-004

## Finding: SDK-004 — CORS Mcp-Session-Id Exposure bei HTTP/SSE

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status (Check)** | ❌ FAIL |
| **Status (Finding)** | open |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `SDK-004` |
| **PDF-Reference** | Sec 3.1 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |

### Kontext (Check-Description)

Bei Streamable HTTP / SSE läuft die MCP-Kommunikation über Cross-Origin-Requests, wenn der Client (Browser-basiert) auf einer anderen Domain als der Server hostet. Der Server gibt nach `init` einen `Mcp-Session-Id`-Header in der Response zurück — diesen muss der Browser an Folge-Requests anhängen können.

Das Problem: Browser blockieren standardmässig den Zugriff auf Custom-Response-Headers via JavaScript (CORS-Spezifikation).

### Observed Behavior

Belege aus Code/Konfiguration des auditierten Servers:

- Transport korrekt auf streamable-http umgestellt (#5)

### Gaps gegenüber Pass-Criteria

- KEINE CORS-Middleware konfiguriert (grep ohne Treffer in src/)
- FastMCP.streamable_http_app setzt per Default kein expose_headers — verifiziert
- Mcp-Session-Id wird Browser-Clients nicht via CORS exponiert. Im Erstaudit als 'adressiert' deklariert, tatsächlich NICHT umgesetzt — bleibt offen.

### Remediation (aus Katalog-Check SDK-004)

```diff
  from starlette.applications import Starlette
  from starlette.routing import Mount
+ from starlette.middleware import Middleware
+ from starlette.middleware.cors import CORSMiddleware

+ ALLOWED_ORIGINS = [
+     o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()
+ ]
+
+ middleware = [
+     Middleware(
+         CORSMiddleware,
+         allow_origins=ALLOWED_ORIGINS,
+         allow_methods=["GET", "POST", "OPTIONS"],
+         allow_headers=["Content-Type", "Mcp-Session-Id", "Authorization"],
+         expose_headers=["Mcp-Session-Id"],
+         allow_credentials=True,
+     ),
+ ]
+
  app = Starlette(
      routes=[Mount("/", app=mcp.streamable_http_app())],
+     middleware=middleware,
  )
```

Plus Umgebungsvariable:

```bash
# .env (production)
ALLOWED_ORIGINS=https://app.schulamt.zh.ch,https://claude.ai
```

### Effort Estimate

S — < 1 Tag. Middleware-Konfig + ENV-Var + Browser-Test.

### Verification After Fix

- Re-Audit von `SDK-004` mit `mcp-audit-skill` (gleicher catalog_hash)
- Ziel-Status: `pass`


### SEC-005

## Finding: SEC-005 — DNS-Rebinding-Prevention: DNS-Pinning gegen TOCTOU

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status (Check)** | ⚠️ PARTIAL |
| **Status (Finding)** | open |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `SEC-005` |
| **PDF-Reference** | Sec 4.4 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |

### Kontext (Check-Description)

SEC-004 (SSRF-Prevention) verlangt: Resolved IP wird gegen Blocklist geprüft, dann Request mit dieser IP. DNS-Rebinding ist ein verfeinerter Angriff, der diese Defense umgeht — durch zwei verschiedene DNS-Antworten für denselben Hostnamen mit kurzem TTL:

**Ablauf des Angriffs (TOCTOU = Time-Of-Check-Time-Of-Use):**

1. Angreifer kontrolliert `evil.attacker.com` mit DNS-TTL = 1 Sekunde
2. Erste Auflösung: `evil.attacker.com` → `198.51.100.42` (öffentliche IP, passiert SSRF-Check)
3. Server validiert: IP ist nicht in Blocklist → Pass
4.

### Observed Behavior

Belege aus Code/Konfiguration des auditierten Servers:

- IP-Blocklist gegen private/loopback/link-local; follow_redirects=False reduziert Rebinding-Fläche (#5)

### Gaps gegenüber Pass-Criteria

- Kein echtes DNS-Pinning (Custom-Resolver) — getaddrinfo-Auflösung und httpx-Connect bleiben getrennt (TOCTOU theoretisch offen, durch feste Hosts entschärft)

### Remediation (aus Katalog-Check SEC-005)

### Schritt 1: HTTP-Client mit Custom Transport

```python
import httpx
import socket
import ipaddress

class PinnedTransport(httpx.AsyncHTTPTransport):
    """HTTPX Transport mit DNS-Pinning."""

    async def handle_async_request(self, request):
        url = request.url
        if url.scheme != "https":
            raise httpx.RequestError("Only HTTPS allowed")

        # Resolve einmalig
        loop = asyncio.get_event_loop()
        addrinfo = await loop.getaddrinfo(
            url.host, url.port, type=socket.SOCK_STREAM
        )
        resolved_ip = addrinfo[0][4][0]

        # Range-Check
        ip = ipaddress.ip_address(resolved_ip)
        for blocked in BLOCKED_NETWORKS:
            if ip in blocked:
                raise httpx.RequestError(f"Blocked IP: {ip}")

        # URL mit gepinnter IP, aber Host-Header bleibt
        pinned_url = httpx.URL(str(url).replace(url.host, resolved_ip, 1))
        new_request = httpx.Request(
            method=request.method,
            url=pinned_url,
            headers=httpx.Headers(request.headers),
            content=request.content,
            extensions=request.extensions,
        )
        new_request.headers["Host"] = url.host
        # SNI bleibt durch URL-Hostname (httpx interner default)
        return await super().handle_async_request(new_request)


# Verwendung
async with httpx.AsyncClient(transport=PinnedTransport()) as client:
    response = await client.get("https://api.external.com/data")
```

### Schritt 2: Alternative — Egress-Proxy

Wenn Custom-Transport zu komplex: Stripe Smokescreen als Sidecar erledigt DNS-Pinning automatisch.

```yaml
# docker-compose.yml
services:
  smokescreen:
    image: stripe/smokescreen:latest
    command: ["--listen-ip", "127.0.0.1", "--listen-port", "4750"]

  mcp-server:
    image: malkreide/mcp-server
    environment:
      HTTPS_PROXY: http://smokescreen:4750
```

```python
# Im Code: einfach Proxy nutzen
async with httpx.AsyncClient(proxy="http://localhost:4750") as client:
    return await client.get(url)
```

### Schritt 3: Tests


*(gekürzt — vollständige Remediation siehe Katalog-Check `checks/SEC-005.md`)*

### Effort Estimate

M — 1–3 Tage. Custom-Transport oder Egress-Proxy-Setup + Tests.

### Verification After Fix

- Re-Audit von `SEC-005` mit `mcp-audit-skill` (gleicher catalog_hash)
- Ziel-Status: `pass`


---

## 6. Remediation-Plan

### Empfohlene Reihenfolge

1. **SDK-004** (high, fail)
2. **SEC-005** (high, partial)
3. **ARCH-012** (medium, partial)
4. **OBS-006** (medium, fail)
5. **SCALE-006** (medium, partial)
6. **SDK-002** (medium, partial)

---

## 7. Audit-Metadata

| Feld | Wert |
|---|---|
| skill_version | `1.0.0` |
| policy | `fail-or-partial` |


_Generated by tools/build_report.py — do not edit by hand._
