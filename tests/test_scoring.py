"""Offline checks with made-up soundings (no internet needed).

Run:  python -m pytest -q   (or)   python tests/test_scoring.py
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from flyforecast.config import load_settings, load_sites  # noqa: E402
from flyforecast.fetch import LEVELS  # noqa: E402
from flyforecast.scoring import agreement, evaluate_site, in_range, wind_check  # noqa: E402
from flyforecast.sounding import bs_ratio, tim_lapse, wstar_ms  # noqa: E402

SETTINGS = load_settings()
SITES = {s["id"]: s for s in load_sites()}

# rough standard-atmosphere heights for each pressure level (m)
HEIGHTS = {1000: 110, 975: 320, 950: 540, 925: 760, 900: 990, 850: 1460,
           800: 1950, 750: 2470, 700: 3010, 650: 3590, 600: 4210, 550: 4870,
           500: 5570}


def fake_model(day, ground_m, t_ground, lapse_c_per_km, wind_mph, wind_dir,
               morning_drop=0.0):
    """One day of hourly data. The air aloft starts from the morning ground
    temperature and cools lapse_c_per_km with height; the ground heats up by
    morning_drop C between 8 am and 2 pm (t_ground is the afternoon high)."""
    times, data = [], {}
    keys = ["temperature_2m", "dew_point_2m", "wind_speed_10m", "wind_direction_10m",
            "precipitation", "cape", "shortwave_radiation"]
    for p in LEVELS:
        keys += [f"temperature_{p}hPa", f"relative_humidity_{p}hPa",
                 f"wind_speed_{p}hPa", f"wind_direction_{p}hPa",
                 f"geopotential_height_{p}hPa"]
    for k in keys:
        data[k] = []
    for h in range(24):
        times.append(f"{day}T{h:02d}:00")
        warm = max(0.0, min(1.0, (h - 8) / 6))  # 0 at 8am -> 1 at 2pm
        tg = t_ground - morning_drop * (1 - warm)
        data["temperature_2m"].append(tg)
        data["dew_point_2m"].append(t_ground - 20)  # dry: no cloud cap
        data["wind_speed_10m"].append(wind_mph * 0.6)
        data["wind_direction_10m"].append(wind_dir)
        data["precipitation"].append(0.0)
        data["cape"].append(0.0)
        data["shortwave_radiation"].append(max(0.0, 800 * (1 - abs(h - 13) / 6)))
        for p in LEVELS:
            z = HEIGHTS[p]
            t = (t_ground - morning_drop) - lapse_c_per_km * max(0, z - ground_m) / 1000
            data[f"temperature_{p}hPa"].append(t)
            data[f"relative_humidity_{p}hPa"].append(40)
            data[f"wind_speed_{p}hPa"].append(wind_mph)
            data[f"wind_direction_{p}hPa"].append(wind_dir)
            data[f"geopotential_height_{p}hPa"].append(z)
    data["time"] = times
    return data


def test_tims_example():
    # 20 C ground, 13 C at a 5,000 ft top of lift -> 1.4 (stay home)
    assert abs(tim_lapse(20, 13, 5000) - 1.4) < 1e-9


def test_wraparound_direction():
    assert in_range(350, 330, 30)
    assert in_range(10, 330, 30)
    assert not in_range(90, 330, 30)


def test_ascutney_north_rules():
    s = SITES["ascutney_north"]
    assert wind_check(s, 6, 320, SETTINGS)[0]            # NW, 6 mph: good
    assert not wind_check(s, 7, 270, SETTINGS)[0]        # due west: no-fly
    assert wind_check(s, 2, 290, SETTINGS)[0]            # WNW light: ok
    assert not wind_check(s, 6, 290, SETTINGS)[0]        # WNW 6 mph: no
    assert wind_check(s, 2, 15, SETTINGS)[0]             # NNE light: ok
    assert not wind_check(s, 13, 330, SETTINGS)[0]       # over 12: no-fly


def test_mt_tom_limits():
    s = SITES["mt_tom"]
    ok, label, _ = wind_check(s, 4, 270, SETTINGS)
    assert ok and label in ("good", "light")
    ok, label, flags = wind_check(s, 6, 270, SETTINGS)
    assert ok and label == "strong" and "Mt Tom's limit" in flags[0]
    assert not wind_check(s, 9, 270, SETTINGS)[0]


def test_unstable_vs_stable_day():
    s = SITES["mt_tom"]
    day = "2027-05-01"
    today = date(2027, 4, 30)
    # Air cooling fast with height vs. a stable airmass, same 10 C of heating
    good = {"gfs_global": fake_model(day, s["ground_m"], 24, 7.5, 4, 270, morning_drop=10)}
    bad = {"gfs_global": fake_model(day, s["ground_m"], 24, 4.0, 4, 270, morning_drop=10)}
    rg = evaluate_site(s, good, SETTINGS, today)[day]["consensus"]
    rb = evaluate_site(s, bad, SETTINGS, today)[day]["consensus"]
    print("unstable:", rg["number"], rg["verdict"], rg["tol_ft_agl"])
    print("stable:  ", rb["number"], rb["verdict"], rb["tol_ft_agl"])
    assert rg["number"] > rb["number"]
    assert rg["flyable"]


def test_buoyancy_shear():
    w = wstar_ms(800, 1500, 25)          # strong sun, 5,000 ft deep
    assert 1.5 < w < 3.0                 # roughly 300-600 ft/min
    calm = bs_ratio(w, 10 * 0.447)       # 10 mph average wind
    windy = bs_ratio(w, 25 * 0.447)      # 25 mph average wind
    print("W*", round(w * 196.85), "fpm  B/S 10 mph:", round(calm, 1), " 25 mph:", round(windy, 1))
    assert calm > 7 and windy <= 5


def test_agreement_meter():
    a = {"number": 2.9, "tol_ft_agl": 6000, "wind_mph": 6, "wind_dir": 300}
    b = dict(a, number=2.85, tol_ft_agl=6200, wind_mph=7, wind_dir=310)
    c = dict(a, number=1.8, tol_ft_agl=2500, wind_mph=14, wind_dir=200)
    same, mixed = agreement([a, b]), agreement([a, b, c])
    print("agreement same:", same, " mixed:", mixed)
    assert same > 85 and mixed < 40


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
