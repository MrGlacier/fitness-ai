# Privates Trainingsplanarchiv

`originals/` bewahrt unveränderte Originale; `structured/` enthält validierte,
durchsuchbare JSON-Pläne. `analyst.sqlite3` enthält lokale Wettkampfziele,
Planzuordnungen und tägliche Indexschnappschüsse. Diese Inhalte sind von Git
ausgeschlossen. Das gesamte Verzeichnis sichern; bei laufenden Schreibzugriffen
für SQLite die Backup-API verwenden oder API und MCP während der Kopie stoppen.
Mit `FITNESS_DATA_DIR` lässt sich ein anderes persistentes Verzeichnis wählen;
API und MCP müssen dasselbe Verzeichnis verwenden.

Import aus dem Projektverzeichnis:

```bash
uv run python -m fitness.import_plan /pfad/plan.json
uv run python -m fitness.import_plan /pfad/plan.csv --metadata /pfad/metadata.json
uv run python -m fitness.import_plan /pfad/plan.xlsx --metadata /pfad/metadata.json
```

## Dan-Lorang-Originaldateien direkt importieren

Der Importer erkennt TrainingCulture/Lorang-JSON automatisch: sowohl direkte
Pläne mit `weeks` als auch Exporte mit `userTrainingPlan`. Grundlage sind die
Feldzuordnung und Einheiten des vorhandenen `lorang-intervals-converter`;
Fitness AI benötigt dessen Installation oder Intervals-Zugang dafür nicht.
Die bereits für Intervals konvertierten `*_converted_for_intervals.json` sind
kein Eingabeformat; bitte immer die Originaldateien verwenden.

Aus dem Fitness-AI-Projektverzeichnis zunächst ohne Schreibzugriffe prüfen:

```bash
uv run python -m fitness.import_plan "../lorang-intervals-converter/Trainingspläne" --pattern 'TC*.json' --dry-run
```

Danach den gesamten Ordner importieren:

```bash
uv run python -m fitness.import_plan "../lorang-intervals-converter/Trainingspläne" --pattern 'TC*.json'
```

Eine einzelne Datei funktioniert genauso:

```bash
uv run python -m fitness.import_plan "/pfad/TC Example Build.json"
```

Vorheriges Kopieren ist unnötig. Der Import legt das unveränderte Original in
`originals/` und den lesbaren Archivplan in `structured/` ab. Die CLI liest die
Projekt-`.env`, insbesondere `FITNESS_DATA_DIR`; explizite Umgebungsvariablen
haben Vorrang. Ein Ordnerimport läuft nicht rekursiv, verarbeitet alle Treffer
und liefert bei Fehlern einen Exitcode ungleich 0. Er zeigt pro Datei die
Plan-ID, Wochen, Einheiten und Anzahl unklarer Zuordnungen.

Die Plan-ID ist inhaltsbasiert: identische Planinhalte werden wiedererkannt,
abweichende Versionen mit derselben ursprünglichen Lorang-ID bleiben getrennt.
Der Import liest Originalwochen statt `sampleWeeks`. Er übernimmt Tagesreihenfolge,
Namen, Beschreibungen, Dauer in Sekunden und Distanzen mit expliziter Einheit.
Wochen-/Tageshinweise, Ernährung mit Originaleinheiten, Kraftvorgaben und
Intervallstrukturen bleiben erhalten. Zusätzliche Quellstrukturen liegen pro
Einheit in `source_details`, Planabsicht in `description`. Persönliche
Autoren-/Kaufangaben werden nicht in die strukturierte Planfassung kopiert.

Eine explizite Wochenphase hat Vorrang. Fehlt sie, wird nur ein eindeutiger
Phasenbegriff Base/Build/Peak/Taper/Recovery aus dem Plantitel übernommen.
Fehlende Phasen, unbekannte Sportarten oder unbekannte Distanzeinheiten werden
als unsicher markiert. TSS, Schwimmdauer, Startdatum und prozentuale
Durchschnittsintensitäten werden nicht aus Trainingsschritten erfunden.

Nach dem ersten Codeupdate die Anwendung mit `./fitness-ai.sh restart` neu
starten. Spätere Planimporte werden bei der nächsten Analyse eingelesen;
ein Neustart pro Import ist nicht erforderlich. Im Dashboard bei Bedarf
Plan, Startdatum der Planwoche 1 und Gültigkeitsende manuell zuordnen, wenn
ähnliche Varianten keine eindeutige Erkennung zulassen. Der lokale Archivimport
verändert niemals den Intervals-Kalender. Einheiten müssen dort weiterhin mit
dem vorhandenen Converter eingeplant werden.

## Eigenes Archivformat

Minimales JSON (synthetisches Beispiel):

```json
{
  "id": "example-build",
  "name": "Example Build",
  "sport": "Triathlon",
  "aliases": ["Example"],
  "start_date": "2027-01-04",
  "sessions": [
    {
      "week": 1,
      "day": 1,
      "title": "Build W1 Easy Run",
      "sport": "Run",
      "phase": "Build",
      "duration_sec": 3600,
      "distance_km": null,
      "intensity": "locker",
      "description": "Beschreibung aus dem Originalplan",
      "tss": null,
      "notes": "Zusatzinformationen aus dem Original",
      "uncertainty": null
    }
  ]
}
```

Wochen beginnen montags; `day` ist 1–7. `start_date` bezeichnet den Start der
Planwoche 1. Fehlende Zahlen bleiben `null`, nicht 0. Unklare Zuordnungen im
Feld `uncertainty` kennzeichnen; solche Titel werden nicht als sichere
Erkennungsevidenz verwendet. Phasen und Sportarten stehen pro Einheit; mehrere
Einheiten am gleichen Tag sind erlaubt. Bei Phasen mit eigener Wochenzählung
je Phase einen eigenen Plan anlegen und über Namen/Aliasse unterscheiden.

CSV und Markdown verwenden dieselben Spalten wie `sessions`; die Metadatendatei
enthält `id`, `name`, `sport` und optional `aliases`, `start_date`. Markdown muss
eine explizite Tabelle mit Kopfzeile und Trennzeile enthalten. XLSX liest
`sheet1` mit denselben expliziten Spaltenüberschriften, skalaren Werten und ohne
verbundene Zellen/Formeln. Bei komplexen Excel-Plänen einen geprüften Export
verwenden. PDF und ältere XLS werden unverändert archiviert, der automatische
Import endet mit einem Hinweis auf eine geprüfte CSV-/JSON-Übertragung.
Es wird keine LLM-Interpretation unklarer Dokumente vorgenommen.

Das Original erhält einen inhaltsbasierten Dateinamen; identische Dateien
werden nicht dupliziert. Ein erneuter strukturierter Import ersetzt nur die
JSON-Datei mit derselben Plan-ID. Vorhandene Originale bleiben erhalten.
Strukturierte JSON-Dateien können unabhängig vom Original wieder importiert
oder direkt nach `structured/` zurückgesichert werden. Ein ungültiger Plan
wird nicht gespeichert; ein archiviertes Original bleibt zur Prüfung erhalten.

Manuelle Korrekturen sind im Dashboard über Plan und Gültigkeitszeitraum möglich.
Das Formular zeigt gespeicherte Angaben wieder an. Alternativ kann die aktuelle
Planwoche eingegeben werden, um den Planstart und das Enddatum vorzuschlagen.
Dort wird das Startdatum der Planwoche 1 (Montag) verwendet; der Zeitraum legt zugleich
die Gültigkeit dieser Zuordnung fest. Einzelne Sessions lassen sich im
strukturierten JSON oder per `PUT /analyst/plans` korrigieren.
