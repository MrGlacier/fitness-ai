# Trainings- und Wettkampfanalyst

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

## Vorbereitungsindex: preparation-v1

Der Index ist eine lokale, ausdrücklich **nicht wissenschaftlich validierte**
Entscheidungshilfe. Er übernimmt weder Garmins internes Modell noch dessen
Genauigkeit. **Vorbereitungsindex, keine Zielerreichungswahrscheinlichkeit.**
Es werden keine Wettkampfzeiten vorhergesagt, auch nicht aus CTL oder TSS.

### Aggregation ohne Prozentgewichte

Jeder belegte Vergleich ist ein Verhältnis zwischen Ist und expliziter Referenz,
auf 0–100 begrenzt. 100 bedeutet nur: das jeweilige Kriterium wird erfüllt.
Das Minimum der Vergleiche begrenzt die Teilbewertung; das Minimum der
vollständigen Teilbewertungen begrenzt den Gesamtindex (Engpassmodell).
Es gibt keine frei gewählten Prozentgewichtungen oder Kompensation einer
schwachen Disziplin durch andere Stärken. Die Anzeige wird auf ganze Punkte
gerundet, um zusätzliche Dezimalpräzision zu vermeiden.

Das Minimum ist eine bewusste konservative Produktregel, kein physiologisches
Gesetz. Alle folgenden Fenster, Mindeststichproben und Vergleichstoleranzen
sind dokumentierte Heuristiken, keine validierten Grenzwerte. Teilbewertungen
werden nur veröffentlicht, wenn ihre Mindestnachweise vollständig sind;
vorhandene einzelne Vergleiche bleiben trotzdem sichtbar. Fehlt eine erforderliche
Teilbewertung, erscheint statt der Gesamtzahl **Datenlage unzureichend**.
Fehlende Werte werden weder als 0 noch als erfüllte Kriterien eingesetzt.

### Teilbewertungen und Nachweise

1. **Planerfüllung:** Soll-Datum zwischen heute−31 Tagen (einschließlich) und
   heute−3 Tagen (ausschließlich); die letzte Verschiebungsfrist bleibt offen.
   Mindestens drei vollständige Vergleiche je Dauer, TSS und mittlerer Intensität.
   Pro Vergleich `100 × min(Soll,Ist)/max(Soll,Ist)`; über die Einheiten jeweils
   der Median. Mehrlast erhält keinen Bonus. Explizit verschobene Einheiten
   erhalten denselben Vergleich. Nicht zugeordnete Soll-Einheiten bleiben
   ungeklärt und verhindern eine vollständige Teilbewertung, statt als Ausfall
   zu zählen. Bekannt durchgeführte, aber in Umfang oder Intensität abweichende
   Einheiten können dagegen belegte Abzüge ergeben.
2. **Leistungsentwicklung:** Für jede Renndisziplin mindestens drei unabhängige
   Paare aus den letzten 21 Tagen und den vorherigen 21 Tagen. Vergleichbare
   Dauer ±20%, Puls höchstens 5 bpm auseinander; alternativ explizite Rennen
   mit Distanz ±10% und ebenfalls vergleichbarer Dauer. Jede ältere Beobachtung
   wird höchstens einmal verwendet, die Paarung erfolgt deterministisch nach
   Dauerabstand und ID. Bei Rad: gewichtete Leistung, sonst Geschwindigkeit.
   Median der Verhältnisse aktuell/früher, `100 × Verhältnis`, maximal 100.
   Ein stabiler Wert erfüllt das Verlaufskriterium, ist allein kein Beleg der
   Wettkampfbereitschaft. Veränderungen sind zusätzlich in Prozent sichtbar.
   Fehlende historische FTP-Reihen werden nicht rekonstruiert. Strecke,
   Wetter und Messgeräte bleiben mögliche Störfaktoren.
