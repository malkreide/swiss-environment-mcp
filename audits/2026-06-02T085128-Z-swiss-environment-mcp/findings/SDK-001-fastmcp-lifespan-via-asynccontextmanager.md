## Finding: SDK-001 — FastMCP Lifespan via @asynccontextmanager + AsyncExitStack

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status (Check)** | ❌ FAIL |
| **Status (Finding)** | open |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `SDK-001` |
| **PDF-Reference** | Sec 3.1 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |

### Kontext (Check-Description)

MCP-Server halten häufig Ressourcen, die über die einzelne Tool-Anfrage hinaus existieren: HTTP-Connection-Pools, DB-Pools, Redis-Verbindungen, gecachte Auth-Tokens, Pre-Computed-Indexes. Werden diese pro Tool-Call neu erzeugt, bricht die Performance ein. Werden sie gar nicht aufgeräumt, ergeben sich Resource-Leaks (offene TCP-Connections, dangling Cursor).

FastMCP bietet das Lifespan-Pattern dafür: Eine `@asynccontextmanager`-Funktion erhält den FastMCP-Server, initialisiert Ressourcen vor dem ersten Request und räumt sie nach dem letzten Request sauber ab.

### Observed Behavior

Belege aus Code/Konfiguration des auditierten Servers:

- FastMCP genutzt (server.py:107)

### Gaps gegenüber Pass-Criteria

- Kein Lifespan / @asynccontextmanager
- httpx.AsyncClient wird pro Tool-Call neu erzeugt (_make_client in jeder api_client-Funktion) statt einmalig im Lifespan — Pass-Criteria explizit verletzt

### Remediation (aus Katalog-Check SDK-001)

Migrationsweg:

```diff
+ from contextlib import asynccontextmanager
+ import httpx
+
+ @asynccontextmanager
+ async def lifespan(server):
+     server.state.http = httpx.AsyncClient(timeout=30)
+     try:
+         yield
+     finally:
+         await server.state.http.aclose()
+
- mcp = FastMCP("zurich-opendata")
+ mcp = FastMCP("zurich-opendata", lifespan=lifespan)

  @mcp.tool()
- async def search(query: str):
-     async with httpx.AsyncClient() as client:
-         return (await client.get(f"https://api/{query}")).json()
+ async def search(query: str, ctx):
+     return (await ctx.fastmcp.state.http.get(f"https://api/{query}")).json()
```

### Effort Estimate

S — < 1 Tag. Lifespan-Block + Tool-Refactoring + Tests.

### Verification After Fix

- Re-Audit von `SDK-001` mit `mcp-audit-skill` (gleicher catalog_hash)
- Ziel-Status: `pass`
