# Technische Referenz: Trainings- und Wettkampfanalyst

Zur kurzen [Bedienungsanleitung mit Beispiel](analyst.md).

Diese Referenz beschreibt Architektur, Berechnungen und Schnittstellen.

## Bestandsaufnahme und Umsetzung

Ausgangsstand: `64deee9`, davor Dashboard-Verbesserungen (`913c32d`),
Stack-Steuerung (`0fad13c`) und Entkopplung der Startseite vom LLM (`4682089`).
Vor Beginn war ausschließlich `llm/prompts.py` geändert. Die damals ergänzten Regeln zu Zeitprognosen wurden erst nach dem expliziten
Folgeauftrag durch Vorbereitungsindex-Regeln ersetzt. Das LLM berechnet
keine Indexwerte oder Fitnessprognosen.

Die Anwendung bestand aus FastAPI/OpenAI-API (`api.py`), httpx-Adapter
(`intervals/intervals_client.py`), `FitnessAnalyzer`, MCP-Server und lokalem
llama.cpp-Client. Jinja/JS-Dashboard lief als separater HTTP-Client der API.
Vorhanden waren Aktivitäten, Details/Streams/Splits, Namenssuche, Zonen/FTP,
aktueller Wellness-Status und gefilterte kommende Wettkämpfe. Es gab keine
Planarchive, Importer oder lokale Datenbank. CTL/ATL stammten aus Intervals;
Form wurde als CTL minus ATL ergänzt. Das Coaching erzeugte Empfehlungen
über einen eigenen Prompt und einen Dashboard-Endpunkt.

Wiederverwendet werden Adapter, Workout-Modelle, Such-/Detailfunktionen,
MCP-Transport, Tool-Planer, LLM-Client, OpenAI-API, Templates, Chat, Dashboard-
Container und Startskript. Modellkonfiguration und llama.cpp-Parameter bleiben
unverändert. Die damaligen Tests deckten diese Schnittstellen, Streamstatistik,
Dashboard und Coaching ab. Coaching-Generierung wurde entfernt; alte
Empfehlungsmodelle und der vom Benutzer bearbeitete Legacy-Prompt bleiben
zur Kompatibilität erhalten. Beide alten HTTP-Coaching-Routen antworten mit 410.

Umgesetzt wurde in dieser Reihenfolge: validiertes Archiv und SQLite-Ziele,
Kalender/Wellness-Adapter, Planzuordnung und Soll/Ist, Fitnessberechnungen und Vorbereitungsindex,
Dashboard, Analyst-Prompts/MCP, Tests und Betriebsdokumentation.

## Datenfluss und Schnittstellen

- Intervals ist führend für Kalender und absolvierte Aktivitäten. Der Client
  liest `/athlete/{id}/events`, `/wellness` und die bestehende Activities-API.
  Erfolgreiche GETs werden pro Prozess 120 Sekunden lang gecacht, maximal 128
  Einträge. Kalender-Synchronisation liest nur; sie schreibt nie zu Intervals.
- `fitness/analyst.py` orchestriert die Datenquellen und isoliert Ausfälle;
  `plan_analysis.py` ordnet zu, `projections.py` berechnet deterministisch.
- `fitness/archive.py` verwaltet portable JSON-Pläne und SQLite mit lokalen
  Zielen, Korrekturen und Indexschnappschüssen. Keine zusätzliche Abhängigkeit.
- `GET /analyst/summary`, `GET/PUT /analyst/plans`,
  `PUT /analyst/assignment`, `PUT /analyst/races` ergänzen die bisherige API.
  Race-/Plan-PUT nimmt jeweils ein vollständiges, validiertes Modell entgegen.
  Bestehende IDs zur Bearbeitung mitsenden. Lokale Ziele ändern keine Kalender.
- MCP: `get_training_analysis(section)` liefert overview/week/plan/fitness/
  comparison/races, `search_training_plan(query, plan_id, week)` durchsucht
  höchstens 30 Archiveinheiten je Antwort. Fitnessreihen fürs LLM sind wöchentlich
  abgetastet, fürs Dashboard täglich. Der Chat nutzt weiterhin dieselben
  Tokenlimits und den bisherigen Tool-Plan-/Antwort-Ablauf.

