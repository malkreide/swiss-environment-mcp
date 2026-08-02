"""
20 Diverse Test-Szenarien fuer swiss-environment-mcp.

Diese Szenarien treffen echte BAFU-Live-APIs und sind daher als `live` markiert
(via `pytest -m "not live"` aus der CI ausgeschlossen). Sie werden sowohl von
pytest (`test_all_scenarios`) als auch als Standalone-Skript (`__main__`) ausgefuehrt.

Deckt ab:
  - Repraesentative Tools aus allen Clustern
  - Verschiedene Parameterkonstellationen
  - Edge Cases (ungueltige Eingaben, Grenzwerte, leere Filter)
  - Cross-Tool-Logik (Stationen finden -> Daten abrufen)
  - Mehrsprachigkeit
  - JSON- vs. Markdown-Ausgabe
  - Grenzwertpruefungen an kritischen Schwellen

Ausfuehrung:
    cd /tmp/swiss-environment-mcp
    python tests/test_20_scenarios.py
"""

import asyncio
import io
import json
import os
import sys
import traceback

# Fix Windows cp1252 encoding issues with Unicode output
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

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

# Szenarien treffen echte Live-APIs → als live markiert (CI: pytest -m "not live").
pytestmark = pytest.mark.live

_pass = 0
_fail = 0
_errors = []


def _safe(text):
    """Sanitize text for Windows console output."""
    if isinstance(text, str):
        return text.encode("ascii", "replace").decode()
    return str(text)


def check(scenario, name, condition, detail=""):
    global _pass, _fail
    if condition:
        print(f"    PASS: {name}")
        _pass += 1
    else:
        msg = f"    FAIL: {name}" + (f" -- {_safe(detail)}" if detail else "")
        print(msg)
        _fail += 1
        _errors.append(f"[{scenario}] {name}: {_safe(detail)}")


async def _tool_text(coro):
    """Tool-Output — oder, bei terminalem ToolError (isError:true seit OBS-001),
    dessen Meldung. Hält die Live-Szenarien robust gegenüber degradierten
    Upstreams (z.B. 301/404 von naturgefahren.ch / waldbrandgefahr.ch): der
    Fehler-Content trägt weiterhin die Recovery-Links, gegen die geprüft wird."""
    from mcp.server.mcpserver.exceptions import ToolError

    try:
        return await coro
    except ToolError as exc:
        return str(exc)


# =============================================================================
# SZENARIO 1: NABEL-Stationsliste - Vollstaendigkeit pruefen
# =============================================================================
async def scenario_01():
    """Alle 16 NABEL-Stationen in Markdown und JSON pruefen."""
    szenario = "S01-NABEL-Vollstaendigkeit"
    print(f"\n{'=' * 60}")
    print(f"  Szenario 1: {szenario}")
    print(f"{'=' * 60}")

    result = await env_nabel_stations(NabelStationsInput())

    all_codes = [
        "BAS",
        "BER",
        "DAV",
        "DUB",
        "HAE",
        "JUN",
        "LAE",
        "LAU",
        "LUG",
        "MAG",
        "PAY",
        "RIG",
        "SIO",
        "TAE",
        "ZUE",
        "ZUR",
    ]
    for code in all_codes:
        check(szenario, f"Station {code} in Markdown", code in result, "fehlt")

    result_json = await env_nabel_stations(NabelStationsInput(response_format=ResponseFormat.JSON))
    data = json.loads(result_json)
    # JSON nutzt seit v0.2.x den ResponseEnvelope (count/results statt total/nabel_stationen).
    check(szenario, "JSON: count=16", data.get("count") == 16, f"count={data.get('count')}")
    check(szenario, "JSON: Schluessel results", "results" in data)
    stations = data.get("results", [])
    check(szenario, "JSON: Jede Station hat name", all("name" in s for s in stations))
    # Kanton-Key kann 'canton' oder 'kanton' heissen
    check(
        szenario,
        "JSON: Jede Station hat Kanton-Info",
        all("canton" in s or "kanton" in s for s in stations),
        f"Erste Station Keys: {list(stations[0].keys()) if stations else 'leer'}",
    )


