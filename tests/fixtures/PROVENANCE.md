# Herkunft der Fixtures

Aufgezeichnet am **2026-08-15** mit `PYTHONPATH=src python scripts/record_fixtures.py`.

Eine Antwort je **Abfrage**, nicht je Endpunkt: fast alles laeuft ueber
denselben SPARQL-Endpunkt auf LINDAS und unterscheidet sich nur in der
Abfrage — Luft, Wasser, Schnee, Jagd, Laerm. Eine Handvoll Dateien wuerde
die Portfolio-Regel erfuellen und fast nichts belegen.

Der **Schluessel** unten ist, woran der Test eine Anfrage wiedererkennt: die
volle URL samt Query-String. Ohne den Query-String waeren die
SPARQL-Abfragen ununterscheidbar — sie gehen an dieselbe Adresse.

Im Schluessel steht der **Hostname**, nicht die IP. Der DNS-Pinning-Transport
schreibt die URL vor dem Connect auf die aufgeloeste Adresse um; die ist beim
naechsten Lauf eine andere, und ein darauf gebauter Schluessel traefe nur mit
Glueck.

Die Antworten stammen aus dem geteilten Client von `api_client.get_client()`
(gleicher User-Agent, gleiches Timeout, gleiche DNS-Pinning-Schicht wie im Betrieb),
abgegriffen ueber einen httpx-Response-Hook. Ausgeloest hat sie jeweils das
Werkzeug selbst — so belegt die Aufzeichnung auch, dass das Werkzeug genau
diese Anfrage schickt.

## Auswahl

Neu gesetzt ist die Einrueckung; gekuerzt ist allein die **Zahl** der
Listeneintraege. Kein Feld eines behaltenen Eintrags ist angetastet, und
Zaehlfelder daneben stehen wie geliefert.

Die Fehlerpfade — Timeout, 5xx, leere Trefferliste — bleiben handgeschrieben.
Sie lassen sich nicht auf Zuruf aufzeichnen und sind als Erfindung in Ordnung.

## `avalanche_bulletin_1.json`

- **Werkzeuge:** `env_avalanche_bulletin`
- **Schluessel:** `https://aws.slf.ch/api/bulletin/caaml/de/geojson`
- **Notiz:** Leer, weil ausserhalb der Lawinensaison aufgezeichnet: die Quelle liefert im August eine leere FeatureCollection.
- **Auswahl:** ungekuerzt
- **Groesse:** 52 Bytes
- **SHA-256:** `b3049ad7a1062091e169bd352424d59721a26b8b6229942aef26d11b0c6a96e1`

## `bafu_datasets_1.json`

- **Werkzeuge:** `env_bafu_datasets`
- **Schluessel:** `https://opendata.swiss/api/3/action/package_search?q=Wasser&fq=organization%3Abundesamt-fur-umwelt-bafu&rows=10&start=0&sort=score+desc%2C+metadata_modified+desc`
- **Auswahl:** 102 von 134 Listeneintraegen — jede Liste im Baum auf die ersten 3 gekuerzt, aus 158888 Bytes Rohantwort
- **Groesse:** 50466 Bytes
- **SHA-256:** `1c1a332efce9c663b0c92814514dde3d4684f8ce66f6af034db4b0a2b1247a33`

## `bathing_water_1.json`

