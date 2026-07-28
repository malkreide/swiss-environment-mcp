"""
Mocked Unit-Tests für die Fluglärm-Erweiterung (BAZL-Lärmbelastungskataster).

Laufen ohne Netzwerk (respx). Die Live-Tests gegen `api3.geo.admin.ch` stehen
am Ende dieser Datei unter dem Marker `live` und sind aus der CI ausgeschlossen
(`pytest -m "not live"`).

Die Fixtures bilden die echten Antwortformen aus der Live-Probe vom 28.07.2026
nach (siehe `docs/probe-fluglaerm.md`) — insbesondere `exposurecurve_level_db`
als **String**, nicht als Zahl.
"""

import os
import sys

import httpx
import pytest
import respx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from swiss_environment_mcp import api_client as api  # noqa: E402
from swiss_environment_mcp import geoadmin  # noqa: E402
from swiss_environment_mcp.server import (  # noqa: E402
    NoiseAircraftAtInput,
    NoiseAircraftRegistersInput,
    NoiseLimitsCheckInput,
    ResponseFormat,
    env_noise_aircraft_at_impl,
    env_noise_aircraft_registers_impl,
    env_noise_limits_check_impl,
)

IDENTIFY = geoadmin.IDENTIFY_URL


@pytest.fixture(autouse=True)
async def _reset_client(monkeypatch):
    """Frischer Client je Test; DNS-Pinning aus, Retry-Delay auf 0."""
    api.dns_pin_enabled = False
    monkeypatch.setattr(api, "GEOADMIN_RETRY_BASE_DELAY", 0)
    await api.shutdown()
    yield
    await api.shutdown()
    api.dns_pin_enabled = True


def _feature(level: str, register: str = "LBK Zürich", fid: int = 1) -> dict:
    """Ein identify-Treffer in der Form, die der Dienst tatsächlich liefert."""
    return {
        "layerBodId": f"{geoadmin.LAYER_PREFIX}_klein-grossflugzeuge",
        "featureId": fid,
        "properties": {
            "noisepollutionregister_validity_validfrom": "03.07.2015",
            "noisepollutionregister_registername": register,
            "noisepollutionregister_editor": "Bundesamt für Zivilluftfahrt BAZL",
            "exposuregroup_exposuretype": "OverallTrafficDay_Lr",
            # STRING, nicht Zahl — Fundstück 4 der Probe.
            "exposurecurve_level_db": level,
            "noisepollutionregister_documentlink": (
                "https://www.bazl.admin.ch/dam/de/sd-web/lxjT5Vru736V/zuerich.pdf"
            ),
            "label": level,
        },
    }


def _resp(*levels: str) -> httpx.Response:
    feats = [_feature(lv, fid=i) for i, lv in enumerate(levels)]
    return httpx.Response(200, json={"results": feats})


# --- LV95-Validator -----------------------------------------------------------


def test_wgs84_input_fails_fast_with_conversion_hint():
    """Der häufigste LLM-Fehler: WGS84-Grad statt LV95-Meter."""
    with pytest.raises(Exception) as exc:
        NoiseAircraftAtInput(east=8.54, north=47.37)
    msg = str(exc.value)
    assert "WGS84" in msg
    assert "LV95" in msg
    assert "REFRAME" in msg or "convert_coordinates" in msg


def test_coordinates_outside_switzerland_rejected():
    with pytest.raises(Exception) as exc:
        NoiseAircraftAtInput(east=3_000_000, north=1_200_000)
    assert "ausserhalb der Schweiz" in str(exc.value)


def test_swapped_axes_rejected():
    """Vertauschte Achsen: north im Ostwert-Bereich."""
    with pytest.raises(Exception) as exc:
        NoiseAircraftAtInput(east=1_247_993, north=2_683_146)
    assert "ausserhalb der Schweiz" in str(exc.value)


