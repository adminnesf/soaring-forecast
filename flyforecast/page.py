"""Build the web page (site/index.html)."""
import html
import shutil
import statistics
from collections import defaultdict
from datetime import date

from .config import ROOT
from .history import REPORTS_CSV, VERIFY_CSV, read_csv
from .scoring import VERDICTS, compass, model_name, rank_key

COLORS = {"GO": "#2e9e44", "MAYBE": "#e8c21a", "WORK": "#f08a24",
          "HOME": "#9aa0a6", "NOLIFT": "#c7cbd1"}

CSS = """
body{font-family:-apple-system,Segoe UI,Arial,sans-serif;margin:0;background:#f6f7f9;color:#1d2329}
header{background:#14261D;color:#FDEBD3;padding:12px 18px;display:flex;align-items:center;gap:14px}
header img{width:64px;height:64px;flex:none}
header .ne{font-size:13px;letter-spacing:.32em;color:#8DB39C;font-weight:600}
header h1{margin:0;font-size:26px;font-weight:800;letter-spacing:.01em;line-height:1.05}
header p{margin:4px 0 0;font-size:12px;opacity:.8}
main{padding:12px 14px;max-width:1300px;margin:auto}
h2{font-size:18px;margin:22px 0 8px}
.scroll{overflow-x:auto;background:#fff;border-radius:8px;box-shadow:0 1px 3px #0002}
table{border-collapse:collapse;width:100%;font-size:13px}
th,td{padding:6px 7px;border-bottom:1px solid #e5e7eb;text-align:center;vertical-align:top}
th{background:#eef1f5;position:sticky;top:0}
td.site{text-align:left;white-space:nowrap;font-weight:600}
.cell{border-radius:6px;padding:5px 4px;color:#111;min-width:74px}
.num{font-size:17px;font-weight:700}
.small{font-size:11px;line-height:1.3}
.nofly{background:repeating-linear-gradient(45deg,#fff,#fff 6px,#fde2e2 6px,#fde2e2 12px)!important;color:#8b1a1a}
.cards{display:flex;flex-wrap:wrap;gap:10px}
.card{background:#fff;border-radius:8px;padding:10px 12px;box-shadow:0 1px 3px #0002;min-width:220px;border-left:6px solid #2e9e44}
.legend span{display:inline-block;padding:2px 8px;border-radius:4px;margin-right:6px;font-size:12px}
details{background:#fff;border-radius:8px;margin:8px 0;padding:8px 12px;box-shadow:0 1px 3px #0002}
summary{cursor:pointer;font-weight:600}
.day{display:flex;flex-wrap:wrap;gap:12px;margin:10px 0;border-top:1px solid #eee;padding-top:10px}
.day img{max-width:100%;width:480px;border:1px solid #ddd;border-radius:6px}
.flag{color:#8b1a1a}
.meter{height:8px;background:#e5e7eb;border-radius:4px;margin:4px auto 0;overflow:hidden}
.meter div{height:100%}
.toprow{display:flex;flex-wrap:wrap;gap:20px;align-items:flex-start}
.toprow>div:first-child{flex:1 1 420px}
.guide{flex:0 1 560px;background:#fff;border-radius:8px;box-shadow:0 1px 3px #0002;padding:12px 16px;font-size:13px}
.guide h3{margin:0 0 4px;font-size:15px}
.guide p{margin:0 0 8px;color:#374151}
.gbar{display:grid;grid-template-columns:5fr 2fr 3fr 4fr;border-radius:6px;overflow:hidden;font-size:12px;font-weight:700;color:#fff;text-align:center}
.gbar div{padding:5px 0}
.guide table{font-size:12.5px;margin-top:8px}
.guide td{text-align:left;padding:4px 6px;vertical-align:top}
.chip{display:inline-block;min-width:56px;text-align:center;color:#fff;border-radius:4px;padding:1px 6px;font-weight:700}
.rank{display:inline-block;background:#14261D;color:#FDEBD3;border-radius:10px;padding:0 7px;font-size:11px;margin-right:4px}
.bs{color:#fff;border-radius:4px;padding:0 5px;font-size:11px;font-weight:700;white-space:nowrap}
.tag{display:inline-block;background:#fff;border:1px solid #c62828;color:#8b1a1a;border-radius:10px;padding:0 6px;margin:2px 1px 0;font-size:11px;line-height:1.5;white-space:nowrap}
.faded{opacity:.55}
th.faded{opacity:.6;font-weight:600}
.rank.none{background:#9ca3af}
"""


