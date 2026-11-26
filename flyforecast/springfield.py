"""Experimental sailplane dashboard. No operational go/no-go rating."""
import json, math, statistics, html
from datetime import datetime
from zoneinfo import ZoneInfo
from .config import load_sites, load_settings, SITE_DIR
from .fetch import fetch_site
from .sounding import profile, top_of_lift, wstar_ms, FT_PER_M, _val
from .history import save_run

def hourly(site,d,i):
    g=site['ground_m']; p=profile(d,i,g)
    if len(p)<3: return None
    t=p[0]['t']; td=p[0]['td']; sun=_val(d,'shortwave_radiation',i)
    # Small parcel excess is an uncalibrated sensitivity assumption.
    top,cb=top_of_lift(p,g,t+0.5,td)
    if td is not None and td>=t: cb=g; top=g
    depth=max(0,top-g)
    if sun is not None and sun<=0: depth=0
    # Profile ending before neutral buoyancy is not a measured ceiling.
    capped=top>=p[-1]['z']-10
    height=None if capped or sun is None else round(depth*FT_PER_M)
    w=wstar_ms(sun,depth,t) if height is not None and depth>0 else (0 if height==0 else None)
    speed=p[0]['ws']; direction=p[0]['wd']
    cross={str(h):round(abs(speed/1.15078*math.sin(math.radians(direction-h))),1) for h in (35,99)} if speed is not None and direction is not None else {}
    return dict(time=d['time'][i],lift_agl=height,lift_msl=None if height is None else round(height+site['ground_ft']),lcl_msl=None if cb is None else round(cb*FT_PER_M),wstar_kt=None if w is None else round(w*1.94384,2),wstar_fpm=None if w is None else round(w*196.85),wind_kt=None if speed is None else round(speed/1.15078,1),wind_dir=direction,crosswind=cross,rain_in=_val(d,'precipitation',i),cape=_val(d,'cape',i),profile=p)

def build(fetch=fetch_site, output=SITE_DIR, archive=True):
    site=load_sites("springfield.yaml")[0]; settings=load_settings(); data=fetch(site,settings['models'],7)
    if not data: raise RuntimeError('No weather data; previous page preserved')
    models={m:[r for i in range(len(d['time'])) if (r:=hourly(site,d,i)) is not None] for m,d in data.items()}
    models={m:r for m,r in models.items() if r}
    if not models: raise RuntimeError('No usable profiles; previous page preserved')
    now=datetime.now(ZoneInfo('UTC')); payload=dict(generated=now.isoformat(),requested=settings['models'],models=models)
    output.mkdir(parents=True,exist_ok=True)
    (output/'forecast.json').write_text(json.dumps(payload,allow_nan=False))
    (output/'index.html').write_text(PAGE)
    if archive: save_run(now.strftime('%Y%m%dT%H%M'),payload)
    return payload