Die Intervals-Felder sind optional: Events verwenden `start_date_local`,
`category`, `moving_time` (Sekunden), `distance` (Meter), `icu_training_load`,
`icu_intensity` (Prozent); RACE_A/B/C markieren Wettkämpfe. Aktivitäten können
`paired_event_id` und `race` liefern. Die Namenssuche und Detailauswertungen
bleiben eigenständige Tools. Referenz: https://intervals.icu/api-docs.html und
https://forum.intervals.icu/t/api-access-to-intervals-icu/609/1.
Keine Prüfung mit privaten Live-Aktivitäten ist Bestandteil der Tests.

## Lorang-Direktimport

`fitness/lorang_import.py` adaptiert die Quellstruktur des vorhandenen
`lorang-intervals-converter`: direkte Pläne oder `userTrainingPlan`, echte
`weeks` statt Sample-Wochen, explizite Wochen-/Tagesnummern und Sportzuordnung.
Er benötigt weder dessen Kalenderimport noch eine Laufzeitabhängigkeit zum
Nachbarprojekt. Inhalte und Varianten bleiben über inhaltsbasierte Archiv-IDs
getrennt; identische Inhalte werden wiedererkannt. Rohschritte und Zusatzangaben
werden in `source_details` erhalten. Die kompakte MCP-Suche schickt diese
umfangreichen Rohstrukturen nicht standardmäßig an das Modell.

Die CLI unterstützt einzelne Dateien, mehrere Dateien und Verzeichnisse mit
`--pattern`. `--dry-run` liest und validiert ohne Archiv- oder Datenbankänderung.
Dateifehler werden einzeln gemeldet; andere Dateien werden weiterverarbeitet.
Anleitung und genaue Befehle: [Trainingsplanarchiv](../training_plans/README.md).

## Erkennung und Soll/Ist

Die Erkennung kombiniert aktuelle Kalenderwoche, Planstart, Planname/Aliasse,
Phasen und ähnliche Sessiontitel samt Sportart. Week/Woche/Wk/W plus Zahl
werden erkannt, Groß-/Kleinschreibung und Trennzeichen normalisiert.
Mehrere Kandidaten bleiben sichtbar; bei geringem Abstand oder schwacher
Evidenz gibt es keinen aktiven Plan. Die Punkte sind eine Heuristik, keine
statistische Wahrscheinlichkeit. Manuelle Zuordnung hat Vorrang.
Ohne Archiv ist keine sichere Planidentität möglich. Individuelle Namensmuster
können über Planaliase und Sessiontitel ergänzt werden.

Explizite Aktivitäts-/Event-Verknüpfungen haben Vorrang. Sonst werden Name,
Sportart und maximal drei Tage Abstand verglichen. Dafür wird das lokale
Intervals-Kalenderdatum verwendet. Widersprüchliche explizite Verknüpfungen
bleiben unsicher und werden nicht durch Namensheuristiken überschrieben. Nur eindeutige eins-zu-eins
Treffer gelten als abgeschlossen/verschoben. Mehrfachbelegungen bleiben
unsicher. Mehrere Sportarten am gleichen Tag werden getrennt behandelt;
gekoppelte Einheiten funktionieren bei getrennten Aktivitäten/Verknüpfungen.
Eine einzelne Aktivität wird niemals spekulativ auf mehrere Soll-Einheiten
aufgeteilt. Fehlende Zuordnung beweist keinen Ausfall. Wochenvergleiche zeigen
Kalenderwochen, für Soll die geplanten Daten und für Ist die tatsächlichen Daten.

### Sichtbare und verlässliche manuelle Zuordnung

Die Zusammenfassung enthält `selected_assignment`, gespeicherte Zuordnungen
und eine verständliche Statusmeldung (aktiv, künftig, abgelaufen oder außerhalb
der Planwochen). Bei überlappenden Zuordnungen hat die zuletzt gespeicherte
Korrektur Vorrang; frühere Datensätze bleiben erhalten. Der Start der Planwoche 1
muss ein Montag sein. Das Dashboard belegt Plan und Zeitraum nach dem Speichern
wieder vor. Optional kann die aktuelle Planwoche eingegeben werden; daraus werden
Planstart und Gültigkeitsende vorgeschlagen. Nicht passende Werte werden mit
konkreten Validierungsfehlern angezeigt.

