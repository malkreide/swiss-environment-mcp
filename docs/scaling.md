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
