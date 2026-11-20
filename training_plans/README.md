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
Dort wird das Startdatum der Planwoche 1 verwendet; der Zeitraum legt zugleich
die Gültigkeit dieser Zuordnung fest. Einzelne Sessions lassen sich im
strukturierten JSON oder per `PUT /analyst/plans` korrigieren.