# =============================================================================
# SZENARIO 2: NABEL-Daten fuer Bergstation (Jungfraujoch)
# =============================================================================
async def scenario_02():
    """Daten einer extremen Bergstation - Jungfraujoch (3580 m)."""
    szenario = "S02-NABEL-Jungfraujoch"
    print(f"\n{'=' * 60}")
    print(f"  Szenario 2: {szenario}")
    print(f"{'=' * 60}")

    result = await env_nabel_current(NabelCurrentInput(station="JUN"))
    check(szenario, "Station JUN gefunden", "Jungfraujoch" in result, f"Inhalt: {result[:200]}")
    check(
        szenario, "Messparameter-Tabelle", "Parameter" in result or "NO" in result or "O3" in result
    )
    check(szenario, "BAFU-Link vorhanden", "bafu.admin.ch" in result)


# =============================================================================
# SZENARIO 3: NABEL - Lowercase-Eingabe + Tessin-Station
# =============================================================================
async def scenario_03():
    """Station Lugano mit Kleinschreibung -> Validator muss uppercase konvertieren."""
    szenario = "S03-NABEL-Lowercase-Lugano"
    print(f"\n{'=' * 60}")
    print(f"  Szenario 3: {szenario}")
    print(f"{'=' * 60}")

    result = await env_nabel_current(NabelCurrentInput(station="lug"))
    check(
        szenario,
        "Lugano erkannt (lowercase -> uppercase)",
        "Lugano" in result,
        f"Inhalt: {result[:200]}",
    )
    check(szenario, "Kanton TI erwaehnt", "TI" in result)


# =============================================================================
# SZENARIO 4: Ungueltige NABEL-Station - Fehlerbehandlung
# =============================================================================
async def scenario_04():
    """Ungueltiger Stationscode -> nuetzliche Fehlermeldung mit Stationsliste."""
    szenario = "S04-NABEL-Ungueltig"
    print(f"\n{'=' * 60}")
    print(f"  Szenario 4: {szenario}")
    print(f"{'=' * 60}")

    result = await env_nabel_current(NabelCurrentInput(station="FAKE"))
    check(
        szenario,
        "Fehlermeldung: nicht gefunden",
        "nicht gefunden" in result,
        f"Inhalt: {result[:200]}",
    )
    check(szenario, "Hilfe: Stationsliste angeboten", "ZUE" in result and "BAS" in result)


# =============================================================================
# SZENARIO 5: Grenzwertpruefung - exakt am Swiss-LRV-Grenzwert
# =============================================================================
async def scenario_05():
    """NO2 = 30.0 -> exakt LRV-Grenzwert -> Eingehalten (nicht ueberschritten)."""
    szenario = "S05-Grenzwert-exakt"
    print(f"\n{'=' * 60}")
    print(f"  Szenario 5: {szenario}")
    print(f"{'=' * 60}")

    result = await env_air_limits_check(AirLimitsCheckInput(pollutant="NO2", value=30.0))
    check(
        szenario,
        "NO2=30: LRV Eingehalten (Grenzwert nicht ueberschritten)",
        "Eingehalten" in result,
        f"Inhalt: {result[:300]}",
    )
    check(
        szenario,
        "NO2=30: WHO ueberschritten (WHO=10)",
        "BERSCHRITTEN" in result or "berschritten" in result.lower(),
    )


