-- =====================================================================
-- Atlas Horizon Group · Data Warehouse (DuckDB)
-- Proceso 4: Gestión de la oferta de alojamiento en el hub de Londres
-- Esquema en estrella · tabla de hechos de tipo SNAPSHOT PERIÓDICO
-- Granularidad: 1 fila = 1 alojamiento en una fecha de captura (snapshot)
--
-- Requiere una tabla de staging `stg_listings` (salida de la ETL en Python).
-- =====================================================================

-- Parámetros de negocio (supuestos del proyecto)
CREATE OR REPLACE TABLE param_negocio AS
SELECT
    DATE '2020-02-16' AS fecha_snapshot,   -- última reseña registrada en el dataset
    51.5013           AS sede_lat,         -- sede de briefing de Atlas (South Kensington)
    -0.1755           AS sede_lon,
    7                 AS max_noches_minimas,
    30                AS min_dias_disponibles,
    5                 AS min_resenas,
    12                AS meses_actividad;

-- ---------------------------------------------------------------------
-- DIMENSIÓN SEGMENTO: traduce el tipo de alojamiento al perfil de
-- huésped de Atlas Horizon (clientes UHNW, staff técnico, staff de apoyo)
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE dim_segmento AS
SELECT
    ROW_NUMBER() OVER (ORDER BY room_type) AS id_segmento,
    room_type                               AS tipo_alojamiento,
    CASE room_type
        WHEN 'Entire home/apt' THEN 'Base privada'
        WHEN 'Hotel room'      THEN 'Hotel'
        WHEN 'Private room'    THEN 'Habitación individual'
        WHEN 'Shared room'     THEN 'Compartido'
    END AS segmento_atlas,
    CASE room_type
        WHEN 'Entire home/apt' THEN 'Clientes UHNW y grupos (privacidad y espacio para briefings)'
        WHEN 'Hotel room'      THEN 'Clientes que requieren servicios de hotel'
        WHEN 'Private room'    THEN 'Staff técnico, científicos y guías'
        WHEN 'Shared room'     THEN 'Staff de apoyo (uso excepcional)'
    END AS perfil_huesped
FROM (SELECT DISTINCT room_type FROM stg_listings);

-- ---------------------------------------------------------------------
-- DIMENSIÓN BARRIO (nivel más bajo de la dimensión conformada DIM_GEO
-- de la Fase 1: Región > País > Ciudad hub > Barrio)
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE dim_barrio AS
WITH c AS (
    SELECT neighbourhood, AVG(latitude) AS lat_centro, AVG(longitude) AS lon_centro
    FROM stg_listings GROUP BY neighbourhood
)
SELECT
    ROW_NUMBER() OVER (ORDER BY neighbourhood) AS id_barrio,
    neighbourhood                                AS barrio,
    'Londres'                                    AS ciudad_hub,
    'Reino Unido'                                AS pais,
    CASE WHEN neighbourhood IN ('Camden','City of London','Greenwich','Hackney',
         'Hammersmith and Fulham','Islington','Kensington and Chelsea','Lambeth',
         'Lewisham','Southwark','Tower Hamlets','Wandsworth','Westminster')
         THEN 'Inner London' ELSE 'Outer London' END AS zona,
    ROUND(lat_centro, 5) AS lat_centro,
    ROUND(lon_centro, 5) AS lon_centro
FROM c;

-- ---------------------------------------------------------------------
-- DIMENSIÓN PROVEEDOR (anfitrión). Se omite el nombre por privacidad.
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE dim_proveedor AS
SELECT
    host_id                              AS id_proveedor,
    MAX(calculated_host_listings_count)  AS num_anuncios,
    CASE
        WHEN MAX(calculated_host_listings_count) = 1   THEN 'Particular'
        WHEN MAX(calculated_host_listings_count) <= 10 THEN 'Multipropiedad'
        ELSE 'Profesional'
    END AS tipo_proveedor
FROM stg_listings
GROUP BY host_id;

