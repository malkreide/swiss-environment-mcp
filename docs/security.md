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

## Tool-Allow-Listing / Gateway (SEC-014)

Der Server hat **kein Auth-Modell** und exponiert ausschliesslich read-only
Public-Data-Tools; `tools/list` ist für alle Clients identisch. Ein rollen-/
teambasiertes Tool-Allow-Listing (default-deny) und die Auditierung
abgelehnter Tool-Aufrufe sind daher **nicht** implementiert — für dieses Profil
eine bewusste, dokumentierte Risiko-Akzeptanz.

**Re-Evaluations-Trigger (verbindlich):** Sobald (a) ein Auth-Modell eingeführt
wird, (b) write-fähige Tools hinzukommen oder (c) der Server in einem
Enterprise-/Multi-Tenant-Kontext betrieben wird, ist ein vorgelagertes
MCP-Gateway mit Tool-Allow-List pro Rolle und 403-Auditierung zwingend
nachzurüsten.

## Tool-Poisoning-Detection (SEC-015)

Der Server läuft eigenständig **ohne** vorgelagertes MCP-Gateway und aggregiert
**keine fremden Tool-Definitionen** — die einzige Tool-Quelle ist dieser Server
selbst. Eine Pre-Flight-Tool-Poisoning-Detection ist daher nicht implementiert.
Die Integrität der eigenen Tool-Definitionen wird über den
**Tool-Definition-Snapshot** (`tool-snapshot.json`, SEC-022, CI-Gate) gegen
unbemerkte Änderungen («Rug Pull») abgesichert.

**Was ein Gateway-Deployment ergänzen müsste** — die vier Detektions-Muster­klassen
des Katalogs, sobald fremde Tool-Definitionen ins Spiel kommen:

1. eingebettete System-Prompts / Instruktionen in Tool-Descriptions,
2. Override-/Jailbreak-Phrasen («ignore previous instructions» u. ä.),
3. unsichtbare Steuerzeichen (Zero-Width, Bidi-Overrides),
4. Homoglyphen / Look-alike-Unicode in Namen und Beschreibungen.

**Re-Evaluations-Trigger:** Sobald der Server hinter ein Gateway gestellt wird
oder Tools Dritter mountet, sind diese vier Muster als default-deny-Filter mit
SIEM-Alerting zu implementieren und gegen Standard-Angriffsmuster zu testen.

## Egress-Kontrolle (SEC-021)

- **Code-Layer (immer aktiv):** `ALLOWED_HOSTS` (frozenset) in `api_client.py`;
  `assert_host_allowed()` läuft vor jedem ausgehenden Request (HTTPS-Zwang,
  Host-Whitelist). Die DNS-Auflösung + IP-Blocklist (private/loopback/
  link-local) erfolgt **einmalig** im `_PinnedTransport` unmittelbar vor dem
  Connect (SEC-005: eine Resolution pro Request, kein TOCTOU-Fenster).
- **Network-Layer (deploybar, Kubernetes):** `deploy/network-policy.example.yaml`
  liefert ein konkretes Artefakt — eine vanilla `NetworkPolicy` (DNS + 443) und
  eine Cilium-`CiliumNetworkPolicy` mit FQDN-Egress, die exakt die Allow-List-
  Hosts freigibt. Es ist Defense-in-Depth zum Code-Layer und **muss mit
  `ALLOWED_HOSTS` synchron** gehalten werden (Verfahren: CONTRIBUTING.md).
- **Render/Docker-Compose:** bieten keine hostbasierte Egress-Beschränkung auf
  App-Ebene; dort bleibt der Code-Layer die massgebliche Kontrolle.

### Allow-List erweitern (verbindliches Verfahren)

Eine Änderung an `ALLOWED_HOSTS` ist eine sicherheitsrelevante Erweiterung der
Angriffsfläche und durchläuft daher:

1. **PR mit expliziter Begründung**, welcher neue Host warum nötig ist
   (Datenquelle, Endpoint, Lizenz).
2. **`deploy/network-policy.example.yaml` im selben PR mitziehen** (FQDN-Liste).
3. **CHANGELOG-Eintrag** unter Security (neuer Egress-Host = dokumentierte
   Änderung des Sicherheitsprofils).
4. Review durch eine zweite Person (kein Self-Merge von Egress-Änderungen).
