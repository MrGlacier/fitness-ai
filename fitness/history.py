"""Evidence-preserving historical analysis, independent of transport and LLM."""
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import re
from statistics import mean
from typing import Callable

import httpx

from fitness.archive import AnalystStore
from fitness.history_models import HistoricalAssignment, HistoricalPreparation, HistoryComparison, HistoryPeriod
from fitness.plan_analysis import sport_family
from intervals.intervals_client import IntervalsClient

PHASE = re.compile(r"\b(base|build|peak|taper|recovery|foundation)\b\s*(?:woche|week|w)?\s*(\d{1,2})?", re.I)
LIMITATIONS = [
    "Mehr Umfang oder TSS belegt keine bessere Leistungsfähigkeit. TSS-Definitionen können abweichen.",
    "Aktivitäts-FTP, Gewicht und Schwellen stammen aus dem jeweiligen gespeicherten Datensatz; spätere Änderungen bei Intervals sind nicht rekonstruierbar.",
    "Keine Neubewertung mit aktuellen Zonen. LIT/HIT ist aus Gesamtintensität nicht zuverlässig ableitbar und bleibt nicht verfügbar.",
    "Strecke, Wetter, Sensoren und Pausen können abweichen. Pace und Herzfrequenz sind Beobachtungen, kein Nachweis der Laufökonomie.",
]


def delta(a: float | None, b: float | None) -> dict:
    return dict(absolute=round(b-a, 3) if a is not None and b is not None else None,
                percent=round(100*(b-a)/a, 1) if a not in (None, 0) and b is not None else None)


def phase_hint(row: dict) -> dict:
    match = PHASE.search(row["name"])
    if not match:
        return dict(phase=None, week=None, confidence="unavailable", reason="Kein eindeutiger Phasenhinweis im Originaltitel.")
    week = int(match[2]) if match[2] and 1 <= int(match[2]) <= 80 else None
    day = date.fromisoformat(row["date"])
    anchor = day-timedelta(days=day.weekday(), weeks=(week or 1)-1)
    return dict(phase=match[1].title(), week=week, anchor=anchor.isoformat(), confidence="candidate",
                reason="Titelhinweis und Montag der angegebenen Woche; keine bestätigte Vorbereitung.")


def aggregate(rows: list[dict], wellness: list[dict], start: date, end: date, available: bool) -> dict:
    metrics = {}

    def record(key, values, unit, total=False, expected=None):
        known = [v for v in values if isinstance(v, (int, float))]
        count = len(values) if expected is None else expected
        # Totals with missing observations are deliberately not published as complete totals.
        value = (sum(known) if total else mean(known)) if known and (not total or len(known) == count) else None
        metrics[key] = dict(value=round(value, 3) if value is not None and available else None,
                            unit=unit, known=len(known), expected=count,
                            status="unavailable" if not available or not known else "partial" if len(known) < count else "available")

    metrics["sessions"] = dict(value=len(rows) if available else None, unit="Einheiten", status="available" if available else "unavailable")
    for key, unit in [("duration_sec", "s"), ("distance_m", "m"), ("tss", "TSS")]:
        record(key, [r.get(key) for r in rows], unit, total=True)
        if not rows and available:
            metrics[key].update(value=0, status="available")
    metric_sports = {"avg_watts": "Ride", "np_watts": "Ride", "ftp": "Ride",
                     "lthr": "Run", "threshold_speed_mps": "Run"}
    for key, unit in [("avg_watts", "W"), ("np_watts", "W"), ("avg_hr", "bpm"), ("ftp", "W"),
                      ("rpe", "RPE"), ("lthr", "bpm"), ("threshold_speed_mps", "m/s")]:
        eligible = [r for r in rows if key not in metric_sports or sport_family(r["sport"]) == metric_sports[key]]
        record(key, [r.get(key) for r in eligible], unit)
    record("w_per_kg", [r["ftp"]/r["weight"] if r.get("ftp") and r.get("weight") else None for r in rows if sport_family(r["sport"]) == "Ride"], "W/kg")
    for key, unit in [("ctl", "CTL"), ("atl", "ATL"), ("tsb", "TSB"), ("hrv", "ms"),
                      ("resting_hr", "bpm"), ("weight", "kg"), ("vo2max", "ml/kg/min")]:
        record(key, [r.get(key) for r in wellness], unit, expected=(end-start).days+1)
    for sport, key, scale, unit in [("Run", "run_pace", 1000, "s/km"), ("Swim", "swim_pace", 100, "s/100m")]:
        record(key, [r["duration_sec"]/r["distance_m"]*scale if r.get("duration_sec") and r.get("distance_m") else None
                     for r in rows if sport_family(r["sport"]) == sport], unit)
    days = (end-start).days+1
    active = len({r["date"] for r in rows})
    metrics["active_days"] = dict(value=active if available else None, unit="Tage", expected=days)
    metrics["sessions_per_week"] = dict(value=round(len(rows)*7/days, 2) if available else None, unit="Einheiten/Woche")
    metrics["lit_hit"] = dict(value=None, unit="", status="unavailable")
    return metrics


