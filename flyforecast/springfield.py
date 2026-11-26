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

PAGE='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Springfield Soaring Forecast</title><style>body{font:16px system-ui;max-width:1100px;margin:auto;padding:24px;color:#183047;background:#f5f8fb}table{border-collapse:collapse;width:100%;background:white}td,th{padding:9px;text-align:left;border-bottom:1px solid #ddd}select{padding:8px}section{overflow:auto}small{color:#43566b}</style><h1>Springfield Soaring Forecast</h1><p>KVSF · Hartness State Airport · Experimental v0.2</p><p>Research estimates only, not a flight briefing. W* is a convective velocity scale, not expected glider climb. LCL is not observed cloud base. Ridge and wave forecasts are not implemented.</p><p id="status">Loading forecast…</p><label>Day <select id="day"></select></label> <label>Model <select id="model"></select></label><section><table><thead><tr><th>Local time</th><th>Lift AGL / MSL ft</th><th>LCL MSL ft</th><th>W* kt / fpm</th><th>Wind kt / true°</th><th>Crosswind 05/11 kt</th><th>Rain in</th><th>CAPE</th></tr></thead><tbody id="rows"></tbody></table></section><p><small>Adapted from <a href="https://github.com/tacoleman69/Newengland-flying-forecast">New England Flying Forecast by tacoleman69</a>. Weather data: <a href="https://open-meteo.com/">Open-Meteo</a>.</small></p><script>fetch('forecast.json').then(r=>{if(!r.ok)throw Error('Data unavailable');return r.json()}).then(d=>{const $=id=>document.getElementById(id), ms=Object.keys(d.models), dates=[...new Set(Object.values(d.models).flat().map(r=>r.time.slice(0,10)))].sort(); $('status').textContent='Generated '+d.generated+' | Available: '+ms.join(', ')+' | Missing: '+d.requested.filter(m=>!ms.includes(m)).join(', ');for(const x of dates)$('day').add(new Option(x,x));for(const x of ms)$('model').add(new Option(x,x));function draw(){const rows=d.models[$('model').value].filter(r=>r.time.startsWith($('day').value));$('rows').replaceChildren();for(const r of rows){let tr=$('rows').insertRow();for(const v of [r.time.slice(11),[r.lift_agl,r.lift_msl],[r.lcl_msl],[r.wstar_kt,r.wstar_fpm],[r.wind_kt,r.wind_dir],[r.crosswind[35],r.crosswind[99]],r.rain_in,r.cape])tr.insertCell().textContent=Array.isArray(v)?v.map(x=>x??'—').join(' / '):v??'—';}}$('day').onchange=$('model').onchange=draw;draw()}).catch(e=>document.getElementById('status').textContent=e.message)</script></html>'''
if __name__=='__main__': build()
