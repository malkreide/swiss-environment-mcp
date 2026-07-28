# Beitragen zu swiss-environment-mcp

Danke für dein Interesse, zu diesem Projekt beizutragen! Dieser MCP-Server ist Teil des [Swiss Public Data MCP Portfolios](https://github.com/malkreide) und folgt den gemeinsamen Konventionen des Portfolios.

[🇬🇧 English Version](CONTRIBUTING.md)

---

## Inhaltsverzeichnis

- [Fehler melden](#fehler-melden)
- [Entwicklungsumgebung einrichten](#entwicklungsumgebung-einrichten)
- [Änderungen vornehmen](#änderungen-vornehmen)
- [Code-Stil](#code-stil)
- [Tests](#tests)
- [Pull Request einreichen](#pull-request-einreichen)
- [Releases](#releases)
- [Datenquellen & Quellenangabe](#datenquellen--quellenangabe)

---

## Fehler melden

Bitte prüfe vor dem Öffnen eines Issues die [bestehenden Issues](https://github.com/malkreide/swiss-environment-mcp/issues), um Duplikate zu vermeiden.

Beim Melden eines Fehlers bitte angeben:

- Eine klare Beschreibung des Problems
- Schritte zur Reproduktion
- Erwartetes vs. tatsächliches Verhalten
- Python-Version und Betriebssystem
- Relevante Fehlermeldungen oder Logs

Bei API-bezogenen Problemen (z. B. Endpunkt-Änderungen bei hydrodaten.admin.ch oder naturgefahren.ch) ist zu beachten, dass dieser Server von externen BAFU-Datenquellen abhängt, die sich ohne Vorankündigung ändern können.

---

## Entwicklungsumgebung einrichten

```bash
# 1. Repository klonen
git clone https://github.com/malkreide/swiss-environment-mcp.git
cd swiss-environment-mcp

# 2. Im bearbeitbaren Modus mit Dev-Abhängigkeiten installieren
pip install -e ".[dev]"

# 3. Serverstart überprüfen
python -m swiss_environment_mcp.server
```

**Voraussetzungen:**
- Python 3.11+
- Keine API-Keys erforderlich – alle Datenquellen sind öffentlich zugänglich

---

## Änderungen vornehmen

1. **Fork** des Repositories erstellen und einen Feature-Branch anlegen:
   ```bash
   git checkout -b feat/dein-feature-name
   ```

2. Format für [Conventional Commits](https://www.conventionalcommits.org/) einhalten:

   | Typ | Verwendung |
   |---|---|
   | `feat` | Neues Tool oder neue Funktionalität |
   | `fix` | Fehlerbehebung |
   | `docs` | Nur Dokumentation |
   | `refactor` | Code-Umstrukturierung ohne Verhaltensänderung |
   | `test` | Tests hinzufügen oder aktualisieren |
   | `chore` | Build, Abhängigkeiten, CI |

3. `CHANGELOG.md` unter `[Unreleased]` für jede benutzerseitig sichtbare Änderung aktualisieren.

4. Bei einem neuen Tool müssen sowohl `README.md` (Englisch) als auch `README.de.md` (Deutsch) aktualisiert werden.

---

## Code-Stil

Dieses Projekt verwendet [Ruff](https://docs.astral.sh/ruff/) für Linting und Formatierung.

```bash
# Auf Linting-Probleme prüfen
ruff check src/

# Wo möglich automatisch beheben
ruff check src/ --fix

# Code formatieren
ruff format src/
```

Die CI-Pipeline führt Ruff bei jedem Push aus – PRs mit Linting-Fehlern werden nicht gemergt.

**Allgemeine Konventionen:**
- Type Hints für alle öffentlichen Funktionen
- Pydantic v2 für Datenvalidierung
- `httpx` für asynchrone HTTP-Aufrufe
- Aussagekräftige Tool-Beschreibungen (sie werden vom KI-Modell gelesen)

---

## Tests

```bash
# Nur Unit-Tests (kein Netzwerk erforderlich)
PYTHONPATH=src pytest tests/ -m "not live"

# Integrationstests (erfordern live BAFU-APIs)
PYTHONPATH=src pytest tests/ -m "live"

# Vollständige Testsuite
PYTHONPATH=src pytest tests/
```

Tests werden mit `@pytest.mark.live` markiert, wenn sie externe APIs aufrufen. Die CI-Pipeline führt nur Nicht-Live-Tests aus, um Instabilität durch externe Abhängigkeiten zu vermeiden.

Bei einem neuen Tool bitte mindestens einen Unit-Test und einen Live-Integrationstest hinzufügen.

---

## Pull Request einreichen

1. Sicherstellen, dass alle Tests bestehen und Ruff keine Fehler meldet
2. `CHANGELOG.md` aktualisieren
3. Branch pushen und Pull Request gegen `main` öffnen
4. Beschreiben, was geändert wurde und warum – verwandte Issues verlinken

PRs, die Breaking Changes an bestehenden Tool-Signaturen einführen, erfordern zuerst eine Diskussion.

---

## Sicherheitsrelevante Änderungen

Zwei Arten von Änderungen betreffen das Sicherheitsprofil des Servers und folgen
einem strengeren Verfahren (kein Self-Merge):

**Egress-Allow-List erweitern (`ALLOWED_HOSTS`, SEC-021).** Ein neuer Host
vergrössert die Angriffsfläche. Ein PR, der `ALLOWED_HOSTS` in
`src/swiss_environment_mcp/api_client.py` ändert, muss: (1) den neuen Host
begründen (Datenquelle, Endpoint, Lizenz); (2) die FQDN-Liste in
`deploy/network-policy.example.yaml` im selben PR nachziehen; (3) einen
CHANGELOG-Eintrag unter *Sicherheit* enthalten; (4) von einer zweiten Person
reviewt werden.

**Tool-Definitionen ändern (SEC-022).** Tool-Name, Beschreibung und
Input-Schema sind über `tool-snapshot.json` gepinnt (CI-Gate). Bei einer
Änderung den Snapshot neu erzeugen (`PYTHONPATH=src python
scripts/tool_snapshot.py`) und einen CHANGELOG-Eintrag ergänzen. Ist die
Änderung breaking für Clients, einen expliziten **Client-Re-Approval-Hinweis**
in den CHANGELOG aufnehmen (der Snapshot-Hash wechselt; Downstreams, die
Tool-Definitionen pinnen, müssen neu zustimmen). Das `env_`-Tool-Präfix ist eine
bewusste, stabile Namespace-Wahl — siehe README.

## Releases

Releases entstehen aus `CHANGELOG.md`. Den mechanischen Teil erledigt der
Workflow **Draft Release** (`.github/workflows/draft-release.yml`): im
Actions-Tab manuell starten (`workflow_dispatch`), optional mit einer Version;
ohne Eingabe wird die Version aus `pyproject.toml` genommen.

Der Workflow

1. prüft die Version gegen `pyproject.toml` und bricht bei Abweichung ab — ein
   Tag, der nicht zur paketierten Version passt, schöbe ein falsch nummeriertes
   Artefakt nach PyPI;
2. bricht ab, wenn Tag oder Release bereits existieren;
3. extrahiert den Abschnitt `## [<version>]` aus `CHANGELOG.md` (Abbruch, wenn
   keiner existiert) und legt ein **Draft**-Release auf dem Commit an, auf dem
   er lief.

**Der Entwurf wird bewusst nicht automatisch veröffentlicht.** GitHub legt den
Tag erst beim Veröffentlichen an — ein Entwurf ist also folgenlos und jederzeit
löschbar. Das Veröffentlichen startet `publish.yml`
(`on: release: [published]`) → **PyPI** und **MCP Registry**, und eine
PyPI-Version lässt sich nie erneut hochladen. Dieser letzte, unumkehrbare
Schritt bleibt ein bewusster Klick eines Menschen im Release-UI.

`publish.yml` synchronisiert `server.json` beim Veröffentlichen aus dem
Tag-Namen — die committete Version erreicht das publizierte Artefakt also nie.
Genau deshalb driftete sie unbemerkt von v0.2.3 bis v0.5.0: funktional
folgenlos, beim Lesen aber irreführend. **`pyproject.toml` und `server.json`
im selben Commit bumpen**; die CI erzwingt das:

```bash
python scripts/check_version_sync.py
```

Der Check läuft im `lint`-Job und vergleicht `pyproject.toml` mit
`server.json → version` **und** jedem `packages[*].version`.

---

## Datenquellen & Quellenangabe

Dieser Server verwendet offene Daten von Schweizer Bundesbehörden:

| Quelle | Anbieter | Nutzungsbedingungen |
|---|---|---|
| [hydrodaten.admin.ch](https://hydrodaten.admin.ch) | BAFU | OGD, Quellenangabe erforderlich |
| [naturgefahren.ch](https://naturgefahren.ch) | SLF / BAFU | OGD, Quellenangabe erforderlich |
| [waldbrandgefahr.ch](https://waldbrandgefahr.ch) | BAFU | OGD, Quellenangabe erforderlich |
| [opendata.swiss](https://opendata.swiss/de/organization/bafu) | BAFU via CKAN | OGD |

**Die Quellenangabe des BAFU ist Pflicht**, wenn Daten über diesen Server verwendet oder weitergegeben werden. Beiträge, die weitere Datenquellen einbinden, müssen deren Lizenz- und Quellenangabepflichten hier dokumentieren.

---

## Portfolio-Kontext

Dieser Server ist Teil eines kohärenten Portfolios von Schweizer Open-Data-MCP-Servern. Beim Beitragen bitte beachten:

- **No-Auth-First**: Endpunkte ohne Authentifizierung bevorzugen
- **Graceful Degradation**: Der Server soll auch dann starten und Teilfunktionalität bieten, wenn einzelne APIs nicht erreichbar sind
- **Bilinguale Dokumentation**: Benutzerseitige Dokumentationsänderungen müssen in `README.md` (Englisch) und `README.de.md` (Deutsch) übernommen werden

---

Fragen? Ein [GitHub Discussion](https://github.com/malkreide/swiss-environment-mcp/discussions) eröffnen oder ein Issue erstellen.
