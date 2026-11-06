import os, re, json, subprocess, sys, collections
from concurrent.futures import ThreadPoolExecutor
import oracle
HERE = os.path.dirname(os.path.abspath(__file__)); SC = os.path.join(HERE, "scenarios")
ALGS = ["nearest", "greedy", "exact"]

def load(d):
    coords = {}; names = {}
    for line in open(os.path.join(d, "destinations.txt"), encoding="utf-8"):
        c = line.rstrip("\n").split("\t"); i = int(c[0]); names[i] = c[1]; coords[i] = (float(c[4]), float(c[5]))
    win = {}; order = []
    for line in open(os.path.join(d, "windows.tsv")).read().splitlines()[1:]:
        i, o, c = line.split("\t"); win[int(i)] = (float(o), float(c)); order.append(int(i))
    props = dict(l.strip().split("=", 1) for l in open(os.path.join(d, "scenario.properties")) if "=" in l)
    return coords, names, win, order, props

def run(alg, d, opts):
    p = subprocess.run([os.path.join(HERE, "runner.sh"), "--algorithm", alg, "--data", d] + opts, capture_output=True, text=True, timeout=120)
    return p.returncode, p.stdout, p.stderr

def tparse(s):
    m = re.match(r"(\d+):(\d+):(\d+)(?:\+(\d+)d)?$", s); h, mi, se, dd = m.groups()
    return int(h)*60 + int(mi) + int(se)/60 + 1440*int(dd or 0)

def parse(out):
    r = {}
    m = re.search(r"^(.*): (OPTIMAL|FEASIBLE_HEURISTIC|SEARCH_LIMIT_REACHED|\w+)\s*$", out, re.M)
    for l in out.splitlines():
        mm = re.match(r"^[^:]*: (OPTIMAL|FEASIBLE_HEURISTIC|SEARCH_LIMIT_REACHED)$", l)
        if mm: r["status"] = mm.group(1)
    m = re.search(r"Visited: (\d+)/(\d+)", out); r["K"], r["N"] = int(m.group(1)), int(m.group(2))
    m = re.search(r"Distance: ([\d.]+) km; travel: ([\d.]+) min; waiting: ([\d.]+) min; return: (\S+)", out)
    r["dist"], r["travel"], r["wait"], r["ret"] = float(m.group(1)), float(m.group(2)), float(m.group(3)), tparse(m.group(4))
    r["route"] = re.search(r"^Route: (.*)$", out, re.M).group(1).split(" -> ")
    r["skipped"] = re.search(r"^Skipped: (.*)$", out, re.M).group(1)
    r["stops"] = [(int(a), tparse(b), tparse(c), float(w)) for a, b, c, w in re.findall(r"^\s+(\d+) .*?: arrival (\S+); visit (\S+); wait ([\d.]+) min", out, re.M)]
    return r

def eff(opts, props, depot_clock):
    o = dict(zip(opts[::2], opts[1::2]))
    sp = float(o.get("--speed", props["speedKmh"])); per = float(o.get("--duration-minutes", props["durationMinutes"]))
    h, m = props["startClock"].split(":"); base = int(h)*60 + int(m)
    st = o.get("--start-time", "0")
    start = (int(st.split(":")[0])*60 + int(st.split(":")[1]) - base) if ":" in st else float(st)
    cap = int(o.get("--max-destinations", 15))
    return sp, per, start, base, cap