# =============================================================================
# SZENARIO 6: Grenzwertpruefung - alle 6 Schadstoffe
# =============================================================================
async def scenario_06():
    """Jeden unterstuetzten Schadstoff einzeln testen (hoher Wert -> ueberschritten)."""
    szenario = "S06-Alle-Schadstoffe"
    print(f"\n{'=' * 60}")
    print(f"  Szenario 6: {szenario}")
    print(f"{'=' * 60}")

    pollutants = {"NO2": 50, "PM10": 40, "PM2.5": 20, "O3": 150, "SO2": 60, "CO": 15000}
    for p, val in pollutants.items():
        result = await env_air_limits_check(AirLimitsCheckInput(pollutant=p, value=float(val)))
        check(szenario, f"{p}={val}: Antwort vorhanden", len(result) > 50, f"Laenge: {len(result)}")
        check(
            szenario,
            f"{p}={val}: LRV ueberschritten",
            "BERSCHRITTEN" in result or "berschritten" in result.lower(),
            f"Inhalt: {result[:150]}",
        )


# =============================================================================
# SZENARIO 7: Grenzwertpruefung - unbekannter Schadstoff
# =============================================================================
async def scenario_07():
    """Ungueltiger Schadstoff H2S -> Fehlermeldung mit gueltiger Liste."""
    szenario = "S07-Schadstoff-ungueltig"
    print(f"\n{'=' * 60}")
    print(f"  Szenario 7: {szenario}")
    print(f"{'=' * 60}")

    result = await env_air_limits_check(AirLimitsCheckInput(pollutant="H2S", value=10.0))
    check(
        szenario,
        "Fehlermeldung: nicht erkannt",
        "nicht erkannt" in result,
        f"Inhalt: {result[:200]}",
    )
    check(szenario, "Hilfe: gueltige Schadstoffe aufgelistet", "NO2" in result and "PM10" in result)


# =============================================================================
# SZENARIO 8: Hydro-Stationen nach Kanton filtern (Bern)
# =============================================================================
async def scenario_08():
    """Messstationen im Kanton BE - Filter testen."""
    szenario = "S08-Hydro-Kanton-BE"
    print(f"\n{'=' * 60}")
    print(f"  Szenario 8: {szenario}")
    print(f"{'=' * 60}")

    result = await env_hydro_stations(HydroStationsInput(canton="BE"))
    check(szenario, "Kein Python-Traceback", "Traceback" not in result)
    check(szenario, "Kanton BE in Filterinfo", "BE" in result)
    check(szenario, "hydrodaten.admin.ch Link", "hydrodaten" in result)


# =============================================================================
# SZENARIO 9: Hydro-Stationen nach Gewaesser filtern (Rhein)
# =============================================================================
async def scenario_09():
    """Gewaesserfilter Rhein - nur Rhein-Stationen."""
    szenario = "S09-Hydro-Rhein"
    print(f"\n{'=' * 60}")
    print(f"  Szenario 9: {szenario}")
    print(f"{'=' * 60}")

    result = await env_hydro_stations(HydroStationsInput(water_body="Rhein"))
    check(szenario, "Kein Traceback", "Traceback" not in result)
    check(
        szenario,
        "Rhein erwaehnt",
        "Rhein" in result or "rhein" in result.lower(),
        f"Inhalt: {result[:200]}",
    )


# =============================================================================
# SZENARIO 10: Hydro-Stationen in JSON-Format
# =============================================================================
async def scenario_10():
    """JSON-Ausgabe der Hydrostationen pruefen."""
    szenario = "S10-Hydro-JSON"
    print(f"\n{'=' * 60}")
    print(f"  Szenario 10: {szenario}")
    print(f"{'=' * 60}")

    result = await env_hydro_stations(HydroStationsInput(response_format=ResponseFormat.JSON))
    check(szenario, "Kein Traceback", "Traceback" not in result)
    try:
        data = json.loads(result)
        check(szenario, "JSON parsebar", True)
        check(
            szenario,
            "Enthaelt strukturierte Daten",
            isinstance(data, dict) and len(data) > 0,
            f"Schluessel: {list(data.keys())[:5]}",
        )
    except json.JSONDecodeError:
        # API kann 404 liefern -> Fallback auf Markdown mit Direktlinks
        check(
            szenario,
            "JSON oder Fallback-Antwort mit Links",
            "hydrodaten" in result or "Fehler" in result,
            f"Inhalt: {result[:200]}",
        )


