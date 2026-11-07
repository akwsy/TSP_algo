"""Saving and reusing full-run sessions.

Sessions have their own index, results/sessions-index.json (NOT results/index.json, which stays
first-day runs only, so the existing pages never see sessions). Layout (stable; the website
tickets read it):

    {"sessions": [ {"file": "sessions/<name>.json",   path relative to the results dir
                    "runId", "algorithmId", "instanceId", "numCustomers", "seed", "experiment",
                    "fingerprint", "instanceHash", "formatVersion", "maxDays", "timestamp",
                    "outcome", "stopReason", "stopDay", "days", "visitedSoFar", "workingMinutes",
                    "unvisitedAtStop", "partialFigures"} ] }

The session files themselves are described in harness/session.py.

Reuse key: algorithmId + fingerprint (hash of every file in the algorithm folder, so the time
limit in algorithm.json counts) + instanceHash + experiment + formatVersion (SESSION_FORMAT_VERSION
in harness/session.py: session logic, record layout, working-hours definition) + maxDays (the
effective day cap). Changing any of them runs the session again. Entries written before
formatVersion and maxDays existed lack them, so they are never reused (they stay as history).
Only indexed sessions are ever reused; a session file without a matching index entry (e.g.
written before this index existed) is not. Saving a session deletes every older file with the
same key and replaces its index entry, so a key never has duplicates. Sessions of other algorithm versions stay (History).
"""
import json

from .run import write_index

INDEX_FIELDS = ("runId", "algorithmId", "instanceId", "numCustomers", "seed", "experiment",
                "fingerprint", "instanceHash", "formatVersion", "maxDays", "timestamp", "outcome",
                "stopReason", "stopDay", "days", "visitedSoFar", "workingMinutes", "unvisitedAtStop",
                "partialFigures")


def session_key(s):
    return (s.get("algorithmId"), s.get("fingerprint"), s.get("instanceHash"), s.get("experiment"),
            s.get("formatVersion"), s.get("maxDays"))


def read_sessions_index(results_dir):
    try:
        return json.loads((results_dir / "sessions-index.json").read_text(encoding="utf-8"))["sessions"]
    except (OSError, ValueError, KeyError):
        return []


def find_saved_session(entries, results_dir, key):
    """Saved session record for `key`, or None (also when its file is missing or unreadable)."""
    if None in key:
        return None
    for entry in reversed(entries):
        if session_key(entry) == key:
            try:
                return json.loads((results_dir / entry["file"]).read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
    return None


def save_session(results_dir, entries, session):
    """Write the session file, drop older files and index entries with the same key, append the
    new entry and rewrite the index atomically. Returns the updated entries."""
    out = results_dir / "sessions"
    key = session_key(session)
    for old in out.glob("*.json"):
        try:
            if session_key(json.loads(old.read_text(encoding="utf-8"))) == key:
                old.unlink()
        except (OSError, ValueError):
            pass
    name = f"{session['algorithmId']}__{session['instanceId']}__{session['runId']}.json"
    (out / name).write_text(json.dumps(session, indent=2) + "\n", encoding="utf-8")
    entries = [e for e in entries if session_key(e) != key]
    entries.append({"file": f"sessions/{name}", **{k: session.get(k) for k in INDEX_FIELDS}})
    write_index(results_dir / "sessions-index.json", {"sessions": entries})
    return entries