def check_one(fam, d, name, opts):
    fails = []; notes = []
    coords, names, win, order, props = load(d)
    depot = order[0]; sp, per, start, base, cap = eff(opts, props, None)
    custs_all = order[1:]; custs = custs_all[:cap-1]
    res = {}
    for alg in ALGS:
        rc, out, err = run(alg, d, opts)
        if rc != 0: fails.append(f"{alg}: nonzero exit {rc}: {err.strip()[:200]}"); continue
        try: r = parse(out)
        except Exception as e: fails.append(f"{alg}: unparseable output ({e})"); continue
        rc2, out2, _ = run(alg, d, opts)
        if out2 != out and re.sub(r"Runtime: .*", "", out2) != re.sub(r"Runtime: .*", "", out):
            if re.sub(r"Runtime:.*|candidates/states.*", "", out) != re.sub(r"Runtime:.*|candidates/states.*", "", out2):
                fails.append(f"{alg}: nondeterministic output")
        ids = [s[0] for s in r["stops"]]; res[alg] = (r, ids)
        if "status" not in r: fails.append(f"{alg}: no status")
        exp = {"nearest": "FEASIBLE_HEURISTIC", "greedy": "FEASIBLE_HEURISTIC", "exact": "OPTIMAL"}[alg]
        if r.get("status") != exp and not (r.get("status") == "SEARCH_LIMIT_REACHED" and ("--time-limit-ms" in opts or "--max-destinations" in opts)):
            fails.append(f"{alg}: status {r.get('status')} expected {exp}")
        if [names[i] for i in ids] != r["route"]: fails.append(f"{alg}: route names disagree with stop lines")
        ok, dist, end, stops = oracle.validate_route(ids, coords, win, start, per, sp)
        if not ok: fails.append(f"{alg}: INFEASIBLE route {ids}"); continue
        if any(i not in custs_all for i in ids[1:-1]): fails.append(f"{alg}: unknown customer")
        if cap < len(order) and any(i not in custs for i in ids[1:-1]): notes.append(f"{alg}: visits customer beyond first {cap-1} (cap semantic differs)")
        if r["K"] != len(ids) - 2: fails.append(f"{alg}: Visited K {r['K']} != {len(ids)-2}")
        if abs(r["dist"] - dist) > 1e-4: fails.append(f"{alg}: distance {r['dist']} vs recomputed {dist}")
        if abs(r["ret"] - (base + end)) > 1/60 + 1e-6: fails.append(f"{alg}: return time {r['ret']} vs {base+end}")
        for (i, a, v, w), (i2, a2, v2, w2) in zip(r["stops"], stops):
            if abs(a - (base + a2)) > 1/60 + 1e-6 or abs(v - (base + v2)) > 1/60 + 1e-6 or abs(w - w2) > 2e-3:
                fails.append(f"{alg}: stop {i} times mismatch reported {a},{v},{w} vs {base+a2},{base+v2},{w2}"); break
        if abs(r["wait"] - sum(s[3] for s in stops)) > 1e-3: fails.append(f"{alg}: waiting total mismatch")
        # depart at start
        if abs(r["stops"][0][2] - (base + start)) > 1/60 + 1e-6: fails.append(f"{alg}: departure time wrong")
    if "exact" in res:
        er, eids = res["exact"]
        limited = er.get("status") == "SEARCH_LIMIT_REACHED"
        if limited: notes.append(f"{name}: exact returned SEARCH_LIMIT_REACHED ({len(eids)-2} visits); heuristics visited " + ", ".join(f"{a}={len(res[a][1])-2}" for a in ('nearest','greedy') if a in res) + f" ({opts})")
        # oracle uses candidate set from file order, capped
        if len(custs) <= 8 and not limited:
            k, od, oo = oracle.solve(depot, custs, coords, win, start, per, sp)
            _, edist, _, _ = oracle.simulate(eids, coords, win, start, per, sp)
            if "--time-limit-ms" in opts and er.get("status") == "SEARCH_LIMIT_REACHED": pass
            elif len(eids) - 2 != k or abs(edist - od) > 1e-6:
                if cap < len(order): notes.append(f"{name}: exact {len(eids)-2}/{edist:.6f} vs oracle(first {cap-1}) {k}/{od:.6f}")
                else: fails.append(f"exact != oracle: exact {len(eids)-2} visits {edist:.6f} km, oracle {k} visits {od:.6f} km")
            for alg in ("nearest", "greedy"):
                if alg in res:
                    ids = res[alg][1]; _, dd, _, _ = oracle.simulate(ids, coords, win, start, per, sp)
                    if len(ids) - 2 > k or (len(ids) - 2 == k and dd < od - 1e-6):
                        if cap < len(order): notes.append(f"{alg} beat oracle under cap")
                        else: fails.append(f"{alg} beats optimum: {len(ids)-2}/{dd:.6f} vs {k}/{od:.6f}")
        for alg in ("nearest", "greedy"):
            if alg in res and not limited:
                ids = res[alg][1]; _, dd, _, _ = oracle.simulate(ids, coords, win, start, per, sp)
                if len(ids) - 2 > len(eids) - 2 or (len(ids) == len(eids) and dd < edist - 1e-6):
                    fails.append(f"{alg} beats exact output")
    return fails, notes