def esc(x):
    return html.escape(str(x))


def agree_color(a):
    """0 = red, 100 = green, shades of orange/yellow between."""
    return f"hsl({round(1.2 * a)},75%,42%)"


def meter(a, wide=False):
    if a is None:
        return "<div class='small'>one model only</div>"
    w = "100%" if wide else "70px"
    return (f"<div class='meter' style='width:{w}' title='Models agree {a}%'>"
            f"<div style='width:{max(a, 4)}%;background:{agree_color(a)}'></div></div>"
            f"<div class='small'>models agree {a}%</div>")


def bs_badge(bs, settings):
    if bs is None:
        return ""
    t = settings.get("turbulence", {"turbulent": 5, "smooth": 7})
    if bs <= t["turbulent"]:
        col, word = "#c62828", "turbulent"
    elif bs < t["smooth"]:
        col, word = "#e08a00", "some shear"
    else:
        col, word = "#2e7d32", "smooth"
    return (f"<span class='bs' style='background:{col}'>B/S {bs:.0f}</span>"
            f"<span class='small'> {word}</span>")


def windy_link(site):
    return f"https://www.windy.com/{site['lat']:.3f}/{site['lon']:.3f}?{site['lat']:.3f},{site['lon']:.3f},11"


FADE_FROM_DAY = 4   # day index (0 = today) where forecasts start to fade: days 5-7


def short_tag(flag):
    """Turn a long flag into a short tag for the day box (full text stays in the details)."""
    f = flag.lower()
    if f.startswith("turbulent"):
        return None                       # the B/S chip already says it
    if f.startswith("no-fly"):
        return "No-fly wind"
    if "doesn't work here" in f:
        return "Wrong wind"
    if "only works here in light wind" in f:
        return "Light wind only"
    if f.startswith("over ") and "mph" in f:
        return "Too windy"
    if f.startswith("edge direction"):
        return "Edge direction"
    if f.startswith("rain"):
        return "Rain"
    if f.startswith("overdevelopment"):
        return "OD / storm risk"
    if "tbd" in f:
        return "Wind dir TBD"
    if f.startswith("no wind data"):
        return "No wind data"
    return flag                           # e.g. "Mt Tom's limit (5-8 mph)"


def _cell(entry, settings, fade=False):
    c = entry.get("consensus") if entry else None
    if not c:
        return "<td><span class='small'>no data</span></td>"
    v = c["verdict"]
    num = "-" if c["number"] is None else f"{c['number']:.2f}"
    cc = entry.get("consensus_corrected")
    corr = (f"<div class='small'>corrected {cc['number']:.2f}</div>"
            if cc and cc.get("number") is not None else "")
    wind = f"{compass(c['wind_dir'])} {c['wind_mph']:.0f} mph" if c["wind_mph"] is not None else "wind ?"
    tol = "" if c["number"] is None else f"<br>TOL {c['tol_ft_agl']:,} ft"
    cls = "cell" if c["flyable"] else "cell nofly"
    if fade:
        cls += " faded"
    tags = [t for t in (short_tag(f) for f in c["flags"]) if t]
    tags = "".join(f"<span class='tag'>{esc(t)}</span>" for t in dict.fromkeys(tags))
    return (f"<td><div class='{cls}' style='background:{COLORS[v]}33;border:2px solid {COLORS[v]}'>"
            f"<div class='num'>{num}</div><div class='small'>{esc(VERDICTS[v])}</div>"
            f"<div class='small'>{wind}{tol}</div>"
            f"<div>{bs_chip(c.get('bs'), settings)}</div>{corr}"
            f"{'<div>' + tags + '</div>' if tags else ''}"
            f"{meter(c.get('agreement'))}</div></td>")


