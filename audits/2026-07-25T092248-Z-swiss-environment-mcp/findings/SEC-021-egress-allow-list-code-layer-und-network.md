## Finding: SEC-021 — Egress-Allow-List: Code-Layer und Network-Layer

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `SEC-021` (Check-Status: partial) |
| **PDF-Reference** | Anhang B5 + B12 |
| **Audit-Datum** | 2026-07-25 |
| **Auditor** | Claude (mcp-audit-Skill, Run 2026-07-25T092248-Z) |

### Observed Behavior

Der Code-Layer ist vorbildlich und deckt auch die neuen LINDAS-/SLF-/Jagd-Hosts ab, aber der vom Check explizit verlangte zweite (Network-)Layer existiert nur als Prosa-Empfehlung; bei striktem Massstab 4 von 6 Pass-Kriterien erfüllt → partial trotz 4 gesammelter Evidenzpunkte.

Lücken im Detail:
- Network-Layer Egress Control ist nur als Empfehlung dokumentiert ('empfohlen für Cloud', docs/security.md:79-81) — kein deploybares Policy-Artefakt (keine NetworkPolicy/Security-Group in render.yaml, docker-compose.yml oder Dockerfile)
- Kein dokumentiertes Update-Verfahren für Allow-List-Erweiterungen (PR-Review + CHANGELOG-Pflicht) in docs/ oder CONTRIBUTING

### Expected Behavior

Siehe Pass Criteria in `checks/SEC-021.md` (Egress-Allow-List: Code-Layer und Network-Layer).

### Evidence

- Code-Layer Allow-List als nicht-mutierbares frozenset mit 10 explizit benannten Gov-/SLF-Hosts (src/swiss_environment_mcp/api_client.py:82-97)
- Pre-Request-Check assert_host_allowed (HTTPS-Zwang + Host-Whitelist + IP-Blocklist) vor jedem ausgehenden Request: _get_json (api_client.py:217-221), _get_json_retry (api_client.py:524-538), LINDAS-Pfad via egress_check-Injection (api_client.py:271-278, lindas/client.py:113-114)
- Defense-in-Depth im Code: DNS-Pinning-Transport ohne TOCTOU-Fenster + Blocklist privater/loopback/link-local IPs (api_client.py:111-175), follow_redirects=False (api_client.py:192)
- Dokumentation der Egress-Policy inkl. DNS-Hinweis in docs/security.md:74-81; Allow-List-Hosts im Modul-Header benannt (api_client.py:11-15)

### Risk Description

Severity high gemäss Katalog; Profil-Kontext: read-only Public-Open-Data-Server ohne Auth, Single-Instance-Cloud-Deployment. Offen — Behebung gemäss Remediation.

### Remediation

Network-Layer-Egress als deploybares Artefakt ergänzen (z.B. auskommentierte NetworkPolicy/egress-Rules in docker-compose.yml oder Render-Doku) und in CONTRIBUTING.md ein Update-Verfahren für ALLOWED_HOSTS-Erweiterungen (PR-Review + CHANGELOG-Pflicht) festschreiben.

### Effort Estimate

S