- **Werkzeuge:** `env_bathing_water`
- **Schluessel:** `https://lindas.admin.ch/query?query=PREFIX+cube%3A+%3Chttps%3A%2F%2Fcube.link%2F%3E%0APREFIX+schema%3A+%3Chttp%3A%2F%2Fschema.org%2F%3E%0APREFIX+sh%3A+%3Chttp%3A%2F%2Fwww.w3.org%2Fns%2Fshacl%23%3E%0APREFIX+dcterms%3A+%3Chttp%3A%2F%2Fpurl.org%2Fdc%2Fterms%2F%3E%0A%0ASELECT+%3Fcube+%3Fname+%3Fversion+%3Fstatus+WHERE+%7B%0A++%3Fcube+a+cube%3ACube+%3B+schema%3Aname+%3Fname+.%0A++FILTER%28LANG%28%3Fname%29+%3D+%27de%27%29%0A++FILTER%28CONTAINS%28LCASE%28STR%28%3Fname%29%29%2C+%22badegew%C3%A4sser%22%29%29%0A++FILTER+NOT+EXISTS+%7B+%3Fcube+schema%3Aexpires+%3Fexpires+%7D%0A++OPTIONAL+%7B+%3Fcube+schema%3Aversion+%3Fversion+%7D%0A++OPTIONAL+%7B+%3Fcube+schema%3AcreativeWorkStatus+%3Fstatus+%7D%0A%7D+LIMIT+50%0A&format=application%2Fsparql-results%2Bjson`
- **Notiz:** Ungekuerzt: das Werkzeug filtert nach Kanton *in* dieser Liste.
- **Auswahl:** ungekuerzt — der Server rechnet *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 710 Bytes
- **SHA-256:** `566e393bd2bdbee67be41aa8fe0b38a72e45b0632223882212be8ab656fe0b5e`

## `bathing_water_2.json`

- **Werkzeuge:** `env_bathing_water`
- **Schluessel:** `https://lindas.admin.ch/query?query=PREFIX+cube%3A+%3Chttps%3A%2F%2Fcube.link%2F%3E%0APREFIX+schema%3A+%3Chttp%3A%2F%2Fschema.org%2F%3E%0APREFIX+sh%3A+%3Chttp%3A%2F%2Fwww.w3.org%2Fns%2Fshacl%23%3E%0APREFIX+dcterms%3A+%3Chttp%3A%2F%2Fpurl.org%2Fdc%2Fterms%2F%3E%0A%0ASELECT+DISTINCT+%3Flicense+WHERE+%7B%0A++%7B+%3Chttps%3A%2F%2Fenvironment.ld.admin.ch%2Ffoen%2Fubd01041prod%2F13%3E+dcterms%3Alicense%7Cschema%3Alicense+%3Flicense+%7D%0A++UNION%0A++%7B%0A++++GRAPH+%3Fg+%7B+%3Chttps%3A%2F%2Fenvironment.ld.admin.ch%2Ffoen%2Fubd01041prod%2F13%3E+a+cube%3ACube+%7D%0A++++GRAPH+%3Fg+%7B+%3Fds+a+schema%3ADataset+%3B+dcterms%3Alicense+%3Flicense+%7D%0A++%7D%0A%7D+LIMIT+1%0A&format=application%2Fsparql-results%2Bjson`
- **Notiz:** Ungekuerzt: das Werkzeug filtert nach Kanton *in* dieser Liste.
- **Auswahl:** ungekuerzt — der Server rechnet *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 258 Bytes
- **SHA-256:** `259a518f5233f949af6f1e7bd36ec406ca10d7843c4ea011799a5602c6428f6a`

## `bathing_water_3.json`

