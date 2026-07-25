# MCP-Server Audit-Report — `swiss-environment-mcp`

**Audit-Datum:** 
**Skill-Version:** 1.0.0
**Catalog-Version:** ?

---

## 1. Executive Summary

Server `swiss-environment-mcp` wurde gegen 44 anwendbare Best-Practice-Checks geprüft. 38 bestanden, 6 Findings dokumentiert (1 critical, 2 high, 3 medium, 0 low). Production-Readiness: erreicht.

**Production-Readiness:** YES

---

## 2. Profil-Snapshot

| Feld | Wert |
|---|---|
| Server-Name | `swiss-environment-mcp` |
| Audit-Datum | ? |
| Skill-Version | 1.0.0 |
| Catalog-Version | ? |

---

## 3. Applicability

### Status pro Kategorie

| Kategorie | Pass | Fail | Partial | Todo | N/A |
|---|---|---|---|---|---|
| ARCH | 11 | 0 | 0 | 0 | 0 |
| CH | 1 | 0 | 0 | 0 | 0 |
| OBS | 5 | 0 | 0 | 0 | 0 |
| OPS | 3 | 0 | 0 | 0 | 0 |
| SCALE | 2 | 0 | 3 | 0 | 0 |
| SDK | 4 | 0 | 0 | 0 | 0 |
| SEC | 12 | 0 | 3 | 0 | 0 |
| **Total** | **38** | **0** | **6** | **0** | **0** |

---

## 4. Findings-Übersicht

_Policy: `fail-or-partial`_

| ID | Category | Severity | Status |
|---|---|---|---|
| SEC-009 | SEC | critical | partial |
| SCALE-002 | SCALE | high | partial |
| SCALE-003 | SCALE | high | partial |
| SCALE-004 | SCALE | medium | partial |
| SEC-014 | SEC | medium | partial |
| SEC-015 | SEC | medium | partial |

**Gesamt:** 6 Findings

---

## 5. Detail-Findings

### SCALE-002

## Finding: SCALE-002 — Stateful Load Balancing für Streamable HTTP / SSE

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | accepted-risk |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `SCALE-002` (Check-Status: partial) |
| **PDF-Reference** | Sec 5.2 |
| **Audit-Datum** | 2026-07-25 (Re-Audit nach Remediation) |
| **Auditor** | Claude (mcp-audit-Skill, Run 2026-07-25T145413-Z) |

### Observed Behavior

Adjudiziert als dokumentierte Single-Instance-Risiko-Akzeptanz (accepted-risk). Die Pass-Kriterien des Checks setzen ein horizontal skaliertes Deployment voraus (applies_when transport==HTTP/SSE, multi-instance); die tatsaechliche Topologie ist bewusst single-instance, wodurch der Session-Stickiness-Bedarf strukturell entfaellt. docs/scaling.md haelt sowohl die aktuelle Entscheidung als auch die verbindlichen Muster + Re-Eval-Trigger fuer Scale-out fest. Ehrliche Einordnung nach Pass-Kriterien: partial (kein Sticky-LB/Shared-State implementiert), Risiko dokumentiert und begruendet.

Verbleibende Lücken:
- Keines der beiden Pass-Muster (Sticky Sessions ODER Shared-State-Session-Manager) ist implementiert — nach den strengen Pass-Kriterien nicht erfuellt.
- Kein Failover-Test (Modus 3), da in Single-Instance-Topologie kein Failover-Pfad existiert.

### Expected Behavior

Siehe Pass Criteria in `checks/SCALE-002.md` (Stateful Load Balancing für Streamable HTTP / SSE).

### Evidence

- docs/scaling.md:5-17 — 'Aktueller Stand: Single-Instance': explizite Architektur-Entscheidung. Server laeuft als einzelne Instanz (Render Web Service / einzelner Container); alle Requests einer Mcp-Session-Id landen zwangslaeufig auf derselben Instanz -> kein verteiltes Session-Management noetig.
- docs/scaling.md:5-17 — State-Eigenschaften dokumentiert: keine serverseitig persistierten Sessions, jeder Tool-Call abgeschlossen/idempotent gegenueber oeffentlichen Daten, ein geteilter httpx.AsyncClient pro Prozess (Lifespan).
- docs/scaling.md:19-37 — Re-Evaluations-Trigger: Sobald horizontal skaliert wird, ist genau EINES der zwei Muster verbindlich: (1) Sticky Sessions am Edge-LB (SCALE-003) oder (2) Shared-State-Session-Manager (Redis / Durable Objects). Session-TTL in beiden Faellen explizit zu setzen; Failover ohne Shared State darf nicht stumm umgeleitet werden.
- Code-Review: kein redis/memcached/SessionStore/session_manager in src/ (grep negativ) — konsistent mit Single-Instance-Topologie (kein Shared State implementiert).

