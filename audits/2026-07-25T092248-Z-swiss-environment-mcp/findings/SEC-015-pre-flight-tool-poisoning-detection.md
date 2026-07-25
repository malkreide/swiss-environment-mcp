## Finding: SEC-015 — Pre-Flight Tool-Poisoning Detection

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | accepted-risk |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `SEC-015` (Check-Status: fail) |
| **PDF-Reference** | Sec 5.3 |
| **Audit-Datum** | 2026-07-25 |
| **Auditor** | Claude (mcp-audit-Skill, Run 2026-07-25T092248-Z) |

### Observed Behavior

Pre-Flight-Tool-Poisoning-Detection ist nicht vorhanden — bewusst und in docs/security.md begründet (nur eigene Tool-Definitionen, Snapshot-CI-Gate als kompensierende Integritätskontrolle). Gegen die Pass-Kriterien gemessen (0/6) ergibt das ein fail; das Restrisiko ist beim aktuellen Single-Server-Profil gering.

Lücken im Detail:
- Kein Detection-Layer, keine der vier geforderten Pattern-Klassen (System-Prompts, Override-Phrasen, Invisible-Characters, Homoglyphs) abgedeckt
- Kein default-deny-Filter für high-risk Tool-Definitionen, kein Logging/SIEM-Alerting von Detection-Events
- Keine Tests für Standard-Angriffsmuster

### Expected Behavior

Siehe Pass Criteria in `checks/SEC-015.md` (Pre-Flight Tool-Poisoning Detection).

### Evidence

- Repo-weite Suche (grep nach tool.poisoning|prompt.injection|sanitize.*description in src/ und deploy-Artefakten) ohne Treffer — kein Pre-Flight-Detection-Layer implementiert
- docs/security.md (Abschnitt 'Tool-Poisoning / Gateway (SEC-015)') — dokumentierte Risiko-Akzeptanz: eigenständiger read-only Public-Data-Server ohne Gateway, Detection 'für dieses Profil nicht erforderlich'; bei Enterprise-Einsatz Prompt-Injection-Filtering am Gateway gefordert
- tool-snapshot.json (Repo-Root) + .github/workflows/ci.yml:40 — Tool-Definition-Snapshot als CI-Gate (SEC-022) sichert die Integrität der eigenen Tool-Definitionen gegen unbemerkte Änderungen (Rug-Pull), ersetzt aber keine Pattern-Detection
- Keine Tests für Injection-/Homoglyph-/Zero-Width-Erkennung in tests/ (grep nach poisoning|injection|homoglyph ohne Treffer in Detection-Kontext)

### Risk Description

Severity medium gemäss Katalog; Profil-Kontext: read-only Public-Open-Data-Server ohne Auth, Single-Instance-Cloud-Deployment. Dokumentierte Risiko-Akzeptanz — Restrisiko im aktuellen Profil gering, Re-Evaluation bei Profil-Änderung zwingend.

### Remediation

Pre-Flight-Tool-Poisoning-Detection ist erst relevant, wenn fremde Tool-Definitionen aggregiert werden (Gateway-Szenario). Kompensierende Kontrolle heute: tool-snapshot.json + CI-Gate (SEC-022). Risiko-Akzeptanz in docs/security.md um die vier Pattern-Klassen des Checks ergänzen.

### Effort Estimate

M
