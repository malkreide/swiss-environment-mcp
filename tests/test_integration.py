"""
Integrationstests für swiss-environment-mcp.

Tests laufen gegen Live-APIs des BAFU. Für Offline-Tests die Umgebungsvariable
SKIP_LIVE_TESTS=1 setzen.

Ausführung:
    python tests/test_integration.py
    # oder:
    pytest tests/ -v
"""

import asyncio
import json
import os
import sys

import pytest
from conftest import _transport_cause
from mcp.server.mcpserver.exceptions import ToolError

# Diese Datei trifft echte BAFU-Live-APIs. Alle hier gesammelten Tests werden
# als `live` markiert und in der Standard-CI via `pytest -m "not live"`
# übersprungen (Audit OPS-001). Mocked Unit-Tests siehe tests/test_unit.py.
pytestmark = pytest.mark.live

# Lokales Paket importieren
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from swiss_environment_mcp.server import (
    AirLimitsCheckInput,
    BafuDatasetDetailInput,
    BafuDatasetsInput,
    FloodWarningsInput,
    HazardOverviewInput,
    HazardRegionsInput,
    HydroCurrentInput,
    HydroHistoryInput,
    HydroStationsInput,
    NabelCurrentInput,
    NabelStationsInput,
    ResponseFormat,
    WildfireDangerInput,
    env_air_limits_check,
    env_bafu_dataset_detail,
    env_bafu_datasets,
    env_flood_warnings,
    env_hazard_overview,
    env_hazard_regions,
    env_hydro_current,
    env_hydro_history,
    env_hydro_stations,
    env_nabel_current,
    env_nabel_stations,
    env_wildfire_danger,
)

SKIP_LIVE = os.environ.get("SKIP_LIVE_TESTS", "0") == "1"

_pass = 0
_fail = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    """Prüft eine Zusicherung: druckt sie und lässt den Test bei ❌ scheitern.

    Der `raise` ist der Punkt (OPS-001). Vorher wurde nur gedruckt und
    hochgezählt — unter pytest scheitert ein Test aber ausschliesslich an einer
    durchschlagenden Exception, und das `sys.exit(1)` in `main()` greift nur im
    Standalone-Pfad (`python tests/test_integration.py`). Jede Zusicherung
    dieser Datei war damit für die nächtliche CI wirkungslos; rot wurde der Job
    nur, wenn ein Tool eine Exception warf. Zwei veraltete Zusicherungen in
    `test_nabel_stations` scheiterten so über Monate unbemerkt.

    `main()` fängt den Fehler ab, damit der Standalone-Lauf weiterhin alle
    Tests durchläuft und am Ende die Gesamtbilanz zieht.
    """
    global _pass, _fail
    if condition:
        print(f"  ✅ {name}")
        _pass += 1
        return
    print(f"  ❌ {name}" + (f": {detail}" if detail else ""))
    _fail += 1
    raise AssertionError(f"{name}: {detail}" if detail else name)


async def _tool_text(coro) -> str:
    """Führt einen Tool-Call aus und liefert dessen Text — oder, bei einem
    terminalen `ToolError`, dessen Meldung.

    Seit OBS-001 werfen die Tools bei einem nicht erreichbaren/degradierten
    Upstream (z.B. HTTP 301/404 von naturgefahren.ch bzw. waldbrandgefahr.ch)
    einen `ToolError` mit `isError:true`, dessen Content weiterhin die
    Recovery-Links trägt. Für die Live-Smoke-Checks (kein Traceback, Link
    vorhanden) ist das eine gültige Graceful-Degradation — wir prüfen daher
    gegen den Fehler-Content, statt an der Exception zu scheitern. So bleiben
    die Live-Tests robust gegenüber Upstream-Ausfällen (wie vor OBS-001, als
    derselbe Text als regulärer String zurückkam).

    **Nicht** abgefangen wird ein `ToolError`, hinter dem ein reiner
    Transportfehler steckt: dann hat der Upstream gar nicht geantwortet, und
    der Hook in `conftest.py` soll den Lauf zu SKIPPED herabstufen. Seit
    `check()` Tests tatsächlich rot macht, würde die Meldung sonst durch die
    Zusicherungen fallen und ein Netzausfall als Vertragsbruch erscheinen."""
    try:
        return await coro
    except ToolError as e:
        if _transport_cause(e) is not None:
            raise
        return str(e)


# --- Luft-Tests ---------------------------------------------------------------


