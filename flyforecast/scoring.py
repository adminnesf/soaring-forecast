"""Rate each site and day."""
import statistics
from collections import defaultdict
from datetime import date

from .sounding import (FT_PER_M, bl_avg_wind_ms, bs_ratio, interp_t, profile,
                       tim_lapse, top_of_lift, vector_mean, wind_at, wstar_ms)

MODEL_NAMES = {"gfs_hrrr": "HRRR", "ncep_rrfs_conus": "RRFS", "gfs_global": "GFS",
               "ecmwf_ifs025": "ECMWF", "gem_seamless": "GEM (Canada)",
               "icon_seamless": "ICON (Germany)"}


def model_name(m):
    return MODEL_NAMES.get(m, m)

VERDICTS = {
    "GO": "Leave work - go fly",
    "MAYBE": "Pretty good",
    "WORK": "Stay at work",
    "HOME": "Stay home",
    "NOLIFT": "No usable lift",
}

DIRS16 = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
          "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]


def compass(deg):
    if deg is None:
        return "?"
    return DIRS16[int((deg % 360) / 22.5 + 0.5) % 16]


def in_range(deg, lo, hi):
    deg, lo, hi = deg % 360, lo % 360, hi % 360
    if lo == hi:
        return True
    if lo < hi:
        return lo <= deg <= hi
    return deg >= lo or deg <= hi  # wraps through north


def verdict(number, settings):
    if number is None:
        return "NOLIFT"
    r = settings["lapse_ratings"]
    if number >= r["go"]:
        return "GO"
    if number >= r["maybe"]:
        return "MAYBE"
    if number >= r["stay_at_work"]:
        return "WORK"
    return "HOME"


def hours_by_date(times):
    """{date: {hour: index}} from Open-Meteo local ISO times."""
    out = defaultdict(dict)
    for i, t in enumerate(times):
        d, hm = t.split("T")
        out[d][int(hm[:2])] = i
    return out


def site_hours(site, settings, ds):
    """Hours used for a site on a given date. Each site can set when its
    thermals turn on, separately for prime season (May-Aug) and the rest."""
    base = dict(settings["hours"])
    th = site.get("thermal_hour")
    if th:
        month = int(ds[5:7])
        prime = month in settings.get("prime_months", [5, 6, 7, 8])
        hour = th["prime"] if prime else th["other"]
        base["lapse_hour"] = hour
        base["flying_start"] = hour
        base["flying_end"] = max(hour + 3, base["flying_end"])
        base["heating_hour"] = max(hour, base["heating_hour"])
    return base


