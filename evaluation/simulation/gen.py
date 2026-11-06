import os, json, random, math, shutil
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scenarios")
BIG = "1.7976931348623157E308"

def write(name, pts, wins, speed=40.0, dur=120.0, clock="08:00", opts=None, valid=True, raw_windows=None, raw_props=None):
    d = os.path.join(ROOT, name); os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "destinations.txt"), "w", encoding="utf-8") as f:
        for (i, nm, la, lo) in pts:
            cols = [""] * 19
            cols[0] = str(i); cols[1] = nm; cols[2] = nm; cols[4] = repr(la); cols[5] = repr(lo)
            cols[6] = "P"; cols[7] = "PPL"; cols[8] = "DE";cols[10] = "14"; cols[14] = "1000"
            f.write("\t".join(cols) + "\n")
    with open(os.path.join(d, "windows.tsv"), "w") as f:
        f.write("geonameid\topensAt\tcloseAt\n".replace("closeAt", "closesAt"))
        if raw_windows is not None:
            for r in raw_windows: f.write(r + "\n")
        else:
            for (i, o, c) in wins:
                f.write(f"{i}\t{o}\t{c if c != 'BIG' else BIG}\n")
    with open(os.path.join(d, "scenario.properties"), "w") as f:
        f.write(raw_props if raw_props else f"speedKmh={speed}\nstartClock={clock}\ndurationMinutes={dur}\n")
    meta = dict(name=name, opts=opts or [], valid=valid)
    json.dump(meta, open(os.path.join(d, "meta.json"), "w"))

def mkpts(rng, n, spread=0.15, clustered=False, colinear=False, dup=False):
    base = (48.0 + rng.random(), 11.0 + rng.random())
    pts = []
    for k in range(n):
        if colinear: la, lo = base[0], base[1] + k * 0.03
        elif clustered: la = base[0] + rng.choice([0, 0.1]) + rng.random()*0.005; lo = base[1] + rng.choice([0, 0.1]) + rng.random()*0.005
        else: la = base[0] + (rng.random()-0.5)*spread*2; lo = base[1] + (rng.random()-0.5)*spread*2
        if dup and k > 0 and rng.random() < 0.4: la, lo = pts[rng.randrange(k)][2:4]
        pts.append((1000 + k, f"City{k}x{rng.randrange(10**6)}", round(la, 5), round(lo, 5)))
    return pts

def wins_for(rng, pts, mode, dur):
    w = [(pts[0][0], 0, "BIG")]
    for p in pts[1:]:
        if mode == "generous": o, c = 0, 10000
        elif mode == "tight":
            o = rng.uniform(0, dur*0.7); c = o + rng.uniform(0, 25)
        elif mode == "mixed":
            o = rng.uniform(0, dur); c = o + rng.uniform(5, dur)
        else:
            o = round(rng.uniform(0, dur), 2); c = o + round(rng.uniform(0, dur), 2)
        w.append((p[0], round(o, 3), round(c, 3)))
    return w