def bs_chip(bs, settings):
    """B/S badge with a one-word label, kept on one line for the day boxes."""
    if bs is None:
        return ""
    t = settings.get("turbulence", {"turbulent": 5, "smooth": 7})
    if bs <= t["turbulent"]:
        col, word = "#c62828", "turbulent"
    elif bs < t["smooth"]:
        col, word = "#e08a00", "some shear"
    else:
        col, word = "#2e7d32", "smooth"
    return (f"<span class='bs' style='background:{col}' title='B/S {bs} - {word}'>B/S {bs:.0f} {word}</span>")


def _verification_table(sites):
    rows = read_csv(VERIFY_CSV)
    if not rows:
        return "<p>No checked days yet. The app compares each day's forecast with what happened every evening.</p>"
    by = defaultdict(lambda: defaultdict(list))
    for r in rows:
        try:
            if r["fc_number"] and r["an_number"]:
                by[r["site"]][f"lead{r['lead']}"].append(float(r["fc_number"]) - float(r["an_number"]))
            if r["fc_tmax_c"] and r["obs_tmax_c"]:
                by[r["site"]]["tmax"].append(float(r["fc_tmax_c"]) - float(r["obs_tmax_c"]))
        except ValueError:
            continue

    def fmt(xs):
        return f"{statistics.mean(xs):+.2f} (n={len(xs)})" if xs else "-"

    h = ("<div class='scroll'><table><tr><th>Site</th><th>Number error, 1 day out</th>"
         "<th>Number error, 3 days out</th><th>High temp error (C)</th></tr>")
    for s in sites:
        b = by.get(s["id"])
        if not b:
            continue
        h += (f"<tr><td class='site'>{esc(s['name'])}</td><td>{fmt(b['lead1'])}</td>"
              f"<td>{fmt(b['lead3'])}</td><td>{fmt(b['tmax'])}</td></tr>")
    h += "</table></div><p class='small'>+ means the forecast ran high. Number error compares the forecast with the model's same-day analysis; temperature error uses the nearby weather station.</p>"
    return h


def _reports_table():
    rows = read_csv(REPORTS_CSV)[-15:]
    if not rows:
        return "<p>No flight reports yet. Use the \"How was it?\" link in alert emails after you fly.</p>"
    h = "<div class='scroll'><table><tr><th>Date</th><th>Site</th><th>Flew</th><th>Top of lift</th><th>Conditions</th><th>Notes</th></tr>"
    for r in reversed(rows):
        h += "".join(["<tr>"] + [f"<td>{esc(r.get(k, ''))}</td>" for k in
                                 ("date", "site", "flew", "tol_ft", "conditions", "notes")] + ["</tr>"])
    return h + "</table></div>"


BS_GUIDE = """<div class='guide'>
<h3>Turbulence: the B/S number (buoyancy / shear)</h3>
<p>Compares how strong the thermals are with how much the wind changes as you climb.
Strong thermals in light, even wind = high number = smooth climbs. Wind that's
stronger or swings direction up high tears thermals apart = low number = rough air.</p>
<div class='gbar'><div style='background:#c62828'>0-5</div><div style='background:#e08a00'>5-7</div>
<div style='background:#7cb342'>7-10</div><div style='background:#2e7d32'>10+</div></div>
<table>
<tr><td><span class='chip' style='background:#c62828'>0-5</span></td><td><b>Turbulent.</b> Thermals get broken up - punchy, chopped-up lift that's hard to core. Be ready for a rough ride or stay on the ground.</td></tr>
<tr><td><span class='chip' style='background:#e08a00'>5-7</span></td><td><b>Some shear.</b> Workable, but thermals lean with the wind and come apart up high. Expect bumps.</td></tr>
<tr><td><span class='chip' style='background:#7cb342'>7-10</span></td><td><b>Good.</b> Thermals hold together and are easy to stay in.</td></tr>
<tr><td><span class='chip' style='background:#2e7d32'>10+</span></td><td><b>Smooth.</b> Well-formed, round thermals. The kind of day you want.</td></tr>
</table>
</div>"""


