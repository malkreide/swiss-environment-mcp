# CLAUDE.md

## Teil 1 — Konventionen (portfolio-weit)

### Vor der Arbeit

Klon-Aktualität prüfen: `git fetch origin main && git rev-list --count HEAD..origin/main`
Ein veralteter Klon erzeugt eine rote CI, deren Ursache nicht im Diff steht.
Am 3.8.2026 zweimal passiert — beide Male fehlten genau die Commits, die
das Gate einführten, an dem der Branch scheiterte.

Gates lokal fahren, mit der GEPINNTEN ruff-Version aus der CI. Eine andere
Version meldet Abweichungen, die niemand verursacht hat.

### Tests

Gegenprobe ist Pflicht. Ein Test, der grün bleibt, wenn man die
Implementierung entfernt, prüft nichts. Jede neue Zusicherung einzeln
neutralisieren und zeigen, dass genau die zugehörigen Tests fallen.

Zwei Fallen, die beide grün blieben:

- Eine Fake-Uhr, die nur beim Schlafen vorrückt, kann eine Zusicherung über
  echte Zeit nicht widerlegen.
- `monkeypatch.setattr(modul.asyncio, "sleep", ...)` greift ins Modul
  `asyncio` selbst und entschärft die Mechanik im ganzen Prozess. Patche
  einen Modul-Alias (`_sleep = asyncio.sleep`), nicht das fremde Modul.

Handgeschriebene Fixtures kodieren die Annahme des Autors und können sie
nicht widerlegen. Mindestens eine aufgezeichnete Antwort pro externem
Endpunkt, mit Aufnahmedatum.

### Wenn etwas rot ist

Roter Live-Test: erst die Quelle abfragen, dann einordnen. Nicht aus der
Fehlermeldung schliessen. Am 3.8.2026 hiess "nicht gefunden" nicht, dass der
Datensatz weg war, sondern dass die Quelle die Schreibweise ihrer Kopfzeile
gewechselt hatte — vier von sechs Datensätzen produktiv kaputt, alle
Unit-Tests grün.

PR ohne jeden Check ist selten ein Repo ohne CI, meistens ein
Merge-Konflikt: GitHub berechnet dafür keinen Merge-Commit und startet nichts.

Ein Codex-Review auf einem PR wird beantwortet oder behoben, nie ignoriert.

## Teil 2 — dieses Repo

**ruff:** genau eine Quelle — `ruff==0.16.1` im `[dev]`-Extra von
`pyproject.toml`. Ein Install des Extras reicht also, lokal wie in der CI.
Keine zweite Version in die Workflows schreiben: ein solcher Schritt läuft
nach dem Install und überstimmt den Pin still — er stand hier an zwei Stellen,
in den Jobs `test` und `lint` (`test_dependencies.py` hält beides fest). Eine
`.pre-commit-config.yaml` gibt es nicht. Vor dem Lauf `ruff --version` prüfen:
ein älteres ruff früher im `PATH` schlägt den Pin, ohne etwas zu melden.

**Gates, wörtlich aus der CI** (Job `test`, dazu `lint` mit denselben zwei
ruff-Schritten plus dem Versions-Sync):

```bash
ruff check src/ tests/ scripts/
ruff format --check src/ tests/ scripts/
python -m py_compile src/swiss_environment_mcp/server.py src/swiss_environment_mcp/api_client.py
python -c "from swiss_environment_mcp.server import mcp; print('Import OK')"
python scripts/tool_snapshot.py check     # PYTHONPATH=src
pytest -m "not live" -v                   # PYTHONPATH=src
python scripts/check_version_sync.py
```

**Zwei weitere Gates hängen an jedem PR, ausserhalb von `ci.yml`:**

- `security.yml` — gitleaks über History *und* Working Tree, Konfig
  `.gitleaks.toml`. Läuft immer.
- `image-size.yml` — baut das Image und bricht über einem Ceiling von
  **350 MB** ab (Audit SCALE-004). Läuft **nur**, wenn `Dockerfile`,
  `pyproject.toml` oder `src/**` im Diff sind.

Der Pfadfilter ist die Falle: Auf einem reinen Doku-PR fehlt dieser Check in
der Liste, und das ist der Normalfall, nicht das Symptom aus Teil 1. Erst
wenn *gar kein* Check läuft, gilt dort der Merge-Konflikt-Verdacht. Beide
brauchen Docker bzw. gitleaks und sind damit die zwei Gates, die sich nicht
so nebenbei lokal nachfahren lassen.

`draft-release.yml` ist kein Gate — nur `workflow_dispatch`.

Die Matrix setzt kein `fail-fast: false`: Eine rote 3.11 bricht 3.12 und 3.13
ab, bevor sie etwas sagen.

Es gibt kein Coverage-Gate. Kein `include` unter `[tool.ruff]` setzen — der
Umfang stimmt: `ruff check` sieht 26 Dateien über alle drei Verzeichnisse,
`ruff format` 27, weil 0.16 auch Markdown formatiert und damit
`tests/fixtures/PROVENANCE.md` mitnimmt. Zwei Zahlen, kein Fehler.

**Fixtures: vorhanden, 20 Stück plus `tests/fixtures/PROVENANCE.md`** mit
Aufnahmedatum und dem Grund für den Schnitt — eine Antwort je *Abfrage*, nicht
je Endpunkt, weil fast alles über denselben SPARQL-Endpunkt läuft. Neu
aufzeichnen mit `PYTHONPATH=src python scripts/record_fixtures.py`.

**Live-Tests:** `.github/workflows/live-tests.yml`, nächtlich per Cron
(`0 4 * * *`) plus `workflow_dispatch`. Sie sind hier also nicht bloss per
`-m "not live"` ausgeschlossen. Der Lauf wird nicht am Exit-Code gemessen,
sondern von `scripts/classify_live_run.py` in `clear` / `finding` / `unknown`
eingeordnet — ein Lauf, in dem alles übersprungen wurde, gilt nicht als
Erfolg, und nur ein `finding` öffnet ein Issue. `unknown` schliesst keines.