- **Werkzeuge:** `env_bathing_water`
- **Schluessel:** `https://lindas.admin.ch/query?query=PREFIX+cube%3A+%3Chttps%3A%2F%2Fcube.link%2F%3E%0APREFIX+schema%3A+%3Chttp%3A%2F%2Fschema.org%2F%3E%0APREFIX+sh%3A+%3Chttp%3A%2F%2Fwww.w3.org%2Fns%2Fshacl%23%3E%0APREFIX+dcterms%3A+%3Chttp%3A%2F%2Fpurl.org%2Fdc%2Fterms%2F%3E%0A%0ASELECT+DISTINCT+%3Fvalue+%3Fname+%3FnameLang+%3Fidentifier+%3Fplace+WHERE+%7B%0A++%3Chttps%3A%2F%2Fenvironment.ld.admin.ch%2Ffoen%2Fubd01041prod%2F13%3E+cube%3AobservationSet+%3Fset+.%0A++%3Fset+cube%3Aobservation+%3Fobs+.%0A++%3Fobs+%3Chttps%3A%2F%2Fenvironment.ld.admin.ch%2Ffoen%2Fubd01041prod%2Flocation%3E+%3Fvalue+.%0A++%3Fvalue+schema%3Aname+%3Fname+.%0A++BIND%28LANG%28%3Fname%29+AS+%3FnameLang%29%0A%0A++OPTIONAL+%7B+%3Fvalue+schema%3Aidentifier+%3Fidentifier+%7D%0A++OPTIONAL+%7B+%3Fvalue+schema%3AcontainedInPlace+%3Fplace+%7D%0A%7D+LIMIT+1000%0A&format=application%2Fsparql-results%2Bjson`
- **Notiz:** Ungekuerzt: das Werkzeug filtert nach Kanton *in* dieser Liste.
- **Auswahl:** ungekuerzt — der Server rechnet *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 116089 Bytes
- **SHA-256:** `671359d47176a269dbf201491c299cef905df4064860f5e2aab8346a10ac43db`

## `flood_warnings_1.json`

- **Werkzeuge:** `env_flood_warnings`
- **Schluessel:** `https://lindas.admin.ch/query?query=%0APREFIX+s%3A+%3Chttp%3A%2F%2Fschema.org%2F%3E%0APREFIX+hd%3A+%3Chttps%3A%2F%2Fenvironment.ld.admin.ch%2Ffoen%2Fhydro%2Fdimension%2F%3E%0ASELECT+%3Fid+%3Fname+%3Fwater+%3Fdanger+%3Flevel+%3Fdischarge+%3Ftime%0AFROM+%3Chttps%3A%2F%2Flindas.admin.ch%2Ffoen%2Fhydro%3E%0AWHERE+%7B%0A++%3Fst+a+%3Chttp%3A%2F%2Fexample.com%2FHydroMeasuringStation%3E+%3B%0A++++++s%3Aidentifier+%3Fid+%3B%0A++++++s%3Aname+%3Fname+.%0A++OPTIONAL+%7B%0A++++%3Fst+s%3AcontainedInPlace+%3Fwb+.%0A++++BIND%28REPLACE%28STR%28%3Fwb%29%2C+%22.%2A%2Fwaterbody%2F%22%2C+%22%22%29+AS+%3Fwater%29%0A++%7D%0A++%3Fobs+hd%3Astation+%3Fst+%3B%0A+++++++hd%3AdangerLevel+%3Fdanger+%3B%0A+++++++hd%3AmeasurementTime+%3Ftime+.%0A++OPTIONAL+%7B+%3Fobs+hd%3AwaterLevel+%3Flevel+%7D%0A++OPTIONAL+%7B+%3Fobs+hd%3Adischarge+%3Fdischarge+%7D%0A++FILTER%28isNumeric%28%3Fdanger%29+%26%26+%3Fdanger+%3E%3D+1%29%0A%7D%0A&format=application%2Fsparql-results%2Bjson`
- **Notiz:** Stufe 1 statt der Standard-Stufe 2: bei 2 liefert die Quelle im Sommer null Zeilen, und eine leere Antwort belegt keine Zeilenform.
- **Auswahl:** 6 von 195 Listeneintraegen — jede Liste im Baum auf die ersten 3 gekuerzt, aus 186204 Bytes Rohantwort
- **Groesse:** 2604 Bytes
- **SHA-256:** `3cc46e9713417eb5abcefa10cff780b0f707b1a1779d48609c971e9c5b598617`

## `hunting_stats_1.json`

