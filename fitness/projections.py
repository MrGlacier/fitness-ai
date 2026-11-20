"""Deterministic load scenarios; race preparation is evaluated separately."""
from datetime import date, timedelta
from math import exp


def forecast_fitness(seed: dict | None, events: list[dict], end: date) -> dict:
    if not seed or seed.get("ctl") is None or seed.get("atl") is None:
        return {"points": [], "status": "unavailable", "reason": "Dated CTL/ATL seed missing"}
    start = date.fromisoformat(seed["date"])
    ctl, atl = seed["ctl"], seed["atl"]
    points = []
    unknown = False
    for offset in range(1, (end - start).days + 1):
        day = start + timedelta(days=offset)
        planned = [e for e in events if e["date"] == day.isoformat()]
        load = 0
        estimated = 0
        missing = 0
        for event in planned:
            value = event.get("tss")
            # icu_intensity is a percentage; no conversion from vague text/HR zones.
            intensity = event.get("intensity_percent")
            if value is None and event.get("duration_sec") is not None and intensity is not None:
                value = event["duration_sec"] / 3600 * (intensity / 100) ** 2 * 100
                estimated += 1
            if value is None:
                missing += 1
            else:
                load += value
        unknown |= missing > 0
        if not unknown:
            ctl += (load - ctl) * (1 - exp(-1 / 42))
            atl += (load - atl) * (1 - exp(-1 / 7))
        points.append(dict(date=day.isoformat(), ctl=round(ctl, 2) if not unknown else None,
                           atl=round(atl, 2) if not unknown else None,
                           tsb=round(ctl - atl, 2) if not unknown else None,
                           tss=round(load, 2) if not missing else None,
                           estimated_sessions=estimated, missing_tss=missing,
                           scheduled_sessions=len(planned), scenario=True))
    return {"status": "incomplete" if unknown else "scenario", "points": points,
            "final_state": dict(date=end.isoformat(), ctl=ctl if not unknown else None, atl=atl if not unknown else None),
            "model": "Exponential EWMA, CTL 42 days, ATL 7 days; TSB after daily load = CTL-ATL",
            "assumption": "Only calendar loads; empty days assumed zero. Missing load stops numeric projection. No guarantee of calendar completeness."}
