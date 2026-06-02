## Finding: ARCH-011 — Standardisierte Repo-Struktur (src-Layout, tests, README.de.md)

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status (Check)** | ⚠️ PARTIAL |
| **Status (Finding)** | open |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `ARCH-011` |
| **PDF-Reference** | Anhang A8 |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |

### Kontext (Check-Description)

Aus dem Schweizer Public-Data-Portfolio bewährt sich ein konsistentes Repo-Layout.

### Observed Behavior

Belege aus Code/Konfiguration des auditierten Servers:

- README.md, README.de.md, CHANGELOG.md, LICENSE, pyproject.toml vorhanden
- src-Layout korrekt, tests/, .github/workflows/ (ci.yml + publish.yml)
- README.de.md parallel zu README.md

### Gaps gegenüber Pass-Criteria

- Bei 12 Tools (>5) kein tools/-Verzeichnis mit Datei-pro-Gruppe — alles in einer server.py (1320 Zeilen)

### Remediation (aus Katalog-Check ARCH-011)

### Schritt 1: Migration zu src-Layout (falls flat)

```bash
mkdir -p src
git mv my_module src/my_module
# pyproject.toml anpassen:
# [tool.hatch.build.targets.wheel]
# packages = ["src/my_module"]
```

### Schritt 2: README.de.md initial befüllen

Wenn nur `README.md` existiert, mit Übersetzung beginnen — mindestens Top-Level-Sektionen synchron halten.

### Schritt 3: CI-Workflows aufsetzen

`.github/workflows/test.yml`:

```yaml
name: Tests
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - uses: actions/setup-python@v6
        with:
          python-version: "3.11"
      - run: pip install -e ".[dev]"
      - run: pytest -m "not live"
```

### Schritt 4: Tools aufteilen

Bei > 5 Tools:

```diff
  src/server_name/
+ ├── tools/
+ │   ├── __init__.py
+ │   ├── search.py        # search_motions, search_authors
+ │   ├── statistics.py    # aggregate_*, count_*
+ │   └── notifications.py # send_*
- └── server.py            # vorher 800 Zeilen
+ └── server.py            # nur Registry, ~100 Zeilen
```

### Effort Estimate

S — < 1 Tag bei einzelnem Server. M — 1 Woche bei portfolio-weitem Roll-out (29 Server).

### Verification After Fix

- Re-Audit von `ARCH-011` mit `mcp-audit-skill` (gleicher catalog_hash)
- Ziel-Status: `pass`
