"""Genera el informe de negocio (HTML) para la Dirección de Operaciones y Logística.

Uso:  python src/build_report.py [--inline]
Lee:  data/processed/*.csv  (generados por el notebook)
Crea: reports/informe_oferta_alojamiento.html
"""
from pathlib import Path
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sys
from plotly.offline import get_plotlyjs, get_plotlyjs_version

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
OUT = ROOT / "reports" / "informe_oferta_alojamiento.html"

# Identidad de Atlas Horizon (colores tomados del logo)
NAVY, COPPER, OK, KO = "#132a43", "#b8763e", "#3d7a5a", "#b4432f"
SAND, LINE, MUTED = "#a59d8f", "#e6dfd3", "#6b6558"
SEG_COL = {"Base privada": NAVY, "Hotel": COPPER, "Habitación individual": "#5b8a8c", "Compartido": SAND}
FONT = "Archivo, 'Helvetica Neue', Arial, sans-serif"

SEDE = (51.5013, -0.1755)
RADIO_KM = 5            # mismo radio que el KPI PI_ALO_04
MIN_BP_RADIO = 300      # bases privadas aptas dentro del radio para recomendar un barrio
PLOT_CFG = {"displayModeBar": False, "responsive": True}
OPS = {">=": "≥", "<=": "≤"}

kpis = pd.read_csv(PROC / "kpis.csv")
agg = pd.read_csv(PROC / "oferta_agregada.csv")
mapa = pd.read_csv(PROC / "mapa_muestra.csv")


def haversine(lat, lon, lat0=SEDE[0], lon0=SEDE[1]):
    p1, p2 = np.radians(lat), np.radians(lat0)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lon0 - lon) / 2) ** 2
    return 2 * 6371 * np.arcsin(np.sqrt(a))


def fmt(x, dec=0):
    return f"{x:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fig_html(fig, h=380):
    fig.update_layout(height=h, margin=dict(l=10, r=10, t=30, b=10), font=dict(family=FONT, color=NAVY, size=12),
                      plot_bgcolor="#fffdf9", paper_bgcolor="#fffdf9", legend_title_text="")
    fig.update_xaxes(gridcolor="#efe9de", zerolinecolor=LINE)
    fig.update_yaxes(gridcolor="#efe9de", zerolinecolor=LINE)
    return fig.to_html(full_html=False, include_plotlyjs=False, config=PLOT_CFG)


# ---------------------------------------------------------------- cálculos
total = agg["alojamientos"].sum()
homol = agg["homologables"].sum()

seg = (agg.groupby("segmento_atlas")[["alojamientos", "homologables", "suma_precio_homologables"]].sum()
          .assign(pct=lambda d: 100 * d.homologables / d.alojamientos,
                  precio=lambda d: d.suma_precio_homologables / d.homologables)
          .sort_values("homologables", ascending=False))

barrio = (agg.groupby(["barrio", "zona", "lat_centro", "lon_centro"])
             [["alojamientos", "homologables", "homologables_5km"]].sum().reset_index())
bp = (agg[agg.segmento_atlas == "Base privada"].groupby("barrio")
         [["homologables", "homologables_5km", "suma_precio_homologables"]].sum())
barrio = barrio.merge(pd.DataFrame({
    "precio_base_privada": bp.suma_precio_homologables / bp.homologables,
    "bases_privadas": bp.homologables,
    "bases_privadas_radio": bp.homologables_5km,
}), left_on="barrio", right_index=True, how="left")
barrio["dist_sede_km"] = haversine(barrio.lat_centro, barrio.lon_centro)
barrio["pct_radio"] = 100 * barrio.bases_privadas_radio / barrio.bases_privadas

# Barrios recomendados: oferta suficiente de bases privadas aptas DENTRO del radio del KPI y precio ≤ meta
META_PRECIO = float(kpis.loc[kpis.id_kpi == "PI_ALO_02", "meta"].iloc[0])
optimos = (barrio[(barrio.bases_privadas_radio >= MIN_BP_RADIO) & (barrio.precio_base_privada <= META_PRECIO)]
           .sort_values("bases_privadas_radio", ascending=False))
