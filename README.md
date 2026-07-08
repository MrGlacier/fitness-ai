# Fitness AI

Ein persönlicher MCP-Server für Triathlon- und Ausdauertraining.

Das Projekt verbindet einen LLM (z. B. Qwen über llama.cpp) mit der
Intervals.icu API über das Model Context Protocol (MCP).

Aktuell unterstützt der Server unter anderem:

- Verbindung zu Intervals.icu testen
- Workouts abrufen
- Letztes Workout abrufen
- BMI berechnen

Weitere Funktionen wie FTP, Trainingszonen, Kalender und Analysen
werden nach und nach ergänzt.

---

## Voraussetzungen

- Python 3.12+
- uv
- Intervals.icu Account
- `.env` Datei mit den Zugangsdaten

---

## Installation

```bash
uv sync
```

---

## MCP Server starten

```bash
uv run python mcp_server.py
```

oder (je nach Projektstruktur)

```bash
uv run mcp_server.py
```

---

## Entwicklung

Abhängigkeiten installieren:

```bash
uv sync
```

Neue Abhängigkeit hinzufügen:

```bash
uv add <paketname>
```

---

## Projektstruktur

```
fitness-ai/
│
├── mcp_server.py          # Einstiegspunkt des MCP Servers
├── intervals_client.py    # Kommunikation mit Intervals.icu
├── models.py              # Pydantic Modelle
├── utils.py               # Hilfsfunktionen
├── config.py              # Konfiguration
├── logger.py              # Logging
└── README.md
```

---

## Aktuell implementierte MCP Tools

- `hello`
- `calculate_bmi`
- `test_intervals_connection`
- `get_workouts`
- `get_last_workout`

---

## Roadmap

- SportSettings abrufen
- FTP
- Herzfrequenzzonen
- Powerzonen
- Trainingskalender
- Trainingsempfehlungen
- AI Coach