- **Werkzeuge:** `env_hunting_stats`
- **Schluessel:** `https://www.jagdstatistik.ch/de/statistics?tt=0&sp=1&th=1&ar=CH`
- **Notiz:** Ungekuerzt: das Werkzeug indiziert Messreihen ueber die Jahresliste.
- **Auswahl:** ungekuerzt — der Server rechnet *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 16666 Bytes
- **SHA-256:** `0fb1837b20260b95d1efef5221e44f07e6fd0c3f3846edd52c64bd343690e48b`

## `nabel_current_1.json`

- **Werkzeuge:** `env_nabel_current`
- **Schluessel:** `https://opendata.swiss/api/3/action/package_search?q=NABEL+BER+NO2&fq=organization%3Abundesamt-fur-umwelt-bafu&rows=5`
- **Auswahl:** 63 von 108 Listeneintraegen — jede Liste im Baum auf die ersten 3 gekuerzt, aus 77273 Bytes Rohantwort
- **Groesse:** 43351 Bytes
- **SHA-256:** `ede74de95f8ad7f8ca2921680b20a2b59ca9e9ebabb02e9fcf77bdd22ef4b660`

## `noise_at_1.json`

- **Werkzeuge:** `env_noise_aircraft_at`
- **Schluessel:** `https://api3.geo.admin.ch/rest/services/ech/MapServer/identify?geometry=2684500%2C1256500&geometryType=esriGeometryPoint&geometryFormat=geojson&imageDisplay=1000%2C1000%2C96&mapExtent=2683500%2C1255500%2C2685500%2C1257500&tolerance=50&layers=all%3Ach.bazl.laermbelastungskataster-zivilflugplaetze_klein-grossflugzeuge&sr=2056&lang=de&returnGeometry=false`
- **Notiz:** Kloten, weil am Zuercher HB kein Kataster liegt und die Antwort leer bleibt.
- **Auswahl:** ungekuerzt
- **Groesse:** 2083 Bytes
- **SHA-256:** `6a5edd6968c83a3f215606f95da572972100c8be109da65539e365d83da1de66`

## `noise_registers_1.json`

- **Werkzeuge:** `env_noise_aircraft_registers`
- **Schluessel:** `https://api3.geo.admin.ch/rest/services/ech/MapServer/identify?geometry=2480000%2C1070000%2C2840000%2C1300000&geometryType=esriGeometryEnvelope&geometryFormat=geojson&imageDisplay=1000%2C1000%2C96&mapExtent=2480000%2C1070000%2C2840000%2C1300000&tolerance=0&layers=all%3Ach.bazl.laermbelastungskataster-zivilflugplaetze_klein-grossflugzeuge&sr=2056&lang=de&returnGeometry=false&limit=1000`
- **Notiz:** Ungekuerzt: das Werkzeug listet die Register vollstaendig.
- **Auswahl:** ungekuerzt — der Server rechnet *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 124829 Bytes
- **SHA-256:** `b9156e81a56c77ce4b7711ec142d837f178551457be7174a58bf200e04654472`

## `noise_registers_2.json`

- **Werkzeuge:** `env_noise_aircraft_registers`
- **Schluessel:** `https://api3.geo.admin.ch/rest/services/ech/MapServer/identify?geometry=2480000%2C1070000%2C2840000%2C1300000&geometryType=esriGeometryEnvelope&geometryFormat=geojson&imageDisplay=1000%2C1000%2C96&mapExtent=2480000%2C1070000%2C2840000%2C1300000&tolerance=0&layers=all%3Ach.bazl.laermbelastungskataster-zivilflugplaetze_erste-nachtstunde&sr=2056&lang=de&returnGeometry=false&limit=1000`
- **Notiz:** Ungekuerzt: das Werkzeug listet die Register vollstaendig.
- **Auswahl:** ungekuerzt — der Server rechnet *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 84054 Bytes
- **SHA-256:** `e539e982a5f942cb3e161e1c8fc30ee0d908c6b422bf429085dd15578de2dfca`