GUIDE_CSS = """
body{font-family:-apple-system,Segoe UI,Arial,sans-serif;margin:0;background:#f6f7f9;color:#1d2329;font-size:15px;line-height:1.45}
header{background:#14261D;color:#FDEBD3;padding:12px 18px;display:flex;align-items:center;gap:14px}
header img{width:56px;height:56px} header h1{margin:0;font-size:24px}
header a{margin-left:auto;color:#FDEBD3;border:1px solid #FDEBD3;border-radius:6px;padding:6px 12px;text-decoration:none;font-size:14px}
main{max-width:860px;margin:auto;padding:8px 18px 40px}
section{background:#fff;border-radius:10px;box-shadow:0 1px 3px #0002;padding:16px 20px;margin:16px 0}
h2{margin:0 0 10px;font-size:19px}
p{margin:0 0 8px}
.ex{display:flex;flex-wrap:wrap;gap:24px;align-items:flex-start}
.box{width:170px;border-radius:8px;padding:8px;text-align:center;background:#2e9e4433;border:2px solid #2e9e44;font-size:13px}
.box div{position:relative;padding:2px 0}
.n{display:inline-block;width:20px;height:20px;border-radius:50%;background:#14261D;color:#fff;font-size:12px;font-weight:700;line-height:20px;text-align:center;margin-right:6px;flex:none}
.box .n{position:absolute;left:-30px;top:2px}
.list{flex:1 1 360px;list-style:none;margin:0;padding:0}
.list li{display:flex;margin:0 0 9px}
.row{display:flex;align-items:center;gap:10px;margin:6px 0}
.sw{min-width:92px;text-align:center;border-radius:5px;padding:3px 8px;font-weight:700;font-size:13px}
.meter{height:9px;width:120px;background:#e5e7eb;border-radius:5px;overflow:hidden;flex:none}
.meter div{height:100%}
.gbar{display:grid;grid-template-columns:5fr 2fr 3fr 4fr;border-radius:6px;overflow:hidden;font-size:12px;font-weight:700;color:#fff;text-align:center;margin:6px 0 4px}
.gbar div{padding:5px 0}
.stripe{background:repeating-linear-gradient(45deg,#fff,#fff 6px,#fde2e2 6px,#fde2e2 12px);border:2px solid #9aa0a6}
"""


