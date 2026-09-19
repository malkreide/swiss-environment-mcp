# CLAUDE.md

## Teil 1 — Konventionen (portfolio-weit)

### Vor der Arbeit

Klon-Aktualität prüfen — Standard-Branch ermitteln, nicht `main` annehmen:

```bash
B=$(git ls-remote --symref origin HEAD | sed -n 's|^ref: refs/heads/\([^[:space:]]*\).*|\1|p')
git fetch origin "${B:?Standard-Branch nicht ermittelbar}" &&
  git rev-list --count HEAD..FETCH_HEAD
```

Drei Server im Portfolio heissen ihren Standard-Branch `master`
(`openlex-mcp`, `swiss-courts-mcp`, `swisstopo-mcp`); dort scheitert ein fest
verdrahtetes `origin/main` mit «couldn't find remote ref main». Wer das für ein
Netzproblem hält, arbeitet weiter auf genau dem veralteten Klon, vor dem dieser
Absatz warnt. Den `:?`-Schutz nicht weglassen: Bei leerem `B` fetcht git still
den Remote-HEAD und endet mit 0.

Ein veralteter Klon erzeugt eine rote CI, deren Ursache nicht im Diff steht.
Am 3.8.2026 zweimal passiert — beide Male fehlten genau die Commits, die
das Gate einführten, an dem der Branch scheiterte.

Gates lokal fahren, mit der GEPINNTEN ruff-Version aus der CI. Eine andere
Version meldet Abweichungen, die niemand verursacht hat.

### Tests

Gegenprobe ist Pflicht. Ein Test, der grün bleibt, wenn man die
Implementierung entfernt, prüft nichts. Jede neue Zusicherung einzeln
neutralisieren und zeigen, dass genau die zugehörigen Tests fallen.

Zwei Fallen, die beide grün blieben:

- Eine Fake-Uhr, die nur beim Schlafen vorrückt, kann eine Zusicherung über
  echte Zeit nicht widerlegen.
- `monkeypatch.setattr(modul.asyncio, "sleep", ...)` greift ins Modul
  `asyncio` selbst und entschärft die Mechanik im ganzen Prozess. Patche
  einen Modul-Alias (`_sleep = asyncio.sleep`), nicht das fremde Modul.

Handgeschriebene Fixtures kodieren die Annahme des Autors und können sie
nicht widerlegen. Mindestens eine aufgezeichnete Antwort pro externem
Endpunkt, mit Aufnahmedatum.

### Wenn etwas rot ist

Roter Live-Test: erst die Quelle abfragen, dann einordnen. Nicht aus der
Fehlermeldung schliessen. Am 3.8.2026 hiess "nicht gefunden" nicht, dass der
Datensatz weg war, sondern dass die Quelle die Schreibweise ihrer Kopfzeile
gewechselt hatte — vier von sechs Datensätzen produktiv kaputt, alle
Unit-Tests grün.

**Ein 4xx ist kein Nein.** Am 29.8.2026 antwortete `past-publications` in
`swiss-procurement-mcp` auf jede Publikation mit Losen mit HTTP 400. Daraus war
geschlossen worden, die Quelle verweigere diese Auskunft; der Befund stand
datiert im Fixture-Nachweis, ein Test bestätigte ihn, alles blieb grün. Die
Spec desselben Endpunkts führt einen als *optional* deklarierten Parameter
`lotId` — für Publikationen mit Losen ist er Pflicht. Mit ihm antwortet
dieselbe Publikation mit 200. Ein Projekt trug sieben Vorgängerpublikationen,
die der Server als «Quelle nicht erreichbar» wegwarf.

Drei Handgriffe daraus:

- **Die Parameterliste der Spec durchgehen, bevor ein Statuscode eingeordnet
  wird.** «Optional» heisst dort oft «optional für die Mehrheit».
- **Einer deterministischen Absage keinen Wiederholungsrat geben.** «Nicht
  erreichbar, bitte später erneut» ist bei einem 400 falsch und liest sich für
  das Modell wie eine Störung. Den Status mitführen und den fehlenden
  Parameter benennen — den Status, nicht den Antwortkörper.
- **Beide Antworten aufzeichnen, mit und ohne den Parameter.** Eine
  Aufzeichnung nur des Fehlschlags kann nicht zeigen, dass er vermeidbar war;
  dass nur der 400er aufgezeichnet war, ist der Grund, warum der falsche
  Befund nicht auffiel.

**Und ein 403 ist gar keine Auskunft.** Am 29.8.2026 sollten für 42 Repos die
Dependabot-Labels nachgemessen werden. Alle 13 Abfragen des ersten Stapels
kamen zurück als:

```
Failed to find label: API rate limit already exceeded for user ID 8864492.
```

Der gefährliche Teil steht vorn: Das Werkzeug verpackt eine Sperre als
Fund-Fehlschlag. Wer die Zeile überfliegt oder nur auf ein leeres Ergebnis
prüft, zählt 39 Repos als «Label fehlt» und hat seine eigene Erschöpfung
gemessen. Das Limit hängt am Konto, nicht am Repo — derselbe Vormittag hatte
es mit 42 eröffneten und 42 gemergten PRs verbraucht.

Das ist der Absatz darüber, andersherum gelesen: dort war ein 400 eine echte,
wiederholbare Antwort und galt als Störung; hier ist eine Störung als Antwort
verpackt. Entscheidend ist nie der Statuscode, sondern ob die Quelle überhaupt
geantwortet hat.

- **Positivkontrolle im selben Repo.** Ein «nicht gefunden» wird erst dadurch
  zur Messung, dass eine gleichzeitige Abfrage etwas findet.
- **Die Messung entlang der Sperre teilen.** `raw.githubusercontent.com` ist
  ein CDN und nicht die REST-API. Um 11:19:27 UTC lieferte es für
  `register-mcp` HTTP 200, während die Label-Abfrage desselben Repos in
  derselben Minute die Sperre meldete. Alle 42 `dependabot.yml` kamen so
  durch, während die Label-Hälfte stand.
- **Am Token vorbei geht es nicht.** Beide Umwege enden am Agent-Proxy, und
  jeder mit einer eigenen irreführenden Begründung. `api.github.com` ohne
  Zugangsdaten:

  ```
  GitHub access is not enabled for this session. An org admin must connect
  the Claude GitHub App for this organization.
  ```

  Das ist keine Aussage über die Organisation, sondern das, was ohne Token
  kommt. Wer ihr folgt, sucht einen Admin für ein Problem, das keiner hat.
  Die HTML-Seite `github.com/<owner>/<repo>/labels` fällt ebenfalls, aber
  anders:

  ```
  This GitHub API path is not available: sessions are bound to their
  configured repositories. Use repository-scoped endpoints
  (repos/{owner}/{repo}/...).
  ```

  Der Proxy behandelt also auch `github.com` als API-Pfad; die zweite Meldung
  klingt nach einem Scope-Problem und ist doch nur dieselbe Sackgasse. Den
  Token aus der Umgebung in einen curl-Header zu setzen, blockiert der
  Klassifikator. Ob es überhaupt hülfe, ist offen: die Sperre nennt ein
  Nutzerkonto, und ob der Token zu diesem gehört, wurde nie geprüft.
- **Die Sperre gilt nicht dem Dienst, sondern dem Zugangspfad.** Unmittelbar
  nachdem eine Abfrage der Checks eines PR sauber durchlief, meldete die
  Label-Abfrage weiter die Sperre. Von einem blockierten Werkzeug also nicht
  auf «GitHub ist zu» schliessen — und umgekehrt eine gelungene Abfrage nicht
  als Entwarnung für die gesperrte nehmen. Das ist dieselbe Asymmetrie wie
  bei der verschwundenen Codex-Meldung weiter unten.

