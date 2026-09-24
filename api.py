"""
HTTP-API für die Fitness-AI.

Diese Datei ist bewusst nur ein Wrapper zwischen Open WebUI und unserer
eigentlichen Fitness-AI.

Open WebUI spricht eine OpenAI-kompatible API.
Unsere Fitness-AI arbeitet intern weiterhin mit FitnessAgent.ask(question).

Die Fachlogik bleibt also vollständig in:

    FitnessAgent
        -> LLM
        -> MCP
        -> FitnessAnalyzer
        -> Intervals.icu

Diese Datei übersetzt lediglich zwischen beiden Welten.
"""

import json
import time
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core.logger import logger
from fitness.fitness_agent import FitnessAgent
from llm.llm_client import LlmClient
from connectors.mcp_client import McpClient


# ---------------------------------------------------------------------------
# FastAPI-Anwendung
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Fitness AI API",
    description="OpenAI-kompatible API für die lokale Fitness-AI",
    version="0.1.0",
)


# ---------------------------------------------------------------------------
# Unsere bestehende Fitness-AI initialisieren
#
# Das ist praktisch dasselbe, was bisher in main.py passiert.
#
# Wichtig:
# Wir bauen hier KEINE neue Fitness-Logik.
# Die API benutzt einfach unseren bestehenden FitnessAgent.
# ---------------------------------------------------------------------------

# Dashboard: Direkter Zugriff auf Analyzer / Intervals — KEIN LLM
from intervals import intervals_client as _intervals_client
from fitness import fitness_analyzer as _fitness_analyzer

intervals_client_instance = _intervals_client.IntervalsClient()
_analyzer = _fitness_analyzer.FitnessAnalyzer(intervals_client_instance)

mcp_client = McpClient()
llm_client = LlmClient()

fitness_agent = FitnessAgent(
    llm_client_instance=llm_client,
    mcp_client_instance=mcp_client,
    analyzer=_analyzer,
)


# ---------------------------------------------------------------------------
# Request-Modelle
#
# Open WebUI schickt Nachrichten ungefähr in dieser Form:
#
# {
#     "model": "fitness-ai",
#     "messages": [
#         {
#             "role": "user",
#             "content": "Wie war mein letzter Lauf?"
#         }
#     ],
#     "stream": true
# }
#
# Später werden hier mehrere Nachrichten stehen:
#
# user      -> Frage
# assistant -> Antwort
# user      -> weitere Frage / Rückfrage
#
# Für Version 0.1 verwenden wir zunächst nur die LETZTE User-Nachricht.
#
# Conversation History bauen wir anschließend bewusst in den FitnessAgent ein.
# ---------------------------------------------------------------------------


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[ChatMessage]

    # Open WebUI verwendet standardmäßig Streaming.
    stream: bool = False


# ---------------------------------------------------------------------------
# Test-Endpunkt
#
# Damit können wir schnell prüfen, ob die API überhaupt erreichbar ist.
#
# Browser:
#
# http://localhost:8000/
# ---------------------------------------------------------------------------


@app.get("/")
async def root():
    return {
        "status": "ok",
        "service": "fitness-ai",
    }


# ---------------------------------------------------------------------------
# Dashboard-Zusammenfassung
#
# Kompakter Endpunkt fur das Dashboard.
#
# Verwendet direkt FitnessAnalyzer / IntervalsClient — KEIN LLM,
# KEIN FitnessAgent, KEIN MCP.
# ---------------------------------------------------------------------------

from datetime import date, timedelta


