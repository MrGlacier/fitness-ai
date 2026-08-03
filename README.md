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

Die verfügbaren MCP-Tools werden dem Tool-Planer zur Laufzeit übergeben. Dadurch muss die Tool-Auswahl nicht fest im LLM-Prompt hinterlegt werden.

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

Der Fokus liegt auf einer einfachen, lesbaren und gut debuggbaren Architektur.
