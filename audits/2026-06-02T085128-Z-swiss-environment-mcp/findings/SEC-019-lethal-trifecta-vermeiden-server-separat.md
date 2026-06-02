## Finding: SEC-019 — Lethal Trifecta vermeiden: Server-Separation Read vs Write/Send

| Feld | Wert |
|---|---|
| **Severity** | critical |
| **Status (Check)** | ⚠️ PARTIAL |
| **Status (Finding)** | open |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `SEC-019` |
| **PDF-Reference** | Anhang B1 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |

### Kontext (Check-Description)

Simon Willisons «Lethal Trifecta»-Konzept beschreibt drei Fähigkeiten, die einzeln harmlos, **kombiniert** aber den Server zur Waffe in der Hand eines Prompt-Injection-Angreifers machen:

1. **Zugriff auf private Daten** (Verwaltungsdaten, PII, interne Dokumente)
2. **Exposition gegenüber untrusted Content** (User-Input, externe Dokumente, Web-Scraping)
3.

### Observed Behavior

Belege aus Code/Konfiguration des auditierten Servers:

- Architektur vermeidet Lethal Trifecta: nur öffentliche Daten, read-only, ausgehende Requests nur an feste Gov-APIs — kein exfiltrierbarer Send-Kanal

### Gaps gegenüber Pass-Criteria

- Keine dokumentierte Trifecta-Bewertung in README/docs (ADR fehlt)

### Remediation (aus Katalog-Check SEC-019)

### Schritt 1: Trifecta-Audit pro Server

Für jeden Server im Portfolio die drei Fragen beantworten:

| Frage | Antwort | Score-Beitrag |
|---|---|---|
| Liest privater Daten? | ja/nein | +1 wenn ja |
| Untrusted Content? | ja/nein | +1 wenn ja |
| Externe Kommunikation? | ja/nein | +1 wenn ja |

Score 0–1: sicher. Score 2: ADR + Compensating Controls. Score 3: Server splitten.

### Schritt 2: Server-Splittung (bei Score 3)

Beispiel — aus einem hypothetischen `eltern-comm-mcp`:

```diff
- # Vorher: ein Server liest UND sendet
- @mcp.tool() def get_eltern_data(klassenid): ...
- @mcp.tool() def send_eltern_mail(recipient, body): ...

+ # Nachher: zwei Server
+ # eltern-data-mcp/
+ @mcp.tool() def get_eltern_data(klassenid): ...
+
+ # eltern-mail-mcp/  (separater Repo, separate Service-Identity)
+ ALLOWED_DOMAINS = frozenset({"schulen.zuerich.ch"})
+ @mcp.tool() def send_eltern_mail(recipient, body):
+     if recipient.split("@")[-1] not in ALLOWED_DOMAINS:
+         raise PermissionError(...)
```

### Schritt 3: ADR dokumentieren

Wie im Pass-Pattern Modus 2.

### Schritt 4: Audit-Trail

Bei Score-2-Servern: alle Tool-Calls werden geloggt, SIEM-Alerts (siehe OBS-005) auf ungewöhnliche Pattern (z.B. Recipients ausserhalb Allow-List).

### Effort Estimate

L — 1–2 Wochen bei nötiger Server-Splittung. S — < 1 Tag für reine Bewertung und ADR.

### Verification After Fix

- Re-Audit von `SEC-019` mit `mcp-audit-skill` (gleicher catalog_hash)
- Ziel-Status: `pass`
