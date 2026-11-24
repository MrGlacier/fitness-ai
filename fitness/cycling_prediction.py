"""Steady-state flat-road power balance, explicitly conditional scenarios."""
from statistics import median

from fitness.performance_evidence import positive
from fitness.plan_analysis import sport_family, workout_date


def road_speed(power: float, mass: float, cda: float, crr: float, rho: float = 1.225,
               efficiency: float = .97, headwind: float = 0, grade: float = 0) -> float:
    """Solve eta*P = .5*rho*CdA*(v+wind)|v+wind|*v + mg(Crr+grade)*v."""
    if not all(positive(v) for v in (power, mass, cda, crr, rho, efficiency)):
        raise ValueError('Positive finite physical inputs required')
    low, high = 0., 50.
    for _ in range(80):
        v = (low + high) / 2
        required = .5 * rho * cda * (v + headwind) * abs(v + headwind) * v + mass * 9.80665 * (crr + grade) * v
        if required > power * efficiency:
            high = v
        else:
            low = v
    return (low + high) / 2


def cycling_scenario(distance: float, workouts: list, today, race: dict) -> dict | None:
    current = [w for w in workouts if sport_family(w.sport) == 'Ride'
               and 0 <= (today - workout_date(w)).days <= 180]
    # Duration is a conservative product gate, not a physiological threshold.
    long = [w for w in current if positive(w.avg_watts) and w.duration_sec >= distance / 30 * 3600 * .5
            and (w.variability_index is None or w.variability_index <= 1.15)
            and (w.rpe is None or w.rpe <= (7 if 'tri' in race.get('sport', '').casefold() else 10))]
    if race.get('elevation_gain_m', 0):
        return None  # Aggregate elevation cannot describe a course profile.
    settings = sorted([w for w in current if positive(w.ftp)], key=lambda w: (workout_date(w), w.id))
    latest = settings[-1] if settings else None
    ftp_fallback = not long and latest is not None
    if not long:
        if not latest:
            return None
        long = [latest]
    masses = [w.weight_kg for w in current if positive(w.weight_kg)]
    if not masses:
        return None
    newest = max(workout_date(w) for w in long)
    recent = [w for w in long if (newest - workout_date(w)).days <= 56]
    powers = [(w.avg_watts * latest.ftp / w.ftp if latest and positive(w.ftp) else w.avg_watts) for w in recent]
    power = median(powers)
    if ftp_fallback:
        hours = distance / 30
        fraction = .78 if hours <= 3.5 else .70
        power = latest.ftp * fraction
    mass = median(masses) + 10
    # Joint resistance is only identifiable under assumptions about wind and Crr.
    calibration = []
    historical = [w for w in workouts if sport_family(w.sport) == 'Ride'
                  and workout_date(w) <= today and positive(w.avg_watts) and w.duration_sec >= 3600]
    for w in historical:
        if w.sport != 'Ride' or w.is_indoor or not positive(w.distance_km) or w.elevation_gain is None:
            continue
        if w.elevation_gain / w.distance_km > 5 or (w.elapsed_sec or w.duration_sec) > 1.05 * w.duration_sec:
            continue
        v = w.distance_km * 1000 / w.duration_sec
        historical_mass = (w.weight_kg if positive(w.weight_kg) else mass - 10) + 10
        cda = (w.avg_watts * .97 - historical_mass * 9.80665 * .004 * v) / (.5 * 1.225 * v ** 3)
        if .15 <= cda <= .65:
            calibration.append(dict(id=w.id, cda=cda))
    cda = median([r['cda'] for r in calibration]) if calibration else .35
    missing_margin = .05 * (not latest) + .05 * any(w.rpe is None for w in recent)
    # Regular range varies one aggregate performance factor, not all adverse extremes together.
    center = distance * 1000 / road_speed(power, mass, cda, .004)
    margin = .10 + missing_margin + (.03 if not calibration else 0) + (.04 if ftp_fallback else 0)
    low, high = center * (1-margin), center * (1+margin)
    extreme_high = distance * 1000 / road_speed(power * .85, mass, cda + .1, .006, headwind=2)
    return dict(times=(low, center, high), selected=recent, power_watts=round(power),
                calibration=calibration, ftp_activity_id=latest.id if latest else None,
                sensitivity_seconds=round(extreme_high),
                assumptions=[f'Bedingtes Flachstreckenmodell: Leistung {power:.0f} W ' + ('aus FTP mit angenommenem nachhaltigem Anteil; nicht persönlich validiert.' if ftp_fallback else 'aus langen Einheiten, keine garantierte Triathlonleistung.'),
                             f'Gesamtmasse {mass:.1f} kg (Rad/Gepäck angenommen 10 kg); CdA {cda:.2f} ±0,10 m², Crr 0,003–0,006, Luftdichte 1,225 kg/m³, Wirkungsgrad 0,97, Gegenwind 0–2 m/s.',
                             'Reguläre Spanne um die zentrale Leistung; kombinierte extreme Widerstands-/Windszenarien separat. Keine statistische Fehlerspanne.',
                             'FTP ist eine datierte Einstellung unbekannter Messmethode; Skalierung historischer Leistung mit FTP-Verhältnis ist heuristisch.'])