caros_cerca = barrio[(barrio.dist_sede_km <= 3) & (barrio.precio_base_privada > META_PRECIO)].sort_values("dist_sede_km")

prov = agg[agg.homologables > 0].groupby("tipo_proveedor").homologables.sum()
prov_pct = 100 * prov / prov.sum()

k = kpis.set_index("id_kpi")
n_ok = (kpis.estado == "Cumple").sum()

# ---------------------------------------------------------------- gráficos
f1 = go.Figure()
f1.add_bar(y=seg.index, x=seg.alojamientos - seg.homologables, name="No apta", orientation="h", marker_color=LINE)
f1.add_bar(y=seg.index, x=seg.homologables, name="Homologable", orientation="h", marker_color=NAVY,
           text=[f"{fmt(p,1)} %" for p in seg.pct], textposition="inside")
f1.update_layout(uniformtext_minsize=10, uniformtext_mode="hide", barmode="stack", xaxis_title="Alojamientos",
                 yaxis=dict(autorange="reversed"), legend=dict(orientation="h", y=1.12))

b2 = barrio.dropna(subset=["precio_base_privada"]).query("bases_privadas >= 100").copy()
b2["recomendado"] = np.where(b2.barrio.isin(optimos.barrio), "Recomendado", b2.zona)
f2 = px.scatter(b2, x="dist_sede_km", y="precio_base_privada", size="bases_privadas", color="recomendado",
                hover_name="barrio", size_max=38,
                color_discrete_map={"Recomendado": COPPER, "Inner London": NAVY, "Outer London": SAND},
                category_orders={"recomendado": ["Recomendado", "Inner London", "Outer London"]},
                labels={"dist_sede_km": "Distancia del centro del barrio a la sede (km)",
                        "precio_base_privada": "£/noche · base privada"},
                custom_data=["bases_privadas", "pct_radio"])
f2.update_traces(hovertemplate="<b>%{hovertext}</b><br>%{x:.1f} km · %{y:.0f} £/noche<br>"
                               "%{customdata[0]} bases privadas aptas · %{customdata[1]:.0f} % a ≤ 5 km<extra></extra>")
f2.add_hline(y=META_PRECIO, line_dash="dash", line_color=KO, annotation_text=f"Meta ≤ {META_PRECIO:.0f} £",
             annotation_position="top right", annotation_font_color=KO)
f2.add_vrect(x0=0, x1=RADIO_KM, fillcolor=COPPER, opacity=0.07, line_width=0)
for _, r in optimos.iterrows():
    f2.add_annotation(x=r.dist_sede_km, y=r.precio_base_privada, text=r.barrio, showarrow=False, yshift=-18,
                      font=dict(size=11, color=COPPER))
f2.update_layout(legend=dict(orientation="h", y=1.12))

f3 = px.scatter_map(mapa, lat="latitude", lon="longitude", color="segmento_atlas", hover_name="barrio",
                    hover_data={"precio_noche": True, "dist_sede_km": ":.1f", "latitude": False, "longitude": False},
                    color_discrete_map=SEG_COL, category_orders={"segmento_atlas": list(SEG_COL)},
                    zoom=10, map_style="carto-positron", center={"lat": 51.51, "lon": -0.13}, opacity=0.65)
f3.add_trace(go.Scattermap(lat=[SEDE[0]], lon=[SEDE[1]], mode="markers+text", text=["Sede"], textposition="top right",
                           marker=dict(size=16, color=KO), name="Sede de briefing"))
circle = [(SEDE[0] + RADIO_KM / 111 * np.sin(t), SEDE[1] + RADIO_KM / (111 * np.cos(np.radians(SEDE[0]))) * np.cos(t))
          for t in np.linspace(0, 2 * np.pi, 80)]
f3.add_trace(go.Scattermap(lat=[c[0] for c in circle], lon=[c[1] for c in circle], mode="lines",
                           line=dict(color=KO, width=2), name=f"Radio {RADIO_KM} km", hoverinfo="skip"))
