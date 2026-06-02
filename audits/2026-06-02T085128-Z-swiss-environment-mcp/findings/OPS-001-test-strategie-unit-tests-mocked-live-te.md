## Finding: OPS-001 — Test-Strategie: Unit-Tests mocked + Live-Tests gemarkert

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status (Check)** | ❌ FAIL |
| **Status (Finding)** | open |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `OPS-001` |
| **PDF-Reference** | Anhang C1 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |

### Kontext (Check-Description)

Aus dem Sormena-Pattern bewährt: zwei Test-Kategorien mit klarer Trennung.

| Kategorie | Zweck | Wann ausgeführt | Mock | Speed |
|---|---|---|---|---|
| **Unit-Tests** | Server-Logik isoliert prüfen | CI bei jedem PR | respx-mocked HTTP | ~1s pro Test |
| **Live-Tests** | Echte API-Antworten gegen aktuelle Schnittstellen prüfen | Manuell, nightly, vor Release | keiner | 5-30s pro Test |

Die Trennung ist nicht akademisch — sie löst drei reale Probleme:

1. **CI-Stabilität:** Live-Tests scheitern bei API-Outages der Datenquelle (z.B. opendata.swiss-Wartung).

### Observed Behavior

Belege aus Code/Konfiguration des auditierten Servers:

- tests/test_integration.py und tests/test_20_scenarios.py vorhanden, decken alle 12 Tools + Edge-Cases ab

### Gaps gegenüber Pass-Criteria

- Kein HTTP-Mocking (kein respx) — Tests treffen LIVE-BAFU-APIs (flaky, netzabhängig)
- Keine @pytest.mark.live-Marker, nicht in pyproject registriert
- CI führt test_integration.py gegen Live-APIs aus statt 'pytest -m "not live"'
- Keine getrennte tests/test_unit.py (mocked) vs. test_live.py

### Remediation (aus Katalog-Check OPS-001)

### Schritt 1: pyproject.toml-Marker registrieren

```toml
[tool.pytest.ini_options]
markers = [
    "live: tests against real APIs (manual, nightly only)",
]
```

### Schritt 2: respx als Dev-Dependency

```toml
[project.optional-dependencies]
dev = [
    "pytest >= 7.4",
    "pytest-asyncio >= 0.21",
    "pytest-cov >= 4.1",
    "respx >= 0.20",
]
```

### Schritt 3: Unit-Test-Suite aufbauen

Pro Tool mindestens drei Tests:
- Happy-Path (200, expected schema)
- Error-Path (4xx/5xx)
- Edge-Case (leere Antwort, malformed input)

### Schritt 4: CI-Workflow updaten

`.github/workflows/test.yml`:

```yaml
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - uses: actions/setup-python@v6
        with:
          python-version: "3.11"
      - run: pip install -e ".[dev]"
      - run: pytest -m "not live" --cov=src
```

### Schritt 5: Nightly-Live-Workflow

Wie im Pass-Pattern Modus 4.

### Effort Estimate

M — 1–3 Tage Initial-Setup. Tests-Schreiben skaliert mit Tool-Anzahl.

### Verification After Fix

- Re-Audit von `OPS-001` mit `mcp-audit-skill` (gleicher catalog_hash)
- Ziel-Status: `pass`