Wann die Sperre fällt, geben diese Beobachtungen nicht her. Die Meldung nennt
keinen Zeitpunkt, und die `X-RateLimit`-Kopfzeilen sind hinter dem Proxy nicht
zu sehen. Belegt sind drei gesperrte Zeitpunkte — 11:14, 11:16 und 11:19 UTC.
Wer daraus eine Dauer macht, hat sie erfunden.

**Dieselbe Falle bei einer Konfigurationsoption: die Vorgabe lesen, bevor man
einen Schlüssel für wirkungslos hält.** Am 29.8.2026 fielen die
`labels:`-Zeilen aus den `dependabot.yml` des Portfolios, begründet mit
«Dependabot legt Labels nicht an». Eine Messung danach zeigte, dass
`dependencies` in 36 von 42 Repos sehr wohl existiert, 35 davon mit GitHubs
Standardbeschreibung. Das las sich zuerst wie ein Beleg, dass die Aktion
falsch war.

Die Optionsreferenz kehrt es um:

```
Dependabot creates these default labels automatically, as necessary in
your repository.

If you define more than one package manager, an additional label for the
ecosystem or language is added to each pull request.

The labels specified are used instead of the default labels.
```

Ohne `labels:` vergibt Dependabot also `dependencies` — und, sobald mehr als
ein Paketmanager deklariert ist, zusätzlich ein Ökosystem-Label — und legt sie
selbst an; eine eigene Liste **ersetzt** diesen Satz, und «if any of these
labels is not defined in the repository, it is ignored». Die Zeile war nicht
wirkungslos — sie tauschte einen sich selbst pflegenden Vorgabesatz gegen eine
starre Liste.

**Die Bedingung nicht weglassen.** Bei nur einem Paketmanager steht das
Ökosystem-Label gar nicht zu; wer es dort trotzdem erwartet, schreibt genau
den Fehlbefund auf, gegen den dieser Abschnitt geschrieben ist — der Abschnitt
liefe an sich selbst vorbei. Im Portfolio deklariert jede `dependabot.yml`
zwei (`pip` und `github-actions`), die Bedingung ist hier also überall
erfüllt; anderswo nicht unbedingt. Aufgefallen ist die fehlende Bedingung
nicht beim Schreiben, sondern durch einen Codex-Review auf
`swiss-environment-mcp` PR #113 — vierzehn Sekunden vor dem Merge desselben
PR.

Was das kostet, ist an `openlex-mcp` gemessen: zwei Ökosysteme deklariert,
also stünden `dependencies` **und** ein Ökosystem-Label zu; vorhanden ist nur
das erste, `github-actions` und `github_actions` fehlen beide (Kontrolle `bug`
vorhanden). `register-mcp` ist die Gegenprobe: dort existieren alle vier
deklarierten Namen mit handgeschriebener Beschreibung, die Liste ist gewollt
und vollständig.

**Dreimal falsch eingeordnet, in drei Richtungen.** Erst die Zeile für bloss
wirkungslos gehalten. Dann die gefundenen Labels für einen Widerspruch. Dann,
auf denselben Fund gestützt, einen richtigen PR geschlossen mit dem Argument,
das Label existiere ja — obwohl es existiert, *weil* die Vorgabe es anlegt.
Der dritte Fehler ist der teuerste, weil er wie eine Messung aussah.

Was die Messung **nicht** hergibt: wer die 36 Labels angelegt hat. Die
Referenz sagt, Dependabot tue es; die Objekt-IDs liegen aber so dicht
beieinander, dass sie eher aus einem Stapellauf stammen. Beides passt zum
Befund, keines ist belegt — die Herkunft blieb ungemessen.

Beim Aufräumen gilt deshalb dieselbe Frage wie bei `lotId`: Was ist die
*Vorgabe*, wenn man das Ding weglässt — nicht bloss, ob der aktuelle Wert
etwas bewirkt.

**`results[0]` ist nur so verlässlich wie die Zusicherung danach.** Pinnt die
Abfrage einen bekannten Datensatz, ist der erste Treffer eine Drift-Wache und
in Ordnung. Hängt die Zusicherung dagegen davon ab, *welche* Variante die
Quelle heute zuoberst hat, prüft der Test den Tag: am 25.8.2026 rot, weil die
neueste Zürcher Publikation zufällig Lose hatte, am 26.8. grün, ohne dass sich
etwas geändert hätte. Den Fall gezielt wählen und beide Zweige fahren.

PR ohne jeden Check ist selten ein Repo ohne CI, meistens ein
Merge-Konflikt: GitHub berechnet dafür keinen Merge-Commit und startet nichts.

Ein Codex-Review auf einem PR wird beantwortet oder behoben, nie ignoriert.

### Wenn Codex gar nicht erst hinsieht

Die Zeile oben unterstellt, dass es einen Befund geben *kann*. Das ist nicht
immer so, und man sieht es dem PR nicht an.

Am 21.8.2026 war das Code-Review-Kontingent zwischen 08:41 und 09:48
aufgebraucht — davor echte Reviews, danach in 30 Repos nur noch:

```
You have reached your Codex usage limits for code reviews.
```

Wie lange die Sperre dauerte, geben die Beobachtungen nur als Spanne her. Vier
Zeitpunkte sind belegt: letzter gelungener Review am 21.8. um 08:41, erste
Limit-Meldung um 09:48, letzte beobachtete Limit-Meldung am 22.8. um 11:03,
erste *andere* Meldung am 23.8. um 08:22.

Zwischen erster und letzter Limit-Meldung liegen **25 h 15 min**. Das ist der
Abstand zweier Fehlschläge, nicht die Dauer einer Sperre. Wer ihn Untergrenze
nennt, hat die durchgehende Erschöpfung schon vorausgesetzt, die er belegen
soll: Öffnete sich das Fenster zwischendurch und schloss es sich durch neue
Auslöser wieder, waren es zwei kurze Sperren und nie eine von 25 Stunden.
Untergrenze einer *einzelnen* Sperre sind die 25 h 15 min nur unter genau dieser
Annahme — und die ist unbelegt.

Nach oben trägt die Rechnung dagegen. Die längste mit den Beobachtungen
verträgliche Sperre reicht vom letzten Erfolg um 08:41 bis zur abweichenden
Meldung um 08:22, also **47 h 41 min**; länger kann keine einzelne gewesen sein.
Wer stattdessen ab der ersten Limit-Meldung rechnet, unterschlägt die 67
Minuten, in denen das Kontingent schon weg gewesen sein kann, und nennt die
Spanne zwischen zwei Beobachtungen eine Obergrenze.

Beobachtungspunkte sind keine Messreihe — die 21 Stunden vor der abweichenden
Meldung liefen ganz ohne Codex-Auslöser, dort hat niemand gemessen.

In der Zwischenzeit sind 32 PRs mit formal erfülltem Häkchen gemergt worden,
ohne dass jemand hineingesehen hat, und am 22.8. noch einmal 43.

**Vier** Gründe, warum Codex schweigt, und nur einer davon ist harmlos:

