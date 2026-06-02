## Finding: SEC-013 — API-Key-Storage: Secret Manager statt Plain-Text Env-Vars

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status (Check)** | ⚠️ PARTIAL |
| **Status (Finding)** | open |
| **Server** | `swiss-environment-mcp` |
| **Check-Reference** | `SEC-013` |
| **PDF-Reference** | Sec 4 (Empirie 2025) |
| **Audit-Datum** | 2026-06-02 |
| **Auditor** | mcp-audit-skill v1.0.0 (automatisiert) |

### Kontext (Check-Description)

ARCH-005 verlangt: **keine Hardcoded Secrets im Code**. SEC-013 geht weiter: in Production reichen Plain-Text Env-Vars nicht aus.

### Observed Behavior

Belege aus Code/Konfiguration des auditierten Servers:

- Public Open Data: keine API-Keys/Secrets erforderlich — Stufe 1 akzeptabel
- Keine Secrets im Container-Layer

### Gaps gegenüber Pass-Criteria

- Keine docs/secret-management.md, die die Stufe-1-Entscheidung dokumentiert

### Remediation (aus Katalog-Check SEC-013)

### Schritt 1: Reife-Stufe pro Server bestimmen

| Server-Profil | Empfohlene Stufe |
|---|---|
| `Public Open Data`, Demo-Deployment | 1 (dokumentiert) |
| `Public Open Data`, Production | 3 |
| `Verwaltungsdaten` | 3 oder 4 |
| `PII` | 4 (Workload Identity) bevorzugt |

### Schritt 2: Migration zu Secret Manager (Stufe 1 → 3)

```diff
- import os
- api_key = os.environ["UPSTREAM_API_KEY"]

+ import boto3, json
+ from cachetools import TTLCache
+
+ _cache = TTLCache(maxsize=1, ttl=300)
+
+ def get_api_key() -> str:
+     if "key" not in _cache:
+         client = boto3.client("secretsmanager", region_name="eu-central-1")
+         response = client.get_secret_value(SecretId="schulamt-mcp/production")
+         _cache["key"] = json.loads(response["SecretString"])["upstream_api_key"]
+     return _cache["key"]
```

### Schritt 3: Rotation-Verfahren dokumentieren

`docs/secret-rotation.md`:

```markdown
# Secret Rotation Procedure

### Effort Estimate

M — 1–3 Tage. Secret-Manager-Setup + Migrations-Skript + Rotation-Doku.

### Verification After Fix

- Re-Audit von `SEC-013` mit `mcp-audit-skill` (gleicher catalog_hash)
- Ziel-Status: `pass`
