"""Turn model data into a sounding (temperature / wind by height) and do the math.

Heights are kept in meters internally and converted to feet for display.
"""
import math

from .fetch import LEVELS

DRY_ADIABAT_C_PER_M = 0.0098  # parcel cools ~3 C per 1000 ft
FT_PER_M = 3.28084


# ---------------------------------------------------------------------------
# TIM'S LAPSE-RATE FORMULA - LOCKED. Do not change. The app never tunes this.
#   (ground temp C - temp C at top of lift) / (top of lift, thousands of ft AGL)
# ---------------------------------------------------------------------------
def tim_lapse(t_ground_c, t_tol_c, tol_agl_ft):
    if tol_agl_ft is None or tol_agl_ft <= 0:
        return None
    return (t_ground_c - t_tol_c) / (tol_agl_ft / 1000.0)


def dewpoint(t_c, rh):
    """Dew point (C) from temperature and relative humidity (Magnus formula)."""
    if t_c is None or rh is None or rh <= 0:
        return None
    a, b = 17.625, 243.04
    g = math.log(rh / 100.0) + a * t_c / (b + t_c)
    return b * g / (a - g)


def _val(d, key, i):
    arr = d.get(key)
    if not arr or i >= len(arr):
        return None
    return arr[i]


def profile(d, i, ground_m):
    """Sounding at hour index i: list of points sorted by height (m MSL).

    The ground point uses the model's 2 m values (already adjusted to the
    LZ elevation); pressure levels below the ground are dropped.
    """
    pts = []
    t2 = _val(d, "temperature_2m", i)
    if t2 is None:
        return []
    pts.append({
        "z": ground_m, "t": t2, "td": _val(d, "dew_point_2m", i),
        "ws": _val(d, "wind_speed_10m", i), "wd": _val(d, "wind_direction_10m", i),
        "p": None,
    })
    for p in LEVELS:
        z = _val(d, f"geopotential_height_{p}hPa", i)
        t = _val(d, f"temperature_{p}hPa", i)
        if z is None or t is None or z <= ground_m + 20:
            continue
        rh = _val(d, f"relative_humidity_{p}hPa", i)
        pts.append({
            "z": z, "t": t, "td": dewpoint(t, rh),
            "ws": _val(d, f"wind_speed_{p}hPa", i), "wd": _val(d, f"wind_direction_{p}hPa", i),
            "p": p,
        })
    pts.sort(key=lambda q: q["z"])
    return pts


def interp_t(prof, z):
    """Environment temperature at height z (m MSL)."""
    if not prof:
        return None
    if z <= prof[0]["z"]:
        return prof[0]["t"]
    for a, b in zip(prof, prof[1:]):
        if a["z"] <= z <= b["z"]:
            f = (z - a["z"]) / (b["z"] - a["z"])
            return a["t"] + f * (b["t"] - a["t"])
    return prof[-1]["t"]


def wind_at(prof, z):
    """Wind speed (mph) and direction (deg from) at height z, interpolating u/v."""
    pts = [q for q in prof if q["ws"] is not None and q["wd"] is not None]
    if not pts:
        return None, None

    def uv(q):
        r = math.radians(q["wd"])
        return -q["ws"] * math.sin(r), -q["ws"] * math.cos(r)

    if z <= pts[0]["z"]:
        u, v = uv(pts[0])
    elif z >= pts[-1]["z"]:
        u, v = uv(pts[-1])
    else:
        for a, b in zip(pts, pts[1:]):
            if a["z"] <= z <= b["z"]:
                f = (z - a["z"]) / (b["z"] - a["z"])
                ua, va = uv(a)
                ub, vb = uv(b)
                u, v = ua + f * (ub - ua), va + f * (vb - va)
                break
    spd = math.hypot(u, v)
    wd = (math.degrees(math.atan2(-u, -v)) + 360) % 360
    return spd, wd


def top_of_lift(prof, ground_m, t_start, td_start=None):
    """Top of lift (m MSL): where a thermal starting at t_start on the ground,
    cooling at the dry rate, meets the environment temperature. Capped at
    cloud base when the air is moist enough for cumulus.

    Returns (tol_m, cloudbase_m or None).
    """
    if not prof or t_start is None:
        return None, None
    cloudbase = None
    if td_start is not None and td_start < t_start:
        cloudbase = ground_m + 125.0 * (t_start - td_start)  # ~ 410 ft per C spread
    top = prof[-1]["z"]
    z = ground_m
    step = 10.0
    tol = top
    while z <= top:
        parcel = t_start - DRY_ADIABAT_C_PER_M * (z - ground_m)
        if z > ground_m + 30 and parcel <= interp_t(prof, z):
            tol = z
            break
        z += step
    if cloudbase is not None and cloudbase < tol:
        return cloudbase, cloudbase
    return tol, cloudbase


def vector_mean(winds):
    """Average a list of (speed, dir) pairs. Returns (mean speed, mean dir)."""
    winds = [(s, d) for s, d in winds if s is not None and d is not None]
    if not winds:
        return None, None
    u = sum(-s * math.sin(math.radians(d)) for s, d in winds) / len(winds)
    v = sum(-s * math.cos(math.radians(d)) for s, d in winds) / len(winds)
    mean_spd = sum(s for s, _ in winds) / len(winds)
    d = (math.degrees(math.atan2(-u, -v)) + 360) % 360
    return mean_spd, d


# ---------------------------------------------------------------------------
# Thermal strength (W*) and Buoyancy/Shear ratio, the RASP / XC Skies way:
#   B/S = W* / (sqrt(Cd) * average wind in the boundary layer),  Cd = 0.003
# 5 or less = dry thermals likely broken up by the wind (turbulent).
# W* (Deardorff velocity) needs surface heating; the models here don't give
# it directly, so it is estimated as ~30% of incoming sunshine.
# ---------------------------------------------------------------------------
CD_BL = 0.003
SENSIBLE_FRACTION = 0.3


def bl_avg_wind_ms(prof, ground_m, top_m):
    """Vector-average wind (m/s) from the ground to top of lift."""
    if top_m is None or top_m <= ground_m:
        return None
    n, us, vs = 0, 0.0, 0.0
    z = ground_m + 10
    while z <= top_m:
        spd, wd = wind_at(prof, z)
        if spd is not None:
            r = math.radians(wd)
            us += -spd * math.sin(r)
            vs += -spd * math.cos(r)
            n += 1
        z += 50
    if not n:
        return None
    return math.hypot(us / n, vs / n) * 0.44704  # mph -> m/s


def wstar_ms(sun_wm2, bl_depth_m, t_c):
    if sun_wm2 is None or bl_depth_m is None or t_c is None or bl_depth_m <= 0:
        return None
    flux = SENSIBLE_FRACTION * max(sun_wm2, 0.0) / 1200.0  # K m/s
    return (9.81 / (t_c + 273.15) * flux * bl_depth_m) ** (1 / 3)


def bs_ratio(wstar, u_bl_ms):
    if wstar is None or u_bl_ms is None:
        return None
    if u_bl_ms < 0.3:
        return 20.0  # practically no wind: no shear
    return min(20.0, wstar / (math.sqrt(CD_BL) * u_bl_ms))