@app.get("/dashboard/summary")
def dashboard_summary():
    """Kompakte Zusammenfassung fur das Dashboard."""
    today = date.today()

    # --- Trainingsstatus ---
    training_status = None
    try:
        status = _analyzer.get_current_training_status(today)
        if status is not None:
            training_status = {
                "ctl": status.ctl,
                "atl": status.atl,
                "form": status.form,
                "form_status": status.form_status,
                "summary": status.summary,
                "resting_hr": status.resting_hr,
                "hrv": status.hrv,
                "readiness": status.readiness,
            }
    except Exception:
        logger.exception("[DASHBOARD] Fehler beim Laden des Trainingsstatus")

    # --- Letzte Workouts (30 Tage) ---
    last_workouts = []
    recent_workouts = []
    try:
        recent_workouts = _analyzer.intervals_client_instance.get_recent_workouts(30)
        for w in recent_workouts[:5]:
            last_workouts.append({
                "date": w.start_time.strftime("%d.%m.%Y") if w.start_time else "?",
                "name": w.name or "?",
                "sport": w.sport,
                "distance_km": round(w.distance_km, 2) if w.distance_km else None,
                "duration_sec": w.duration_sec,
                "tss": w.tss,
            })
    except Exception:
        logger.exception("[DASHBOARD] Fehler beim Laden der Workouts")

    # --- 7-Tage-Statistiken ---
    week_stats = {}
    try:
        week_start = today - timedelta(days=7)
        week_workouts = [
            workout
            for workout in recent_workouts
            if workout.start_time.date() >= week_start
        ]
        total_seconds = sum(w.duration_sec for w in week_workouts)
        total_tss = sum(w.tss or 0 for w in week_workouts)

        by_sport: dict[str, dict] = {}
        for w in week_workouts:
            sport = w.sport
            if sport not in by_sport:
                by_sport[sport] = {"count": 0, "duration_sec": 0, "tss": 0}
            by_sport[sport]["count"] += 1
            by_sport[sport]["duration_sec"] += w.duration_sec
            by_sport[sport]["tss"] += w.tss or 0

        def fmt_hours(sec: int) -> str:
            if sec is None:
                return "?"
            hours = sec // 3600
            minutes = (sec % 3600) // 60
            return f"{hours}h {minutes}m" if hours else f"{minutes}m"

        week_stats = {
            "total_sessions": len(week_workouts),
            "total_duration": fmt_hours(total_seconds),
            "total_duration_sec": total_seconds,
            "total_tss": round(total_tss),
            "by_sport": by_sport,
        }
    except Exception:
        logger.exception("[DASHBOARD] Fehler beim Berechnen der Wochenstatistiken")

    return {
        "training_status": training_status,
        "last_workouts": last_workouts,
        "week_stats": week_stats,
    }


# ---------------------------------------------------------------------------
# Training Today — strukturierte Empfehlung
#
# POST /dashboard/training-today
#
# Fragt den FitnessAgent um eine personalisierte Trainingsempfehlung
# für heute. Die Antwort ist strukturiertes JSON.
# ---------------------------------------------------------------------------


@app.post("/dashboard/training-today")
def dashboard_training_today():
    """Strukturierte Trainingsempfehlung für heute."""
    try:
        recommendation = fitness_agent.get_training_today_recommendation()
        return {
            "success": True,
            "data": recommendation.model_dump(mode="json"),
        }
    except RuntimeError as exc:
        logger.exception("[TRAINING-TODAY] LLM-Fehler")
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )
    except Exception:
        logger.exception("[TRAINING-TODAY] Unerwarteter Fehler")
        raise HTTPException(
            status_code=500,
            detail="Konnte keine Trainingsempfehlung erzeugen.",
        )


# ---------------------------------------------------------------------------
# OpenAI-kompatibler Models-Endpunkt
#
# Open WebUI fragt diesen Endpoint ab, um herauszufinden,
# welche Modelle unsere API anbietet.
#
# Für Open WebUI sieht unsere komplette Fitness-AI wie ein Modell aus.
# ---------------------------------------------------------------------------


@app.get("/v1/models")
async def models():
    return {
        "object": "list",
        "data": [
            {
                "id": "fitness-ai",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "local",
            }
        ],
    }


