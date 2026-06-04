# Sicherheitsrichtlinie & Sicherheitslage

[🇬🇧 English Version](SECURITY.md)

`swiss-environment-mcp` wurde gegen den internen MCP-Best-Practice-Audit-Katalog
gehärtet. Dieses Dokument fasst die Sicherheitslage zusammen und dokumentiert die
**akzeptierten Risiken** für Kontrollen, die bewusst auf der Portfolio-/Gateway-Ebene
statt innerhalb dieses einzelnen Servers behandelt werden.

## Schwachstelle melden

Bitte eröffnen Sie ein privates Security Advisory im GitHub-Repository oder
kontaktieren Sie die in `README.md` genannte verantwortliche Person. Erstellen Sie
für ausnutzbare Schwachstellen **keine** öffentlichen Issues.

## Zusammenfassung der Sicherheitslage

Dies ist ein **rein lesender**, **PII-freier** MCP-Server für **öffentliche Open
Data**. Alle 12 Tools fragen ausschliesslich offizielle Schweizer
Bundesumweltdatenquellen (BAFU/SLF und opendata.swiss) ab. Bereits umgesetzte
Härtungsmassnahmen:

| Bereich | Kontrolle |
|---|---|
| Egress | HTTPS-erzwungene Allow-List ausschliesslich für feste BAFU-/SLF-/opendata.swiss-Hosts (`ALLOWED_HOSTS` in `api_client.py`, SEC-021) |
| TLS | Verifizierung standardmässig aktiv; DNS-Pinning schliesst das Rebinding-/TOCTOU-Fenster (SEC-005) |
| Binding | Netzwerk-Transporte binden standardmässig an `127.0.0.1` (SEC-016) |
| Transport | Streamable HTTP mit CORS, das nur `Mcp-Session-Id` exponiert (SDK-004) |
| Input | Pydantic-v2-Strict-Validierung an allen Tool-Grenzen (SEC-018) |
| Secrets | Keine erforderlich — nur nicht-geheime Umgebungsvariablen, `.gitignore` schützt `.env`, keine hartcodierten Secrets (ARCH-005/SEC-013) |
| Fehler | Upstream-Antworten werden nach stderr geloggt, niemals an das Modell weitergegeben (OBS-002) |
| Stdout | Reserviert für den JSON-RPC-Stream; Logging fest auf stderr (OBS-004) |
| Tool-Integrität | Tool-Definition-Snapshot (`tool-snapshot.json`) in CI gegen Veränderung / Rug-Pulls verifiziert (SEC-022) |

Die vollständige Sicherheitsarchitektur (Datenklassifikation,
Lethal-Trifecta-Bewertung, Secret-Management, Session-Modell, Egress-Kontrolle)
finden Sie unter [`docs/security.md`](docs/security.md), die zugrunde liegenden
Audit-Berichte unter `audits/` und die Härtungshistorie in `CHANGELOG.md`.

## Akzeptierte Risiken (Kontrollen auf Portfolio-Ebene)

Die folgenden Audit-Prüfungen sind **bewusst nicht** innerhalb dieses Servers
implementiert. Es handelt sich um portfolioweite Belange, die am besten auf einer
MCP-Gateway-/Host-Ebene durchgesetzt werden; das Restrisiko ist hier gering, da der
Server rein lesend ist und nur eine feste Menge vertrauenswürdiger
Open-Data-Anbieter erreicht.

### SEC-014 — Tool-Allow-Listing über ein MCP-Gateway

**Status:** akzeptiertes Risiko (Portfolio-Ebene).
Eine Allow-List pro Tool gehört zum MCP-Host/-Gateway, das mehrere Server aggregiert,
nicht zu einem einzelnen Server, der ein festes, rein lesendes Tool-Set exponiert.
Sobald ein zentrales Gateway für das Portfolio eingeführt wird, sollte das
Tool-Allow-Listing dort konfiguriert werden. Bis dahin ist das Risiko begrenzt: Jedes
Tool ist rein lesend und durch die oben genannte Egress-Allow-List eingeschränkt.

### SEC-015 — Pre-Flight-Erkennung von Tool-Poisoning

**Status:** akzeptiertes Risiko (Portfolio-Ebene) — mit lokaler Schutzmassnahme.
Tool-Poisoning (bösartige Tool-Beschreibungen / Rug-Pulls) ist ein Lieferketten- und
Host-seitiges Problem. Die Tool-Definitionen dieses Servers sind versionskontrolliert
und werden aus diesem Repository ausgeliefert; es gibt keine dynamische/entfernte
Tool-Registrierung. Lokal erkennt **SEC-022 Tool-Definition-Snapshotting**
(`tool-snapshot.json`) jegliche Veränderung der Tool-Oberfläche in CI. Die
serverübergreifende Poisoning-Erkennung bleibt eine Gateway-/Host-Verantwortung, die
auf Portfolio-Ebene verfolgt wird.

## Re-Evaluierungs-Auslöser

Diese Akzeptanzen sollten neu bewertet werden, falls der Server jemals:

- **Schreib**-Funktionalität erhält oder beginnt, **PII** zu verarbeiten, oder
- Tools **dynamisch** / aus entfernten Quellen registriert, oder
- hinter einem gemeinsamen MCP-Gateway aggregiert wird (dann SEC-014/015 dort umsetzen).
