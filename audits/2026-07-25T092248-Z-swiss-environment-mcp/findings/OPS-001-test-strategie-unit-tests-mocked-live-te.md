## Finding: OPS-001 — Test-Strategie: Unit-Tests mocked + Live-Tests gemarkert

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `OPS-001` (Check-Status: partial) |
| **PDF-Reference** | Anhang C1 |
| **Audit-Datum** | 2026-07-25 |
| **Auditor** | Claude (mcp-audit-Skill, Run 2026-07-25T092248-Z) |

### Observed Behavior

Die Test-Strategie (mocked/live-Trennung, Marker, CI-Exklusion, nightly Workflow) ist vollständig und der neue LINDAS-Code überdurchschnittlich getestet. Partial wegen der ungemockten Hazard-Tools und verfehlter Per-Tool-Quoten.

Lücken im Detail:
- Quantitatives Kriterium 'mind. 5 Unit-Tests pro Tool' verfehlt (72 gemockte Tests / 18 Tools ≈ 4): env_hazard_overview, env_hazard_regions und env_wildfire_danger haben KEINE gemockten Unit-Tests (nur Live-Tests) — Fehlerpfade dieser drei Tools sind in CI ungetestet
- Kein Live-Test für env_avalanche_bulletin und env_snow_stations als eigenständige Tools (nur indirekt via test_slf_snow)
- tests/test_20_scenarios.py ist ein Standalone-Skript ohne pytest-Testfunktionen (0 collected) und im Docstring veraltet ('Alle 12 Tools')

### Expected Behavior

Siehe Pass Criteria in `checks/OPS-001.md` (Test-Strategie: Unit-Tests mocked + Live-Tests gemarkert).

### Evidence

- tests/test_unit.py (56 Tests) + tests/test_lindas.py (16 Tests) — respx-gemockte Unit-Tests inkl. Happy-/Error-/Edge-Pfaden; der NEUE lindas-Code ist gut abgedeckt (client 400/Timeout/Retry/POST, cube-Dedup/Label-Resolution/Injection-Guard, Bathing-Water happy/not-found/degradation tests/test_lindas.py:51-305)
- tests/test_integration.py:23 — 'pytestmark = pytest.mark.live': 16 Live-Tests decken fast alle Tools inkl. der neuen (test_bathing_water_lindas:177, test_slf_snow:202, test_hunting_stats:224)
- pyproject.toml [tool.pytest.ini_options] — live-Marker registriert ('live: Test trifft echte BAFU-Live-APIs …'); respx als dev-Dependency
- .github/workflows/ci.yml:44-48 — CI läuft 'pytest -m "not live"'; .github/workflows/live-tests.yml — separater nightly-Workflow (cron 0 4 * * *) + workflow_dispatch; Live-Tests brauchen keine Credentials (auth-freie Public-APIs, SEC-013 gegenstandslos)

### Risk Description

Severity high gemäss Katalog; Profil-Kontext: read-only Public-Open-Data-Server ohne Auth, Single-Instance-Cloud-Deployment. Offen — Behebung gemäss Remediation.

### Remediation

Gemockte Unit-Tests für env_hazard_overview, env_hazard_regions, env_wildfire_danger ergänzen (Happy Path + Fehlerpfad), eigene Live-Tests für env_avalanche_bulletin/env_snow_stations, tests/test_20_scenarios.py als pytest-kompatibel refaktorieren oder als Skript deklarieren (Docstring '12 Tools' korrigieren).

### Effort Estimate

M
