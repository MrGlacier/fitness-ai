"""Dashboard-Routes — reiner HTTP-Client zur Fitness API."""

import httpx
from typing import Annotated

from fastapi import Form, Request, HTTPException
from fastapi.responses import HTMLResponse

from dashboard.app import app, FITNESS_API_URL, templates


# ------------------------------------------------------------------ #
# TSS-Färbung: zentrale, leicht anpassbare Schwellenwerte
# ------------------------------------------------------------------ #

#: Niedriger TSS — blaue Markierung
TSS_LOW_MAX = 40
#: Mittlerer TSS — orangefarbene Markierung
TSS_MEDIUM_MAX = 70
#: Hoher TSS — rote Markierung (alles darüber)


def _tss_color_class(tss: int | float | None) -> str:
    """Gibt CSS-Klasse für TSS-Färbung zurück."""
    if tss is None:
        return ""
    if tss <= TSS_LOW_MAX:
        return "tss-low"
    if tss <= TSS_MEDIUM_MAX:
        return "tss-medium"
    return "tss-high"


# Globaler httpx-Client — wird wiederverwendet
_api_client = httpx.Client(
    base_url=FITNESS_API_URL,
    timeout=30.0,
)

_CHAT_TIMEOUT = 120.0  # LLM-Antworten können länger dauern


# ------------------------------------------------------------------ #
# Formatierungs-Helfer für die reine Anzeige
# ------------------------------------------------------------------ #

def _format_duration(seconds: int) -> str:
    """Sekunden als H:MM:SS oder M:SS formatieren."""
    if not seconds or seconds <= 0:
        return "—"
    seconds = int(seconds)
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


# ------------------------------------------------------------------ #
# Hauptseite
# ------------------------------------------------------------------ #

@app.get("/", response_class=HTMLResponse)
def dashboard_index(request: Request):
    """Hauptseite des Dashboards."""
    summary = _safe_summary()

    training_status = summary.get("training_status")
    last_workouts = summary.get("last_workouts", [])[:5]
    week_stats = summary.get("week_stats", {})

    return _render_template(
        request,
        training_status=training_status,
        last_workouts=last_workouts,
        week_stats=week_stats,
    )


@app.get("/dashboard/training-today", response_class=HTMLResponse)
def dashboard_training_today(request: Request):
    raise HTTPException(410, "Trainingsempfehlungen sind deaktiviert.")


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
        analyst=_safe_analyst(),
    )
    return HTMLResponse(content=html)


# Custom Jinja2-Filter für die reine Anzeige
templates.env.filters["format_duration"] = _format_duration
templates.env.filters["format_duration_short"] = _format_duration_short
templates.env.filters["tss_color_class"] = _tss_color_class


def _safe_analyst() -> dict:
    try:
        response = _api_client.get("/analyst/summary")
        response.raise_for_status()
        return response.json()
    except Exception:
        return {"errors": ["Analyse-API nicht verfügbar"]}


@app.put("/dashboard/races")
def save_race(payload: dict):
    try:
        response = _api_client.put("/analyst/races", json=payload)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as exc:
        raise HTTPException(502, "Wettkampf konnte nicht gespeichert werden.") from exc


@app.put("/dashboard/assignment")
def save_assignment(payload: dict):
    try:
        response = _api_client.put("/analyst/assignment", json=payload)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as exc:
        raise HTTPException(502, "Planzuordnung konnte nicht gespeichert werden.") from exc