Das HTML-Formular besitzt zusätzlich einen normalen POST-Speicherweg, sodass
blockiertes JavaScript die Zuordnung nicht als bloßen Seitenaufruf verschluckt.
JavaScript zeigt Erfolg oder Fehler und bleibt auch bei gesperrtem Webspeicher
nutzbar. `node tests/dashboard_ui.test.cjs` prüft die Formularlogik unabhängig
von einem Browser.

`TrainingAnalyst.local_plan_context()` liest die manuelle Zuordnung und die
archivierten Vorgaben der aktiven Woche ohne Intervals-Abfrage. API- und
Terminal-Chat geben diesen Kontext sowohl an die Tool-Planung als auch an die
Antwortgenerierung weiter. Das MCP-Tool `get_training_analysis(section="plan")`
liefert ebenfalls die aktiven Wocheninhalte. Umfangreiche Rohstrukturen bleiben
außerhalb dieses kompakten Kontexts; Kalenderplanung und Archive werden als
unterschiedliche Quellen gekennzeichnet.

## Fitnessmodell

Historie: beobachtete CTL/ATL aus Wellness, TSB = CTL − ATL. Trend zeigt die
Differenz der ersten/letzten verfügbaren Werte mit Datum. Umfang/Häufigkeit,
Soll/Ist und TSS werden über acht Wochen aggregiert. Intensitätsverteilung ist
Dauer nach mittlerer Aktivitätsintensität, ausdrücklich keine Zeit-in-Zonen.

Szenario: tägliche exponentielle Fortschreibung
`CTL += (TSS − CTL) × (1 − exp(−1/42))`, analog ATL mit 7 Tagen.
TSB wird nach der jeweiligen Tageslast als CTL − ATL ausgewiesen; andere
Plattformen können einen anderen Tagesbezug oder individuelle Zeitkonstanten
verwenden. Ein älterer datierter Wellness-Ausgangswert wird zunächst ausschließlich
mit den absolvierten Aktivitäten bis heute fortgeschrieben. Dann folgt der
zukünftige Kalender, mindestens 42 Tage bzw. bis zum nächsten Wettkampf.
Datenabruf und numerische Prognose reichen höchstens ein Jahr voraus. Liegt
der Wettkampf später, endet die Prognose am Kalenderhorizont mit explizitem
Hinweis auf fehlende Planwerte. Auch innerhalb dieses Jahres bleibt Kalender-Vollständigkeit eine Annahme.

Explizite TSS 0 bleiben bekannt. Fehlen TSS, sind bei expliziter Dauer und
numerischer Intensität (Prozent) Schätzungen möglich:
`Dauer_in_Stunden × (Intensität/100)^2 × 100`.
Sie werden pro Tag als geschätzt markiert. Das ist eine vereinfachte IF-basierte
Belastungsschätzung, keine Rekonstruktion von HR-/Pace-Zonen. Sonst werden CTL,
ATL und TSB ab dem unvollständigen Tag nicht weiter numerisch ausgegeben.
Leere Kalendertage zählen im Szenario als 0; dies beweist keinen Ruhetag.
Grafik unterscheidet beobachtete Daten (Linie) von Planwerten (gestrichelt).

## Wettkämpfe und Prognosegrenzen

Rennen werden per Intervals-ID verknüpft, neue lokale Rennen bei eindeutigem
identischem Namen und Datum zusammengeführt. Synchrone Namens-/Datumsänderungen
überschreiben keine Ziele, Distanzen, Wechselvorgaben oder lokalen Statuswerte.
Mehrdeutige lokale Datensätze müssen ausdrücklich über source_id verbunden
werden. Entfernte Kalenderereignisse werden lokal nicht automatisch gelöscht.
Triathlon-Distanzen werden nicht aus dem Rennnamen geraten, sondern lokal erfasst.

## Wettkampfvorbereitung: preparation-v2

