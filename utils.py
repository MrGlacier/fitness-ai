def meters_to_km(meters: float) -> float:
    if meters is None:
        return 0

    return round(meters / 1000, 2)