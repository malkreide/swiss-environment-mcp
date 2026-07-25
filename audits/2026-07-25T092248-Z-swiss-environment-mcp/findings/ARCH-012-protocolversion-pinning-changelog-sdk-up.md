## Finding: ARCH-012 — protocolVersion-Pinning + CHANGELOG + SDK-Update-Disziplin

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `ARCH-012` (Check-Status: partial) |
| **PDF-Reference** | Anhang A9 |
| **Audit-Datum** | 2026-07-25 |
| **Auditor** | Claude (mcp-audit-Skill, Run 2026-07-25T092248-Z) |

### Observed Behavior

CHANGELOG-Disziplin, README-Policy-Sektion und Dependabot sind vorbildlich; das Kernkriterium — explizites protocolVersion-Pinning im Code statt SDK-Default — ist jedoch nicht erfüllt. 4 von 6 Kriterien erfüllt → partial.

Lücken im Detail:
- protocolVersion ist im Server-Code nicht explizit gepinnt — FastMCP wird ohne Versions-Pin instanziiert (server.py:310-322); der SDK-Major-Pin ist nur ein indirekter Proxy, ein Minor-Update des SDK kann die ausgehandelte Spec-Version still ändern
- CHANGELOG-Einträge nennen keine expliziten Spec-Version-Bumps (nur SDK-Pin-Erwähnung) — Audit-Trail-Lücke bei künftigen Protokollwechseln

### Expected Behavior

Siehe Pass Criteria in `checks/ARCH-012.md` (protocolVersion-Pinning + CHANGELOG + SDK-Update-Disziplin).

### Evidence

- pyproject.toml:21-24 — SDK-Major-Pin 'mcp[cli]>=1.28.1,<2' mit explizitem ARCH-012-Kommentar ('legt die ausgehandelte MCP-Protokoll-Version fest'); aber KEIN explizites protocolVersion-Pinning im Server-Code (grep protocolVersion/protocol_version in src/ = 0 Treffer)
- CHANGELOG.md — vorhanden, Keep-a-Changelog-Format mit datierten Releases ([0.3.0] – 2026-07-25, Sektionen Neu/Architektur/Refactor/Behoben); CHANGELOG.md:167 dokumentiert den SDK-Pin
- README.md:295-304 — Sektion 'MCP Protocol Version & Maintenance' mit Update-Policy (Dependabot monatlich, semver-Bump bei Tool-/Verhaltensänderung, Tool-Snapshot-Gate SEC-022)
- .github/dependabot.yml — monatliche Update-PRs für pip UND github-actions aktiv

### Risk Description

Severity medium gemäss Katalog; Profil-Kontext: read-only Public-Open-Data-Server ohne Auth, Single-Instance-Cloud-Deployment. Offen — Behebung gemäss Remediation.

### Remediation

Ausgehandelte protocolVersion beim Start loggen und im CHANGELOG bei SDK-Bumps den resultierenden Spec-Stand notieren; optional Pin über FastMCP-Konfiguration, sobald das SDK das erststellt.

### Effort Estimate

S
