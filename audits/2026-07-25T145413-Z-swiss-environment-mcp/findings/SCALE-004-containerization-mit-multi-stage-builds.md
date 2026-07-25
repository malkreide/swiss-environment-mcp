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