Die Rundanzeige liefert einen trainingsbasierten Index von 0 bis 100. Sie
übernimmt nicht Garmins internes Modell und ist **keine kalibrierte statistische
Erfolgswahrscheinlichkeit**. Sie erzeugt keine Wettkampfzeitprognose. `scope`
unterscheidet die allgemeine Trainingsbasis (`training_preparation`) von einem
zusätzlich belegbaren Zielvergleich (`training_and_goal`). Ein gespeichertes
Gesamtzeitziel allein macht aus der Trainingsbasis keine bestätigte Zielzeit.

### Nicht blockierende Aggregation

Pro Teilbereich begrenzt der schwächste auswertbare Vergleich dessen Score;
der schwächste verfügbare Teilbereich begrenzt den Gesamtwert. Es gibt keine
frei gewählten Prozentgewichtungen. Fehlende Kriterien erhalten weder 0 noch
100. Sie stehen als Hinweise neben den tatsächlich berechneten Vergleichen.
Ein einzelnes ungeklärtes Training blockiert weder den Planwert noch den
Gesamtindex. Der Anteil bestätigter Zuordnungen ist ein gesonderter Vergleich:
Er beschreibt die bestätigte Untergrenze der Planumsetzung, nicht die Anzahl
angeblich ausgefallener Trainings.

`coverage` enthält die Zahl auswertbarer und vollständig belegter Kernbereiche
von insgesamt vier. `provisional` kennzeichnet vorhandene Hinweise oder nur
teilweise auswertbare Bereiche. Die Zahl selbst ist keine Messung dieser
Datenqualität; es gibt keinen erfundenen Unsicherheitsabschlag. Planerfüllung
allein erzeugt weiterhin keinen Gesamtwert: mindestens ein unabhängiger
Leistungs- oder Ausdauervergleich muss vorliegen.

Fenster, Mindeststichproben, Vergleichstoleranzen und Farbbereiche sind
reproduzierbare Produktheuristiken, keine wissenschaftlich validierten Grenzen.
Auch 100 bestätigt nur die ausgewerteten Kriterien und garantiert kein Zeitziel.

### Verwendete Vergleiche

1. **Planumsetzung:** Soll-Daten von heute−31 Tagen einschließlich bis heute−3
   Tagen ausschließlich; die Verschiebungsfrist bleibt offen. Bestätigte
   Einheiten/fällige Einheiten sowie Median der paarweisen Übereinstimmung bei
   Dauer, TSS und mittlerer Intensität. Übereinstimmung ist
   `100 × min(Soll,Ist)/max(Soll,Ist)`; Mehrlast erhält keinen Bonus. Fehlende
   Metriken und ungeklärte Zuordnungen bleiben Hinweise. Vorhandene Vergleiche
   werden auch bei weniger als drei Paaren angezeigt, mit entsprechender Notiz.
2. **Leistungsentwicklung:** Zunächst unabhängige Direktpaare aus den letzten
   21 und den vorherigen 21 Tagen: Dauer ±20%, Puls höchstens 5 bpm auseinander;
   alternativ explizite Rennen mit Distanz ±10%. Beim Rad müssen beide Paare
   einen Leistungswert haben, bevor die nächste Einheit ausgewählt wird.
   Ab drei Direktpaaren wird deren medianes Verhältnis ausgewertet.
   Kommen nicht genug Direktpaare zustande, nutzt das Modell die Mediane aus
   mindestens drei Einheiten je Zeitfenster mit Puls und mindestens 15 Minuten
   Dauer: Radleistung/Puls, sonst Geschwindigkeit/Puls. Das Verhältnis der
   persönlichen Mediane aktuell/früher ergibt den auf 100 begrenzten Verlauf.
   Dieser `cohort_efficiency`-Vergleich ist ein Beobachtungsindikator bei
   gemischten Einheiten, kein kontrollierter Leistungstest. Intensität, Strecke,
   Wetter und Geräte können ihn beeinflussen; diese Grenze wird mitgeliefert.
   Falls auch das nicht möglich ist, bleiben ein oder zwei vorhandene Direktpaare
   vorläufig nutzbar. Historische FTP-Werte werden nicht erfunden.
