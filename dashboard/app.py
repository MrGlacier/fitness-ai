"""FastAPI-Instanz für das Dashboard."""

import os

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI(
    title="Fitness AI Dashboard",
    version="0.1.0",
)


@app.get("/health")
def health() -> dict[str, str]:
    """Leichter Healthcheck ohne Abhängigkeit von API oder LLM."""
    return {"status": "ok", "service": "fitness-ai-dashboard"}


# Statische Dateien (CSS, JS, Bilder) ausliefern
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")

# Sportart → Emoji Mapping
_SPORT_EMOJI: dict[str, str] = {
    "run": "🏃",
    "ride": "🚴",
    "swim": "🏊",
    "walk": "🚶",
}


def sport_emoji_filter(sport: str | None) -> str:
    """Gibt das Emoji für eine Sportart zurück."""
    if not sport:
        return "🏃"
    key = sport.lower().strip()
    # Exakte Mapping-Schlüssel
    emoji = _SPORT_EMOJI.get(key)
    if emoji:
        return emoji
    # Fallback: Substring-Erkennung für Varianten wie "VirtualRide"
    if "ride" in key:
        return "🚴"
    if "run" in key or "lauf" in key:
        return "🏃"
    if "swim" in key or "schwimm" in key:
        return "🏊"
    if "walk" in key or "geh" in key:
        return "🚶"
    return "🏃"


templates = Jinja2Templates(directory="dashboard/templates")
templates.env.filters["sport_emoji"] = sport_emoji_filter

# Fitness API URL — zur Laufzeit aus Environment
FITNESS_API_URL = os.environ.get(
    "FITNESS_API_URL", "http://host.docker.internal:8000"
)

# Routes importieren — muss am Ende stehen, um Zirkelimporte zu vermeiden
import dashboard.routes  # noqa: E402, F401