f3.update_layout(legend=dict(orientation="h", y=1.08))
f3.update_traces(marker=dict(size=6), selector=dict(mode="markers"))


# ---------------------------------------------------------------- HTML
# Por defecto se carga plotly.js desde su CDN (fichero ligero). Con --inline se incrusta (uso offline).
PLOTLY_TAG = (f"<script>{get_plotlyjs()}</script>" if "--inline" in sys.argv
              else f'<script src="https://cdn.plot.ly/plotly-{get_plotlyjs_version()}.min.js"></script>')


def kpi_card(row):
    ok = row.estado == "Cumple"
    unidad = row.unidad
    val = (f"{fmt(row.valor, 0)} £" if unidad == "£" else f"{fmt(row.valor, 0)} días" if unidad.startswith("días")
           else f"{fmt(row.valor, 1)} {unidad}")
    meta = f"{OPS[row.operador]} {fmt(row.meta)} {unidad}"
    return f"""
    <div class="kpi {'ok' if ok else 'ko'}">
      <div class="kpi-id">{row.id_kpi}</div>
      <div class="kpi-name">{row.kpi}</div>
      <div class="kpi-val">{val}</div>
      <div class="kpi-meta">Meta {meta}</div>
      <div class="kpi-st">{'Cumple' if ok else 'No cumple'}</div>
      {'' if ok else f'<div class="kpi-acc">Acción: {row.accion[0].lower() + row.accion[1:]}</div>'}
    </div>"""


optimos_txt = " y ".join(
    f"<b>{r.barrio}</b> ({fmt(r.bases_privadas_radio)} bases privadas aptas a ≤ {RADIO_KM} km, {fmt(r.precio_base_privada)} £ de media)"
    for _, r in optimos.iterrows())
fuera = optimos[optimos.dist_sede_km > RADIO_KM]
fuera_txt = "".join(
    f" El centro de {r.barrio} está a {fmt(r.dist_sede_km,1)} km, pero el {fmt(r.pct_radio)} % de sus bases privadas "
    f"aptas queda dentro del radio." for _, r in fuera.iterrows())
caros_txt = " y ".join(f"{r.barrio} ({fmt(r.precio_base_privada)} £)" for _, r in caros_cerca.iterrows())
seg_rows = "".join(
    f"<tr><td>{s}</td><td>{fmt(r.alojamientos)}</td><td>{fmt(r.homologables)}</td>"
    f"<td>{fmt(r.pct,1)} %</td><td>{fmt(r.precio)} £</td></tr>" for s, r in seg.iterrows())

