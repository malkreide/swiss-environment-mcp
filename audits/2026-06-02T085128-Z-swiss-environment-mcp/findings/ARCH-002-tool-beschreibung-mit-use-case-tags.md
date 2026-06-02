## Finding: ARCH-002 — Tool-Beschreibung mit Use-Case-Tags

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status (Check)** | ⚠️ PARTIAL |
| **Status (Finding)** | open |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `ARCH-002` |
| **PDF-Reference** | Sec 2.2 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |

### Kontext (Check-Description)

LLMs wählen Tools nicht über exakte Namens-Treffer, sondern über semantische Embeddings der Tool-Beschreibung. Eine Beschreibung wie `"Searches database"` lässt das Modell zwischen drei `getX`-Tools rätseln.

### Observed Behavior

Belege aus Code/Konfiguration des auditierten Servers:

- Docstrings >100 Zeichen mit Use-Case-Kontext (z.B. server.py:973-988 env_hazard_regions)

### Gaps gegenüber Pass-Criteria

- Keine strukturierten <use_case>/<important_notes>/<example>-Tags in den description=-Klauseln

### Remediation (aus Katalog-Check ARCH-002)

```diff
  @mcp.tool(
      name="searchEducationStats",
-     description="Search education statistics."
+     description=(
+         "Sucht in den städtischen Bildungsstatistiken nach Kennzahlen "
+         "(Klassengrösse, Lehrer-Schüler-Verhältnis, Anteil DaZ, etc.).\n\n"
+         "<use_case>Politische / journalistische Recherche, "
+         "Schulamts-interne Reportings, Pädagogik-Analysen.</use_case>\n\n"
+         "<important_notes>Daten werden quartalsweise aktualisiert. "
+         "Personendaten sind nicht abrufbar — nur aggregierte "
+         "Kennzahlen.</important_notes>"
+     ),
  )
```

### Effort Estimate

S — Pro Tool 5–10 Minuten. Bei 10 Tools: ~1 Tag.

### Verification After Fix

- Re-Audit von `ARCH-002` mit `mcp-audit-skill` (gleicher catalog_hash)
- Ziel-Status: `pass`