3. **Ausdauer:** Referenz sind aktuelle und zwei vorherige Planwochen. Bei
   Peak/Taper oder innerhalb von 21 Tagen bis zum Rennen reichen die Referenzen
   bis zu sieben Wochen zurück. Mediane der drei längsten Plan-/Ist-Einheiten
   und typischer Umfang der letzten drei vollständigen Kalenderwochen werden
   verglichen. Distanzbasierte Schwimmpläne werden in km und km/Woche ausgewertet,
   zeitbasierte Vorgaben in Sekunden und Sekunden/Woche. Fehlende Distanzen
   werden nicht als 0 km gewertet; vorhandene Zeitvergleiche bleiben sichtbar.
   Beim Triathlon begrenzt zusätzlich der Anteil in den letzten 28 Tagen
   tatsächlich trainierter Wettkampfdisziplinen den Ausdauerwert. Eine reine
   Laufvorbereitung kann dadurch nicht als vollständige Triathlon-Vorbereitung
   erscheinen. Der Wert ist planrelativ und zertifiziert nicht die Eignung des
   externen Plans für Renndistanz oder Gelände.
4. **Belastungsverträglichkeit:** RPE-Paare gleicher Sportart bei ähnlicher TSS
   (±20%) aus zwei 21-Tage-Fenstern; mindestens drei Paare für den RPE-Vergleich.
   Zusätzlich persönliche Mediane von HRV, Ruhepuls oder Schlafdauer: letzte
   14 Tage gegen vorherige 28 Tage, jeweils mindestens sieben Messungen.
   RPE früher/aktuell, HRV bzw. Schlaf aktuell/früher, Ruhepuls früher/aktuell,
   jeweils auf 100 begrenzt. Fehlende RPE blockiert vorhandene Erholungsvergleiche
   nicht und umgekehrt. Das sind unspezifische Beobachtungen, keine medizinische
   Diagnose und kein Beleg kausaler Verträglichkeit. CTL/TSB allein ändern
   diesen Teilwert nicht.
5. **Optionaler Zielvergleich:** Eine Gesamtzielzeit genügt als Benutzervorgabe.
   Ohne Zeitziel wird die Vorbereitung ohne Zeitvorgabe bewertet. Bei einem
   Triathlon-Gesamtziel ohne Splits lautet der Status `target_recorded`; die
   Zielzeit wird nicht aus Einzelannahmen bestätigt. Der Code beendet diesen
   Zweig vor dem Leistungsabgleich; er stellt keinen Mangel der Benutzereingaben
   und keinen Beleg fehlender Gesamtrennnachweise fest. Eine automatische
   Ableitung der Gesamtziel-Erreichbarkeit aus Trainingsleistungen ist nicht
   implementiert. Freiwillige Disziplinziele
   können bei passenden Vergleichsrennen einen belegbaren Zielscore liefern.
   Fehlende oder widersprüchliche Zielnachweise werden nicht als Bestätigung
   gewertet und sperren die übrige Auswertung nicht.

### Anzeige, Verlauf und Ausfälle

Die SVG-Rundanzeige hat einen 270-Grad-Bogen mit vier Bereichen
(0–24 rot, 25–49 orange, 50–74 gelb, 75–100 grün), Zeiger und Textwert.
Die Farbbereiche sind visuelle Indexkategorien, keine medizinischen Grenzwerte.
Planphase, Rennabstand, Teilwerte, Rohvergleiche, Abdeckung und Hinweise bleiben
sichtbar bzw. aufklappbar. Die Anzeige heißt immer Wettkampfvorbereitung.
`limiting_factor` liefert bei Werten unter 100 den niedrigsten Rohvergleich
des begrenzenden Teilbereichs; er wird direkt unter der Uhr genannt. Bei 100
heißt es ausschließlich, dass die ausgewerteten Vergleiche erfüllt sind.
Die Farbbereiche werden nicht mit frei gewählten Leistungsurteilen verknüpft.
Ein offener Zielzeitbezug wird in einfachen Worten neben der Anzeige erklärt:
Die Punkte sagen nicht, ob die Leistung für die Wunschzeit reicht. Der Verlauf
ist als Beobachtungshilfe über Wochen gedacht, kleine Änderungen beweisen
keinen Leistungsfortschritt.

