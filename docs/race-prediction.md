# Wettkampfprognose `race-time-v3.1`

## Produktverhalten und Modelle

V3 ergänzt die unten unverändert dokumentierten wissenschaftlichen Grundlagen
von V2 um alltagstaugliche Ersatzmodelle. Die V2-Verfügbarkeitsregeln und die alte
Indexskala im Archiv gelten **nicht** mehr. Die Gesamtpipeline ist weiterhin
nicht prospektiv oder individuell wissenschaftlich validiert.

- Aktuelle Leistung, vorsichtige Renntag-Prognose und persönlicher Zielindex
  sind getrennte Ergebnisse. Zielzeiten gehen ausschließlich in den Index ein.
- Normale Trainingsleistungen und ihr Kontext tragen die Prognose eigenständig.
  Rennen und maximale Tests sind zusätzliche Kalibrierungsnachweise, keine
  Voraussetzung. Ein fehlendes Race-Flag ist kein Datenmangel und reduziert
  für sich weder die Aussagekraft noch den Zielindex. Wahrscheinliche Rennen aus Namen
  werden als `probable` gekennzeichnet, niemals als bestätigtes Race-Flag.
  Plan-/Tempo-/Vorbereitungsbezeichnungen werden nicht als Rennen behandelt.
- Lauf: Riegel bleibt erhalten. Eine aktuelle Schwellen-Einstellung wird als
  angenäherte Stundenleistung mit Exponent 1,07 übertragen. Bei zusätzlicher
  direkter Evidenz werden die Modelle verglichen und zeitgewichtet kombiniert
  (direkte Evidenz: `2^(-Alter/84)`, Schwellenmodell: Gewicht 0,5).
  Ohne Schwellen-Einstellung können strukturierte Laufintervalle ein Szenario
  liefern: mindestens 30 aktive Minuten in Abschnitten ab zehn Minuten,
  Sitzungs-RPE 5–8 oder Abschnittspuls bei 85–103 % des hinterlegten Schwellenpulses.
  Die Distanz-Zeit-Übertragung erhält 4 % Pausen-/Ausdaueraufschlag und eine
  modellbasierte Spanne von −12/+16 %. Das ist eine offengelegte Heuristik;
  kurze VO2-Wiederholungen oder Gesamtzeit einschließlich Pausen werden nicht
  extrapoliert. Vorbelastete Koppellauf-Pace erhält keinen zweiten Ermüdungsaufschlag.
  Ohne beide liefern längere Dauerläufe ein ausdrücklich grobes Szenario:
  Riegel mit höchstens 5 % Temporeserve bei RPE ≤4, Spanne mindestens ±20 %.
  Kurze HIT-/VO2-Intervalle werden weiterhin nicht auf lange Rennen extrapoliert.
- Schwimmen: aktive Serien statt Gesamtzeit mit Pausen. Bekannte Technik,
  Hilfsmittel, Pausen und Ein-/Ausschwimmen werden verworfen. Unbenannte
  Abschnitte unter 200 m sowie wahrscheinliche Randabschnitte gehen nicht ein;
  längere aktive Abschnitte sind vorsichtige, unsichere Ersatznachweise.
  Kurze Serien erhalten 4 % Ausdaueraufschlag. Falls Serien fehlen, kann eine
  datierte Schwimm-Schwelle mit 3 % Ausdaueraufschlag dienen. Keine erfundenen
  Stil- oder Hilfsmittelmessungen, keine pauschalen Neoprenboni.
  Auch bei vorhandenen Rennen/Tests werden aktuelle aktive Serien als weiteres
  Modell verglichen und gewichtet, statt normales Training wegen eines Rennens zu ignorieren.
- Rad: stationäre Leistungsbilanz und alte Outdoor-Kalibrierung bleiben erhalten.
  Auch Jahre alte flache Outdoor-Einheiten mit gemessener Leistung und damaliger
  Masse können den gemeinsamen Widerstand kalibrieren. Aktuelle Indoor-Leistung
  liefert Leistung, niemals Outdoor-Geschwindigkeit. Ohne lange Leistung dient
  FTP bedingt mit 78 % (bis etwa 3,5 h) bzw. 70 % (länger); diese Anteile sind
  **Heuristiken**, keine persönlich bestätigte nachhaltige Rennleistung.
  Die reguläre Spanne variiert einen Gesamtfaktor; die Kombination sämtlicher
  extremer Widerstands-/Windannahmen ist ein separates Sensitivitätsszenario.
