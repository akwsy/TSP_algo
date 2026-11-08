"""Build a problem instance from places and a configuration."""
import math
import random

from .config import ConfigError, DAY_END, DAY_START, SLOT_COUNT, SLOT_MINUTES

EARTH_RADIUS_KM = 6371.0088
DEPOT_NAME = "Kuala Lumpur"


def haversine_km(a, b):
    p1, p2 = math.radians(a.lat), math.radians(b.lat)
    dp, dl = p2 - p1, math.radians(b.lon - a.lon)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(h))


def select_kuala_lumpur_150km(places, config, rng):
    """Default selection rule: depot Kuala Lumpur, customers a seeded sample of
    populated places (class P) within config.radius_km (default 150 km), without replacement.
    A rule is any function (places, config, rng) -> (depot, customers)."""
    depots = [p for p in places if p.name == DEPOT_NAME and p.feature_class == "P"]
    if not depots:
        raise ConfigError(f"depot place '{DEPOT_NAME}' (populated place) not found in dataset")
    depot = min(depots, key=lambda p: p.geoname_id)
    candidates = sorted(
        (p for p in places
         if p.feature_class == "P" and p is not depot and haversine_km(depot, p) <= config.radius_km),
        key=lambda p: p.geoname_id)
    if len(candidates) < config.num_customers:
        raise ConfigError(
            f"only {len(candidates)} candidate places within {config.radius_km:g} km of the depot, "
            f"but {config.num_customers} customers requested")
    return depot, rng.sample(candidates, config.num_customers)


def build_instance(places, config, select=select_kuala_lumpur_150km):
    rng = random.Random(config.seed)
    depot, customers = select(places, config, rng)
    points = [depot] + list(customers)
    locations = [{"id": 0, "geonameId": depot.geoname_id, "name": depot.name,
                  "lat": depot.lat, "lon": depot.lon, "isDepot": True,
                  "opensAt": 0, "closesAt": DAY_END}]
    for i, p in enumerate(customers, start=1):
        slot = rng.randrange(SLOT_COUNT)
        start = DAY_START + slot * SLOT_MINUTES
        locations.append({"id": i, "geonameId": p.geoname_id, "name": p.name,
                          "lat": p.lat, "lon": p.lon, "isDepot": False,
                          "opensAt": start, "closesAt": start + SLOT_MINUTES, "slot": slot})
    size = len(points)
    matrix = [[0.0] * size for _ in range(size)]
    for i in range(size):
        for j in range(i):
            matrix[i][j] = matrix[j][i] = haversine_km(points[i], points[j])
    return {"instanceId": config.instance_id, "seed": config.seed,
            "departureMinute": config.departure_minute, "periodMinutes": config.period_minutes,
            "deadlineMinute": config.deadline_minute, "speedKmh": config.speed_kmh,
            "locations": locations, "distanceKm": matrix}