Es werden keine früheren Zahlen erfunden. Tägliche Schnappschüsse behalten
`model_version`; unterschiedliche Versionen werden im Diagramm nicht verbunden.
Ist die Aktivitätsquelle ausgefallen, kann ein ausdrücklich datierter letzter
Wert derselben Modellversion, desselben Renntermins und desselben Ziels angezeigt
werden (`cached`, `stale`). Er wird nicht als neue Berechnung gespeichert.
Bei geändertem Ziel wird kein alter passender Wert vorgetäuscht.

Ohne tatsächlich auswertbare Aktivitäts-/Vergleichsdaten erscheint ein Ladezustand
statt einer erfundenen 0 oder 100; die Pauschalmeldung „Datenlage unzureichend“
sperrt vorhandene Trainingsanalysen nicht mehr. Das LLM darf ausschließlich die
berechneten Werte interpretieren und muss Index, Datenabdeckung und tatsächliche
Zielzeitnachweise auseinanderhalten.

## Betrieb und Prüfung

Installation und Stack-Start stehen in der Haupt-README. Nach Änderung API/MCP
neu starten und Dashboard-Container neu bauen: `./fitness-ai.sh restart` bzw.
`docker compose up -d --build dashboard`. API und MCP greifen auf denselben
lokalen Archivpfad zu; der Dashboard-Container hält keine private Datenkopie.
Das Dashboard lädt berechnete Daten unabhängig vom LLM. Nur der explizit
abgesendete Chat benötigt das lokale Modell. Ziele können neu angelegt oder
bearbeitet werden; Zeiten werden im Formular in Sekunden eingegeben.

Tests: `uv run python -m pytest -q`. Sie verwenden synthetische Daten und
Mocks, keine reale LLM und keine private Intervals-Verbindung. Abgedeckt sind
Import/Validierung, Mehrdeutigkeit, manuelle Korrekturen, verschobene/mehrfache
Sessions, Prognoseformeln, fehlende Last, Rennensynchronisation, Zielerhaltung,
Index-Grenzen, Ausreißer, fehlende Daten, Phasenbezug, Zielbezug,
Quellenausfälle und Dashboard-Darstellung ohne LLM.

## Historischer Trainingsvergleich

Der neue Navigationspunkt **Trainingsvergleich** (`/comparison`) vergleicht zwei frei wählbare Zeiträume von jeweils höchstens 366 Tagen. Unterstützt werden einzelne Kalenderwochen, mehrere Wochen, beobachtete Base-/Build-Phasen und explizit zu einem bestätigten Wettkampftermin ausgerichtete Zeiträume. Ein Sportfilter, absolute/prozentuale Differenzen und interaktive Wochen- bzw. Fitnessverläufe erschließen die Daten schrittweise. Detailkennzahlen und Quellaktivitäten sind aufklappbar.

Die Integration nutzt denselben Intervals-Client und dieselbe private SQLite-Datenbank wie der übrige Analyst. Aktivitäten, Kalender und Wellness werden nur für benötigte Kalendermonate geladen. Historische Monate werden sieben Tage, aktuelle Monate zwei Minuten gecacht. Detailintervalle und Kommentare werden bei Bedarf geladen. Quellenstatus und Abrufzeit bleiben sichtbar; HTTP 429 respektiert `Retry-After`. Bereits gespeicherte Quellaktivitäten und Pläne werden nicht verändert. Die Snapshots spiegeln die aktuell von Intervals gespeicherten historischen Datensätze wider und sind kein revisionssicheres Archiv früherer Intervals-Einstellungen.

