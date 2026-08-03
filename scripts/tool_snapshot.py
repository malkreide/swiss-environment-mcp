"""
Tool-Definition Hash-Snapshot (Audit SEC-022 — Rug-Pull-Schutz).

Erzeugt bzw. prüft einen SHA-256-Snapshot über alle Tool-Definitionen. Ändert
sich eine Definition unbemerkt, ändert sich der Hash und der CI-Check (`check`)
schlägt fehl — das erzwingt einen bewussten CHANGELOG-Eintrag + Versions-Bump
(Synergie zu ARCH-012 / SEC-022).

Erfasst werden Tool-Name, Tool-Description und die **Parameter des
Eingabemodells**: Name, Pflicht-Status, Beschreibung, Default und die
Validierungs-Schranken (`pattern`, Längen, Grenzwerte, `enum`).

Genau diese Parameter-Ebene fehlte bis 08/2026 faktisch. Das Input-Schema eines
Tools hat nur eine Property — `params` —, deren Modell unter `$defs` liegt und
per `$ref` referenziert wird. Der Snapshot las `properties.keys()` und schrieb
deshalb für jedes der 21 Tools dieselbe Liste `["params"]`: eine umbenannte,
entfernte oder in ihrer Bedeutung gedrehte Eingabe war unsichtbar. Der `$ref`
wird jetzt aufgelöst.

Verwendung:
    python scripts/tool_snapshot.py          # Snapshot schreiben/aktualisieren
    python scripts/tool_snapshot.py check    # gegen committeten Snapshot prüfen (exit 1 bei Drift)
"""

import asyncio
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from swiss_environment_mcp.server import mcp  # noqa: E402

SNAPSHOT_PATH = Path(__file__).resolve().parent.parent / "tool-snapshot.json"


# Schema-Schlüssel, die *wir* schreiben und die deshalb versions-stabil sind.
# Bewusst NICHT das rohe Schema hashen: dessen Serialisierung variiert zwischen
# Pydantic-/MCP-Versionen (CI 3.11 vs 3.13) und machte den Hash
# nicht-reproduzierbar. `type` steht aus demselben Grund nicht hier — optionale
# Felder erscheinen je nach Version als `type` oder als `anyOf`.
_STABLE_KEYS = (
    "description",
    "default",
    "enum",
    "pattern",
    "minLength",
    "maxLength",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
)


def _resolve(node: dict, defs: dict) -> dict:
    """Löst eine `$ref`-Referenz (auch in `allOf`) eine Ebene auf.

    Pydantic hängt Enums und verschachtelte Modelle unter `$defs` und verweist
    per `$ref` darauf. Ohne diese Auflösung sieht der Snapshot statt der Felder
    nur den Verweis.
    """
    if "$ref" not in node and "allOf" in node and len(node["allOf"]) == 1:
        merged = {k: v for k, v in node.items() if k != "allOf"}
        merged.update(node["allOf"][0])
        node = merged
    ref = node.get("$ref")
    if not ref or not ref.startswith("#/$defs/"):
        return node
    target = defs.get(ref.rsplit("/", 1)[-1], {})
    # Lokale Angaben (z.B. eine feldspezifische description) gewinnen.
    return {**target, **{k: v for k, v in node.items() if k != "$ref"}}


def _fields(schema: dict) -> list[dict]:
    """Die tatsächlichen Eingabefelder eines Tools, normalisiert.

    Ein Tool dieses Servers hat genau eine Property `params`, hinter der das
    Pydantic-Modell steckt. Diese Hülle wird durchstossen; gehasht werden die
    Felder des Modells.
    """
    defs = schema.get("$defs") or {}
    model = schema
    props = schema.get("properties") or {}
    if list(props) == ["params"]:
        model = _resolve(props["params"], defs)
        props = model.get("properties") or {}
    required = set(model.get("required") or [])

    fields = []
    for name in sorted(props):
        node = _resolve(props[name], defs)
        entry: dict = {"name": name, "required": name in required}
        for key in _STABLE_KEYS:
            if key not in node:
                continue
            value = node[key]
            # Beschreibungen wie die Tool-Description whitespace-normalisieren.
            entry[key] = " ".join(value.split()) if key == "description" else value
        fields.append(entry)
    return fields


async def _collect_tools() -> list[dict]:
    """Normalisierte, versions-stabile Repräsentation der Tool-Definitionen."""
    tools = await mcp.list_tools()
    result = []
    for t in sorted(tools, key=lambda x: x.name):
        fields = _fields(t.input_schema or {})
        # Whitespace kollabieren: Python 3.13 dedentet Docstrings anders als 3.11/3.12,
        # wodurch die Description sonst pro Python-Version unterschiedlich wäre.
        description = " ".join((t.description or "").split())
        result.append(
            {
                "name": t.name,
                "description": description,
                "params": [f["name"] for f in fields],
                "required": [f["name"] for f in fields if f["required"]],
                "fields": fields,
            }
        )
    return result


def _compute_hash(tools: list[dict]) -> str:
    canonical = json.dumps(tools, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_snapshot() -> dict:
    """Baut den Snapshot-Datensatz (Tool-Anzahl, Namen, Hash, Definitionen).

    Die normalisierten Definitionen stehen mit im File, nicht nur ihr Hash: bei
    Drift will man sehen, *was* sich geändert hat. Ein blosser Hash-Vergleich
    sagt nur, dass etwas anders ist — `git diff tool-snapshot.json` zeigt die
    umbenannte Eingabe oder die gedrehte Beschreibung.
    """
    tools = asyncio.run(_collect_tools())
    return {
        "tool_count": len(tools),
        "tool_names": [t["name"] for t in tools],
        "sha256": _compute_hash(tools),
        "tools": tools,
    }


def main() -> None:
    snap = build_snapshot()
    if len(sys.argv) > 1 and sys.argv[1] == "check":
        if not SNAPSHOT_PATH.exists():
            print("Kein tool-snapshot.json — bitte zuerst generieren.", file=sys.stderr)
            sys.exit(1)
        existing = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
        if existing.get("sha256") != snap["sha256"]:
            print(
                "DRIFT: Tool-Definitionen geändert. Snapshot aktualisieren "
                "(python scripts/tool_snapshot.py), CHANGELOG + Version bumpen.",
                file=sys.stderr,
            )
            sys.exit(1)
        print(f"tool-snapshot OK ({snap['tool_count']} Tools, {snap['sha256'][:12]})")
    else:
        SNAPSHOT_PATH.write_text(
            json.dumps(snap, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(
            f"geschrieben: {SNAPSHOT_PATH.name} ({snap['tool_count']} Tools, {snap['sha256'][:12]})"
        )


if __name__ == "__main__":
    main()
