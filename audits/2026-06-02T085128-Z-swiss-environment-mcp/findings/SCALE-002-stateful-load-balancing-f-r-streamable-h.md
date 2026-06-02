## Finding: SCALE-002 — Stateful Load Balancing für Streamable HTTP / SSE

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status (Check)** | ⚠️ PARTIAL |
| **Status (Finding)** | open |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `SCALE-002` |
| **PDF-Reference** | Sec 5.2 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |

### Kontext (Check-Description)

MCP-Verbindungen über Streamable HTTP / SSE sind **fundamental zustandsbehaftet**. Bei der Verbindungsinitialisierung verhandeln Client und Server Protokollversionen, Capability-Flags und etablieren Abonnements für Ressourcenänderungen.

In horizontal skalierten Deployments (Kubernetes, mehrere Pods, Cloudflare Workers, Railway-Replicas) routen Standard-Load-Balancer naive Anfragen ohne Affinität zu unterschiedlichen Backend-Instanzen.

### Observed Behavior

Belege aus Code/Konfiguration des auditierten Servers:

- render.yaml als Single-Web-Service deployt (Single-Instance funktioniert)

### Gaps gegenüber Pass-Criteria

- Keine Sticky-Sessions / kein Shared-State-Session-Manager (Redis/Durable Objects)
- Keine explizite Session-TTL — Scale-out würde Sessions brechen
- Strategie nicht dokumentiert

### Remediation (aus Katalog-Check SCALE-002)

### Variante A: Sticky Sessions mit HAProxy

```haproxy
frontend mcp_frontend
    bind *:443 ssl crt /etc/ssl/server.pem
    mode http
    # Backend-Selection nach Mcp-Session-Id
    default_backend mcp_backend

backend mcp_backend
    mode http
    balance roundrobin
    stick-table type string len 64 size 200k expire 24h peers mycluster
    stick on hdr(Mcp-Session-Id)
    option httpchk GET /healthz
    server mcp1 10.0.1.1:8080 check
    server mcp2 10.0.1.2:8080 check
    server mcp3 10.0.1.3:8080 check
```

### Variante B: Redis-basierter Session-Manager

```python
# pyproject.toml
# dependencies = ["fastmcp", "redis>=5.0", "structlog"]

from contextlib import asynccontextmanager
from fastmcp import FastMCP
from redis.asyncio import Redis
import json

@asynccontextmanager
async def lifespan(app):
    redis_client = Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    app.state.session_store = redis_client
    try:
        yield
    finally:
        await redis_client.aclose()

mcp = FastMCP("zurich-opendata", lifespan=lifespan)
```

### Effort-Empfehlung

- **Variante A** schneller bei vorhandener LB-Infrastruktur (1–2 Tage)
- **Variante B** robuster langfristig, vermeidet Sticky-Session-Komplikationen (3–5 Tage)

### Effort Estimate

M — 1–3 Tage je nach Komplexität der bestehenden Infrastruktur.

### Verification After Fix

- Re-Audit von `SCALE-002` mit `mcp-audit-skill` (gleicher catalog_hash)
- Ziel-Status: `pass`
