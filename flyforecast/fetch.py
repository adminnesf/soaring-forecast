"""Download model forecasts (temperature / wind by altitude) from Open-Meteo.

Open-Meteo is free and needs no key. It serves GFS, HRRR, ECMWF, GEM and
more, including the pressure-level data a skew-T is drawn from.
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.open-meteo.com/v1/forecast"
TZ = "America/New_York"

LEVELS = [1000, 975, 950, 925, 900, 850, 800, 750, 700, 650, 600, 550, 500]
LEVEL_VARS = ["temperature", "relative_humidity", "wind_speed", "wind_direction",
              "geopotential_height"]
SURFACE_VARS = ["temperature_2m", "dew_point_2m", "wind_speed_10m",
                "wind_direction_10m", "wind_gusts_10m", "precipitation",
                "cloud_cover", "cape", "shortwave_radiation"]


def _hourly_vars():
    v = list(SURFACE_VARS)
    for p in LEVELS:
        for name in LEVEL_VARS:
            v.append(f"{name}_{p}hPa")
    return v


def _get(params, tries=3):
    url = API + "?" + urllib.parse.urlencode(params, safe=",")
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "newengland-flying-forecast"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")[:300]
            if e.code == 400:  # bad request - retrying won't help
                raise RuntimeError(f"Open-Meteo 400: {body}") from e
            last = e
        except Exception as e:  # network hiccup
            last = e
        time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"Open-Meteo request failed: {last}")


def _split_models(data, models):
    """Return {model: {"time": [...], var: [...]}} from an Open-Meteo reply."""
    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    out = {}
    for m in models:
        suffix = f"_{m}"
        d = {"time": times}
        for key, vals in hourly.items():
            if key == "time":
                continue
            if len(models) == 1:
                d[key] = vals
            elif key.endswith(suffix):
                d[key[: -len(suffix)]] = vals
        # keep only models that actually returned temperatures
        temps = d.get("temperature_2m") or []
        if any(t is not None for t in temps):
            out[m] = d
    return out


_BAD_MODELS = set()  # models Open-Meteo rejected this run


def fetch_site(site, models, forecast_days=7, past_days=0):
    """Fetch every model for one site. Returns {model: hourly dict}."""
    models = [m for m in models if m not in _BAD_MODELS]
    base = {
        "latitude": site["lat"],
        "longitude": site["lon"],
        # temperatures are adjusted to the valley/LZ elevation
        "elevation": round(site["ground_m"]),
        "hourly": ",".join(_hourly_vars()),
        "wind_speed_unit": "mph",
        "precipitation_unit": "inch",
        "temperature_unit": "celsius",
        "timezone": TZ,
        "forecast_days": forecast_days,
        "past_days": past_days,
    }
    try:
        data = _get({**base, "models": ",".join(models)})
        return _split_models(data, models)
    except RuntimeError as e:
        # One model may reject a variable; fall back to one model at a time.
        print(f"  {site['id']}: combined request failed ({e}); trying models one by one")
    out = {}
    for m in models:
        try:
            data = _get({**base, "models": m})
            out.update(_split_models(data, [m]))
        except RuntimeError as e:
            print(f"  {site['id']}: {m} unavailable ({e})")
            if "400" in str(e):
                _BAD_MODELS.add(m)
    return out
