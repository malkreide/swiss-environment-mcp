## Finding: SEC-015 — Pre-Flight Tool-Poisoning Detection

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | accepted-risk |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `SEC-015` (Check-Status: partial) |
| **PDF-Reference** | Sec 5.3 |
| **Audit-Datum** | 2026-07-25 (Re-Audit nach Remediation) |
| **Auditor** | Claude (mcp-audit-Skill, Run 2026-07-25T145413-Z) |

### Observed Behavior

applies_when nur via is_cloud_deployed==true erfuellt (enterprise/stadt_zuerich=false). Das Threat (poisoned Fremd-Tool-Definitionen) existiert fuer diesen single-server ohne Tool-Aggregation nicht; der Snapshot-Gate deckt den einzigen realen Vektor (Rug-Pull eigener Defs) ab. Ehrlich bewertet: Statuswechsel FAIL -> partial (accepted-risk) — dokumentierte, begruendete Risiko-Akzeptanz + vier benannte Muster + kompensierende Kontrolle + Re-Eval-Trigger rechtfertigen partial fuer dieses Profil; kein voller pass, da die technische Detection-Anforderung offen bleibt.

Verbleibende Lücken:
- Harte Pass-Kriterien technisch unerfuellt: kein Pre-Flight-Detection-Layer, keine Pattern-Klassen als Code, kein default-deny-Filter fuer High-Risk-Tools, kein SIEM-Alerting, keine Detection-Tests.

### Expected Behavior

Siehe Pass Criteria in `checks/SEC-015.md` (Pre-Flight Tool-Poisoning Detection).

### Evidence

- docs/security.md §'Tool-Poisoning-Detection (SEC-015)' (Zeilen 76-95) formalisiert die Risiko-Akzeptanz: Server laeuft ohne vorgelagertes Gateway und aggregiert KEINE fremden Tool-Definitionen (einzige Tool-Quelle ist der Server selbst) -> Pre-Flight-Detection nicht implementiert.
- Alle vier Katalog-Muster­klassen sind dokumentiert (eingebettete System-Prompts, Override-/Jailbreak-Phrasen, unsichtbare Steuerzeichen/Zero-Width/Bidi, Homoglyphen) als das, was ein Gateway-Deployment ergaenzen muesste (docs/security.md:85-91).
- Kompensierende Kontrolle gegen Rug-Pull der eigenen Tool-Defs: Tool-Definition-Snapshot tool-snapshot.json (SEC-022, CI-Gate) — docs/security.md:81-83.
- Verbindlicher Re-Evaluations-Trigger: Sobald der Server hinter ein Gateway gestellt wird oder Tools Dritter mountet -> vier Muster als default-deny-Filter + SIEM-Alerting + Tests (docs/security.md:93-95).
- Der Check selbst stuft das Risiko bei ausschliesslich eigenen Servern als niedrig ein (SEC-015.md Description).

### Risk Description

Severity medium; Profil: read-only Public-Open-Data-Server ohne Auth, Single-Instance-Cloud-Deployment. Dokumentierte Risiko-Akzeptanz — Restrisiko im aktuellen Profil gering, Re-Evaluation bei Profil-Änderung zwingend (Trigger dokumentiert).

### Remediation

Kein Pre-Flight-Detection-Layer, da keine fremden Tool-Definitionen aggregiert werden; die vier Detektions-Muster­klassen sind in docs/security.md als Nachrüst-Pflicht dokumentiert, Snapshot-Gate (SEC-022) als kompensierende Kontrolle. Re-Evaluations-Trigger: sobald der Server hinter ein Gateway gestellt wird oder Fremd-Tools mountet.

### Effort Estimate

M
