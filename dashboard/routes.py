"""Dashboard-Routes — reiner HTTP-Client zur Fitness API."""

import httpx
from typing import Annotated

from fastapi import Form, Request
from fastapi.responses import HTMLResponse

from dashboard.app import app, FITNESS_API_URL, templates

from core.logger import logger

# Globaler httpx-Client — wird wiederverwendet
_api_client = httpx.Client(
    base_url=FITNESS_API_URL,
    timeout=30.0,
)

_CHAT_TIMEOUT = 120.0  # LLM-Antworten können länger dauern
_TRAINING_TODAY_TIMEOUT = 180.0  # Training-Today braucht länger (mehr Daten + LLM)


# ------------------------------------------------------------------ #
# Formatierungs-Helfer für die reine Anzeige
# ------------------------------------------------------------------ #

def _format_duration(seconds: int) -> str:
    """Sekunden als H:MM:SS oder M:SS formatieren."""
    if not seconds or seconds <= 0:
        return "—"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def _format_duration_short(value) -> str:
    """Sekunden als '1h 35min' formatieren; Strings werden durchgereicht."""
    if isinstance(value, (int, float)):
        hours = int(value) // 3600
        minutes = (int(value) % 3600) // 60
        if hours > 0 and minutes > 0:
            return f"{hours}h {minutes}min"
        elif hours > 0:
            return f"{hours}h"
        return f"{minutes}min"
    return str(value) if value else "—"


# ------------------------------------------------------------------ #
# Hilfsfunktionen — alle mit try/except
# ------------------------------------------------------------------ #

def _safe_summary() -> dict:
    """Lädt Dashboard-Zusammenfassung von der Fitness API."""
    try:
        resp = _api_client.get("/dashboard/summary")
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return {
            "training_status": None,
            "last_workouts": [],
            "week_stats": {},
        }


def _safe_chat(question: str) -> str:
    """Sendet eine Frage an die Fitness API (Chat)."""
    try:
        resp = _api_client.post(
            "/v1/chat/completions",
            json={
                "model": "fitness-ai",
                "messages": [{"role": "user", "content": question}],
                "stream": False,
            },
            timeout=_CHAT_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except Exception as exc:
        return f"Konnte keine Antwort erhalten: {exc}"


def _safe_training_today() -> dict:
    """Lädt Training-Heute-Empfehlung von der Fitness API."""
    try:
        resp = _api_client.post(
            "/dashboard/training-today",
            json={},
            timeout=_TRAINING_TODAY_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("success"):
            return data.get("data", {})
        return {}
    except Exception as exc:
        logger.warning("[DASHBOARD] Fehler beim Laden von Training Today: %s", exc)
        return {"error": str(exc)}


# ------------------------------------------------------------------ #
# Hauptseite
# ------------------------------------------------------------------ #

@app.get("/", response_class=HTMLResponse)
def dashboard_index(request: Request):
    """Hauptseite des Dashboards."""
    summary = _safe_summary()
    training_today = _safe_training_today()

    training_status = summary.get("training_status")
    last_workouts = summary.get("last_workouts", [])[:5]
    week_stats = summary.get("week_stats", {})

    return _render_template(
        request,
        training_status=training_status,
        last_workouts=last_workouts,
        week_stats=week_stats,
        training_today=training_today,
    )


# ------------------------------------------------------------------ #
# Chat
# ------------------------------------------------------------------ #

@app.post("/dashboard/chat", response_class=HTMLResponse)
def dashboard_chat(
    request: Request,
    question: Annotated[str, Form()] = "",
):
    """Chat-Eingabe verarbeiten."""
    question = question.strip()

    summary = _safe_summary()
    training_status = summary.get("training_status")
    last_workouts = summary.get("last_workouts", [])[:5]
    week_stats = summary.get("week_stats", {})

    if not question:
        return _render_template(
            request,
            training_status=training_status,
            last_workouts=last_workouts,
            week_stats=week_stats,
            chat_answer="Bitte gib eine Frage ein.",
        )

    answer = _safe_chat(question)
    return _render_template(
        request,
        training_status=training_status,
        last_workouts=last_workouts,
        week_stats=week_stats,
        chat_answer=answer,
    )


# ------------------------------------------------------------------ #
# Template-Hilfe
# ------------------------------------------------------------------ #

def _render_template(
    request: Request,
    training_status: dict | None,
    last_workouts: list,
    week_stats: dict,
    chat_answer: str | None = None,
    training_today: dict | None = None,
) -> HTMLResponse:
    """Rendert das Dashboard-Template mit allen Daten."""
    template = templates.get_template("dashboard.html")
    html = template.render(
        request=request,
        training_status=training_status,
        last_workouts=last_workouts,
        week_stats=week_stats,
        chat_answer=chat_answer,
        training_today=training_today,
    )
    return HTMLResponse(content=html)


# Custom Jinja2-Filter für die reine Anzeige
templates.env.filters["format_duration"] = _format_duration
templates.env.filters["format_duration_short"] = _format_duration_short