PAGE = '''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Springfield Soaring Forecast</title>
<style>
:root{color-scheme:light;--ink:#142e39;--muted:#48616a;--line:#dce7e8;--teal:#12665c;--paper:#f3f7f6}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.5 system-ui,sans-serif}a{color:var(--teal)}
.hero{background:radial-gradient(ellipse at 88% 0%,#23776d 0%,transparent 58%),linear-gradient(115deg,#12313f,#144a4f);color:#fff;padding:clamp(32px,7vw,88px) 20px 56px}.wrap{max-width:1120px;margin:auto}.location{color:#b8e8dc;font-weight:700;letter-spacing:.09em;text-transform:uppercase;font-size:.78rem;margin:0 0 14px}.hero h1{font-size:clamp(2.5rem,6.5vw,5rem);line-height:1.02;letter-spacing:-.06em;margin:0;max-width:850px}.hero .updated{color:#d4edeb;margin:18px 0 0;font-size:.9rem}
main.wrap{padding:0 20px 30px;margin-top:-25px}.panel{background:#fff;border:1px solid var(--line);border-radius:18px;box-shadow:0 8px 30px #16373d0a}.controls{padding:18px;display:grid;grid-template-columns:1fr 1fr;gap:14px}.controls label{font-size:.82rem;font-weight:700;color:var(--muted);min-width:0}select{display:block;width:100%;margin-top:5px;padding:10px 12px;border:1px solid #a9bec0;border-radius:9px;background:#f8fbfa;color:var(--ink);font:inherit;font-size:1rem}select:focus-visible,.scroll:focus-visible{outline:3px solid #168377;outline-offset:3px}
.notice{font-size:.87rem;color:#4a4735;background:#fff9e9;border:1px solid #ecdfba;border-radius:10px;padding:11px 14px;margin:16px 0}.models{color:var(--muted);font-size:.87rem;margin:12px 0 18px;overflow-wrap:anywhere}.models summary{cursor:pointer;width:fit-content}.models p{margin:6px 0}
.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:18px}.metric{padding:15px 17px;border-top:3px solid #49a597}.metric span{display:block;color:var(--muted);font-size:.82rem;font-weight:650}.metric strong{font-size:clamp(1.2rem,3vw,1.9rem);letter-spacing:-.05em;font-variant-numeric:tabular-nums}
.table-head{padding:16px 18px 12px}.table-head h2{margin:0;font-size:1.25rem}.scroll{overflow:auto;max-height:590px;border-radius:0 0 18px 18px}table{width:100%;min-width:780px;border-spacing:0;font-variant-numeric:tabular-nums}th,td{text-align:left;padding:11px 13px;white-space:nowrap;border-bottom:1px solid #e6eeed}th{position:sticky;top:0;z-index:2;background:#e8f2f0;color:#254b4c;font-size:.78rem}td{font-size:.9rem;background:#fff}tr:nth-child(even) td{background:#f6faf9}td:first-child,th:first-child{position:sticky;left:0;font-weight:700;box-shadow:1px 0 var(--line)}td:first-child{z-index:1}th:first-child{z-index:3}footer{color:var(--muted);font-size:.82rem;margin:20px 0 0}
@media(max-width:560px){main.wrap{padding-inline:12px}.controls{padding:13px;gap:9px}.metrics{gap:6px}.metric{padding:9px 8px}.metric span{font-size:.72rem}.table-head{padding:13px}.hero{padding-inline:16px}.scroll{max-height:65vh}}
</style>
</head>
<body>
<header class="hero"><div class="wrap">
<p class="location">KVSF · Hartness State Airport</p>
<h1>Springfield Soaring Forecast</h1>
<p class="updated" id="status" role="status">Loading forecast…</p>
</div></header>
<main class="wrap">
<div class="controls panel"><label>Forecast day<select id="day" disabled></select></label><label>Weather model<select id="model" disabled></select></label></div>
<p class="notice">Experimental v0.2 · Research estimates only. Use an aviation weather briefing for flight decisions. W* is a convective velocity scale. LCL is an estimate. Ridge and wave forecasts are unavailable.</p>
<details class="models" id="coverage" hidden><summary id="coverage-label">Model coverage</summary><p id="coverage-detail"></p></details>
<div class="metrics" aria-label="Selected forecast day summary">
<div class="metric panel"><span>Peak lift height AGL</span><strong id="lift">—</strong></div>
<div class="metric panel"><span>Peak W*</span><strong id="thermal">—</strong></div>
<div class="metric panel"><span>Peak surface wind</span><strong id="wind">—</strong></div>
</div>
<section class="panel" aria-labelledby="hourly-title">
<div class="table-head"><h2 id="hourly-title">Hourly forecast</h2></div>
<div class="scroll" tabindex="0" role="region" aria-label="Scrollable hourly forecast table">
<table><thead><tr><th scope="col">Local time</th><th scope="col">Lift AGL / MSL ft</th><th scope="col">LCL MSL ft</th><th scope="col">W* kt / fpm</th><th scope="col">Wind kt / true°</th><th scope="col">Crosswind 05/11 kt</th><th scope="col">Rain in</th><th scope="col">CAPE</th></tr></thead><tbody id="rows"></tbody></table>
</div></section>
<footer>Weather data from <a href="https://open-meteo.com/">Open-Meteo</a>. Adapted from <a href="https://github.com/tacoleman69/Newengland-flying-forecast">New England Flying Forecast</a>.</footer>
</main>
<script>
const byId = id => document.getElementById(id);
const day = byId('day');
const model = byId('model');
const dayFormat = new Intl.DateTimeFormat('en-US', { weekday: 'short', month: 'short', day: 'numeric', timeZone: 'UTC' });
const runFormat = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', timeZoneName: 'short', timeZone: 'America/New_York' });
const modelNames = { ncep_rrfs_conus: 'NOAA RRFS', gfs_hrrr: 'NOAA HRRR', gfs_global: 'NOAA GFS', ecmwf_ifs025: 'ECMWF IFS', ecmwf_aifs025: 'ECMWF AIFS', icon_seamless: 'DWD ICON', gem_seamless: 'Canada GEM', ukmo_global_deterministic_10km: 'UK Met Office Global', ncep_nam_conus: 'NOAA NAM', ncep_rap_conus: 'NOAA RAP' };
const modelLabel = id => modelNames[id] || id;
const display = value => value ?? '—';

function showPeak(id, rows, key, unit) {
  const values = rows.map(row => row[key]).filter(Number.isFinite);
  byId(id).textContent = values.length ? Math.max(...values).toLocaleString('en-US') + ' ' + unit : '—';
}

async function loadForecast() {
  const response = await fetch('forecast.json');
  if (!response.ok) throw new Error('Forecast data is unavailable.');
  const data = await response.json();
  const models = Object.keys(data.models);
  const dates = [...new Set(Object.values(data.models).flat().map(row => row.time.slice(0, 10)))].sort();
  if (!models.length || !dates.length) throw new Error('No forecast hours are available.');

  byId('status').textContent = 'Updated ' + runFormat.format(new Date(data.generated));
  const missing = data.requested.filter(id => !models.includes(id));
  byId('coverage-label').textContent = models.length + ' of ' + data.requested.length + ' models available';
  byId('coverage-detail').textContent = missing.length ? 'Unavailable: ' + missing.map(modelLabel).join(', ') : 'All requested models returned data.';
  byId('coverage').hidden = false;
  for (const date of dates) day.add(new Option(dayFormat.format(new Date(date + 'T12:00:00Z')), date));
  for (const id of models) model.add(new Option(modelLabel(id), id));
  day.disabled = model.disabled = false;

  function draw() {
    const rows = data.models[model.value].filter(row => row.time.startsWith(day.value));
    showPeak('lift', rows, 'lift_agl', 'ft');
    showPeak('thermal', rows, 'wstar_kt', 'kt');
    showPeak('wind', rows, 'wind_kt', 'kt');
    const body = byId('rows');
    body.replaceChildren();
    if (!rows.length) {
      const cell = body.insertRow().insertCell();
      cell.colSpan = 8;
      cell.textContent = 'No hourly values for this day and model.';
      return;
    }
    for (const row of rows) {
      const tr = body.insertRow();
      const cells = [row.time.slice(11), [row.lift_agl, row.lift_msl], row.lcl_msl, [row.wstar_kt, row.wstar_fpm], [row.wind_kt, row.wind_dir], [row.crosswind[35], row.crosswind[99]], row.rain_in, row.cape];
      for (const value of cells) tr.insertCell().textContent = Array.isArray(value) ? value.map(display).join(' / ') : display(value);
    }
  }
  day.addEventListener('change', draw);
  model.addEventListener('change', draw);
  draw();
}
loadForecast().catch(error => { byId('status').textContent = error.message; });
</script>
</body>
</html>
'''
if __name__=='__main__': build()