- **Kein Befund** — dann schreibt er einen gewöhnlichen Issue-Kommentar:

  ```
  Codex Review: Didn't find any major issues. Swish!
  ```

  Der Schlusssatz wechselt bei jedem Lauf («Delightful!», «Keep it up!»,
  «Nice work!», «More of your lovely PRs please.»); stabil ist nur der Satz
  davor. Seit dem 18.9.2026 steht darunter zusätzlich der geprüfte Stand
  («Reviewed commit: `5c08df8ff0`») — damit lässt sich diese Meldung, anders
  als früher, einem Head zuordnen.

  Der Infokasten behauptet eine Reaktion («otherwise it will react with 👍»);
  am 23.8. kam in sechs Repos die Meldung und in keinem die Reaktion. Der
  Kasten ist keine Quelle — aber diese Gegenprobe ist schwächer, als sie
  aussieht: Die Reaktion steht auf dem **Pull Request**, nicht am Kommentar
  (gemessen am 19.9., Einzelheiten weiter unten), und wo am 23.8. gesucht
  wurde, ist nicht festgehalten. Vor einem «kam nicht» also erst prüfen, ob am
  richtigen Objekt gesucht wurde.
- **Der PR ist ein Draft** — darauf läuft Codex nicht an.
- **Das Kontingent ist weg** — dann schreibt er die Meldung oben.
- **Für das Repo fehlt eine Environment** — dann schreibt er:

  ```
  To use Codex here, create an environment for this repo.
  ```

Der vierte kam erst zum Vorschein, als der dritte wegfiel, und das ist kein
Zufall: Die Prüfungen liegen hintereinander. Dass es diese Reihenfolge ist und
nicht die umgekehrte, lässt sich an einem einzigen Repo ablesen — in
`swiss-public-data-mcp` bekam PR #54 am 22.8. um 10:56:55 die Kontingent-Meldung
und PR #56 am 23.8. um 08:22:20 die Environment-Meldung. Läge die
Environment-Prüfung vorn, hätte #54 sie schon am Vortag gesehen; die Environment
fehlte ja bereits. Zwei Meldungen aus demselben Repo schlagen hier jede
Vermutung über die Reihenfolge.

Praktisch heisst das: **Eine verschwundene Limit-Meldung ist keine Entwarnung.**
Sie kann bedeuten, dass das Kontingent wieder da ist — und dass jetzt etwas
anderes den Review verhindert. Belegt ist eine Prüfung erst durch ein
Review-Objekt **oder** eine Befundlos-Meldung. Wer nur das Objekt gelten lässt,
zählt jeden befundlosen Review als ungeprüft — und baut sich denselben Fehlalarm
ein, den dieser Abschnitt verhindern soll, nur in die andere Richtung.

«Kein Kommentar» heisst also nicht «geprüft und sauber». Unterscheiden lässt es
sich an der Form: Ein Review **mit** Befund ist ein Review-Objekt
(«💡 Codex Review», mit Commit-Angabe); ein Review **ohne** Befund und die
beiden Ausfallmeldungen — Kontingent wie Environment — sind gewöhnliche
Issue-Kommentare und trennen sich nur im Text. Beim Draft gibt es überhaupt
nichts, weil Codex nicht anläuft; ein kommentarloser Draft ist deshalb kein
Beleg, sondern ein nicht durchgeführter Test.

Das sind verschiedene Abfragen — `get_reviews` fürs Objekt, `get_comments` für
alles andere; wer nur eine nimmt, übersieht den Rest. Genau so ist die
Limit-Meldung zuerst durchgerutscht.

Der Kommentarzähler allein reicht ohnehin nicht: `comments: 1` kann die
Befundlos-, die Kontingent- **oder** die Environment-Meldung sein — drei
gegensätzliche Bedeutungen unter derselben Zahl. Den Text lesen, nicht die Zahl.
Und einen unbekannten vierten Text wörtlich zitieren, statt ihn in eine der
bekannten Schubladen zu zwingen: Dieser Abschnitt musste schon einmal von drei
auf vier Gründe wachsen, und die 👍-Reaktion stand hier zwei Fassungen lang als
Tatsache.

Und ein befundloser Lauf ist kein Freispruch. Am 23.8. lief derselbe Text durch
42 Reviews: 36 meldeten denselben P2-Befund, 6 die Befundlos-Meldung — gleiche
Eingabe, gegenteiliges Urteil, alles in denselben neun Minuten. Ein sauberer
Lauf sagt damit etwas über den Lauf, nicht über den Text. Wer sein Häkchen
daran hängt, hängt es an einen Münzwurf.

### Und dann wechselt die Quelle ihr Format

Am 29.8.2026 hat Codex das Meldeformat umgestellt. Statt Einzelmeldungen führt
er jetzt **einen** Kommentar je PR und schreibt ihn fort — eine Zeile je Review,
mit Status und Commit. Wörtlich an `swiss-environment-mcp#104`, Head `5147312`,
um 06:50:52:

```
| 📝 **Code Review** | 🔄 **Running** since 2026-08-29T06:50:41Z | `5147312` | Draft marked ready |
```

und um 06:52:29 derselbe Kommentar, dieselbe `id`, dasselbe `created_at`:

```
| 📝 **Code Review** | ✅ **Completed** 2026-08-29T06:52:26.201705Z | `5147312` | Draft marked ready |
```

Der Infokasten sagt neu: «Codex reacts with 👀 while any review is running,
comments if it has suggestions, and reacts with 👍 once all reviews finish with
no findings.»

**Hier stand daraus geschlossen, die Befundlos-Meldung falle als Text weg und
ein sauberer Lauf hinterlasse nur noch eine Reaktion. Das ist falsch — es ist
beides.** Gemessen am 19.9.2026 an zwei Fällen, beide mit der neuen Summary
daneben:

| PR | Kommentar | Text |
|---|---|---|
| #118 | 18.9., 17:05:24 | «Codex Review: Didn't find any major issues. Nice work!» |
| #119 | 19.9., 07:55:17 | «Codex Review: Didn't find any major issues. Keep it up!» |

Beide **zusätzlich** zur Summary-Tabelle, die für denselben Commit `Completed`
meldet. Der Fehler war, einen Infokasten als vollständige Beschreibung zu lesen:
Er zählt auf, was Codex tut, nicht was er nicht mehr tut. Wer die
Befundlos-Meldung daraufhin aus dem Klassifikator entfernt, nimmt dem Gate einen
funktionierenden Nachweisweg weg — `MARK_NO_FINDING` in
`scripts/classify_codex_review.py`.

Drei Beobachtungen dazu:

- **Die 👍-Reaktion kommt, aber auf den PULL REQUEST, nicht auf einen
  Kommentar.** Auf #118 und #119 steht sie je einmal auf PR-Ebene, während
  sämtliche Kommentar-Reaktionen auf 0 stehen. Negativkontrolle ist #117: Dort
  hatte der letzte Review einen Befund, und der PR trägt **keine** Reaktion.
  Nicht messbar ist, *wer* reagiert hat — `issue_read` liefert Zähler, keine
  Urheber; die Zuordnung trägt allein diese Korrelation über drei PRs.
- **Die Befundlos-Meldung nennt den geprüften Commit** («Reviewed commit:
  `32cb7cc1b1`»). Das Gate datiert sie bisher über `created_at` gegen
  `head_seen_at`, also über den schwächeren Zeitstempel, obwohl der Stand im
  Text steht. Ungenutzt, aber notiert.
- **Zwei Infokästen laufen nebeneinander.** Die Summary trägt den neuen
  («reacts with 👀 … 👍»), die Befundlos-Meldung am selben Tag den alten
  («otherwise it will react with 👍») — Minuten auseinander, im selben PR.

