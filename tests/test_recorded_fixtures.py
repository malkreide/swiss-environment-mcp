"""Jedes Werkzeug, gefahren aus einer aufgezeichneten Antwort.

Die handgeschriebenen Stubs im Rest der Suite pruefen die *Fehler*-Pfade — ein
Timeout, ein 5xx, eine leere Trefferliste —, die sich nicht auf Zuruf
aufzeichnen lassen und als Erfindung in Ordnung sind. Was sie nicht koennen: die
Form einer Erfolgs-Antwort belegen. Sie stimmen mit dem ueberein, was ihr Autor
annahm.

Wenige Hosts, aber viele Abfrageformen: fast alles laeuft ueber denselben
SPARQL-Endpunkt auf LINDAS und unterscheidet sich nur in der Abfrage — Luft,
Wasser, Schnee, Lawinen, Jagd, Laerm. Der Query-String gehoert deshalb in den
Schluessel; ohne ihn waeren die Abfragen ununterscheidbar und der Dispatcher
gaebe allen dieselbe Antwort.

Zugeordnet wird beim Abspielen nach der Anfrage und nicht nach der Reihenfolge:
mehrere Werkzeuge schicken mehr als eine Abfrage — `env_noise_aircraft_registers`
allein acht.

Herkunft, Datum, Auswahlregel und SHA-256 je Datei stehen in
`tests/fixtures/PROVENANCE.md`; neu aufzeichnen mit
`PYTHONPATH=src python scripts/record_fixtures.py`.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from typing import Any

import httpx
import pytest
import respx
from fixture_data import (
    fixture_json,
    fixture_text,
    provenance,
    recorded_names,
    recorder,
    schluessel_fuer,
    schluesselverzeichnis,
)
from mcp.server.mcpserver.exceptions import ToolError

from swiss_environment_mcp import api_client, server

# Werkzeug → (Eingabeklasse, Eingabe). Bewusst noch einmal hingeschrieben und
# nicht aus dem Recorder-Plan abgeleitet: die Tests sollen eine eigene Aussage
# machen. Dass beide dieselben Aufrufe fahren, prueft
# `test_der_recorder_faehrt_dieselben_aufrufe`.
WERKZEUGE: dict[str, tuple[str, str, dict[str, Any]]] = {
    "nabel_current": ("env_nabel_current", "NabelCurrentInput", {"station": "BER"}),
    "flood_warnings": ("env_flood_warnings", "FloodWarningsInput", {"min_level": 1}),
    "bathing_water": ("env_bathing_water", "BathingWaterInput", {"canton": "BE"}),
    "wildfire_danger": ("env_wildfire_danger", "WildfireDangerInput", {}),
    "snow_stations": ("env_snow_stations", "SnowStationsInput", {"canton": "GR"}),
    "avalanche_bulletin": ("env_avalanche_bulletin", "AvalancheBulletinInput", {}),
    "hunting_stats": ("env_hunting_stats", "HuntingStatsInput", {"species": "Rothirsch"}),
    "bafu_datasets": ("env_bafu_datasets", "BafuDatasetsInput", {"query": "Wasser"}),
    "noise_registers": (
        "env_noise_aircraft_registers",
        "NoiseAircraftRegistersInput",
        {},
    ),
    "noise_at": (
        "env_noise_aircraft_at",
        "NoiseAircraftAtInput",
        {"east": 2684500, "north": 1256500},
    ),
}

# Aufzeichnungen, die leer sind, weil die Quelle im August nichts liefert — kein
# Versehen, sondern der Sommerzustand des SLF-Lawinenbulletins. Steht hier
# namentlich, damit der Leerheitstest nicht stillschweigend alles durchlaesst.
SAISONAL_LEER = {"avalanche_bulletin_1.json"}

# Je Werkzeug ein Wort, das *nur* aus seiner Aufzeichnung stammen kann.
#
# «kommt ohne Fehler zurueck» ist als Zusicherung zu duenn: eine Antwort, in der
# nichts steht, ist auch fehlerfrei. Geprueft wird darum, dass die Ausgabe eine
# Zeile *dieser* Antwort traegt. Wuerde der Dispatcher allen dieselbe Datei
# geben, faellt hier neun Mal etwas — vorher genau nichts.
#
# Das Lawinenbulletin steht mit seiner Entwarnung drin: seine Aufzeichnung ist
# leer, und die richtige Ausgabe dazu ist der Satz, dass gerade keines laeuft.
BELEG: dict[str, str] = {
    "nabel_current": "Stickstoffdioxid-Immissionen entlang der A2 und A13",
    "flood_warnings": "Berlingen",
    "bathing_water": "Aare Marzili",
    "wildfire_danger": "Aletsch (VS)",
    "snow_stations": "Bärentälli",
    "avalanche_bulletin": "kein aktives Lawinenbulletin",
    "hunting_stats": "11657",
    "bafu_datasets": "Restwasserkarte Schweiz: Zuleitung",
    "noise_registers": "CDB Bressaucourt",
    "noise_at": "LBK Zürich",
}

# Werkzeuge, die einen im Quellcode gepflegten Katalog liefern und keine
# Anfrage schicken. Sie stehen deshalb nicht im Fixture-Ordner.
OHNE_NETZ: dict[str, tuple[str, dict[str, Any]]] = {
    "env_nabel_stations": ("NabelStationsInput", {}),
    "env_hydro_stations": ("HydroStationsInput", {"canton": "BE"}),
    "env_hazard_overview": ("HazardOverviewInput", {}),
    "env_hazard_regions": ("HazardRegionsInput", {}),
    "env_hunting_species": ("HuntingSpeciesInput", {}),
}


@pytest.fixture
def quelle():
    """Beantwortet jede Anfrage aus ihrer eigenen Aufzeichnung und protokolliert mit.

    Nach der *Anfrage* zugeordnet, nicht nach der Reihenfolge — und der
    Query-String gehoert dazu: die SPARQL-Abfragen gehen alle an dieselbe
    Adresse. Eine Anfrage ohne Aufzeichnung faellt hier laut auf, statt still
    eine fremde Datei zu bekommen.
    """
    protokoll: list[httpx.Request] = []
    verzeichnis = schluesselverzeichnis()

    def antwort(request: httpx.Request) -> httpx.Response:
        protokoll.append(request)
        schluessel = schluessel_fuer(request)
        name = verzeichnis.get(schluessel)
        if name is None:
            raise AssertionError(
                f"keine Aufzeichnung fuer diese Anfrage:\n  {schluessel}\n"
                "Neu aufzeichnen mit `PYTHONPATH=src python scripts/record_fixtures.py`."
            )
        return httpx.Response(200, text=fixture_text(name))

    with respx.mock:
        respx.route().mock(side_effect=antwort)
        yield protokoll


async def _fahre(name: str) -> str:
    """Ruft ein Werkzeug mit der Eingabe aus der Tabelle."""
    werkzeug, klasse, eingabe = WERKZEUGE[name]
    return await getattr(server, werkzeug)(getattr(server, klasse)(**eingabe))


# --------------------------------------------------------------------------
# Herkunft
# --------------------------------------------------------------------------
def test_provenance_nennt_ein_brauchbares_aufnahmedatum():
    """Eine Aufzeichnung ohne Datum ist eine undatierte Behauptung ueber die Quelle."""
    treffer = re.search(r"Aufgezeichnet am \*\*(\d{4}-\d{2}-\d{2})\*\*", provenance())
    assert treffer, "PROVENANCE.md nennt kein Aufnahmedatum im erwarteten Format"
    wann = dt.date.fromisoformat(treffer.group(1))
    assert wann <= dt.datetime.now(dt.UTC).date(), "Aufnahmedatum liegt in der Zukunft"


def test_jede_fixture_steht_in_der_provenance():
    """Sonst waechst der Ordner und der Nachweis bleibt zurueck."""
    text = provenance()
    fehlend = [n for n in recorded_names() if f"## `{n}`" not in text]
    assert not fehlend, f"ohne Eintrag in PROVENANCE.md: {fehlend}"


def test_jeder_schluessel_zeigt_auf_eine_vorhandene_datei():
    """Der Nachweis traegt hier den Abspielbetrieb — er darf nicht ins Leere zeigen."""
    fehlend = sorted(set(schluesselverzeichnis().values()) - set(recorded_names()))
    assert not fehlend, f"im Nachweis genannt, aber nicht vorhanden: {fehlend}"


def test_keine_aufzeichnung_liegt_unbenutzt_herum():
    """Die Gegenrichtung — eine Datei, die kein Schluessel erreicht, belegt nichts."""
    ueberzaehlig = sorted(set(recorded_names()) - set(schluesselverzeichnis().values()))
    assert not ueberzaehlig, f"von keinem Schluessel erreicht: {ueberzaehlig}"


def test_der_recorder_faehrt_dieselben_aufrufe():
    """Recorder und Tests duerfen nicht auseinanderlaufen.

    Laedt `scripts/record_fixtures.py` als Modul — `main()` wird nicht gerufen,
    es geht keine Anfrage raus.
    """
    modul = recorder()
    assert {a.name for a in modul.PLAN} == set(WERKZEUGE), (
        "Recorder und Testtabelle nennen verschiedene Aufrufe"
    )
    assert set(modul.OHNE_NETZ) == set(OHNE_NETZ), (
        "Recorder und Testtabelle nennen verschiedene Katalog-Werkzeuge"
    )


def _eintraege(daten: Any) -> int | None:
    """Die Zahl der Treffer einer Antwort, oder None, wenn sie keine Liste fuehrt."""
    if isinstance(daten, list):
        return len(daten)
    if not isinstance(daten, dict):
        return None
    for pfad in (
        ("results", "bindings"),  # SPARQL
        ("features",),  # GeoJSON
        ("results",),  # api3.geo.admin.ch identify
        ("result", "results"),  # CKAN
    ):
        knoten: Any = daten
        for stufe in pfad:
            knoten = knoten.get(stufe) if isinstance(knoten, dict) else None
        if isinstance(knoten, list):
            return len(knoten)
    return None


@pytest.mark.parametrize("name", sorted(n for n in recorded_names() if n.endswith(".json")))
def test_keine_aufzeichnung_ist_leer(name):
    """Eine leere Antwort sieht aus wie eine gueltige und prueft nichts.

    Die eine Ausnahme steht namentlich in `SAISONAL_LEER` und traegt ihren Grund
    im Nachweis — genau daran soll sie auffallen, wenn sie jemand aufhebt.
    """
    daten = fixture_json(name)
    anzahl = _eintraege(daten)
    if name in SAISONAL_LEER:
        assert anzahl == 0, f"{name} ist nicht mehr leer — Ausnahme in SAISONAL_LEER streichen"
        block = provenance().split(f"## `{name}`", 1)[1].split("## ", 1)[0]
        assert "Notiz" in block, f"{name} ist leer, ohne dass der Nachweis sagt warum"
        return
    assert daten, f"{name} ist leer"
    if anzahl is not None:
        assert anzahl, f"{name} traegt keine Treffer — neu aufzeichnen"


def test_die_schluessel_unterscheiden_sich_im_query_string():
    """Der Grund, warum der Query-String in den Schluessel gehoert.

    Acht Aufzeichnungen liegen unter derselben Adresse und unterscheiden sich
    allein im `layers`-Parameter; drei weitere teilen sich den SPARQL-Endpunkt.
    Ein Dispatcher, der nur Schema und Pfad liest, gaebe allen dieselbe Antwort.
    """
    schluessel = list(schluesselverzeichnis())
    ohne_query = [s.split("?", 1)[0] for s in schluessel]
    assert len(set(schluessel)) == len(schluessel), (
        "zwei Aufzeichnungen tragen denselben Schluessel"
    )
    assert len(set(ohne_query)) < len(schluessel), (
        "kein Schluesselpaar teilt sich eine Adresse — dann traegt der Query-String hier nichts"
    )


def test_kein_schluessel_traegt_eine_ip_statt_eines_hostnamens():
    """Sonst haengt die Zuordnung an der DNS-Antwort des Aufnahmetages.

    `_PinnedTransport` schreibt die URL vor dem Connect auf die aufgeloeste IP
    um. Der erste Entwurf zeichnete `13.226.251.100` auf und traf beim
    Abspielen auf `13.226.251.119` — dieselbe Anfrage, eine andere Adresse aus
    demselben CDN. Gruen war das nur, solange der Resolver dasselbe sagte.
    """
    ip = re.compile(r"^https://(\d{1,3}\.){3}\d{1,3}(/|$)")
    mit_ip = [s for s in schluesselverzeichnis() if ip.match(s)]
    assert not mit_ip, f"Schluessel auf einer IP statt einem Hostnamen: {mit_ip}"


# --------------------------------------------------------------------------
# Die Kataloge ohne Netz
# --------------------------------------------------------------------------
@pytest.mark.parametrize("werkzeug", sorted(OHNE_NETZ))
@respx.mock
async def test_die_katalog_werkzeuge_fragen_nichts(werkzeug):
    """Fuenf Werkzeuge liefern einen im Quellcode gepflegten Katalog.

    Sie haben deshalb keine Aufzeichnung — und das ist kein Versehen, sondern
    eine Aussage: was nie ein Netz beruehrt, kann auch nicht driften. Diese
    Zusicherung faellt, sobald eines von ihnen doch eine Quelle fragt; dann
    gehoert es in den Ordner.
    """
    klasse, eingabe = OHNE_NETZ[werkzeug]
    route = respx.route().mock(side_effect=AssertionError("hat doch gefragt"))
    ergebnis = await getattr(server, werkzeug)(getattr(server, klasse)(**eingabe))
    assert not route.called, f"{werkzeug} schickt eine Anfrage — es gehoert in den Plan"
    assert str(ergebnis).strip(), f"{werkzeug} liefert nichts"


# --------------------------------------------------------------------------
# Die Werkzeuge, jedes an seiner eigenen Antwort
# --------------------------------------------------------------------------
@pytest.mark.parametrize("name", sorted(WERKZEUGE))
async def test_jedes_werkzeug_liest_seine_aufgezeichnete_antwort(quelle, name):
    """Der eigentliche Punkt: jede Abfrage bekommt *ihre* Antwort.

    Alle mit derselben zu bedienen hiesse, die Aufzeichnung gegen eine Abfrage
    zu halten, die sie nicht beantwortet. Der Dispatcher faellt laut, wenn eine
    Anfrage keine Aufzeichnung hat.
    """
    ergebnis = str(await _fahre(name))
    assert ergebnis.strip(), f"{name} liefert nichts"
    assert "Fehler" not in ergebnis[:200], ergebnis[:300]
    assert quelle, f"{name} hat gar keine Anfrage abgeschickt"
    assert BELEG[name] in ergebnis, (
        f"{name} gibt nichts aus seiner Aufzeichnung wieder — "
        f"'{BELEG[name]}' fehlt in:\n{ergebnis[:600]}"
    )


def test_jedes_werkzeug_hat_einen_beleg():
    """Ein fehlender Eintrag in BELEG wuerde den Test oben lautlos entschaerfen."""
    assert set(BELEG) == set(WERKZEUGE), "BELEG und WERKZEUGE nennen verschiedene Werkzeuge"


async def test_das_laermregister_fragt_acht_mal(quelle):
    """Acht Abfragen in einem Aufruf — der Grund fuer die Zuordnung nach Anfrage.

    Je Sublayer eine, und alle acht gehen an dieselbe Adresse; sie unterscheiden
    sich allein im `layers`-Parameter. Eine Zuordnung nach Reihenfolge waere
    hier mit hoher Wahrscheinlichkeit falsch und im gruenen Fall bloss zufaellig
    richtig.
    """
    await _fahre("noise_registers")
    assert len(quelle) == 8, f"{len(quelle)} statt 8 Anfragen — die Form hat sich geaendert"
    layers = {httpx.URL(str(r.url)).params.get("layers") for r in quelle}
    assert len(layers) == 8, f"nur {len(layers)} verschiedene Sublayer abgefragt: {layers}"


async def test_das_laermregister_steht_ungekuerzt_im_ordner():
    """Es zaehlt *in* der Antwort — gekuerzt behauptete es einen kleineren Bestand."""
    block = provenance().split("## `noise_registers_1.json`", 1)[1].split("## ", 1)[0]
    assert "ungekuerzt" in block, block


def test_der_nachweis_meldet_was_gekuerzt_wurde():
    """Ein Nachweis, der ueber jeder Datei «ungekuerzt» schreibt, belegt nichts.

    Genau das tat er: `_kuerze` gab die Zaehler als `return vorher, nachher,
    geh(daten)` zurueck, und Python liest die beiden Zahlen, *bevor* `geh` sie
    hochzaehlt — also immer (0, 0). Jede gekuerzte Datei stand als vollstaendig
    im Ordner. Diese Zusicherung faellt, wenn die Zaehler wieder blind sind.
    """
    modul = recorder()
    vorher, nachher, gekuerzt = modul._kuerze({"a": list(range(10))})
    assert (vorher, nachher) == (10, modul.ZEILEN), (
        f"_kuerze meldet {vorher}→{nachher} statt 10→{modul.ZEILEN}"
    )
    assert len(gekuerzt["a"]) == modul.ZEILEN
    assert re.search(r"- \*\*Auswahl:\*\* \d+ von \d+ Listeneintraegen", provenance()), (
        "keine einzige Datei im Nachweis ist als gekuerzt ausgewiesen"
    )


def test_die_sparql_antworten_tragen_das_bindings_format():
    """Ein Stub mit einer flachen Liste sieht einfacher aus und ist falsch.

    SPARQL antwortet mit `head.vars` und `results.bindings`, und jeder Wert ist
    ein Objekt mit `type` und `value` — nicht der Wert selbst.
    """
    sparql = [
        n
        for n in recorded_names()
        if n.endswith(".json")
        and "results" in fixture_json(n)
        and isinstance(fixture_json(n).get("results"), dict)
    ]
    assert sparql, "keine SPARQL-Antwort im Ordner"
    daten = fixture_json(sparql[0])
    assert "head" in daten and "vars" in daten["head"], list(daten)
    erster = daten["results"]["bindings"][0]
    assert all(isinstance(v, dict) and "value" in v for v in erster.values()), erster


async def test_die_waldbrandgefahr_liest_erst_eine_seite_dann_die_datei(quelle):
    """Nicht jede Quelle antwortet mit JSON — eine Aufzeichnung ist eine HTML-Seite.

    Das Werkzeug liest aus ihr erst den Link auf die Tagesdatei und holt die
    dann. Ein Loader, der ueberall JSON erwartet, faellt hier ueber die erste
    Zeile; ein Dispatcher, der nur eine Antwort kennt, gaebe die Seite zweimal.
    """
    seiten = [n for n in recorded_names() if n.endswith(".html")]
    assert seiten, "keine Nicht-JSON-Aufzeichnung — die Form hat sich geaendert"
    ergebnis = str(await _fahre("wildfire_danger"))
    assert "Waldbrandgefahr" in ergebnis
    assert len(quelle) == 2, f"{len(quelle)} statt 2 Anfragen (Seite + Tagesdatei)"


# --------------------------------------------------------------------------
# Die Gegenrichtung
# --------------------------------------------------------------------------
@respx.mock
async def test_eine_leere_trefferliste_bleibt_eine_leere_trefferliste():
    """`bindings: []` ist eine Aussage der Quelle: dazu gibt es nichts.

    Das darf nicht als Fehler herauskommen — sonst kann das Modell einen echten
    Negativtreffer nicht von einem Ausfall unterscheiden.
    """
    leer = json.dumps({"head": {"vars": ["x"]}, "results": {"bindings": []}})
    respx.route().mock(return_value=httpx.Response(200, text=leer))
    ergebnis = str(await _fahre("hunting_stats"))
    assert ergebnis.strip()
    assert "Fehler" not in ergebnis[:200], ergebnis[:300]


@respx.mock
async def test_ein_abbruch_bleibt_ein_fehler(monkeypatch):
    """Und die andere Haelfte: ein Ausfall darf nicht als leeres Ergebnis erscheinen.

    Das Werkzeug meldet ihn nicht als Text, sondern als `ToolError` — der Client
    sieht `isError: true` und kann ihn von einem echten Negativbefund
    unterscheiden. Genau darum wird hier die Ausnahme erwartet und nicht ein
    Rueckgabewert: ein Fehlertext im Erfolgskanal saehe fuer das Modell aus wie
    ein Ergebnis.
    """
    monkeypatch.setattr(api_client, "RETRY_BASE_DELAY", 0)
    respx.route().mock(side_effect=httpx.ConnectError("weg"))
    with pytest.raises(ToolError) as fehler:
        await _fahre("hunting_stats")
    assert "nicht abrufbar" in str(fehler.value), str(fehler.value)[:300]


# --------------------------------------------------------------------------
# Der Nachweis, nachgerechnet
# --------------------------------------------------------------------------
@pytest.mark.parametrize("name", sorted(n for n in recorded_names() if n != "PROVENANCE.md"))
def test_die_pruefsumme_im_nachweis_stimmt(name):
    """Eine Pruefsumme, die niemand nachrechnet, ist Zierde.

    Sie steht im Nachweis, um genau einen Fall zu fangen: eine Aufzeichnung,
    die nach dem Lauf von Hand nachgebessert wurde. Eine korrigierte Antwort
    ist wieder eine erfundene — und von aussen ist ihr das nicht anzusehen.
    Ohne diesen Test faengt die Summe nichts.

    Gerechnet wird ueber die Bytes auf der Platte, nicht ueber den Loader:
    genau die hat der Recorder gehasht, und ein Loader, der unterwegs dekodiert
    oder normalisiert, wuerde die Pruefung gegen sich selbst fuehren.
    """
    import hashlib
    import re
    from pathlib import Path

    teile = provenance().split(f"## `{name}`", 1)
    assert len(teile) == 2, f"{name} hat keinen Block in PROVENANCE.md"
    treffer = re.search(r"\*\*SHA-256:\*\*\s*`([0-9a-f]{64})`", teile[1].split("## ", 1)[0])
    assert treffer, f"{name} steht ohne Pruefsumme im Nachweis"
    roh = (Path(__file__).resolve().parent / "fixtures" / name).read_bytes()
    assert hashlib.sha256(roh).hexdigest() == treffer.group(1), (
        f"{name} weicht vom Nachweis ab — von Hand nachgebessert? Neu aufzeichnen."
    )
