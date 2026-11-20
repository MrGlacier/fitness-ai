from datetime import date

from mcp.server.fastmcp import FastMCP
from fitness.models import Workout, Athlete, TrainingZones, TrainingStatus
from intervals import intervals_client
from fitness import fitness_analyzer

mcp = FastMCP("Fitness AI")
intervals_client_instance = intervals_client.IntervalsClient()
fitness_analyzer_instance = fitness_analyzer.FitnessAnalyzer(intervals_client_instance)


@mcp.tool()
def get_last_workout(sport_type: str | None = None) -> Workout | None:
    """Liefert das letzte abgeschlossene Workout, optional gefiltert nach einer Sportart wie run, ride oder swim."""
    return fitness_analyzer_instance.get_last_workout(sport_type)

@mcp.tool()
def get_workouts(
    from_date: date | None = None,
    to_date: date | None = None,
    sport_type: str | None = None
) -> list[Workout]:
    """Liefert Trainings zwischen zwei konkreten Datumswerten. Verwende dieses Tool nur, wenn Start- und Enddatum als echte Datumswerte bekannt sind."""
    from_date = from_date or date.today()
    to_date = to_date or date.today()
    return intervals_client_instance.get_workouts(from_date, to_date, sport_type)

@mcp.tool()
def get_recent_workouts(days: int, sport_type: str | None = None) -> list[Workout]:
    """Liefert Trainings aus einem relativen Zeitraum, zum Beispiel aus den letzten 7, 14 oder 30 Tagen. Verwende dieses Tool bei Formulierungen wie „letzte Woche“, „letzte 30 Tage“ oder „im letzten Monat“."""
    return intervals_client_instance.get_recent_workouts(days, sport_type)

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
def get_current_training_status(for_date: date | None = None) -> TrainingStatus | None:
    """Liefert den aktuellen Trainings- und Erholungsstatus des Athleten mit Fitness, Ermüdung, Form, Ruhepuls, HRV, Schlaf und subjektivem Befinden."""
    for_date = for_date or date.today()
    return fitness_analyzer_instance.get_current_training_status(for_date)

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
def get_upcoming_events(days_ahead: int = 30) -> list[dict]:
    """Liefert geplante Wettkämpfe des Athleten für die nächsten N Tage als Trainingskontext."""
    return intervals_client_instance.get_upcoming_events(days_ahead)

@mcp.tool()
def test_intervals_connection() -> dict:
    """Prüft die Verbindung zur Intervals.icu API und gibt den konfigurierten Athleten zurück."""
    return intervals_client_instance.test_connection()

@mcp.tool()
def get_activity_detail(activity_id: str) -> dict:
    """Liefert eine einzelne Aktivität mit Stream-Statistiken (HR, Leistung, Pace etc.) und Splits. activity_id ist die ID der Aktivität in Intervals.icu."""
    return fitness_analyzer_instance.get_activity_detail(activity_id)

@mcp.tool()
def search_activities_by_name(
    search_term: str,
    sport_type: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """Sucht Aktivitäten nach einem Suchbegriff im Namen (case-insensitive Teilsuche). Optional nach Sportart filtern. Liefert maximal 50 Treffer."""
    return fitness_analyzer_instance.search_activities_by_name(search_term, sport_type, limit)

from fitness.analyst import TrainingAnalyst


@mcp.tool()
def get_training_analysis(section: str = "overview") -> dict:
    """Analyst data: overview, week, plan, fitness, comparison or races. Deterministic fitness scenarios and preparation index (not goal probability); no race-time predictions or training generation."""
    data = TrainingAnalyst(intervals_client_instance).summary()
    keys = {
        "overview": ["date", "errors", "next_race", "days_to_race", "plan", "fitness_trend"],
        "week": ["date", "errors", "week", "weekly_comparison"],
        "plan": ["plan", "available_plans"],
        "fitness": ["fitness_history", "fitness_forecast", "fitness_trend", "errors"],
        "comparison": ["comparison", "weekly_comparison", "errors"],
        "races": ["races", "race_preparation", "errors"],
    }
    if section not in keys:
        return {"error": "Unknown section", "sections": list(keys)}
    result = {k: data[k] for k in keys[section]}
    if section == "fitness":
        # Dashboard keeps daily points; model receives weekly samples plus endpoints.
        def weekly(points):
            return [p for i, p in enumerate(points) if i % 7 == 0 or i == len(points) - 1]
        result["fitness_history"] = weekly(data["fitness_history"])
        result["fitness_forecast"] = dict(data["fitness_forecast"],
            points=weekly(data["fitness_forecast"].get("points", [])), sampling="weekly, including last point")
    if section == "comparison":
        rows = data["comparison"]["sessions"]
        result["comparison"] = dict(data["comparison"], sessions=rows[-40:], omitted_sessions=max(0, len(rows) - 40))
    if section == "races":
        result["race_preparation"] = {key: dict(value, history=value["history"][-12:])
                                      for key, value in data["race_preparation"].items()}
    return result


@mcp.tool()
def search_training_plan(query: str, plan_id: str | None = None, week: int | None = None) -> list[dict]:
    """Search archived plan sessions, optionally by plan ID and week; at most 30 results."""
    from fitness.archive import AnalystStore
    results = []
    for plan in AnalystStore().plans():
        if plan_id and plan.id != plan_id:
            continue
        for session in plan.sessions:
            if week is not None and session.week != week:
                continue
            row = session.model_dump(mode="json")
            if query.casefold() in str(row).casefold():
                results.append(dict(plan_id=plan.id, **row))
    return results[:30]

if __name__ == "__main__":
    mcp.run(transport="stdio")
