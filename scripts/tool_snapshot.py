"""
Tool-Definition Hash-Snapshot (Audit SEC-022 — Rug-Pull-Schutz).

Erzeugt bzw. prüft einen SHA-256-Snapshot über alle Tool-Definitionen
(Name + Description + Input-Schema). Ändert sich eine Tool-Definition
unbemerkt, ändert sich der Hash und der CI-Check (`check`) schlägt fehl —
das erzwingt einen bewussten CHANGELOG-Eintrag + Versions-Bump (Synergie
zu ARCH-012 / SEC-022).

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


async def _collect_tools() -> list[dict]:
    tools = await mcp.list_tools()
    return [
        {"name": t.name, "description": t.description, "input_schema": t.inputSchema}
        for t in sorted(tools, key=lambda x: x.name)
    ]


def _compute_hash(tools: list[dict]) -> str:
    canonical = json.dumps(tools, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_snapshot() -> dict:
    """Baut den Snapshot-Datensatz (Tool-Anzahl, Namen, Hash)."""
    tools = asyncio.run(_collect_tools())
    return {
        "tool_count": len(tools),
        "tool_names": [t["name"] for t in tools],
        "sha256": _compute_hash(tools),
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
        print(f"geschrieben: {SNAPSHOT_PATH.name} ({snap['tool_count']} Tools, {snap['sha256'][:12]})")


if __name__ == "__main__":
    main()