Die ältere Notiz weiter oben, am 23.8. sei in sechs Repos die Meldung und in
keinem die Reaktion gekommen, steht damit unter Vorbehalt: Wo damals gesucht
wurde, ist nicht festgehalten, und auf Kommentarebene wäre auch heute nichts zu
finden. Nachmessen lässt sie sich nicht. «Der Kasten ist keine Quelle» bleibt
richtig, nur mit anderer Begründung als dort — dieser Absatz hat ihn eben selbst
zu weit gelesen.

Drei Folgen, und die dritte ist die unangenehme:

- **`created_at` ist kein Alter mehr.** Der Kommentar wird bearbeitet, nicht neu
  geschrieben; sein Erstelldatum steht still, während sein Inhalt weiterläuft.
  Ein Frischefilter über `created_at` wirft nach dem nächsten Push genau das
  Signal weg, auf das er wartet.
- **Die Commit-Spalte ist das bessere Signal.** Sie nennt den geprüften Stand
  selbst — genauer als jeder Zeitstempel, und in beide Richtungen.
- **«Running» ist kein Ausfall.** Das Gate hier hat den neuen Kommentar als
  unbekannten Text eingeordnet und rot gesetzt. Für einen *laufenden* Review ist
  das falsch; richtig wäre gelb. Dass es überhaupt auffiel, ist die Regel oben
  in Funktion: Unbekanntes wird zitiert, nicht einsortiert.

Und der Wechsel `Running` → `Completed` ist eine **Bearbeitung**. Ein Workflow
auf `issue_comment: [created]` sieht ihn nie.

Der Zähler taugt damit noch weniger als vorher: `comments: 1` ist heute meist
die Summary — und die kann laufend, fertig oder für einen ganz anderen Commit
sein.

Portfolio-weit nachsehen:

```
search_pull_requests: user:malkreide commenter:chatgpt-codex-connector[bot] updated:>=<Datum>
```

Findet nur, wo er *kommentiert* hat. Repos ohne PR-Aktivität tauchen nicht auf
— das ist kein Beleg, dass dort geprüft wurde.

Zweiter Weg, den Prüfer zu verlieren, ganz ohne Kontingentproblem: zu schnell
mergen. Am 21./22.8. lagen zwischen «ready for review» und Merge mehrfach drei
bis fünf Sekunden. Codex wird beim Umschalten von Draft auf ready ausgelöst und
braucht danach Zeit; wer sofort mergt, hat das Häkchen gesetzt und den Review
nicht abgewartet.

### Dritter Weg: der Push, der keinen Review auslöst

Der Absatz oben nennt einen Auslöser. Es sind drei, und der Infokasten unter
jedem Codex-Kommentar zählt sie vollständig auf:

```
Reviews are triggered when you
- Open a pull request for review
- Mark a draft as ready
- Comment "@codex review" or "@codex security review".
```

**Ein Push ist nicht dabei.** Ein `synchronize` löst *keinen* Review aus — nach
einem Fix-Push bleibt das Gate also auf gelb, bis jemand von Hand nachfragt, und
zwar unbegrenzt. Wer darauf wartet, dass es von selbst grün wird, wartet für
immer; wer das Warten aufgibt und mergt, mergt ungeprüft. Das ist das
Spiegelbild des «zu schnell mergen» von oben — dieselbe Lücke, von der anderen
Seite betreten.

Gemessen am 18.9.2026 auf `swiss-environment-mcp#118`: Head `f2f0c0c` bekam
einen Review (Trigger-Spalte: «Draft marked ready»), danach zwei Fix-Pushes auf
`6c96b1f` und `958f31e` — und für beide **gar nichts**: keine Summary-Zeile,
keine Reaktion, keine Ausfallmeldung. Jeder beobachtete Review der PRs #116,
#117 und #118 trägt in der Trigger-Spalte «Draft marked ready»; kein einziger
stammt von einem Push.

**Stille und Kontingent lassen sich dabei trennen.** Ein erschöpftes Kontingent
*schreibt* seine Meldung, sobald ein Review angefordert wird, und zwar sofort:
Anfrage 13:55:15, Meldung 13:55:26 — elf Sekunden. Auf die beiden Pushes kam
dagegen nichts. Kein Kommentar heisst hier also nicht «Kontingent weg», sondern
«es wurde nie etwas angestossen». Wer beides verwechselt, wartet auf ein
Kontingent, das nie das Problem war.

**Die Anforderung in Prosa zu erwähnen, IST eine Anforderung.** Am 18.9. stand
in einem erklärenden Kommentar der Satz «sobald Kontingent da ist, die
Review-Anforderung posten» — mit der Auslöser-Zeichenkette wörtlich darin, in
Backticks und mitten im Fliesstext. Neun Sekunden später (Kommentar 13:57:27,
Meldung 13:57:36) schrieb Codex eine zweite Kontingent-Meldung. Der Bot
unterscheidet nicht zwischen Anfordern und Erklären, und Backticks schützen
nicht. In Kommentaren also nur schreiben, wenn man es meint; sonst umschreiben.
Hier war es folgenlos, weil das Kontingent ohnehin leer war — bei vorhandenem
hätte es einen ungewollten Review zu einem beliebigen Zeitpunkt gestartet und
aus demselben Topf bezahlt.

**Und ein frisches Gelb ist noch kein Urteil.** `codex-gate` setzt den Status
sofort beim Laufstart auf `pending`, bevor der Poll etwas gesehen hat. Ein
gelber Status wenige Sekunden nach einem Auslöser ist deshalb der Startwert und
kein Befund; das Urteil kommt bis zu `POLL_MAX_SECONDS` später. Am 18.9. sah
dieses Startgelb nach einem Gate-Defekt aus («Kontingent-Meldung müsste rot
setzen») — 44 Sekunden später stand es korrekt auf rot. Erst den Lauf abwarten,
dann den Defekt behaupten.

Das Kontingent hängt am Konto, nicht am Repo, und Code-Reviews haben einen
eigenen Topf — nur GitHub-getriggerte Reviews zählen hinein. ChatGPT-Pläne
fahren ein rollendes Fünf-Stunden-Fenster plus Wochenlimits; welches greift,
steht im Codex-Dashboard. Welches hier griff, ist **offen**. Die Lücke oben
schliesst das Fünf-Stunden-Fenster nicht aus: Es kann sich zwischendurch
geöffnet und durch neue Auslöser wieder erschöpft haben. Das auszuschliessen
bräuchte den Nachweis, dass in der ganzen Spanne kein einziger Review durchlief
— den gibt es nicht, weil nur Fehlschläge beobachtet wurden. Eine lange Reihe
von Fehlschlägen belegt eine lange Reihe von Fehlschlägen, nicht ihre Ursache.

Zeigt das Dashboard freies Kontingent, während Reviews weiter scheitern, ist
das ein bekannter Fehler bei mehreren verbundenen Konten — dann den
GitHub-Connector in den Codex-Einstellungen trennen und neu verbinden.

Die Environment legt man unter `chatgpt.com/codex/cloud/settings/environments`
an, und zwar **je Repo**. Die Meldung sagt es selbst («for this repo»), und am
23.8. war es genau so: In `swiss-public-data-mcp` fehlte sie, dort kam kein
Review; in den übrigen Repos lief Codex am selben Morgen durch. Eine
Environment fürs Konto genügt also nicht — wer eine anlegt und den Rest für
erledigt hält, mergt weiter Ungeprüftes.

### Wenn zwei Agenten dasselbe tun

