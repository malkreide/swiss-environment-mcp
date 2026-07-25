# Skalierung & Session-Strategie — swiss-environment-mcp

Adressiert die Findings SCALE-002 und SCALE-003 des MCP-Audits.

## Aktueller Stand: Single-Instance

Der Server wird als **einzelne Instanz** betrieben (Render Web Service /
einzelner Container). In dieser Topologie ist kein verteiltes Session-Management
nötig — alle Requests einer `Mcp-Session-Id` landen zwangsläufig auf derselben
Instanz.

Eigenschaften:

- **Transport:** Streamable HTTP (Cloud) bzw. stdio (lokal).
- **State:** keine serverseitig persistierten Sessions; jeder Tool-Call ist für
  sich abgeschlossen und idempotent gegenüber öffentlichen Daten.
- **HTTP-Client:** ein geteilter `httpx.AsyncClient` pro Prozess (Lifespan).

## Scale-out (mehrere Instanzen)

Sobald horizontal skaliert wird (mehrere Replicas hinter einem Load Balancer),
muss die `Mcp-Session-Id`-Affinität sichergestellt werden, da der Streamable-
HTTP-Transport Session-State pro Verbindung hält. Genau **eines** der folgenden
Muster ist dann verbindlich:

1. **Sticky Sessions am Edge-LB** (SCALE-003): HAProxy/Nginx/K8s-Ingress routet
   anhand des `Mcp-Session-Id`-Headers konsistent auf dasselbe Backend.
   - HAProxy: Stick-Table auf den Header, TTL korreliert mit Session-TTL
     (z.B. 24h), Kapazität ≥ 100k Sessions.
2. **Shared-State-Session-Manager** (SCALE-002): Redis / Cloudflare Durable
   Objects o.ä. als gemeinsamer Session-Store, sodass jede Instanz jede Session
   bedienen kann.

**Session-TTL** ist in beiden Fällen explizit zu setzen. **Failover:** Bei
Ausfall eines Backends darf eine Session ohne Shared State nicht stumm auf ein
neues Backend umgeleitet werden — entweder Shared State oder sauberer
Session-Neuaufbau.

## Resource-Limits (SCALE-006)

Pro Container Memory-/CPU-Limits setzen (Multi-Tenant-Scheduling-Schutz);
Requests < Limits für Burst-Spielraum; `ulimit -n` ≥ 4096 wegen ausgehender
Connections; restart-policy aktiv für sauberes OOM-Verhalten.

**Nach Deployment-Pfad:**

| Pfad | Memory / CPU | Restart bei OOM |
|---|---|---|
| **Docker-Compose** (self-hosted) | `mem_limit: 256m`, `mem_reservation: 128m`, `cpus: 0.5`, `ulimits.nofile 4096/8192` — explizit in `docker-compose.yml` | `restart: unless-stopped` |
| **Render** (`render.yaml`, Plan `starter`) | Plan-gebunden: 512 MB RAM / 0.5 vCPU (Render deckelt hart auf Plan-Ebene) | Render startet den Dienst bei OOM automatisch neu (managed) |
| **Kubernetes** | `resources.requests/limits` im Pod-Spec setzen (Werte analog Compose) + `restartPolicy: Always` | kubelet killt+restartet bei Limit-Überschreitung |

**OOM-Verhalten (verifizierbar):** Der Prozess ist single-instance und hält
keinen unbeschränkt wachsenden State (kein Session-Store, gecachte Codelisten
sind klein). Ein OOM-Kill ist damit ein sauberer Neustart ohne Datenverlust.
Lokal reproduzierbar: `docker run --memory=64m …` erzwingt einen OOM-Kill; der
Container wird durch die restart-policy neu gestartet, der `/health`-Endpoint ist
danach wieder grün. Ein knappes `--memory` unterhalb des Startbedarfs zeigt den
CrashLoop, ein realistisches Limit (≥ 256 MB) läuft stabil.

## SPARQL-Client (Portfolio-Baustein)

Der SPARQL-/JSON-Retry-Client ist in `sparql_client.py` isoliert: abhängigkeitsarm
(nur `httpx`/`asyncio`), Egress-Guard als Callback, HTTP-Client vom Aufrufer.
`api_client.run_sparql` / `_get_json_retry` sind dünne Bindungen. Der Baustein
stammt ursprünglich aus `fedlex-mcp` (`_execute_sparql`).

**Aktueller Stand — Vendoring:** `sparql_client.py` liegt **byte-identisch** in
`swiss-environment-mcp` und `fedlex-mcp` (beide Server binden dünn daran). Damit
ist die *Logik* vereinheitlicht (eine kanonische Datei, kopiert). Änderungen sind
in beiden Kopien synchron zu halten — der Moduldocstring weist darauf hin.

**Offener Folgeschritt (Cross-Repo, echte De-Duplikation):** ein installierbares
Paket `swiss-mcp-commons` publizieren und beide Server darauf umstellen, sodass es
nur noch **eine** Quelle gibt. Erfordert eine Paketierungs-Entscheidung (Name,
PyPI/OIDC Trusted Publisher — Letzteres kann nur der Repo-/PyPI-Owner einrichten)
und berührt mehrere Repos — daher als separater, abgestimmter Schritt offen.
