"""Dashboard-Routes — reiner HTTP-Client zur Fitness API."""

import httpx
from math import cos, isfinite, radians, sin
from typing import Annotated

from fastapi import Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

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
        if response.status_code == 422:
            raise HTTPException(422, response.json().get("detail", "Bitte Eingaben prüfen."))
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as exc:
        raise HTTPException(502, "Wettkampf konnte nicht gespeichert werden.") from exc


@app.put("/dashboard/assignment")
def save_assignment(payload: dict):
    try:
        response = _api_client.put("/analyst/assignment", json=payload)
        if response.status_code == 422:
            raise HTTPException(422, response.json().get("detail", "Bitte Eingaben prüfen."))
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as exc:
        raise HTTPException(502, "Planzuordnung konnte nicht gespeichert werden.") from exc


def _session_status(value: str) -> str:
    return {"completed": "Absolviert", "moved": "Verschoben", "planned": "Geplant",
            "uncertain": "Zuordnung prüfen", "unmatched": "Nicht zugeordnet"}.get(value, value)


templates.env.filters["session_status"] = _session_status
templates.env.filters["weekday_name"] = lambda value: {1: "Mo", 2: "Di", 3: "Mi", 4: "Do", 5: "Fr", 6: "Sa", 7: "So"}.get(value, "—")


def _gauge_geometry(value: float | None) -> dict:
    """Ordnet den bereits berechneten Index auf einem 270-Grad-Instrument an."""
    if value is None or not isfinite(value):
        return {}
    score = max(0, min(100, value))
    angle = radians(135 + score * 2.7)
    color = "#fa7182" if score < 25 else "#ffa45c" if score < 50 else "#e5ca58" if score < 75 else "#68d98b"
    return dict(x=round(110 + 78 * cos(angle), 2), y=round(110 + 78 * sin(angle), 2), color=color)


templates.env.filters["gauge_geometry"] = _gauge_geometry


@app.post("/dashboard/assignment")
def save_assignment_form(
    plan_id: Annotated[str, Form()],
    start_date: Annotated[str, Form()],
    end_date: Annotated[str, Form()],
):
    """Speichert auch bei blockiertem JavaScript über das normale HTML-Formular."""
    save_assignment(dict(plan_id=plan_id, start_date=start_date, end_date=end_date))
    return RedirectResponse("/?assignment=saved#plan", status_code=303)


@app.get("/comparison", response_class=HTMLResponse)
def comparison_page(request: Request):
    return HTMLResponse(templates.get_template("comparison.html").render(request=request))


def _history_proxy(method: str, path: str, **kwargs):
    try:
        response = _api_client.request(method, f"/analyst/history/{path}", **kwargs)
        if response.status_code == 422:
            raise HTTPException(422, response.json().get("detail", "Eingaben prüfen."))
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as exc:
        raise HTTPException(502, "Historische Daten derzeit nicht erreichbar. Bitte später erneut versuchen.") from exc


@app.get("/dashboard/history/catalog")
def history_catalog_proxy():
    return _history_proxy("GET", "catalog")


@app.post("/dashboard/history/compare")
def history_compare_proxy(payload: dict):
    return _history_proxy("POST", "compare", json=payload, timeout=120)


@app.put("/dashboard/history/preparation")
def history_preparation_proxy(payload: dict):
    return _history_proxy("PUT", "preparation", json=payload)


@app.put("/dashboard/history/assignment")
def history_assignment_proxy(payload: dict):
    return _history_proxy("PUT", "assignment", json=payload)


@app.get("/dashboard/history/pair")
def history_pair_proxy(a_id: str, b_id: str):
    return _history_proxy("GET", "pair", params=dict(a_id=a_id, b_id=b_id), timeout=120)


@app.post("/dashboard/history/explain")
def history_explain(payload: dict):
    from pydantic import BaseModel, Field, ValidationError

    class PairRequest(BaseModel):
        a_id: str = Field(pattern=r"^[\w-]{1,100}$")
        b_id: str = Field(pattern=r"^[\w-]{1,100}$")

    try:
        pair = PairRequest.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(422, "Zwei gültige Aktivitäts-IDs sind erforderlich.") from exc
    return {"answer": _safe_chat(
        f"Vergleiche activity:{pair.a_id} (A) mit activity:{pair.b_id} (B). "
        "Lade get_historical_session_pair mit diesen IDs. Werte persönliche Originalkommentare semantisch aus, "
        "beachte Negationen und gleiche sie mit RPE und Messwerten ab. Zitiere relevante Aussagen mit Datum und Referenz. "
        "Benenne Widersprüche. Trenne messbaren Unterschied, plausible Interpretation und unbelegte Vermutung. "
        "Keine Entwicklung behaupten, wenn Vergleichbarkeit oder Belege fehlen.")}