async def test_nabel_stations() -> None:
    print("\n[Luft] NABEL-Stationen")

    # Markdown
    result = await env_nabel_stations(NabelStationsInput())
    check("Enthält Tabellenheader", "| Kürzel |" in result)
    check("Enthält ZUE (Zürich-Kaserne)", "ZUE" in result)
    check("Enthält DUB (Dübendorf)", "DUB" in result)
    check("Link zu BAFU vorhanden", "bafu.admin.ch" in result)

    # JSON — Hülle ist der ResponseEnvelope (SDK-002): count/results/match_type.
    # Die Zusicherungen prüften bis hierher `total` und `nabel_stationen`, also
    # eine Form, die es seit der Envelope-Umstellung nicht mehr gibt. Sie
    # scheiterten still, weil `check()` den Test nicht rot machte.
    result_json = await env_nabel_stations(NabelStationsInput(response_format=ResponseFormat.JSON))
    data = json.loads(result_json)
    check("JSON: 16 Stationen", data.get("count") == 16, f"count={data.get('count')}")
    check("JSON: results ist die Stationsliste", len(data.get("results", [])) == 16)
    check("JSON: match_type gesetzt", data.get("match_type") == "exact")


async def test_nabel_current() -> None:
    print("\n[Luft] NABEL Aktuelle Daten")

    # Gültige Station
    result = await env_nabel_current(NabelCurrentInput(station="ZUE"))
    check("Station ZUE: Name vorhanden", "Zürich-Kaserne" in result)
    check("Station ZUE: Parameter-Tabelle", "NO₂" in result)
    check("Station ZUE: BAFU-Link", "bafu.admin.ch" in result)

    # Ungültige Station
    result_invalid = await env_nabel_current(NabelCurrentInput(station="XXX"))
    check("Ungültige Station: Fehlermeldung", "nicht gefunden" in result_invalid)
    check("Ungültige Station: Stationsliste als Hilfe", "ZUE" in result_invalid)


async def test_air_limits() -> None:
    print("\n[Luft] Grenzwertprüfung")

    # NO2 unter Grenzwert
    result = await env_air_limits_check(AirLimitsCheckInput(pollutant="NO2", value=15.0))
    check("NO2=15: LRV eingehalten", "Eingehalten" in result)
    check("NO2=15: WHO überschritten", "ÜBERSCHRITTEN" in result)

    # PM2.5 über beiden Grenzwerten
    result2 = await env_air_limits_check(AirLimitsCheckInput(pollutant="PM2.5", value=25.0))
    check("PM2.5=25: LRV überschritten", "ÜBERSCHRITTEN" in result2)

    # Unbekannter Schadstoff
    result3 = await env_air_limits_check(AirLimitsCheckInput(pollutant="XYZ", value=100.0))
    check("Unbekannter Schadstoff: Fehlermeldung", "nicht erkannt" in result3)


# --- Wasser-Tests -------------------------------------------------------------


async def test_hydro_stations() -> None:
    print("\n[Wasser] Messstationen")

    if SKIP_LIVE:
        print("  ⏭️  Live-Test übersprungen (SKIP_LIVE_TESTS=1)")
        return

    result = await env_hydro_stations(HydroStationsInput())
    check(
        "Stationsliste: Überschrift vorhanden",
        "Hydrologische" in result or "hydrodaten.admin.ch" in result,
    )
    check("Stationsliste: Link zu hydrodaten.admin.ch", "hydrodaten" in result)

    # Kanton-Filter ZH
    result_zh = await env_hydro_stations(HydroStationsInput(canton="ZH"))
    check("Kanton-Filter ZH: Filterinfo vorhanden", "ZH" in result_zh)


async def test_hydro_current() -> None:
    print("\n[Wasser] Aktuelle Hydrodaten")

    if SKIP_LIVE:
        print("  ⏭️  Live-Test übersprungen")
        return

    # Station 2099 = Limmat Zürich/Unterwerk
    result = await _tool_text(env_hydro_current(HydroCurrentInput(station_id="2099")))
    check("Station 2099: Kein Python-Traceback", "Traceback" not in result)
    check("Station 2099: Datenportal-Link", "hydrodaten.admin.ch" in result)