# =============================================================================
# SZENARIO 11: Aktuelle Hydrodaten - Station Limmat Zuerich (2099)
# =============================================================================
async def scenario_11():
    """Aktuelle Messwerte der Limmat in Zuerich abrufen."""
    szenario = "S11-Hydro-Limmat-Aktuell"
    print(f"\n{'=' * 60}")
    print(f"  Szenario 11: {szenario}")
    print(f"{'=' * 60}")

    result = await _tool_text(env_hydro_current(HydroCurrentInput(station_id="2099")))
    check(szenario, "Kein Traceback", "Traceback" not in result)
    check(szenario, "Portal-Link vorhanden", "hydrodaten.admin.ch" in result)
    has_params = any(
        p in result
        for p in ["Pegel", "Abfluss", "Temperatur", "m3/s", "m/s", "Fehler", "hydrodaten"]
    )
    check(
        szenario,
        "Messparameter oder Fallback vorhanden",
        has_params,
        f"Inhalt: {result[:200].encode('ascii', 'replace').decode()}",
    )


# =============================================================================
# SZENARIO 12: Historische Hydrodaten - Temperatur, 3 Tage
# =============================================================================
async def scenario_12():
    """Historische Wassertemperatur der Limmat - 3 Tage."""
    szenario = "S12-Hydro-Historie-Temperatur"
    print(f"\n{'=' * 60}")
    print(f"  Szenario 12: {szenario}")
    print(f"{'=' * 60}")

    result = await env_hydro_history(
        HydroHistoryInput(station_id="2099", parameter="Temperatur", days=3)
    )
    check(szenario, "Kein Traceback", "Traceback" not in result)
    check(szenario, "Portal-Link", "hydrodaten" in result)
    check(szenario, "Datenportal erwaehnt", "opendata.swiss" in result or "hydrodaten" in result)


# =============================================================================
# SZENARIO 13: Hochwasserwarnungen - Stufe 1 (alle) + Stufe 5 (leer)
# =============================================================================
async def scenario_13():
    """Hochwasserwarnungen: alle Stufen vs. nur Stufe 5 (selten aktiv)."""
    szenario = "S13-Hochwasser-Stufen"
    print(f"\n{'=' * 60}")
    print(f"  Szenario 13: {szenario}")
    print(f"{'=' * 60}")

    result_all = await _tool_text(env_flood_warnings(FloodWarningsInput(min_level=1)))
    check(szenario, "Stufe 1: Kein Traceback", "Traceback" not in result_all)
    check(szenario, "Stufe 1: Antwort > 20 Zeichen", len(result_all) > 20)

    result_5 = await _tool_text(env_flood_warnings(FloodWarningsInput(min_level=5)))
    check(szenario, "Stufe 5: Kein Traceback", "Traceback" not in result_5)
    check(szenario, "Stufe 5: Rueckmeldung vorhanden", len(result_5) > 20)


# =============================================================================
# SZENARIO 14: Hochwasserwarnungen nach Kanton filtern
# =============================================================================
async def scenario_14():
    """Hochwasserwarnungen nur fuer den Kanton Graubuenden."""
    szenario = "S14-Hochwasser-Kanton-GR"
    print(f"\n{'=' * 60}")
    print(f"  Szenario 14: {szenario}")
    print(f"{'=' * 60}")

    result = await _tool_text(env_flood_warnings(FloodWarningsInput(min_level=1, canton="GR")))
    check(szenario, "Kein Traceback", "Traceback" not in result)
    check(szenario, "Antwort nicht leer", len(result) > 20)
    check(
        szenario,
        "GR erwaehnt oder keine Warnungen",
        "GR" in result or "keine" in result.lower() or "Keine" in result or "Fehler" in result,
        f"Inhalt: {result[:200].encode('ascii', 'replace').decode()}",
    )


