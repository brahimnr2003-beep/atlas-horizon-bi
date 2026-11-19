# Datos

## `raw/listings_london_2020-02.csv.gz`

Resumen de los alojamientos de Londres publicado por [Inside Airbnb](http://insideairbnb.com/get-the-data/), captura de febrero de 2020 (fichero `listings.csv` de la sección *visualisations*). Licencia [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

- 87.531 filas y 16 columnas. El original tenía 87.571 filas; las 40 sin nombre de anuncio o de anfitrión se eliminaron en la versión 1 del proyecto.
- La columna `neighbourhood_group` del original (100 % vacía) ya no está.
- La columna `expedition_type` es la recodificación de la versión 1. La ETL actual la descarta y la sustituye por `dim_segmento`.

## `processed/`

Salidas del data warehouse que se generan al ejecutar el notebook. Las usan `src/build_report.py` y `src/build_dashboard.py`.

| Fichero | Contenido |
|---|---|
| `kpis.csv` | Valor, meta y estado de cada KPI |
| `oferta_agregada.csv` | Oferta por barrio × segmento × tipo de proveedor |
| `distribucion_precios.csv` | Oferta homologable por tramos de precio |
| `mapa_muestra.csv` | Muestra reproducible de 3.000 alojamientos homologables |
| `tableau_oferta.csv` | Tabla de hechos desnormalizada para Tableau: 87.531 alojamientos con dimensiones y flags de negocio, sin nombres. La genera `src/export_tableau.py` |

El fichero `atlas_horizon.duckdb` (el data warehouse) se crea al ejecutar el notebook y no se versiona.
