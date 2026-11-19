"""Genera el informe de negocio (HTML) para la Dirección de Operaciones y Logística.

Uso:  python src/build_report.py
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

NAVY, AMBER, GREEN, RED, GREY = "#1d3557", "#c8873a", "#2a9d8f", "#c0392b", "#8d99ae"
SEDE = (51.5013, -0.1755)
PLOT_CFG = {"displayModeBar": False, "responsive": True}

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
    fig.update_layout(height=h, margin=dict(l=10, r=10, t=30, b=10), font_family="Inter, system-ui, sans-serif",
                      plot_bgcolor="white", paper_bgcolor="white", legend_title_text="")
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
         [["homologables", "suma_precio_homologables"]].sum())
barrio = barrio.merge((bp.suma_precio_homologables / bp.homologables).rename("precio_base_privada"),
                      left_on="barrio", right_index=True, how="left")
barrio = barrio.merge(bp.homologables.rename("bases_privadas"), left_on="barrio", right_index=True, how="left")
barrio["dist_sede_km"] = haversine(barrio.lat_centro, barrio.lon_centro)

# Barrios "óptimos": cerca de la sede (≤ 6 km), base privada ≤ meta y oferta suficiente
META_PRECIO = float(kpis.loc[kpis.id_kpi == "PI_ALO_02", "meta"].iloc[0])
optimos = (barrio[(barrio.dist_sede_km <= 6) & (barrio.precio_base_privada <= META_PRECIO)
                  & (barrio.bases_privadas >= 300)]
           .sort_values("dist_sede_km"))
caros_cerca = barrio[(barrio.dist_sede_km <= 3) & (barrio.precio_base_privada > META_PRECIO)].sort_values("dist_sede_km")

prov = agg[agg.homologables > 0].groupby("tipo_proveedor").homologables.sum()
prov_pct = 100 * prov / prov.sum()

k = kpis.set_index("id_kpi")
n_ok = (kpis.estado == "Cumple").sum()

# ---------------------------------------------------------------- gráficos
f1 = go.Figure()
f1.add_bar(y=seg.index, x=seg.alojamientos - seg.homologables, name="No apta", orientation="h", marker_color="#dfe3ea")
f1.add_bar(y=seg.index, x=seg.homologables, name="Homologable", orientation="h", marker_color=NAVY,
           text=[f"{fmt(p,1)} %" for p in seg.pct], textposition="inside")
f1.update_layout(uniformtext_minsize=10, uniformtext_mode="hide", barmode="stack", xaxis_title="Alojamientos", yaxis=dict(autorange="reversed"),
                 legend=dict(orientation="h", y=1.12))

b2 = barrio.dropna(subset=["precio_base_privada"]).query("bases_privadas >= 100")
f2 = px.scatter(b2, x="dist_sede_km", y="precio_base_privada", size="bases_privadas", color="zona",
                hover_name="barrio", size_max=38, color_discrete_map={"Inner London": NAVY, "Outer London": GREY},
                labels={"dist_sede_km": "Distancia a la sede (km)", "precio_base_privada": "£/noche · base privada"},
                custom_data=["bases_privadas"])
f2.update_traces(hovertemplate="<b>%{hovertext}</b><br>%{x:.1f} km · %{y:.0f} £/noche<br>%{customdata[0]} bases privadas aptas<extra></extra>")
f2.add_hline(y=META_PRECIO, line_dash="dash", line_color=RED, annotation_text=f"Meta ≤ {META_PRECIO:.0f} £",
             annotation_position="top right")
f2.add_vrect(x0=0, x1=6, fillcolor=GREEN, opacity=0.06, line_width=0)
for _, r in optimos.iterrows():
    f2.add_annotation(x=r.dist_sede_km, y=r.precio_base_privada, text=r.barrio, showarrow=False, yshift=-16,
                      font=dict(size=10, color=GREEN))
f2.update_layout(legend=dict(orientation="h", y=1.12))

f3 = px.scatter_map(mapa, lat="latitude", lon="longitude", color="segmento_atlas", hover_name="barrio",
                    hover_data={"precio_noche": True, "dist_sede_km": ":.1f", "latitude": False, "longitude": False},
                    color_discrete_sequence=[NAVY, AMBER, GREEN, RED], zoom=10, map_style="carto-positron",
                    center={"lat": 51.51, "lon": -0.13}, opacity=0.6)
f3.add_trace(go.Scattermap(lat=[SEDE[0]], lon=[SEDE[1]], mode="markers+text", text=["Sede"], textposition="top right",
                           marker=dict(size=16, color=RED), name="Sede de briefing"))
circle = [(SEDE[0] + 5 / 111 * np.sin(t), SEDE[1] + 5 / (111 * np.cos(np.radians(SEDE[0]))) * np.cos(t))
          for t in np.linspace(0, 2 * np.pi, 80)]
f3.add_trace(go.Scattermap(lat=[c[0] for c in circle], lon=[c[1] for c in circle], mode="lines",
                           line=dict(color=RED, width=2), name="Radio 5 km", hoverinfo="skip"))
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
    meta = f"{row.operador} {fmt(row.meta)} {unidad}" if unidad != "£" else f"{row.operador} {fmt(row.meta)} £"
    return f"""
    <div class="kpi {'ok' if ok else 'ko'}">
      <div class="kpi-id">{row.id_kpi}</div>
      <div class="kpi-name">{row.kpi}</div>
      <div class="kpi-val">{val}</div>
      <div class="kpi-meta">Meta {meta} · <b>{'✔ Cumple' if ok else '✖ No cumple'}</b></div>
      {'' if ok else f'<div class="kpi-acc">→ {row.accion}</div>'}
    </div>"""


optimos_txt = ", ".join(f"<b>{r.barrio}</b> ({fmt(r.dist_sede_km,1)} km, {fmt(r.precio_base_privada)} £)"
                        for _, r in optimos.iterrows())
caros_txt = ", ".join(f"{r.barrio} ({fmt(r.precio_base_privada)} £)" for _, r in caros_cerca.iterrows())
seg_rows = "".join(
    f"<tr><td>{s}</td><td>{fmt(r.alojamientos)}</td><td>{fmt(r.homologables)}</td>"
    f"<td>{fmt(r.pct,1)} %</td><td>{fmt(r.precio)} £</td></tr>" for s, r in seg.iterrows())

html = f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Informe · Oferta de alojamiento en Londres · Atlas Horizon Group</title>
{PLOTLY_TAG}
<style>
  :root {{ --navy:{NAVY}; --amber:{AMBER}; --green:{GREEN}; --red:{RED}; --ink:#1f2933; --muted:#5f6b7a; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; font-family:Inter, system-ui, -apple-system, Segoe UI, sans-serif; color:var(--ink); background:#f5f6f8; line-height:1.55; }}
  header {{ background:var(--navy); color:#fff; padding:40px 24px 32px; }}
  .wrap {{ max-width:1040px; margin:0 auto; padding:0 24px; }}
  header .wrap {{ padding:0; }}
  .eyebrow {{ text-transform:uppercase; letter-spacing:.12em; font-size:12px; color:#f1c48d; }}
  h1 {{ margin:6px 0 8px; font-size:30px; }}
  header p {{ margin:0; color:#cfd8e3; }}
  section {{ background:#fff; border-radius:12px; padding:28px; margin:24px 0; box-shadow:0 1px 3px rgba(0,0,0,.06); }}
  h2 {{ margin:0 0 6px; font-size:21px; color:var(--navy); }}
  .lead {{ color:var(--muted); margin:0 0 18px; }}
  .summary li {{ margin:6px 0; }}
  .kpis {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:14px; }}
  .kpi {{ border-radius:10px; padding:14px; border-top:4px solid; background:#fafbfc; }}
  .kpi.ok {{ border-color:var(--green); }} .kpi.ko {{ border-color:var(--red); background:#fdf5f4; }}
  .kpi-id {{ font-size:11px; color:var(--muted); letter-spacing:.06em; }}
  .kpi-name {{ font-size:13px; font-weight:600; min-height:38px; }}
  .kpi-val {{ font-size:26px; font-weight:700; margin:4px 0; }}
  .kpi-meta {{ font-size:12px; color:var(--muted); }}
  .kpi.ok .kpi-meta b {{ color:var(--green); }} .kpi.ko .kpi-meta b {{ color:var(--red); }}
  .kpi-acc {{ font-size:12px; margin-top:8px; color:var(--ink); }}
  table {{ width:100%; border-collapse:collapse; font-size:14px; margin-top:12px; }}
  th, td {{ text-align:left; padding:8px 10px; border-bottom:1px solid #e8ebef; }}
  th {{ font-size:12px; text-transform:uppercase; letter-spacing:.05em; color:var(--muted); }}
  .callout {{ border-left:4px solid var(--amber); background:#fdf8f1; padding:12px 16px; border-radius:6px; margin-top:14px; }}
  .rec {{ display:grid; grid-template-columns:28px 1fr; gap:10px; margin:12px 0; }}
  .rec .n {{ background:var(--navy); color:#fff; border-radius:50%; width:28px; height:28px; display:grid; place-items:center; font-weight:700; }}
  .rec small {{ color:var(--muted); }}
  footer {{ color:var(--muted); font-size:12px; padding:8px 0 40px; }}
</style></head>
<body>
<header><div class="wrap">
  <div class="eyebrow">Atlas Horizon Group · Informe mensual de operaciones</div>
  <h1>Oferta de alojamiento en el hub de Londres</h1>
  <p>Para: Dirección de Operaciones y Logística · Datos: captura de febrero de 2020 · {fmt(total)} alojamientos analizados</p>
</div></header>
<main class="wrap">

<section>
  <h2>Resumen ejecutivo</h2>
  <ul class="summary">
    <li><b>{fmt(homol)} alojamientos</b> ({fmt(k.loc['PI_ALO_01','valor'],1)} %) cumplen nuestros estándares. La oferta apta es suficiente.</li>
    <li><b>Alerta de precio:</b> la base privada homologada cuesta de media <b>{fmt(k.loc['PI_ALO_02','valor'])} £/noche</b>, por encima de la meta de {fmt(META_PRECIO)} £.</li>
    <li><b>Alerta de ubicación:</b> solo el <b>{fmt(k.loc['PI_ALO_04','valor'],1)} %</b> de la oferta apta está a ≤ 5 km de la sede de briefing (meta: 50 %).</li>
    <li><b>Oportunidad:</b> hay barrios cercanos donde la base privada está por debajo de la meta: {optimos_txt}.</li>
  </ul>
</section>

<section>
  <h2>Indicadores clave</h2>
  <p class="lead">{n_ok} de {len(kpis)} indicadores en meta. Los que no cumplen incluyen la acción prevista.</p>
  <div class="kpis">{''.join(kpi_card(r) for r in kpis.itertuples())}</div>
</section>

<section>
  <h2>1 · ¿Cuánta oferta es apta para Atlas?</h2>
  <p class="lead">Un alojamiento es <i>homologable</i> si tiene precio válido, estancia mínima ≤ 7 noches, ≥ 30 días disponibles, ≥ 5 reseñas y actividad en los últimos 12 meses.</p>
  {fig_html(f1, 260)}
  <table><tr><th>Segmento</th><th>Oferta</th><th>Homologables</th><th>% apto</th><th>Precio medio apto</th></tr>{seg_rows}</table>
  <div class="callout">La oferta para clientes (base privada y hotel) es amplia. El cuello de botella no es la <b>cantidad</b>, sino el <b>precio</b> y la <b>ubicación</b>.</div>
</section>

<section>
  <h2>2 · Precio frente a distancia a la sede</h2>
  <p class="lead">Cada burbuja es un barrio. Su tamaño indica cuántas bases privadas aptas tiene. La zona verde marca ≤ 6 km de la sede.</p>
  {fig_html(f2, 440)}
  <div class="callout">Los barrios más próximos a la sede son también los más caros: {caros_txt}. Los barrios en verde ofrecen el mejor equilibrio entre cercanía y coste.</div>
</section>

<section>
  <h2>3 · Dónde está la oferta apta</h2>
  <p class="lead">Muestra de 3.000 alojamientos homologables. El círculo rojo marca el radio de 5 km alrededor de la sede.</p>
  {fig_html(f3, 520)}
</section>

<section>
  <h2>4 · Riesgo de proveedor</h2>
  <p class="lead">Reparto de la oferta homologable según el tipo de anfitrión.</p>
  <table><tr><th>Tipo de proveedor</th><th>Alojamientos aptos</th><th>% del total apto</th></tr>
  {''.join(f"<tr><td>{t}</td><td>{fmt(v)}</td><td>{fmt(prov_pct[t],1)} %</td></tr>" for t, v in prov.sort_values(ascending=False).items())}
  </table>
  <div class="callout">La dependencia de proveedores profesionales ({fmt(k.loc['PI_ALO_05','valor'],1)} %) está dentro de la meta (≤ 30 %). El mayor peso está en <b>{prov.idxmax().lower()}</b> ({fmt(prov_pct.max(),1)} %): una cartera repartida entre muchos anfitriones pequeños diversifica el riesgo, pero exige más control de calidad.</div>
</section>

<section>
  <h2>Recomendaciones</h2>
  <div class="rec"><div class="n">1</div><div><b>Priorizar {' y '.join(optimos.barrio.head(3))} para las bases privadas de clientes.</b><br><small>Precio por debajo de la meta y a menos de 6 km de la sede. Responsable: Coordinación de logística.</small></div></div>
  <div class="rec"><div class="n">2</div><div><b>Negociar tarifas por volumen</b> con los proveedores multipropiedad de Westminster y Kensington and Chelsea para las estancias VIP que exigen máxima cercanía.<br><small>Responsable: Compras.</small></div></div>
  <div class="rec"><div class="n">3</div><div><b>Incluir el traslado al briefing</b> en el paquete cuando el alojamiento esté a más de 5 km, en lugar de pagar el sobrecoste del centro.<br><small>Responsable: Operaciones.</small></div></div>
</section>

<footer>
  Fuente: Inside Airbnb (Londres, febrero 2020), licencia CC BY 4.0. Datos procesados en el data warehouse de Atlas Horizon (DuckDB).
  Atlas Horizon Group es una empresa ficticia; la sede de briefing y las metas son supuestos del proyecto.
</footer>
</main></body></html>"""

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(html, encoding="utf-8")
print(f"Informe generado: {OUT.relative_to(ROOT)} ({OUT.stat().st_size/1024:.0f} KB)")
