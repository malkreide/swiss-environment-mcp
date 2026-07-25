## Finding: SCALE-004 — Containerization mit Multi-Stage-Builds

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `SCALE-004` (Check-Status: partial) |
| **PDF-Reference** | Sec 5.3 |
| **Audit-Datum** | 2026-07-25 |
| **Auditor** | Claude (mcp-audit-Skill, Run 2026-07-25T092248-Z) |

### Observed Behavior

Struktur ist vorbildlich: Multi-Stage mit benannten Stages, Slim-Base, Non-Root-User mit hoher UID, Healthcheck gegen den echten /health-Endpoint. Einzig das Grössen-Kriterium (<200 MB) konnte nicht bestätigt werden und ist gemäss Dependency-Footprint-Messung grenzwertig — daher partial statt pass.

Lücken im Detail:
- Final-Image-Grösse < 200 MB nicht verifizierbar (kein Docker-Daemon im Audit-Container); die Schätzung liegt mit ~210-220 MB unkomprimiert leicht über der Schwelle.

### Expected Behavior

Siehe Pass Criteria in `checks/SCALE-004.md` (Containerization mit Multi-Stage-Builds).

### Evidence

- Dockerfile:2 und Dockerfile:15 — zwei FROM-Statements mit benannten Stages (AS builder / AS runtime); Build-Stage baut Wheel, Runtime-Stage installiert nur das Wheel (Dockerfile:23-24)
- Dockerfile:2,15 — beide Stages auf python:3.12-slim (Slim-Base)
- Dockerfile:20-21,34 — dedizierter Non-Root-User (uid/gid 10001, --no-create-home), USER app vor CMD
- Dockerfile:37-38 — HEALTHCHECK-Direktive (30s-Intervall) gegen /health; Endpoint existiert in src/swiss_environment_mcp/server.py:328-331 und liefert im Runtime-Test HTTP 200
- Grössen-Schätzung (Audit-Lauf, kein Docker-Daemon verfügbar): site-packages der installierten Dependencies = 92 MB + python:3.12-slim-Base ≈ 125 MB → ~210-220 MB unkomprimiert

### Risk Description

Severity medium gemäss Katalog; Profil-Kontext: read-only Public-Open-Data-Server ohne Auth, Single-Instance-Cloud-Deployment. Offen — Behebung gemäss Remediation.

### Remediation

Image-Grösse in CI messen (docker build + docker image inspect als Workflow-Step mit Schwellwert-Gate <200 MB) oder Schwellwert-Abweichung dokumentieren; ggf. Dependencies im Runtime-Stage weiter beschneiden.

### Effort Estimate

S
