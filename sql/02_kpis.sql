-- =====================================================================
-- Atlas Horizon Group · KPIs del Proceso 4 (oferta de alojamiento)
-- Las metas son supuestos de negocio definidos en docs/diseno_bi.md
-- =====================================================================
CREATE OR REPLACE VIEW v_kpis AS
WITH f AS (
    SELECT f.*, s.segmento_atlas, p.tipo_proveedor
    FROM fact_oferta_alojamiento f
    JOIN dim_segmento  s USING (id_segmento)
    JOIN dim_proveedor p USING (id_proveedor)
),
h AS (SELECT * FROM f WHERE flag_homologable = 1),
kpis AS (
    SELECT 'PI_ALO_01' AS id_kpi, 'Tasa de homologación de la oferta' AS kpi, '%' AS unidad,
           100.0 * SUM(flag_homologable) / COUNT(*) AS valor, 25 AS meta, '>=' AS operador,
           'Ampliar criterios o buscar plataformas alternativas de alojamiento' AS accion
    FROM f
    UNION ALL
    SELECT 'PI_ALO_02', 'Precio medio por noche · bases privadas homologadas', '£',
           AVG(precio_noche), 150, '<=',
           'Negociar tarifas por volumen o desplazar reservas a barrios más baratos'
    FROM h WHERE segmento_atlas = 'Base privada'
    UNION ALL
    SELECT 'PI_ALO_03', 'Disponibilidad media de la oferta homologada', 'días/año',
           AVG(dias_disponibles), 180, '>=',
           'Reservar con más antelación en temporada alta'
    FROM h
    UNION ALL
    SELECT 'PI_ALO_04', 'Oferta homologada a ≤ 5 km de la sede de briefing', '%',
           100.0 * AVG(CASE WHEN dist_sede_km <= 5 THEN 1 ELSE 0 END), 50, '>=',
           'Contratar traslados al briefing o abrir un segundo punto de reunión'
    FROM h
    UNION ALL
    SELECT 'PI_ALO_05', 'Dependencia de proveedores profesionales', '%',
           100.0 * AVG(CASE WHEN tipo_proveedor = 'Profesional' THEN 1 ELSE 0 END), 30, '<=',
           'Diversificar proveedores para reducir el riesgo de concentración'
    FROM h
)
SELECT
    id_kpi, kpi, unidad, ROUND(valor, 1) AS valor, meta, operador,
    CASE WHEN (operador = '>=' AND valor >= meta) OR (operador = '<=' AND valor <= meta)
         THEN 'Cumple' ELSE 'No cumple' END AS estado,
    accion
FROM kpis
ORDER BY id_kpi;

-- Vista agregada para el informe y el dashboard (barrio × segmento × proveedor)
CREATE OR REPLACE VIEW v_oferta_agregada AS
SELECT
    b.barrio, b.zona, b.lat_centro, b.lon_centro,
    s.segmento_atlas, p.tipo_proveedor,
    COUNT(*)                                   AS alojamientos,
    SUM(f.flag_homologable)                    AS homologables,
    SUM(f.flag_precio_atipico)                 AS precios_atipicos,
    SUM(CASE WHEN f.flag_homologable = 1 AND f.dist_sede_km <= 5 THEN 1 ELSE 0 END) AS homologables_5km,
    SUM(CASE WHEN f.flag_homologable = 1 THEN f.precio_noche END)     AS suma_precio_homologables,
    SUM(CASE WHEN f.flag_homologable = 1 THEN f.dias_disponibles END) AS suma_dias_homologables
FROM fact_oferta_alojamiento f
JOIN dim_barrio    b USING (id_barrio)
JOIN dim_segmento  s USING (id_segmento)
JOIN dim_proveedor p USING (id_proveedor)
GROUP BY ALL;