# =============================================================================
# SZENARIO 15: Naturgefahren-Bulletin in 4 Sprachen
# =============================================================================
async def scenario_15():
    """Bulletin in de, fr, it, en - alle muessen antworten."""
    szenario = "S15-Bulletin-Mehrsprachig"
    print(f"\n{'=' * 60}")
    print(f"  Szenario 15: {szenario}")
    print(f"{'=' * 60}")

    for lang in ["de", "fr", "it", "en"]:
        result = await _tool_text(env_hazard_overview(HazardOverviewInput(language=lang)))
        check(szenario, f"Sprache {lang}: Kein Traceback", "Traceback" not in result)
        check(
            szenario,
            f"Sprache {lang}: Antwort > 50 Zeichen",
            len(result) > 50,
            f"Laenge: {len(result)}",
        )


# =============================================================================
# SZENARIO 16: Regionale Naturgefahren - Graubuenden + Lawinenfilter
# =============================================================================
async def scenario_16():
    """Regionale Warnungen fuer Graubuenden, gefiltert auf Lawinen."""
    szenario = "S16-Gefahren-GR-Lawinen"
    print(f"\n{'=' * 60}")
    print(f"  Szenario 16: {szenario}")
    print(f"{'=' * 60}")

    result = await _tool_text(
        env_hazard_regions(
            HazardRegionsInput(region="Graubuenden", hazard_type="lawinen", language="de")
        )
    )
    check(szenario, "Kein Traceback", "Traceback" not in result)
    check(szenario, "Antwort vorhanden", len(result) > 30)
    check(
        szenario,
        "Relevanter Inhalt",
        "naturgefahren" in result
        or "map.bafu" in result
        or "Graub" in result
        or "Warnung" in result,
        f"Inhalt: {result[:200]}",
    )


# =============================================================================
# SZENARIO 17: Waldbrandgefahr - Kanton Wallis (VS)
# =============================================================================
async def scenario_17():
    """Waldbrandgefahr im Kanton Wallis (haeufig erhoeht im Sommer)."""
    szenario = "S17-Waldbrand-VS"
    print(f"\n{'=' * 60}")
    print(f"  Szenario 17: {szenario}")
    print(f"{'=' * 60}")

    result = await _tool_text(env_wildfire_danger(WildfireDangerInput(language="de", canton="VS")))
    check(szenario, "Kein Traceback", "Traceback" not in result)
    check(szenario, "Antwort vorhanden", len(result) > 30)
    has_content = any(
        w in result
        for w in ["Gering", "Maessig", "Erheblich", "Gross", "waldbrandgefahr", "Wallis", "VS"]
    )
    check(szenario, "Relevanter Inhalt (Stufe oder Kanton)", has_content, f"Inhalt: {result[:200]}")


# =============================================================================
# SZENARIO 18: Waldbrandgefahr auf Franzoesisch
# =============================================================================
async def scenario_18():
    """Waldbrandgefahr in Franzoesisch abfragen."""
    szenario = "S18-Waldbrand-FR"
    print(f"\n{'=' * 60}")
    print(f"  Szenario 18: {szenario}")
    print(f"{'=' * 60}")

    result = await _tool_text(env_wildfire_danger(WildfireDangerInput(language="fr")))
    check(szenario, "Kein Traceback", "Traceback" not in result)
    check(szenario, "Antwort vorhanden", len(result) > 30)


# =============================================================================
# SZENARIO 19: BAFU-Datenkatalog - Biodiversitaet suchen + Pagination
# =============================================================================
async def scenario_19():
    """Datensatz-Suche: Biodiversitaet mit 3 Ergebnissen, dann Offset=3."""
    szenario = "S19-Datenkatalog-Suche"
    print(f"\n{'=' * 60}")
    print(f"  Szenario 19: {szenario}")
    print(f"{'=' * 60}")

    result = await _tool_text(env_bafu_datasets(BafuDatasetsInput(query="Biodiversitaet", rows=3)))
    check(szenario, "Kein Traceback", "Traceback" not in result)
    check(szenario, "opendata.swiss erwaehnt", "opendata.swiss" in result)
    check(szenario, "Ergebnisse vorhanden", len(result) > 100, f"Laenge: {len(result)}")

    # Pagination: Offset 3
    result_page2 = await _tool_text(
        env_bafu_datasets(BafuDatasetsInput(query="Biodiversitaet", rows=3, offset=3))
    )
    check(szenario, "Pagination: Kein Traceback", "Traceback" not in result_page2)
    check(szenario, "Pagination: Antwort vorhanden", len(result_page2) > 50)


