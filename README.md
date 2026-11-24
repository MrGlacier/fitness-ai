<div align="center">

# 🏊‍♂️ 🚴‍♂️ 🏃‍♂️ Fitness AI

**Dein lokaler AI-Assistent für Triathlon- und Ausdauertraining**

<img alt="Python 3.12+" src="https://img.shields.io/badge/Python-3.12%2B-3776AB?style=for-the-badge&amp;logo=python&amp;logoColor=white">
<img alt="uv Paketverwaltung" src="https://img.shields.io/badge/uv-Paketverwaltung-DE5FE9?style=for-the-badge">
<img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-API-009688?style=for-the-badge&amp;logo=fastapi&amp;logoColor=white">
<img alt="Docker und Open WebUI" src="https://img.shields.io/badge/Docker-Open_WebUI-2496ED?style=for-the-badge&amp;logo=docker&amp;logoColor=white">
<img alt="100 % lokale AI" src="https://img.shields.io/badge/AI-100%25_lokal-7C3AED?style=for-the-badge">

</div>

Eine lokale Fitness-AI für Triathlon- und Ausdauertraining. Sie verbindet ein
lokal über `llama.cpp` laufendes Sprachmodell mit Fitnessdaten aus der
Intervals.icu API. Ein Tool-Planer wählt abhängig von der Frage die passenden
MCP-Tools aus; der `FitnessAnalyzer` bereitet die Daten auf und das Sprachmodell
formuliert daraus die Antwort.

Das Projekt dient zugleich als Lernprojekt für lokale LLMs, Tool-Calling, MCP
und einfache AI-Agenten.

## ✅ Voraussetzungen

