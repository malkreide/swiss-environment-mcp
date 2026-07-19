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

# Diese Datei trifft echte BAFU-Live-APIs. Alle hier gesammelten Tests werden
# als `live` markiert und in der Standard-CI via `pytest -m "not live"`
# übersprungen (Audit OPS-001). Mocked Unit-Tests siehe tests/test_unit.py.
pytestmark = pytest.mark.live

# Lokales Paket importieren
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from swiss_environment_mcp.server import (
    AirLimitsCheckInput,
    BafuDatasetsInput,
    BafuDatasetDetailInput,
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
    global _pass, _fail
    if condition:
        print(f"  ✅ {name}")
        _pass += 1
    else:
        print(f"  ❌ {name}" + (f": {detail}" if detail else ""))
        _fail += 1


# --- Luft-Tests ---------------------------------------------------------------


async def test_nabel_stations() -> None:
    print("\n[Luft] NABEL-Stationen")

    # Markdown
    result = await env_nabel_stations(NabelStationsInput())
    check("Enthält Tabellenheader", "| Kürzel |" in result)
    check("Enthält ZUE (Zürich-Kaserne)", "ZUE" in result)
    check("Enthält DUB (Dübendorf)", "DUB" in result)
    check("Link zu BAFU vorhanden", "bafu.admin.ch" in result)

    # JSON
    result_json = await env_nabel_stations(NabelStationsInput(response_format=ResponseFormat.JSON))
    data = json.loads(result_json)
    check("JSON: 16 Stationen", data.get("total") == 16)
    check("JSON: nabel_stationen vorhanden", "nabel_stationen" in data)


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
    result = await env_hydro_current(HydroCurrentInput(station_id="2099"))
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

    result = await env_flood_warnings(FloodWarningsInput(min_level=1))
    check("Warnungen: Kein Python-Traceback", "Traceback" not in result)
    check("Warnungen: Link zu Hochwasser-Portal", "hydrodaten" in result or "Direktzugang" in result)

    # Stufe 5 = meist leer
    result_high = await env_flood_warnings(FloodWarningsInput(min_level=5))
    check("Stufe 5: Rückmeldung vorhanden", len(result_high) > 20)


# --- Naturgefahren-Tests ------------------------------------------------------


async def test_hazard_overview() -> None:
    print("\n[Naturgefahren] Bulletin")

    if SKIP_LIVE:
        print("  ⏭️  Live-Test übersprungen")
        return

    result = await env_hazard_overview(HazardOverviewInput(language="de"))
    check("Bulletin: Kein Python-Traceback", "Traceback" not in result)
    check("Bulletin: naturgefahren.ch erwähnt", "naturgefahren.ch" in result)


async def test_hazard_regions() -> None:
    print("\n[Naturgefahren] Regionen")

    if SKIP_LIVE:
        print("  ⏭️  Live-Test übersprungen")
        return

    result = await env_hazard_regions(HazardRegionsInput(region="Zürich"))
    check("Zürich-Region: Kein Traceback", "Traceback" not in result)
    check("Zürich-Region: GIS-Link", "map.bafu.admin.ch" in result or "naturgefahren" in result)


async def test_wildfire_danger() -> None:
    print("\n[Naturgefahren] Waldbrand")

    if SKIP_LIVE:
        print("  ⏭️  Live-Test übersprungen")
        return

    result = await env_wildfire_danger(WildfireDangerInput(language="de"))
    check("Waldbrand: Kein Traceback", "Traceback" not in result)
    check("Waldbrand: Gefahrenstufen erklärt", "Gering" in result or "waldbrandgefahr" in result)


# --- Datenkatalog-Tests -------------------------------------------------------


async def test_bafu_datasets() -> None:
    print("\n[Datenkatalog] BAFU-Datensätze suchen")

    if SKIP_LIVE:
        print("  ⏭️  Live-Test übersprungen")
        return

    # Suche nach Luftqualität
    result = await env_bafu_datasets(BafuDatasetsInput(query="Luftqualität", rows=5))
    check("Suche Luftqualität: Kein Traceback", "Traceback" not in result)
    check("Suche Luftqualität: Ergebnisse", "opendata.swiss" in result)

    # Leere Suche (alle BAFU-Datensätze)
    result_all = await env_bafu_datasets(BafuDatasetsInput(query="", rows=3))
    check("Leere Suche: Rückmeldung", len(result_all) > 50)


async def test_bafu_dataset_detail() -> None:
    print("\n[Datenkatalog] Datensatz-Detail")

    if SKIP_LIVE:
        print("  ⏭️  Live-Test übersprungen")
        return

    result = await env_bafu_dataset_detail(
        BafuDatasetDetailInput(
            dataset_id="nationales-beobachtungsnetz-fur-luftfremdstoffe-nabel-stationen"
        )
    )
    check("NABEL-Datensatz: Kein Traceback", "Traceback" not in result)
    check("NABEL-Datensatz: Ressourcen-Liste", "Ressourcen" in result or "opendata" in result)

    # Ungültige ID
    result_invalid = await env_bafu_dataset_detail(
        BafuDatasetDetailInput(dataset_id="gibts-nicht-xyzabc")
    )
    check("Ungültige ID: Fehlermeldung mit Hilfehinweis", "env_bafu_datasets" in result_invalid)


# --- Main ---------------------------------------------------------------------


async def main() -> None:
    print("=" * 60)
    print("swiss-environment-mcp – Integrationstests")
    print("=" * 60)

    await test_nabel_stations()
    await test_nabel_current()
    await test_air_limits()
    await test_hydro_stations()
    await test_hydro_current()
    await test_hydro_history()
    await test_hydro_current_lindas()
    await test_slf_snow()
    await test_hunting_stats()
    await test_flood_warnings()
    await test_hazard_overview()
    await test_hazard_regions()
    await test_wildfire_danger()
    await test_bafu_datasets()
    await test_bafu_dataset_detail()

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