async def test_hydro_current_lindas() -> None:
    print("\n[Wasser] LINDAS SPARQL — aktueller Limmat-Abfluss (Anchor)")

    if SKIP_LIVE:
        print("  ⏭️  Live-Test übersprungen")
        return

    from swiss_environment_mcp import api_client as api

    data = await api.fetch_hydro_current_lindas("2099")
    check("LINDAS: Station 2099 gefunden", data.get("found") is True)
    check("LINDAS: Gewässer Limmat", "limmat" in (data.get("water") or "").lower())
    check("LINDAS: Abfluss-Wert vorhanden", data.get("discharge") is not None)

    stations = await api.fetch_hydro_stations_lindas()
    check("LINDAS: >200 Stationen", len(stations) > 200)


async def test_bathing_water_lindas() -> None:
    print("\n[Wasser] LINDAS Cube — Badegewässerqualität (Zwei-Phasen-Zugriff)")

    if SKIP_LIVE:
        print("  ⏭️  Live-Test übersprungen")
        return

    from swiss_environment_mcp import api_client as api
    from swiss_environment_mcp.lindas import cube as lcube
    from swiss_environment_mcp.server import BathingWaterInput, env_bathing_water

    # Fundstück 6 live: Struktur & Observations nur via observationSet-Pfad.
    cubes = await lcube.find_cubes(api.run_sparql, "badegewässer")
    check("Cube-Suche: Badegewässer-Cube gefunden", len(cubes) >= 1)
    if cubes:
        structure = await lcube.get_cube_structure(api.run_sparql, cubes[0]["cube"])
        dims = {d["dimension"].rsplit("/", 1)[-1] for d in structure}
        check("Struktur: location-Dimension vorhanden", "location" in dims)

    result = await _tool_text(env_bathing_water(BathingWaterInput(location="Clendy")))
    check("Tool: Kein Python-Traceback", "Traceback" not in result)
    check("Tool: Label statt Code-URI", "ld.admin.ch/dimension" not in result)
    check("Tool: Lizenzfeld vorhanden", "Lizenz" in result or "Open-Use" in result)


async def test_slf_snow() -> None:
    print("\n[Schnee] SLF IMIS — Stationen + Tages-Schneewerte")

    if SKIP_LIVE:
        print("  ⏭️  Live-Test übersprungen")
        return

    from swiss_environment_mcp import api_client as api

    stations = await api.fetch_slf_snow_stations()
    check("SLF: >50 IMIS-Stationen", len(stations) > 50)
    check("SLF: Station hat canton_code", any(s.get("canton_code") for s in stations))

    snow = await api.fetch_slf_daily_snow()
    check("SLF: Tages-Schneewerte vorhanden", len(snow) > 0)
    check("SLF: HS-Feld vorhanden", "HS" in (snow[0] if snow else {}))

    # Bulletin: ausserhalb der Saison leere FeatureCollection (kein Fehler)
    bulletin = await api.fetch_slf_avalanche_bulletin("de")
    check("SLF: Bulletin ist FeatureCollection", bulletin.get("type") == "FeatureCollection")


async def test_snow_stations_tool() -> None:
    """env_snow_stations eigenständig (OPS-001).

    Bewusst **ohne** `_tool_text` und mit `assert` statt `check`: der Test soll
    scheitern, wenn der Upstream antwortet, aber nicht mehr das liefert, woraus
    das Tool seine Tabelle baut. Vorher fing `_tool_text` den `ToolError` ab und
    geprüft wurde nur, ob „SLF" im Text steht — was auch die Fehlermeldung
    („SLF-Stationsliste nicht abrufbar") erfüllt. Der Test bestand damit bei
    komplett totem SLF.

    Kam die Verbindung gar nicht zustande, stuft der Hook in `conftest.py` den
    Lauf zu SKIPPED herab; jede beantwortete Störung (HTTP-Fehler, Schema-Bruch)
    bleibt ein Befund.
    """
    print("\n[Schnee] env_snow_stations — Tool eigenständig (OPS-001)")

    if SKIP_LIVE:
        print("  ⏭️  Live-Test übersprungen")
        return

    from swiss_environment_mcp.server import SnowStationsInput, env_snow_stations

    payload = json.loads(
        await env_snow_stations(SnowStationsInput(canton="GR", response_format=ResponseFormat.JSON))
    )
    stations = payload["results"]
    assert stations, "GR betreibt IMIS-Stationen — eine leere Trefferliste ist ein Befund"
    assert payload["count"] == len(stations)
    assert payload["match_type"] == "exact"
    assert all(s.get("canton_code") == "GR" for s in stations), "Kantonsfilter greift nicht"

    # Genau die Felder, aus denen das Tool seine Tabelle baut — fällt eines weg,
    # rendert das Tool stumm Platzhalter statt Daten.
    for field in ("code", "label", "canton_code", "elevation", "type"):
        assert field in stations[0], f"Feld '{field}' fehlt in der SLF-Antwort"

    markdown = await env_snow_stations(SnowStationsInput(canton="GR"))
    assert f"– {len(stations)} Stationen" in markdown
    assert "| Code | Name | Kanton | Höhe (m) | Typ |" in markdown
    assert "| GR |" in markdown, "keine einzige Datenzeile gerendert"
    print(f"  ✅ Snow-Stations: {len(stations)} GR-Stationen gerendert")