Vor dem Anlegen eines Branches mit vorgegebenem Namen prüfen, ob es ihn schon
gibt:

```bash
git ls-remote --heads origin claude/<name> | wc -l
```

Steht dort `1`, arbeitet jemand anderes daran — mit Schreibrecht auf denselben
Ref.

Ein PR mit leerem Diff wird geschlossen, nicht gemergt. Der Test ist
`get_files` auf dem PR: kommt `[]` zurück, ändert er nichts. Ein grüner Check
sagt dazu nichts — die CI prüft den Head, nicht die Differenz zur Basis.

Am 21.8.2026 liefen zwei Sessions dieselbe Aufgabe über 45 Repos, auf den
Branches `claude/codex-review-audit-templates-9sn6mx` und
`claude/codex-review-audit-7ioh56`. Wo die eine zuerst nach `main` kam, wurde
`main` in den Branch der anderen gemergt und der add/add-Konflikt zugunsten
von `main` aufgelöst. Übrig blieben 14 PRs, die durch sämtliche Gates grün
liefen und nichts enthielten; sie wurden gemergt und hinterliessen leere
Merge-Commits. Mit den zwei Folge-PRs, die aus demselben Grund gegenstandslos
waren, waren 16 der 59 PRs jenes Tages reine Reibung.

Dieselbe Klasse wie der handgeschriebene Stub, der denselben Feldnamen annahm
wie der Code: Nichts ist rot, weil nichts geprüft wird, worauf es ankommt.

## Teil 2 — dieses Repo

**ruff:** genau eine Quelle — der exakte Pin im `[dev]`-Extra von
`pyproject.toml`. Ein Install des Extras reicht also, lokal wie in der CI.
Die Nummer steht hier bewusst **nicht**: Sie stand es, und der Abschnitt, der
«genau eine Quelle» verspricht, war damit selbst die zweite. Am 18.9.2026 nannte
er `0.16.3`, während `pyproject.toml` nach zwei Dependabot-Bumps auf `0.16.5`
stand — ausgerechnet der Absatz, der vor ruff-Versionsdrift warnt, war
abgedriftet. Wer die aktuelle Zahl braucht, liest sie dort:

```bash
grep 'ruff==' pyproject.toml
```

Keine zweite Version in die Workflows schreiben: ein solcher Schritt läuft
nach dem Install und überstimmt den Pin still — er stand hier an zwei Stellen,
in den Jobs `test` und `lint` (`test_dependencies.py` hält beides fest). Eine
`.pre-commit-config.yaml` gibt es nicht.

**Und nicht das `ruff` aus dem `PATH` nehmen.** Ein älteres früher im `PATH`
schlägt den Pin, ohne etwas zu melden. `ruff --version` zu prüfen reicht dafür
nicht — es sagt, welches gewinnt, aber nicht, dass das falsche gewinnt. Den
Interpreter entscheiden lassen; in der CI gibt es nur das eine ruff, lokal
nicht, deshalb steht dort `ruff` und hier `python -m ruff`:

```bash
python -m ruff --version      # muss die Zahl aus pyproject.toml sein
python -m ruff check src/ tests/ scripts/
```

Am 18.9.2026 lag in dieser Umgebung `ruff 0.15.8` vor dem damals gepinnten
`0.16.4`; `ruff format --check` meldete prompt eine Abweichung, die mit dem
richtigen Binary verschwand. Auch der Installationsausgabe nicht glauben:
`pip install -e ".[dev]"` lud sichtbar `ruff-0.16.5` herunter und schrieb in
dieselbe Zusammenfassung `ruff-0.16.4`. Gemessen wird mit
`python -m ruff --version`, nicht mit dem, was pip behauptet.

**Gates, wörtlich aus der CI** (Job `test`, dazu `lint` mit denselben zwei
ruff-Schritten plus dem Versions-Sync):

```bash
ruff check src/ tests/ scripts/
ruff format --check src/ tests/ scripts/
python -m py_compile src/swiss_environment_mcp/server.py src/swiss_environment_mcp/api_client.py
python -c "from swiss_environment_mcp.server import mcp; print('Import OK')"
python scripts/tool_snapshot.py check     # PYTHONPATH=src
pytest -m "not live" -v                   # PYTHONPATH=src
python scripts/check_version_sync.py
```

**Weitere Gates hängen an jedem PR, ausserhalb von `ci.yml`:**

- `security.yml` — gitleaks über History *und* Working Tree, Konfig
  `.gitleaks.toml`. Läuft immer.
- `image-size.yml` — baut das Image und bricht über einem Ceiling von
  **350 MB** ab (Audit SCALE-004). Läuft **nur**, wenn `Dockerfile`,
  `pyproject.toml` oder `src/**` im Diff sind.

**Ein drittes PR-Gate, und es prüft keinen Code:** `codex-gate.yml`. Es setzt
einen Commit-Status `codex-gate` auf den PR-Head und wird nur grün, wenn Codex
diesen Head nachweislich geprüft hat — Review-Objekt ODER Befundlos-Meldung.
Kontingent- und Environment-Meldung lassen es **rot**: Beide heissen
ausdrücklich «nicht geprüft», und ohne Handlung ändert sich daran nichts. Seit
dem Formatwechsel vom 29.8. zählt zusätzlich die Summary-Tabelle: `Completed`
für den Head ist ein Nachweis, `Running` hält auf **gelb**, ein drittes
Statuswort wird zitiert statt geraten. Ihre Frische hängt an der Commit-Spalte,
nicht an `created_at` — Gründe oben. Mehrere Zeilen zählen einzeln: Solange eine
läuft, ist der Head nicht fertig geprüft. Zusammengeführt wird nach Schwere: Was
ausdrücklich «nicht geprüft» sagt, schlägt jede Fertigmeldung. Ein Draft steht
auf **gelb** — er ist ohnehin nicht mergebar, und ein Repo, in dem jeder Draft
ein rotes Kreuz trägt, bringt seinen Leuten bei, rote Kreuze zu übersehen. Das
Gate hat sich diese Lektion selbst erteilt: Seine ersten beiden Läufe färbten
zwei frische Draft-PRs rot.

**Der Check-Run des Gate-Jobs ist nicht das Gate** — und am 18.9.2026 hat er
das Spiegelbild derselben Lektion vorgeführt. Weil der Job das Urteil nicht
trägt und immer mit 0 endet, sagt sein Check-Run über Codex gar nichts. Er hiess
trotzdem «Codex hat diesen Head geprueft» und log damit in beide Richtungen: Auf
PR #116 stand er um 10:23:49 auf **grün**, während `codex-gate` in derselben
Minute «PR ist ein Draft — Codex laeuft darauf nicht an» meldete. Die Checkliste
behauptete eine Prüfung, die der Status ausdrücklich verneinte. Ein grünes
Häkchen, das lügt, ist schlimmer als ein rotes Kreuz, das man übersehen soll:
Beim Kreuz schaut wenigstens noch jemand hin. Der Job heisst jetzt nach seiner
Tätigkeit (`codex-gate: Status setzen`), nicht nach fremdem Urteil.

Die zweite Richtung derselben Verwechslung: `cancel-in-progress: true` räumte
einen laufenden Poll ab, sobald ein neues Signal eintraf — bei einem
Poll-Fenster von 900 s traf das fast jeder Codex-Kommentar. Der abgebrochene
Lauf blieb als `cancelled` in der Liste stehen und sah aus wie eine
gescheiterte Prüfung.