### Risk Description

Severity high; Profil: read-only Public-Open-Data-Server ohne Auth, Single-Instance-Cloud-Deployment. Dokumentierte Risiko-Akzeptanz — Restrisiko im aktuellen Profil gering, Re-Evaluation bei Profil-Änderung zwingend (Trigger dokumentiert).

### Remediation

Single-Instance-Topologie — Session-Affinität trivial erfüllt, verteiltes Session-Management nicht nötig. Dokumentiert in docs/scaling.md mit den verbindlichen Mustern (Sticky-LB / Shared-State) für den Scale-out. Wird zum harten Handlungsbedarf, sobald >1 Replica deployt wird.

### Effort Estimate

M


### SCALE-003

## Finding: SCALE-003 — Mcp-Session-Id Routing via Edge-LB (HAProxy Stick-Tables)

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | accepted-risk |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `SCALE-003` (Check-Status: partial) |
| **PDF-Reference** | Sec 5.2 |
| **Audit-Datum** | 2026-07-25 (Re-Audit nach Remediation) |
| **Auditor** | Claude (mcp-audit-Skill, Run 2026-07-25T145413-Z) |

### Observed Behavior

Adjudiziert als dokumentierte Single-Instance-Risiko-Akzeptanz (accepted-risk). SCALE-003 ergaenzt SCALE-002 um den konkreten Routing-Layer und greift erst bei multi-instance-Deployment. Die verbindliche Edge-LB-Konfiguration (HAProxy Stick-Table auf Mcp-Session-Id, TTL >= 24h, Kapazitaet >= 100k) ist als Scale-out-Trigger in docs/scaling.md hinterlegt, aber im aktuellen Single-Instance-Betrieb nicht aktiv. Ehrliche Einordnung nach Pass-Kriterien: partial.

Verbleibende Lücken:
- Kein Edge-LB liest den Mcp-Session-Id-Header (keine HAProxy-Stick-Table / NGINX-Hash / K8s-Ingress-Affinity implementiert) — strenge Pass-Kriterien nicht erfuellt.
- Kein Affinitaets-/Failover-Runtime-Test (Modus 2), da kein Edge-LB im Single-Instance-Setup vorhanden.

### Expected Behavior

Siehe Pass Criteria in `checks/SCALE-003.md` (Mcp-Session-Id Routing via Edge-LB (HAProxy Stick-Tables)).

### Evidence

- docs/scaling.md:19-37 — Scale-out-Abschnitt beschreibt den konkreten Edge-LB-Routing-Layer: HAProxy/Nginx/K8s-Ingress routet anhand des Mcp-Session-Id-Headers konsistent auf dasselbe Backend; HAProxy-Stick-Table auf den Header, TTL korreliert mit Session-TTL (z.B. 24h), Kapazitaet >= 100k Sessions.
- docs/scaling.md:5-17 — Begruendung, warum aktuell kein Edge-LB-Routing noetig ist: Single-Instance-Topologie, alle Requests einer Mcp-Session-Id landen zwangslaeufig auf derselben Instanz.
- docs/scaling.md:33-37 — Failover-Regel dokumentiert: bei Backend-Ausfall darf eine Session ohne Shared State nicht stumm auf ein neues Backend umgeleitet werden (entweder Shared State oder sauberer Session-Neuaufbau).
- find . -name 'haproxy.cfg' -o -name 'nginx.conf' -o -name 'ingress*.yaml' -> keine Edge-LB-Konfiguration im Repo (konsistent mit Single-Instance).

### Risk Description

