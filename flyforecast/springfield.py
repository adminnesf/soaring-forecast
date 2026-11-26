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

.charts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin-bottom:18px}.chart{padding:16px;margin:0;min-width:0}.chart h2{font-size:1rem;margin:0}.chart p,.chart-legend,.blend-note{font-size:.83rem;color:var(--muted);margin:4px 0 10px}.chart canvas{display:block;width:100%;height:220px}.chart-legend{margin:0 0 12px}.chart-legend::before{content:'';display:inline-block;width:1.25em;height:.75em;background:#bfdfd9;margin-right:.45em;border-radius:3px}.blend-note{margin:0 0 14px}.sample{display:block;font-size:.7rem;color:var(--muted);font-weight:400}@media(max-width:670px){.charts{grid-template-columns:1fr}.chart canvas{height:195px}}

.thermal-window{padding:20px;margin-bottom:18px;border-left:4px solid #49a597}.thermal-window h2{margin:0;font-size:1.08rem}.window-time{font-size:clamp(1.25rem,3vw,1.75rem);font-weight:750;margin:6px 0 2px;letter-spacing:-.035em}.thermal-window p:not(.window-time){font-size:.87rem;color:var(--muted);margin:5px 0}.thermal-window details{font-size:.83rem;color:var(--muted);margin-top:8px}.thermal-window summary{cursor:pointer}.window-hour td:first-child{box-shadow:inset 3px 0 #49a597,1px 0 var(--line)}
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
<section class="thermal-window panel" aria-labelledby="window-title">
<h2 id="window-title">Best thermal window</h2>
<p id="window-time" class="window-time" role="status">Loading forecast…</p>
<p id="window-values" hidden></p>
<p id="window-support" hidden></p>
<p id="window-weather" hidden></p>
<details><summary>How the window is selected</summary><p>The page ranks three consecutive local forecast hours by average W*. In the blended view, a majority of the models available that day must show positive modeled lift and lift height in all three hours. This experimental ranking has no minimum flyable lift threshold and does not estimate flight duration.</p></details>
</section>
<div class="metrics" aria-label="Selected forecast day summary">
<div class="metric panel"><span>Peak lift height AGL</span><strong id="lift">—</strong></div>
<div class="metric panel"><span>Peak W*</span><strong id="thermal">—</strong></div>
<div class="metric panel"><span>Peak surface wind</span><strong id="wind">—</strong></div>
</div>
<p class="blend-note" id="blend-note" hidden>Equal-weight median by hour. Only available values contribute. Wind direction uses a circular mean. The count beside each hour is the number of models with an hourly profile.</p>
<p class="chart-legend" id="chart-legend" hidden>Shaded area shows the lowest to highest model estimate. The line is the median.</p>
<div class="charts">
<figure class="chart panel"><h2>Modeled top of lift</h2><p>Feet above ground level</p><canvas id="lift-chart" role="img" aria-label="Modeled top of lift by local hour. Values are available in the hourly table."></canvas></figure>
<figure class="chart panel"><h2>Thermal strength · W*</h2><p>Feet per minute of convective velocity</p><canvas id="thermal-chart" role="img" aria-label="Modeled thermal strength by local hour. Values are available in the hourly table."></canvas></figure>
</div>
<section class="panel" aria-labelledby="hourly-title">
<div class="table-head"><h2 id="hourly-title">Hourly forecast</h2></div>
<div class="scroll" tabindex="0" role="region" aria-label="Scrollable hourly forecast table">
<table><thead><tr><th scope="col">Local time</th><th scope="col">Modeled lift (fpm)</th><th scope="col">Wind kt / true°</th><th scope="col">Rain in</th><th scope="col">CAPE (J/kg)</th></tr></thead><tbody id="rows"></tbody></table>
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

function updateThermalWindow(rows, series, isBlend) {
  const best = windowForecast(rows, series);
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
  const rain = best.samples.map(modelHours => modelHours.filter(row => Number.isFinite(row?.rain_in)));
  const wet = rain.filter(modelHours => modelHours.some(row => row.rain_in > 0)).length;
  const covered = rain.filter(modelHours => modelHours.length > 0).length;
  if (wet) {
    weather.textContent = isBlend ? 'Precipitation appears during the window in ' + wet + ' of ' + covered + ' models with precipitation data.' : 'The selected model shows precipitation during the window.';
    weather.hidden = false;
  }
  return new Set(best.times);
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
    const daySeries = (isBlend ? Object.values(data.models) : [data.models[model.value]])
      .map(series => series.filter(row => row.time.startsWith(day.value)));
    const windowHours = updateThermalWindow(rows, daySeries, isBlend);
    byId('blend-note').hidden = !isBlend;
    byId('chart-legend').hidden = !isBlend || !rows.some(row => row.spread?.lift_agl || row.spread?.wstar_fpm);
    renderCharts();
    showPeak('lift', rows, 'lift_agl', 'ft');
    showPeak('thermal', rows, 'wstar_fpm', 'fpm');
    showPeak('wind', rows, 'wind_kt', 'kt');
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