async def test_avalanche_bulletin_tool() -> None:
    """env_avalanche_bulletin eigenständig (OPS-001).

    Wie oben ohne `_tool_text`: „Bulletin" stand vorher auch in der
    Fehlermeldung. Beide Saison-Zweige sind gültig — ausserhalb der Saison
    publiziert das SLF keins —, aber sie müssen unterscheidbar bleiben. Die
    Zweig-Logik selbst ist gemockt abgedeckt
    (`test_avalanche_bulletin_offseason_empty` / `..._winter_danger`); hier
    zählt, ob die echte Antwort in einem der beiden Zweige landet statt in der
    Fehlerbehandlung.
    """
    print("\n[Schnee] env_avalanche_bulletin — Tool eigenständig (OPS-001)")

    if SKIP_LIVE:
        print("  ⏭️  Live-Test übersprungen")
        return

    from swiss_environment_mcp.server import AvalancheBulletinInput, env_avalanche_bulletin

    result = await env_avalanche_bulletin(AvalancheBulletinInput(language="de"))
    assert result.startswith("## 🏔️ Lawinenbulletin SLF")
    assert "slf.ch/de/lawinenbulletin-und-schneesituation" in result

    if "**Aktuell kein aktives Lawinenbulletin.**" in result:
        assert "Mai–November" in result
        print("  ✅ Avalanche: kein aktives Bulletin (regulärer Saisonzyklus)")
        return

    assert "| Warnregion | Gefahrenstufe |" in result
    regions = [
        line
        for line in result.splitlines()
        if line.startswith("| ") and "Warnregion" not in line and not line.startswith("|--")
    ]
    assert regions, "Bulletin aktiv, aber keine Warnregion gerendert"
    assert " Warnregionen" in result
    print(f"  ✅ Avalanche: Bulletin aktiv, {len(regions)} Warnregionen")


async def test_hunting_stats() -> None:
    print("\n[Jagd] Eidg. Jagdstatistik — Rothirsch Abschuss Graubünden")

    if SKIP_LIVE:
        print("  ⏭️  Live-Test übersprungen")
        return

    from swiss_environment_mcp import api_client as api

    data = await api.fetch_jagd_statistics("1", "1", "GR")  # Rothirsch, Abschuss, GR
    check("Jagd: Chart-Daten gefunden (Schema-Guard)", data.get("found") is True)
    check("Jagd: Jahre vorhanden", len(data.get("years", [])) > 0)
    check("Jagd: Serien mit Werten", len(data.get("series", [])) > 0)


async def test_hydro_history() -> None:
    print("\n[Wasser] Historische Daten")

    result = await env_hydro_history(HydroHistoryInput(station_id="2099", days=7))
    check("Verlaufsdaten: Portal-Link vorhanden", "hydrodaten" in result)
    check("Verlaufsdaten: opendata.swiss erwähnt", "opendata.swiss" in result)


async def test_flood_warnings() -> None:
    print("\n[Wasser] Hochwasserwarnungen")

    if SKIP_LIVE:
        print("  ⏭️  Live-Test übersprungen")
        return

    result = await _tool_text(env_flood_warnings(FloodWarningsInput(min_level=1)))
    check("Warnungen: Kein Python-Traceback", "Traceback" not in result)
    check(
        "Warnungen: Link zu Hochwasser-Portal", "hydrodaten" in result or "Direktzugang" in result
    )

    # Stufe 5 = meist leer
    result_high = await _tool_text(env_flood_warnings(FloodWarningsInput(min_level=5)))
    check("Stufe 5: Rückmeldung vorhanden", len(result_high) > 20)


# --- Naturgefahren-Tests ------------------------------------------------------


async def test_hazard_overview() -> None:
    print("\n[Naturgefahren] Bulletin")

    if SKIP_LIVE:
        print("  ⏭️  Live-Test übersprungen")
        return

    result = await _tool_text(env_hazard_overview(HazardOverviewInput(language="de")))
    check("Bulletin: Kein Python-Traceback", "Traceback" not in result)
    check("Bulletin: naturgefahren.ch erwähnt", "naturgefahren.ch" in result)