## `noise_registers_3.json`

- **Werkzeuge:** `env_noise_aircraft_registers`
- **Schluessel:** `https://api3.geo.admin.ch/rest/services/ech/MapServer/identify?geometry=2480000%2C1070000%2C2840000%2C1300000&geometryType=esriGeometryEnvelope&geometryFormat=geojson&imageDisplay=1000%2C1000%2C96&mapExtent=2480000%2C1070000%2C2840000%2C1300000&tolerance=0&layers=all%3Ach.bazl.laermbelastungskataster-zivilflugplaetze_zweite-nachtstunde&sr=2056&lang=de&returnGeometry=false&limit=1000`
- **Notiz:** Ungekuerzt: das Werkzeug listet die Register vollstaendig.
- **Auswahl:** ungekuerzt — der Server rechnet *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 54305 Bytes
- **SHA-256:** `a8ad62524b2ee89f70ca85e49fadbba2cf2643b41c986487f153bf58893f9051`

## `noise_registers_4.json`

- **Werkzeuge:** `env_noise_aircraft_registers`
- **Schluessel:** `https://api3.geo.admin.ch/rest/services/ech/MapServer/identify?geometry=2480000%2C1070000%2C2840000%2C1300000&geometryType=esriGeometryEnvelope&geometryFormat=geojson&imageDisplay=1000%2C1000%2C96&mapExtent=2480000%2C1070000%2C2840000%2C1300000&tolerance=0&layers=all%3Ach.bazl.laermbelastungskataster-zivilflugplaetze_letzte-nachtstunde&sr=2056&lang=de&returnGeometry=false&limit=1000`
- **Notiz:** Ungekuerzt: das Werkzeug listet die Register vollstaendig.
- **Auswahl:** ungekuerzt — der Server rechnet *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 4817 Bytes
- **SHA-256:** `179211e57c8fd2253daa2e33ab34267cdfed6786aa915a2d31cc6516e405be91`

## `noise_registers_5.json`

- **Werkzeuge:** `env_noise_aircraft_registers`
- **Schluessel:** `https://api3.geo.admin.ch/rest/services/ech/MapServer/identify?geometry=2480000%2C1070000%2C2840000%2C1300000&geometryType=esriGeometryEnvelope&geometryFormat=geojson&imageDisplay=1000%2C1000%2C96&mapExtent=2480000%2C1070000%2C2840000%2C1300000&tolerance=0&layers=all%3Ach.bazl.laermbelastungskataster-zivilflugplaetze_kleinluftfahrzeuge&sr=2056&lang=de&returnGeometry=false&limit=1000`
- **Notiz:** Ungekuerzt: das Werkzeug listet die Register vollstaendig.
- **Auswahl:** ungekuerzt — der Server rechnet *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 138548 Bytes
- **SHA-256:** `8c19bd7d5613ad7bda0130e5df5bb3d2393df77d2a60627fb9a88de740096814`

## `noise_registers_6.json`

- **Werkzeuge:** `env_noise_aircraft_registers`
- **Schluessel:** `https://api3.geo.admin.ch/rest/services/ech/MapServer/identify?geometry=2480000%2C1070000%2C2840000%2C1300000&geometryType=esriGeometryEnvelope&geometryFormat=geojson&imageDisplay=1000%2C1000%2C96&mapExtent=2480000%2C1070000%2C2840000%2C1300000&tolerance=0&layers=all%3Ach.bazl.laermbelastungskataster-zivilflugplaetze_helikopter&sr=2056&lang=de&returnGeometry=false&limit=1000`
- **Notiz:** Ungekuerzt: das Werkzeug listet die Register vollstaendig.
- **Auswahl:** ungekuerzt — der Server rechnet *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 12638 Bytes
- **SHA-256:** `4de5b4a6c76d7dfc88c935f00d4f1d20fd066f2cf1d2f46a7a6fe5af53daafb0`