- Triathlon: Vorbelastung und Wechsel werden weiterhin addiert. Die angezeigte
  Laufzeit enthält die Radvorbelastung. Die Gesamtspanne kombiniert Disziplin-
  abweichungen quadratisch statt alle Extremannahmen gleichzeitig zu stapeln;
  dies ist eine Szenarioheuristik, kein statistisches Prognoseintervall.

## Renntag und Ausdauer

Die Aussagekraft bewertet wiederholte aktuelle Beobachtungen und deren
Modellspanne: mindestens drei Einheiten, jüngste höchstens 42 Tage alt und
relative Spanne höchstens 40 % erlauben „mittel“, auch ohne Rennen oder Tests.
Rein grobe Dauerlauf-/historische Szenarien bleiben vorsichtiger eingeordnet.

Verglichen werden die letzten 28 Tage mit den davorliegenden 56 Tagen.
Mindestens drei submaximale Paare brauchen ähnlichen Puls (±5), RPE (±1),
Dauer (±25 %), Höhenmeterdichte (±5 m/km) und Indoor-/Outdoor-Kontext.
Der Median ihrer Effizienzentwicklung und wiederholte datierte Schwellen-/FTP-
Einstellungen werden als getrennte Indikatoren gleich gewichtet.
Fortschreibung je Disziplin: halbe beobachtete 28-Tage-Rate über höchstens
84 verbleibende Tage, auf ±5 % begrenzt. Rad-Leistungsentwicklung wird wegen
der nichtlinearen Physik nur zu einem Drittel auf Geschwindigkeit übertragen.
Ohne beobachteten Trend wird keine Verbesserung unterstellt. Eine Entlastungs-
woche, Planerfüllung oder CTL erzeugen allein keine Zeitgewinne/-verluste.

Ausdauer wird separat aus dem Median der drei längsten Nachweise in 120 Tagen
bewertet: Schwimmen relativ zu 80 % der Distanz, Lauf relativ zu 70 % und Rad
relativ zu 65 % der prognostizierten Dauer. Indoor-km gehen nicht ein. Das sind
transparente Produktheuristiken. Historische Finish-Nachweise können unterstützen;
fehlende aktuelle Beobachtungen werden als unbekannt, nicht als Unfähigkeit markiert.
Offiziell hinterlegte Gesamtlimits (`cutoff_seconds`) begrenzen die Finish-Einschätzung.

## Verbindliche Indexskala

| Index | Farbe | Bedeutung |
|---|---|---|
| 0–25 | Rot | Finish gefährdet |
| 26–49 | Orange | Finish möglich |
| 50–64 | Gelb | Zielzeit ambitioniert |
| 65–74 | Gelbgrün | Zielzeit in Reichweite |
| 75–89 | Grün | Zielzeit realistisch erreichbar |
| 90–99 | Grün | Zielzeit sehr gut erreichbar |
| 100 | Grün | Leistungsreserven vorhanden |

Zuerst begrenzt die schwächste **beobachtete** Disziplinausdauer den Index:
Abdeckung <0,35 erlaubt 0–25, <0,65 höchstens 26–49, <0,85 höchstens 50–74.
Eine unrealistische Wunschzeit allein führt nie in Rot. Unbekannte Ausdauer
begrenzt hohe Werte, wird aber nicht als gefährdetes Finish ausgegeben.

Für hinreichende Ausdauer werden die Anker der Reserve `Zielzeit/Renntagzeit−1`
abschnittsweise interpoliert: −30 % →35, −15 % →50, −6 % →65, 0 % →75,
+8 % →90, +15 % →100. Das ist **keine Wahrscheinlichkeit** und keine Umrechnung
von FTP/Herzfrequenz in RPE. 75 bedeutet erreichbar, aber anspruchsvoll;
90 bedeutet zunehmend Reserve, ungefähr angestrebtes subjektives Gesamt-RPE 6–7;
100 bedeutet deutliche Reserve, keine Garantie. Ab 90 muss außerdem das
konservative Szenario zur Zielzeit passen und Ausdauer ≥0,95 vorliegen.
Nur grob unterstützende oder rein historische Zeitmodelle erlauben höchstens 89.

## Lokale KI, Daten und Reproduzierbarkeit