html = f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Informe · Oferta de alojamiento en Londres · Atlas Horizon Group</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;700&family=Newsreader:opsz,wght@6..72,500;6..72,600&display=swap" rel="stylesheet">
{PLOTLY_TAG}
<style>
  :root {{ --navy:{NAVY}; --copper:{COPPER}; --ok:{OK}; --ko:{KO}; --line:{LINE}; --muted:{MUTED};
           --paper:#f7f4ee; --card:#fffdf9; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; font-family:{FONT}; color:var(--navy); background:var(--paper); line-height:1.55; font-size:15.5px; }}
  .wrap {{ max-width:1040px; margin:0 auto; padding:0 24px; }}
  header {{ padding:28px 0 22px; border-bottom:1px solid var(--line); background:var(--card); }}
  header img {{ height:46px; mix-blend-mode:multiply; display:block; margin-bottom:22px; }}
  .doc-type {{ font-size:13px; color:var(--copper); font-weight:600; margin:0; }}
  h1, h2 {{ font-family:Newsreader, Georgia, serif; font-weight:600; letter-spacing:-.01em; }}
  h1 {{ margin:2px 0 8px; font-size:36px; line-height:1.15; }}
  header p.meta {{ margin:0; color:var(--muted); font-size:14px; }}
  section {{ background:var(--card); border:1px solid var(--line); border-radius:6px; padding:28px; margin:22px 0; }}
  h2 {{ margin:0 0 6px; font-size:25px; }}
  h2 .n {{ color:var(--copper); margin-right:6px; }}
  .lead {{ color:var(--muted); margin:0 0 18px; }}
  .summary {{ padding-left:20px; }} .summary li {{ margin:8px 0; }} .summary li::marker {{ color:var(--copper); }}
  .kpis {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:12px; }}
  .kpi {{ border:1px solid var(--line); border-radius:6px; padding:14px; background:#fff; }}
  .kpi-id {{ font-size:11px; color:var(--muted); letter-spacing:.04em; }}
  .kpi-name {{ font-size:13px; font-weight:600; min-height:38px; }}
  .kpi-val {{ font-size:28px; font-weight:700; margin:6px 0 2px; font-variant-numeric:tabular-nums; }}
  .kpi.ko .kpi-val {{ color:var(--ko); }}
  .kpi-meta {{ font-size:12.5px; color:var(--muted); }}
  .kpi-st {{ font-size:12.5px; font-weight:600; margin-top:6px; color:var(--ok); }}
  .kpi-st::before {{ content:""; display:inline-block; width:8px; height:8px; border-radius:50%; background:currentColor; margin-right:6px; }}
  .kpi.ko .kpi-st {{ color:var(--ko); }}
  .kpi-acc {{ font-size:12.5px; margin-top:8px; padding-top:8px; border-top:1px solid var(--line); }}
  table {{ width:100%; border-collapse:collapse; font-size:14px; margin-top:12px; font-variant-numeric:tabular-nums; }}
  th, td {{ text-align:left; padding:8px 10px; border-bottom:1px solid var(--line); }}
  th {{ font-size:12.5px; font-weight:600; color:var(--muted); }}
  .callout {{ border-left:3px solid var(--copper); background:#faf4ea; padding:12px 16px; margin-top:16px; }}
  .rec {{ display:grid; grid-template-columns:32px 1fr; gap:10px; margin:14px 0; }}
  .rec .n {{ font-family:Newsreader, Georgia, serif; font-size:24px; font-weight:600; color:var(--copper); line-height:1.1; }}
  .rec small {{ color:var(--muted); }}
  footer {{ color:var(--muted); font-size:12.5px; padding:8px 0 40px; }}
  @media (max-width:600px) {{ h1 {{ font-size:28px; }} section {{ padding:20px; }} }}
</style></head>
<body>
<header><div class="wrap">
  <img src="../docs/img/logo.png" alt="Atlas Horizon Group">
  <p class="doc-type">Informe mensual de operaciones</p>
  <h1>Oferta de alojamiento en el hub de Londres</h1>
  <p class="meta">Para: Dirección de Operaciones y Logística · Datos: captura de febrero de 2020 · {fmt(total)} alojamientos analizados</p>
</div></header>
<main class="wrap">

<section>
  <h2>Resumen ejecutivo</h2>
  <ul class="summary">
    <li><b>{fmt(homol)} alojamientos</b> ({fmt(k.loc['PI_ALO_01','valor'],1)} %) cumplen nuestros estándares. Hay oferta apta de sobra.</li>
    <li><b>Precio:</b> la base privada homologada cuesta de media <b>{fmt(k.loc['PI_ALO_02','valor'])} £/noche</b>, por encima de la meta de {fmt(META_PRECIO)} £.</li>
    <li><b>Ubicación:</b> solo el <b>{fmt(k.loc['PI_ALO_04','valor'],1)} %</b> de la oferta apta está a ≤ {RADIO_KM} km de la sede de briefing (meta: 50 %).</li>
    <li><b>Oportunidad:</b> {optimos_txt} combinan cercanía y precio dentro de la meta.</li>
  </ul>
</section>

<section>
  <h2>Indicadores clave</h2>
  <p class="lead">{n_ok} de {len(kpis)} indicadores en meta. Los que no cumplen llevan la acción prevista.</p>
  <div class="kpis">{''.join(kpi_card(r) for r in kpis.itertuples())}</div>
</section>

<section>
  <h2><span class="n">1</span>¿Cuánta oferta es apta para Atlas?</h2>
  <p class="lead">Un alojamiento es <i>homologable</i> si tiene precio válido, estancia mínima ≤ 7 noches, ≥ 30 días disponibles, ≥ 5 reseñas y actividad en los últimos 12 meses.</p>
  {fig_html(f1, 260)}
  <table><tr><th>Segmento</th><th>Oferta</th><th>Homologables</th><th>% apto</th><th>Precio medio apto</th></tr>{seg_rows}</table>
  <div class="callout">La oferta para clientes (base privada y hotel) es amplia. El cuello de botella no es la <b>cantidad</b>, sino el <b>precio</b> y la <b>ubicación</b>.</div>
</section>

<section>
  <h2><span class="n">2</span>Precio frente a distancia a la sede</h2>
  <p class="lead">Cada burbuja es un barrio, situado según la distancia de su centro a la sede. El tamaño indica cuántas bases privadas aptas tiene. La franja sombreada marca el radio de {RADIO_KM} km.</p>
  {fig_html(f2, 440)}
  <div class="callout">Los barrios más próximos a la sede son también los más caros: {caros_txt}. En cobre, los barrios recomendados: al menos {MIN_BP_RADIO} bases privadas aptas dentro del radio y precio medio por debajo de la meta.{fuera_txt}</div>
</section>

<section>
  <h2><span class="n">3</span>Dónde está la oferta apta</h2>
  <p class="lead">Muestra de 3.000 alojamientos homologables. El círculo marca el radio de {RADIO_KM} km alrededor de la sede.</p>
  {fig_html(f3, 520)}
</section>

<section>
  <h2><span class="n">4</span>Riesgo de proveedor</h2>
  <p class="lead">Reparto de la oferta homologable según el tipo de anfitrión.</p>
  <table><tr><th>Tipo de proveedor</th><th>Alojamientos aptos</th><th>% del total apto</th></tr>
  {''.join(f"<tr><td>{t}</td><td>{fmt(v)}</td><td>{fmt(prov_pct[t],1)} %</td></tr>" for t, v in prov.sort_values(ascending=False).items())}
  </table>
  <div class="callout">La dependencia de proveedores profesionales ({fmt(k.loc['PI_ALO_05','valor'],1)} %) está dentro de la meta (≤ 30 %). El mayor peso está en <b>{prov.idxmax().lower()}</b> ({fmt(prov_pct.max(),1)} %): una cartera repartida entre muchos anfitriones pequeños diversifica el riesgo, pero exige más control de calidad.</div>
</section>

<section>
  <h2>Recomendaciones</h2>
  <div class="rec"><div class="n">1</div><div><b>Priorizar {' y '.join(optimos.barrio)} para las bases privadas de clientes.</b><br><small>Precio medio por debajo de la meta y al menos {MIN_BP_RADIO} bases privadas aptas a ≤ {RADIO_KM} km de la sede. Responsable: Coordinación de logística.</small></div></div>
  <div class="rec"><div class="n">2</div><div><b>Negociar tarifas por volumen</b> con los proveedores multipropiedad de {' y '.join(caros_cerca.barrio)} para las estancias VIP que exigen máxima cercanía.<br><small>Responsable: Compras.</small></div></div>
  <div class="rec"><div class="n">3</div><div><b>Incluir el traslado al briefing</b> en el paquete cuando el alojamiento esté a más de {RADIO_KM} km, en lugar de pagar el sobrecoste del centro.<br><small>Responsable: Operaciones.</small></div></div>
</section>

<footer>
  Fuente: Inside Airbnb (Londres, febrero de 2020), licencia CC BY 4.0. Datos procesados en el data warehouse de Atlas Horizon (DuckDB).
  Atlas Horizon Group es una empresa ficticia; la sede de briefing y las metas son supuestos del proyecto.
</footer>
</main>
<script>document.fonts && document.fonts.ready.then(() => document.querySelectorAll(".plotly-graph-div").forEach(d => Plotly.Plots.resize(d)));</script>
</body></html>"""

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(html, encoding="utf-8")
print(f"Informe generado: {OUT.relative_to(ROOT)} ({OUT.stat().st_size/1024:.0f} KB)")
