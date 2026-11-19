"""Genera el cuadro de mando interactivo (HTML autónomo) para los coordinadores de logística.

Uso:  python src/build_dashboard.py [--inline]
Lee:  data/processed/*.csv  (generados por el notebook)
Crea: dashboard/index.html  (listo para GitHub Pages)
"""
from pathlib import Path
import json
import sys
import pandas as pd
from plotly.offline import get_plotlyjs, get_plotlyjs_version

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
OUT = ROOT / "dashboard" / "index.html"

kpis = pd.read_csv(PROC / "kpis.csv")
agg = pd.read_csv(PROC / "oferta_agregada.csv")
dist = pd.read_csv(PROC / "distribucion_precios.csv")
mapa = pd.read_csv(PROC / "mapa_muestra.csv")

data = {
    "kpis": kpis[["id_kpi", "kpi", "unidad", "meta", "operador", "accion"]].to_dict("records"),
    "agg": agg.fillna(0).to_dict("split"),
    "dist": dist.to_dict("split"),
    "mapa": mapa[["barrio", "zona", "segmento_atlas", "precio_noche", "dist_sede_km", "latitude", "longitude"]]
            .round({"dist_sede_km": 1, "latitude": 5, "longitude": 5}).to_dict("split"),
}
for v in ("agg", "dist", "mapa"):
    data[v].pop("index", None)

plotly_tag = (f"<script>{get_plotlyjs()}</script>" if "--inline" in sys.argv
              else f'<script src="https://cdn.plot.ly/plotly-{get_plotlyjs_version()}.min.js"></script>')

