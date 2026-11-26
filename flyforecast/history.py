"""Saved forecast runs, alert bookkeeping, verification log and corrections."""
import csv
import json
from datetime import datetime, timedelta

from .config import DATA_DIR

RUNS = DATA_DIR / "runs"
ALERTS = DATA_DIR / "alerts_sent.json"
VERIFY_CSV = DATA_DIR / "verification.csv"
REPORTS_CSV = DATA_DIR / "flight_reports.csv"
BIAS = DATA_DIR / "bias.json"

VERIFY_FIELDS = ["date", "site", "model", "lead", "fc_number", "an_number",
                 "fc_tol_ft", "an_tol_ft", "fc_tmax_c", "an_tmax_c", "obs_tmax_c",
                 "fc_wind_mph", "an_wind_mph", "obs_wind_mph"]
REPORT_FIELDS = ["date", "site", "flew", "tol_ft", "conditions", "notes", "issue"]


def _read_json(path, default):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_run(run_id, payload):
    RUNS.mkdir(parents=True, exist_ok=True)
    (RUNS / f"{run_id}.json").write_text(json.dumps(payload, separators=(",", ":")))


def list_runs():
    return sorted(RUNS.glob("*.json")) if RUNS.exists() else []


def load_run(path):
    return _read_json(path, {})


def previous_runs(n, exclude=None):
    out = []
    for p in reversed(list_runs()):
        if exclude and p.stem == exclude:
            continue
        out.append(load_run(p))
        if len(out) >= n:
            break
    return out


def prune_runs(keep_days=21):
    cutoff = (datetime.utcnow() - timedelta(days=keep_days)).strftime("%Y%m%dT%H")
    for p in list_runs():
        if p.stem < cutoff:
            p.unlink()


def alerts_sent():
    return _read_json(ALERTS, {})


def mark_alert(key):
    sent = alerts_sent()
    sent[key] = datetime.utcnow().isoformat(timespec="minutes")
    # forget alerts older than 14 days
    cutoff = (datetime.utcnow() - timedelta(days=14)).isoformat()
    sent = {k: v for k, v in sent.items() if v >= cutoff}
    ALERTS.parent.mkdir(parents=True, exist_ok=True)
    ALERTS.write_text(json.dumps(sent, indent=1))


def load_bias():
    return _read_json(BIAS, {})


def save_bias(b):
    BIAS.write_text(json.dumps(b, indent=1))


def _append_csv(path, fields, rows):
    new = not path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if new:
            w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in fields})


def append_verification(rows):
    _append_csv(VERIFY_CSV, VERIFY_FIELDS, rows)


def append_reports(rows):
    _append_csv(REPORTS_CSV, REPORT_FIELDS, rows)


def read_csv(path):
    if not path.exists():
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))