Hier stand, das sei unvermeidbar: `false` verschiebe den Abbruch nur vom
laufenden auf den wartenden Lauf. **Auch das war falsch**, aufgedeckt von einem
Codex-Review auf PR #117 (P2). GitHub räumt einen *wartenden* Lauf erst ab, wenn
ein weiterer derselben Gruppe dazukommt — bei `false` braucht ein Abbruch also
**drei** überlappende Läufe, bei `true` genügen **zwei**. Der beobachtete Fall
auf #116 waren genau zwei (`ready_for_review` plus «Running»-Kommentar); mit
`false` wäre dort nichts abgebrochen worden.

Zwei Messungen kippten den Rest der Begründung: Die Poll-Schleife liest
`pr.head.sha` in **jeder** Iteration neu — ein laufender Lauf folgt einem Push
von selbst, der Grund ihn zu töten fällt weg — und sie bricht ab, sobald ein
Urteil feststeht. Das Gate steht deshalb auf `cancel-in-progress: false`:
Anstehen statt töten schliesst die Gleichzeitigkeit genauso aus.

**Die Einstellung wirkt aber nicht dort, wo man sie hinschreibt.** Am 18.9.2026
lag `false` im PR, und der Gate-Lauf von #118 wurde trotzdem abgeräumt: 17:02:50
gestartet, 17:04:06 `cancelled`. Keine falsche Einstellung, sondern eine
Versionsschere. Bei `pull_request` nimmt GitHub die Workflow-Datei aus dem PR,
bei `issue_comment` dagegen aus dem **Default-Branch** — und dort stand noch
`true`. Der Kommentar-Lauf mit der alten Fassung tötete den PR-Lauf mit der
neuen, denn die Concurrency-Gruppe verbindet die beiden Fassungen, sie trennt
sie nicht.

**Hier stand zuerst `pull_request_review` in derselben Aufzählung. Das war
falsch**, aufgedeckt von einem Codex-Review auf PR #119 (P2). Gemessen war nur
der Kommentar-Lauf; das Review-Ereignis hatte ich dazugeschrieben, weil es in
dieselbe Schublade zu passen schien — eine Verallgemeinerung über die Messung
hinaus, und damit genau der Fehler, gegen den dieser Teil geschrieben ist. Die
Gegenprobe liegt vor, zwei Läufe aus derselben Minute am 19.9.2026:

| Lauf | Ereignis | `head_branch` | `head_sha` |
|---|---|---|---|
| 92 | `pull_request_review` | `claude/tender-edison-mc5jyr` | `bfa2cdd` (PR-Head) |
| 93 | `issue_comment` | `main` | `a66698a` |

Die Ereignistabelle von GitHub sagt dasselbe: `pull_request_review` trägt
`GITHUB_REF: refs/pull/<N>/merge` wie `pull_request`, und der Satz «will only
trigger a workflow run if the workflow file exists on the default branch» steht
dort bei `issue_comment`, nicht bei den Review-Ereignissen. Am PR testbar sind
also beide PR-Ereignisse; blind bleibt allein `issue_comment`.

Zwei Handgriffe daraus:

- **Für `issue_comment` ist eine Änderung an diesem Workflow erst nach dem Merge
  scharf.** Wer sie am PR prüft, prüft die PR-Ereignisse; das Kommentar-Ereignis
  läuft weiter mit der alten Fassung. Verwandt mit `schedule` bei den Live-Tests
  weiter unten, nur tückischer: Dort bleibt die andere Hälfte aus, hier läuft
  sie falsch.
- **Ein so getöteter Lauf darf erneut gestartet werden.** Er ist an einer
  Kollision gestorben, nicht an einem Befund — derselbe Fall wie ein verlorener
  Runner, und keine Wiederholung gegen eine Absage. Am 19.9. um 07:08 setzte
  Attempt 2 des Laufs 35372017233 den Check-Run auf `success`, ohne den Head zu
  ändern; der Codex-Review auf `5c08df8` blieb damit gültig.

**Und `false` heisst nicht «keine abgebrochenen Läufe in der Liste».** Am 19.9.
standen mit `false` auf beiden Seiten vier Läufe derselben Gruppe gleichzeitig
an: 90 (`pull_request`), 91/93/94 (`issue_comment`), 92
(`pull_request_review`). Abgebrochen wurden 91, 92 und 93 — alle drei, während
sie *warteten*; der laufende 90 kam durch, und 94 lief danach. Das ist die
Mechanik aus dem #117-Befund in Reinform: Ein wartender Lauf fällt, sobald ein
weiterer derselben Gruppe dazukommt. Ein so abgeräumter Lauf hat aber nie einen
Job gestartet und hinterlässt deshalb **keinen** Check-Run am PR — die Liste von
#119 blieb 7/7 grün. Ein abgebrochener Lauf in der Actions-Liste ist also nicht
dasselbe wie ein abgebrochener Check-Run am PR; nur der zweite kostet etwas.

**Was hier kurz als Tatsache stand und falsch war:** dass ein abgebrochener Run
`mergeable_state` auf `unstable` setzt. Geschlossen aus #116, wo beides
gleichzeitig vorlag. Die Gegenprobe widerlegt es — PR #117 stand am 18.9.2026
auf `unstable` mit sechs grünen Runs und **keinem** abgebrochenen, während
`codex-gate` als Draft auf `pending` stand. Ein pendender Commit-Status genügt
allein; über den Beitrag eines abgebrochenen Runs sagt keine der beiden
Beobachtungen etwas. Merke: Zwei Ursachen, die immer zusammen auftreten, sind
kein Beleg für eine von beiden — dafür braucht es den Fall, in dem nur eine
vorliegt.

**Nachgetragen am 19.9.2026:** Für den *anderen* Zustand liegt der Fall jetzt
vor. Auf #118 wurde genau eine Grösse verändert — derselbe Check-Run ging von
`cancelled` auf `success` —, und `mergeable_state` kippte von `blocked` auf
`clean`. Ein abgebrochener Check-Run blockiert also, **sofern er selbst
required ist**. Über `unstable` sagt auch das nichts; das bleibt offen.

Bewusst kein Timer. Ein Gate, das nach N Minuten von selbst grün wird,
behauptet eine Prüfung, die es nicht gesehen hat — am 21./22.8. war das
Kontingent über eine Spanne von mindestens 25 h weg, ein Timer wäre die ganze
Zeit durchgelaufen. Die Wartezeit ist die Folge, nicht die Einstellung: Solange
kein Signal da ist, bleibt der Status rot.

Die Einordnung steht in `scripts/classify_codex_review.py` neben ihrem Test,
nicht im YAML — aus demselben Grund wie bei `classify_live_run.py`.

**Das Gate wirkt nur mit Branch Protection.** Der Kontext `codex-gate` muss auf
`main` als *required status check* stehen, samt «Do not allow bypassing the
above settings». Seit dem 19.9.2026 ist das nicht mehr nur die *gewollte*, sondern
die gemessene Lage — Beleg zwei Absätze weiter unten. Ohne die Protection bleibt
der Merge-Button klickbar. Am 28.8.2026 war
`main` hier `protected: false` — es gab überhaupt keinen Required Check, die
sechs grünen Häkchen waren informativ. Wer die Protection wegnimmt, nimmt
das Gate weg, ohne dass eine Datei sich ändert.

**Seit dem 18.9.2026 ist sie da:** `main` meldet `protected: true`, und PR #118
stand mit pendendem `codex-gate` auf `mergeable_state: blocked` statt wie zuvor
auf `unstable` — der Merge-Button ist also tatsächlich gesperrt.

