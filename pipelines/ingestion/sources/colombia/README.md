# Colombian sources — ingestion scripts

## `dane_mgn.py` — Administrative boundaries (DANE MGN 2025)

Produces the boundary files used by the public data portal map (Module A).

| Item | Value |
|---|---|
| Institution | Departamento Administrativo Nacional de Estadística (DANE) |
| Product | Marco Geoestadístico Nacional (MGN), version 2025 |
| Service | `https://geoportal.dane.gov.co/mparcgis/rest/services/MGN2025/Serv_CapasMGN_2025/FeatureServer` (layers 319 Departamento, 317 Municipio) |
| Official status | DANE states MGN department/municipal limits follow official IGAC limits |
| Reuse terms | DANE site terms authorise use and transformation with the citation: *"Fuente: Departamento Administrativo Nacional de Estadística: www.dane.gov.co"* — <https://www.dane.gov.co/index.php/terrminos-y-condiciones-dane> |
| Source CRS | EPSG:3857 (Web Mercator) |
| Output CRS | EPSG:4326 (WGS84), reprojected server-side (`outSR=4326`) |

### Run

```bash
# from the repository root; Python 3 standard library only, no dependencies
python3 pipelines/ingestion/sources/colombia/dane_mgn.py --out frontend/public/geo
```

### Outputs (`frontend/public/geo/`)

| File | Content |
|---|---|
| `colombia-departamentos.geojson` | 33 departments (32 + Bogotá D.C.), generalised ≈ 1.1 km |
| `municipios-05.geojson` | 125 municipalities of Antioquia, generalised ≈ 220 m |
| `boundaries.metadata.json` | Source, retrieval timestamp, processing parameters and quality report |

Feature `id` = numeric DIVIPOLA code (enables MapLibre `feature-state`); `properties.code` keeps the
zero-padded string code (`05400`).

### Processing and validation

1. Server-side generalisation with ArcGIS `maxAllowableOffset` and coordinate rounding (`geometryPrecision`).
2. Esri rings → RFC 7946 GeoJSON (outer rings CCW, holes CW and assigned to their outer ring).
3. Label point per feature (pole-of-inaccessibility approximation), so names stay inside concave shapes.
4. Validation (the script writes nothing if it fails): expected counts, unique codes, non-empty names,
   coordinates within Colombia, closed rings.
5. Area check vs DANE's official area field. Last run: Antioquia municipalities mean 0.45 %, max 2.2 %
   (Pueblorrico); departments ≤ 1 % except San Andrés (17.8 %, small islands — reference only).

Generalised boundaries are for visualisation only — not for cadastral or legal use.

### Adding another department

Change `PILOT_DEPARTMENT_CODE` / `EXPECTED_PILOT_MUNICIPALITIES` (or extend the script to loop over
codes), run it, and register the new `municipios-XX.geojson` in
`frontend/src/app/core/catalog/pilot-territory.ts`.
