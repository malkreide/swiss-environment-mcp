## Finding: SDK-002 — Pydantic v2 / TypedDict / Dataclass als Tool-Returns

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status (Check)** | ❌ FAIL |
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

- Pydantic v2 für Inputs, ConfigDict/Field genutzt

### Gaps gegenüber Pass-Criteria

- Tools geben rohe str (Markdown/JSON-String) zurück statt BaseModel/TypedDict
- Kein konsistenter Response-Envelope mit source/provenance/results/count

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
