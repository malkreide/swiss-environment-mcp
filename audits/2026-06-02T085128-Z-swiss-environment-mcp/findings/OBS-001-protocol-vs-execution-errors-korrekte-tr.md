## Finding: OBS-001 — Protocol vs. Execution Errors: korrekte Trennung

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status (Check)** | ⚠️ PARTIAL |
| **Status (Finding)** | open |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `OBS-001` |
| **PDF-Reference** | Sec 6.1 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |

### Kontext (Check-Description)

Die MCP-Spezifikation fordert eine strikte Trennung zwischen zwei Fehler-Typen.

### Observed Behavior

Belege aus Code/Konfiguration des auditierten Servers:

- Tool-Handler fangen anwendungsspezifische Fehler ab und liefern verständliche Texte (try/except in allen netzgebundenen Tools)

### Gaps gegenüber Pass-Criteria

- Fehler werden als normaler String-Result zurückgegeben, nicht via isError-Mechanismus
- Teils stilles Schlucken (env_nabel_current/env_hydro_history)
- Keine dedizierten Tests für Execution- vs. Protocol-Error-Pfade

### Remediation (aus Katalog-Check OBS-001)

```diff
+ from mcp.types import TextContent
+
  @mcp.tool()
  async def query_database(query: str) -> dict:
-     # FAIL: alle Exceptions werden zu JSON-RPC-Errors
-     conn = await asyncpg.connect(DATABASE_URL)
-     return {"rows": await conn.fetch(query)}
+     try:
+         conn = await asyncpg.connect(DATABASE_URL)
+         try:
+             rows = await conn.fetch(query)
+             return {"rows": [dict(r) for r in rows]}
+         finally:
+             await conn.close()
+     except asyncpg.PostgresSyntaxError as e:
+         # Execution Error: Query-Problem ist Aufgabe des LLMs zu lösen
+         return {
+             "isError": True,
+             "content": [TextContent(
+                 type="text",
+                 text=f"SQL syntax error: {str(e)}. Try simplifying the query."
+             )],
+         }
+     except asyncpg.PostgresConnectionError:
+         # Protocol-nahe: Server ist degraded
+         raise McpError(code=-32603, message="Database temporarily unavailable")
```

### Effort Estimate

M — 1–3 Tage. Pro Tool muss der Error-Pfad reviewed werden. Bei vielen Tools (>10) entsprechend aufwändiger.

### Verification After Fix

- Re-Audit von `OBS-001` mit `mcp-audit-skill` (gleicher catalog_hash)
- Ziel-Status: `pass`
