"""Independent route validator and scoring (brief sections 5.4 and 5.5)."""

TOLERANCE = 1e-9


def failure_result(reason):
    """Result for a run that produced no scorable route, with a plain-text reason."""
    return {
        "valid": False,
        "failureReason": reason,
        "visited": None,
        "skipped": None,
        "distanceKm": None,
        "travelMinutes": None,
        "waitMinutes": None,
        "totalMinutes": None,
        "returnMinute": None,
        "schedule": None,
    }


def _check_shape(route, count):
    if not isinstance(route, list) or len(route) < 2:
        return "route must be a list with at least a start and an end"
    for loc in route:
        if type(loc) is not int or not 0 <= loc < count:
            return f"unknown location id {loc!r}"
    if route[0] != 0:
        return "route must start at depot 0"
    if route[-1] != 0:
        return "route must end at depot 0"
    middle = route[1:-1]
    if 0 in middle:
        return "depot 0 visited in the middle of the route"
    if len(set(middle)) != len(middle):
        return "route repeats a customer"
    return None


def validate_route(instance, route):
    """Replay `route` on `instance`; return a result dict.

    Always has keys: valid, failureReason, visited, skipped, distanceKm,
    travelMinutes, waitMinutes, totalMinutes, returnMinute, schedule.
    When invalid, failureReason is text and all metrics are None.
    """
    locations = instance["locations"]
    dist = instance["distanceKm"]
    speed = instance["speedKmh"]

    problem = _check_shape(route, len(locations))
    if problem:
        return failure_result(problem)

    clock = instance["departureMinute"]
    travel = wait = km = 0
    schedule = []
    for i, j in zip(route, route[1:]):
        step = dist[i][j]
        minutes = step / speed * 60
        arrive = clock + minutes
        km += step
        travel += minutes
        if j == 0:
            clock = arrive
            break
        loc = locations[j]
        start = max(arrive, loc["opensAt"])
        if start > loc["closesAt"] + TOLERANCE:
            return failure_result(f"arrived late at location {j}: {start} after close {loc['closesAt']}")
        wait += start - arrive
        schedule.append({"id": j, "arriveMinute": arrive, "startMinute": start, "leaveMinute": start})
        clock = start

    if clock > instance["deadlineMinute"] + TOLERANCE:
        return failure_result(f"returned to depot at {clock}, after deadline {instance['deadlineMinute']}")

    visited_ids = set(route[1:-1])
    return {
        "valid": True,
        "failureReason": None,
        "visited": len(visited_ids),
        "skipped": [loc["id"] for loc in locations[1:] if loc["id"] not in visited_ids],
        "distanceKm": km,
        "travelMinutes": travel,
        "waitMinutes": wait,
        "totalMinutes": travel + wait,
        "returnMinute": clock,
        "schedule": schedule,
    }


def rank_key(result):
    """Sort key: smaller is better. Failures sort after every valid result."""
    if not result["valid"]:
        return (1, 0, 0)
    return (0, -result["visited"], result["distanceKm"])