def test_valid_lv95_accepted():
    p = NoiseAircraftAtInput(east=2685000, north=1258000)
    assert (p.east, p.north) == (2685000, 1258000)
    assert p.period == "day"
    assert p.radius_m == geoadmin.DEFAULT_RADIUS_M


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("62", 62.0),
        ("62.5", 62.5),
        ("62,5", 62.5),
        ("65 dB", 65.0),
        (61, 61.0),
        (None, None),
        ("", None),
        ("k.A.", None),
    ],
)
def test_clean_level_db_normalises_strings(raw, expected):
    """dB-Werte kommen als String — zentral zu float normalisieren."""
    assert geoadmin.clean_level_db(raw) == expected


def test_clean_level_db_prevents_string_sorting_bug():
    """'9' > '62' als String — nach Normalisierung stimmt die Ordnung."""
    values = [geoadmin.clean_level_db(v) for v in ("9", "62", "71")]
    assert max(values) == 71.0


# --- Happy Path ---------------------------------------------------------------


@respx.mock
async def test_aircraft_at_happy_path_returns_bracket():
    """Zwei nahe Kurven → Klammer 61–62 dB, höchster Wert als obere Schranke."""
    respx.get(IDENTIFY).mock(return_value=_resp("62", "61"))
    out = await env_noise_aircraft_at_impl(
        NoiseAircraftAtInput(east=2685000, north=1258000, response_format=ResponseFormat.JSON)
    )
    assert '"provenance": "live_api"' in out
    assert '"level_db": 62.0' in out
    assert '"level_db_lower": 61.0' in out
    assert '"resolution": "bracketed"' in out
    # source_freshness trägt das validfrom, behauptet nie «live».
    assert "03.07.2015" in out
    assert "live" not in out.split('"source_freshness"')[1].split(",")[0].replace("live_api", "")
    assert "Orientierungsgrundlage" in out  # Rechtshinweis in JEDER Response


@respx.mock
async def test_aircraft_at_markdown_carries_legal_notice_and_provenance():
    respx.get(IDENTIFY).mock(return_value=_resp("62", "61"))
    out = await env_noise_aircraft_at_impl(NoiseAircraftAtInput(east=2685000, north=1258000))
    assert "Rechtlicher Hinweis" in out
    assert "Baubewilligungsabklärung" in out
    assert "`live_api`" in out
    assert "Stand der Grundlage" in out
    assert "62 dB" in out


@respx.mock
async def test_aircraft_at_sends_lv95_and_correct_layer():
    route = respx.get(IDENTIFY).mock(return_value=_resp("62"))
    await env_noise_aircraft_at_impl(
        NoiseAircraftAtInput(east=2685000, north=1258000, period="night_first")
    )
    params = route.calls[0].request.url.params
    assert params["sr"] == "2056"
    assert params["geometry"] == "2685000,1258000"
    # Layer-ID MUSS den Sublayer-Suffix tragen (Basis-ID → HTTP 400).
    assert params["layers"] == f"all:{geoadmin.LAYER_PREFIX}_erste-nachtstunde"
    assert params["geometryType"] == "esriGeometryPoint"


@respx.mock
async def test_duplicate_curve_segments_are_deduped():
    """Eine Isolinie kann in mehreren Segmenten kommen — es zählt die Kurve."""
    respx.get(IDENTIFY).mock(
        return_value=httpx.Response(
            200,
            json={"results": [_feature("62", fid=1), _feature("62", fid=2), _feature("61", fid=3)]},
        )
    )
    out = await env_noise_aircraft_at_impl(
        NoiseAircraftAtInput(east=2685000, north=1258000, response_format=ResponseFormat.JSON)
    )
    assert '"curves_found": 2' in out


# --- Null-Treffer: die Zweideutigkeit auflösen --------------------------------


@respx.mock
async def test_no_hits_anywhere_yields_speaking_result_not_empty_list():
    """Chur-Fall: kein Kataster — sprechendes Ergebnis, nie ein stilles []."""
    respx.get(IDENTIFY).mock(return_value=httpx.Response(200, json={"results": []}))
    out = await env_noise_aircraft_at_impl(NoiseAircraftAtInput(east=2759500, north=1191000))
    assert "Kein Lärmbelastungskataster an diesem Standort" in out
    assert "gültiges Ergebnis, kein Abruffehler" in out