def build_guide(settings, out_dir):
    r = settings["lapse_ratings"]
    w = settings["wind"]
    page = f"""<!doctype html><html lang='en'><head><meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>How to read the New England Flying Forecast</title>
<link rel='icon' type='image/svg+xml' href='icon.svg'><style>{GUIDE_CSS}</style></head><body>
<header><img src='logo.svg' alt=''><h1>How to read this forecast</h1><a href='index.html'>Back to forecast</a></header>
<main>

<section><h2>One day box</h2>
<p>Every site gets one box per day. Here's what each line means.</p>
<div class='ex'>
<div class='box' style='margin-left:30px'>
<div style='font-size:20px;font-weight:700'><span class='n'>1</span>2.95</div>
<div><span class='n'>2</span>Leave work - go fly</div>
<div><span class='n'>3</span>NW 6 mph</div>
<div><span class='n'>4</span>TOL 6,200 ft</div>
<div><span class='n'>5</span><span style='background:#2e7d32;color:#fff;border-radius:4px;padding:0 5px;font-weight:700'>B/S 11</span> smooth</div>
<div style='color:#8b1a1a;font-size:12px'><span class='n'>6</span>Overdevelopment risk</div>
<div><span class='n'>7</span><div class='meter' style='margin:4px auto 0'><div style='width:85%;background:hsl(102,75%,42%)'></div></div>models agree 85%</div>
</div>
<ol class='list'>
<li><span class='n'>1</span><span><b>Lapse rate</b> - how fast the air cools as you climb. Higher = stronger thermals.</span></li>
<li><span class='n'>2</span><span><b>The call</b> - what that number means (see the scale below).</span></li>
<li><span class='n'>3</span><span><b>Wind at launch height</b> - direction it comes from and speed in mph, late morning to afternoon.</span></li>
<li><span class='n'>4</span><span><b>Top of lift</b> - how high thermals should take you, in feet above the valley.</span></li>
<li><span class='n'>5</span><span><b>Turbulence (B/S)</b> - green is smooth, red is rough (see below).</span></li>
<li><span class='n'>6</span><span><b>Warnings</b> in red - wrong wind direction, too windy, rain, storms.</span></li>
<li><span class='n'>7</span><span><b>Models agree</b> - how much the weather models agree. Green = confident, red = unsure.</span></li>
</ol></div></section>

<section><h2>Lapse rate</h2>
<p>(ground temp - temp at top of lift) / top of lift in thousands of feet.</p>
<div class='row'><span class='sw' style='background:#2e9e4455'>{r['go']} +</span><span>Leave work - go fly <i style='color:#6b7280'>(Call in to work and tell them your grandmother died. Again.)</i></span></div>
<div class='row'><span class='sw' style='background:#e8c21a55'>{r['maybe']} - {r['go']}</span>Pretty good - could still be a very good day</div>
<div class='row'><span class='sw' style='background:#f08a2455'>{r['stay_at_work']} - {r['maybe']}</span>Stay at work</div>
<div class='row'><span class='sw' style='background:#9aa0a655'>under {r['stay_at_work']}</span>Stay home</div>
<div class='row'><span class='sw' style='background:#c7cbd155'>-</span>No usable lift</div>
</section>

<section><h2>Turbulence: the B/S number</h2>
<p>Compares how strong the thermals are with how much the wind changes as you climb.
Strong thermals in light, even wind = high number = smooth. Wind that tears thermals apart = low number = rough.</p>
<div class='gbar'><div style='background:#c62828'>0-5</div><div style='background:#e08a00'>5-7</div>
<div style='background:#7cb342'>7-10</div><div style='background:#2e7d32'>10+</div></div>
<div class='row'><span class='sw' style='background:#c62828;color:#fff'>0-5</span><span><b>Turbulent.</b> Broken, punchy lift that's hard to stay in.</span></div>
<div class='row'><span class='sw' style='background:#e08a00;color:#fff'>5-7</span><span><b>Some shear.</b> Workable but bumpy.</span></div>
<div class='row'><span class='sw' style='background:#7cb342;color:#fff'>7-10</span><span><b>Good.</b> Thermals hold together.</span></div>
<div class='row'><span class='sw' style='background:#2e7d32;color:#fff'>10+</span><span><b>Smooth.</b> Round, easy thermals.</span></div>
</section>

<section><h2>Models agree</h2>
<p>The app checks six weather models. When they all tell the same story, trust the forecast more.</p>
<div class='row'><div class='meter'><div style='width:90%;background:hsl(108,75%,42%)'></div></div>Green - models agree</div>
<div class='row'><div class='meter'><div style='width:55%;background:hsl(66,75%,42%)'></div></div>Yellow - some disagreement</div>
<div class='row'><div class='meter'><div style='width:20%;background:hsl(24,75%,42%)'></div></div>Red - models disagree, low confidence</div>
</section>

<section><h2>Wind at launch</h2>
<div class='row'><span class='sw' style='background:#e5e7eb'>0-{w['light_mph']} mph</span>Light</div>
<div class='row'><span class='sw' style='background:#2e9e4433'>{w['light_mph']}-{w['strong_mph']} mph</span>Good</div>
<div class='row'><span class='sw' style='background:#e8c21a55'>{w['strong_mph']}-{w['max_mph']} mph</span>Strong - flagged</div>
<div class='row'><span class='sw' style='background:#c6282833'>over {w['max_mph']} mph</span>Too windy</div>
<p style='margin-top:8px'>Each site also has its own good wind directions. Mt Tom has a lower limit (5-8 mph) because of the cliff.</p>
</section>

<section><h2>Striped boxes and site order</h2>
<div class='row'><span class='sw stripe' style='min-width:92px'>&nbsp;</span>Striped = not flyable that day (wind or rain). Still shown so you can go check.</div>
<p style='margin-top:8px'>Sites are sorted best to worst: sites with a flyable day this week come first, then by lapse rate. <b>#1</b> is the top pick. A gray number means that site has no flyable day this week.</p>
<p>Small red tags in a box say why a day fails, e.g. <i>Wrong wind</i>, <i>Too windy</i>, <i>Rain</i>. Open the site's details for the full story.</p>
<p>Days 5-7 are shown lighter: forecasts that far out are much less reliable. The numbers are calculated the same way.</p>
</section>

</main></body></html>"""
    (out_dir / "guide.html").write_text(page)


