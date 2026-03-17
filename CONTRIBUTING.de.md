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