@respx.mock
async def test_no_hits_nearby_but_hits_far_is_not_reported_as_no_cadastre():
    """Pistenfall: r=100 m leer, r=1000 m voll → NICHT «kein Kataster»."""
    responses = [
        httpx.Response(200, json={"results": []}),
        _resp("75", "74", "73"),
    ]
    respx.get(IDENTIFY).mock(side_effect=responses)
    out = await env_noise_aircraft_at_impl(
        NoiseAircraftAtInput(east=2683600, north=1256800, response_format=ResponseFormat.JSON)
    )
    assert '"resolution": "wide_area_only"' in out
    assert '"level_db": 75.0' in out
    assert '"search_radius_m": 1000' in out
    assert "Kein Lärmbelastungskataster" not in out


# --- Resilienz ----------------------------------------------------------------


@respx.mock
async def test_retry_on_503_then_success():
    """5xx wird wiederholt (Backoff im Test auf 0)."""
    route = respx.get(IDENTIFY).mock(
        side_effect=[httpx.Response(503), httpx.Response(503), _resp("62")]
    )
    out = await env_noise_aircraft_at_impl(
        NoiseAircraftAtInput(east=2685000, north=1258000, response_format=ResponseFormat.JSON)
    )
    assert route.call_count == 3
    assert '"level_db": 62.0' in out


@respx.mock
async def test_timeout_degrades_gracefully_without_stacktrace():
    respx.get(IDENTIFY).mock(side_effect=httpx.TimeoutException("timeout"))
    out = await env_noise_aircraft_at_impl(
        NoiseAircraftAtInput(east=2685000, north=1258000, response_format=ResponseFormat.JSON)
    )
    assert '"status": "degraded"' in out
    assert "Traceback" not in out
    assert "Timeout" in out or "timeout" in out.lower()
    # Der Rechtshinweis fehlt auch im Degradationsfall nicht.
    assert "Orientierungsgrundlage" in out


@respx.mock
async def test_degraded_envelope_reports_last_successful_fetch():
    respx.get(IDENTIFY).mock(return_value=_resp("62"))
    await env_noise_aircraft_at_impl(NoiseAircraftAtInput(east=2685000, north=1258000))
    respx.get(IDENTIFY).mock(side_effect=httpx.ConnectError("down"))
    out = await env_noise_aircraft_at_impl(
        NoiseAircraftAtInput(east=2685000, north=1258000, response_format=ResponseFormat.JSON)
    )
    assert '"status": "degraded"' in out
    assert '"last_success"' in out


@respx.mock
async def test_http_400_on_invalid_layer_is_not_retried():
    """Basis-ID ohne Sublayer-Suffix → HTTP 400, deterministisch, kein Retry."""
    route = respx.get(IDENTIFY).mock(return_value=httpx.Response(400, text="Bad Request"))
    out = await env_noise_aircraft_at_impl(
        NoiseAircraftAtInput(east=2685000, north=1258000, response_format=ResponseFormat.JSON)
    )
    assert route.call_count == 1  # kein Retry auf 4xx
    assert '"status": "degraded"' in out
    assert "400" in out


async def test_base_layer_id_without_suffix_is_never_constructed():
    """Regressionsschutz zu Fundstück 5: jede Periode trägt einen Suffix."""
    for name, spec in geoadmin.PERIODS.items():
        assert spec.layer != geoadmin.LAYER_PREFIX, name
        assert spec.layer.startswith(f"{geoadmin.LAYER_PREFIX}_"), name


@respx.mock
async def test_egress_allow_list_covers_geoadmin():
    api.assert_host_allowed(IDENTIFY)
    with pytest.raises(api.SecurityError):
        api.assert_host_allowed("https://evil.example.com/rest/identify")


