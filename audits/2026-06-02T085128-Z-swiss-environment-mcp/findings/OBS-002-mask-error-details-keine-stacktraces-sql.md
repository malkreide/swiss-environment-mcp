## Finding: OBS-002 — Mask Error Details: keine Stacktraces / SQL ans LLM

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status (Check)** | ⚠️ PARTIAL |
| **Status (Finding)** | open |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `OBS-002` |
| **PDF-Reference** | Sec 6.2 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |

### Kontext (Check-Description)

Wenn Tool-Errors Stacktraces, SQL-Syntax, Datei-Pfade oder gar Credentials enthalten, fliesst dieser Inhalt in den LLM-Kontext und damit potentiell ins User-Sichtbare zurück. Das ist Information Disclosure: Angreifer mit User-Zugriff erfahren über provozierte Errors die Server-Architektur, DB-Schema, gemountete Pfade, sogar geleakte Tokens (z.B. in `Authorization`-Headern, die im Stacktrace landen).

FastMCP bietet `mask_error_details=True`: Server-Errors werden auf eine generische Message reduziert (`"An error occurred"`), Original-Details landen nur im Server-Log.

### Observed Behavior

Belege aus Code/Konfiguration des auditierten Servers:

- handle_http_error liefert generische, user-freundliche Meldungen ohne Stacktraces (api_client.py:49-64)
- Keine traceback.format_exc()-Ausgaben

### Gaps gegenüber Pass-Criteria

- mask_error_details=True nicht im FastMCP-Init gesetzt
- Catch-all gibt type(e).__name__ + str(e) zurück (api_client.py:64) — kann interne Details leaken

### Remediation (aus Katalog-Check OBS-002)

```diff
  mcp = FastMCP(
      "server",
+     mask_error_details=True,
  )

  @mcp.tool()
  async def search(query: str):
      try:
          return await db.search(query)
-     except Exception as e:
-         return {"error": str(e), "traceback": traceback.format_exc()}
+     except UserInputError as e:
+         return {"isError": True, "content": [
+             TextContent(type="text", text=f"Invalid input: {e.user_message}")
+         ]}
+     except Exception:
+         logger.exception("Unhandled error in search tool")
+         raise  # mask_error_details greift, generische Message ans LLM
```

### Effort Estimate

S — < 1 Tag pro Server.

### Verification After Fix

- Re-Audit von `OBS-002` mit `mcp-audit-skill` (gleicher catalog_hash)
- Ziel-Status: `pass`