3. **Wettkampfspezifische Ausdauer:** Alle drei Triathlon-Disziplinen, sonst die
   Rennsportart. Referenz sind die aktuelle und zwei vorhergehende Planwochen,
   niemals pauschal die spätere Peak-Phase. Innerhalb von 21 Tagen zum Rennen
   sowie bei erkanntem Peak/Taper werden bis zu sieben vorherige Planwochen
   herangezogen, damit ein reduzierter Taper nicht als ausreichender neuer
   Ausdauernachweis gilt. Je Sport mindestens drei sichere Plan- und drei
   Ist-Einheiten aus den letzten 28 Tagen. Vergleich des Medians der drei
   längsten Einheiten mit dem entsprechenden Planmedian; falls mindestens
   drei Distanzen vorliegen, zusätzlich Distanzvergleich. Wochenumfang ist
   der Median der letzten drei vollständigen Kalenderwochen gegenüber dem
   Median der referenzierten Planwochen. Verhältnis Ist/Plan, maximal 100.
   Unsichere/fehlende Dauervorgaben verhindern die vollständige Bewertung.
   Der Index prüft hier die zum aktuellen Planabschnitt passende Vorbereitung;
   er zertifiziert nicht die Eignung des externen Plans für die Renndistanz.
4. **Belastungsverträglichkeit:** Drei unabhängige RPE-Paare derselben Sportart
   bei vergleichbarer TSS (±20%) in den zwei 21-Tage-Fenstern; Score aus dem
   Median RPE früher/aktuell. Zusätzlich mindestens ein Erholungsindikator
   (HRV, Ruhepuls, Schlafdauer) mit mindestens sieben Messungen in jedem Fenster:
   letzte 14 Tage gegen vorherige 28 Tage. HRV/Schlaf: aktueller Median/Basis;
   Ruhepuls: Basis/aktueller Median. Verhältnis maximal 100. Es werden
   unspezifische Beobachtungsindikatoren verglichen, keine Gesundheit,
   Verletzungsgefahr oder kausale Verträglichkeit diagnostiziert. TSS dient
   nur zur Vergleichbarkeit; CTL und TSB verändern diesen Teilscore nicht.
5. **Zielbezug:** Ohne Zeitziel nicht anwendbar, daher kein Pflichtbaustein.
   Mit Zeitziel sind je Disziplin zwei markierte Rennen der letzten 90 Tage
   mit ±10% Zieldistanz erforderlich. Nachgewiesene mediane Geschwindigkeit
   wird mit der erforderlichen Zielgeschwindigkeit verglichen, maximal 100.
   Für Triathlon müssen explizite `goal_splits_seconds` (Swim/Ride/Run) und
   `transition_seconds` vorliegen; ihre Summe darf das Gesamtziel nicht
   überschreiten. Es wird keine Disziplinzeit aus FTP oder CTL geraten.
   Die Einzelrennen belegen keine sichere Triathlon-Gesamtleistung.

Die Mindeststichproben und Mediane begrenzen den Einfluss einzelner Ausreißer.
Eine vollständige Zahlenbewertung erfordert alle vier Kernbereiche und, wenn
ein Zeitziel existiert, auch den Zielbezug. Ein Datenquellenausfall verhindert
eine neue Gesamtzahl. Phase, Rennabstand, Referenzwochen, offene Nachweise,
Vergleichswerte, Stichproben und positive/begrenzende Faktoren werden mitgeliefert.
„Belegt, methodisch begrenzt“ ist eine qualitative Datenqualitätsangabe, kein
statistisches Konfidenzmaß.

### Verlauf, Dashboard und LLM

`race_preparation` ersetzt `race_predictions` in `/analyst/summary` und MCP.
Das Dashboard zeigt Index, Teilbewertungen, Begründungen, Datenqualität,
Einflussfaktoren und den täglichen Verlauf als Grafik und Tabelle über bis zu
90 Tage. Verlauf entsteht ab Nutzung, ohne erfundene frühere Prozentwerte.
Jeder Schnappschuss enthält `model_version`; die Grafik verbindet verschiedene
Versionen nicht. `preparation_history` ist eine eigene SQLite-Tabelle.
Alte Zeitschätzungen werden weder gelöscht noch in Indexwerte umgerechnet.
Bei Datenquellenausfall wird der vorhandene Tagesschnappschuss nicht ersetzt.

Nur Anwendungscode (`fitness/preparation.py`) berechnet Indexwerte. Der Chat
nutzt berechnete Teilbewertungen und darf keine eigenen Prozentzahlen oder
Wettkampfzeitprognosen erzeugen. Lokale Disziplin-Zielzeiten sind ausdrücklich
Benutzervorgaben und werden im Dashboard in Sekunden bearbeitet.

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
