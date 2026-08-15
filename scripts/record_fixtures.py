#!/usr/bin/env python3
"""Zeichnet je eine echte Antwort pro Abfrage auf.

Warum nicht von Hand geschrieben: eine handgeschriebene Erfolgs-Antwort stimmt
mit dem ueberein, was ihr Autor annahm, und kann die Quelle deshalb nicht
widerlegen. Aufgezeichnet wird darum an demselben Ort, an dem der Server die
Antwort entgegennimmt — ueber einen httpx-Response-Hook auf dem geteilten
Client aus `api_client.get_client()`. Damit tragen Aufzeichnung und Betrieb
denselben User-Agent, dasselbe Timeout und dieselbe DNS-Pinning-Transportschicht.

Wenige Hosts, aber viele Abfrageformen: fast alles laeuft ueber denselben
SPARQL-Endpunkt auf LINDAS und unterscheidet sich nur in der Abfrage — Luft,
Wasser, Schnee, Jagd, Laerm. Die Portfolio-Regel «eine Antwort je externem
Endpunkt» waere mit einer Handvoll Dateien erfuellt und truege fast nichts. Die
volle URL samt Query-String gehoert deshalb in den Schluessel.

Zugeordnet wird beim Abspielen nach der Anfrage und nicht nach der Reihenfolge:
mehrere Werkzeuge schicken mehr als eine Abfrage.

## Aufruf

    PYTHONPATH=src python scripts/record_fixtures.py

Schreibt nach `tests/fixtures/` und erzeugt `tests/fixtures/PROVENANCE.md` neu.
Dateien, die kein Plan-Eintrag mehr erzeugt, werden geloescht — sonst waechst
der Ordner und der Nachweis bleibt zurueck.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL / "src"))

from swiss_environment_mcp import api_client, server  # noqa: E402

FIXTURES = WURZEL / "tests" / "fixtures"

VERSUCHE = 4

# Wie viele Eintraege einer Trefferliste bleiben. Die Form einer Zeile belegen
# drei genauso gut wie hundert; die Zahl steht je Datei im Nachweis.
ZEILEN = 3


@dataclass(frozen=True)
class Aufruf:
    """Ein Werkzeugaufruf, der Anfragen ausloesen soll."""

    name: str
    werkzeug: str
    klasse: str
    eingabe: dict[str, Any]
    # Kuerzen ist nur dort harmlos, wo der Server die Liste ganz liest. Filtert
    # oder zaehlt er *in* ihr, schneidet ein Schnitt womoeglich genau die Zeile
    # weg, die er sucht.
    kuerzen: bool = True
    notiz: str = ""


# Fuenf Werkzeuge stehen bewusst nicht im Plan: `env_nabel_stations`,
# `env_hydro_stations`, `env_hazard_overview`, `env_hazard_regions` und
# `env_hunting_species` liefern im Quellcode gepflegte Kataloge und schicken
# keine Anfrage. Was nie ein Netz beruehrt, hat hier nichts aufzuzeichnen —
# gepruft wird das in `test_die_katalog_werkzeuge_fragen_nichts`.
PLAN: list[Aufruf] = [
    Aufruf("nabel_current", "env_nabel_current", "NabelCurrentInput", {"station": "BER"}),
    Aufruf(
        "flood_warnings",
        "env_flood_warnings",
        "FloodWarningsInput",
        # `min_level=2` ist der Standard und liefert im Sommer nichts: am
        # 2026-08-15 stehen alle 180 Stationen mit gesetzter Gefahrenstufe auf 1
        # (53 weitere auf `cube.link/Undefined`). Eine leere Trefferliste ist
        # eine richtige Antwort, belegt aber die Form einer Zeile nicht — und
        # genau die soll die Aufzeichnung belegen. Deshalb Stufe 1.
        {"min_level": 1},
        notiz=(
            "Stufe 1 statt der Standard-Stufe 2: bei 2 liefert die Quelle im "
            "Sommer null Zeilen, und eine leere Antwort belegt keine Zeilenform."
        ),
    ),
    Aufruf(
        "bathing_water",
        "env_bathing_water",
        "BathingWaterInput",
        {"canton": "BE"},
        # Das Werkzeug filtert die Badestellen *in* dieser Liste nach Kanton.
        # Gekuerzt blieben zufaellig drei Waadtlaender Stellen stehen — die
        # Aufzeichnung behauptete damit «keine Badestelle im Kanton BE».
        kuerzen=False,
        notiz="Ungekuerzt: das Werkzeug filtert nach Kanton *in* dieser Liste.",
    ),
    Aufruf(
        "wildfire_danger",
        "env_wildfire_danger",
        "WildfireDangerInput",
        {},
        kuerzen=False,
        notiz="Ungekuerzt: das Werkzeug filtert nach Kanton *in* dieser Liste.",
    ),
    Aufruf(
        "snow_stations",
        "env_snow_stations",
        "SnowStationsInput",
        {"canton": "GR"},
        kuerzen=False,
        notiz="Ungekuerzt: das Werkzeug filtert nach Kanton *in* dieser Liste.",
    ),
    Aufruf(
        "avalanche_bulletin",
        "env_avalanche_bulletin",
        "AvalancheBulletinInput",
        {},
        # Der SLF veroeffentlicht das Bulletin nur in der Lawinensaison. Am
        # 2026-08-15 gibt die Quelle eine leere FeatureCollection zurueck, auch
        # fuer ein Winterdatum. Das ist keine kaputte Aufzeichnung, sondern der
        # Sommerzustand der Quelle — er steht so im Nachweis.
        notiz=(
            "Leer, weil ausserhalb der Lawinensaison aufgezeichnet: die Quelle "
            "liefert im August eine leere FeatureCollection."
        ),
    ),
    Aufruf(
        "hunting_stats",
        "env_hunting_stats",
        "HuntingStatsInput",
        {"species": "Rothirsch"},
        # Das Werkzeug rechnet *in* den Reihen: `values[i]` wird ueber `years`
        # indiziert. Ein Schnitt verschoebe die Jahreszuordnung.
        kuerzen=False,
        notiz="Ungekuerzt: das Werkzeug indiziert Messreihen ueber die Jahresliste.",
    ),
    Aufruf("bafu_datasets", "env_bafu_datasets", "BafuDatasetsInput", {"query": "Wasser"}),
    Aufruf(
        "noise_registers",
        "env_noise_aircraft_registers",
        "NoiseAircraftRegistersInput",
        {},
        kuerzen=False,
        notiz="Ungekuerzt: das Werkzeug listet die Register vollstaendig.",
    ),
    Aufruf(
        "noise_at",
        "env_noise_aircraft_at",
        "NoiseAircraftAtInput",
        # Kloten statt Zuerich HB: der erste Entwurf fragte 2683000/1248000 ab,
        # den Hauptbahnhof. Dort liegt kein Kataster, die Quelle antwortete
        # `{"results": []}` — richtig, aber ohne jede Zeilenform.
        {"east": 2684500, "north": 1256500},
        notiz="Kloten, weil am Zuercher HB kein Kataster liegt und die Antwort leer bleibt.",
    ),
]

# Die Kataloge, die ohne Netz auskommen — hier festgehalten, damit der Test
# dieselbe Liste pruefen kann.
OHNE_NETZ = (
    "env_nabel_stations",
    "env_hydro_stations",
    "env_hazard_overview",
    "env_hazard_regions",
    "env_hunting_species",
)


def schluessel_fuer(request: httpx.Request) -> str:
    """Woran eine Anfrage beim Abspielen wiedererkannt wird.

    Nicht `str(request.url)`: `_PinnedTransport` schreibt den Hostnamen vor dem
    Connect auf die aufgeloeste IP um (DNS-Pinning, Audit SEC-005). Die steht
    dann in der URL — und ist beim naechsten Lauf eine andere. Der erste
    Entwurf zeichnete `13.226.251.100` auf und traf beim Abspielen auf
    `13.226.251.119`; zwei Aufrufe desselben Werkzeugs landeten schon innerhalb
    eines Laufs auf verschiedenen Adressen. Gruen war das nur zufaellig.

    Der `Host`-Header traegt weiterhin den Original-Hostnamen — er ist hier die
    stabile Angabe. Die Abfrage selbst steht bei allen Quellen dieses Servers im
    Query-String, nicht im Rumpf; die volle URL genuegt deshalb als Schluessel.
    """
    host = request.headers.get("host") or request.url.host
    return str(request.url.copy_with(host=host.split(":")[0], port=None))


@dataclass
class Antwort:
    """Eine gesehene Antwort samt der Anfrage, die sie ausgeloest hat."""

    schluessel: str
    text: str
    werkzeuge: list[str] = field(default_factory=list)
    darf_kuerzen: bool = True
    notiz: str = ""
    dateiname: str = ""
    original_bytes: int = 0
    gekuerzt_von: int = 0
    behalten: int = 0
    sha256: str = ""
    bytes: int = 0


def _endung(text: str) -> str:
    """`.json`, wenn die Antwort JSON ist — sonst `.html`.

    Die Waldbrandgefahr kommt als HTML-Seite, aus der das Werkzeug erst den Link
    auf die JSON-Datei liest. `.xml` waere hier der falsche Name gewesen.
    """
    try:
        json.loads(text)
    except json.JSONDecodeError:
        return ".html"
    return ".json"


def _hook_fuer(gesehen: list[Antwort]) -> Callable[[httpx.Response], Awaitable[None]]:
    """Baut den Response-Hook fuer einen Versuch.

    Eigene Funktion, damit die Liste als Argument gebunden ist und nicht als
    Schleifenvariable aus dem umgebenden Namensraum (ruff B023).
    """

    async def hook(response: httpx.Response) -> None:
        await response.aread()
        gesehen.append(Antwort(schluessel=schluessel_fuer(response.request), text=response.text))

    return hook


async def _fahre(a: Aufruf, client: httpx.AsyncClient) -> list[Antwort]:
    """Ruft ein Werkzeug und gibt die dabei gesehenen Antworten zurueck."""
    fn = getattr(server, a.werkzeug)
    modell = getattr(server, a.klasse)(**a.eingabe)
    letzter: Exception | None = None

    for versuch in range(VERSUCHE):
        if versuch:
            await asyncio.sleep(2**versuch)
        gesehen: list[Antwort] = []
        hook = _hook_fuer(gesehen)
        client.event_hooks.setdefault("response", []).append(hook)
        try:
            ergebnis = await fn(modell)
        except Exception as e:  # noqa: BLE001 — jeder Fehler ist hier ein Retry-Grund
            letzter = e
            continue
        finally:
            client.event_hooks["response"].remove(hook)

        if "Fehler" in str(ergebnis)[:200]:
            letzter = RuntimeError(f"{a.werkzeug} meldet: {str(ergebnis)[:200]}")
            continue
        if not gesehen:
            letzter = RuntimeError(f"{a.werkzeug} hat keine Anfrage abgeschickt")
            continue
        for antwort in gesehen:
            antwort.werkzeuge.append(a.werkzeug)
            antwort.darf_kuerzen = a.kuerzen
            antwort.notiz = a.notiz
        return gesehen

    raise RuntimeError(f"{a.name} nach {VERSUCHE} Versuchen nicht aufgezeichnet: {letzter}")


def _kuerze(daten: Any) -> tuple[int, int, Any]:
    """Kuerzt jede Liste im Baum auf `ZEILEN`; gibt (vorher, nachher, Daten).

    Nur die Zahl der Eintraege, nie ein Feld. Zaehlfelder daneben bleiben
    stehen: die Quelle meint damit die Gesamtzahl und nicht die Zahl der
    gelieferten Zeilen, und genau die liest der Server aus.
    """
    vorher = nachher = 0

    def geh(knoten: Any) -> Any:
        nonlocal vorher, nachher
        if isinstance(knoten, dict):
            return {k: geh(v) for k, v in knoten.items()}
        if isinstance(knoten, list):
            vorher += len(knoten)
            gekuerzt = knoten[:ZEILEN]
            nachher += len(gekuerzt)
            return [geh(v) for v in gekuerzt]
        return knoten

    # Erst laufen lassen, dann die Zaehler lesen. `return vorher, nachher,
    # geh(daten)` wertet von links nach rechts aus und lieferte deshalb immer
    # (0, 0) — der Nachweis schrieb «ungekuerzt» ueber jede gekuerzte Datei.
    ergebnis = geh(daten)
    return vorher, nachher, ergebnis


async def main() -> int:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    heute = datetime.now(UTC).date().isoformat()
    nach_schluessel: dict[str, Antwort] = {}
    zaehler: dict[str, int] = {}

    client = api_client.get_client()
    try:
        for a in PLAN:
            print(f"… {a.werkzeug} ({a.name})", file=sys.stderr)
            for antwort in await _fahre(a, client):
                if antwort.schluessel in nach_schluessel:
                    vorhanden = nach_schluessel[antwort.schluessel]
                    if a.werkzeug not in vorhanden.werkzeuge:
                        vorhanden.werkzeuge.append(a.werkzeug)
                    continue
                zaehler[a.name] = zaehler.get(a.name, 0) + 1
                antwort.dateiname = f"{a.name}_{zaehler[a.name]}{_endung(antwort.text)}"
                nach_schluessel[antwort.schluessel] = antwort
    finally:
        await api_client.shutdown()

    for antwort in nach_schluessel.values():
        antwort.original_bytes = len(antwort.text.encode("utf-8"))
        try:
            daten = json.loads(antwort.text)
        except json.JSONDecodeError:
            # Nicht jede Quelle antwortet mit JSON — der SLF liefert teils XML.
            (FIXTURES / antwort.dateiname).write_text(antwort.text, encoding="utf-8")
            roh = (FIXTURES / antwort.dateiname).read_bytes()
            antwort.sha256 = hashlib.sha256(roh).hexdigest()
            antwort.bytes = len(roh)
            continue
        if antwort.darf_kuerzen:
            antwort.gekuerzt_von, antwort.behalten, daten = _kuerze(daten)
        # Neu eingerueckt geschrieben: eine Zeile JSON waere kleiner, aber im
        # Diff nicht lesbar, und ein Fixture will gelesen werden.
        (FIXTURES / antwort.dateiname).write_text(
            json.dumps(daten, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        roh = (FIXTURES / antwort.dateiname).read_bytes()
        antwort.sha256 = hashlib.sha256(roh).hexdigest()
        antwort.bytes = len(roh)

    antworten = sorted(nach_schluessel.values(), key=lambda x: x.dateiname)
    _schreibe_provenance(antworten, heute)

    # Aufraeumen: was kein Plan-Eintrag mehr erzeugt, hat auch keinen Nachweis.
    geschrieben = {a.dateiname for a in antworten} | {"PROVENANCE.md"}
    for pfad in sorted(FIXTURES.iterdir()):
        if pfad.name not in geschrieben:
            print(f"– entferne veraltet: {pfad.name}", file=sys.stderr)
            pfad.unlink()

    print(f"{len(antworten)} Aufzeichnungen in {FIXTURES}", file=sys.stderr)
    return 0


def _schreibe_provenance(antworten: list[Antwort], heute: str) -> None:
    zeilen = [
        "# Herkunft der Fixtures",
        "",
        f"Aufgezeichnet am **{heute}** mit `PYTHONPATH=src python scripts/record_fixtures.py`.",
        "",
        "Eine Antwort je **Abfrage**, nicht je Endpunkt: fast alles laeuft ueber",
        "denselben SPARQL-Endpunkt auf LINDAS und unterscheidet sich nur in der",
        "Abfrage — Luft, Wasser, Schnee, Jagd, Laerm. Eine Handvoll Dateien wuerde",
        "die Portfolio-Regel erfuellen und fast nichts belegen.",
        "",
        "Der **Schluessel** unten ist, woran der Test eine Anfrage wiedererkennt: die",
        "volle URL samt Query-String. Ohne den Query-String waeren die",
        "SPARQL-Abfragen ununterscheidbar — sie gehen an dieselbe Adresse.",
        "",
        "Im Schluessel steht der **Hostname**, nicht die IP. Der DNS-Pinning-Transport",
        "schreibt die URL vor dem Connect auf die aufgeloeste Adresse um; die ist beim",
        "naechsten Lauf eine andere, und ein darauf gebauter Schluessel traefe nur mit",
        "Glueck.",
        "",
        "Die Antworten stammen aus dem geteilten Client von `api_client.get_client()`",
        "(gleicher User-Agent, gleiches Timeout, gleiche DNS-Pinning-Schicht wie im Betrieb),",
        "abgegriffen ueber einen httpx-Response-Hook. Ausgeloest hat sie jeweils das",
        "Werkzeug selbst — so belegt die Aufzeichnung auch, dass das Werkzeug genau",
        "diese Anfrage schickt.",
        "",
        "## Auswahl",
        "",
        "Neu gesetzt ist die Einrueckung; gekuerzt ist allein die **Zahl** der",
        "Listeneintraege. Kein Feld eines behaltenen Eintrags ist angetastet, und",
        "Zaehlfelder daneben stehen wie geliefert.",
        "",
        "Die Fehlerpfade — Timeout, 5xx, leere Trefferliste — bleiben handgeschrieben.",
        "Sie lassen sich nicht auf Zuruf aufzeichnen und sind als Erfindung in Ordnung.",
        "",
    ]
    for a in antworten:
        zeilen += [
            f"## `{a.dateiname}`",
            "",
            f"- **Werkzeuge:** {', '.join(f'`{w}`' for w in sorted(a.werkzeuge))}",
            f"- **Schluessel:** `{a.schluessel}`",
        ]
        if a.notiz:
            zeilen.append(f"- **Notiz:** {a.notiz}")
        if a.gekuerzt_von > a.behalten:
            zeilen.append(
                f"- **Auswahl:** {a.behalten} von {a.gekuerzt_von} Listeneintraegen — "
                f"jede Liste im Baum auf die ersten {ZEILEN} gekuerzt, "
                f"aus {a.original_bytes} Bytes Rohantwort"
            )
        elif not a.darf_kuerzen:
            zeilen.append(
                "- **Auswahl:** ungekuerzt — der Server rechnet *in* dieser Antwort, "
                "ein Schnitt erfaende ein anderes Ergebnis"
            )
        else:
            zeilen.append("- **Auswahl:** ungekuerzt")
        zeilen += [
            f"- **Groesse:** {a.bytes} Bytes",
            f"- **SHA-256:** `{a.sha256}`",
            "",
        ]
    (FIXTURES / "PROVENANCE.md").write_text("\n".join(zeilen), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
