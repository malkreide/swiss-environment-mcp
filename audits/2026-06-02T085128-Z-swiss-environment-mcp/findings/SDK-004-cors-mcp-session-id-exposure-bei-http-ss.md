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

- streamable_http-Transport aktiv für Cloud (Dockerfile/render.yaml)

### Gaps gegenüber Pass-Criteria

- Keine CORS-Middleware konfiguriert
- Mcp-Session-Id nicht in expose_headers/allow_headers — Browser-/SSE-Clients können Session-Header nicht lesen

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
