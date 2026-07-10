from datetime import date, datetime

from mcp.server.fastmcp import FastMCP
from models import Workout, Athlete, TrainingZones

import intervals_client
import fitness_analyzer
import llm_client

from utils import meters_to_km

from logger import logger

mcp = FastMCP("Fitness AI")
intervals_client_instance = intervals_client.IntervalsClient()
fitness_analyzer_instance = fitness_analyzer.FitnessAnalyzer(intervals_client_instance)
llm_client_instane = llm_client.LlmClient()

@mcp.tool()
def ask_llm() -> dict:
    """Testamfrage an die LLM um zu prüfen ob Sie verfügbar ist"""
    llm_client_instane.ask("Was ist FTP im Radsport?")
    llm_client_instane.ask("Erkläre FTP so, dass es ein Anfänger versteht.")
    llm_client_instane.ask("Wie hoch ist mein aktueller FTP?")
    llm_client_instane.ask("Wenn dir ein Tool zum Abrufen meines FTP zur Verfügung stünde, wie würdest du vorgehen?")
    return {
        "success": True
    }

@mcp.tool()
def get_last_workout(sport_type: str) -> Workout | None:
    """Liefert das letzte abgeschlossene Workout für eine Sportart, z. B. run, ride oder swim."""
    return intervals_client_instance.get_last_workout(sport_type)

@mcp.tool()
def get_workouts(
    from_date: date | None = None,
    to_date: date | None = None,
    sport_type: str | None = None
) -> list[Workout]:
    """Liefert alle abgeschlossenen Workouts innerhalb eines Datumsbereichs. Optional kann nach einer Sportart (z. B. run, ride oder swim) gefiltert werden."""
    from_date = from_date or date.today()
    to_date = to_date or date.today()
    return intervals_client_instance.get_workouts(from_date, to_date, sport_type)

@mcp.tool()
def get_athlete() -> Athlete:
    """Liefert die Stammdaten des konfigurierten Intervals.icu-Athleten."""
    return intervals_client_instance.get_athlete()

@mcp.tool()
def get_training_zones(sport_type: str | None = None) -> list[TrainingZones]:
    """Liefert Trainingszonen und Schwellenwerte des Athleten je Sportart."""
    return intervals_client_instance.get_training_zones(sport_type)

@mcp.tool()
def get_current_ftp(sport_type: str  | None = None) -> dict:
    """Liefert den aktuell hinterlegten FTP-Wert für eine Sportart, z. B. ride."""
    return fitness_analyzer_instance.get_current_ftp(sport_type)

@mcp.tool()
def hello(name: str) -> str:
    """Begrüßt eine Person."""
    return f"Hallo {name}! 👋"

@mcp.tool()
def calculate_bmi(height: int, weight: float) -> float:
    """Berechnet den Body-Mass-Index (BMI) anhand der Körpergröße in Zentimetern und des Gewichts in Kilogramm."""
    height_m = height / 100
    bmi = weight / (height_m ** 2)
    return round(bmi, 2)

@mcp.tool()
def test_intervals_connection() -> dict:
    """Prüft die Verbindung zur Intervals.icu API und gibt den konfigurierten Athleten zurück."""
    return intervals_client_instance.test_connection()