def evaluate_model_day(site, d, idx, settings, t_offset=0.0, hrs=None):
    """One model, one day. idx = {hour: index}. t_offset (C) is subtracted
    from the 2 m temperatures (bias correction); 0 = raw model."""
    hrs = hrs or settings["hours"]
    g = site["ground_m"]

    def t2(i):
        v = d["temperature_2m"][i]
        return None if v is None else v - t_offset

    temps = [t2(idx[h]) for h in range(9, 19) if h in idx and t2(idx[h]) is not None]
    if not temps or hrs["heating_hour"] not in idx or hrs["lapse_hour"] not in idx:
        return None
    tmax = max(temps)

    ih = idx[hrs["heating_hour"]]
    prof_h = profile(d, ih, g)
    if len(prof_h) < 3:
        return None
    td_h = d.get("dew_point_2m", [None] * (ih + 1))[ih]
    tol_m, cb_m = top_of_lift(prof_h, g, tmax, td_h)
    if tol_m is None:
        return None
    tol_agl_ft = (tol_m - g) * FT_PER_M

    def number_at(hour):
        if hour not in idx:
            return None
        i = idx[hour]
        prof = profile(d, i, g)
        if not prof or t2(i) is None or tol_agl_ft < 300:
            return None
        return tim_lapse(t2(i), interp_t(prof, tol_m), tol_agl_ft)

    number = number_at(hrs["lapse_hour"])

    # thermal strength and buoyancy/shear at the thermal hour
    il = idx[hrs["lapse_hour"]]
    prof_l = profile(d, il, g)
    sun = d.get("shortwave_radiation", [None] * (il + 1))[il]
    ws = wstar_ms(sun, tol_m - g, t2(il))
    bs = bs_ratio(ws, bl_avg_wind_ms(prof_l, g, tol_m))
    by_hour = {h: number_at(h) for h in range(9, 16)}

    winds, rain, cape = [], 0.0, 0.0
    for h in range(hrs["flying_start"], hrs["flying_end"] + 1):
        if h not in idx:
            continue
        i = idx[h]
        winds.append(wind_at(profile(d, i, g), site["launch_m"]))
        rain += d.get("precipitation", [0] * (i + 1))[i] or 0.0
        cape = max(cape, d.get("cape", [0] * (i + 1))[i] or 0.0)
    spd, wdir = vector_mean(winds)
    speeds = [w[0] for w in winds if w[0] is not None]

    return {
        "number": None if number is None else round(number, 2),
        "lapse_hour": hrs["lapse_hour"],
        "by_hour": {str(h): (None if v is None else round(v, 2)) for h, v in by_hour.items()},
        "tol_ft_agl": round(tol_agl_ft),
        "tol_ft_msl": round(tol_m * FT_PER_M),
        "cloudbase_ft_msl": None if cb_m is None else round(cb_m * FT_PER_M),
        "tmax_c": round(tmax, 1),
        "wind_mph": None if spd is None else round(spd, 1),
        "wind_max_mph": round(max(speeds), 1) if speeds else None,
        "wind_dir": None if wdir is None else round(wdir),
        "rain_in": round(rain, 2),
        "cape": round(cape),
        "thermal_fpm": None if ws is None else round(ws * 196.85),
        "bs": None if bs is None else round(bs, 1),
    }


def wind_check(site, spd, wdir, settings):
    """Return (flyable, label, flags) for the wind at launch."""
    w = settings["wind"]
    light = w["light_mph"]
    strong = site.get("strong_mph", w["strong_mph"])
    mx = site.get("max_mph", w["max_mph"])
    flags = []
    if spd is None or wdir is None:
        return False, "no wind data", ["No wind data"]

    for nf in site["no_fly"]:
        if in_range(wdir, nf["from"], nf["to"]):
            return False, "no-fly direction", [f"NO-FLY: {nf['reason']}"]

    if not site["windows"]:
        flags.append("Wind directions TBD - direction not checked")
    ok_dir = not site["windows"]
    for win in site["windows"]:
        if in_range(wdir, win["from"], win["to"]):
            if win.get("light_only"):
                if spd <= light:
                    ok_dir = True
                    flags.append("Edge direction - works only because wind is light")
                else:
                    return False, "edge direction, too strong", [
                        f"{compass(wdir)} only works here in light wind (0-{light} mph)"]
            else:
                ok_dir = True
            if ok_dir:
                break
    if not ok_dir:
        return False, "wrong direction", [f"Wind {compass(wdir)} doesn't work here"]

    if spd > mx:
        return False, "too strong", [f"Over {mx} mph at launch"]
    if spd > strong:
        flags.append(site.get("strong_label", f"Strong ({strong}-{mx} mph)"))
        return True, "strong", flags
    if spd <= light:
        return True, "light", flags
    return True, "good", flags