**Welcher Check required ist, war am Vormittag des 19.9.2026 gemessen — und es
war der falsche.** (Nachmittags kam der richtige dazu, siehe unten.) Die Positivkontrolle, die hier als fehlend notiert stand, ergab sich
beim Entsperren von #118 von selbst: verändert wurde genau eine Grösse, der
Check-Run `codex-gate: Status setzen` ging von `cancelled` auf `success`, und
`mergeable_state` kippte von `blocked` auf `clean`. Required ist damit der
**Check-Run des Jobs** — ausgerechnet das Signal, das über Codex nichts aussagt,
weil der Job immer mit 0 endet. Erzwungen wird so «der Job ist gelaufen», nicht
«Codex hat geprüft»; das ist die Verwechslung von oben, diesmal in der
Repo-Einstellung statt im Jobnamen. In die Required-Liste gehört der Kontext
`codex-gate`.

Die Grenze blieb dabei: Die Messung zeigt, dass dieser eine Kontext required
ist, nicht dass er der einzige ist. Und `protected: true` aus `list_branches`
sagt weiterhin nur, *dass* eine Protection existiert; die Liste selbst liegt
hinter dem Branch-Protection-Endpunkt, den das hier verfügbare Werkzeug nicht
anbietet.

**Am 19.9.2026 hat der Maintainer `codex-gate` ergänzt.** Das ist zunächst eine
Aussage und keine Messung — ablesen lässt sich die Required-Liste hier nach wie
vor nicht. Getrennt wird sie über den Fall, den der Absatz oben schon benennt:
ein PR, bei dem **nur dieser Status** offen ist. Ein Draft liefert ihn frei
Haus, denn dort beendet sich der Gate-Job sofort («PR ist ein Draft»), sein
Check-Run wird grün, und der Commit-Status bleibt gelb.

Gemessen am 19.9.2026 an PR #124, zwei Zustände:

| Zustand | Check-Runs | `codex-gate` | `mergeable_state` |
|---|---|---|---|
| A — Draft | alle grün | pending | **blocked** |
| B — ready, nach Review | alle grün | success | **clean** |

**Was B ausschliesst:** eine Genehmigungspflicht und einen required Kontext,
der auf einem Doku-PR gar nicht berichtet — mit beidem wäre `clean` unmöglich.
Das ist schon mehr, als `protected: true` je hergab.

**Was A allein nicht trägt**, und ein Codex-Review auf diesem PR hat genau
darauf gezeigt: Zwischen A und B ändern sich **zwei** Grössen, der Status und
die Draft-Eigenschaft. Die historische Kontrolle — PR #117 stand am 18.9. in
Lage A auf `unstable`, ein Draft ist also nicht von sich aus `blocked` — lief
unter dem **alten** Ruleset und taugt deshalb nicht.

**Ein dritter Zustand sollte die einzelne Variable liefern — er tut es nicht,
und warum, steht unter der Tabelle.** Herzustellen war er mit Geduld statt mit
Rechten: ein **ready** PR nach einem Push. Ein Push löst keinen Review aus (Teil 1), der Poll lief also die vollen
`POLL_MAX_SECONDS` = 900 s leer — zweimal, weil der wartende Lauf der
Concurrency-Gruppe danach ebenfalls drankam. Erst als beide Gate-Läufe fertig
waren, stand der Zustand sauber:

| Zustand | Draft? | Check-Runs | `codex-gate` | `mergeable_state` |
|---|---|---|---|---|
| B | nein | alle grün, gleiche Menge | success | `clean` |
| C | nein | alle grün, gleiche Menge | **pending** | **blocked** |

Gleicher PR, gleiches Ruleset, gleiche Basis, kein Draft-Wechsel.

**Hier stand «verändert wurde genau eine Grösse». Das war falsch**, aufgedeckt
von einem Codex-Review auf PR #125 (P2). Zustand C entsteht durch einen
**Push** — mit dem Status wechseln auch der Head-SHA und der Inhalt des
Commits. Zwei Beobachtungen an zwei verschiedenen Heads trennen nichts, und
«dieselbe Menge grüner Check-Runs» schliesst eine andere kopfgebundene Regel
nicht aus. Das ist derselbe Fehler wie bei der historischen Kontrolle #117 zwei
Absätze weiter oben, nur eine Runde später bemerkt: Beide Male war die
Einzelvariable behauptet statt hergestellt.

**Die Messung mit festgehaltenem Head liegt seit dem 19.9.2026 vor**, an PR
#125, Head `7b548d9` in beiden Zeilen:

| Uhrzeit (UTC) | Draft? | Check-Runs | `codex-gate` | `mergeable_state` |
|---|---|---|---|---|
| 14:47:19 | nein | 6, alle grün und fertig | **pending** | **blocked** |
| 14:50:46 | nein | 7, alle grün | **success** | **clean** |

Der Head steht still, der Inhalt auch. Vom Nicht-Grünen zum Grünen wechselt
allein der Commit-Status. Was das mit ausschliesst: ein required Kontext, der
auf einem Doku-PR **gar nicht** berichtet — `image-size` wäre der Kandidat —
hielte beide Zeilen auf `blocked`; die zweite widerlegt ihn.

**Der Rest, den auch diese Messung nicht ausräumt**, und er gehört genannt
statt weggelassen: Zwischen den Zeilen kommt ein **siebter** Check-Run dazu,
ein zweiter Lauf von `codex-gate: Status setzen` (der `ready_for_review`-Lauf
neben dem `pull_request`-Lauf). Er kann keinen fehlenden Kontext nachliefern,
weil derselbe Kontext in der ersten Zeile bereits grün und fertig dastand —
aber eine Grösse ist er. Näher als so kommt man hier nicht heran, solange die
Required-Liste nicht abzulesen ist.

**In beiden Tabellen steht bewusst keine Zahl.** Hier standen erst welche —
6/6 für B in der oberen, 7/7 für dasselbe B in der unteren. Beide Male
abgelesen, beide Male an einem anderen Moment, und damit eine Tabelle, die
sich selbst widerspricht, ohne dass eine der beiden Zahlen falsch sein muss.
Tragend ist ohnehin nicht der Absolutwert, sondern dass B und C **dieselbe**
Menge zeigten.

Denn die Zahl ist als Variable unbrauchbar, und drei Mechaniken dahinter sind
gemessen. **Erstens** trugen von den Gate-Läufen zu #124 die aus
`issue_comment` als `head_sha` den Stand von `main` (`6a3cf1e`), die aus
`pull_request` und `pull_request_review` dagegen den PR-Head (`cc57770`) — der
Check-Run eines Kommentar-Laufs landet also gar nicht am PR, während der
Commit-Status, den derselbe Lauf per API setzt, sehr wohl dort ankommt;
dieselbe Trennung von Check-Run und Status wie oben, eine Ebene tiefer.
**Zweitens** hinterlässt der wartend abgeräumte Lauf überhaupt keinen
Check-Run. **Drittens** — und das ist die Quelle des 6 → 7 auf #125 — trägt
derselbe Head zwei Check-Runs *gleichen Namens*, sobald zwei PR-Ereignisse den
Workflow auslösen; `pull_request` und `ready_for_review` taten das um 14:46:05
und 14:50:38.

Wie viele Check-Runs ein Head trägt, hängt damit an der Auslöser-Mischung des
Augenblicks und nicht an dem Zustand, den man messen will.