TEMPLATE = r"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Cuadro de mando · Oferta de alojamiento · Atlas Horizon Group</title>
__PLOTLY__
<style>
  :root { --navy:#1d3557; --amber:#c8873a; --green:#2a9d8f; --red:#c0392b; --ink:#1f2933; --muted:#5f6b7a; --line:#e3e7ec; }
  * { box-sizing:border-box; }
  body { margin:0; font-family:Inter, system-ui, -apple-system, Segoe UI, sans-serif; background:#f2f4f7; color:var(--ink); }
  header { background:var(--navy); color:#fff; padding:16px 24px; display:flex; flex-wrap:wrap; gap:8px 24px; align-items:baseline; }
  header h1 { font-size:20px; margin:0; } header span { color:#cfd8e3; font-size:13px; }
  .filters { background:#fff; border-bottom:1px solid var(--line); padding:12px 24px; display:flex; flex-wrap:wrap; gap:18px; align-items:center; position:sticky; top:0; z-index:5; }
  .filters label { font-size:11px; text-transform:uppercase; letter-spacing:.06em; color:var(--muted); display:block; margin-bottom:4px; }
  .chips { display:flex; gap:6px; flex-wrap:wrap; }
  .chip { border:1px solid var(--line); background:#fff; border-radius:16px; padding:5px 12px; font-size:13px; cursor:pointer; }
  .chip.on { background:var(--navy); border-color:var(--navy); color:#fff; }
  select, button.reset { font:inherit; font-size:13px; padding:5px 8px; border:1px solid var(--line); border-radius:6px; background:#fff; }
  button.reset { cursor:pointer; color:var(--muted); }
  main { padding:18px 24px 40px; max-width:1400px; margin:0 auto; }
  .kpis { display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:12px; margin-bottom:16px; }
  .kpi { background:#fff; border-radius:10px; padding:12px 14px; border-left:5px solid var(--green); }
  .kpi.ko { border-color:var(--red); } .kpi.na { border-color:#c5ccd6; }
  .kpi .id { font-size:11px; color:var(--muted); } .kpi .name { font-size:13px; font-weight:600; min-height:34px; }
  .kpi .val { font-size:26px; font-weight:700; } .kpi .meta { font-size:12px; color:var(--muted); }
  .kpi.ko .st { color:var(--red); font-weight:700; } .kpi .st { color:var(--green); font-weight:700; }
  .grid { display:grid; grid-template-columns:1fr 1fr; gap:16px; }
  .card { background:#fff; border-radius:10px; padding:14px 16px; min-width:0; }
  .card h2 { font-size:15px; margin:0 0 2px; color:var(--navy); } .card p { margin:0 0 6px; font-size:12px; color:var(--muted); }
  .wide { grid-column:1 / -1; }
  table { width:100%; border-collapse:collapse; font-size:13px; }
  th, td { padding:6px 8px; border-bottom:1px solid var(--line); text-align:right; } th:first-child, td:first-child { text-align:left; }
  th { font-size:11px; text-transform:uppercase; color:var(--muted); cursor:pointer; user-select:none; }
  td.bad { color:var(--red); font-weight:600; } td.good { color:var(--green); font-weight:600; }
  footer { font-size:12px; color:var(--muted); margin-top:18px; }
  @media (max-width:900px) { .grid { grid-template-columns:1fr; } }
</style></head>
<body>
<header>
  <h1>Oferta de alojamiento · Hub de Londres</h1>
  <span>Atlas Horizon Group · Coordinación de logística · Captura feb-2020 · Actualización mensual</span>
</header>
<div class="filters">
  <div><label>Segmento</label><div class="chips" id="f-seg"></div></div>
  <div><label>Zona</label><select id="f-zona"><option value="">Todo Londres</option><option>Inner London</option><option>Outer London</option></select></div>
  <div><label>Tipo de proveedor</label><select id="f-prov"><option value="">Todos</option><option>Particular</option><option>Multipropiedad</option><option>Profesional</option></select></div>
  <div><label>&nbsp;</label><button class="reset" id="reset">Restablecer filtros</button></div>
</div>
<main>
  <div class="kpis" id="kpis"></div>
  <div class="grid">
    <div class="card"><h2>¿Dónde hay más oferta apta?</h2><p>Top 15 barrios · alojamientos homologables, a ≤ 5 km de la sede y a más distancia</p><div id="c-barrios"></div></div>
    <div class="card"><h2>Precio frente a distancia a la sede</h2><p>Precio medio de la oferta homologable por barrio · tamaño = nº de alojamientos aptos</p><div id="c-precio"></div></div>
    <div class="card"><h2>Distribución de precios</h2><p>Oferta homologable por tramos de 25 £ (el último tramo agrupa ≥ 500 £)</p><div id="c-dist"></div></div>
    <div class="card"><h2>Mapa de la oferta apta</h2><p>Muestra de 3.000 alojamientos homologables · círculo = 5 km de la sede</p><div id="c-mapa"></div></div>
    <div class="card wide"><h2>Detalle por barrio</h2><p>Haz clic en las columnas para ordenar. El precio en rojo supera la meta de precio por noche.</p><div id="t-barrios"></div></div>
  </div>
  <footer>Fuente: Inside Airbnb (Londres, febrero 2020), CC BY 4.0 · Modelo y KPIs: data warehouse Atlas Horizon (DuckDB). Atlas Horizon Group es una empresa ficticia; la sede y las metas son supuestos del proyecto.</footer>
</main>
<script>
const D = __DATA__;
const rows = (t) => t.data.map(r => Object.fromEntries(t.columns.map((c, i) => [c, r[i]])));
const AGG = rows(D.agg), DIST = rows(D.dist), MAPA = rows(D.mapa);
const SEGS = ["Base privada", "Hotel", "Habitación individual", "Compartido"];
const COL = {"Base privada":"#1d3557","Hotel":"#c8873a","Habitación individual":"#2a9d8f","Compartido":"#8d99ae"};
const SEDE = [51.5013, -0.1755];
const META = Object.fromEntries(D.kpis.map(k => [k.id_kpi, k]));
const CFG = {displayModeBar:false, responsive:true};
const LAYOUT = {margin:{l:10,r:10,t:10,b:10}, font:{family:"Inter, system-ui, sans-serif", size:12}, plot_bgcolor:"#fff", paper_bgcolor:"#fff", height:340, legend:{orientation:"h", y:1.12}};
const nf = (x, d=0) => x == null || isNaN(x) ? "—" : x.toLocaleString("es-ES", {minimumFractionDigits:d, maximumFractionDigits:d});
const sum = (a, f) => a.reduce((s, r) => s + (+r[f] || 0), 0);

let state = {segs: new Set(SEGS), zona: "", prov: ""};
const segBox = document.getElementById("f-seg");
SEGS.forEach(s => {
  const b = document.createElement("span"); b.className = "chip on"; b.textContent = s;
  b.onclick = () => { if (state.segs.has(s) && state.segs.size > 1) state.segs.delete(s); else state.segs.add(s); render(); };
  segBox.appendChild(b);
});
document.getElementById("f-zona").onchange = e => { state.zona = e.target.value; render(); };
document.getElementById("f-prov").onchange = e => { state.prov = e.target.value; render(); };
document.getElementById("reset").onclick = () => {
  state = {segs: new Set(SEGS), zona: "", prov: ""};
  document.getElementById("f-zona").value = ""; document.getElementById("f-prov").value = ""; render();
};
const pass = r => state.segs.has(r.segmento_atlas) && (!state.zona || r.zona === state.zona) && (!state.prov || r.tipo_proveedor === state.prov);

function kpiCard(id, val, fmtVal) {
  const k = META[id];
  let cls = "na", st = "Sin datos";
  if (val != null && !isNaN(val)) {
    const ok = k.operador === ">=" ? val >= k.meta : val <= k.meta;
    cls = ok ? "" : "ko"; st = ok ? "✔ Cumple" : "✖ No cumple";
  }
  const unidad = k.unidad === "£" ? " £" : " " + k.unidad;
  return `<div class="kpi ${cls}" title="${cls === 'ko' ? 'Acción: ' + k.accion : ''}"><div class="id">${id}</div><div class="name">${k.kpi}</div>
    <div class="val">${fmtVal}</div><div class="meta">Meta ${k.operador} ${nf(k.meta)}${unidad} · <span class="st">${st}</span></div></div>`;
}

function render() {
  [...segBox.children].forEach(c => c.classList.toggle("on", state.segs.has(c.textContent)));
  const A = AGG.filter(pass);
  const H = sum(A, "homologables");
  const bp = A.filter(r => r.segmento_atlas === "Base privada");
  const k1 = 100 * H / sum(A, "alojamientos");
  const k2 = bp.length ? sum(bp, "suma_precio_homologables") / sum(bp, "homologables") : NaN;
  const k3 = sum(A, "suma_dias_homologables") / H;
  const k4 = 100 * sum(A, "homologables_5km") / H;
  const k5 = 100 * sum(A.filter(r => r.tipo_proveedor === "Profesional"), "homologables") / H;
  document.getElementById("kpis").innerHTML =
    kpiCard("PI_ALO_01", k1, nf(k1, 1) + " %") + kpiCard("PI_ALO_02", k2, isNaN(k2) ? "—" : nf(k2) + " £") +
    kpiCard("PI_ALO_03", k3, nf(k3) + " días") + kpiCard("PI_ALO_04", k4, nf(k4, 1) + " %") +
    kpiCard("PI_ALO_05", k5, nf(k5, 1) + " %");

  // agregación por barrio
  const byB = {};
  A.forEach(r => {
    const b = byB[r.barrio] ??= {barrio:r.barrio, zona:r.zona, lat:r.lat_centro, lon:r.lon_centro, oferta:0, hom:0, h5:0, sp:0, sd:0, bpH:0, bpS:0};
    b.oferta += r.alojamientos; b.hom += r.homologables; b.h5 += r.homologables_5km;
    b.sp += r.suma_precio_homologables; b.sd += r.suma_dias_homologables;
    if (r.segmento_atlas === "Base privada") { b.bpH += r.homologables; b.bpS += r.suma_precio_homologables; }
  });
  const B = Object.values(byB).map(b => {
    const p1 = b.lat * Math.PI/180, p2 = SEDE[0] * Math.PI/180, dl = (SEDE[1] - b.lon) * Math.PI/180;
    const a = Math.sin((p2-p1)/2)**2 + Math.cos(p1)*Math.cos(p2)*Math.sin(dl/2)**2;
    return {...b, dist: 2*6371*Math.asin(Math.sqrt(a)), precio: b.hom ? b.sp/b.hom : NaN, precioBP: b.bpH ? b.bpS/b.bpH : NaN};
  });

  const top = [...B].sort((a, b) => b.hom - a.hom).slice(0, 15).reverse();
  Plotly.react("c-barrios", [
    {type:"bar", orientation:"h", y:top.map(b=>b.barrio), x:top.map(b=>b.h5), name:"≤ 5 km de la sede", marker:{color:"#1d3557"}},
    {type:"bar", orientation:"h", y:top.map(b=>b.barrio), x:top.map(b=>b.hom-b.h5), name:"> 5 km", marker:{color:"#c5ccd6"}},
  ], {...LAYOUT, barmode:"stack", height:380, margin:{l:150,r:10,t:10,b:30}}, CFG);

  const Bp = B.filter(b => b.hom >= 50);
  Plotly.react("c-precio", [{
    type:"scatter", mode:"markers", x:Bp.map(b=>b.dist), y:Bp.map(b=>b.precio), text:Bp.map(b=>b.barrio),
    customdata:Bp.map(b=>b.hom),
    marker:{size:Bp.map(b=>Math.max(8, Math.sqrt(b.hom)*0.9)), color:Bp.map(b=>b.zona==="Inner London"?"#1d3557":"#8d99ae"), opacity:.75, line:{color:"#fff", width:1}},
    hovertemplate:"<b>%{text}</b><br>%{x:.1f} km · %{y:.0f} £/noche<br>%{customdata} aptos<extra></extra>",
  }], {...LAYOUT, height:380, margin:{l:50,r:10,t:10,b:45}, showlegend:false,
       xaxis:{title:"Distancia a la sede (km)", gridcolor:"#eef1f4"}, yaxis:{title:"£/noche (medio, homologables)", gridcolor:"#eef1f4"},
       shapes:[{type:"rect", x0:0, x1:5, y0:0, y1:1, yref:"paper", fillcolor:"#2a9d8f", opacity:.07, line:{width:0}}]}, CFG);

  const Dd = DIST.filter(r => state.segs.has(r.segmento_atlas) && (!state.zona || r.zona === state.zona));
  const tramos = [...new Set(DIST.map(r => r.tramo_precio))].sort((a,b)=>a-b);
  Plotly.react("c-dist", SEGS.filter(s => state.segs.has(s)).map(s => ({
    type:"bar", name:s, marker:{color:COL[s]}, x:tramos.map(t => t === 500 ? "500+" : String(t)),
    y:tramos.map(t => sum(Dd.filter(r => r.segmento_atlas === s && r.tramo_precio === t), "alojamientos")),
  })), {...LAYOUT, barmode:"stack", margin:{l:45,r:10,t:10,b:45},
       xaxis:{title:"£/noche (inicio del tramo)", type:"category"}, yaxis:{title:"Alojamientos", gridcolor:"#eef1f4"}}, CFG);

  const M = MAPA.filter(r => state.segs.has(r.segmento_atlas) && (!state.zona || r.zona === state.zona));
  const circle = [...Array(81).keys()].map(i => { const t = i/80*2*Math.PI;
    return [SEDE[0] + 5/111*Math.sin(t), SEDE[1] + 5/(111*Math.cos(SEDE[0]*Math.PI/180))*Math.cos(t)]; });
  Plotly.react("c-mapa", [
    ...SEGS.filter(s => state.segs.has(s)).map(s => { const m = M.filter(r => r.segmento_atlas === s);
      return {type:"scattermap", name:s, lat:m.map(r=>r.latitude), lon:m.map(r=>r.longitude), mode:"markers",
        marker:{size:6, color:COL[s], opacity:.65}, text:m.map(r=>`${r.barrio} · ${r.precio_noche} £ · ${r.dist_sede_km} km`), hoverinfo:"text"}; }),
    {type:"scattermap", name:"Radio 5 km", lat:circle.map(c=>c[0]), lon:circle.map(c=>c[1]), mode:"lines", line:{color:"#c0392b", width:2}, hoverinfo:"skip"},
    {type:"scattermap", name:"Sede", lat:[SEDE[0]], lon:[SEDE[1]], mode:"markers", marker:{size:14, color:"#c0392b"}, hoverinfo:"name"},
  ], {...LAYOUT, height:380, map:{style:"carto-positron", center:{lat:51.51, lon:-0.13}, zoom:9.3}}, CFG);

  renderTable(B);
}

let sortKey = "hom", sortDir = -1;
function renderTable(B) {
  const cols = [["barrio","Barrio"],["zona","Zona"],["oferta","Oferta"],["hom","Homologables"],["pct","% apto"],["h5","≤ 5 km"],["dist","Dist. sede (km)"],["precioBP","Base privada (£)"],["dias","Disponib. (días)"]];
  const R = B.map(b => ({...b, pct: b.oferta ? 100*b.hom/b.oferta : 0, dias: b.hom ? b.sd/b.hom : NaN}))
             .sort((a, b) => (a[sortKey] > b[sortKey] ? 1 : a[sortKey] < b[sortKey] ? -1 : 0) * sortDir);
  const meta = META.PI_ALO_02.meta;
  const fmtCell = (k, v) => k === "barrio" || k === "zona" ? v : k === "pct" || k === "dist" ? nf(v, 1) : nf(v);
  document.getElementById("t-barrios").innerHTML = `<table><thead><tr>${cols.map(([k,l]) =>
    `<th data-k="${k}">${l}${k===sortKey ? (sortDir>0?" ▲":" ▼") : ""}</th>`).join("")}</tr></thead><tbody>${R.map(r =>
    `<tr>${cols.map(([k]) => `<td class="${k==='precioBP' && !isNaN(r[k]) ? (r[k] > meta ? 'bad' : 'good') : ''}">${fmtCell(k, r[k])}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
  document.querySelectorAll("#t-barrios th").forEach(th => th.onclick = () => {
    const k = th.dataset.k; sortDir = k === sortKey ? -sortDir : -1; sortKey = k; renderTable(B);
  });
}
render();
</script>
</body></html>"""

html = (TEMPLATE.replace("__PLOTLY__", plotly_tag)
                .replace("__DATA__", json.dumps(data, ensure_ascii=False, separators=(",", ":"))))
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(html, encoding="utf-8")
print(f"Dashboard generado: {OUT.relative_to(ROOT)} ({OUT.stat().st_size/1024:.0f} KB)")