- Linux mit Bash und tmux
- Python 3.12 oder neuer
- [`uv`](https://docs.astral.sh/uv/)
- Intervals.icu Account und API-Zugang
- `llama.cpp` mit einem über `PATH` erreichbaren `llama-server`
- ein lokales GGUF-Modell (voreingestellt ist Qwen3 14B Q4_K_M)
- Docker; falls nötig, verwendet das Startskript automatisch `sudo docker`

## ⚙️ Installation und Konfiguration

Python-Abhängigkeiten installieren:

```bash
uv sync
```

Konfigurationsdatei anlegen:

```bash
cp .env.example .env
```

Anschließend in `.env` mindestens diese Werte eintragen:

```dotenv
INTERVALS_ICU_BASE_URL=https://intervals.icu/
INTERVALS_ICU_API=api/v1
INTERVALS_ICU_USER_NAME=API_KEY
INTERVALS_ICU_ATHLETE_ID=<athlete-id>
INTERVALS_ICU_API_KEY=<api-key>
LLM_BASE_URL=http://127.0.0.1:8080/
```

`INTERVALS_ICU_USER_NAME` bleibt für die API-Authentifizierung normalerweise
auf `API_KEY`. Die eigene Athlete-ID und der API-Key müssen ergänzt werden.
Die `.env` ist bereits von Git ausgeschlossen.

> [!IMPORTANT]
> Trage echte Zugangsdaten ausschließlich in `.env` ein. Die Datei
> `.env.example` bleibt eine Vorlage ohne geheime Werte.

Vor dem ersten Start müssen außerdem die Variablen `PROJECT_DIR` und `MODEL`
am Anfang von `fitness-ai.sh` zu den lokalen Pfaden passen:

```bash
PROJECT_DIR="/pfad/zum/fitness-ai-projekt"
MODEL="/pfad/zum/modell.gguf"
```

Falls das Skript nach dem Kopieren nicht ausführbar ist:

```bash
chmod +x fitness-ai.sh
```

## 🚀 Startskript verwenden

`fitness-ai.sh` verwaltet den gesamten lokalen Stack:

- `llama-server` auf `127.0.0.1:8080`
- die Fitness-AI API auf `0.0.0.0:8000`
- Open WebUI auf `localhost:3000`
- eine gemeinsame tmux-Session namens `fitness-ai`

Der normale Start erfolgt aus dem Projektverzeichnis:

```bash
./fitness-ai.sh start
```

Beim ersten Start wird der Open-WebUI-Container automatisch aus
`ghcr.io/open-webui/open-webui:main` erstellt. Das Docker-Volume `open-webui`
bewahrt dessen Daten auch nach einem Stopp des Containers auf.

### 🎛️ Befehle und Argumente

Das Skript wertet einen der folgenden Befehle als erstes Argument aus:

| Aktion | Befehl | Wirkung |
| :---: | --- | --- |
| 🟢 | `./fitness-ai.sh start` | Startet Open WebUI sowie die tmux-Session mit LLM und API. Bereits laufende Komponenten werden nicht erneut gestartet. |
| 🔴 | `./fitness-ai.sh stop` | Beendet die tmux-Session und stoppt den Open-WebUI-Container. |
| 🔄 | `./fitness-ai.sh restart` | Stoppt und startet den gesamten Stack neu. |
| 🔍 | `./fitness-ai.sh status` | Zeigt den Status von LLM/API und Open WebUI an. |
| 🖥️ | `./fitness-ai.sh console` | Öffnet die gemeinsame tmux-Konsole. Die Anwendung muss dafür bereits laufen. |

Ohne Argument oder mit einem unbekannten Argument zeigt das Skript die
Verwendung an und beendet sich mit Statuscode 1. Weitere Optionen oder
Positionsargumente unterstützt es derzeit nicht.

### 🖥️ tmux-Konsole bedienen

In der tmux-Session werden drei untereinander angeordnete Panes angezeigt:

1. `LLM` – Ausgabe von `llama-server`
2. `API` – Ausgabe von Uvicorn/FastAPI
3. `WEBUI` – Docker-Logs von Open WebUI

Die Konsole öffnen:

```bash
./fitness-ai.sh console
```

Zwischen den Panes nach oben oder unten wechseln:

```text
Ctrl+B  ↑
Ctrl+B  ↓
```

Alternativ wechselt folgende Tastenkombination zum jeweils nächsten Pane:

```text
Ctrl+B  o
```

Detach ohne die laufenden Dienste zu stoppen:

```text
Ctrl+B
D
```

Später lässt sich die Session wieder öffnen:

```bash
./fitness-ai.sh console
```

Zum tatsächlichen Beenden aller Dienste den Skriptbefehl verwenden:

```bash
./fitness-ai.sh stop
```

Nach dem Start sind die Dienste hier erreichbar:

- 💬 Open WebUI: <http://localhost:3000>
- ⚡ Fitness-AI API: <http://localhost:8000>
- 🧠 lokaler LLM-Server: <http://localhost:8080>

## 💬 Open WebUI einrichten

Beim ersten Aufruf unter <http://localhost:3000> muss ein lokales Admin-Konto
angelegt werden. Zugangsdaten können lokal in
`.openWebUi_Lokale_Admin_Konto_Daten` abgelegt werden; diese Datei ist über
`.gitignore` vom Repository ausgeschlossen.

In Open WebUI eine OpenAI-Verbindung mit folgenden Werten anlegen:

```text
Base URL: http://host.docker.internal:8000/v1
API-Key:  local-fitness-ai
```

Der API-Key ist derzeit nur ein Dummy-Wert, da die lokale Fitness-AI API ihn
nicht prüft. Danach sollte das Modell `fitness-ai` zur Auswahl stehen.

> [!WARNING]
> Die Installation ist ausschließlich für lokale Entwicklung gedacht. API und
> Open WebUI sollten nicht öffentlich erreichbar gemacht werden.

## 💻 Terminal-Client verwenden

Wenn der Stack läuft, kann die Fitness-AI alternativ direkt im Terminal
aufgerufen werden:

```bash
PYTHONPATH=. uv run python -m main "Wie ist mein aktueller Trainingszustand?"
```

Mehrere Argumente werden als mehrere eigenständige Fragen verarbeitet:

```bash
PYTHONPATH=. uv run python -m main \
  "Wie hoch ist meine aktuelle FTP?" \
  "Zeige mir mein letztes Lauftraining."
```

Weitere Beispielfragen:

```text
Bewerte meine letzte Trainingseinheit.
Welche Herzfrequenzzonen habe ich beim Laufen?
Wie gut habe ich meinen Trainingsplan diese Woche umgesetzt?
Wie viele Kilometer bin ich in den letzten 14 Tagen gelaufen?
```

Je nach Frage unterscheidet die Fitness-AI zwischen:

- `data`: sachliche Abfragen, Berechnungen und Vergleiche
- `coach`: nur noch als kompatibler Antworttyp für Analysen akzeptiert; keine Trainingsgenerierung

## 🧩 Architektur und Ablauf

```text
Browser → Open WebUI :3000 → OpenAI-kompatible API :8000 ┐
                                                          ├→ FitnessAgent
Terminal ───────────────────────────────→ main.py ─────────┘       ↓
                                                       Tool-Planer und MCP-Tools
                                                                  ↓
                                                FitnessAnalyzer / Intervals.icu
                                                                  ↓
                                             llama-server :8080 / lokales Qwen
```

Der Tool-Planer erhält die verfügbaren MCP-Tools zur Laufzeit und verwendet
Qwen im Modus `/no_think`. Die Tool-Auswahl ist daher nicht als feste Liste im
LLM-Prompt hinterlegt.

Aktuell stehen unter anderem folgende Funktionen bereit:

- Verbindung zu Intervals.icu testen
- Athlete-Stammdaten abrufen
- Workouts nach Zeitraum und Sportart abrufen
- letzte Trainingseinheit einschließlich Detailauswertung abrufen
- FTP sowie Trainings- und Herzfrequenzzonen abrufen
- aktuellen Trainings- und Erholungsstatus mit Fitness, Ermüdung, Form,
  Ruhepuls, HRV, Schlaf und subjektivem Befinden auswerten
- mehrere MCP-Tools für eine Frage kombinieren
- BMI berechnen

## 🔌 API direkt testen

Status und Modellliste abrufen:

```bash
curl http://localhost:8000/
curl http://localhost:8000/v1/models
```

Eine nicht streamende Chat-Anfrage senden:

```bash
curl http://localhost:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "fitness-ai",
    "messages": [
      {"role": "user", "content": "Wie hoch ist meine aktuelle FTP?"}
    ],
    "stream": false
  }'
```

Der Chat-Endpunkt unterstützt außerdem OpenAI-kompatible SSE-Antworten mit
`"stream": true`. Die vollständige Antwort wird momentan in einem einzelnen
Chunk übertragen; echtes Token-für-Token-Streaming ist noch nicht
implementiert.

Open WebUI übermittelt den Chatverlauf. Die letzte User-Nachricht wird als
aktuelle Frage und der übrige Verlauf als Kontext an den FitnessAgent übergeben.

## 🛠️ Logging und Entwicklung

Die Anwendung protokolliert Tool-Aufrufe, Tool-Ergebnisse, LLM-Antwortzeiten
und – sofern vom LLM-Server geliefert – die Token-Nutzung. Das Log live
verfolgen:

```bash
tail -f core/fitness-ai.log
```

Tests ausführen:

```bash
uv run python -m pytest -q
```

Neue Python-Abhängigkeit hinzufügen:

```bash
uv add <paketname>
```

## 🎯 Trainings- und Wettkampfanalyst

Fitness AI analysiert externe Trainingspläne und reale Intervals-Daten. Sie
erstellt keine Ersatzpläne und keine automatischen Trainingsempfehlungen.
Das Dashboard zeigt Wettkampfziele, aktuelle Planwoche, Soll/Ist, Fitnessverlauf
mit Kalenderszenario, Planfortschritt und einen nachvollziehbaren Vorbereitungsindex (0–100 Punkte).

- [Bedienungsanleitung mit Vergleichsbeispiel](docs/analyst.md)
- [Architektur, Modelle und Grenzen](docs/analyst-technical.md)
- [Trainingspläne ablegen, importieren und sichern](training_plans/README.md)

Nach dem Update API/MCP neu starten und Dashboard neu bauen:

```bash
docker compose up -d --build dashboard
```

Eigene Pläne mit `uv run python -m fitness.import_plan /pfad/plan.json`
importieren; Originale werden automatisch archiviert. Dan-Lorang-Originalexporte
werden direkt erkannt. Ein ganzer Ordner lässt sich mit
`uv run python -m fitness.import_plan /pfad/Trainingspläne --pattern 'TC*.json'`
importieren; `--dry-run` prüft vorher ohne Schreibzugriffe.
Lokale Wettkämpfe/Ziele und manuelle Planzuordnungen im Dashboard pflegen.
PDF/ältere XLS erfordern eine geprüfte strukturierte Übertragung; einfache
XLSX-, CSV-, JSON- und Markdown-Tabellen werden deterministisch eingelesen.
Eine Garmin-ähnliche Rundanzeige von 0 bis 100 zeigt die Wettkampfvorbereitung.
Die Punkte vergleichen das Training mit dem Plan und früheren Trainings. Sie
sagen nicht, ob die Leistung für eine Wunschzeit reicht. Der begrenzende
Vergleich wird direkt angezeigt. Einzelne offene Zuordnungen sperren die
Auswertung nicht.
Teilbewertungen, Datenabdeckung und Indexverlauf bleiben nachvollziehbar;
das LLM interpretiert ausschließlich die berechneten Werte.