## `noise_registers_7.json`

- **Werkzeuge:** `env_noise_aircraft_registers`
- **Schluessel:** `https://api3.geo.admin.ch/rest/services/ech/MapServer/identify?geometry=2480000%2C1070000%2C2840000%2C1300000&geometryType=esriGeometryEnvelope&geometryFormat=geojson&imageDisplay=1000%2C1000%2C96&mapExtent=2480000%2C1070000%2C2840000%2C1300000&tolerance=0&layers=all%3Ach.bazl.laermbelastungskataster-zivilflugplaetze_helikopter-maximalpegel&sr=2056&lang=de&returnGeometry=false&limit=1000`
- **Notiz:** Ungekuerzt: das Werkzeug listet die Register vollstaendig.
- **Auswahl:** ungekuerzt — der Server rechnet *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 90827 Bytes
- **SHA-256:** `63f428bc91ea1bdf44a26b1fa5eadbb0ab70def7d84804c000f22459b795ff03`

## `noise_registers_8.json`

- **Werkzeuge:** `env_noise_aircraft_registers`
- **Schluessel:** `https://api3.geo.admin.ch/rest/services/ech/MapServer/identify?geometry=2480000%2C1070000%2C2840000%2C1300000&geometryType=esriGeometryEnvelope&geometryFormat=geojson&imageDisplay=1000%2C1000%2C96&mapExtent=2480000%2C1070000%2C2840000%2C1300000&tolerance=0&layers=all%3Ach.bazl.laermbelastungskataster-zivilflugplaetze_militaer-gesamt&sr=2056&lang=de&returnGeometry=false&limit=1000`
- **Notiz:** Ungekuerzt: das Werkzeug listet die Register vollstaendig.
- **Auswahl:** ungekuerzt — der Server rechnet *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 2140 Bytes
- **SHA-256:** `0fa30d8e2ed791cff15567e1eeddf2366c3a000fea201ac65e9c22334ca9ac48`

## `snow_stations_1.json`

- **Werkzeuge:** `env_snow_stations`
- **Schluessel:** `https://measurement-api.slf.ch/public/api/imis/stations`
- **Notiz:** Ungekuerzt: das Werkzeug filtert nach Kanton *in* dieser Liste.
- **Auswahl:** ungekuerzt — der Server rechnet *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 42525 Bytes
- **SHA-256:** `49fbf0435fd85daa7a3e2554965ea492f28cec15544a2219bc0f5ad163dc0f1d`

## `wildfire_danger_1.html`

- **Werkzeuge:** `env_wildfire_danger`
- **Schluessel:** `https://www.waldbrandgefahr.ch/`
- **Notiz:** Ungekuerzt: das Werkzeug filtert nach Kanton *in* dieser Liste.
- **Auswahl:** ungekuerzt — der Server rechnet *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 30435 Bytes
- **SHA-256:** `d1758a43a2a8e4efcf8c9c8f462159777ea859558c68b8507662e45a291b3464`

## `wildfire_danger_2.json`

- **Werkzeuge:** `env_wildfire_danger`
- **Schluessel:** `https://www.waldbrandgefahr.ch/rails/active_storage/blobs/proxy/eyJfcmFpbHMiOnsiZGF0YSI6MTgyMTk0MTMsInB1ciI6ImJsb2JfaWQifX0=--cef299c94aea8f8aa17736ebdee0ba3c17f2c23b/fire_warn_levels-20260814120044.json`
- **Notiz:** Ungekuerzt: das Werkzeug filtert nach Kanton *in* dieser Liste.
- **Auswahl:** ungekuerzt — der Server rechnet *in* dieser Antwort, ein Schnitt erfaende ein anderes Ergebnis
- **Groesse:** 41652 Bytes
- **SHA-256:** `c8bc3d0e4da2e92ea851f753d5ed3d79e2de43347650485d9d07e591e7128451`