def similar_sessions(a: list[dict], b: list[dict]) -> list[dict]:
    """One-to-one descriptive matches, never a physiological equivalence claim."""
    pairs, used = [], set()
    for current in sorted(b, key=lambda r: (r["date"], r["id"])):
        candidates = []
        for previous in a:
            if previous["id"] in used or previous["id"] == current["id"] or sport_family(previous["sport"]) != sport_family(current["sport"]):
                continue
            ratios = [current[k]/previous[k] for k in ("duration_sec", "distance_m")
                      if current.get(k) and previous.get(k)]
            if not ratios or min(ratios) < .8 or max(ratios) > 1.2:
                continue
            intensity = abs(current["intensity_percent"]-previous["intensity_percent"]) if current.get("intensity_percent") is not None and previous.get("intensity_percent") is not None else None
            if intensity is not None and intensity > 10:
                continue
            candidates.append((mean(min(r, 1/r) for r in ratios), previous, intensity))
        if candidates:
            _, previous, intensity = max(candidates, key=lambda c: (c[0], c[1]["id"]))
            used.add(previous["id"])
            pairs.append(dict(a=previous["reference"], b=current["reference"], comparability="limited",
                              evidence="Gleiche Sportart; bekannte Dauer/Distanz innerhalb 20 %." + (" Gesamtintensität innerhalb 10 Prozentpunkten." if intensity is not None else " Intensität fehlt."),
                              interval_structure_equal=bool(previous.get("intervals")) and previous.get("intervals") == current.get("intervals"),
                              differences={k: delta(previous.get(k), current.get(k)) for k in ("avg_watts", "np_watts", "avg_hr", "rpe")},
                              limitation="Intervallziele, Umgebung und Messgeräte müssen einzeln geprüft werden; keine automatische Leistungsbewertung."))
    return pairs