Titelhinweise wie `Build W3` oder `Base Week 5` werden anhand der lokalen Aktivitätsdaten auf eine gemeinsame Phasenstartwoche bezogen. Sie bleiben ausdrücklich Kandidaten und werden dauerhaft gespeichert. Namenlose Einheiten erhalten keine erfundene Phase. Vorbereitungen lassen sich mit Zeitraum und optionalem Wettkampftermin anlegen; jede geladene Aktivität oder geplante Einheit kann manuell einer Vorbereitung, Phase und Woche zugeordnet werden. Manuelle Angaben haben Vorrang. Überschneidende Zeiträume liefern lediglich Vorbereitungskandidaten. Eine komplette Vorbereitung oder ihr früherer Wettkampf wird nicht aus Titelähnlichkeit geraten.

Kennzahlen stammen ausschließlich aus gespeicherten Aktivitäts- und Wellnesswerten. Fehlende Gesamtsummen bleiben unbekannt, statt fehlende Werte mit null zu ersetzen. Mittelwerte zeigen ihre Abdeckung und sind ungewichtete Mittel der verfügbaren Einheiten bzw. Tage. Radleistung/FTP/W/kg und Laufschwellen werden nach Sportart getrennt berechnet. Historische FTP, Gewicht und Schwellen werden niemals mit heutigen Sporteinstellungen ergänzt. Die Aktivitätsdaten verwenden `start_date_local`; Wochen beginnen montags. TSB ist hier ausdrücklich CTL minus ATL. Umfang und TSS sind keine Bewertung der Leistungsfähigkeit.

Ähnliche Einheiten werden ohne Mehrfachverwendung anhand Sportart, bekannter Dauer/Distanz (±20 % gegenüber A) und – soweit vorhanden – Gesamtintensität (±10 Prozentpunkte) vorgeschlagen. Vergleichbarkeit bleibt eingeschränkt; Rohintervalle, Geräteinformationen und verfügbare Temperaturwerte können im Einzelvergleich geprüft werden. Intervall-Soll/Ist-Abschluss, Zonenvergleichbarkeit, kontrollierte Laufökonomie und eine belastbare LIT-/HIT-Verteilung sind ohne zusätzliche Belege nicht verfügbar. Es gibt keine automatische Leistungssteigerungs- oder Effizienzbehauptung aus einem Paar.

Persönliche Kommentare werden über die separate Aktivitätsnachrichten-Schnittstelle abgerufen und anhand der Autorenkennung von fremden Kommentaren getrennt. Originaltext, Zeitpunkt und Aktivitätsreferenz bleiben erhalten. Beschreibungen werden separat mit ungeklärter Urheberschaft angezeigt. Stichwortthemen dienen nur als Suchhinweise; sie interpretieren keine Negationen oder Entwicklungen. Die Schaltfläche zur KI-Einordnung lädt über vorhandene Agent-Tools Kommentare, RPE, Messwerte und Intervalle gemeinsam. Die Prompts verlangen Kontextprüfung, Belege, Widerspruchshinweise und die Trennung von Messung, Interpretation und Vermutung. Der Abruf ist auf 100 Nachrichten pro Aktivität begrenzt und kennzeichnet mögliche Kürzungen.

API: `POST /analyst/history/compare`, `GET /analyst/history/catalog`, `PUT /analyst/history/preparation`, `PUT /analyst/history/assignment`, `GET /analyst/history/pair?a_id=…&b_id=…`. Das Vergleichsobjekt enthält `a` und `b` mit ISO-Feldern `start`, `end`, optional `race_date`, sowie `sport` (`all`, `Ride`, `Run`, `Swim`). Die Dashboard-Routen reichen diese Anfragen an die Fitness-API weiter. MCP bietet `get_historical_comparison`, `get_historical_preparations` und `get_historical_session_pair`; Toolausgaben sind mengenbegrenzt und weisen Auslassungen aus. Bei Kommentaranfragen kann der Zeitraumvergleich über `include_comments` Originalkommentare für höchstens drei ähnliche Paare laden.

Tests: `pytest -q`, `node tests/dashboard_ui.test.cjs`, `node tests/history_ui.test.cjs`. Die UI-Logiktests prüfen mit synthetischen Daten unter anderem leere Quellen, Fehleranzeige, Wettkampfausrichtung, sichere Textausgabe und Tastaturinteraktion der Diagrammpunkte. Sie ersetzen keine visuelle Browserprüfung. Ein separater Typechecker ist im Projekt derzeit nicht konfiguriert.