def main():
    if os.path.isdir(ROOT): shutil.rmtree(ROOT)
    os.makedirs(ROOT)
    rng = random.Random(12345)
    N = 16
    for i in range(N):
        n = rng.randint(2, 8)
        pts = mkpts(rng, n+1)
        write(f"random_{i}", pts, wins_for(rng, pts, "random", 120), speed=rng.choice([30, 40, 60]),
              dur=120, opts=[])
    for i in range(N):
        pts = mkpts(rng, rng.randint(2, 7)); write(f"zeroperiod_{i}", pts, wins_for(rng, pts, "generous", 0), dur=0, opts=["--duration-minutes", "0"])
    for i in range(N):
        pts = mkpts(rng, rng.randint(3, 7), spread=0.5); write(f"smallperiod_{i}", pts, wins_for(rng, pts, "generous", 1), dur=0.5, opts=["--duration-minutes", "0.5"])
    for i in range(N):
        pts = mkpts(rng, rng.randint(3, 8), spread=0.3)
        w = [(pts[0][0], 0, "BIG")] + [(p[0], 0, 0.001) for p in pts[1:]]
        write(f"unreachable_{i}", pts, w, dur=300)
    # window closing exactly at arrival: customer window closes at travel time (computed in run_sims too); here use depot-adjacent
    for i in range(N):
        pts = mkpts(rng, rng.randint(1, 4)); write(f"exactclose_{i}", pts, [], dur=600, opts=[])
        # windows filled by run_sims? Compute here with own haversine
        d = os.path.join(ROOT, f"exactclose_{i}")
        from oracle import hav
        sp = 40.0
        w = [(pts[0][0], 0, "BIG")]
        for p in pts[1:]:
            t = hav(pts[0][2], pts[0][3], p[2], p[3]) * 60 / sp
            w.append((p[0], 0, t))  # close exactly at arrival (floating risk reported as ambiguity)
        write(f"exactclose_{i}", pts, w, dur=600)
    for i in range(N):
        pts = mkpts(rng, rng.randint(2, 6)); w = [(pts[0][0], 0, "BIG")] + [(p[0], 200 + rng.randint(0, 50), 400) for p in pts[1:]]
        write(f"earlywait_{i}", pts, w, dur=900)
    for i in range(N):
        pts = mkpts(rng, rng.randint(1, 5)); write(f"depotonly_{i}", pts, [(pts[0][0], 0, "BIG")], dur=100)
    for i in range(N):
        pts = mkpts(rng, 2); write(f"one_{i}", pts, wins_for(rng, pts, "mixed", 120), dur=rng.choice([20, 60, 120]))
    for i in range(N):
        pts = mkpts(rng, 9, spread=0.1); write(f"eight_{i}", pts, wins_for(rng, pts, "generous", 600), dur=600, speed=60)
    for i in range(N):
        pts = mkpts(rng, rng.randint(5, 9)); write(f"tight_{i}", pts, wins_for(rng, pts, "tight", 120), dur=150)
    for fam, kw in (("cluster", dict(clustered=True)), ("colinear", dict(colinear=True)), ("dupcoord", dict(dup=True))):
        for i in range(N):
            pts = mkpts(rng, rng.randint(4, 9), **kw); write(f"{fam}_{i}", pts, wins_for(rng, pts, "mixed", 200), dur=240, speed=rng.choice([20, 40]))
    for i in range(N):
        pts = mkpts(rng, rng.randint(3, 8)); sp = rng.choice([5, 15, 40, 90, 500])
        write(f"speed_{i}", pts, wins_for(rng, pts, "mixed", 200), speed=sp, dur=200, opts=["--speed", str(sp)])
    offs = [["--start-time", "09:30"], ["--start-time", "08:00"], ["--start-time", "30"], ["--start-time", "1500"], ["--start-time", "1440"], ["--start-time", "45.5"], ["--start-time", "23:59"]]
    for i in range(N):
        pts = mkpts(rng, rng.randint(3, 7)); o = offs[i % len(offs)]
        write(f"startoff_{i}", pts, wins_for(rng, pts, "generous", 3000), dur=120, opts=o)
    for i in range(N):
        pts = mkpts(rng, rng.randint(6, 9)); write(f"cap_{i}", pts, wins_for(rng, pts, "generous", 500), dur=500, opts=["--max-destinations", str(rng.randint(2, 5))])
    for i in range(N):
        pts = mkpts(rng, rng.randint(4, 8)); write(f"tl0_{i}", pts, wins_for(rng, pts, "mixed", 200), dur=240, opts=["--time-limit-ms", "0"])
    # invalid
    pts = mkpts(rng, 4); W = wins_for(rng, pts, "generous", 100)
    def inv(name, **kw): write("invalid_" + name, kw.pop("pts", pts), kw.pop("wins", W), valid=False, **kw)
    inv("dupid", wins=W + [W[1]])
    inv("reversed", wins=[W[0], (W[1][0], 50, 10)] + W[2:])
    inv("nan", wins=[W[0], (W[1][0], "NaN", 10)] + W[2:])
    inv("negative", wins=[W[0], (W[1][0], -5, 10)] + W[2:])
    inv("unknownid", wins=W + [(999999, 0, 10)])
    badp = [pts[0], (pts[1][0], pts[1][1], 95.0, pts[1][3])] + pts[2:]
    inv("badlat", pts=badp)
    inv("negdur", opts=["--duration-minutes", "-5"])
    inv("speed0", opts=["--speed", "0"])
    inv("startbefore", opts=["--start-time", "07:00"])
    inv("dupid_dest", pts=pts + [pts[1]])
    print("generated", len(os.listdir(ROOT)))
if __name__ == "__main__": main()