-- ---------------------------------------------------------------------
-- DIMENSIÓN TIEMPO (fecha de snapshot). Preparada para añadir capturas
-- mensuales futuras sin cambiar el modelo.
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE dim_tiempo AS
SELECT
    CAST(strftime(fecha_snapshot, '%Y%m%d') AS INTEGER) AS id_tiempo,
    fecha_snapshot                                      AS fecha,
    year(fecha_snapshot)                                AS anio,
    quarter(fecha_snapshot)                             AS trimestre,
    month(fecha_snapshot)                               AS mes,
    CASE WHEN month(fecha_snapshot) IN (12,1,2) THEN 'Invierno'
         WHEN month(fecha_snapshot) IN (3,4,5)  THEN 'Primavera'
         WHEN month(fecha_snapshot) IN (6,7,8)  THEN 'Verano'
         ELSE 'Otoño' END                               AS temporada
FROM param_negocio;

-- ---------------------------------------------------------------------
-- TABLA DE HECHOS: OFERTA DE ALOJAMIENTO
-- Reglas de negocio:
--   · flag_precio_atipico: precio 0 o por encima del percentil 99 de su tipo
--   · flag_activo: reseña en los últimos 12 meses
--   · flag_homologable: cumple TODOS los criterios de Atlas Horizon
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE fact_oferta_alojamiento AS
WITH p99 AS (
    SELECT room_type, quantile_cont(price, 0.99) AS precio_p99
    FROM stg_listings WHERE price > 0 GROUP BY room_type
),
base AS (
    SELECT
        s.*,
        p.precio_p99,
        -- distancia (km) a la sede de briefing · fórmula de Haversine
        2 * 6371 * asin(sqrt(
            power(sin(radians(prm.sede_lat - s.latitude) / 2), 2) +
            cos(radians(s.latitude)) * cos(radians(prm.sede_lat)) *
            power(sin(radians(prm.sede_lon - s.longitude) / 2), 2)
        )) AS dist_sede_km,
        prm.*
    FROM stg_listings s
    JOIN p99 p USING (room_type)
    CROSS JOIN param_negocio prm
)
SELECT
    b.id                                                    AS id_alojamiento,   -- dimensión degenerada
    CAST(strftime(b.fecha_snapshot, '%Y%m%d') AS INTEGER)   AS id_tiempo,
    db.id_barrio,
    b.host_id                                               AS id_proveedor,
    ds.id_segmento,
    -- medidas
    b.price                                                 AS precio_noche,      -- no aditiva (se promedia)
    b.minimum_nights                                        AS noches_minimas,    -- no aditiva
    b.availability_365                                      AS dias_disponibles,  -- semi-aditiva
    b.number_of_reviews                                     AS num_resenas,       -- aditiva
    b.reviews_per_month                                     AS resenas_mes,       -- no aditiva
    ROUND(b.dist_sede_km, 2)                                AS dist_sede_km,      -- no aditiva
    b.last_review                                           AS fecha_ultima_resena,
    -- flags (aditivos como contadores 0/1)
    CAST(b.price = 0 OR b.price > b.precio_p99 AS INTEGER)  AS flag_precio_atipico,
    CAST(COALESCE(b.last_review >= b.fecha_snapshot - INTERVAL (b.meses_actividad) MONTH, FALSE)
         AS INTEGER)                                        AS flag_activo,
    CAST(COALESCE(
        b.price > 0 AND b.price <= b.precio_p99
        AND b.minimum_nights   <= b.max_noches_minimas
        AND b.availability_365 >= b.min_dias_disponibles
        AND b.number_of_reviews >= b.min_resenas
        AND b.last_review >= b.fecha_snapshot - INTERVAL (b.meses_actividad) MONTH
    , FALSE) AS INTEGER)                                             AS flag_homologable
FROM base b
JOIN dim_barrio   db ON db.barrio = b.neighbourhood
JOIN dim_segmento ds ON ds.tipo_alojamiento = b.room_type;