`prediction_context.py` nutzt den bestehenden LLM-Client ohne Änderung von
llama.cpp-Parametern. Maximal 16 datierte Aktivitäten, aktuelle archivierte
Planinhalte und drei Wellness-Tage werden lokal interpretiert. Struktur und
Feldgrenzen werden per Pydantic validiert; zusätzlich begrenzt ein mitgesendetes
JSON-Schema die Generierung über die [llama.cpp-API](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md); jede übernommene Einordnung muss
Aktivitäts-ID und ein tatsächlich vorhandenes Originalzitat enthalten.
Die KI klassifiziert kontrollierte/ermüdete Einheiten, mögliche Rennen und
Trainingskontext; sie setzt weder Messwerte noch Zeitkorrekturen oder Indexwerte.
Zitierte Einordnungen dürfen Ersatzmodell-Beobachtungen mit 0,9–1,05 gewichten.
Der deterministisch belegte Entlastungsplan hat Vorrang bei der Phaseneinordnung.
Die validierte Antwort wird unter dem Hash **aller übergebenen Eingaben und der
Schemaversion** privat gespeichert; identische Eingaben erhalten dieselbe Analyse.
Bei Ausfall oder ungültiger Antwort bleibt die deterministische Rechnung verfügbar.

Alle verfügbaren Aktivitätsjahre werden geladen, die Sammlung für zehn Minuten
athletenspezifisch zwischengespeichert. Bis zu 16 jüngste Schwimmeinheiten werden
um echte, separat gespeicherte Abschnitte ergänzt (zehn Minuten Cache). Aktuelle Schwellen und
Ausdauer bleiben zeitlich begrenzt; historische Kalibrierung wird nicht pauschal
nach 180 Tagen abgeschnitten. Kalenderabgleich bleibt auf den aktuellen
Kalenderzeitraum begrenzt. API-Audits sind auf jüngste 120 plus tatsächlich
verwendete Nachweise begrenzt. Auslassungen werden gezählt.

Gewicht geht in die Radphysik ein. HRV, Ruhepuls, Schlafdauer/-qualität/-score,
Readiness, VO2max und Lastwerte dienen als verfügbare Kontextdaten. Vergleiche der
Wochenmediane mit dem vorherigen persönlichen Vergleich benötigen mindestens
drei bzw. sieben Beobachtungen. Sie sind keine medizinischen Aussagen und keine
unbegründeten Zeitkorrekturen. Alter/Größe, eFTP, segmentiertes GPX, Wetter und
offizielle Splits werden ohne explizite Quelle nicht erfunden oder vorausgesetzt.

Erfolgreiche Tagesprognosen einschließlich Version, Kontext und Datenherkunft
werden privat gespeichert. Wochenänderungen verlangen einen vergleichbaren
Stand von vor 7–10 Tagen mit gleicher Zielzeit und Version. Ohne solchen Snapshot
wird kein Vorwochenwert erfunden. Backtests schließen das Ergebnisrennen und
alle nach dem Stichtag liegenden Aktivitäten aus; erkannte Rennen bleiben als
`probable` markiert. Später bearbeitete historische Daten können ohne damalige
Snapshots keine strikt zeitgenaue Validierung liefern. Automatische Gesamt-
triathlon-Ergebniszuordnung und persönliche Ermüdungskausalität bleiben offen.

Die Tests verwenden ausschließlich synthetische Daten. Der reale Referenzlauf
und gerenderte Prüfseiten bleiben außerhalb versionierter Dateien. Umfangreiche
historische Kalibrierung ist keine nachgewiesene persönliche Prognosegenauigkeit.

---

# Archiv: Wettkampfprognose `race-time-v2`

## Ergebnis und Status

Die Berechnung ist deterministisch und unabhängig vom LLM. Sie verändert keine
Trainingspläne, Ziele, llama.cpp-Parameter oder API-Schreibpfade. Modellformeln
sind wissenschaftlich begründet; **die gesamte Anwendung ist weder individuell
noch prospektiv validiert**. Auswahlregeln, Unsicherheitsbreiten, FTP-Übertragung,
Zielindex und Triathlon-Kombination sind ausdrücklich Produktheuristiken.

Vier Aussagen bleiben getrennt:

1. **Heutige Leistung:** Teilschätzungen und gegebenenfalls Gesamtzeit, jeweils
   mit modellbasierter Szenariospanne und Aussagekraft.
