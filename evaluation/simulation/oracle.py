import math, itertools
R = 6371.0088
def hav(la1, lo1, la2, lo2):
    p1, p2 = math.radians(la1), math.radians(la2)
    dp = p2 - p1; dl = math.radians(lo2 - lo1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2 * R * math.asin(min(1.0, math.sqrt(a)))
EPS = 1e-9
def simulate(order, coords, win, start, period, speed):
    """order: list of ids incl depot first and last. returns (ok, dist, end, stops[(id,arr,visit,wait)])"""
    t = start; dist = 0.0; stops = [(order[0], start, start, 0.0)]
    d0 = order[0]
    if not (win[d0][0] - EPS <= start <= win[d0][1] + EPS): return False, 0, 0, stops
    if len(set(order[1:-1])) != len(order) - 2 or order[0] != order[-1] or d0 in order[1:-1]: return False, 0, 0, stops
    for a, b in zip(order, order[1:]):
        km = hav(*coords[a], *coords[b]); dist += km; t += km * 60 / speed
        if b == d0: stops.append((b, t, t, 0.0)); break
        o, c = win[b]
        if t > c + EPS: return False, dist, t, stops
        v = max(t, o); stops.append((b, t, v, v - t)); t = v
    return t <= start + period + EPS, dist, t, stops
def validate_route(order, coords, win, start, period, speed):
    ok, dist, end, stops = simulate(order, coords, win, start, period, speed)
    return ok, dist, end, stops
def solve(depot, custs, coords, win, start, period, speed):
    best = (0, 0.0, [depot, depot])
    for k in range(1, len(custs) + 1):
        for perm in itertools.permutations(custs, k):
            order = [depot, *perm, depot]
            ok, dist, _, _ = simulate(order, coords, win, start, period, speed)
            if ok and (k > best[0] or (k == best[0] and dist < best[1] - 1e-12)):
                best = (k, dist, order)
    return best