# =============================================================================
# SZENARIO 20: Datensatz-Detail - NABEL + ungueltige ID
# =============================================================================
async def scenario_20():
    """Detailabruf des NABEL-Datensatzes + Fehlerbehandlung bei ungueltiger ID."""
    szenario = "S20-Datensatz-Detail"
    print(f"\n{'=' * 60}")
    print(f"  Szenario 20: {szenario}")
    print(f"{'=' * 60}")

    result = await _tool_text(
        env_bafu_dataset_detail(
            BafuDatasetDetailInput(
                dataset_id="nationales-beobachtungsnetz-fur-luftfremdstoffe-nabel-stationen"
            )
        )
    )
    check(szenario, "NABEL-Datensatz: Kein Traceback", "Traceback" not in result)
    check(
        szenario,
        "NABEL-Datensatz: Ressourcen erwaehnt",
        "Ressourcen" in result or "ressource" in result.lower() or "opendata" in result,
    )
    check(szenario, "NABEL-Datensatz: Download-URL(s)", "http" in result)

    # Ungueltige ID → seit OBS-001 ein terminaler ToolError (isError:true),
    # dessen Content weiterhin den Bezug zu env_bafu_datasets enthaelt.
    from mcp.server.mcpserver.exceptions import ToolError

    try:
        await env_bafu_dataset_detail(
            BafuDatasetDetailInput(dataset_id="non-existent-dataset-xyz-12345")
        )
        check(szenario, "Ungueltige ID: ToolError erwartet", False, "kein Fehler geworfen")
    except ToolError as exc:
        msg = str(exc)
        check(
            szenario,
            "Ungueltige ID: Fehlermeldung",
            "nicht gefunden" in msg or "env_bafu_datasets" in msg,
            f"Inhalt: {msg[:200]}",
        )


# =============================================================================
# MAIN
# =============================================================================

_SCENARIOS = [
    scenario_01,
    scenario_02,
    scenario_03,
    scenario_04,
    scenario_05,
    scenario_06,
    scenario_07,
    scenario_08,
    scenario_09,
    scenario_10,
    scenario_11,
    scenario_12,
    scenario_13,
    scenario_14,
    scenario_15,
    scenario_16,
    scenario_17,
    scenario_18,
    scenario_19,
    scenario_20,
]


async def test_all_scenarios():
    """pytest-Einstieg (live): führt alle 20 Szenarien aus, erwartet 0 Fehl-Checks."""
    global _pass, _fail, _errors
    _pass, _fail, _errors = 0, 0, []
    for i, scenario_fn in enumerate(_SCENARIOS, 1):
        await scenario_fn()
    assert _fail == 0, f"{_fail} Szenario-Check(s) fehlgeschlagen: {_errors}"


async def main():
    print("=" * 60)
    print("  swiss-environment-mcp -- 20 Testszenarien")
    print("=" * 60)

    scenarios = _SCENARIOS

    for i, scenario_fn in enumerate(scenarios, 1):
        try:
            await scenario_fn()
        except Exception as e:
            print(f"\n  !!! Szenario {i} hat eine Exception geworfen:")
            traceback.print_exc()
            _errors.append(f"[S{i:02d}] EXCEPTION: {e}")

    print("\n" + "=" * 60)
    total = _pass + _fail
    print(f"  Ergebnis: {_pass}/{total} Checks bestanden")
    if _fail > 0:
        print(f"  WARNUNG: {_fail} Check(s) fehlgeschlagen:")
        for err in _errors:
            print(f"    -> {err}")
        sys.exit(1)
    else:
        print("  ALLE 20 Szenarien bestanden!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
