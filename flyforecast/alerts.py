"""Email alerts when a good day is shaping up."""
import os
import smtplib
import ssl
import urllib.parse
from email.message import EmailMessage

from .history import alerts_sent, mark_alert
from .scoring import VERDICTS, compass


def _good(c):
    return bool(c) and c["verdict"] == "GO" and c["flyable"]


def find_alerts(results, sites, prev_runs, settings, evening):
    """Return a list of (key, kind, site, date, consensus) to send."""
    a = settings["alerts"]
    sent = alerts_sent()
    names = {s["id"]: s for s in sites}
    out = []
    for sid, days in results.items():
        for ds, entry in days.items():
            c = entry["consensus"]
            if not _good(c):
                continue
            lead = entry["lead"]
            if a["lead_min_days"] <= lead <= a["lead_max_days"]:
                key = f"trend:{sid}:{ds}"
                held = [r.get("results", {}).get(sid, {}).get(ds, {}).get("consensus")
                        for r in prev_runs[: a["trend_runs"] - 1]]
                if (key not in sent and len(held) >= a["trend_runs"] - 1
                        and all(_good(h) for h in held)):
                    out.append((key, "trend", names[sid], ds, entry))
            if a.get("night_before") and evening and lead == 1:
                key = f"night:{sid}:{ds}"
                if key not in sent:
                    out.append((key, "night", names[sid], ds, entry))
    return out


def report_link(settings, site, ds):
    q = urllib.parse.urlencode({
        "template": "flight-report.yml",
        "title": f"Flight report {ds} {site['name']}",
        "date": ds,
        "site": site["name"],
    })
    return f"https://github.com/{settings['repo']}/issues/new?{q}"


def build_email(alerts, settings):
    trend = [x for x in alerts if x[1] == "trend"]
    night = [x for x in alerts if x[1] == "night"]
    if night:
        subject = "Flying tomorrow: " + ", ".join(sorted({x[2]['name'] for x in night}))
        if trend:
            subject += f" (+{len(trend)} more shaping up)"
    else:
        days = sorted({x[3] for x in trend})
        subject = "Good flying day shaping up: " + ", ".join(days)

    def rows(items):
        h = ""
        for _, _, site, ds, entry in sorted(items, key=lambda x: (x[3], -(x[4]["consensus"]["number"] or 0))):
            c = entry["consensus"]
            cc = entry.get("consensus_corrected")
            corr = f" (corrected {cc['number']:.2f})" if cc and cc.get("number") is not None else ""
            flags = "; ".join(c["flags"]) or "none"
            a = c.get("agreement")
            agree = "-" if a is None else (f"<span style='color:hsl({round(1.2 * a)},75%,35%);"
                                           f"font-weight:bold'>{a}%</span>")
            bs = "-" if c.get("bs") is None else f"{c['bs']:.0f}"
            h += (f"<tr><td><b>{ds}</b></td><td>{site['name']}</td>"
                  f"<td><b>{c['number']:.2f}</b>{corr}</td>"
                  f"<td>{c['tol_ft_agl']:,} ft AGL</td>"
                  f"<td>{compass(c['wind_dir'])} {c['wind_mph']:.0f} mph</td>"
                  f"<td>{bs}</td><td>{agree}</td><td>{flags}</td>"
                  f"<td><a href='{report_link(settings, site, ds)}'>How was it?</a></td></tr>")
        return h

    head = ("<tr><th>Day</th><th>Site</th><th>Lapse rate</th><th>Top of lift</th>"
            "<th>Wind at launch</th><th>B/S (turbulence)</th><th>Models agree</th><th>Flags</th><th>After you fly</th></tr>")
    body = "<div style='font-family:Arial,sans-serif'>"
    if night:
        body += "<h2>Still looks good for tomorrow</h2><table border=1 cellpadding=4 cellspacing=0>" + head + rows(night) + "</table>"
    if trend:
        body += ("<h2>Good day shaping up (holding across model runs)</h2>"
                 "<table border=1 cellpadding=4 cellspacing=0>" + head + rows(trend) + "</table>")
    body += (f"<p>Full forecast and skew-Ts: <a href='{settings['page_url']}'>{settings['page_url']}</a></p>"
             f"<p>{VERDICTS['GO']} = 2.8 and up. Wind is at launch height.</p></div>")
    return subject, body


def send_email(subject, html):
    user = os.environ.get("GMAIL_ADDRESS")
    pw = os.environ.get("GMAIL_APP_PASSWORD")
    to = os.environ.get("ALERT_TO") or user
    if not user or not pw:
        print("Email not set up (GMAIL_ADDRESS / GMAIL_APP_PASSWORD missing); would have sent:", subject)
        return False
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to
    msg.set_content("This email needs an HTML-capable mail reader.")
    msg.add_alternative(html, subtype="html")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context()) as s:
        s.login(user, pw.replace(" ", ""))
        s.send_message(msg)
    print("Sent email:", subject)
    return True


def send_alerts(alerts, settings):
    if not alerts:
        print("No alerts this run.")
        return
    subject, html = build_email(alerts, settings)
    if send_email(subject, html):
        for key, *_ in alerts:
            mark_alert(key)
