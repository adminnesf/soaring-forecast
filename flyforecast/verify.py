"""Evening check: how did today's forecast do?

1. Re-runs today through the newest model data (the same-day "analysis").
2. Pulls today's high temperature and wind from each site's NWS weather station.
3. Compares both with the forecasts made 1 and 3 days earlier and logs it.
4. Works out each model's temperature error per site. Those corrections are
   applied to the INPUTS only - Tim's formula and thresholds never change.
5. Logs any flight reports Tim filed and closes them.
"""
import json
import os
import re
import statistics
import urllib.request
from collections import defaultdict
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from . import history
from .config import load_settings, load_sites
from .fetch import fetch_site
from .scoring import evaluate_model_day, hours_by_date, site_hours

TZ = ZoneInfo("America/New_York")
UA = {"User-Agent": "(newengland-flying-forecast, github.com)",
      "Accept": "application/geo+json"}


def _json(url, headers=None, method="GET", body=None):
    req = urllib.request.Request(url, headers=headers or UA, method=method,
                                 data=None if body is None else json.dumps(body).encode())
    with urllib.request.urlopen(req, timeout=60) as r:
        txt = r.read().decode()
        return json.loads(txt) if txt else {}


def station_obs(station, day):
    """Today's high temp (C, 9am-6pm) and mean wind (mph, 11am-4pm) at a station."""
    meta = _json(f"https://api.weather.gov/stations/{station}")
    elev_m = (meta.get("properties", {}).get("elevation") or {}).get("value")
    start = datetime(day.year, day.month, day.day, 9, tzinfo=TZ)
    end = start + timedelta(hours=9)
    url = (f"https://api.weather.gov/stations/{station}/observations?"
           f"start={start.isoformat()}&end={end.isoformat()}")
    feats = _json(url).get("features", [])
    temps, winds = [], []
    for f in feats:
        p = f["properties"]
        t = (p.get("temperature") or {}).get("value")
        if t is not None:
            temps.append(t)
        hour = datetime.fromisoformat(p["timestamp"]).astimezone(TZ).hour
        w = (p.get("windSpeed") or {}).get("value")  # km/h
        if w is not None and 11 <= hour <= 16:
            winds.append(w * 0.621371)
    return {"tmax_c": max(temps) if temps else None,
            "wind_mph": statistics.mean(winds) if winds else None,
            "elev_m": elev_m}


def _latest_run_per_day():
    """{run date: run payload} keeping the last run made each day."""
    out = {}
    for p in history.list_runs():
        run = history.load_run(p)
        made = run.get("made_local")
        if made:
            out[date.fromisoformat(made[:10])] = run
    return out


def _f(x, nd=2):
    return None if x is None else round(x, nd)


def check_reports(settings):
    token = os.environ.get("GITHUB_TOKEN")
    repo = settings["repo"]
    if not token:
        print("No GITHUB_TOKEN - skipping flight reports")
        return
    h = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
         "User-Agent": "newengland-flying-forecast"}
    api = f"https://api.github.com/repos/{repo}"
    issues = _json(f"{api}/issues?state=open&per_page=50", h)
    rows = []
    for iss in issues:
        if iss.get("user", {}).get("login", "").lower() != repo.split("/")[0].lower():
            continue  # only Tim's own reports count
        labels = [lab["name"] for lab in iss.get("labels", [])]
        if "flight-report" not in labels and not iss["title"].lower().startswith("flight report"):
            continue
        body = iss.get("body") or ""
        fields = dict(re.findall(r"###\s*(.+?)\s*\n+(.*?)(?=\n###|\Z)", body, re.S))
        get = lambda *names: next((fields[n].strip() for n in names if n in fields), "")  # noqa: E731
        rows.append({"date": get("Date"), "site": get("Site"), "flew": get("Did you fly?"),
                     "tol_ft": get("Top of lift (ft)"), "conditions": get("Conditions"),
                     "notes": get("Notes").replace("\n", " "), "issue": iss["number"]})
        _json(f"{api}/issues/{iss['number']}/comments", h, "POST",
              {"body": "Logged - thanks. This goes into the forecast check."})
        _json(f"{api}/issues/{iss['number']}", h, "PATCH", {"state": "closed"})
    if rows:
        history.append_reports(rows)
        print(f"Logged {len(rows)} flight report(s)")


def recompute_bias(settings):
    rows = history.read_csv(history.VERIFY_CSV)
    cutoff = (date.today() - timedelta(days=settings["tuning"]["window_days"])).isoformat()
    errs = defaultdict(lambda: defaultdict(list))
    for r in rows:
        if r["date"] < cutoff or not r["fc_tmax_c"] or not r["obs_tmax_c"]:
            continue
        errs[r["site"]][r["model"]].append(float(r["fc_tmax_c"]) - float(r["obs_tmax_c"]))
    bias = {s: {m: {"tmax_bias_c": round(statistics.mean(v), 2), "n": len(v)}
                for m, v in models.items()} for s, models in errs.items()}
    history.save_bias(bias)
    print("Corrections updated:", json.dumps(bias))


def run_verify(fetch=fetch_site, obs=station_obs):
    settings = load_settings()
    sites = load_sites()
    today = datetime.now(TZ).date()
    ds = today.isoformat()
    runs = _latest_run_per_day()
    rows = []
    for site in sites:
        sid = site["id"]
        try:
            data = fetch(site, ["ncep_rrfs_conus", "gfs_hrrr", "gfs_global"], forecast_days=1)
        except Exception as e:
            print(f"{sid}: analysis fetch failed: {e}")
            data = {}
        an = None
        for m in ("ncep_rrfs_conus", "gfs_hrrr", "gfs_global"):
            if m in data:
                idx = hours_by_date(data[m]["time"]).get(ds, {})
                an = evaluate_model_day(site, data[m], idx, settings,
                                        hrs=site_hours(site, settings, ds))
                if an:
                    break
        try:
            o = obs(site["station"], today)
        except Exception as e:
            print(f"{sid}: station {site['station']} failed: {e}")
            o = {}
        obs_t = o.get("tmax_c")
        if obs_t is not None and o.get("elev_m") is not None:
            # bring the station reading to the site's ground elevation
            obs_t -= 0.0098 * (site["ground_m"] - o["elev_m"])

        for lead in (1, 3):
            run = runs.get(today - timedelta(days=lead))
            day = (run or {}).get("results", {}).get(sid, {}).get(ds)
            if not day:
                continue
            for m, fc in day["models"].items():
                if not fc:
                    continue
                rows.append({
                    "date": ds, "site": sid, "model": m, "lead": lead,
                    "fc_number": fc["number"], "an_number": an and an["number"],
                    "fc_tol_ft": fc["tol_ft_agl"], "an_tol_ft": an and an["tol_ft_agl"],
                    "fc_tmax_c": fc["tmax_c"], "an_tmax_c": an and an["tmax_c"],
                    "obs_tmax_c": _f(obs_t, 1),
                    "fc_wind_mph": fc["wind_mph"], "an_wind_mph": an and an["wind_mph"],
                    "obs_wind_mph": _f(o.get("wind_mph"), 1),
                })
    if rows:
        history.append_verification(rows)
        print(f"Logged {len(rows)} forecast checks for {ds}")
    else:
        print("Nothing to check yet (need forecasts made 1 or 3 days ago).")
    recompute_bias(settings)
    try:
        check_reports(settings)
    except Exception as e:
        print(f"Flight report check failed: {e}")
