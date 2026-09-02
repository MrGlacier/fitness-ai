# Fitness AI

Eine lokale Fitness-AI für Triathlon- und Ausdauertraining.

Das Projekt verbindet ein lokal laufendes Sprachmodell über `llama.cpp` mit Fitnessdaten aus der Intervals.icu API. Die Fitness-AI entscheidet selbstständig, welche MCP-Tools für eine Benutzerfrage benötigt werden, ruft diese auf und formuliert daraus eine verständliche Antwort.

Das Projekt dient gleichzeitig als Lernprojekt für LLMs, Tool-Calling, MCP und den Aufbau einfacher AI-Agenten.

---

## Voraussetzungen

- Python 3.12+
- `uv`
- Intervals.icu Account und API-Zugang
- `llama.cpp` mit `llama-server`
- lokales GGUF-Modell, aktuell Qwen3 14B Q4_K_M
- Docker für Open WebUI
- `.env` Datei mit den benötigten Zugangsdaten

---

## Installation

Abhängigkeiten installieren:

```bash
uv sync
```

---

## LLM starten

Aktuell wird Qwen3 14B über `llama-server` auf Port `8080` gestartet:

```bash
llama-server \
  -m /home/MrGlacier/.cache/llama.cpp/Qwen_Qwen3-14B-GGUF_Qwen3-14B-Q4_K_M.gguf \
  --host 127.0.0.1 \
  --port 8080 \
  -ngl 99 \
  -c 8192 \
  --flash-attn on \
  --jinja
```

Die Parameter bedeuten:

- `-ngl 99`: möglichst alle Modell-Layer auf die GPU auslagern
- `-c 8192`: Kontextfenster auf 8192 Tokens begrenzen
- `--flash-attn on`: Flash Attention aktivieren
- `--jinja`: das im Modell hinterlegte Chat-Template verwenden

Falls es zu CUDA-Speicherfehlern kommt, kann Flash Attention deaktiviert oder das Kontextfenster reduziert werden:

```bash
--flash-attn off
```

oder beispielsweise:

```bash
-c 4096
```

---

## Fitness-AI aufrufen

Die Fitness-AI wird aus dem Projektverzeichnis gestartet. Die Benutzerfrage wird als Argument übergeben:

```bash
PYTHONPATH=. uv run python -m main "Wie ist mein aktueller Trainingszustand?"
```

Weitere Beispiele:

```bash
PYTHONPATH=. uv run python -m main "Wie hoch ist meine aktuelle FTP?"
```

```bash
PYTHONPATH=. uv run python -m main "Zeige mir mein letztes Lauftraining."
```

```bash
PYTHONPATH=. uv run python -m main "Bewerte meine letzte Trainingseinheit."
```

```bash
PYTHONPATH=. uv run python -m main "Welche Herzfrequenzzonen habe ich beim Laufen?"
```

```bash
PYTHONPATH=. uv run python -m main "Welche Einheit sollte ich heute machen?"
```

Je nach Frage unterscheidet die Fitness-AI zwischen:

- `data`: sachliche Abfragen, Berechnungen und Vergleiche
- `coach`: Bewertungen, Einordnungen und Trainingsempfehlungen

---

## Ablauf einer Anfrage

```text
Benutzerfrage
    ↓
Tool-Planer wählt passende MCP-Tools
    ↓
MCP-Tools werden ausgeführt
    ↓
FitnessAnalyzer bereitet die Daten fachlich auf
    ↓
LLM formuliert die fertige Antwort
```

Der Tool-Planer verwendet Qwen im Modus `/no_think`. Dadurch werden einfache Tool-Entscheidungen schneller und mit deutlich weniger erzeugten Tokens beantwortet.

---

## Logging

Die Anwendung protokolliert unter anderem:

- ausgewählte MCP-Tools und Argumente
- Tool-Ergebnisse
- Antwortzeit des LLM
- Prompt-, Completion- und Gesamt-Tokens

Das Log kann während eines Tests live verfolgt werden:

```bash
tail -f core/fitness-ai.log
```

---

## Aktuelle Funktionen

Die Fitness-AI unterstützt unter anderem:

- Verbindung zu Intervals.icu testen
- Workouts und letzte Trainingseinheiten abrufen
- aktuelle FTP und Trainingszonen abrufen
- Trainingsbelastung und aktuellen Trainingszustand auswerten
- Ruhepuls, HRV und Schlafdaten in Antworten berücksichtigen
- Datenfragen von Trainerfragen unterscheiden
- mehrere MCP-Tools für eine Frage kombinieren
- BMI berechnen
- Nutzung über Open WebUI statt ausschließlich über das Terminal
- OpenAI-kompatible HTTP-API über FastAPI

Die verfügbaren MCP-Tools werden dem Tool-Planer zur Laufzeit übergeben. Dadurch muss die Tool-Auswahl nicht fest im LLM-Prompt hinterlegt werden.

---

## Open WebUI

Open WebUI wird als lokale Chat-Oberfläche für die Fitness AI verwendet.

Die Architektur sieht aktuell so aus:

```text
Browser
    ↓
Open WebUI :3000
    ↓
OpenAI-kompatible HTTP-API :8000
    ↓
FitnessAgent
    ↓
MCP / FitnessAnalyzer / Intervals.icu
    ↓
lokales Qwen-Modell über llama-server :8080
```

Open WebUI ersetzt dabei **nicht** den FitnessAgent oder dessen Tool-Logik. Es dient ausschließlich als Benutzeroberfläche.

