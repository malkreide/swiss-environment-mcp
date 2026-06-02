## Finding: OPS-003 — Phasenarchitektur: Read-only First, dann Write, dann Multi-Agent

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status (Check)** | ⚠️ PARTIAL |
| **Status (Finding)** | open |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `OPS-003` |
| **PDF-Reference** | Anhang C4 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |

### Kontext (Check-Description)

Der Anhang sagt klar: «Die häufigste Ursache von MCP-Sicherheitsvorfällen 2025/26 war: ‹Wir haben gleich Schreibzugriffe gebaut, weil es ging.›»

Disziplin: jeder Server durchläuft drei Phasen.

### Observed Behavior

Belege aus Code/Konfiguration des auditierten Servers:

- Server ist durchgängig read-only (alle Tools readOnlyHint=True) — entspricht Phase 1

### Gaps gegenüber Pass-Criteria

- Keine explizite Phasen-Deklaration (Phase 1/2/3) im README
- Kein Roadmap-File mit Phasen-Tasks

### Remediation (aus Katalog-Check OPS-003)

### Schritt 1: Phase-Audit pro Server

Pro Server im Portfolio:

| Frage | Antwort |
|---|---|
| Hat der Server destruktive Tools? | ja → mindestens Phase 3 |
| Hat der Server Semantic Layer / Federation? | ja → mindestens Phase 2 |
| Sonst | Phase 1 |

### Schritt 2: Phase-Sektion ins README

Mit Status-Tabelle wie im Pass-Pattern Modus 1.

### Schritt 3: Roadmap erstellen

Mit Phase-Voraussetzungen als Tasks. Falls aktueller Server in Phase 2 oder 3 ist und Phase-1-Voraussetzungen fehlen: Findings im Audit-Tracker dokumentieren, retroaktiv schliessen.

### Schritt 4: Phase-Gate als Notion-Workflow

In Notion-Audit-Tracker-Schema (`a2736a65-...`) ein Feld «Phase» (Single-Select: 1, 2, 3) mit klaren Übergangs-Anforderungen.

### Effort Estimate

S — < 1 Tag pro Server für Initial-Phase-Deklaration. M — Wochen für Phase-Übergänge mit allen Compensating-Action-Anforderungen.

### Verification After Fix

- Re-Audit von `OPS-003` mit `mcp-audit-skill` (gleicher catalog_hash)
- Ziel-Status: `pass`
