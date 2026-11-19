"""Exporta la tabla de hechos desnormalizada para construir el dashboard en Tableau.

Uso:  python src/export_tableau.py
Lee:  data/atlas_horizon.duckdb  (se crea al ejecutar el notebook)
Crea: data/processed/tableau_oferta.csv

Una fila por alojamiento con sus dimensiones ya unidas (barrio, segmento, proveedor,
fecha) y los flags de negocio calculados en el data warehouse. Así, Tableau usa
exactamente las mismas reglas que el informe y el dashboard HTML. No incluye el
nombre del anuncio ni el del anfitrión.
"""
from pathlib import Path
import duckdb

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "atlas_horizon.duckdb"
OUT = ROOT / "data" / "processed" / "tableau_oferta.csv"

if not DB.exists():
    raise SystemExit(f"No existe {DB.relative_to(ROOT)}. Ejecuta antes el notebook.")

QUERY = """
SELECT
    f.id_alojamiento,
    t.fecha                                    AS fecha_snapshot,
    b.barrio,
    b.zona,
    s.segmento_atlas,
    s.tipo_alojamiento,
    p.tipo_proveedor,
    p.num_anuncios                             AS anuncios_proveedor,
    f.precio_noche,
    f.noches_minimas,
    f.dias_disponibles,
    f.num_resenas,
    f.resenas_mes,
    CAST(f.fecha_ultima_resena AS DATE)        AS fecha_ultima_resena,
    f.dist_sede_km,
    CAST(f.dist_sede_km <= 5 AS INTEGER)       AS flag_5km,
    f.flag_precio_atipico,
    f.flag_activo,
    f.flag_homologable,
    ROUND(st.latitude, 5)                      AS latitude,
    ROUND(st.longitude, 5)                     AS longitude
FROM fact_oferta_alojamiento f
JOIN dim_tiempo    t USING (id_tiempo)
JOIN dim_barrio    b USING (id_barrio)
JOIN dim_segmento  s USING (id_segmento)
JOIN dim_proveedor p USING (id_proveedor)
JOIN stg_listings st ON st.id = f.id_alojamiento
ORDER BY f.id_alojamiento
"""

with duckdb.connect(str(DB), read_only=True) as con:
    con.execute(f"COPY ({QUERY}) TO '{OUT.as_posix()}' (HEADER, DELIMITER ',')")
    n = con.execute(f"SELECT COUNT(*) FROM read_csv_auto('{OUT.as_posix()}')").fetchall()[0][0]

print(f"Exportado: {OUT.relative_to(ROOT)} ({n:,} filas, {OUT.stat().st_size / 1e6:.1f} MB)")
