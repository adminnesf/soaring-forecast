"""Draw a skew-T style chart (height in feet) for one site / day."""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from .scoring import compass, hours_by_date, site_hours  # noqa: E402
from .sounding import FT_PER_M, profile, top_of_lift  # noqa: E402

SKEW = 2.0  # degrees C of lean per 1000 ft


def _x(t, z_ft):
    return t + SKEW * z_ft / 1000.0


def draw(site, d, ds, settings, result, path, model_name):
    hrs = site_hours(site, settings, ds)
    idx = hours_by_date(d["time"]).get(ds, {})
    if hrs["heating_hour"] not in idx:
        return False
    g = site["ground_m"]
    prof_h = profile(d, idx[hrs["heating_hour"]], g)
    prof_l = profile(d, idx.get(hrs["lapse_hour"], idx[hrs["heating_hour"]]), g)
    if len(prof_h) < 3:
        return False

    top_ft = 14000
    fig, ax = plt.subplots(figsize=(6.4, 6.4), dpi=80)

    # background: isotherms and dry adiabats
    zs = list(range(0, top_ft + 1, 500))
    for t in range(-60, 50, 5):
        ax.plot([_x(t, z) for z in zs], zs, color="#dddddd", lw=0.6, zorder=0)
    for t0 in range(-20, 60, 5):
        ax.plot([_x(t0 - 3.0 * z / 1000, z) for z in zs], zs, color="#f3d9b1",
                lw=0.6, zorder=0)

    def line(prof, key, **kw):
        pts = [(q[key], q["z"] * FT_PER_M) for q in prof if q[key] is not None]
        ax.plot([_x(t, z) for t, z in pts], [z for _, z in pts], **kw)

    line(prof_l, "t", color="#d62728", lw=1.4, ls="--",
         label=f"Temp {hrs['lapse_hour']}:00")
    line(prof_h, "t", color="#d62728", lw=2.2, label=f"Temp {hrs['heating_hour']}:00")
    line(prof_h, "td", color="#2ca02c", lw=1.8, label="Dew point")

    # thermal (parcel) from forecast high
    tmax = result["tmax_c"]
    td = d["dew_point_2m"][idx[hrs["heating_hour"]]]
    tol_m, cb_m = top_of_lift(prof_h, g, tmax, td)
    g_ft = g * FT_PER_M
    if tol_m:
        tol_ft = tol_m * FT_PER_M
        pz = [g_ft + i * 100 for i in range(int((tol_ft - g_ft) / 100) + 1)]
        ax.plot([_x(tmax - 3.0 * (z - g_ft) / 1000, z) for z in pz], pz,
                color="#ff7f0e", lw=1.6, label="Thermal from forecast high")
        ax.axhline(tol_ft, color="#1f77b4", lw=1.2, ls=":")
        ax.text(0.02, tol_ft + 120, f"Top of lift {tol_ft:,.0f} ft MSL "
                f"({tol_ft - g_ft:,.0f} AGL)", transform=ax.get_yaxis_transform(),
                color="#1f77b4", fontsize=8)

    ax.axhline(site["launch_ft"], color="#555555", lw=0.8)
    ax.text(0.02, site["launch_ft"] + 120, f"Launch {site['launch_ft']:,} ft",
            transform=ax.get_yaxis_transform(), fontsize=8, color="#555555")
    ax.axhline(g_ft, color="#8c564b", lw=0.8)
    ax.text(0.02, g_ft + 120, f"Ground {site['ground_ft']:,} ft",
            transform=ax.get_yaxis_transform(), fontsize=8, color="#8c564b")

    # winds by height (heating hour)
    for q in prof_h:
        z_ft = q["z"] * FT_PER_M
        if q["ws"] is None or z_ft > top_ft:
            continue
        ax.text(1.01, z_ft, f"{compass(q['wd'])} {q['ws']:.0f}",
                transform=ax.get_yaxis_transform(), fontsize=7, va="center")

    num = result["number"]
    ax.set_title(f"{site['name']}  {ds}  ({model_name})\n"
                 f"Lapse rate at {hrs['lapse_hour']}:00: "
                 f"{'n/a' if num is None else f'{num:.2f}'}", fontsize=10)
    ax.set_ylim(0, top_ft)
    ax.set_xlim(-25, 55)
    ax.set_ylabel("Feet MSL")
    ax.set_xlabel("Temperature C (skewed)   |   wind mph at right")
    ax.legend(loc="lower right", fontsize=7)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return True