def consensus(site, per_model, settings, lead):
    """Combine the models into one rating for the site/day."""
    vals = {m: r for m, r in per_model.items() if r}
    if not vals:
        return None
    numbers = [r["number"] for r in vals.values() if r["number"] is not None]
    number = round(statistics.median(numbers), 2) if numbers else None
    spd, wdir = vector_mean([(r["wind_mph"], r["wind_dir"]) for r in vals.values()])
    flyable, wind_label, flags = wind_check(site, spd, wdir, settings)
    rainy = sum(1 for r in vals.values() if r["rain_in"] >= settings["rain_inches"])
    if rainy * 2 >= len(vals):
        flyable = False
        flags.append("Rain in the forecast")
    od = sum(1 for r in vals.values()
             if r["cape"] >= settings["od_cape"] and r["rain_in"] > 0)
    if od * 2 >= len(vals):
        flags.append("Overdevelopment / thunderstorm risk")
    spread = round(max(numbers) - min(numbers), 2) if len(numbers) > 1 else None
    agree = agreement(list(vals.values()))
    bss = [r["bs"] for r in vals.values() if r.get("bs") is not None]
    bs = round(statistics.median(bss), 1) if bss else None
    b = settings.get("turbulence", {"turbulent": 5, "smooth": 7})
    if bs is not None and bs <= b["turbulent"]:
        flags.append(f"Turbulent: wind likely to break up thermals (B/S {bs})")
    fpms = [r["thermal_fpm"] for r in vals.values() if r.get("thermal_fpm") is not None]
    v = verdict(number, settings)
    tols = [r["tol_ft_agl"] for r in vals.values()]
    return {
        "number": number,
        "verdict": v,
        "flyable": flyable and v != "NOLIFT",
        "wind_mph": None if spd is None else round(spd, 1),
        "wind_dir": None if wdir is None else round(wdir),
        "wind_label": wind_label,
        "tol_ft_agl": round(statistics.median(tols)),
        "flags": flags,
        "spread": spread,
        "agreement": agree,
        "bs": bs,
        "thermal_fpm": round(statistics.median(fpms)) if fpms else None,
        "models": sorted(vals),
        "lead": lead,
    }


def _ang_diff(a, b):
    d = abs(a - b) % 360
    return min(d, 360 - d)


def agreement(results):
    """0-100: how well the models agree on Tim's number, top of lift, and
    wind at launch. 100 = all the same, 0 = all over the place."""
    rs = [r for r in results if r]
    if len(rs) < 2:
        return None
    parts = []
    nums = [r["number"] for r in rs if r["number"] is not None]
    if len(nums) >= 2:
        parts.append(min(1.0, (max(nums) - min(nums)) / 1.2))
    elif any(r["number"] is None for r in rs) and nums:
        parts.append(1.0)  # some models see lift, others none
    tols = [r["tol_ft_agl"] for r in rs]
    parts.append(min(1.0, (max(tols) - min(tols)) / 4000))
    spds = [r["wind_mph"] for r in rs if r["wind_mph"] is not None]
    if len(spds) >= 2:
        parts.append(min(1.0, (max(spds) - min(spds)) / 10))
    dirs = [r["wind_dir"] for r in rs if r["wind_dir"] is not None]
    if len(dirs) >= 2 and max(spds or [0]) > 3:
        worst = max(_ang_diff(a, b) for a in dirs for b in dirs)
        parts.append(min(1.0, worst / 90))
    return round(100 * (1 - sum(parts) / len(parts)))


def rank_key(c):
    """Higher is better. Unflyable days sink to the bottom but stay listed."""
    if c is None or c["number"] is None:
        return -99
    return c["number"] + (0 if c["flyable"] else -10)


def evaluate_site(site, model_data, settings, today, bias=None):
    """All days for a site. Returns {date_str: {"models": {...},
    "corrected": {...}, "consensus": {...}, "consensus_corrected": {...}}}"""
    out = {}
    bias = bias or {}
    dates = set()
    for d in model_data.values():
        dates |= set(hours_by_date(d["time"]))
    for ds in sorted(dates):
        lead = (date.fromisoformat(ds) - today).days
        if lead < 0:
            continue
        raw, corr = {}, {}
        hrs = site_hours(site, settings, ds)
        for m, d in model_data.items():
            idx = hours_by_date(d["time"]).get(ds, {})
            raw[m] = evaluate_model_day(site, d, idx, settings, hrs=hrs)
            b = bias.get(m, {})
            if raw[m] and b.get("n", 0) >= settings["tuning"]["min_samples"]:
                corr[m] = evaluate_model_day(site, d, idx, settings,
                                             t_offset=b["tmax_bias_c"], hrs=hrs)
        out[ds] = {
            "lead": lead,
            "lapse_hour": hrs["lapse_hour"],
            "models": raw,
            "corrected": corr,
            "consensus": consensus(site, raw, settings, lead),
            "consensus_corrected": consensus(site, corr, settings, lead) if corr else None,
        }
    return out
