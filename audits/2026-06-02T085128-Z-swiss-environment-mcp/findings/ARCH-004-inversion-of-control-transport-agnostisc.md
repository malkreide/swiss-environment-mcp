## Finding: ARCH-004 — Inversion of Control: Transport-agnostische Server-Logik

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status (Check)** | ⚠️ PARTIAL |
| **Status (Finding)** | open |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `ARCH-004` |
| **PDF-Reference** | Sec 2.1 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |

### Kontext (Check-Description)

Die MCP-Spezifikation trennt strikt zwischen Data Layer (JSON-RPC 2.0, Tools/Resources/Prompts) und Transport Layer (stdio / Streamable HTTP / SSE). Der Best-Practice-Standard verlangt, dass die Geschäftslogik des Servers diese Trennung respektiert: Tool-Handler müssen **transport-agnostisch** sein. Derselbe `searchData()`-Tool-Handler muss identisch funktionieren, egal ob er via stdio (Claude Desktop) oder SSE (Cloud-Deployment) aufgerufen wird.

**Warum:**

1. **Dual-Transport-Support:** Portfolio-Server müssen sowohl lokal (stdio) als auch in der Cloud (SSE) laufen.

### Observed Behavior

Belege aus Code/Konfiguration des auditierten Servers:

- Transport via MCP_TRANSPORT env-var wählbar, stdio + streamable_http (server.py:1309-1316)
- Keine request/stdin/stdout-Internals in Tool-Handlern

### Gaps gegenüber Pass-Criteria

- Konfiguration via direktem os.environ.get in main(), kein Pydantic-Settings-Objekt
- Kein gemeinsamer Lifespan/Setup für beide Transports

### Remediation (aus Katalog-Check ARCH-004)

Migrationsweg von monolithischem Setup zu IoC:

```diff
+ from pydantic_settings import BaseSettings
+ from contextlib import asynccontextmanager
+
+ class Settings(BaseSettings):
+     transport: str = "stdio"
+     host: str = "127.0.0.1"
+     port: int = 8000
+
+ @asynccontextmanager
+ async def lifespan(server):
+     # Shared setup für alle Transports
+     server.state.http_client = httpx.AsyncClient(timeout=30)
+     try:
+         yield
+     finally:
+         await server.state.http_client.aclose()
+
- mcp = FastMCP("server")
+ settings = Settings()
+ mcp = FastMCP("server", lifespan=lifespan)

  @mcp.tool()
- async def search(query: str, request: Request):
-     ua = request.headers["User-Agent"]
-     ...
+ async def search(query: str, ctx: Context):
+     client_name = ctx.client_info.name
+     ...

  if __name__ == "__main__":
-     mcp.run(transport="stdio")
+     if settings.transport == "sse":
+         mcp.settings.host = settings.host
+         mcp.settings.port = settings.port
+     mcp.run(transport=settings.transport)
```

### Effort Estimate

M — 1–3 Tage. Refactoring der Transport-Auswahl, Migration aller `request`-Zugriffe auf `ctx`, Testing in beiden Modi.

### Verification After Fix

- Re-Audit von `ARCH-004` mit `mcp-audit-skill` (gleicher catalog_hash)
- Ziel-Status: `pass`