### Open WebUI beim ersten Mal erstellen

Der Container wird einmalig mit folgendem Befehl angelegt:

```bash
docker run -d \
  -p 3000:8080 \
  --add-host=host.docker.internal:host-gateway \
  -v open-webui:/app/backend/data \
  --name open-webui \
  --restart always \
  ghcr.io/open-webui/open-webui:main
```

Falls Docker für den aktuellen Benutzer nicht freigegeben ist, den Befehl mit `sudo` ausführen:

```bash
sudo docker run -d \
  -p 3000:8080 \
  --add-host=host.docker.internal:host-gateway \
  -v open-webui:/app/backend/data \
  --name open-webui \
  --restart always \
  ghcr.io/open-webui/open-webui:main
```

Danach ist Open WebUI erreichbar unter:

```text
http://localhost:3000
```

### Wenn der Container bereits existiert

Der Container muss **nicht erneut mit `docker run` erstellt werden**.

Vorhandene Container anzeigen:

```bash
docker ps -a
```

Open WebUI starten:

```bash
docker start open-webui
```

Prüfen, ob der Container läuft:

```bash
docker ps
```

Open WebUI stoppen:

```bash
docker stop open-webui
```

Open WebUI neu starten:

```bash
docker restart open-webui
```

Logs anzeigen:

```bash
docker logs -f open-webui
```

Falls Docker nur mit Root-Rechten verwendet werden kann, bei diesen Befehlen entsprechend `sudo` davor setzen.

### Lokales Admin-Konto

Open WebUI benötigt beim ersten Start einen lokalen Admin-Account.

Die Zugangsdaten für das lokale Admin-Konto befinden sich in:

```text
.openWebUi_Lokale_Admin_Konto_Daten
```

**Wichtig:** Die Datei enthält lokale Zugangsdaten und darf nicht in das Git-Repository eingecheckt werden.

Sie muss deshalb in `.gitignore` eingetragen sein:

```gitignore
.openWebUi_Lokale_Admin_Konto_Daten
```

Die aktuelle Open-WebUI-Installation ist ausschließlich für die lokale Entwicklung vorgesehen und darf nicht öffentlich erreichbar gemacht werden.

### Fitness-AI API starten

Open WebUI kommuniziert nicht direkt mit dem `FitnessAgent`, sondern über die OpenAI-kompatible API in `api.py`.

Die benötigten Python-Abhängigkeiten sind:

```bash
uv add fastapi uvicorn
```

Die API wird aus dem Projektverzeichnis gestartet:

```bash
PYTHONPATH=. uv run uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```

Die API kann anschließend getestet werden:

```bash
curl http://localhost:8000/
```

Modelle anzeigen:

```bash
curl http://localhost:8000/v1/models
```

Die Antwort sollte das Modell `fitness-ai` enthalten.

### Open WebUI mit der Fitness-AI verbinden

In Open WebUI unter den OpenAI-Verbindungen folgende Base URL verwenden:

```text
http://host.docker.internal:8000/v1
```

Falls Open WebUI einen API-Key verlangt, kann für die lokale Entwicklung ein beliebiger Dummy-Wert verwendet werden, zum Beispiel:

```text
local-fitness-ai
```

Die Fitness-AI API prüft aktuell keinen API-Key.

Anschließend sollte in Open WebUI das Modell

```text
fitness-ai
```

zur Auswahl stehen.

### Streaming

Open WebUI verwendet standardmäßig Streaming für Chat-Antworten.

Die API unterstützt deshalb den OpenAI-kompatiblen Streaming-Endpunkt. Aktuell wird die fertige Antwort des `FitnessAgent` in einem einzelnen SSE-Chunk übertragen.

Echtes Token-für-Token-Streaming ist aktuell noch nicht implementiert.

### Aktueller Gesprächsstand

Open WebUI sendet bereits den vollständigen bisherigen Chatverlauf an die Fitness-AI API.

Aktuell wird in `api.py` jedoch nur die jeweils letzte Nachricht des Benutzers an

```python
FitnessAgent.ask(question)
```

weitergegeben.

Der nächste Entwicklungsschritt ist daher:

```text
Conversation History
    ↓
FitnessAgent
    ↓
Antwort oder echte Rückfrage
```

Damit soll die Fitness-AI künftig echte Mehrturn-Gespräche führen und selbst Rückfragen stellen können.

---

## Entwicklung

Neue Abhängigkeit hinzufügen:

```bash
uv add <paketname>
```

Projekt mit Logausgabe testen:

```bash
PYTHONPATH=. uv run python -m main "Wie ist mein aktueller Trainingszustand?"
```

---

## Ziel des Projekts

Die Fitness-AI soll schrittweise lernen:

- natürliche Benutzerfragen zu verstehen
- passende Tools und Argumente auszuwählen
- mehrere Datenquellen zu kombinieren
- Trainingsdaten fachlich nachvollziehbar aufzubereiten
- sachliche Datenantworten von Coach-Antworten zu unterscheiden
- persönliche Trainingsempfehlungen vorsichtig und begründet zu formulieren
- Gesprächskontext über mehrere Nachrichten hinweg zu verstehen
- bei fehlenden Informationen selbstständig Rückfragen zu stellen
- später Trainingsplanung und Plan-vs-Ist-Auswertung zu unterstützen

Der Fokus liegt auf einer einfachen, lesbaren und gut debuggbaren Architektur.
