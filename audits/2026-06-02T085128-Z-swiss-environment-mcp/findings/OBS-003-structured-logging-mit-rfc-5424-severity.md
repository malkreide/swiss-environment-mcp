## Finding: OBS-003 — Structured Logging mit RFC 5424 Severity-Stufen

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status (Check)** | ❌ FAIL |
| **Status (Finding)** | open |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `OBS-003` |
| **PDF-Reference** | Sec 6.3 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |

### Kontext (Check-Description)

MCP-Server-Logs müssen strukturiert sein (JSON oder logfmt), nicht plaintext. Das ermöglicht Aggregation in Datadog/Splunk/Loki ohne Regex-Parsing, korrelierte Suche über Correlation-IDs, und konsistente Severity-Filterung.

Der MCP-Standard nutzt RFC 5424's 8 Severity-Stufen: `debug`, `info`, `notice`, `warning`, `error`, `critical`, `alert`, `emergency`. Über das `notifications/message`-Event können Logs auch an den Client weitergereicht werden — der Client kann via `logging/setLevel` dynamisch filtern.

Für Python ist `structlog` der Standard, für TypeScript `pino`.

### Observed Behavior

Belege aus Code/Konfiguration des auditierten Servers:

- (keine positiven Belege)

### Gaps gegenüber Pass-Criteria

- Kein Logging im gesamten Code (kein logging/structlog/loguru)
- Keine Severity-Stufen, kein bound context (tool name, session_id)

### Remediation (aus Katalog-Check OBS-003)

```diff
- import logging
- logger = logging.getLogger(__name__)
+ import structlog
+ logger = structlog.get_logger("mcp.server")

  @mcp.tool()
  async def search(query: str, ctx):
-     logger.info(f"Searching for {query}")
-     result = await api.search(query)
-     logger.info(f"Got {len(result)} results")
+     log = logger.bind(tool="search", query=query, session=ctx.session_id)
+     log.info("tool_invoked")
+     result = await api.search(query)
+     log.info("tool_succeeded", count=len(result))
      return result
```

### Effort Estimate

S — < 1 Tag pro Server.

### Verification After Fix

- Re-Audit von `OBS-003` mit `mcp-audit-skill` (gleicher catalog_hash)
- Ziel-Status: `pass`