# --- Registerübersicht --------------------------------------------------------


@respx.mock
async def test_registers_lists_validity_dates_and_pdf_links():
    respx.get(IDENTIFY).mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    _feature("62", register="LBK Zürich", fid=1),
                    _feature("61", register="LBK Zürich", fid=2),
                    _feature("55", register="CDB Genève", fid=3),
                ]
            },
        )
    )
    out = await env_noise_aircraft_registers_impl(
        NoiseAircraftRegistersInput(period="day", response_format=ResponseFormat.JSON)
    )
    assert "LBK Zürich" in out and "CDB Genève" in out
    assert "03.07.2015" in out
    assert "zuerich.pdf" in out
    assert '"count": 2' in out


@respx.mock
async def test_registers_queries_all_eight_sublayers_without_filter():
    route = respx.get(IDENTIFY).mock(return_value=httpx.Response(200, json={"results": []}))
    await env_noise_aircraft_registers_impl(NoiseAircraftRegistersInput())
    assert route.call_count == len(geoadmin.PERIODS) == 8


@respx.mock
async def test_registers_uses_envelope_over_switzerland():
    route = respx.get(IDENTIFY).mock(return_value=httpx.Response(200, json={"results": []}))
    await env_noise_aircraft_registers_impl(NoiseAircraftRegistersInput(period="day"))
    params = route.calls[0].request.url.params
    assert params["geometryType"] == "esriGeometryEnvelope"
    assert params["geometry"] == geoadmin.CH_ENVELOPE


def test_oldest_valid_from_picks_earliest_swiss_date():
    entries = [
        {"valid_from": "16.04.2024"},
        {"valid_from": "01.03.2009"},
        {"valid_from": "03.07.2015"},
    ]
    assert geoadmin.oldest_valid_from(entries) == "01.03.2009"


# --- LSV-Grenzwerte (Anhang 5) ------------------------------------------------


@pytest.mark.parametrize(
    "es,expected",
    [("I", (53, 55, 60)), ("II", (57, 60, 65)), ("III", (60, 65, 70)), ("IV", (65, 70, 75))],
)
def test_lsv_day_values_match_annex_5_ziff_221(es, expected):
    r = geoadmin.check_limits(0.0, es, "day")
    assert tuple(int(t["limit_db"]) for t in r["thresholds"]) == expected
    assert r["legal_reference"]["citation"] == "Anhang 5 Ziff. 221 LSV"


@pytest.mark.parametrize(
    "es,expected",
    [("I", (43, 45, 55)), ("II", (47, 50, 60)), ("III", (50, 55, 65)), ("IV", (55, 60, 70))],
)
def test_lsv_night_values_match_annex_5_ziff_222(es, expected):
    r = geoadmin.check_limits(0.0, es, "night_second")
    assert tuple(int(t["limit_db"]) for t in r["thresholds"]) == expected


def test_first_night_hour_uses_higher_values_for_es_ii_only():
    """Die Fussnote zu Ziff. 222 betrifft ausschliesslich ES II."""
    first = geoadmin.check_limits(0.0, "II", "night_first")
    other = geoadmin.check_limits(0.0, "II", "night_second")
    assert [t["limit_db"] for t in first["thresholds"]] == [50, 55, 65]
    assert [t["limit_db"] for t in other["thresholds"]] == [47, 50, 60]
    for es in ("I", "III", "IV"):
        a = [t["limit_db"] for t in geoadmin.check_limits(0.0, es, "night_first")["thresholds"]]
        b = [t["limit_db"] for t in geoadmin.check_limits(0.0, es, "night_second")["thresholds"]]
        assert a == b, f"ES {es} darf sich zwischen den Nachtstunden nicht unterscheiden"