class HistoricalAnalysis:
    def __init__(self, client: IntervalsClient, store: AnalystStore | None = None):
        self.client = client
        self.store = store or AnalystStore()
        self.namespace = hashlib.sha256(str(client.athlete_id).encode()).hexdigest()[:16]

    def _kind(self, name: str) -> str:
        return f"history:{self.namespace}:{name}" + (":v2" if name == "cache" else "")

    def _cached(self, label: str, key: str, loader: Callable[[], list[dict] | dict],
                historic: bool = False) -> tuple[list[dict] | dict, dict]:
        kind = self._kind("cache")
        with self.store.connect() as db:
            record = db.execute("SELECT body FROM records WHERE kind=? AND id=?", (kind, f"{label}:{key}")).fetchone()
        cached = json.loads(record[0]) if record else None
        now = datetime.now(timezone.utc)
        if cached and (now-datetime.fromisoformat(cached["fetched_at"])).total_seconds() < (604800 if historic else 120):
            return cached["data"], dict(source=label, status="cached", fetched_at=cached["fetched_at"])
        gates = self.store.records(self._kind("rate_limit"))
        if gates and now < datetime.fromisoformat(gates[0]["until"]):
            return cached["data"] if cached else [], dict(source=label, status="stale" if cached else "unavailable",
                http_status=429, retry_after=gates[0]["until"], fetched_at=cached["fetched_at"] if cached else None)
        try:
            data = loader()
        except (httpx.HTTPError, ValueError) as exc:
            status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
            if status == 429:
                retry = exc.response.headers.get("Retry-After", "60")
                try:
                    seconds = max(60, int(retry))
                except ValueError:
                    from email.utils import parsedate_to_datetime
                    try:
                        seconds = max(60, (parsedate_to_datetime(retry)-now).total_seconds())
                    except (ValueError, TypeError):
                        seconds = 60
                seconds = min(seconds, 604800)
                self.store.put(self._kind("rate_limit"), "all", dict(until=(now+timedelta(seconds=seconds)).isoformat()))
            return cached["data"] if cached else [], dict(source=label, status="stale" if cached else "unavailable",
                http_status=status, retry_after=exc.response.headers.get("Retry-After") if status == 429 else None,
                fetched_at=cached["fetched_at"] if cached else None)
        body = dict(data=data, fetched_at=now.isoformat())
        self.store.put(kind, f"{label}:{key}", body)
        return data, dict(source=label, status="loaded", fetched_at=body["fetched_at"])

    def period(self, period: HistoryPeriod) -> dict:
        activities, events, wellness, sources = [], [], [], []
        # Fixed calendar months allow overlap reuse; only requested months are loaded.
        cursor = period.start.replace(day=1)
        while cursor <= period.end:
            following = (cursor.replace(day=28)+timedelta(days=4)).replace(day=1)
            finish = following-timedelta(days=1)
            for label, loader, target in [("activities", self.client.get_historical_activities, activities),
                                           ("calendar", self.client.get_calendar, events),
                                           ("wellness", self.client.get_wellness_history, wellness)]:
                data, status = self._cached(label, cursor.isoformat(), lambda f=loader, s=cursor, e=finish: f(s, e),
                                            historic=finish < date.today()-timedelta(days=7))
                target.extend(r for r in data if period.start.isoformat() <= r["date"] <= period.end.isoformat())
                sources.append(dict(month=cursor.isoformat(), **status))
            cursor = following
        events = [dict(r, source="planned", distance_m=r.get("distance_km")*1000 if r.get("distance_km") is not None else None)
                  for r in events if r.get("category") == "WORKOUT" or str(r.get("category", "")).startswith("RACE_")]
        manual = {r["reference"]: r for r in self.store.records(self._kind("assignment"))}
        preparations = self.store.records(self._kind("preparation"))
        hints = []
        for row in activities+events:
            row["reference"] = f'{row["source"]}:{row["id"]}'
            hint = phase_hint(row)
            key = row["reference"]
            if key in manual:
                hint = dict(manual[key], confidence="manual", reason="Manuell bestätigt/korrigiert.")
            else:
                hints.append(dict(reference=key, date=row["date"], name=row["name"], **hint))
            if hint.get("confidence") == "manual" and hint.get("week"):
                day = date.fromisoformat(row["date"])
                hint["anchor"] = (day-timedelta(days=day.weekday(), weeks=hint["week"]-1)).isoformat()
            row["assignment"] = hint
            row["preparation_candidates"] = [p["id"] for p in preparations if p["start"] <= row["date"] <= p["end"]]
        for hint in hints:
            self.store.put(self._kind("candidate"), hint["reference"], hint)
        okay = all(s["status"] not in {"unavailable", "stale"} for s in sources if s["source"] == "activities")
        metrics = aggregate(activities, wellness, period.start, period.end, okay)
        if any(s["status"] in {"unavailable", "stale"} for s in sources if s["source"] == "wellness"):
            for key in ("ctl", "atl", "tsb", "hrv", "resting_hr", "weight", "vo2max"):
                metrics[key].update(value=None, status="unavailable")
        groups = {}
        for row in activities+events:
            hint = row["assignment"]
            if hint.get("anchor"):
                group = groups.setdefault((hint["phase"], hint["anchor"]), [])
                group.append(row)
        phases = [dict(phase=phase, anchor=anchor, start=min(r["date"] for r in group), end=max(r["date"] for r in group),
                       weeks=sorted({r["assignment"]["week"] for r in group if r["assignment"].get("week")}),
                       references=[r["reference"] for r in group], confidence="candidate") for (phase, anchor), group in groups.items()]
        return dict(start=period.start.isoformat(), end=period.end.isoformat(), race_date=period.race_date.isoformat() if period.race_date else None,
                    activities=activities, planned=events, wellness=wellness, sources=sources, metrics=metrics,
                    phases=phases, activity_source_complete=okay)

    def compare(self, request: HistoryComparison) -> dict:
        a, b = self.period(request.a), self.period(request.b)
        for p, spec in [(a, request.a), (b, request.b)]:
            if request.sport != "all":
                p["activities"] = [r for r in p["activities"] if sport_family(r["sport"]) == request.sport]
                p["planned"] = [r for r in p["planned"] if sport_family(r["sport"]) == request.sport]
                filtered = aggregate(p["activities"], p["wellness"], spec.start, spec.end, p["activity_source_complete"])
                # Wellness describes the athlete, not a particular sport.
                for key in ("ctl", "atl", "tsb", "hrv", "resting_hr", "weight", "vo2max"):
                    filtered[key] = p["metrics"][key]
                p["metrics"] = filtered
            p["sports"] = {sport: aggregate([r for r in p["activities"] if sport_family(r["sport"]) == sport], [],
                                             spec.start, spec.end, p["activity_source_complete"])
                           for sport in ("Ride", "Run", "Swim")}
            p["weekly"] = []
            cursor = spec.start-timedelta(days=spec.start.weekday())
            while cursor <= spec.end:
                finish = min(cursor+timedelta(days=6), spec.end)
                start = max(cursor, spec.start)
                rows = [r for r in p["activities"] if start.isoformat() <= r["date"] <= finish.isoformat()]
                m = aggregate(rows, [], start, finish, p["activity_source_complete"])
                p["weekly"].append(dict(start=start.isoformat(), end=finish.isoformat(),
                    race_week=(start-spec.race_date).days//7 if spec.race_date else None,
                    **{k: m[k]["value"] for k in ("duration_sec", "tss", "sessions")}))
                cursor += timedelta(days=7)
        pairs = similar_sessions(a["activities"], b["activities"])
        return dict(a=a, b=b, differences={k: delta(a["metrics"][k]["value"], b["metrics"][k]["value"]) for k in a["metrics"]},
                    pairs=pairs, limitations=LIMITATIONS,
                    unequal_days=(request.a.end-request.a.start) != (request.b.end-request.b.start))

    def catalog(self) -> dict:
        return dict(races=self.store.records("race"), preparations=self.store.records(self._kind("preparation")),
                    assignments=self.store.records(self._kind("assignment")),
                    phase_candidates=[r for r in self.store.records(self._kind("candidate")) if r.get("phase")])

    def save_preparation(self, preparation: HistoricalPreparation) -> dict:
        body = preparation.model_dump(mode="json")
        self.store.put(self._kind("preparation"), preparation.id, body)
        return body

    def save_assignment(self, assignment: HistoricalAssignment) -> dict:
        body = assignment.model_dump(mode="json")
        if assignment.preparation_id and assignment.preparation_id not in {r["id"] for r in self.catalog()["preparations"]}:
            raise ValueError("Vorbereitung nicht vorhanden.")
        known = {r["reference"] for r in self.store.records(self._kind("candidate"))} | {r["reference"] for r in self.catalog()["assignments"]}
        if assignment.reference not in known:
            raise ValueError("Einheit zuerst über einen Zeitraum laden.")
        self.store.put(self._kind("assignment"), assignment.reference, body)
        return body

    def comments(self, activity_id: str, historic: bool = False) -> dict:
        data, source = self._cached("comments", activity_id, lambda: self.client.get_historical_comments(activity_id), historic=historic)
        if not isinstance(data, dict):
            return dict(comments=[], source=source)
        # These are search cues, never diagnoses or progress assertions. Negation remains visible.
        cues = {"Abbruch": r"abgebroch|abbruch|aufgegeben|cut short|stopped",
                "Ermüdung": r"müd|muede|schwere[nr]? beine|tired|fatigue",
                "Anstrengung": r"anstreng|hart|locker|easy|effort|erschöpf",
                "Erholung": r"erholt|erholung|recovered|recovery"}
        for comment in data["comments"]:
            comment["topics"] = [label for label, pattern in cues.items() if re.search(pattern, comment["text"], re.I)]
        return dict(**data, source=source, interpretation="Themenhinweise ohne Polaritätsbewertung. Negationen und Kontext im Original prüfen; keine belegte Entwicklung allein aus Schlüsselwörtern.")

    def session_pair(self, a_id: str, b_id: str) -> dict:
        snapshots = self.store.records(self._kind("cache"))
        rows = {}
        for snapshot in sorted(snapshots, key=lambda r: r["fetched_at"]):
            data = snapshot["data"]
            if isinstance(data, list):
                rows.update({r["id"]: dict(r, snapshot_fetched_at=snapshot["fetched_at"]) for r in data if r.get("source") == "activity"})
        if a_id not in rows or b_id not in rows:
            raise ValueError("Beide Aktivitäten zuerst über einen Zeitraum laden.")
        a, b = dict(rows[a_id]), dict(rows[b_id])
        for row in (a, b):
            details, source = self._cached("details", row["id"],
                lambda key=row["id"]: self.client.get_historical_session_details(key),
                historic=date.fromisoformat(row["date"]) < date.today()-timedelta(days=7))
            row["details"] = details if isinstance(details, dict) else {}
            row["details_source"] = source
        comments_a = self.comments(a_id, historic=date.fromisoformat(a["date"]) < date.today()-timedelta(days=7))
        comments_b = self.comments(b_id, historic=date.fromisoformat(b["date"]) < date.today()-timedelta(days=7))
        observations = []
        for key in ("avg_watts", "np_watts", "avg_hr", "rpe", "duration_sec", "distance_m"):
            difference = delta(a.get(key), b.get(key))
            if difference["absolute"] is not None:
                observations.append(dict(metric=key, a=a.get(key), b=b.get(key), **difference,
                                         evidence=[f'activity:{a_id}', f'activity:{b_id}']))
        reference_a, reference_b = dict(a, reference=f"activity:{a_id}"), dict(b, reference=f"activity:{b_id}")
        match = similar_sessions([reference_a], [reference_b])
        return dict(a=a, b=b, comments_a=comments_a, comments_b=comments_b,
                    observations=observations, comparability=match[0] if match else None,
                    interpretation="Messbare Unterschiede sind deskriptiv. RPE und persönliche Kommentare müssen im Zusammenhang mit Dauer, Leistung und Puls gelesen werden. Widersprüchliche Hinweise erlauben keine eindeutige Entwicklungsaussage.",
                    insufficient_evidence=["Intervallabschluss und Abbruch sind ohne Intervall-Soll/Ist und eindeutige persönliche Aussage nicht belegbar.",
                                           "Sensoren, Wetter und Streckenbedingungen sind nicht kontrolliert."])

    def compact_comparison(self, request: HistoryComparison, include_comments: bool = False) -> dict:
        result = self.compare(request)
        for key in ("a", "b"):
            period = result[key]
            period.pop("wellness")
            period.pop("sports")
            period["activities"] = [{k: r.get(k) for k in ("reference", "date", "name", "sport", "duration_sec", "distance_m", "tss", "avg_hr", "avg_watts", "np_watts", "rpe", "assignment")}
                                    for r in period["activities"][:20]]
            period["activities_omitted"] = max(0, period["metrics"]["sessions"]["value"]-20) if period["metrics"]["sessions"]["value"] is not None else None
            period["planned_omitted"] = max(0, len(period["planned"])-10)
            period["planned"] = [dict(r, description=r.get("description", "")[:1000]) for r in period["planned"][:10]]
        result["pairs_omitted"] = max(0, len(result["pairs"])-10)
        result["pairs"] = result["pairs"][:10]
        if include_comments:
            result["comment_pairs"] = [self.session_pair(p["a"].split(":", 1)[1], p["b"].split(":", 1)[1]) for p in result["pairs"][:3]]
            for pair in result["comment_pairs"]:
                for key in ("a", "b"):
                    pair[key].pop("description", None)
                    pair[key].pop("details", None)
                    comments = pair[f"comments_{key}"].get("comments", [])
                    pair[f"comments_{key}"]["omitted_comments"] = max(0, len(comments)-5)
                    pair[f"comments_{key}"]["comments"] = [dict(c, text=c["text"][:1000], text_truncated=len(c["text"]) > 1000) for c in comments[:5]]
            result["comment_coverage"] = "Originalkommentare für maximal drei ähnliche Paare; keine vollständige semantische Auswertung aller Aktivitäten."
        result["comment_note"] = "Für persönliche Kommentare get_historical_session_pair verwenden; Beschreibungen sind keine bestätigten persönlichen Aussagen."
        return result
