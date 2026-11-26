"""Experimental sailplane dashboard. No operational go/no-go rating."""
import json, math, statistics, html
from datetime import datetime
from shutil import copyfile
from zoneinfo import ZoneInfo
from .config import load_sites, load_settings, ROOT, SITE_DIR
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
    (output/'index.html').write_text(PAGE, encoding='utf-8')
    for portrait in ('business-ranger-studio.jpg', 'business-ranger-rain.jpg', 'business-ranger-wind.jpg'):
        source = ROOT / 'static' / portrait
        if source.is_file():
            copyfile(source, output / portrait)
    if archive: save_run(now.strftime('%Y%m%dT%H%M'),payload)
    return payload

PAGE = '''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ranger’s Weather Prediction for KVSF · Springfield Soaring Forecast</title>
<style>
:root{color-scheme:light;--ink:#142e39;--muted:#48616a;--line:#dce7e8;--teal:#12665c;--paper:#f3f7f6}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.5 system-ui,sans-serif}a{color:var(--teal)}
.hero{background:radial-gradient(ellipse at 88% 0%,#23776d 0%,transparent 58%),linear-gradient(115deg,#12313f,#144a4f);color:#fff;padding:clamp(32px,7vw,88px) 20px 56px}.wrap{max-width:1120px;margin:auto}.location{color:#b8e8dc;font-weight:700;letter-spacing:.09em;text-transform:uppercase;font-size:.78rem;margin:0 0 14px}.hero h1{font-size:clamp(2.5rem,6.5vw,5rem);line-height:1.02;letter-spacing:-.06em;margin:0;max-width:850px}.hero .updated{color:#d4edeb;margin:18px 0 0;font-size:.9rem}
main.wrap{padding:0 20px 30px;margin-top:-25px}.panel{background:#fff;border:1px solid var(--line);border-radius:18px;box-shadow:0 8px 30px #16373d0a}.controls{padding:18px;display:grid;grid-template-columns:1fr 1fr;gap:14px}.controls label{font-size:.82rem;font-weight:700;color:var(--muted);min-width:0}select{display:block;width:100%;margin-top:5px;padding:10px 12px;border:1px solid #a9bec0;border-radius:9px;background:#f8fbfa;color:var(--ink);font:inherit;font-size:1rem}select:focus-visible,.scroll:focus-visible{outline:3px solid #168377;outline-offset:3px}
.notice{font-size:.87rem;color:#4a4735;background:#fff9e9;border:1px solid #ecdfba;border-radius:10px;padding:11px 14px;margin:16px 0}.models{color:var(--muted);font-size:.87rem;margin:12px 0 18px;overflow-wrap:anywhere}.models summary{cursor:pointer;width:fit-content}.models p{margin:6px 0}
.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:18px}.metric{padding:15px 17px;border-top:3px solid #49a597}.metric span{display:block;color:var(--muted);font-size:.82rem;font-weight:650}.metric strong{font-size:clamp(1.2rem,3vw,1.9rem);letter-spacing:-.05em;font-variant-numeric:tabular-nums}
.table-head{padding:16px 18px 12px}.table-head h2{margin:0;font-size:1.25rem}.scroll{overflow:auto;max-height:590px;border-radius:0 0 18px 18px}table{width:100%;min-width:780px;border-spacing:0;font-variant-numeric:tabular-nums}th,td{text-align:left;padding:11px 13px;white-space:nowrap;border-bottom:1px solid #e6eeed}th{position:sticky;top:0;z-index:2;background:#e8f2f0;color:#254b4c;font-size:.78rem}td{font-size:.9rem;background:#fff}tr:nth-child(even) td{background:#f6faf9}td:first-child,th:first-child{position:sticky;left:0;font-weight:700;box-shadow:1px 0 var(--line)}td:first-child{z-index:1}th:first-child{z-index:3}footer{color:var(--muted);font-size:.82rem;margin:20px 0 0}
@media(max-width:560px){main.wrap{padding-inline:12px}.controls{padding:13px;gap:9px}.metrics{gap:6px}.metric{padding:9px 8px}.metric span{font-size:.72rem}.table-head{padding:13px}.hero{padding-inline:16px}.scroll{max-height:65vh}}

.charts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin-bottom:18px}.chart{padding:16px;margin:0;min-width:0}.chart h2{font-size:1rem;margin:0}.chart p,.chart-legend,.blend-note{font-size:.83rem;color:var(--muted);margin:4px 0 10px}.chart canvas{display:block;width:100%;height:220px}.chart-legend{margin:0 0 12px}.chart-legend::before{content:'';display:inline-block;width:1.25em;height:.75em;background:#bfdfd9;margin-right:.45em;border-radius:3px}.blend-note{margin:0 0 14px}.sample{display:block;font-size:.7rem;color:var(--muted);font-weight:400}@media(max-width:670px){.charts{grid-template-columns:1fr}.chart canvas{height:195px}}

.thermal-window{padding:20px;margin-bottom:18px;border-left:4px solid #49a597}.thermal-window h2{margin:0;font-size:1.08rem}.window-time{font-size:clamp(1.25rem,3vw,1.75rem);font-weight:750;margin:6px 0 2px;letter-spacing:-.035em}.thermal-window p:not(.window-time){font-size:.87rem;color:var(--muted);margin:5px 0}.thermal-window details{font-size:.83rem;color:var(--muted);margin-top:8px}.thermal-window summary{cursor:pointer}.window-hour td:first-child{box-shadow:inset 3px 0 #49a597,1px 0 var(--line)}

.weekend{margin-bottom:18px}.weekend-header{display:flex;flex-wrap:wrap;align-items:baseline;justify-content:space-between;gap:4px 12px;margin-bottom:9px}.weekend-header h2{margin:0;font-size:1.25rem}.weekend-header p,.weekend-card p,.flight-log p{margin:4px 0;color:var(--muted);font-size:.85rem}.weekend-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.weekend-card{padding:15px 17px;border-top:3px solid #49a597}.weekend-card h3{margin:0;font-size:.94rem}.weekend-card .weekend-time{font-size:1.08rem;color:var(--ink);font-weight:700;margin-top:5px}.weekend-card button{background:#e8f2f0;color:var(--teal);border:1px solid var(--line);border-radius:7px;padding:7px 10px;font:inherit;font-size:.82rem;font-weight:700;cursor:pointer;margin-top:8px}.weekend-card button:focus-visible{outline:3px solid #168377;outline-offset:3px}.flight-log{margin-top:18px;padding:14px 17px}.flight-log summary{font-weight:700;cursor:pointer}.flight-log a{display:inline-block;margin-top:5px}@media(max-width:520px){.weekend-grid{gap:8px}.weekend-card{padding:10px}.weekend-card .weekend-time{font-size:1rem}}

.hero .weather-desk{display:grid;grid-template-columns:minmax(0,1fr) clamp(170px,24vw,276px);align-items:center;gap:clamp(18px,5vw,62px)}.hero h1{font-size:clamp(2.45rem,5.7vw,4.7rem)}.hero h1 span{color:#c4f2e5}.hero .ranger-line{color:#e7f5f2;font-size:clamp(.95rem,1.7vw,1.12rem);margin:16px 0 0}.ranger-portrait{margin:0;overflow:hidden;border-radius:16px;background:#0e2e38;border:1px solid #b8e8dc65;box-shadow:0 16px 40px #071e2860}.ranger-portrait img{display:block;width:100%;height:auto;aspect-ratio:1.15;object-fit:cover;object-position:center 42%}.ranger-portrait figcaption{padding:10px 12px;line-height:1.25}.ranger-portrait strong,.ranger-portrait small{display:block}.ranger-portrait small{color:#b8e8dc;margin-top:3px}
@media(max-width:560px){.hero .weather-desk{grid-template-columns:minmax(0,1fr) clamp(92px,27vw,145px);gap:12px}.hero h1{font-size:clamp(1.7rem,6.2vw,2.55rem)}.hero .location{font-size:.65rem;margin-bottom:9px}.hero .ranger-line{font-size:.82rem;margin-top:10px}.hero .updated{font-size:.76rem;margin-top:10px}.ranger-portrait{border-radius:10px}.ranger-portrait img{aspect-ratio:1}.ranger-portrait figcaption{padding:6px}.ranger-portrait strong{font-size:.73rem}.ranger-portrait small{font-size:.66rem}}

.ranger-quip,.weekend-card .ranger-quip,.thermal-window p.ranger-quip,.metric .ranger-quip{display:block;color:var(--teal);font-size:.8rem;font-weight:650;line-height:1.35;margin:7px 0 4px}.ranger-quip[hidden],.metric .ranger-quip[hidden]{display:none}
</style>
</head>
<body>
<header class="hero"><div class="wrap weather-desk">
<div class="weather-copy">
<p class="location">Hartness State Airport · Springfield, Vermont</p>
<h1>Ranger’s weather prediction <span>for KVSF</span></h1>
<p class="ranger-line">“I sniff out thermals. The models do the math.”</p>
<p class="updated" id="status" role="status">Loading forecast…</p>
<p class="updated"><strong>Weather refresh schedule.</strong> The site checks for new weather data Wednesday through Saturday at 6:41 a.m., 12:41 p.m., and 6:41 p.m. EST, and Sunday at 6:41 a.m. and 12:41 p.m. EST. During daylight saving time, checks run one hour later. The timestamp above shows when this forecast was generated.</p>
</div>
<figure class="ranger-portrait">
<img id="ranger-banner" src="business-ranger-studio.jpg" width="560" height="560" alt="Business Ranger, a cream-colored dog in a suit and tie">
<figcaption><strong>Business Ranger</strong><small>KVSF weather dog</small></figcaption>
</figure>
</div></header>
<main class="wrap">
<section class="weekend" id="weekend" aria-labelledby="weekend-title" hidden>
<div class="weekend-header"><h2 id="weekend-title">Weekend at KVSF</h2><p id="weekend-updated"></p></div>
<div class="weekend-grid" id="weekend-days"></div>
</section>

<div class="controls panel"><label>Forecast day<select id="day" disabled></select></label><label>Weather model<select id="model" disabled></select></label></div>
<p class="notice">Experimental v0.2 · Research estimates only. Use an aviation weather briefing for flight decisions. W* is a convective velocity scale. LCL is an estimate. Ridge and wave forecasts are unavailable.</p>
<details class="models" id="coverage" hidden><summary id="coverage-label">Model coverage</summary><p id="coverage-detail"></p></details>
<section class="thermal-window panel" aria-labelledby="window-title">
<h2 id="window-title" tabindex="-1">Best thermal window</h2>
<p id="window-time" class="window-time" role="status">Loading forecast…</p>
<p id="window-quip" class="ranger-quip" hidden></p>
<p id="window-values" hidden></p>
<p id="window-support" hidden></p>
<p id="window-weather" hidden></p>
<details><summary>How the window is selected</summary><p>The page ranks three consecutive local forecast hours by average W*. In the blended view, a majority of the models available that day must show positive modeled lift and lift height in all three hours. This experimental ranking has no minimum flyable lift threshold and does not estimate flight duration. Ranger’s quips are playful descriptions of modeled conditions.</p></details>
</section>
<section class="panel" aria-labelledby="sounding-title" style="padding:18px;margin:16px 0">
<h2 id="sounding-title">KVSF forecast sounding</h2>
<p id="sounding-label" aria-live="polite">Waiting for forecast data…</p>
<p id="sounding-summary" hidden></p>
<details id="sounding-detail" hidden><summary>View Skew-T</summary>
<p>Temperature (red) and dew point (blue) by pressure. Diagonal guides show temperature in °C. Surface values appear in the summary only.</p>
<svg id="sounding-plot" viewBox="0 0 530 350" role="img" aria-label="Modeled KVSF temperature and dew point on a skewed temperature and logarithmic pressure chart" style="display:block;width:100%;max-width:620px;background:#fff"></svg>
</details>
</section>
<div class="metrics" aria-label="Selected forecast day summary">
<div class="metric panel"><span>Peak lift height AGL</span><strong id="lift">—</strong><small id="lift-quip" class="ranger-quip" hidden></small></div>
<div class="metric panel"><span>Peak W*</span><strong id="thermal">—</strong><small id="thermal-quip" class="ranger-quip" hidden></small></div>
<div class="metric panel"><span>Peak surface wind</span><strong id="wind">—</strong><small id="wind-quip" class="ranger-quip" hidden></small></div>
</div>
<p class="blend-note" id="blend-note" hidden>Equal-weight median by hour. Only available values contribute. Wind direction uses a circular mean. The count beside each hour is the number of models with an hourly profile.</p>
<p class="chart-legend" id="chart-legend" hidden>Shaded area shows the lowest to highest model estimate. The line is the median.</p>
<div class="charts">
<figure class="chart panel"><h2>Modeled top of lift</h2><p>Feet above ground level</p><canvas id="lift-chart" role="img" aria-label="Modeled top of lift by local hour. Values are available in the hourly table."></canvas><p id="lift-band-note" hidden>Narrower shading means closer model agreement.</p></figure>
<figure class="chart panel"><h2>Thermal strength · W*</h2><p>Feet per minute of convective velocity</p><canvas id="thermal-chart" role="img" aria-label="Modeled thermal strength by local hour. Values are available in the hourly table."></canvas><p id="thermal-band-note" hidden>Narrower shading means closer model agreement.</p></figure>
</div>
<section class="panel" aria-labelledby="hourly-title">
<div class="table-head"><h2 id="hourly-title">Hourly forecast</h2></div>
<div class="scroll" tabindex="0" role="region" aria-label="Scrollable hourly forecast table">
<table><thead><tr><th scope="col">Local time</th><th scope="col">Modeled lift (fpm)</th><th scope="col">Wind kt / true°</th><th scope="col">Rain in</th><th scope="col">CAPE (J/kg)</th></tr></thead><tbody id="rows"></tbody></table>
</div></section>
<details class="flight-log panel"><summary>Compare with a KVSF flight</summary><p>Make one entry per flight. Record the forecast you saw before flying, then fill in what you observed. Leave unknown values blank and keep the completed file with your own records.</p><a download="kvsf-flight-log.csv" href="data:text/csv;charset=utf-8,Flight%20date%20(local)%2CTow%20release%20time%20(local)%2CTow%20release%20height%20(ft%20AGL)%2CSustained%20lift%20found%20(yes%2Fno%2Funknown)%2CObserved%20top%20of%20lift%20(ft%20AGL)%2CTime%20lift%20faded%20(local)%2CMinutes%20from%20release%20to%20landing%2CForecast%20updated%20time%20(local)%2CForecast%20window%20(local)%2CForecast%20W-star%20(fpm)%2CForecast%20top%20of%20lift%20(ft%20AGL)%2CNotes%0D%0A">Download flight log template (CSV)</a></details>
<footer>Weather data from <a href="https://open-meteo.com/">Open-Meteo</a>. Adapted from <a href="https://github.com/tacoleman69/Newengland-flying-forecast">New England Flying Forecast</a>.</footer>
</main>
<script>
const byId = id => document.getElementById(id);
const day = byId('day');
const model = byId('model');
const dayFormat = new Intl.DateTimeFormat('en-US', { weekday: 'short', month: 'short', day: 'numeric', timeZone: 'UTC' });
const windowDateFormat = new Intl.DateTimeFormat('en-US', { weekday: 'long', month: 'long', day: 'numeric', timeZone: 'UTC' });
const runFormat = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', timeZoneName: 'short', timeZone: 'America/New_York' });
const modelNames = { ncep_rrfs_conus: 'NOAA RRFS', gfs_hrrr: 'NOAA HRRR', gfs_global: 'NOAA GFS', ecmwf_ifs025: 'ECMWF IFS', ecmwf_aifs025: 'ECMWF AIFS', icon_seamless: 'DWD ICON', gem_seamless: 'Canada GEM', ukmo_global_deterministic_10km: 'UK Met Office Global', ncep_nam_conus: 'NOAA NAM', ncep_rap_conus: 'NOAA RAP' };
const modelLabel = id => modelNames[id] || id;
const display = value => Number.isFinite(value) ? value.toLocaleString('en-US', { maximumFractionDigits: 3 }) : value ?? '—';

function showPeak(id, rows, key, unit) {
  const values = rows.map(row => row[key]).filter(Number.isFinite);
  byId(id).textContent = values.length ? Math.max(...values).toLocaleString('en-US') + ' ' + unit : '—';
}

const BLEND = 'blend';
const forecastFields = ['lift_agl', 'lift_msl', 'lcl_msl', 'wstar_fpm', 'wind_kt', 'rain_in', 'cape'];

function blendedRows(modelRows) {
  const hours = new Map();
  for (const series of modelRows) {
    for (const row of series) {
      if (!hours.has(row.time)) hours.set(row.time, []);
      hours.get(row.time).push(row);
    }
  }
  return [...hours.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([time, rows]) => {
    const blended = { time, modelCount: rows.length, spread: {} };
    for (const field of forecastFields) {
      const values = rows.map(row => row[field]).filter(Number.isFinite).sort((a, b) => a - b);
      const middle = Math.floor(values.length / 2);
      if (!values.length) {
        blended[field] = null;
        continue;
      }
      blended[field] = values.length % 2 ? values[middle] : (values[middle - 1] + values[middle]) / 2;
      if (values.length > 1) blended.spread[field] = [values[0], values[values.length - 1]];
    }
    const angles = rows.map(row => row.wind_dir).filter(Number.isFinite).map(deg => deg * Math.PI / 180);
    const east = angles.reduce((sum, angle) => sum + Math.sin(angle), 0);
    const north = angles.reduce((sum, angle) => sum + Math.cos(angle), 0);
    blended.wind_dir = Math.hypot(east, north) > angles.length * 0.1
      ? (Math.round(Math.atan2(east, north) * 180 / Math.PI) + 360) % 360 : null;
    return blended;
  });
}

function drawChart(id, rows, key, color) {
  const canvas = byId(id);
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  if (!width || !height) return;
  const scale = window.devicePixelRatio || 1;
  canvas.width = Math.round(width * scale);
  canvas.height = Math.round(height * scale);
  const ctx = canvas.getContext('2d');
  ctx.scale(scale, scale);
  const maxValue = Math.max(0, ...rows.flatMap(row => [row[key], row.spread?.[key]?.[1]]).filter(Number.isFinite));
  const step = key === 'lift_agl' ? 100 : 25;
  const tick = Math.max(step, Math.ceil(maxValue / (4 * step)) * step);
  const left = 48, right = width - 14, top = 12, bottom = height - 29;
  const x = hour => left + hour / 23 * (right - left);
  const y = value => bottom - value / (4 * tick) * (bottom - top);
  const hourOf = row => Number(row.time.slice(11, 13));
  ctx.font = '11px system-ui';
  ctx.fillStyle = '#48616a';
  ctx.strokeStyle = '#dce7e8';
  ctx.textAlign = 'right';
  for (let i = 0; i <= 4; i++) {
    const value = i * tick;
    ctx.beginPath(); ctx.moveTo(left, y(value)); ctx.lineTo(right, y(value)); ctx.stroke();
    ctx.fillText(value.toLocaleString('en-US'), left - 7, y(value) + 4);
  }
  ctx.textAlign = 'center';
  for (const hour of [0, 6, 12, 18, 23]) ctx.fillText(String(hour).padStart(2, '0') + ':00', x(hour), height - 8);
  ctx.fillStyle = '#bfdfd9';
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  for (let i = 1; i < rows.length; i++) {
    const a = rows[i - 1], b = rows[i];
    if (hourOf(b) - hourOf(a) !== 1) continue;
    const ar = a.spread?.[key], br = b.spread?.[key];
    if (!ar || !br) continue;
    ctx.beginPath(); ctx.moveTo(x(hourOf(a)), y(ar[0])); ctx.lineTo(x(hourOf(b)), y(br[0]));
    ctx.lineTo(x(hourOf(b)), y(br[1])); ctx.lineTo(x(hourOf(a)), y(ar[1])); ctx.closePath(); ctx.fill();
  }
  let previous = null;
  ctx.fillStyle = color;
  for (const row of rows) {
    if (!Number.isFinite(row[key])) { previous = null; continue; }
    const px = x(hourOf(row)), py = y(row[key]);
    if (previous && hourOf(row) - hourOf(previous) === 1) {
      ctx.beginPath(); ctx.moveTo(x(hourOf(previous)), y(previous[key])); ctx.lineTo(px, py); ctx.stroke();
    }
    ctx.beginPath(); ctx.arc(px, py, 2.4, 0, Math.PI * 2); ctx.fill();
    previous = row;
  }
  if (!rows.some(row => Number.isFinite(row[key]))) {
    ctx.fillStyle = '#48616a';
    ctx.fillText('No model values available', (left + right) / 2, (top + bottom) / 2);
  }
}

function windowForecast(rows, series) {
  const valid = row => row && Number.isFinite(row.wstar_fpm) && row.wstar_fpm > 0
    && Number.isFinite(row.lift_agl) && row.lift_agl > 0;
  const byModel = series.filter(modelRows => modelRows.length).map(modelRows => new Map(modelRows.map(row => [row.time, row])));
  const localMinutes = time => Number(time.slice(11, 13)) * 60 + Number(time.slice(14, 16));
  let best = null;
  for (let index = 0; index + 2 < rows.length; index++) {
    const hours = rows.slice(index, index + 3);
    const firstMinute = localMinutes(hours[0].time);
    if (!hours.every((row, offset) => valid(row) && localMinutes(row.time) === firstMinute + offset * 60)) continue;
    const times = hours.map(row => row.time);
    const samples = byModel.map(modelRows => times.map(time => modelRows.get(time)));
    const support = samples.filter(modelHours => modelHours.every(valid)).length;
    if (support <= byModel.length / 2) continue;
    const lift = hours.reduce((sum, row) => sum + row.wstar_fpm, 0) / hours.length;
    const height = hours.reduce((sum, row) => sum + row.lift_agl, 0) / hours.length;
    if (!best || lift > best.lift || (lift === best.lift && height > best.height)) {
      best = { times, lift, height, support, total: byModel.length, samples };
    }
  }
  return best;
}

function rangerQuip(report) {
  if (!report) return 'The thermals are playing fetch. Ranger hasn’t found them yet.';
  const { wet, covered } = precipitationCoverage(report.samples);
  if (wet) return 'Ranger packed an umbrella. Some models show precipitation.';
  if (report.total >= 3 && report.support / report.total >= 2 / 3 && covered === report.total
      && report.lift >= 300 && report.height >= 2500) {
    return 'The models are hinting at a howling thermal day!';
  }
  if (report.lift < 120 || report.height < 750) return 'More tail wags than thermals in this run.';
  return 'Ranger caught a whiff of lift.';
}

function setPeakQuip(id, rows, key, threshold, above, below) {
  const values = rows.map(row => row[key]).filter(Number.isFinite);
  const note = byId(id);
  note.hidden = values.length === 0;
  note.textContent = values.length ? (Math.max(...values) >= threshold ? above : below) : '';
}

function soundingPoints(row) {
  return (row.profile || []).filter(point => Number.isFinite(point.p) && point.p >= 600 && Number.isFinite(point.t));
}

function drawSounding(points) {
  const bottom = Math.max(1000, ...points.map(point => point.p));
  const top = Math.min(650, ...points.map(point => point.p));
  const fraction = pressure => Math.log(bottom / pressure) / Math.log(bottom / top);
  const y = pressure => 316 - 288 * fraction(pressure);
  const skew = 24;
  const values = points.flatMap(point => [point.t, point.td].filter(Number.isFinite)
    .map(value => value + skew * fraction(point.p)));
  const low = Math.floor((Math.min(...values) - 4) / 10) * 10;
  const high = Math.ceil((Math.max(...values) + 4) / 10) * 10;
  const x = (temperature, pressure) => 58 + 446 * (temperature + skew * fraction(pressure) - low) / (high - low);
  const guides = [];
  for (let pressure = Math.floor(bottom / 50) * 50; pressure >= top; pressure -= 50) {
    guides.push('<line x1="58" x2="504" y1="' + y(pressure) + '" y2="' + y(pressure) + '" stroke="#dce7e8"/>');
    guides.push('<text x="51" y="' + (y(pressure) + 4) + '" text-anchor="end">' + pressure + '</text>');
  }
  for (let t = low - 30; t <= high; t += 10) {
    guides.push('<line x1="' + x(t, bottom) + '" x2="' + x(t, top) + '" y1="316" y2="28" stroke="#dce7e8" clip-path="url(#sounding-clip)"/>');
    if (t >= low) guides.push('<text x="' + x(t, bottom) + '" y="336" text-anchor="middle">' + t + '°</text>');
  }
  const trace = (field, color) => {
    let path = '';
    let connected = false;
    for (const point of points) {
      if (!Number.isFinite(point[field])) { connected = false; continue; }
      path += (connected ? ' L ' : ' M ') + x(point[field], point.p) + ' ' + y(point.p);
      connected = true;
    }
    return '<path d="' + path + '" stroke="' + color + '" stroke-width="2.8" fill="none"/>';
  };
  byId('sounding-plot').innerHTML = '<defs><clipPath id="sounding-clip"><rect x="58" y="28" width="446" height="288"/></clipPath></defs>' +
    '<g font-size="12" fill="#142e39"><text x="22" y="18">hPa</text>' + guides.join('') + '</g>' +
    '<rect x="58" y="28" width="446" height="288" stroke="#9aadb2" fill="none"/>' + trace('t', '#ae2828') + trace('td', '#176297');
}

function updateSounding(models, selectedModel, selectedDay, windowHours) {
  const label = byId('sounding-label');
  const summary = byId('sounding-summary');
  const detail = byId('sounding-detail');
  summary.hidden = detail.hidden = true;
  const middle = [...windowHours][Math.floor(windowHours.size / 2)];
  const target = middle || selectedDay + 'T13:00';
  const minutes = time => Number(time.slice(11, 13)) * 60 + Number(time.slice(14, 16));
  const all = Object.entries(models).flatMap(([id, rows]) => rows
    .filter(row => row.time.startsWith(selectedDay) && soundingPoints(row).length >= 2)
    .map(row => ({ id, row })));
  const available = all.filter(item => selectedModel === BLEND || item.id === selectedModel);
  available.sort((a, b) => Math.abs(minutes(a.row.time) - minutes(target)) - Math.abs(minutes(b.row.time) - minutes(target)) ||
    a.row.time.localeCompare(b.row.time) || a.id.localeCompare(b.id));
  if (!available.length) { label.textContent = 'No usable sounding for this day and model.'; return; }
  const time = available[0].row.time;
  const atHour = available.filter(item => item.row.time === time);
  const heights = all.filter(item => item.row.time === time).map(item => item.row.lift_agl)
    .filter(Number.isFinite).sort((a, b) => a - b);
  const mid = Math.floor(heights.length / 2);
  const median = heights.length % 2 ? heights[mid] : (heights[mid - 1] + heights[mid]) / 2;
  const distance = item => Number.isFinite(item.row.lift_agl) ? Math.abs(item.row.lift_agl - median) : Infinity;
  if (selectedModel === BLEND && heights.length) atHour.sort((a, b) => distance(a) - distance(b));
  const { id, row } = atHour[0];
  label.textContent = (selectedModel === BLEND ? 'Representative model · ' : '') + modelLabel(id) + ' · ' + time.slice(11, 16) +
    ' Eastern · ' + (!middle ? 'afternoon snapshot' : time === target ? 'middle hour of thermal window' : 'nearest available hour to window midpoint');
  const feet = value => Math.round(value).toLocaleString('en-US');
  const ground = row.profile[0].z;
  const altitude = point => (point.z - ground) * 3.28084;
  const inversion = row.profile.find((point, i, points) => i > 0 && altitude(point) <= 6000 && point.t > points[i - 1].t);
  const notes = [];
  if (Number.isFinite(row.lift_agl)) notes.push('Modeled top of lift ' + feet(row.lift_agl) + ' ft AGL');
  if (heights.length > 1) notes.push('Model spread ' + feet(heights[0]) + '–' + feet(heights[heights.length - 1]) + ' ft AGL (' + heights.length + ' models)');
  if (Number.isFinite(row.lcl_msl)) notes.push('Estimated LCL ' + feet(row.lcl_msl) + ' ft MSL');
  if (inversion) notes.push('Possible inversion below ' + feet(altitude(inversion)) + ' ft AGL');
  const winds = row.profile.filter(point => Number.isFinite(point.ws) && Number.isFinite(point.wd));
  const nearest = [0, 1500, 3500].map(height => winds.reduce((best, point) =>
    !best || Math.abs(altitude(point) - height) < Math.abs(altitude(best) - height) ? point : best, null));
  const wind = [...new Set(nearest.filter(Boolean))].map(point => (point.p === null ? 'surface' : feet(altitude(point)) + ' ft AGL') +
    ' ' + Math.round(point.wd) + '° true at ' + Math.round(point.ws / 1.15078) + ' kt');
  if (wind.length) notes.push('Wind ' + wind.join(', '));
  summary.textContent = notes.join(' · ');
  summary.hidden = !notes.length;
  drawSounding(soundingPoints(row));
  detail.hidden = false;
}

function updateThermalWindow(rows, series, isBlend) {
  const best = windowForecast(rows, series);
  const quip = byId('window-quip');
  quip.textContent = rangerQuip(best);
  quip.hidden = !rows.length;
  const values = byId('window-values');
  const support = byId('window-support');
  const weather = byId('window-weather');
  values.hidden = support.hidden = weather.hidden = true;
  if (!best) {
    byId('window-time').textContent = 'No clear thermal window';
    return new Set();
  }
  const localHour = time => time.slice(11, 16);
  const rounded = value => Math.round(value).toLocaleString('en-US');
  byId('window-time').textContent = localHour(best.times[0]) + '–' + localHour(best.times[2]) + ' local · three forecast hours';
  values.textContent = 'Window averages: ' + rounded(best.lift) + ' fpm W* · ' + rounded(best.height) + ' ft AGL top of lift.';
  values.hidden = false;
  if (isBlend) {
    support.textContent = best.support + ' of ' + best.total + ' available models show positive modeled lift and height in all three hours.';
    support.hidden = false;
  }
  const { wet, covered } = precipitationCoverage(best.samples);
  if (wet) {
    weather.textContent = isBlend ? 'Precipitation appears during the window in ' + wet + ' of ' + covered + ' models with precipitation data.' : 'The selected model shows precipitation during the window.';
    weather.hidden = false;
  }
  return new Set(best.times);
}

function precipitationCoverage(samples) {
  const rain = samples.map(hours => hours.filter(row => Number.isFinite(row?.rain_in)));
  return {
    covered: rain.filter(hours => hours.length > 0).length,
    wet: rain.filter(hours => hours.some(row => row.rain_in > 0)).length
  };
}

function updateRangerBanner(blend) {
  const today = new Intl.DateTimeFormat('sv-SE', { timeZone: 'America/New_York' }).format(new Date());
  const daylightRows = blend.filter(row => row.time.startsWith(today) &&
    row.time.slice(11, 16) >= '10:00' && row.time.slice(11, 16) <= '17:00');
  const windy = daylightRows.some(row => Number.isFinite(row.wind_kt) && row.wind_kt >= 20);
  const rainy = daylightRows.some(row => Number.isFinite(row.rain_in) && row.rain_in >= 0.05);
  if (!windy && !rainy) return;

  const portrait = byId('ranger-banner');
  const weatherPortrait = new Image();
  weatherPortrait.onload = () => {
    portrait.src = weatherPortrait.src;
    portrait.alt = windy ? 'Business Ranger being swept sideways by the wind' : 'Business Ranger holding an umbrella in the rain';
  };
  weatherPortrait.src = windy ? 'business-ranger-wind.jpg' : 'business-ranger-rain.jpg';
}

function showWeekend(data, blend, dates) {
  const localParts = new Intl.DateTimeFormat('en-US', {
    year: 'numeric', month: 'numeric', day: 'numeric', timeZone: 'America/New_York'
  }).formatToParts(new Date());
  const local = Object.fromEntries(localParts.map(part => [part.type, part.value]));
  // Advance calendar dates in UTC after finding today's date in Springfield.
  const saturday = new Date(Date.UTC(+local.year, +local.month - 1, +local.day));
  const offset = saturday.getUTCDay() === 0 ? -1 : 6 - saturday.getUTCDay();
  saturday.setUTCDate(saturday.getUTCDate() + offset);
  const sunday = new Date(saturday);
  sunday.setUTCDate(sunday.getUTCDate() + 1);
  const updated = new Date(data.generated);
  const ageHours = (Date.now() - updated.getTime()) / 3600000;
  byId('weekend-updated').textContent = 'Run issued ' + runFormat.format(updated) + (ageHours >= 24 ? ' · over 24 hours old' : '');
  const number = value => Math.round(value).toLocaleString('en-US');
  for (const date of [saturday, sunday]) {
    const key = date.toISOString().slice(0, 10);
    const dayRows = rows => rows.filter(row => row.time.startsWith(key));
    const report = windowForecast(dayRows(blend), Object.values(data.models).map(dayRows));
    const card = document.createElement('article');
    card.className = 'weekend-card panel';
    const title = card.appendChild(document.createElement('h3'));
    title.textContent = dayFormat.format(date);
    const time = card.appendChild(document.createElement('p'));
    time.className = 'weekend-time';
    time.textContent = report ? report.times[0].slice(11, 16) + '–' + report.times[2].slice(11, 16) + ' local'
      : dates.includes(key) ? 'No clear thermal window' : 'Forecast not available';
    if (dates.includes(key)) {
      const quip = card.appendChild(document.createElement('p'));
      quip.className = 'ranger-quip';
      quip.textContent = rangerQuip(report);
    }
    if (report) {
      const averages = card.appendChild(document.createElement('p'));
      averages.textContent = number(report.lift) + ' fpm W* · ' + number(report.height) + ' ft AGL';
      const agreement = card.appendChild(document.createElement('p'));
      agreement.textContent = report.support + ' of ' + report.total + ' models show lift in all three hours';
      const { wet, covered } = precipitationCoverage(report.samples);
      const rain = card.appendChild(document.createElement('p'));
      rain.textContent = covered ? 'Precipitation: ' + wet + ' of ' + covered + ' models during the window' : 'Precipitation data unavailable';
    }
    if (dates.includes(key)) {
      const detail = card.appendChild(document.createElement('button'));
      detail.type = 'button';
      detail.textContent = 'View ' + (date === saturday ? 'Saturday' : 'Sunday') + ' details';
      detail.addEventListener('click', () => {
        day.value = key;
        model.selectedIndex = 0;
        day.dispatchEvent(new Event('change'));
        byId('window-title').scrollIntoView({ block: 'start' });
        byId('window-title').focus({ preventScroll: true });
      });
    }
    byId('weekend-days').append(card);
  }
  byId('weekend').hidden = false;
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
  const blend = blendedRows(Object.values(data.models));
  updateRangerBanner(blend);
  showWeekend(data, blend, dates);
  if (models.length > 1) model.add(new Option('Blended forecast', BLEND));
  for (const id of models) model.add(new Option(modelLabel(id), id));
  day.disabled = model.disabled = false;

  let selectedRows = [];
  function renderCharts() {
    drawChart('lift-chart', selectedRows, 'lift_agl', '#12665c');
    drawChart('thermal-chart', selectedRows, 'wstar_fpm', '#395991');
  }
  function draw() {
    const isBlend = model.value === BLEND;
    const rows = (isBlend ? blend : data.models[model.value]).filter(row => row.time.startsWith(day.value));
    selectedRows = rows;
    const dateLabel = windowDateFormat.format(new Date(day.value + 'T12:00:00Z'));
    byId('window-title').textContent = 'Best thermal window for ' + dateLabel;
    const daySeries = (isBlend ? Object.values(data.models) : [data.models[model.value]])
      .map(series => series.filter(row => row.time.startsWith(day.value)));
    const windowHours = updateThermalWindow(rows, daySeries, isBlend);
    updateSounding(data.models, model.value, day.value, windowHours);
    byId('blend-note').hidden = !isBlend;
    byId('lift-band-note').hidden = !isBlend || !rows.some(row => row.spread?.lift_agl);
    byId('thermal-band-note').hidden = !isBlend || !rows.some(row => row.spread?.wstar_fpm);
    byId('chart-legend').hidden = byId('lift-band-note').hidden && byId('thermal-band-note').hidden;
    renderCharts();
    showPeak('lift', rows, 'lift_agl', 'ft');
    showPeak('thermal', rows, 'wstar_fpm', 'fpm');
    showPeak('wind', rows, 'wind_kt', 'kt');
    setPeakQuip('lift-quip', rows, 'lift_agl', 2000, 'Ranger likes the view from up here.', 'Ranger is keeping his ears low.');
    setPeakQuip('thermal-quip', rows, 'wstar_fpm', 250, 'Ranger’s tail is picking up speed.', 'Easy on the tail wags.');
    setPeakQuip('wind-quip', rows, 'wind_kt', 15, 'Hold on to your floppy ears.', 'Ranger’s tie might stay straight.');

    const body = byId('rows');
    body.replaceChildren();
    if (!rows.length) {
      const cell = body.insertRow().insertCell();
      cell.colSpan = 5;
      cell.textContent = 'No hourly values for this day and model.';
      return;
    }
    for (const row of rows) {
      const tr = body.insertRow();
      tr.classList.toggle('window-hour', windowHours.has(row.time));
      const cells = [row.time.slice(11), Number.isFinite(row.wstar_fpm) ? Math.round(row.wstar_fpm).toLocaleString('en-US') + ' fpm' : null, [row.wind_kt, row.wind_dir], row.rain_in, row.cape];
      for (const value of cells) tr.insertCell().textContent = Array.isArray(value) ? value.map(display).join(' / ') : display(value);
      if (isBlend) {
        const count = document.createElement('span');
        count.className = 'sample';
        count.textContent = row.modelCount + (row.modelCount === 1 ? ' model' : ' models');
        tr.cells[0].append(count);
      }
    }
  }
  day.addEventListener('change', draw);
  model.addEventListener('change', draw);
  new ResizeObserver(renderCharts).observe(byId('lift-chart'));
  draw();
}
loadForecast().catch(error => { byId('status').textContent = error.message; });
</script>
</body>
</html>
'''
if __name__=='__main__': build()