2. **Fitnessentwicklung:** datierte FTP-/Schwellenpace-Einstellungen als
   Indikatoren, ergänzt um Rennleistungen mit Distanzkontext und submaximale
   Leistung/Puls- bzw. Distanz/Herzschlag-Indikatoren bei RPE ≤4. Dies belegt
   ohne kontrollierte Vergleichsbedingungen keine Fitnesszuwächse.
3. **Wettkampftag:** derzeit ausdrücklich nicht belastbar fortschreibbar. Aus
   CTL, Planphase, verbleibender Zeit oder Kontinuität entstehen keine
   garantierten Verbesserungen.
4. **Zielerreichungsindex:** nur bei wiederholten vergleichbaren Rennleistungen;
   sonst „Noch nicht belastbar bewertbar“. Keine Erfolgswahrscheinlichkeit.

## Bestandsaufnahme und behobene Probleme

`race-time-v1` übertrug beliebiges Dauertempo auf die Zielstrecke. Beim Schwimmen
wurden Distanz und Gesamtzeit einschließlich Pausen/Technik gemischt. Beim Lauf
wurden lockere Einheiten als potentielle Rennleistung verwendet. Virtuelle und
Indoor-Aktivitäten wurden komplett verworfen, obwohl ihre Leistung verwertbar
ist. Alte Rennen hatten pauschalen Vorrang vor neuem Training. Ein zusätzliches
56-Tage-Fenster relativ zum jüngsten gewählten Nachweis konnte dieses Problem
verstärken. Der alte Score war lediglich eine Zielposition in einer Zeitspanne.

V2 klassifiziert erst die Evidenz, rechnet danach und enthält keine Zielzeit in
den Leistungsformeln. Lockere Läufe verändern keine Maximalleistungsprognose.
Kurze Intervalle bleiben Indikatoren. Indoor-Leistung kann das Radmodell speisen;
virtuelles Tempo niemals. Fehlende Disziplinen verhindern die Gesamtzeit, ohne
vorliegende Teilergebnisse zu löschen. Die alte Funktion `goal_position` bleibt
als Kompatibilitätshilfe erhalten, wird aber nicht mehr für `score` verwendet.

## Dateninventar und Herkunft