Severity high; Profil: read-only Public-Open-Data-Server ohne Auth, Single-Instance-Cloud-Deployment. Dokumentierte Risiko-Akzeptanz — Restrisiko im aktuellen Profil gering, Re-Evaluation bei Profil-Änderung zwingend (Trigger dokumentiert).

### Remediation

Wie SCALE-002: In der Single-Instance-Topologie existiert kein Edge-LB, den man auf Mcp-Session-Id-Routing konfigurieren könnte. Muster (Stick-Table mit Kapazität + TTL, Failover-Test) in docs/scaling.md festgehalten; verbindlich beim Scale-out.

### Effort Estimate

M


### SCALE-004

## Finding: SCALE-004 — Containerization mit Multi-Stage-Builds

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `SCALE-004` (Check-Status: partial) |
| **PDF-Reference** | Sec 5.3 |
| **Audit-Datum** | 2026-07-25 (Re-Audit nach Remediation) |
| **Auditor** | Claude (mcp-audit-Skill, Run 2026-07-25T145413-Z) |

### Observed Behavior

5 von 6 Pass-Kriterien erfuellt: multi-stage, benannte Stages, slim-Base, USER non-root, HEALTHCHECK. Der frueher offene Punkt 'nicht verifizierbar / kein Gate' ist behoben — image-size.yml stellt jetzt eine reproduzierbare, path-gefilterte Groessenpruefung mit Regressions-Ceiling bereit. Streng bewertet bleibt jedoch das harte Kriterium '< 200 MB' unerfuellt (Ceiling bei 350 MB, Repo raeumt die Ueberschreitung selbst ein). Die Ueberschreitung ist ein begruendeter Trade-off gegen die OBS-006-Anforderung (otel-Extra im Image). Daher partial statt pass.

Verbleibende Lücken:
- Pass-Kriterium 'Final-Image-Groesse < 200 MB (Python)' ist NICHT erfuellt: das Image liegt (per Repo-eigenem Ceiling 350 MB und Schaetzung ~250-290 MB) oberhalb von 200 MB. Der OBS-006-otel-Extra treibt die Groesse ueber die 200-MB-Marke (dokumentierter Trade-off).
- Live-Docker-Build zur exakten Groessenmessung in der Audit-Umgebung nicht moeglich (kein Docker-Daemon).

### Expected Behavior

Siehe Pass Criteria in `checks/SCALE-004.md` (Containerization mit Multi-Stage-Builds).

### Evidence