def check_invalid(d, name, opts):
    rc, out, err = run("exact", d, opts)
    return ([] if rc != 0 and err.startswith("Error:") else [f"expected nonzero exit + 'Error:' (rc={rc}, stderr={err.strip()[:100]!r})"]), []

def main():
    jobs = []
    for n in sorted(os.listdir(SC)):
        d = os.path.join(SC, n); m = json.load(open(os.path.join(d, "meta.json")))
        jobs.append((("invalid" if n.startswith("invalid") else n.rsplit("_", 1)[0]), d, n, m["opts"], m["valid"]))
    def work(j):
        fam, d, n, opts, valid = j
        try: f, nt = (check_one(fam, d, n, opts) if valid else check_invalid(d, n, opts))
        except Exception as e: f, nt = [f"harness exception {e!r}"], []
        return j, f, nt
    with ThreadPoolExecutor(8) as ex: results = list(ex.map(work, jobs))
    fam = collections.defaultdict(lambda: [0, 0]); failures = []; notes = []
    for (f_, d, n, opts, valid), f, nt in results:
        fam[f_][0 if not f else 1] += 1
        for x in f: failures.append((n, d, opts, x))
        for x in nt: notes.append((n, x))
    L = ["# Black-box test report", "", "## Counts per family", "", "| family | pass | fail |", "|---|---|---|"]
    for k in sorted(fam): L.append(f"| {k} | {fam[k][0]} | {fam[k][1]} |")
    tp = sum(v[0] for v in fam.values()); tf = sum(v[1] for v in fam.values())
    L += ["", f"Total scenarios: {tp+tf}; passed: {tp}; failed: {tf}", "", "## Failures", ""]
    if not failures: L.append("None.")
    for n, d, opts, x in failures:
        alg = x.split(":")[0] if x.split(":")[0] in ALGS else "exact"
        L.append(f"- `{n}` ({d}): {x}\n  - repro: `./runner.sh --algorithm {alg} --data {d} {' '.join(opts)}`")
    L += ["", "## Notes (non-failures observed during run)", ""] + ([f"- {n}: {x}" for n, x in notes] or ["None."])
    L += ["", "## Spec ambiguities", "", AMB]
    open(os.path.join(HERE, "REPORT.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L[:40])); print("failed", tf, "of", tp + tf)

AMB = """- OBSERVATION (cap): with --max-destinations below the data size, exact returns SEARCH_LIMIT_REACHED with the greedy feasible route, while nearest/greedy ignore the cap and visit all reachable customers. The "never beat exact" rule is only enforced when exact reported OPTIMAL.
- `--max-destinations` semantics: assumed to keep the first N-1 customers in windows.tsv order; the spec does not say which are kept. Mismatches vs that assumption are only listed as notes.
- Window closing "exactly at arrival" is subject to floating-point rounding of haversine/speed; the tester's close = own computed travel time may differ from the implementation's by 1 ulp (rule 5 gives 1e-9 tolerance for the return time, but rule 3 states no tolerance for windows). The oracle uses a 1e-9 tolerance on windows too.
- Oracle treats depot window as checked only at departure (start in [opensAt, closesAt]); return-time vs depot closesAt is not constrained by spec.
- Reported times are printed rounded to seconds; reported times are compared with a 1 second tolerance, distance with 1e-4 km.
- Numeric `--start-time` that is a plain number is interpreted as minutes offset (decimals accepted?) - spec says "plain number"; decimal offsets were tested.
- Status for `--time-limit-ms 0` is allowed to be OPTIMAL or SEARCH_LIMIT_REACHED for exact; heuristics' behavior at limit 0 unspecified (FEASIBLE_HEURISTIC or limit status both accepted only if the former; any other flagged).
- destinations.txt required plausible values in columns 8/9 (feature code, country) and 15 (population): runner rejected rows lacking them ('Invalid population or missing classification/country'), which the spec only hints at ('others may be anything plausible').
- Generated 'invalid_startbefore' (--start-time earlier than startClock) and 'invalid_dupid_dest' (duplicate ID in destinations.txt) are extra invalid cases beyond the spec's list (spec: start-time must not precede startClock; IDs unique)."""
if __name__ == "__main__": main()