# ---------------------------------------------------------------------------
# OpenAI-kompatibler Chat-Endpunkt
#
# Das ist der eigentliche Einstiegspunkt für Open WebUI.
#
# Open WebUI sendet die Unterhaltung hier hin.
#
# AKTUELL:
#
# Wir suchen die letzte User-Nachricht und geben nur diese an:
#
#     fitness_agent.ask(...)
#
# weiter.
#
# SPÄTER:
#
# Statt nur einer einzelnen Frage werden wir die komplette Conversation
# an unseren FitnessAgent übergeben.
#
# Genau dort ermöglichen wir dann echte Gespräche und Rückfragen.
# ---------------------------------------------------------------------------


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):

    # -----------------------------------------------------------------------
    # Letzte User-Nachricht suchen
    #
    # Wir benutzen bewusst nicht einfach:
    #
    #     request.messages[-1]
    #
    # weil ein OpenAI-kompatibler Request verschiedene Rollen enthalten kann:
    #
    # system
    # user
    # assistant
    #
    # Uns interessiert aktuell nur die letzte User-Nachricht.
    # -----------------------------------------------------------------------

    question = None
    question_index = None
    history = []

    for index, message in enumerate(request.messages):

        # Die letzte User-Nachricht merken wir uns als aktuelle Frage.
        if message.role == "user":
            question = message.content
            question_index = index

        # Alle Nachrichten sammeln wir erstmal als History.
        history.append({
            "role": message.role,
            "content": message.content,
        })


    if question is None or question_index is None:
        raise HTTPException(
            status_code=400,
            detail="Keine User-Nachricht gefunden.",
        )


    # Nur die tatsächlich als aktuelle Frage ausgewählte User-Nachricht
    # entfernen. Nachfolgende System- oder Assistant-Nachrichten bleiben Teil
    # des Gesprächsverlaufs.
    history.pop(question_index)

    # -----------------------------------------------------------------------
    # Übergang zu unserer eigentlichen Fitness-AI
    #
    # Früher:
    #
    # Terminal
    #    ->
    # main.py
    #    ->
    # fitness_agent.ask(question)
    #
    #
    # Jetzt:
    #
    # Open WebUI
    #    ->
    # api.py
    #    ->
    # fitness_agent.ask(question)
    #
    #
    # Der FitnessAgent selbst muss aktuell noch nichts davon wissen,
    # dass die Anfrage aus einem Browser kommt.
    # -----------------------------------------------------------------------

    try:
        answer = await fitness_agent.ask(
            question=question,
            history=history,
        )

    except Exception as error:
        # Fehler logging + saubere 500-Antwort mit Message
        logger.exception("Chat-Verarbeitung fehlgeschlagen: %s", error)
        raise HTTPException(
            status_code=500,
            detail={"error": type(error).__name__, "message": str(error)},
        ) from error

    # -----------------------------------------------------------------------
    # STREAMING
    #
    # Open WebUI verwendet standardmäßig:
    #
    #     "stream": true
    #
    #
    # Unsere Fitness-AI erzeugt aktuell allerdings erst die komplette Antwort
    # und liefert sie anschließend zurück.
    #
    # Wir machen deshalb NOCH KEIN echtes Token-für-Token-Streaming.
    #
    # Stattdessen liefern wir die komplette Antwort in einem einzigen
    # gültigen SSE-Chunk.
    #
    # Open WebUI kann damit trotzdem korrekt umgehen.
    # -----------------------------------------------------------------------

    if request.stream:

        async def generate_stream():

            completion_id = f"chatcmpl-{uuid.uuid4().hex}"

            # ----------------------------------------------------------------
            # Erster und aktuell einziger Content-Chunk
            #
            # Später könnten hier viele kleine Chunks entstehen:
            #
            # "Dein"
            # " letzter"
            # " Lauf"
            # ...
            #
            # Aktuell kommt die komplette Antwort auf einmal.
            # ----------------------------------------------------------------

            chunk = {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": "fitness-ai",
                "choices": [
                    {
                        "index": 0,
                        "delta": {
                            "role": "assistant",
                            "content": answer,
                        },
                        "finish_reason": None,
                    }
                ],
            }

            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"

            # ----------------------------------------------------------------
            # Abschluss-Chunk
            #
            # Damit teilen wir dem Client mit:
            #
            # Die Antwort ist vollständig.
            # ----------------------------------------------------------------

            end_chunk = {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": "fitness-ai",
                "choices": [
                    {
                        "index": 0,
                        "delta": {},
                        "finish_reason": "stop",
                    }
                ],
            }

            yield f"data: {json.dumps(end_chunk)}\n\n"

            # OpenAI beendet Streaming-Antworten mit [DONE].
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream",
        )

    # -----------------------------------------------------------------------
    # NORMALE NICHT-STREAMING-ANTWORT
    #
    # Wird zum Beispiel verwendet, wenn wir unsere API direkt per curl testen:
    #
    #     "stream": false
    #
    #
    # Das Format orientiert sich an OpenAI Chat Completions.
    # -----------------------------------------------------------------------

    completion_id = f"chatcmpl-{uuid.uuid4().hex}"

    return {
        "id": completion_id,
        "object": "chat.completion",
        "created": int(time.time()),
        "model": "fitness-ai",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": answer,
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            # Aktuell nur Platzhalter.
            #
            # Unser LLM-Client liefert noch keine Token-Zählung,
            # die wir hier sinnvoll weiterreichen könnten.
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
    }