def test_light_aircraft_uses_ziff_21_and_helicopter_max_ziff_23():
    assert geoadmin.check_limits(0.0, "II", "light_aircraft")["legal_reference"]["citation"] == (
        "Anhang 5 Ziff. 21 LSV"
    )
    assert geoadmin.check_limits(0.0, "II", "helicopter_max")["legal_reference"]["citation"] == (
        "Anhang 5 Ziff. 23 LSV"
    )


def test_military_refuses_instead_of_applying_wrong_annex():
    """Anhang 5 gilt nur für zivile Flugplätze — lieber keine als falsche Auskunft."""
    with pytest.raises(geoadmin.LimitsUnavailableError) as exc:
        geoadmin.check_limits(70.0, "II", "military")
    assert "Anhang 8" in str(exc.value)


def test_limits_check_tool_reports_military_refusal_gracefully():
    out = env_noise_limits_check_impl(
        NoiseLimitsCheckInput(level_db=70, sensitivity_level="II", period="military")
    )
    assert "Keine Grenzwerte anwendbar" in out
    assert "Anhang 8" in out


def test_exceedance_detection_and_severity():
    r = geoadmin.check_limits(72.0, "II", "day")
    assert [t["exceeded"] for t in r["thresholds"]] == [True, True, True]
    assert r["severity"] == "alarm_value"
    r2 = geoadmin.check_limits(50.0, "II", "day")
    assert [t["exceeded"] for t in r2["thresholds"]] == [False, False, False]
    assert r2["severity"] == "ok"


def test_boundary_value_is_not_an_exceedance():
    """Genau auf dem Grenzwert ist keine Überschreitung (Art. 15 USG: «überschreiten»)."""
    r = geoadmin.check_limits(60.0, "II", "day")
    immission = next(t for t in r["thresholds"] if t["key"] == "immission_limit")
    assert immission["limit_db"] == 60.0
    assert immission["exceeded"] is False


@pytest.mark.parametrize("raw", ["II", "ii", "ES II", "es-ii", "2"])
def test_sensitivity_level_normalisation(raw):
    assert geoadmin.normalise_sensitivity(raw) == "II"


def test_unknown_sensitivity_level_rejected():
    with pytest.raises(ValueError) as exc:
        geoadmin.normalise_sensitivity("V")
    assert "ES I–IV" in str(exc.value)


def test_limits_check_carries_legal_reference_and_no_network():
    out = env_noise_limits_check_impl(
        NoiseLimitsCheckInput(
            level_db=62,
            sensitivity_level="II",
            period="day",
            response_format=ResponseFormat.JSON,
        )
    )
    assert "SR 814.41" in out
    assert "Anhang 5" in out
    assert "01.04.2026" in out  # Fassung
    assert "2026-07-28" in out  # Abrufdatum der Verifikation
    assert "Orientierungsgrundlage" in out


# --- Live-Tests (aus der CI ausgeschlossen) -----------------------------------


@pytest.mark.live
async def test_live_kloten_returns_curves():
    p = NoiseAircraftAtInput(east=2685000, north=1258000, response_format=ResponseFormat.JSON)
    out = await env_noise_aircraft_at_impl(p)
    assert '"found": true' in out
    assert "LBK Zürich" in out


@pytest.mark.live
async def test_live_chur_has_no_cadastre():
    p = NoiseAircraftAtInput(east=2759500, north=1191000)
    out = await env_noise_aircraft_at_impl(p)
    assert "Kein Lärmbelastungskataster an diesem Standort" in out


@pytest.mark.live
async def test_live_all_eight_sublayers_are_identifiable():
    """Jeder Sublayer muss HTTP 200 liefern (nicht 400)."""
    for period in geoadmin.PERIODS:
        entries = await api.fetch_aircraft_noise_registers(period)
        assert entries, f"Sublayer '{period}' lieferte keine Register"


@pytest.mark.live
async def test_live_registers_span_multiple_validity_dates():
    out = await env_noise_aircraft_registers_impl(
        NoiseAircraftRegistersInput(period="day", response_format=ResponseFormat.JSON)
    )
    assert "CDB Genève" in out
    assert "LBK Zürich" in out
