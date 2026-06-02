## Finding: ARCH-003 — «Not Found» Anti-Pattern: Heuristiken statt leerer Antworten

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status (Check)** | ⚠️ PARTIAL |
| **Status (Finding)** | open |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `ARCH-003` |
| **PDF-Reference** | Sec 2.2 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |

### Kontext (Check-Description)

LLMs reagieren empirisch nachweisbar empfindlich auf negativ-framing in Tool-Responses. Eine Antwort wie `"No results found"` oder `[]` ohne Kontext führt häufig zu einer von zwei Failure-Modes:

1. **Halluzination:** Das Modell konstruiert eine Antwort aus Trainingsdaten, statt zuzugeben, dass es keine Information hat.
2.

### Observed Behavior

Belege aus Code/Konfiguration des auditierten Servers:

- Fallback-Antworten mit Direktlinks bei leeren/Fehler-Resultaten (server.py:586-599, 851-857)
- Station-not-found liefert bekannte Stationsliste + Tipp (server.py:452-458)

### Gaps gegenüber Pass-Criteria

- Kein match_type-Feld (exact/fuzzy/none) in Responses
- Einige Pfade liefern reine Fehler-Strings statt strukturierter Hinweise

### Remediation (aus Katalog-Check ARCH-003)

```diff
  @mcp.tool()
  async def find_school(name: str) -> list:
      results = await db.find(name)
-     if not results:
-         return []
+     if not results:
+         fuzzy = await db.find_fuzzy(name, threshold=0.7)
+         suggestions = await db.popular_school_names_starting_with(name[:3])
+         return {
+             "results": fuzzy[:5],
+             "match_type": "fuzzy" if fuzzy else "none",
+             "note": (
+                 f"Keine exakten Treffer für '{name}'. "
+                 f"{'Ähnliche Schulen aufgeführt.' if fuzzy else ''} "
+                 f"Häufige Schulnamen: {', '.join(suggestions[:5])}"
+             ),
+         }
      return {"results": results, "match_type": "exact"}
```

### Effort Estimate

S — Pro Tool ~30 Minuten. Bei 10 Such-Tools: 1 Tag.

### Verification After Fix

- Re-Audit von `ARCH-003` mit `mcp-audit-skill` (gleicher catalog_hash)
- Ziel-Status: `pass`
