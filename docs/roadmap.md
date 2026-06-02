# Roadmap & Phasenarchitektur — swiss-environment-mcp

Adressiert Finding OPS-003 (Phasenarchitektur: Read-only First).

## Aktuelle Phase: **Phase 1 — Read-only Wrapper**

Der Server befindet sich in **Phase 1**. Alle 12 Tools sind read-only
(`readOnlyHint: true`), es gibt keine schreibenden oder destruktiven Operationen
und keine Authentifizierung. Datenquellen sind ausschliesslich öffentliche
BAFU/SLF/opendata.swiss-Endpunkte.

Diese Phase entspricht den Tool-Annotations (kein Phase-1-Server mit
destruktiven Tools) und dem Security-Profil in [`security.md`](security.md).

## Phasenmodell

| Phase | Inhalt | Status |
|---|---|---|
| **1 — Read-only** | Öffentliche Daten lesen, keine Auth, keine Seiteneffekte | ✅ aktuell |
| **2 — Write/Auth** | Schreibende Tools und/oder Authentifizierung | offen |
| **3 — Multi-Agent** | Sampling, Agent-Orchestrierung, Identity-Resolution | offen |

## Voraussetzungen für Phasenübergänge

**Phase 1 → 2** (bevor schreibende Tools oder Auth eingeführt werden):

- Abgeschlossener Audit-Run (mcp-audit-skill) ohne offene critical/high-Findings.
- ISDS / DSG-Verarbeitungsverzeichnis, falls Personendaten ins Spiel kommen.
- OAuth/OIDC mit Session-User-Binding (siehe SEC-009 in `security.md`).
- Neubewertung der Lethal Trifecta (SEC-019): ein schreibender/sendender Kanal
  verschiebt das Bedrohungsmodell deutlich.
- Secret-Management auf Stufe 3 (Secret-Manager) heben (SEC-013).

**Phase 2 → 3:**

- Semantic Layer / Identity-Resolution.
- GL- und Datenschutzbeauftragte:n-Sign-off.

## Geplante kleinere Verbesserungen (Phase 1)

- Optionaler strukturierter JSON-Envelope auch für die übrigen Tools.
- OpenTelemetry-Tracing (OBS-006) für Cloud-Deployments.

Phasenübergänge werden im [CHANGELOG](../CHANGELOG.md) dokumentiert.