Die Schnittstellen wurden gegen die [offizielle OpenAPI-Spezifikation](https://intervals.icu/api/v1/docs)
und echte, ausschließlich lesend abgerufene Antworten geprüft. Private Rohdaten
und Aktivitätskennungen sind keine Repository-Fixtures oder Dokumentationsdaten.

| Quelle | Übernommene Felder | Grenzen |
|---|---|---|
| Aktivitäten | `moving_time`, `elapsed_time`, `distance`, `race`, `trainer`, `icu_rpe`, Puls, Höhenmeter | Fehlen oder fehlerhafte Messungen sind kein Leistungsmangel |
| Datierte Leistung | `icu_average_watts`, `icu_weighted_avg_watts`, `icu_variability_index`, `icu_intensity`, `decoupling` | NP/IF sind keine konstant gefahrene mechanische Leistung |
| Datierte Einstellungen | `icu_ftp`, `icu_weight`, `threshold_pace`, `lthr` | FTP-Messmethode unbekannt; `threshold_pace` ist Geschwindigkeit in m/s |
| Aktivitätsdetail | `icu_intervals`: Label, Typ, Distanz, aktive/gesamte Zeit, Leistung, Puls | Stil/Hilfsmittel sind ohne eindeutige Metadaten unbekannt |
| Streams, bestehender Detailpfad | Zeit, Distanz, Leistung, Puls, Höhe, Moving | Künstliche Streamsplits belegen keinen Schwimmstil oder Intervallzweck |
| Kalender | explizite Aktivitätszuordnung, Sollintensität, Titel | Absicht ist keine tatsächlich erbrachte Intensität |
| Lokales Planarchiv | strukturierte Phasen und Einheiten über bestehenden Planvergleich | Kein Erraten von Abschnittszuordnungen oder Planänderungen |

Die vorhandene `compare_sessions`-Logik bevorzugt explizite Verknüpfungen;
mehrdeutige Zuordnungen bleiben offen. Der Prognosepfad übernimmt nur zuverlässig
zugeordnete Kalenderabsichten. Archivtexte werden nicht automatisch auf einzelne
Schwimmabschnitte übertragen. Eine validierte eFTP-Serie ist im untersuchten
Datenmaterial nicht vorhanden; sie wird nicht aus einem erfundenen Feld erzeugt.
Es existiert bisher kein GPX-basierter Wettkampfstreckenpfad im Prognosemodell.

## Verwendete Modelle

### Lauf: Distanz-Zeit-Modell

Quelle: [Riegel (1981), Athletic Records and Human Endurance](https://www.rrtc.net/Articles/ARHE.pdf).
Prüfung bei Freizeitläufern: [Vickers & Vertosick (2016), DOI 10.1186/s13102-016-0052-y](https://doi.org/10.1186/s13102-016-0052-y).

- Formel: `T2 = T1 * (D2/D1)^k`.
- Voraussetzungen: plausible, distanznahe maximale Dauerleistung, vergleichbare
  Strecke, keine Intervallpause als Leistungszeit. Rennen oder explizit benannter
  maximaler Test mit RPE ≥9; hohe RPE allein reicht nicht.
- Umsetzung: standardmäßig `k=1,07`; bei unterschiedlich langen Rennen Median
  paarweiser logarithmischer Steigungen im Bereich 1–1,3, Distanzverhältnis ≥1,4.
- Individuelle Kalibrierung: ausschließlich vor dem Auswertungszeitpunkt
  liegende Rennen. Paarweises Median-Fitting ist unsere robuste Heuristik.
- Einschränkungen: Fitnessänderungen zwischen Rennen, Wetter und Gelände sind
  nicht kontrolliert. Marathonübertragung kann zu optimistisch sein.
- Abweichung: nicht Weltrekorde, sondern persönliche Nachweise; Auswahl und
  Szenariobreiten sind keine im Original validierte Prognosepipeline.

### Rad: mechanische Leistungsbilanz

Quelle: [Martin et al. (1998), DOI 10.1123/jab.14.3.276](https://doi.org/10.1123/jab.14.3.276),
[Originalpublikation als PDF](https://www.edzo.info.hu/images/MartinJC.pdf).

- Formel: `eta*P = 0,5*rho*CdA*(v+w)*abs(v+w)*v + m*g*(Crr+s)*v`.
  `road_speed` löst die stationäre Gleichung durch Bisektion.
- Voraussetzungen: gemessene Durchschnittsleistung, Körpermasse und eine
  nachhaltige Zieldauer. Indoor-Distanz/Geschwindigkeit gehen nicht ein.
- Umsetzung: bedingte **flache** Streckenszenarien. Bekannte positive
  Gesamt-Höhenmeter blockieren dieses Szenario; ein Gesamtanstieg wird nicht in
  eine erfundene durchschnittliche Streckensteigung umgerechnet.
- Lange Nachweise: Dauer mindestens halb so lang wie `Distanz / 30 km/h`.
  Die 30 km/h sind allein eine offengelegte Auswahlheuristik. VI ≤1,15, sofern
  bekannt; bei Triathlon RPE ≤7, sofern bekannt. Das beweist keine nachhaltige
  Maximalleistung. Die jüngste 56-Tage-Kohorte dieser Nachweise wird verwendet.
- Aktuelle FTP-Einstellung skaliert datierte alte Leistung mit
  `P_alt * FTP_aktuell / FTP_alt`. Dies ist **keine validierte Physiologie** und
  kein universeller FTP-Prozentsatz. Kurze Indoor-Einheiten liefern höchstens
  einen datierten FTP-Indikator, keine lange Dauerleistungsbestätigung.
- Kalibrierung: flache Outdoor-Einheiten mit Leistung, bekannten Höhenmetern und
  höchstens 5 % Pausen können unter Windstille/Crr=0,004 ein effektives CdA
  liefern. Akzeptiert wird 0,15–0,65 m², danach Median. Das ist eine gemeinsame
  Widerstandsschätzung unter Annahmen, keine identifizierte Aerodynamikmessung.
- Fehlende Kalibrierung: CdA=0,35 ±0,10 m², Crr 0,003–0,006, Rad/Gepäck 10 kg,
  rho=1,225 kg/m³, eta=0,97, Gegenwind 0–2 m/s. Annahmen stehen im Ergebnis.
  Leistung variiert −15 bis +10 %; fehlende FTP und RPE erweitern die Grenzen
  jeweils um 5 Prozentpunkte. Diese Grenzen sind nicht statistisch kalibriert.
- Abweichung vom Original: keine Beschleunigung, Lagerreibung, Windrichtung,
  Kurven/Abfahrten oder segmentweise Strecke. Ein Szenario ist deshalb keine
  präzise Vorhersage der Wettkampfstrecke. Niedrige Aussagekraft bleibt sichtbar.

Aktuelle valide Leistungsszenarien können einen älteren Radrennvergleich
ablösen. Ein altes Rennen verdrängt aktuelle Indoor-Leistung nicht automatisch.

### Schwimmen: belegte aktive Dauerabschnitte

Die lineare Distanzübertragung `T2=T1*D2/D1` ist eine **Heuristik**, kein eigenes
validiertes physiologisches Modell. Nur Rennen oder bestätigte maximale Tests
können eine direkte Zeitschätzung liefern. Bei strukturierten Tests müssen
geeignete Abschnitte explizit Kraul/Freestyle benennen, aktive Zeit ausweisen
und mindestens die halbe Zieldistanz umfassen. Pausen, Technik, Beine,
Ein-/Ausschwimmen und erkannte Hilfsmittel werden ausgeschlossen. Mehrere
geeignete Abschnitte ergeben eine Sitzungsbeobachtung, nicht viele unabhängige
Leistungsnachweise. Ein Freestyle-Label ohne Hilfsmittelhinweis ist weiterhin
keine verifizierte Geräteerkennung; dies bleibt eine Metadatenannahme.

Fehlende aktive Zeit, Stil-/Hilfsmittelangaben oder maximale Intensität führen
zu keiner direkten Wettkampfpace aus dem Sitzungsgesamtmittel. Unbekannte
Beckenlänge, Wenden, Neopren und Freiwasserbedingungen erhalten keine erfundenen
Zeitboni. Serien mit kurzen Wiederholungen werden nicht als durchgeschwommene
Langdistanz behandelt. Eine automatische quantitative Pacestabilitätsdiagnostik
ist noch nicht implementiert.

### Triathlon und Durability

[Etxebarria et al. (2013), DOI 10.1123/ijspp.8.5.502](https://doi.org/10.1123/ijspp.8.5.502)
zeigt den Einfluss variabler Radbelastung auf einen anschließenden kurzen Lauf;
daraus folgt kein universeller 70.3-Halbmarathonaufschlag.
[Maunder et al. (2021), DOI 10.1007/s40279-021-01459-0](https://doi.org/10.1007/s40279-021-01459-0)
beschreibt Durability als zeitabhängige Veränderung physiologischer Kennwerte.

Die Umsetzung bleibt heuristisch: `Gesamt = Schwimmen + Rad + Lauf*(1+f) + Wechsel`.
Koppelläufe werden nicht zusätzlich als frische Läufe eingesetzt. Persönliche
Vergleiche brauchen mindestens drei unabhängige Koppel-/Einzellaufpaare,
Puls ±5 bpm, RPE ±1, Dauer ±20 %, Höhenmeterdichte ±5 m/km. Vorheriges Radfahren
muss ≥1 Stunde dauern, innerhalb 45 Minuten enden und Leistung/FTP/RPE ausweisen.
Zusätzlich werden Radvorbelastungen mit FTP-relativer Leistung ±0,10, RPE ±1,
Puls ±5 bpm und Dauer ±20 % verglichen. In der Gesamtprognose muss die
Radvorbelastungsdauer außerdem zur geschätzten Wettkampf-Raddauer passen.
Diese Matchingtoleranzen sind Heuristiken, keine physiologischen Äquivalenzbelege.
Ohne solche Paare: offen benanntes Sensitivitätsszenario `f=0/0,075/0,15`.
Dies ist kein kausaler persönlicher Ermüdungsfaktor. Wechsel: Nutzervorgabe oder
angenommen 5/7,5/10 Minuten. Kein weiterer Ermüdungsabschlag im Radmodell.

## Geprüfte, noch nicht für Zeiten eingesetzte Modelle

| Modell/Quelle | Formel und Voraussetzung | Entscheidung und Grenze |
|---|---|---|
| [Critical Power / Speed, Jones & Vanhatalo (2017), DOI 10.1007/s40279-017-0688-0](https://doi.org/10.1007/s40279-017-0688-0) | `P=CP+W'/t`, `D=CS*t+D'`; mehrere valide maximale Belastungen verschiedener Dauer | Keine CP-/CS-Kurve aus beliebigen submaximalen Trainingseinheiten fitten. Nicht ohne Dauerleistungsnachweis auf Stunden extrapolieren. Individuelle Kalibrierung erst mit geeigneten Tests; derzeit keine Umsetzung |
| [CSS/CV, Wakayoshi et al. (1992), DOI 10.2114/ahs1983.11.301](https://doi.org/10.2114/ahs1983.11.301) | `D=a+CV*t`; Steigung mehrerer maximaler Freistiltests unter vergleichbaren Bedingungen | Keine CSS aus unklassifizierten 200-/400-m-Trainingsintervallen. Original untersuchte mehrere maximale Distanzen; keine Umsetzung eines bloßen Zwei-Intervall-Pseudotests |
| Individuelle Leistungs-Dauer-Kurve | zeitgestempelte maximale Bestleistungen und passende Modellgüte nötig | NP, FTP und kurze HIT-Intervalle ersetzen diese Daten nicht. Noch keine Stream-Bestleistungs-/Durability-Kurve |
| FTP / Laktatschwelle / VO2max | Messprotokoll und individuelle Beziehung zur Wettkampfdauer erforderlich | Keine Gleichsetzung; [Functional Threshold Power Is Not Equivalent to Lactate Parameters in Trained Cyclists](https://pubmed.ncbi.nlm.nih.gov/31269000/) zeigt begrenzte individuelle Übereinstimmung. Keine Zeit aus VO2max erfunden |
| [Minetti et al. (2002)](https://pubmed.ncbi.nlm.nih.gov/12183501/) | Laufkosten abhängig von lokaler Steigung; echtes Profil benötigt | Gesamt-Höhenmeter reichen nicht für Energiekorrektur. Bestehender konservativer Trail-Streckenvergleich bleibt heuristisch |

## Auswahl, Gewichtung und Unsicherheit

- Jede Aktivität erhält Datum, ID, Name, Sport, Typ, Rolle, Indoor-Status,
  verfügbare Messwerte, Planabsicht, Qualitätsstufe und konkrete Auswahlbegründung.
- Rollen: direkt, indirekt, Ausdauer, Durability oder unterstützend. Unbekannte
  Intensität wird nicht durch erfundene MIT-/Schwellenklassifizierung ersetzt.
- Leistungsgewicht: `2^(-Alter_in_Tagen/42)`. 42 Tage Halbwertszeit sind eine
  Produktannahme. Nur direkte Nachweise speisen die gewichtete Medianzeit.
- Distanzvergleich: 0,5–2 der Zielstrecke; Laufrennen ab 0,25. Älter als ein Jahr
  bleibt historischer Kontext; die laufende Summary lädt bisher 180 Tage.
- Robuste Quartile mit Tukey-Ausreißerbehandlung bilden die Basisspanne.
  Die Mitte ist der nach Aktualität gewichtete Median, kein ausgewählter Bestwert.
- Zusätzliche relative Szenariobreite:
  `0,04 + 0,08/sqrt(n) + min(0,20, Alter/900) + min(0,20, relative_Streuung/2)`;
  fehlende RPE zusätzlich 0,02. Widersprüche >20 % werden genannt.
- Aussagekraft derzeit höchstens mittel (≥3 Rennen, jüngstes ≤42 Tage);
  sonst niedrig. Gleiche Trainingszeiten belegen keine hohe Modellgenauigkeit.
- Fehlende/alte Daten vergrößern Unsicherheit oder verhindern eine Aussage;
  sie setzen sportliche Leistungsfähigkeit nicht künstlich herab.

Diese Zahlen sind nachvollziehbare Startheuristiken, noch keine empirisch
kalibrierten Fehlermodelle. Insbesondere sind die Szenariospannen **keine
Konfidenz- oder statistischen Prognoseintervalle**.

## Zielindex: Definition der Skala

Voraussetzung je Disziplin: ≥3 direkte Rennen, jüngstes ≤42 Tage, ≥42 Tage
Verlauf, Distanzvariation höchstens 5 %. Bedingte Radszenarien reichen nicht.

- `Leistungsnähe = clip(1 - max(Gesamtlücke, optionale Einzieldisziplinlücken)/0,20)`.
- Trend: schlechteste Disziplinentwicklung pro 28 Tage, auf 0–1 skaliert mit
  `clip(0,5 + Veränderung/0,04)`; Zeitfaktor `min(1,Tage_bis_Rennen/90)`.
- Kontinuität: Anteil der acht zurückliegenden Wochen mit Trainingsaufzeichnung.
- Qualität: kleinerer Wert aus `min(Nachweise)/6` und `1-max(relative_Spannenbreite)`.
- `Index = 100 * Leistungsnähe * (0,70 + 0,15*Trend + 0,10*Kontinuität + 0,05*Qualität)`.

Alle Faktoren werden begrenzt. 0 bedeutet deutliche heutige Leistungslücke;
100 bedeutet starke Übereinstimmung der heutigen Leistung und Indikatoren mit
dem Ziel. Ein Index von 70 bedeutet **nicht 70 % Erfolgswahrscheinlichkeit**.
Kontinuität kann eine große Leistungslücke nicht kompensieren. Eine Änderung der
Wunschzeit ändert nur diese Zielbewertung, niemals die unabhängigen Rennzeiten.

## Backtesting und Testbericht

`fitness.race_validation.backtest` führt zeitliche Prüfungen 90/60/30/7 Tage vor
markierten Rennen aus. Vor jeder Modellberechnung wird nach dem Stichtag
gefiltert; das Ergebnisrennen selbst ist ausgeschlossen. Der optionale
`baseline`-Callable erhält dieselben Daten. MAE, Bias, Szenarioabdeckung und
gepaarte Alt-/Neu-MAE werden je Sport ausgegeben. Wiederholte Horizonte desselben
Rennens zählen ausdrücklich nicht als unabhängige Wettkämpfe. Ohne auswertbare
Rennen bleiben Kennzahlen `null`.

Backtests verwenden keine heutigen Sporteinstellungen. Dennoch beweist ein
Aktivitätsdatum nicht, wann spätere Änderungen an FTP/RPE/Metadaten erfolgt sind.
**Strenge As-of-Validierung benötigt unveränderte archivierte Snapshots**; die
retrospektive Auswertung bleibt bis dahin vorläufig. Triathlon-Gesamtergebnisse
und offizielle Split-Importe werden noch nicht automatisch validiert.

Die Implementierung wurde mit synthetischen Unit-/Integrationstests geprüft:
Zielunabhängigkeit, aktive Schwimmzeiten und lange Pausen, Hilfsmittel/Technik,
fehlende Abschnitte, Grundlagenläufe, maximale Tests, kurze Intervalle, aktuelle
Indoor-Leistung, FTP-Übertragung, fehlende FTP/RPE, Alterung, widersprüchliche
Nachweise, Datenfehler, Koppelvergleiche, Zukunftsfilter und Backtesting.
Bestehende Tests, die gewöhnliche lockere Trainings als Maximalleistung
voraussetzten, wurden an die ausdrücklich geänderte Anforderung angepasst.
Dashboard-Rendering und begrenzte LLM-Evidenz werden ebenfalls geprüft.
Die konkrete Testanzahl und der private Referenzvergleich stehen im Abschluss
an den Auftraggeber; echte Trainingsdaten werden hier nicht veröffentlicht.

## Architektur und verbleibende Arbeit

- `intervals/intervals_client.py`: API-Mapping datierter Werte und echter Runden.
- `fitness/analyst.py`: Datenbeschaffung, zuverlässige Planzuordnung, Orchestrierung.
- `fitness/performance_evidence.py`: Klassifizierung, Schwimmabschnitte,
  Einstellungsverlauf, kontextbezogene Leistungs-/Effizienzindikatoren und Zielindex.
- `fitness/cycling_prediction.py`: physikalische Bilanz und Annahmenszenarien.
- `fitness/race_prediction.py`: Disziplinmodelle, robuste Aggregation,
  Triathlon-Kombination und Unsicherheit.
- `fitness/race_validation.py`: zeitliche Evaluation mit optionalem Vergleichsmodell.
- Dashboard: aktuelle Leistung, Fitnessindikatoren, fehlende Renntagfortschreibung,
  Zielindex und aufklappbare Belege. Lokale KI erklärt ausschließlich Ergebnisse.

Offen bleiben validierte Schwellen-/CSS-/CP-Tests, verlässliche Schwimmstil- und
Hilfsmittelmetadaten, GPX-Segmente/Wind-/Positionsdaten, gemessene Dauerleistung
nach relevanter Radvorbelastung, vergleichbare historische Rennen und echte
As-of-Snapshots. Es gibt keine automatische Renntag-Fitnessfortschreibung,
keine kausal validierte Koppelkorrektur und keine kalibrierte Erfolgswahrscheinlichkeit.
Diese Begrenzungen sind Bestandteil des Ergebnisses, keine versteckten Defaults.
