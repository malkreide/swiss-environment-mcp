# Security-Architektur — swiss-environment-mcp

Dieses Dokument hält die sicherheitsrelevanten Architektur­entscheide fest. Es
adressiert die Findings SEC-009, SEC-013, SEC-015, SEC-019 und SEC-021 des
MCP-Audits.

## Datenklassifikation & Bedrohungsmodell

- **Datenklasse:** ausschliesslich *Public Open Data* (BAFU/SLF, opendata.swiss).
- **Schreibzugriff:** keiner — alle 12 Tools sind read-only (`readOnlyHint: true`).
- **Auth:** keine. Der Server verarbeitet keine Personendaten und keine Secrets.

Daraus folgt ein bewusst kleines Bedrohungsmodell: Es gibt keine vertraulichen
Daten zu exfiltrieren und keine schreibenden Seiteneffekte. Die relevanten Risiken
sind serverseitig (SSRF, Resource-Exhaustion) und Lieferketten-/Tool-Integrität.

## Lethal Trifecta — Bewertung (SEC-019)

Die «Lethal Trifecta» entsteht, wenn ein Agent gleichzeitig (1) Zugriff auf
private Daten, (2) Exposition gegenüber nicht vertrauenswürdigem Inhalt und
(3) einen ausgehenden Kommunikationskanal hat.

| Fähigkeit | Vorhanden? | Begründung |
|---|---|---|
| Zugriff auf private Daten | **Nein** | Nur öffentliche BAFU-Daten |
| Exposition ggü. untrusted content | Teilweise | Tool-Inputs/LLM, aber kein Datenexfiltrations-Wert |
| Ausgehender Kanal | Eingeschränkt | Nur fixe Gov-Hosts (Egress-Allow-List), read-only |

**Ergebnis:** Der Server hat **maximal eine** der drei Trifecta-Fähigkeiten in
schädlicher Ausprägung. Es existiert kein exfiltrierbarer Kanal: ausgehende
Requests gehen ausschliesslich an eine feste Allow-List (`ALLOWED_HOSTS` in
`api_client.py`, SEC-021), `follow_redirects=False`, und es werden keine
Empfänger-/Webhook-Ziele aus User-Input gebildet. Eine Eskalation Richtung
Trifecta würde erst entstehen, wenn schreibende Tools oder eine
Send-/Mail-Fähigkeit ergänzt würden — siehe Roadmap-Phasenübergänge.

## Secret-Management (SEC-013)

Der Server benötigt **keine** Secrets/API-Keys (Public Open Data). Damit gilt
Reifegrad-Stufe 1 (keine Geheimnisse) als ausreichend und bewusst gewählt:

- Keine Hardcoded Secrets im Code (CI-Scan via `gitleaks`, ARCH-005).
- Konfiguration ausschliesslich über nicht-geheime Env-Vars
  (`MCP_TRANSPORT`, `MCP_HOST`, `PORT`), dokumentiert in `.env.example`.
- Container-Image enthält keine Secrets in Layern.

**Falls künftig ein authentifizierter Upstream hinzukommt:** auf Stufe 3
(Secret-Manager, EU/CH-Region) wechseln und `SecretStr` für die
In-Memory-Repräsentation verwenden.

## Session-Modell (SEC-009)

Da kein Auth-Modell existiert, gibt es kein anwendungsseitiges
User-zu-Session-Binding. Im HTTP-Transport verwaltet FastMCP die
`Mcp-Session-Id` selbst. Es werden keine benutzerbezogenen Sessions über
Requests hinweg persistiert und keine sensiblen Daten an eine Session gebunden.

**Bei künftiger Einführung von OAuth/OIDC** ist Folgendes verbindlich:
kryptografisch zufällige Session-IDs, Bindung an den validierten `sub`-Claim,
explizite TTL und serverseitige Invalidierung bei Logout.

## Tool-Poisoning / Gateway (SEC-015)

Der Server läuft als eigenständiger, read-only Public-Data-Server **ohne**
vorgelagertes MCP-Gateway. Eine Pre-Flight-Tool-Poisoning-Detection ist daher
nicht implementiert und für dieses Profil nicht erforderlich. Die Tool-Integrität
wird stattdessen über den **Tool-Definition-Snapshot** (`tool-snapshot.json`,
SEC-022, CI-Gate) gegen unbemerkte Änderungen («Rug Pull») abgesichert.

Sollte der Server in einem Enterprise-Kontext hinter ein Gateway gestellt
werden, ist dort Tool-Allow-Listing (default-deny) und Prompt-Injection-Filtering
zu ergänzen.

## Egress-Kontrolle (SEC-021)

- **Code-Layer:** `ALLOWED_HOSTS` (frozenset) in `api_client.py`;
  `assert_host_allowed()` läuft vor jedem ausgehenden Request (HTTPS-Zwang,
  Host-Whitelist, IP-Blocklist gegen private/loopback/link-local).
- **Network-Layer (empfohlen für Cloud):** zusätzlich eine NetworkPolicy /
  Security-Group, die ausgehenden Traffic auf die BAFU-/opendata.swiss-Hosts
  beschränkt. DNS-Auflösung für diese Hosts muss erlaubt bleiben.