def site_order(sites, results):
    """Best site first: its best flyable day this week, then its best number."""
    def key(s):
        days = results.get(s["id"], {})
        best = max((rank_key(e.get("consensus")) for e in days.values()), default=-99)
        return -best
    return sorted(sites, key=key)


def build(results, sites, settings, run_label, images, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    dates = sorted({ds for days in results.values() for ds in days})
    names = {s["id"]: s for s in sites}

    # best bets
    picks = []
    for sid, days in results.items():
        for ds, e in days.items():
            c = e.get("consensus")
            if c and c["flyable"] and c["verdict"] in ("GO", "MAYBE"):
                picks.append((rank_key(c), ds, sid, c))
    picks.sort(key=lambda x: (-x[0], x[1]))
    cards = ""
    for _, ds, sid, c in picks[:6]:
        d = date.fromisoformat(ds)
        cards += (f"<div class='card' style='border-left-color:{COLORS[c['verdict']]}'>"
                  f"<b>{d:%a %b %d}</b> - {esc(names[sid]['name'])}<br>"
                  f"<span class='num'>{c['number']:.2f}</span> {esc(VERDICTS[c['verdict']])}<br>"
                  f"<span class='small'>Top of lift {c['tol_ft_agl']:,} ft AGL - "
                  f"{compass(c['wind_dir'])} {c['wind_mph']:.0f} mph at launch</span><br>"
                  f"{bs_badge(c.get('bs'), settings)}{meter(c.get('agreement'), wide=True)}</div>")
    if not cards:
        cards = "<p>Nothing flyable in the next week by your numbers. Keep the faith.</p>"

    # main grid
    def day_head(i, ds):
        d = date.fromisoformat(ds)
        top = "Today" if i == 0 else "Tomorrow" if i == 1 else f"{d:%a}"
        if i >= FADE_FROM_DAY:
            return f"<th class='faded'>{top}<br>{d:%b %d}<div class='small'>less reliable</div></th>"
        return f"<th>{top}<br>{d:%b %d}</th>"
    head = "<tr><th>Site</th>" + "".join(day_head(i, ds) for i, ds in enumerate(dates)) + "</tr>"
    body = ""
    for n, s in enumerate(site_order(sites, results), 1):
        days = results.get(s["id"], {})
        live = any((e.get("consensus") or {}).get("flyable") for e in days.values())
        rank_cls = "rank" if live else "rank none"
        body += (f"<tr><td class='site'><span class='{rank_cls}'>#{n}</span><a href='#{s['id']}'>{esc(s['name'])}</a>"
                 f"<div class='small'>{s['state']}</div></td>")
        body += "".join(_cell(days.get(ds), settings, fade=i >= FADE_FROM_DAY)
                        for i, ds in enumerate(dates)) + "</tr>"

    # per-site detail
    detail = ""
    for s in sites:
        days = results.get(s["id"], {})
        win = ", ".join(f"{w['from']}-{w['to']}{' (light only)' if w.get('light_only') else ''}"
                        for w in s["windows"]) or "TBD"
        detail += (f"<details id='{s['id']}'><summary>{esc(s['name'])} ({s['state']}) - launch "
                   f"{s['launch_ft']:,} ft, ground {s['ground_ft']:,} ft</summary>"
                   f"<p class='small'>Works in: {win}{'' if win == 'TBD' else ' deg'}. {esc(s['notes'])}"
                   f"{'' if s['ushpa'] else ' Not a USHPA site.'} "
                   f"<a href='{windy_link(s)}' target=_blank>Open in Windy</a></p>")
        for ds in dates:
            e = days.get(ds)
            if not e:
                continue
            img = images.get((s["id"], ds))
            rows = ""
            for m, r in sorted(e["models"].items()):
                if not r:
                    rows += f"<tr><td>{model_name(m)}</td><td colspan=7>no data</td></tr>"
                    continue
                cr = (e.get("corrected") or {}).get(m)
                corr = f" / {cr['number']:.2f}" if cr and cr.get("number") is not None else ""
                hours = " ".join(f"{h}:{'-' if v is None else f'{v:.1f}'}" for h, v in r["by_hour"].items())
                num = "-" if r["number"] is None else f"{r['number']:.2f}"
                bs = "-" if r.get("bs") is None else f"{r['bs']:.0f}"
                fpm = "-" if r.get("thermal_fpm") is None else f"{r['thermal_fpm']}"
                rows += (f"<tr><td>{model_name(m)}</td><td><b>{num}</b>{corr}</td><td>{r['tol_ft_agl']:,}</td>"
                         f"<td>{bs} / {fpm}</td>"
                         f"<td>{r['tmax_c']}</td><td>{compass(r['wind_dir'])} {r['wind_mph']} (max {r['wind_max_mph']})</td>"
                         f"<td>{r['rain_in']}\"</td><td class='small'>{hours}</td></tr>")
            cdet = e.get("consensus") or {}
            detail += (f"<div class='day'><div>{'<img loading=lazy src=' + img + '>' if img else ''}"
                       f"<div style='max-width:480px'>{meter(cdet.get('agreement'), wide=True)}</div></div>"
                       f"<div style='flex:1;min-width:300px'><b>{date.fromisoformat(ds):%A %b %d}</b>"
                       f" <span class='small'>(number from the {e.get('lapse_hour', '?')}:00 sounding)</span>"
                       f"<div class='scroll'><table><tr><th>Model</th><th>Number (raw / corrected)</th>"
                       f"<th>TOL ft AGL</th><th>B/S / thermal ft/min</th><th>High C</th><th>Wind at launch mph</th><th>Rain</th>"
                       f"<th>Number by hour</th></tr>{rows}</table></div></div></div>")
        detail += "</details>"

    legend = "".join(f"<span style='background:{COLORS[k]}55'>{esc(VERDICTS[k])}</span>"
                     for k in ("GO", "MAYBE", "WORK", "HOME"))
    r = settings["lapse_ratings"]
    page = f"""<!doctype html><html><head><meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>New England Flying Forecast</title>
<link rel='icon' type='image/svg+xml' href='icon.svg'>
<link rel='apple-touch-icon' href='apple-touch-icon.png'>
<link rel='manifest' href='manifest.webmanifest'>
<meta name='theme-color' content='#14261D'>
<style>{CSS}</style></head><body>
<header><img src='logo.svg' alt=''><div><div class='ne'>NEW ENGLAND</div><h1>FLYING FORECAST</h1>
<p>Updated {esc(run_label)} - NH, VT, MA</p></div>
<a href='guide.html' style='margin-left:auto;color:#FDEBD3;border:1px solid #FDEBD3;border-radius:6px;padding:6px 12px;text-decoration:none;font-size:14px'>How to read this</a></header>
<main>
<p class='legend'>{legend} <span class='small'>{r['go']}+ go fly, {r['maybe']}-{r['go']} pretty good,
{r['stay_at_work']}-{r['maybe']} stay at work, under {r['stay_at_work']} stay home. Striped = not flyable (wind/rain), still shown so you can go check.</span></p>
<p class='small'>Sites are sorted best to worst: sites with a flyable day come first, then by lapse rate. A gray <span class='rank none'>#</span> means no flyable day this week. <a href='guide.html'><b>How to read this forecast</b></a></p>
<h2>Best bets</h2><div class='cards'>{cards}</div>
<h2>All sites</h2><div class='scroll'><table>{head}{body}</table></div>
<h2>Site details and skew-Ts</h2>{detail}
<h2>How the forecasts have done</h2>{_verification_table(sites)}
<h2>Your flight reports</h2>{_reports_table()}
<p class='small'>Data: Open-Meteo (RRFS, HRRR, GFS, ECMWF, ICON, GEM). Thermal strength is estimated from sunshine and top of lift. Wind is the model wind interpolated to launch height,
averaged over the flying hours. Always make the call on launch.</p>
</main>
<script>
function openSite(){{var id=location.hash.slice(1);var d=id&&document.getElementById(id);
if(d&&d.tagName==='DETAILS'){{d.open=true;d.scrollIntoView();}}}}
window.addEventListener('hashchange',openSite);openSite();
</script></body></html>"""
    (out_dir / "index.html").write_text(page)
    (out_dir / ".nojekyll").write_text("")
    build_guide(settings, out_dir)
    static = ROOT / "static"
    if static.exists():
        for f in static.iterdir():
            shutil.copy(f, out_dir / f.name)
