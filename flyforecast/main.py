"""Entry point.

    python -m flyforecast.main forecast   # fetch models, rate, build page, send alerts
    python -m flyforecast.main verify     # evening check of today's forecast
"""
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from . import alerts, history, page, skewt
from .config import SITE_DIR, load_settings, load_sites
from .fetch import fetch_site
from .scoring import evaluate_site, model_name

TZ = ZoneInfo("America/New_York")


def skewt_model(model_data, lead):
    """Pick which model's sounding to draw: HRRR for today/tomorrow, else GFS."""
    order = (["ncep_rrfs_conus", "gfs_hrrr", "gfs_global", "ecmwf_ifs025"] if lead <= 2
             else ["gfs_global", "ecmwf_ifs025", "icon_seamless", "gem_seamless"])
    for m in order:
        if m in model_data:
            return m
    return next(iter(model_data), None)


def run_forecast(fetch=fetch_site):
    settings = load_settings()
    sites = load_sites()
    now = datetime.now(TZ)
    today = now.date()
    run_id = now.astimezone(ZoneInfo("UTC")).strftime("%Y%m%dT%H%M")
    bias = history.load_bias()

    results, images = {}, {}
    img_dir = SITE_DIR / "skewt"
    img_dir.mkdir(parents=True, exist_ok=True)
    for site in sites:
        print(f"Fetching {site['name']} ...")
        try:
            data = fetch(site, settings["models"], settings["forecast_days"])
        except Exception as e:  # keep going with the other sites
            print(f"  failed: {e}")
            continue
        if not data:
            print("  no model data")
            continue
        print("  models:", ", ".join(sorted(data)))
        res = evaluate_site(site, data, settings, today, bias.get(site["id"]))
        results[site["id"]] = res
        for ds, e in res.items():
            m = skewt_model(data, e["lead"])
            r = e["models"].get(m)
            if not r:
                continue
            name = f"{site['id']}_{ds}.png"
            try:
                if skewt.draw(site, data[m], ds, settings, r, img_dir / name, model_name(m)):
                    images[(site["id"], ds)] = f"skewt/{name}"
            except Exception as ex:
                print(f"  skew-T failed for {ds}: {ex}")

    # Safety: if most sites failed (e.g. the weather data service is down or we
    # hit its daily limit), stop here so the last good page stays up.
    if len(results) < len(sites) / 2:
        raise SystemExit(f"Only {len(results)} of {len(sites)} sites fetched - keeping the old page")

    payload = {"run_id": run_id, "made_local": now.isoformat(timespec="minutes"),
               "results": results}
    # The page updates every hour, but only about two runs a day (>= 11 h apart)
    # go into the history. That keeps the history small and keeps the
    # "trending" alert meaning "still a GO after half a day or more".
    utc = now.astimezone(ZoneInfo("UTC"))
    saved = history.list_runs()
    stamp = lambda h: (utc - timedelta(hours=h)).strftime("%Y%m%dT%H%M")
    trend_n = settings["alerts"]["trend_runs"] - 1
    prev = [history.load_run(p) for p in reversed(saved) if p.stem <= stamp(6)][:max(trend_n, 1)]
    if not saved or saved[-1].stem <= stamp(11):
        history.save_run(run_id, payload)
        history.prune_runs()

    page.build(results, sites, settings, now.strftime("%a %b %d %Y, %I:%M %p"), images, SITE_DIR)
    print(f"Page built: {SITE_DIR / 'index.html'}")

    found = alerts.find_alerts(results, sites, prev, settings, evening=now.hour >= 18)
    alerts.send_alerts(found, settings)


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "forecast"
    if cmd == "forecast":
        run_forecast()
    elif cmd == "verify":
        from .verify import run_verify
        run_verify()
    elif cmd == "testemail":
        s = load_settings()
        ok = alerts.send_email(
            "Flying forecast: test email",
            f"<p>Email alerts are working. Forecast page: "
            f"<a href='{s['page_url']}'>{s['page_url']}</a></p>")
        sys.exit(0 if ok else 1)
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