**Und `mergeable_state` ist kein Messgerät mit Sofortanzeige.** GitHub
berechnet den Wert nachlaufend. Am 19.9. lieferte eine Abfrage um 14:50:38
`clean`, während der zugehörige Status erst um 14:50:46 auf `success` gesetzt
wurde — welche der beiden API-Antworten zuerst entstand, geben ihre Laufzeiten
nicht her. Als Datum zählt deshalb nur, was **stehen bleibt**: Zustand C hielt
sich rund 30 Minuten auf `blocked`, die `clean`-Zeile wurde nach dem Umschlag
erneut abgefragt. Ein Einzelwert unmittelbar nach einem Statuswechsel ist ein
Rauschwert.

Was weiterhin offen bleibt: ob der Check-Run des Jobs **zusätzlich** required
ist. Er war in allen drei Zuständen grün, also nie die veränderte Grösse. Der
Befund vom Vormittag (`cancelled` → `success` kippte `blocked` → `clean`) sagt,
dass er es damals war; ob die Liste ihn noch führt, sagt er nicht.

**Und dabei ist noch etwas anderes passiert.** Seit derselben Änderung melden
*sämtliche* Branches `protected: true`, nicht nur `main`; am Vormittag standen
die `claude/*`-Branches noch auf `false`. Das Ruleset greift also breiter als
`main`.

**Was es dort erzwingt, stand hier als ungemessen — und ist es seit dem
19.9.2026 nicht mehr.** Der Fall kam von selbst: #124 wurde gemergt, während
ein Korrektur-Commit noch entstand, der damit eine neue Basis brauchte. Der
übliche Rebase endete an der Sperre:

```
remote: - Cannot force-push to this branch
```

Ein *normaler* Push auf denselben Branch lief unmittelbar davor und danach
durch. Verboten ist also nicht das Schreiben, sondern das Umschreiben. Zwei
Handgriffe daraus:

- **Auf einem Arbeitsbranch dieses Repos ist der Rebase keine Option mehr.**
  Basis nachziehen heisst hier `git merge origin/main`, auch auf dem eigenen
  Branch — der Merge-Commit hält den Branch vorwärts-kompatibel und kommt ohne
  Force-Push aus.
- **Wer die Sperre für ein Netzproblem hält, verliert den Commit.** Die
  Meldung nennt eine Regelverletzung (`GH013`), keinen Übertragungsfehler; ein
  Wiederholungsversuch mit Backoff scheitert beliebig oft gleich.

Der Pfadfilter ist die Falle: Auf einem reinen Doku-PR fehlt dieser Check in
der Liste, und das ist der Normalfall, nicht das Symptom aus Teil 1. Erst
wenn *gar kein* Check läuft, gilt dort der Merge-Konflikt-Verdacht. Beide
brauchen Docker bzw. gitleaks und sind damit die zwei Gates, die sich nicht
so nebenbei lokal nachfahren lassen.

Vor dem Merge-Konflikt-Verdacht steht aber noch eine billigere Erklärung: Alle
drei PR-Gates filtern auf `branches: [main]` (`ci.yml`, `security.yml`,
`image-size.yml`). Ein PR gegen eine andere Basis läuft völlig ungeprüft — er
ist nicht grün, weil nichts zu beanstanden war, sondern weil nichts gefragt
wurde. Also erst die Basis prüfen, dann den Merge-Konflikt vermuten.

`draft-release.yml` ist kein Gate — nur `workflow_dispatch`.

**Ein Workflow, der nicht parst, wird nicht rot — er faellt aus.** GitHub
startet ihn gar nicht, es entsteht kein Check-Run, und in der Liste des PR
fehlt er einfach; nach Teil 1 sucht man dann zuerst den Merge-Konflikt. Am
18.9.2026 ist genau das um Haaresbreite passiert: `name: codex-gate: Status
setzen` ist ungueltiges YAML (unquotierter Skalar mit «: »), und geprueft hat
es im Repo nichts — `test_dependencies.py` liest die Workflows als *Text*.
Seither hält `tests/test_workflows.py` beide Halften fest: dass jede Datei
parst, und dass sie `on:` und `jobs` trägt. Das zweite ist nicht Zierde — eine
geleerte Datei parst (`yaml.safe_load("")` ist `None`) und käme sonst durch.

Dafür steht `pyyaml` im `[dev]`-Extra, als Spanne und nicht exakt gepinnt: Es
entscheidet, ob gültiges YAML parst, und daran ändert ein Minor-Update nichts.

**Den `on:`-Block nicht über `safe_load` suchen — in keiner der beiden
Richtungen.** PyYAML ist YAML **1.1**, dort wird das blanke `on:` zum Boolean
`True`; die Schlüssel von `ci.yml` sind `['name', True, 'jobs']`. Wer auf
`"on"` prüft, baut sich also einen Fehlalarm auf jeden Workflow. Die
naheliegende Gegenrichtung ist aber die gefährliche: `on:`, `true:` und `yes:`
landen alle auf demselben Schlüssel `True`, `1:` landet auf `1`, und
`1 == True` ist in Python wahr. Ein Workflow mit `true:` statt `on:` hat für
GitHub **gar keinen Auslöser** und läuft nie — eine Prüfung auf `True` bliebe
grün, also blind für genau das lautlose Verschwinden, um das es hier geht.
Aufgedeckt von einem Codex-Review auf PR #118 (P2), nachdem die
Fehlalarm-Richtung schon dokumentiert war.

Gelesen wird deshalb die **geschriebene Form** statt des aufgelösten Werts:
`yaml.compose` hält beim Knotenbaum an, wo ein Schlüssel-Skalar seinen Text
noch trägt (`'on'`, `'true'`, `'1'`). `oberste_schluessel()` in
`tests/test_workflows.py` macht genau das.

Die Matrix setzt kein `fail-fast: false`: Eine rote 3.11 bricht 3.12 und 3.13
ab, bevor sie etwas sagen.

Es gibt kein Coverage-Gate. Kein `include` unter `[tool.ruff]` setzen — der
Umfang sind die drei Pfade im Gate-Befehl selbst. Wer ihn prüfen will, zählt
nach statt hier abzulesen: `ruff check src/ tests/ scripts/ --show-files | wc -l`.
`ruff format` meldet dabei eine Datei mehr als `ruff check`, weil 0.16 auch
Markdown formatiert und damit `tests/fixtures/PROVENANCE.md` mitnimmt — zwei
Zahlen, kein Fehler.

**Fixtures: vorhanden, 20 Stück plus `tests/fixtures/PROVENANCE.md`** mit
Aufnahmedatum und dem Grund für den Schnitt — eine Antwort je *Abfrage*, nicht
je Endpunkt, weil fast alles über denselben SPARQL-Endpunkt läuft. Neu
aufzeichnen mit `PYTHONPATH=src python scripts/record_fixtures.py`.

**Live-Tests:** `.github/workflows/live-tests.yml`, nächtlich per Cron
(`0 4 * * *`) plus `workflow_dispatch`. Sie sind hier also nicht bloss per
`-m "not live"` ausgeschlossen. Der Lauf wird nicht am Exit-Code gemessen,
sondern von `scripts/classify_live_run.py` in `clear` / `finding` / `unknown`
eingeordnet — ein Lauf, in dem alles übersprungen wurde, gilt nicht als
Erfolg, und nur ein `finding` öffnet ein Issue. `unknown` schliesst keines.
`schedule` greift nur auf dem Default-Branch: Eine Änderung an Kadenz oder
Workflow ist auf einem Branch wirkungslos und wird erst nach dem Merge scharf.
Vorher von Hand per `workflow_dispatch` prüfen.