- Dockerfile:2 (FROM python:3.12-slim AS builder) + :15 (FROM python:3.12-slim AS runtime) — 2 FROM-Statements, benannte Stages (multi-stage), slim-Base. Build-Stage baut ein Wheel, Runtime-Stage installiert nur das Wheel (+[otel]).
- Dockerfile:33-37 — non-root: groupadd/useradd 'app' (uid/gid 10001), USER app gesetzt (SEC-007).
- Dockerfile:40-42 — HEALTHCHECK-Direktive vorhanden (python urllib gegen http://127.0.0.1:8000/health, interval 30s).
- .github/workflows/image-size.yml — NEUER Regressions-Gate (SCALE-004): docker build + Groessenpruefung via 'docker image inspect --format {{.Size}}'; path-gefiltert auf [Dockerfile, pyproject.toml, src/**]; fail bei > CEILING.
- .github/workflows/image-size.yml — CEILING=350 (MB). Der Workflow-Kommentar raeumt explizit ein, dass das <=200-MB-Ideal durch den python-slim-Unterbau + das otel-Extra (OBS-006) knapp ueberschritten wird; das Ceiling faengt echte Regressionen (Fat-Dependencies), ohne bei jedem Build zu scheitern.
- Groessen-Schaetzung (Docker-Daemon in der Audit-Umgebung nicht verfuegbar, kein Live-Build): venv-site-packages der Runtime-Deps ohne otel bereits 95 MB; python:3.12-slim-Base ~130 MB unkomprimiert; + otel-Extra -> geschaetzt ~250-290 MB. Konsistent mit dem 350-MB-Ceiling und dem Repo-eigenen Eingestaendnis.

### Risk Description

Severity medium; Profil: read-only Public-Open-Data-Server ohne Auth, Single-Instance-Cloud-Deployment. Begründeter Trade-off — Kontrolle vorhanden, hartes Ideal-Kriterium bewusst zurückgestellt.

### Remediation

Der Image-Size-Gate (`.github/workflows/image-size.yml`) behebt das zuvor bemängelte Fehlen einer Grössen-Verifikation, gated aber auf ein Regressions-Ceiling von 350 MB statt des <200-MB-Ideals — ein bewusster Trade-off gegen die für OBS-006 nötige otel-Abhängigkeit. Falls <200 MB verbindlich gefordert wird: otel-Extra optional halten (separates Tracing-Image) oder Runtime-Dependencies weiter beschneiden.

### Effort Estimate

S


### SEC-009

## Finding: SEC-009 — Session-ID Cryptographic Binding (user_id:session_id)

| Feld | Wert |
|---|---|
| **Severity** | critical |
| **Status** | accepted-risk |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `SEC-009` (Check-Status: partial) |
| **PDF-Reference** | Sec 4.6 |
| **Audit-Datum** | 2026-07-25 (Re-Audit nach Remediation) |
| **Auditor** | Claude (mcp-audit-Skill, Run 2026-07-25T145413-Z) |

### Observed Behavior

applies_when erfuellt (transport != stdio-only, dual). Die harte Anforderung (Bindung an validierte User-Identitaet) bleibt technisch unerfuellt, weil kein Auth-/User-Konzept existiert; das zugrundeliegende Threat (Hijacking eines authentifizierten Opfer-Kontexts) hat mangels Auth und mangels privater Daten keine schaedliche Auspraegung. Dokumentierte, begruendete Risiko-Akzeptanz mit verbindlichen Re-Eval-Triggern. Ehrlich: partial (accepted-risk), unveraendert gegenueber Run 2026-07-25T092248-Z — die Remediation hat die Doku formalisiert, aber keine technische Kontrolle ergaenzt (weil bei no-auth nicht anwendbar).

Verbleibende Lücken:
- Harte Pass-Kriterien technisch unerfuellt: kein kryptografisches user_id:session_id-Binding, kein 401/403 bei Session-Mismatch, kein anwendungsseitiges TTL/Logout-Invalidation — mangels Auth nicht implementierbar.
- Session-ID-Generierung liegt im FastMCP-SDK (uuid4, crypto-sicher), aber ohne User-Binding und ohne Test-Nachweis im Repo.

### Expected Behavior

Siehe Pass Criteria in `checks/SEC-009.md` (Session-ID Cryptographic Binding (user_id:session_id)).

### Evidence

- Kein Auth-Modell im Code (profile.yaml auth_model: none); kein anwendungsseitiges User-zu-Session-Binding, weil keine User-Identitaet existiert.
- docs/security.md §'Session-Modell (SEC-009)' (Zeilen 52-60) dokumentiert die bewusste Entscheidung: FastMCP verwaltet die Mcp-Session-Id selbst, keine benutzerbezogenen Sessions/sensitiven Daten an Sessions gebunden.
- Verbindliche Re-Evaluations-Trigger dokumentiert: bei kuenftiger OAuth/OIDC-Einfuehrung sind kryptografisch zufaellige Session-IDs, Bindung an validierten sub-Claim, explizite TTL und serverseitige Logout-Invalidierung vorgeschrieben (docs/security.md:58-60).
- Kompensierend: read-only, ausschliesslich Public Open Data — geleakte Session-ID hat keinen exfiltrierbaren Wert (docs/security.md §Datenklassifikation).

### Risk Description

Severity critical; Profil: read-only Public-Open-Data-Server ohne Auth, Single-Instance-Cloud-Deployment. Dokumentierte Risiko-Akzeptanz — Restrisiko im aktuellen Profil gering, Re-Evaluation bei Profil-Änderung zwingend (Trigger dokumentiert).

### Remediation

Kein Auth-Modell → ein User-zu-Session-Binding ist nicht anwendbar. Dokumentierte Risiko-Akzeptanz mit Re-Evaluations-Trigger in docs/security.md. Sobald OAuth/OIDC eingeführt wird: kryptografische Session-IDs, Bindung an validierten sub-Claim, explizite TTL, serverseitige Invalidierung.

### Effort Estimate

S


### SEC-014

## Finding: SEC-014 — Tool-Allow-Listing via MCP-Gateway-Pattern

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | accepted-risk |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `SEC-014` (Check-Status: partial) |
| **PDF-Reference** | Sec 5.3 |
| **Audit-Datum** | 2026-07-25 (Re-Audit nach Remediation) |
| **Auditor** | Claude (mcp-audit-Skill, Run 2026-07-25T145413-Z) |

### Observed Behavior

applies_when nur via is_cloud_deployed==true erfuellt (enterprise/stadt_zuerich=false). Die Substanz des Checks (Lateral Movement zwischen Teams/Servern, rollenbasierter Zugriff) hat fuer einen single-server, no-auth, read-only Public-Data-Server praktisch keine Angriffsflaeche. Die harte technische Kontrolle (Allow-List/Gateway) bleibt jedoch unimplementiert. Ehrlich bewertet: Statuswechsel FAIL -> partial (accepted-risk) — begruendete, dokumentierte Risiko-Akzeptanz mit verbindlichen Re-Eval-Triggern + kompensierendem Snapshot-Gate rechtfertigt partial fuer dieses Profil, aber kein voller pass, da die Anforderung technisch offen bleibt.

Verbleibende Lücken:
- Harte Pass-Kriterien technisch unerfuellt: keine explizite default-deny Tool-Allow-List, kein Server-Side Group/Role-Check (mangels Auth/Gruppen nicht moeglich), keine team-/rollenspezifische tools/list-Filterung, keine Auditierung abgelehnter Tool-Calls.
- Kein vorgelagertes MCP-Gateway vorhanden.

### Expected Behavior

Siehe Pass Criteria in `checks/SEC-014.md` (Tool-Allow-Listing via MCP-Gateway-Pattern).

### Evidence

- docs/security.md §'Tool-Allow-Listing / Gateway (SEC-014)' (Zeilen 62-74) formalisiert die Risiko-Akzeptanz: kein Auth-Modell, nur read-only Public-Data-Tools, tools/list fuer alle Clients identisch -> kein rollen-/teambasiertes Allow-Listing implementiert.
- Verbindliche Re-Evaluations-Trigger dokumentiert: Sobald (a) Auth-Modell, (b) write-faehige Tools oder (c) Enterprise-/Multi-Tenant-Kontext -> vorgelagertes MCP-Gateway mit Tool-Allow-List pro Rolle + 403-Auditierung zwingend (docs/security.md:70-74).
- Profilkontext stuetzt niedriges Risiko: enterprise_context=false, stadt_zuerich_context=false, write_capable=false, single-server, keine Fremd-Tools (profile.yaml).
- Kompensierend fuer Server-Integritaet: Tool-Definition-Snapshot tool-snapshot.json (SEC-022 CI-Gate), Namespace-Praefix env_ (README.md).

### Risk Description

Severity medium; Profil: read-only Public-Open-Data-Server ohne Auth, Single-Instance-Cloud-Deployment. Dokumentierte Risiko-Akzeptanz — Restrisiko im aktuellen Profil gering, Re-Evaluation bei Profil-Änderung zwingend (Trigger dokumentiert).

### Remediation

Für das aktuelle Profil (no-auth, read-only, Public Open Data, single-server, keine Fremd-Tools) technisch nicht umsetzbar; dokumentierte Risiko-Akzeptanz + kompensierendes Snapshot-Gate (SEC-022). Re-Evaluations-Trigger in docs/security.md: MCP-Gateway mit Tool-Allow-List pro Rolle + 403-Auditierung nachrüsten, sobald Auth/Write/Enterprise-Betrieb hinzukommt.

### Effort Estimate

M


### SEC-015

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


---

## 6. Remediation-Plan

### Empfohlene Reihenfolge

1. **SEC-009** (critical, partial)
2. **SCALE-002** (high, partial)
3. **SCALE-003** (high, partial)
4. **SCALE-004** (medium, partial)
5. **SEC-014** (medium, partial)
6. **SEC-015** (medium, partial)

---

## 7. Audit-Metadata

| Feld | Wert |
|---|---|
| skill_version | `1.0.0` |
| policy | `fail-or-partial` |


_Generated by tools/build_report.py — do not edit by hand._
