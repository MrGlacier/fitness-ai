# Zielzeit-Einschätzung: Modelle und Grenzen

Die Zielzeit-Auswertung (`race-time-v1`) ist unabhängig vom bisherigen
Planvergleich (`preparation-v2`). Ein gut erfüllter Plan ohne Zielzeit belegt
keine bestimmte Wettkampfzeit. `/analyst/summary` liefert dafür zusätzlich
`goal_predictions` pro Wettkampf. Keine neue Abhängigkeit und kein LLM sind
für die Berechnung erforderlich.

## Was wissenschaftlich begründet ist

Für Laufleistungen verwendet der Code das Potenzmodell
`T2 = T1 × (D2 / D1)^k`. Distanz und Zeit stammen aus aufgezeichneten
Einheiten. Ausgangspunkt ist [Riegel (1981)](https://www.rrtc.net/Articles/ARHE.pdf).
Der Standardexponent ist hier `k = 1,07`, entsprechend dem untersuchten
Vergleichsmodell bei [Vickers und Vertosick (2016)](https://doi.org/10.1186/s13102-016-0052-y).
Diese Studie mit Freizeitläufern zeigt ausdrücklich die Grenze: Für Marathon
waren die Standardvorhersagen häufig deutlich zu schnell. Die Anwendung
weist darauf hin und behauptet keine validierte Marathon-Fehlerspanne.

Wenn unterschiedlich lange persönliche Wettkämpfe vorhanden sind, wird `k`
aus dem Median der paarweisen logarithmischen Steigungen geschätzt. Das
folgt dem Gedanken individuell angepasster Distanz-Zeit-Kurven aus
[Modelling human endurance (2023)](https://doi.org/10.1007/s00421-023-05274-5).
Diese wissenschaftliche Grundlage validiert weder unsere gesamte Pipeline
noch die Übertragung von gewöhnlichem Trainingstempo auf maximale Leistung.

Beim Triathlon ist die Vorbelastung des Laufs relevant. Beispielsweise zeigt
[Etxebarria et al. (2013)](https://pubmed.ncbi.nlm.nih.gov/23347994/), dass die
Verteilung der Radleistung die anschließende Laufleistung beeinflussen kann.
Daraus lässt sich kein universeller persönlicher Zeitaufschlag ableiten.

Für Bergläufe begründet [Minetti et al. (2002)](https://pubmed.ncbi.nlm.nih.gov/12183501/)
die Bedeutung von Steigung und Gefälle. Wir wenden keine scheinbar exakte
Steigungskorrektur auf bloße Gesamt-Höhenmeter an. Ohne Streckenprofil fehlen
dafür die nötigen Angaben. Auch die verwendete Übertragung zwischen ähnlich
hügeligen Einheiten ist keine validierte Trail-Prognose.

Radleistung/FTP allein ergibt kein Straßentempo. Das physikalische Modell von
[Martin et al. (1998)](https://pubmed.ncbi.nlm.nih.gov/28121252/) benötigt unter
anderem Widerstands- und Streckenparameter. Solche Werte werden hier nicht
erfunden: Verwendet werden tatsächlich gefahrene Straßen-Geschwindigkeiten.

## Welche Einheiten verwendet werden

Die folgenden Auswahlgrenzen sind **Produktheuristiken**, keine publizierten
universellen Grenzwerte. Sie sind bewusst im Code nachvollziehbar:

- Aufzeichnungen der letzten 180 Tage, mindestens zehn Minuten und positive
  Distanz. Pro Disziplin werden bevorzugt markierte Rennen verwendet; sonst
  gewöhnliche Trainings. Das Kohortenfenster umfasst höchstens 56 Tage vor
  dem jüngsten passenden Nachweis. Bei Nachweisen älter als 42 Tage erscheint
  ein Hinweis. Es wird keine Alterungskorrektur erfunden.
- Distanzverhältnis zur Zielstrecke zwischen 0,5 und 2; bei Laufwettkämpfen
  darf die Ausgangsdistanz bis zu viermal kürzer sein. Kurze schnelle
  Intervalle werden nicht als dauerhaft haltbares Tempo behandelt.
- Virtuelle/Indoor-Geschwindigkeiten werden ausgeschlossen, auch bei einem
  ausdrücklich gesetzten Trainer-Flag. Bei Straßenrennen wird Gravel-/MTB-
  Geschwindigkeit nicht übernommen. Indoor-Leistungen bleiben im getrennten
  Plan-/Trainingsvergleich verfügbar; sie sind nicht wertlos.
- Bei Rad- und Laufeinheiten werden Höhenmeter verlangt. Für die implizite
  flache Vergleichsstrecke werden Einheiten über 15 Höhenmetern pro km
  ausgeschlossen. Wind und Streckenverlauf bleiben unberücksichtigt.
- Beim Berglauf wird die Wettkampf-Höhenmeterdichte mit einer Toleranz von
  25 % oder mindestens 5 Höhenmetern pro km verglichen. Technische Wege,
  Gefälleverteilung, Untergrund und Gehanteile werden damit nicht beschrieben.
- Geschwindigkeit wird aus der Gesamtzeit einschließlich erfasster Pausen
  berechnet, sofern vorhanden. Andernfalls bleibt nur die Bewegungszeit
  verfügbar. Radaufzeichnungen mit über 20 % zusätzlicher Pausenzeit werden
  verworfen. Schwimmpausen werden nicht aus der Rechnung herausgerechnet und
  dann als durchgehendes Wettkampftempo ausgegeben.
- Sehr hohe Durchschnittsgeschwindigkeiten werden verworfen: Schwimmen über
  10, Laufen über 30, Rad über 70 km/h. Das sind Plausibilitätsfilter.

Jede Disziplin liefert die tatsächlich verwendeten Aktivitäts-IDs, Daten,
Distanzen, Zeiten, RPE, Puls und Ausschlussgründe. Persönliche Kommentare
werden nicht in die Formel hineingedeutet.

## Wie die Zeitspanne entsteht

Schwimmen und Rad werden aus dem beobachteten Dauertempo linear auf die
Zieldistanz übertragen. Beim Lauf wird das Potenzmodell verwendet. Für
gewöhnliche Trainingseinheiten ist das ein **Trainingsszenario**, keine
gemessene Maximalleistung. Eine langsame Trainingsschätzung beweist nicht,
dass das Zeitziel unmöglich ist. Beckenschwimmen wird nicht stillschweigend
mit Freiwasser gleichgesetzt; die Grenze wird angezeigt.

Die Mitte ist der Median der hochgerechneten Zeiten. Bei mindestens vier
Werten werden Ausreißer außerhalb der Tukey-Grenzen (1,5 × IQR) verworfen.
Der angezeigte Bereich basiert auf den Quartilen; bei weniger als drei Werten
auf Minimum und Maximum. Beim Lauf kommen Sensitivitätsszenarien mit
`k = 1,06`, `1,10` und dem verwendeten Exponenten hinzu. Diese Auswahl misst
die Modellsensitivität, **keine statistische Konfidenz oder prognostische
Fehlerwahrscheinlichkeit**. Ein geringer Bereich aus ähnlichen Trainings
beweist keine geringe Unsicherheit am Renntag.

Die Triathlon-Gesamtzeit summiert die drei Disziplinen:

- Persönliche Koppel-/Einzellaufvergleiche können den zusätzlichen Zeitbedarf
  nach dem Rad beschreiben: mindestens drei unabhängige Paare aus 90 Tagen,
  Puls ±5 bpm, Dauer ±20 %, Höhenmeterdichte ±5 m/km. Koppelläufe beginnen
  innerhalb von 45 Minuten nach einer mindestens einstündigen Radeinheit.
  Verhältnisse außerhalb von 0,8–1,5 werden verworfen. Beobachtete schnellere
  Koppelläufe liefern keinen erfundenen negativen Ermüdungsbonus. Dieser
  Vergleich ist nicht kausal und nicht wettkampfdauerkalibriert.
- Ohne solche Paare werden **offen benannte Szenarien** mit 0–15 % zusätzlicher
  Laufzeit, Mitte 7,5 %, genutzt. Dies ist eine eigene Annahme, keine aus einer
  Studie übernommene oder individuell validierte Fehlerspanne. Koppelläufe
  werden nicht zusätzlich als frische Läufe verwendet; sonst würde der
  Effekt doppelt angerechnet.
- Wechselzeiten stammen aus der freiwilligen Gesamtwechselvorgabe. Ohne diese
  werden sichtbar 5–10 Minuten, Mitte 7,5 Minuten, angenommen. Einzelzielzeiten
  werden nicht benötigt oder als Nutzervorgabe erfunden.

Für die explizite Bezeichnung `70.3` werden fehlende Distanzen durch
1,9/90/21,1 km ergänzt und als **Annahme** sichtbar gemacht. Die eigene
Streckeneingabe hat Vorrang. Das Format entspricht beispielsweise dem
[offiziellen Jesolo-Athletenhandbuch 2026](https://www.ironman.com/sites/default/files/2026-04/AG%20ENG%202026%2070.3%20IM%20Venice-Jesolo%201.pdf).
Das bestätigt nicht automatisch die Streckenführung einer zukünftigen Ausgabe.
Aus einer Wunschzeit oder einem beliebigen Namen werden keine Distanzen geraten.

Eine nicht auswertbare Disziplin wird nicht durch eine Formel ohne Belege
ersetzt. Teilschätzungen und konkrete Gründe bleiben sichtbar; die Summe fehlt.
Ohne Zeitziel wird die Zeitspanne ohne Zielbewertung angezeigt.

## Was die neue Uhr bedeutet

In der Mitte der Uhr steht die geschätzte Zeit, an den Bogenenden die
Szenariozeiten. Der Zeiger zeigt die Lage der Wunschzeit. Eine Zahl von 0 bis
100 wird hier bewusst nicht als persönliche Zielchance angezeigt. Die interne
Zeigerposition wird weiterhin reproduzierbar berechnet:

`Punkte = begrenze(100 × (Zielzeit − schneller Rand) / (langsamer Rand − schneller Rand), 0, 100)`

0 liegt am schnellen Rand oder davor, 100 am langsamen Rand oder dahinter.
Bei einer Spanne ohne Breite ergibt sich 100, wenn die Zielzeit die gemeinsame
Zeit abdeckt, andernfalls 0. Das wird nicht als Sicherheit ausgegeben.
Die Farben sind ausschließlich visuelle Kategorien dieser **Zielposition**.
Sie messen weder Erfolgswahrscheinlichkeit noch Anstrengung oder Renngarantie.
Der Bereich selbst ist kein validierter individueller Vorhersagekorridor.

Die aktuelle Leistung wird nicht ohne Belege bis zum Wettkampftermin
fortgeschrieben. Planung und verbleibende Vorbereitungszeit bleiben Kontext.
Bei Aktivitätsausfällen wird keine frische Prognose aus Kalender oder CTL erzeugt.
Alte Vorbereitungsindex-Verläufe werden nicht als Zielprognose-Verlauf verwendet.

## Rolle der lokalen KI und Prüfung

`get_training_analysis(section="predictions")` liefert kompakt die berechneten Zeitspannen,
Zielposition, Auswahlbelege, Annahmen und Quellen. Für den LLM-Kontext werden
pro Disziplin höchstens fünf Einzelnachweise übertragen. Die lokale KI kann
sie erklären und über vorhandene Tools weitere Originaldaten einordnen.
Sie darf keine Zeiten, Gewichte, Prozentchancen oder Verbesserungen erfinden.
Der Dashboard-Knopf nutzt den bestehenden lokalen Chat und ändert keine
llama.cpp-Parameter. Die Zahlen entstehen unabhängig vom LLM.

Deterministische Tests verwenden synthetische Daten: Zieländerungen, veränderte
Leistungen, persönliche Exponenten, Bewegungs-/Gesamtzeit, Ausreißer,
Indoor-/Strecken-Ausschlüsse, Teilnachweise, Wechsel, Koppelvergleiche, Ausfälle,
Dashboard und KI-Tool-Ausgabe. Das ist eine Implementierungsprüfung. Eine
prospektive Validierung gegen tatsächliche spätere Wettkampfergebnisse ist
noch nicht erfolgt; eine persönliche Prognosegenauigkeit wird nicht behauptet.
