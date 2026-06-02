## Finding: SDK-003 — Context Injection für Progress Reports und Logging

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status (Check)** | ⚠️ PARTIAL |
| **Status (Finding)** | open |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `SDK-003` |
| **PDF-Reference** | Sec 3.1 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |

### Kontext (Check-Description)

FastMCP bietet via `Context`-Parameter ein typsicheres Interface zu Server-Internals: Logging, Progress-Reports, Client-Info, Session-State, Sampling, Elicitation.

### Observed Behavior

Belege aus Code/Konfiguration des auditierten Servers:

- Tools fangen Exceptions und liefern verständliche Fehlermeldungen

### Gaps gegenüber Pass-Criteria

- Kein ctx: Context-Parameter in irgendeinem Tool
- Kein ctx.report_progress() bei netzgebundenen Tools (>2s möglich)
- Teils stilles Schlucken von Exceptions (env_nabel_current: api.handle_http_error-Return ignoriert, server.py:463-465)

### Remediation (aus Katalog-Check SDK-003)

Migrationsweg für ein langes Tool:

```diff
+ from mcp.server.fastmcp import Context

  @mcp.tool()
- async def export_all_records(format: str) -> dict:
-     records = await db.fetch_all()
-     for record in records:
-         await transform(record, format)
-     return {"count": len(records)}
+ async def export_all_records(format: str, ctx: Context) -> dict:
+     await ctx.info(f"Starting export in format={format}")
+     records = await db.fetch_all()
+     await ctx.info(f"Loaded {len(records)} records, transforming...")
+
+     transformed = []
+     for i, record in enumerate(records):
+         if i % 50 == 0:
+             await ctx.report_progress(
+                 progress=i,
+                 total=len(records),
+                 message=f"Transformed {i}/{len(records)}",
+             )
+         transformed.append(await transform(record, format))
+
+     await ctx.info(f"Export complete: {len(transformed)} records")
+     return {"count": len(transformed), "format": format}
```

### Effort Estimate

S — < 1 Tag. Pro Tool 10 Minuten + Tests.

### Verification After Fix

- Re-Audit von `SDK-003` mit `mcp-audit-skill` (gleicher catalog_hash)
- Ziel-Status: `pass`
