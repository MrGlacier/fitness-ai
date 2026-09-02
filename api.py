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

mcp_client = McpClient()
llm_client = LlmClient()

fitness_agent = FitnessAgent(
    llm_client_instance=llm_client,
    mcp_client_instance=mcp_client,
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

    user_message = None

    for message in reversed(request.messages):
        if message.role == "user":
            user_message = message.content
            break

    if user_message is None:
        raise HTTPException(
            status_code=400,
            detail="Keine User-Nachricht gefunden.",
        )

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
        answer = await fitness_agent.ask(user_message)

    except Exception as error:
        # Für die Entwicklungsphase geben wir die eigentliche
        # Fehlermeldung sichtbar zurück.
        #
        # Später kann hier Logging und eine sauberere Fehlerbehandlung hin.
        raise HTTPException(
            status_code=500,
            detail=str(error),
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