async def test_hazard_regions() -> None:
    print("\n[Naturgefahren] Regionen")

    if SKIP_LIVE:
        print("  ⏭️  Live-Test übersprungen")
        return

    result = await _tool_text(env_hazard_regions(HazardRegionsInput(region="Zürich")))
    check("Zürich-Region: Kein Traceback", "Traceback" not in result)
    check("Zürich-Region: GIS-Link", "map.bafu.admin.ch" in result or "naturgefahren" in result)


async def test_wildfire_danger() -> None:
    print("\n[Naturgefahren] Waldbrand")

    if SKIP_LIVE:
        print("  ⏭️  Live-Test übersprungen")
        return

    result = await _tool_text(env_wildfire_danger(WildfireDangerInput(language="de")))
    check("Waldbrand: Kein Traceback", "Traceback" not in result)
    check("Waldbrand: Gefahrenstufen erklärt", "Gering" in result or "waldbrandgefahr" in result)


# --- Datenkatalog-Tests -------------------------------------------------------


async def test_bafu_datasets() -> None:
    print("\n[Datenkatalog] BAFU-Datensätze suchen")

    if SKIP_LIVE:
        print("  ⏭️  Live-Test übersprungen")
        return

    # Suche nach Luftqualität
    result = await _tool_text(env_bafu_datasets(BafuDatasetsInput(query="Luftqualität", rows=5)))
    check("Suche Luftqualität: Kein Traceback", "Traceback" not in result)
    check("Suche Luftqualität: Ergebnisse", "opendata.swiss" in result)

    # Leere Suche (alle BAFU-Datensätze)
    result_all = await _tool_text(env_bafu_datasets(BafuDatasetsInput(query="", rows=3)))
    check("Leere Suche: Rückmeldung", len(result_all) > 50)


async def test_bafu_dataset_detail() -> None:
    print("\n[Datenkatalog] Datensatz-Detail")

    if SKIP_LIVE:
        print("  ⏭️  Live-Test übersprungen")
        return

    result = await _tool_text(
        env_bafu_dataset_detail(
            BafuDatasetDetailInput(
                dataset_id="nationales-beobachtungsnetz-fur-luftfremdstoffe-nabel-stationen"
            )
        )
    )
    check("NABEL-Datensatz: Kein Traceback", "Traceback" not in result)
    check("NABEL-Datensatz: Ressourcen-Liste", "Ressourcen" in result or "opendata" in result)

    # Ungültige ID → terminaler ToolError (isError:true), Content nennt env_bafu_datasets
    result_invalid = await _tool_text(
        env_bafu_dataset_detail(BafuDatasetDetailInput(dataset_id="gibts-nicht-xyzabc"))
    )
    check("Ungültige ID: Fehlermeldung mit Hilfehinweis", "env_bafu_datasets" in result_invalid)


# --- Main ---------------------------------------------------------------------


async def main() -> None:
    print("=" * 60)
    print("swiss-environment-mcp – Integrationstests")
    print("=" * 60)

    # Ein ❌ bricht seinen Test ab (siehe `check`), nicht aber den Lauf: der
    # Standalone-Pfad soll das ganze Bild zeigen und am Ende bilanzieren.
    # Unter pytest scheitert derselbe Fehler regulär als FAILED.
    for test in (
        test_nabel_stations,
        test_nabel_current,
        test_air_limits,
        test_hydro_stations,
        test_hydro_current,
        test_hydro_history,
        test_hydro_current_lindas,
        test_bathing_water_lindas,
        test_slf_snow,
        test_snow_stations_tool,
        test_avalanche_bulletin_tool,
        test_hunting_stats,
        test_flood_warnings,
        test_hazard_overview,
        test_hazard_regions,
        test_wildfire_danger,
        test_bafu_datasets,
        test_bafu_dataset_detail,
    ):
        try:
            await test()
        except AssertionError:
            pass  # bereits als ❌ gedruckt und in `_fail` gezählt

    print("\n" + "=" * 60)
    total = _pass + _fail
    print(f"Ergebnis: {_pass}/{total} Tests bestanden")
    if _fail > 0:
        print(f"⚠️  {_fail} Test(s) fehlgeschlagen")
        sys.exit(1)
    else:
        print("✅ Alle Tests bestanden")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
