# CLAUDE.md

## 1. Project Identity

**Project name:** Not yet defined

This project is a web-based agricultural
data exploration and decision-support platform designed for Colombia.
**Challenge:** NASA Space Apps Challenge 2026 — Field Shift: Adapting Farms with NASA Data
**Hackathon implementation scope:** Antioquia, Colombia.
**Initial pilot territory:** Selected municipalities and agricultural contexts in Antioquia.
**Long-term expansion scope:** Colombia, with potential coverage of all departments.
**Institutional context:** Universidad de Antioquia.
**Target awards:**
- Best Use of Data
- Local Impact Award

### Project concept

The platform is a web-based agricultural data and decision-support platform for Colombia.

It integrates NASA Earth observations, international agricultural datasets, Colombian institutional information, and farmer-provided data to make agricultural and environmental information accessible and useful.

The platform has two main modules:

1. **Public Agricultural and Environmental Data Portal:** A public agricultural and environmental data portal for exploring, visualizing, filtering, comparing, and downloading datasets for research and characterization.
2. **Farmer Decision-Support Workspace:** A private farmer-centered platform where users register their farms, provide information about their soil and agricultural history, explore environmental conditions, and receive explainable crop-rotation scenarios adapted to their priorities and constraints.

The platform must support evidence-based agricultural decisions. It must never present unvalidated predictions or recommendations as guaranteed outcomes.

---

## 2. Challenge Requirements

The solution must directly address the NASA Space Apps challenge, Field Shift: Adapting Farms with NASA Data.

The project must:

1. Use NASA Earth observations as essential inputs, not decorative map layers.
2. Combine NASA data with local agricultural information, soil information, crop characteristics, and farmer priorities.
3. Help users understand environmental conditions affecting agricultural resilience.
4. Support the exploration of crop-rotation strategies that may improve soil health and adaptation to changing climate and water conditions.
5. Compare at least three rotation strategies for a selected agricultural system:
   - Existing or representative current practice.
   - Alternative rotation strategy A.
   - Alternative rotation strategy B.
6. Explain the potential benefits, risks, evidence, assumptions, and information gaps associated with each strategy.
7. Distinguish satellite observations, ground measurements, modeled products, literature-based evidence, and farmer-provided information.
8. Explain uncertainty and spatial and temporal resolution limitations.
9. Support, rather than replace, farmers, agronomists, and agricultural extension workers.

---
## 3. Geographic Scope

### Long-term geographic scope

The long-term geographic scope of the platform is Colombia, with the
possibility of supporting agricultural and environmental information
across all departments and municipalities.

The platform must be designed to accommodate different geographic,
environmental, agricultural, and socioeconomic contexts throughout
the country.

National coverage is a long-term objective and must not be presented
as fully implemented unless the corresponding data and functionality
are actually available.

### Hackathon implementation scope

Antioquia, Colombia, is the initial pilot territory for the NASA
Space Apps Challenge 2026 implementation.

The MVP should prioritize a manageable selection of municipalities,
agricultural systems, and environmental variables based on data
availability, relevance, and feasibility.

The first pilot municipality, subregion, and crop system must be
selected after examining data availability and agronomic relevance.

Do not select a territory or crop solely based on familiarity.

### Geographic levels

The platform must distinguish three levels:

- **Regional:** broad environmental and agricultural patterns.
- **Municipal:** agricultural statistics and environmental summaries
  at municipal scale.
- **Farm/field:** information associated with an individual farm or
  field, only when the input data and source resolution support that
  interpretation.

Never present municipal statistics or coarse satellite observations
as direct field-level measurements.

## 4. Main Product Modules

# MODULE A — Public Agricultural and Environmental Data Portal

### Purpose

A public agricultural and environmental data portal that centralizes and makes accessible information from NASA, international institutions, and Colombian data providers.

The portal serves researchers, students, agricultural institutions, extension workers, and farmers.

### Main functionality

Users should be able to:

1. Explore an interactive map of Colombia.
2. Select departments, municipalities, and supported geographic areas.
3. Explore agricultural production and crop-distribution information.
4. Visualize environmental variables and historical trends.
5. Filter information by geographic area, variable, source, and time period.
6. Compare variables across different periods or territories.
7. Consult dataset metadata and methodological descriptions.
8. Download available datasets in appropriate formats.
9. Understand the limitations and uncertainty of each data product.

### Data visualization

Potential environmental layers include:

- Air temperature and temperature anomalies.
- Precipitation and rainfall anomalies.
- Surface soil moisture.
- Evapotranspiration.
- Solar radiation.
- Vegetation indices such as NDVI.
- Land-surface temperature.
- Elevation and slope.
- Agricultural suitability.
- Crop production and harvested area.

The portal should provide:

- Interactive maps.
- Time-series charts.
- Comparative charts.
- Data tables.
- Dataset information panels.
- Download options.

### Dataset catalog

Every integrated dataset must have a metadata record containing, where available:

- Dataset name.
- Institution or mission.
- Source URL.
- Product and variable names.
- Description.
- Units.
- Geographic coverage.
- Spatial resolution.
- Temporal resolution.
- Available time period.
- Acquisition or publication date.
- Processing methodology.
- License and reuse conditions.
- Known limitations.
- Last successful update.
- Data quality or validation status.

The system must not imply that a dataset is updated in real time when it is not.

### Data downloads

Downloads must preserve the source and meaning of the information.

Supported formats may include:

- CSV for tabular data.
- GeoJSON for vector geographic data.
- GeoTIFF for processed raster layers, when practical.
- JSON for structured API responses.

Each download should include metadata or an accompanying description identifying the source, units, time period, and processing steps.

Do not offer arbitrary raster downloads if the data cannot be generated or served reliably.

---

# MODULE B — Farmer Decision-Support Workspace

### Purpose

A private decision-support environment for farmers.

Users should be able to create an account, register one or more farms, provide agricultural information, and explore environmental conditions and crop-rotation scenarios adapted to their needs.

### Farmer account

The system may include:

- Account registration.
- Secure authentication.
- Login and logout.
- Password recovery, if supported by the chosen authentication system.
- Private farmer profile.
- Farm registration and editing.
- Access control to private farm information.

### Farm information

Collect only information needed for the analysis.

Potential fields include:

**Location and geometry**
- Farm name or identifier.
- Department.
- Municipality.
- Coordinates.
- Farm area.
- Field boundaries, if the user can provide them.

**Soil information**
- Soil type or classification, if known.
- Texture.
- Drainage.
- Soil pH, if measured.
- Organic matter, if measured.
- Available soil laboratory results.
- Known erosion or compaction problems.

**Water and environmental management**
- Water availability.
- Irrigation system.
- Water-source type.
- Drainage conditions.
- Known drought or flooding problems.

**Agricultural history**
- Current crops.
- Previous crops.
- Planting and harvesting dates.
- Crop rotations previously used.
- Historical yields, if available.
- Fertilizer and soil-management practices, if provided.
- Known pests and diseases.

**Farmer priorities and constraints**
- Water conservation.
- Soil protection.
- Diversification of income.
- Climate resilience.
- Available labor.
- Machinery and equipment.
- Irrigation limitations.
- Market availability.
- Investment limitations.

### Farm environmental analysis

After registration, the system should use the farm's location or supported geometry to retrieve and summarize available environmental information.

Possible outputs include:

- Historical temperature patterns.
- Rainfall patterns and anomalies.
- Soil-moisture indicators.
- Vegetation trends.
- Evapotranspiration indicators.
- Terrain and slope.
- Relevant agricultural suitability information.

The system must display the spatial and temporal resolution of each source.

A point or polygon query must not create the illusion of field-scale accuracy when the underlying product is too coarse.

### Crop-rotation decision support

The system must compare at least three strategies, including the existing or representative local practice.

For each strategy, provide:

- Crop sequence.
- Tentative planting and harvesting periods, when supported by local evidence.
- Water-related considerations.
- Soil-cover and erosion considerations.
- Potential nutrient-cycling benefits.
- Nitrogen-fixation potential, where applicable.
- Rooting characteristics.
- Potential pest and disease-cycle considerations.
- Market and operational constraints.
- Supporting evidence.
- Risks and missing information.

The platform should allow farmers to adjust priorities and see how the comparison changes.

Recommendations must be explainable and must identify what requires local agronomic validation.

### Calendar and planning

A future or optional feature is an agricultural calendar that presents:

- Proposed crop sequences.
- Tentative planting windows.
- Expected growing periods.
- Relevant environmental conditions.
- Tasks and reminders, if implemented.

Do not generate planting dates without adequate crop-calendar and local climate evidence.

---

## 5. Differentiating Features

The main differentiator is the integration of a public agricultural data infrastructure with a private farmer-centered decision-support system.

### A. Unified Agricultural Data Catalog

Provide one interface to discover, explore, compare, and download data from different providers.

The catalog should make data provenance and limitations visible.

### B. Explainable Environmental Intelligence

Translate satellite observations and institutional information into understandable agricultural indicators.

Users should be able to see how source data produces each indicator.

### C. Personalized Rotation Explorer

Use farm information and farmer priorities to compare rotation strategies and expose their trade-offs.

### D. Evidence and Confidence Passport

Every important result should display:

- Data sources.
- Data dates.
- Spatial and temporal resolution.
- Processing methodology.
- Evidence supporting the result.
- Missing information.
- Uncertainty and validation needs.

Use evidence categories such as:

- **High support:** relevant and sufficiently complete evidence at an appropriate scale.
- **Moderate support:** useful evidence with important local gaps.
- **Limited support:** indirect or incomplete evidence requiring local validation.

These categories must follow explicit documented rules.

---

## 6. Data Sources and Integration Priorities

NASA Earth observations must be central to the analytical pipeline.

Prioritize data integration according to feasibility, relevance, and scientific value. Do not attempt to integrate every source during the hackathon.

### 6.1 NASA POWER — Very High Priority

https://power.larc.nasa.gov/
https://power.larc.nasa.gov/docs/services/api/

Potential variables:
- Air temperature.
- Relative humidity.
- Solar radiation.
- Precipitation-related variables where available.
- Other agroclimatic variables supported by the selected API endpoint.

Purpose:
- Agroclimatic characterization.
- Historical time series.
- Climate context for agricultural analysis.

Limitations:
- Gridded estimates are not field-scale station measurements.
- Variable availability and spatial resolution depend on the product and API community.
- Document the exact parameters and units requested.

### 6.2 GPM IMERG — Very High Priority

https://gpm.nasa.gov/data

Potential variables:
- Precipitation rate.
- Precipitation accumulation.
- Rainfall variability.
- Intense precipitation events.

Purpose:
- Analyze rainfall patterns and anomalies.
- Study periods of excess or insufficient precipitation.
- Support water-stress and erosion-related analysis.

Limitations:
- Satellite precipitation estimates have uncertainty.
- Validation against appropriate ground observations is desirable.
- Product versions and temporal aggregations must be documented.

### 6.3 SMAP — Very High Priority

https://www.earthdata.nasa.gov/data/platforms/space-based-platforms/smap

Potential variables:
- Surface soil moisture.
- Soil-moisture anomalies.
- Freeze/thaw information where relevant.

Purpose:
- Characterize regional surface moisture conditions.
- Study temporal moisture variations.

Limitations:
- Surface soil moisture is not equivalent to root-zone soil moisture.
- Spatial resolution may be too coarse for individual small farms.
- Product type and retrieval quality must be documented.

### 6.4 FAO GAEZ — Very High Priority

https://gaez.fao.org/

Potential information:
- Agroecological suitability.
- Land and water resource assessment.
- Crop suitability.
- Agroclimatic potential.
- Attainable yield estimates under documented assumptions.
- Agricultural productivity and suitability layers.

Purpose:
- Provide crop-suitability context.
- Compare environmental suitability across territories.
- Support the selection and screening of candidate rotation crops.

Limitations:
- Suitability and potential-yield products are model-based assessments, not guarantees of farm production.
- Resolution, scenario, management level, and assumptions must be documented.
- Do not treat potential yield as actual measured yield.

### 6.5 Landsat / Harmonized Landsat Sentinel (HLS) — High Priority

https://earthexplorer.usgs.gov/
https://hls.gsfc.nasa.gov/

Potential variables:
- Surface reflectance.
- NDVI and other vegetation indices.
- Vegetation dynamics.
- Bare-ground and vegetation-cover indicators.

Purpose:
- Analyze vegetation patterns and seasonal changes.
- Explore possible vegetation stress.
- Identify changes in land cover where the product supports it.

Limitations:
- Clouds and cloud shadows affect observations.
- NDVI is not a direct measurement of crop yield or soil health.
- Mixed pixels and field size affect interpretation.

### 6.6 ECOSTRESS — High Priority

https://ecostress.jpl.nasa.gov/data

Potential variables:
- Land-surface temperature.
- Evapotranspiration products.
- Thermal indicators.

Purpose:
- Explore thermal stress and evapotranspiration patterns.
- Complement other environmental observations.

Limitations:
- Land-surface temperature is not equivalent to air temperature.
- Acquisition timing and coverage must be checked.
- Evapotranspiration products are model-derived estimates with uncertainty.

### 6.7 Sentinel-2 — High Priority

https://dataspace.copernicus.eu/

Potential variables:
- Multispectral reflectance.
- NDVI and other vegetation indices.
- Red-edge vegetation indicators.
- Bare-soil and vegetation-cover indicators.

Purpose:
- Higher-resolution vegetation analysis.
- Explore within-field spatial differences where the imagery and field geometry support it.

Limitations:
- Sentinel-2 is an ESA mission, not a NASA mission.
- It complements NASA observations but must be identified correctly.
- Clouds, shadows, and mixed pixels must be considered.

### 6.8 SRTM — Medium Priority

https://www.earthdata.nasa.gov/data/instruments/srtm

Potential variables:
- Elevation.
- Slope.
- Terrain derivatives.

Purpose:
- Characterize topography.
- Explore terrain-related runoff and erosion proxies.
- Contextualize agricultural suitability.

Limitations:
- Derived slope and erosion indicators are proxies, not direct erosion measurements.
- Resolution and terrain-processing methodology must be documented.

### 6.9 GLDAS — Medium Priority

https://www.earthdata.nasa.gov/

Potential variables:
- Modeled soil moisture.
- Evapotranspiration-related variables.
- Surface energy and water-balance variables.

Purpose:
- Complement satellite and meteorological time series.
- Explore modeled water-balance patterns.

Limitations:
- GLDAS is a land data assimilation product, not a direct field measurement.
- Model structure, forcing data, and spatial resolution must be documented.

### 6.10 MODIS / VIIRS — Medium Priority

https://lpdaac.usgs.gov/products/
https://search.earthdata.nasa.gov/search?q=VIIRS

Potential variables:
- Vegetation indices.
- Vegetation dynamics.
- Land-surface temperature products, where relevant.

Purpose:
- Regional and long-term vegetation monitoring.
- Seasonal and interannual comparisons.

Limitations:
- Spatial resolution is generally coarser than Landsat or Sentinel-2.
- Not suitable for all field-level analyses.

### 6.11 Colombian and Other Complementary Sources

**UPRA — EVA**
https://upra.gov.co/es-co/eva

Potential information:
- Planted area.
- Harvested area.
- Production.
- Yield.
- Crop and municipality.
- Reference period.

**UPRA — SIPRA**
https://sipra.upra.gov.co/

Potential information:
- Agricultural suitability.
- Agricultural frontier.
- Productive chains.
- Agricultural planning and geographic layers.

**IDEAM — DHIME**
https://www.ideam.gov.co/dhime

Potential information:
- Meteorological stations.
- Hydrological stations.
- Ground-based environmental observations.

**AGROSAVIA**
https://www.agrosavia.co/

Potential information:
- Colombian crop research.
- Agronomic practices.
- Soil management.
- Rotation systems.
- Technical publications.

**SoilGrids**
https://soilgrids.org/

Potential information:
- Soil properties and modeled soil maps.

**IGAC**
https://www.igac.gov.co/

Potential information:
- Soil surveys.
- Cartographic information.
- Geographic reference data.

**DANE**
https://www.dane.gov.co/

Potential information:
- Agricultural and rural statistics.
- Socioeconomic context.

All external sources must be cited in project documentation and submission materials.

---

## 7. Data Engineering and Processing

The platform must use a consistent data-ingestion and processing pipeline.

### Data ingestion

Each source connector should be responsible for:
- Accessing the source.
- Requesting or downloading the required data.
- Recording acquisition metadata.
- Handling errors and missing data.
- Preserving original source files when permitted.
- Returning a standardized internal representation.

Do not assume every provider offers a simple REST API. Some sources may require authentication, file downloads, cloud catalogs, or manual acquisition.

### Data organization

Separate:

- Raw source data.
- Cleaned data.
- Processed and harmonized data.
- Derived indicators.
- Model outputs.
- Farmer-provided private data.
- Demonstration or illustrative data.

Never silently replace real observations with simulated data.

### Data harmonization

Different sources have different:
- Coordinate reference systems.
- Spatial resolutions.
- Temporal resolutions.
- Units.
- No-data conventions.
- Coverage and quality flags.

Harmonization must document:
- Reprojection.
- Resampling.
- Temporal aggregation.
- Spatial aggregation.
- Missing-data treatment.
- Quality filtering.

Resampling data to a common grid does not create new information or improve the original resolution.

### Data validation

Validate:
- Coordinate ranges.
- Geometry validity.
- Date formats.
- Units.
- Missing values.
- Duplicate records.
- Implausible values.
- Source metadata.
- API and download errors.

Keep data-quality reports for important ingestion and processing steps.

---

## 8. Scientific and Analytical Framework

### Environmental indicators

Potential indicators include:
- Precipitation totals and anomalies.
- Temperature trends and anomalies.
- Dry-spell duration.
- Soil-moisture anomalies.
- Vegetation-index trends.
- Evapotranspiration indicators.
- Terrain and slope.
- Heat exposure.
- Extreme precipitation indicators.

Do not label a proxy as a direct measurement of soil health, crop stress, erosion, or yield.

### Rotation strategy evaluation

Use a transparent multi-criteria approach.

A possible scoring structure is:

S_j = sum_i (w_i * z_ij)

Where:
- S_j is the score for strategy j.
- w_i is the weight assigned to criterion i.
- z_ij is the normalized value of criterion i for strategy j.

Potential criteria:
- Water-use implications.
- Soil cover.
- Erosion protection.
- Nitrogen-fixation potential.
- Organic matter contribution.
- Rooting characteristics.
- Pest and disease-cycle interruption.
- Market feasibility.
- Labor and equipment requirements.

Only include criteria supported by data or documented agronomic evidence.

Explain:
- The meaning of each criterion.
- Its source.
- Its units or scoring method.
- The direction of preference.
- Normalization.
- User-selected weights.
- Missing data.
- Uncertainty.

Do not invent scientifically validated coefficients or numerical weights.

### Predictive modeling

Machine-learning models may be used only when:
- Appropriate training data exist.
- The target variable is clearly defined.
- Training and evaluation procedures are documented.
- Validation is appropriate for the spatial and temporal structure of the data.
- Performance metrics are reported honestly.

Do not train a model on arbitrary synthetic data and present its predictions as real-world forecasts.

If reliable training data are unavailable, use transparent rules, literature-supported criteria, historical summaries, and scenario analysis instead.

### Model evaluation

Where applicable, evaluate:
- Generalization to unseen data.
- Spatial leakage.
- Temporal leakage.
- Class imbalance.
- Missing-data effects.
- Calibration and uncertainty.
- Baseline performance.

The model must not imply causal relationships when it only identifies statistical associations.

---

## 9. Technical Architecture

The project uses a modular full-stack architecture.

### Frontend — Angular

Location:

`apps/web/`

Responsibilities:
- Public portal.
- Interactive maps.
- Data visualization.
- Dataset catalog.
- Download interface.
- Farmer registration and login interfaces.
- Farm profile and data-entry forms.
- Rotation comparison.
- Agricultural calendar.
- User-facing explanations and warnings.

Suggested feature organization:

`apps/web/src/app/`

- `core/`: configuration, HTTP clients, authentication, guards.
- `features/map/`: geospatial map.
- `features/data/`: catalog, filters, visualization, downloads.
- `features/crops/`: crop information and rotations.
- `features/analysis/`: environmental and analytical results.
- `features/farm/`: farm registration and profile.
- `features/auth/`: login and account management.
- `features/calendar/`: agricultural calendar.
- `shared/`: reusable components.

Use a consistent API service layer. Do not put data-processing logic directly into UI components.

### Backend — FastAPI

Location:

`apps/api/`

Responsibilities:
- REST API.
- Authentication and authorization.
- Farm profile management.
- Data catalog endpoints.
- Dataset metadata.
- Data retrieval and filtering.
- Geospatial queries.
- Processing and analysis requests.
- Rotation scenario services.
- Download endpoints.

Suggested organization:

`apps/api/app/`

- `routers/`: REST endpoints.
- `services/`: application and domain logic.
- `repositories/`: data-access operations.
- `schemas/`: request and response models.
- `db/`: database connections and configuration.
- `main.py`: FastAPI application entry point.

Keep business logic separate from HTTP routes.

Document the API using OpenAPI.

### Database — PostgreSQL + PostGIS

Use PostgreSQL with PostGIS for geographic data and application records.

Potential entities:
- Users.
- Farms.
- Farm fields.
- Soil observations.
- Agricultural history.
- Crop records.
- Dataset catalog.
- Data-source metadata.
- Environmental summaries.
- Rotation scenarios.
- User priorities.
- Model and analysis results.

Important:
- Private farm data must be access-controlled.
- A user must not be able to access another user's private farm records without authorization.
- Public datasets and private user records must have clear access boundaries.
- Avoid storing large raster files directly in relational tables when object or file storage is more appropriate.

### Data pipelines

Location:

`pipelines/`

Responsibilities:
- External data ingestion.
- Cleaning.
- Harmonization.
- Geospatial processing.
- Temporal processing.
- Validation.
- Derived indicators.

Use Prefect for orchestration only if it is justified and practical.

For the hackathon MVP, a small number of reproducible scripts or scheduled jobs may be sufficient.

### Machine learning and analytical services

Location:

`ml/`

Responsibilities:
- Feature engineering.
- Training.
- Evaluation.
- Inference.
- Model configuration.

The rotation comparison engine should remain explainable and separable from any predictive model.

### Shared contracts

Location:

`packages/contracts/`

Responsibilities:
- OpenAPI specifications.
- JSON Schemas.
- Shared data contracts.
- Consistent frontend/backend field definitions.

### Infrastructure

Location:

`infra/`

Responsibilities:
- Database setup.
- Database migrations.
- Docker configuration.
- Environment configuration.

Use Docker Compose to simplify local development when the team can support it.

---

## 10. Repository Structure

Use the following target structure:

```text
field-shift/
│
├── CLAUDE.md
├── README.md
├── .gitignore
├── .env.example
├── docker-compose.yml
│
├── apps/
│   ├── web/
│   │   └── src/app/
│   │       ├── core/
│   │       ├── features/
│   │       │   ├── map/
│   │       │   ├── data/
│   │       │   ├── crops/
│   │       │   ├── analysis/
│   │       │   ├── farm/
│   │       │   ├── auth/
│   │       │   └── calendar/
│   │       └── shared/
│   │
│   └── api/
│       ├── app/
│       │   ├── routers/
│       │   ├── services/
│       │   ├── repositories/
│       │   ├── schemas/
│       │   ├── db/
│       │   └── main.py
│       └── tests/
│
├── pipelines/
│   ├── ingestion/
│   │   ├── sources/
│   │   │   ├── nasa/
│   │   │   │   ├── power.py
│   │   │   │   ├── gpm.py
│   │   │   │   ├── smap.py
│   │   │   │   ├── hls.py
│   │   │   │   └── ecostress.py
│   │   │   ├── esa/
│   │   │   │   └── sentinel2.py
│   │   │   ├── colombia/
│   │   │   │   ├── ideam.py
│   │   │   │   └── upra.py
│   │   │   └── global/
│   │   │       ├── fao.py
│   │   │       └── soilgrids.py
│   │   └── flows/
│   │
│   └── processing/
│       ├── cleaning/
│       ├── geospatial/
│       ├── temporal/
│       └── validation/
│
├── ml/
│   ├── features/
│   ├── training/
│   ├── evaluation/
│   ├── inference/
│   └── configs/
│
├── packages/
│   └── contracts/
│
├── infra/
│   ├── database/
│   │   └── migrations/
│   └── docker/
│
├── tests/
├── docs/
│   ├── architecture.md
│   ├── methodology.md
│   ├── data_sources.md
│   ├── data_dictionary.md
│   ├── privacy.md
│   └── limitations.md
│
├── samples/
├── scripts/
└── .github/
    └── workflows/
```

Do not create every directory or module automatically if it is not needed for the current implementation phase.

---

## 11. Security, Privacy, and Responsible Use

Farm information can be sensitive, especially exact farm coordinates, ownership details, production history, and economic information.

The application must:
- Keep private farm data separate from public datasets.
- Require authentication for private farmer features.
- Enforce authorization on the backend, not only in the frontend.
- Avoid exposing farm coordinates or personal information through public endpoints.
- Never commit passwords, API keys, tokens, or credentials.
- Use environment variables for secrets.
- Provide clear information about what farm data are collected and why.
- Collect only the data needed for the intended functionality.
- Avoid using farmer-provided information for model training without an appropriate, transparent consent process.
- Avoid presenting an illustrative demonstration profile as a real farmer's record.

Use synthetic demonstration data only when clearly labeled.

---

## 12. User Experience and Accessibility

The primary users are:
- Farmers.
- Agricultural extension workers.
- Researchers.
- Students.
- Agricultural institutions.

The interface must:
- Use clear Spanish by default.
- Explain technical terms in accessible language.
- Use maps, charts, legends, and concise descriptions.
- Show data provenance, dates, units, and resolution.
- Provide accessible visual alternatives to maps and charts.
- Work on common desktop and mobile screen sizes where feasible.
- Avoid requiring users to understand remote sensing or machine learning.
- Clearly distinguish measured data, modeled products, derived indicators, and assumptions.

The project submission page and linked documentation must also be available in English.

---

## 13. Development Rules for Claude Code

Before modifying the repository:

1. Inspect the existing repository and current Git status.
2. Read this CLAUDE.md completely.
3. Identify existing frontend, backend, database, and pipeline implementations.
4. Respect the team's current architecture and coding conventions.
5. Propose a short implementation plan before major changes.
6. Identify files that will be created or modified.
7. Work incrementally.
8. Run appropriate tests and report their results.
9. Document new dependencies and setup instructions.

Do not:
- Rewrite the repository structure without approval.
- Delete or overwrite teammates' work.
- Fabricate data or citations.
- Invent API responses.
- Claim that a dataset was downloaded or validated when it was not.
- Present simulated data as real observations.
- Present model outputs as validated predictions without evaluation.
- Make destructive Git operations.
- Commit secrets or private farm information.
- Install unnecessary dependencies without explaining why.

When working with Git:
- Check `git status` before editing or committing.
- Do not force-push.
- Do not rewrite shared history.
- Do not overwrite remote branches.
- Prefer small, descriptive commits.
- Coordinate changes to shared files with the team.

---

## 14. Hackathon MVP Priorities

The full architecture describes the long-term product. The hackathon MVP must remain small enough to implement, integrate, test, and demonstrate reliably.

### Required MVP — Public Agricultural and Environmental Data Portal

1. A working public web interface.
2. A map of the selected pilot territory in Antioquia.
3. A small catalog of real, documented datasets.
4. At least one meaningful NASA-derived environmental analysis.
5. Colombian agricultural context from an official source.
6. Interactive visualization of selected variables.
7. At least one working data export or download.
8. A source and metadata panel.

### Required MVP — Farmer Decision-Support Workspace

1. A farmer-facing registration or demonstration login flow.
2. A farm profile with location and basic agricultural information.
3. Retrieval or display of environmental information associated with the farm's location.
4. A comparison of at least three rotation strategies.
5. Adjustable farmer priorities.
6. Explainable benefits, risks, assumptions, and evidence.
7. A clear warning that the output is decision support and requires local validation.

If full authentication is not feasible, use a clearly labeled demonstration account or prototype flow. Do not imply that private user data are securely stored if the security architecture has not been implemented.

### Prioritization

Prioritize:
1. A functional and coherent end-to-end experience.
2. Real NASA data integration.
3. Colombian agricultural relevance.
4. Explainable rotation comparisons.
5. Data provenance and uncertainty.
6. A clear demonstration of local impact.

Defer complex model training, full multi-source automation, advanced user management, and large-scale infrastructure if they threaten the working MVP.

---

## 15. Award Strategy

### Best Use of Data

Demonstrate:
- NASA data are essential to the analytical results.
- NASA observations are combined with relevant Colombian and international sources.
- Data are processed reproducibly.
- Spatial and temporal resolution are respected.
- Users can explore and download data.
- Metadata and provenance are transparent.
- Derived indicators have clear definitions and limitations.
- The platform turns complex observations into useful agricultural information.

### Local Impact Award

Demonstrate:
- A specific agricultural problem in an identifiable Colombian territory.
- Relevance to farmers and agricultural extension workers.
- A farmer-centered interface.
- Adaptation to farm-specific information and priorities.
- Useful, understandable rotation scenarios.
- A credible path to validation with local experts and farmers.
- Potential to expand to other Colombian territories.

Never claim community validation or demonstrated improvements in crop yields unless the team has actually established them.

---

## 16. Definition of Success

The platform succeeds when:

### A data portal user can:
1. Select a territory in Colombia.
2. Discover available agricultural and environmental datasets.
3. Visualize environmental and agricultural variables.
4. Compare spatial or temporal patterns.
5. Understand the origin, resolution, and limitations of the data.
6. Download supported datasets for further analysis.

### A farmer can:
1. Create or access a private farm profile.
2. Register relevant farm and agricultural information.
3. Explore available environmental conditions for the farm's location.
4. Compare at least three crop-rotation strategies.
5. Adjust priorities and see the resulting trade-offs.
6. Understand the evidence, risks, uncertainty, and information gaps.
7. Identify what should be validated with local agricultural expertise.

The platform must be scientifically responsible, transparent, useful, accessible, and demonstrably connected to NASA Earth observations.

# PROJECT DECISION UPDATE — NOVEMBER 2026

This section contains the latest approved project decisions. If older sections conflict with this update, follow this section.

## 1. Product Identity and Geographic Scope

Product name: Not yet defined.

Positioning:
"Territorial intelligence for more resilient agriculture."

Agricultural Intelligence Platform is an agricultural intelligence platform that integrates satellite observations, environmental information, agricultural datasets, and local knowledge to support better agricultural decisions.

### Geographic strategy

- Hackathon implementation and demonstration: Antioquia, Colombia.
- Initial pilot: selected municipalities and agricultural contexts in Antioquia.
- Long-term expansion: other Colombian departments and agricultural regions.
- The platform must support geographic expansion without requiring major architectural changes.

IMPORTANT:
Antioquia is the initial implementation scope, not a permanent product limitation.

Avoid hardcoding municipalities, departments, crop catalogs, or geographic boundaries in frontend components or business logic.

Geographic information must be managed through data and configuration.

## 2. Product Modules

### Public Agricultural and Environmental Data Portal

Public agricultural and environmental data portal.

Main capabilities:
- Interactive geographic exploration.
- Municipality selection.
- Agricultural and crop information.
- Environmental variable visualization.
- Historical data exploration.
- Dataset metadata and provenance.
- Filtering and downloading datasets when supported.

Target users:
Researchers, students, institutions, agricultural professionals, and the general public.

### Farmer Decision-Support Workspace

Private farmer-centered workspace.

Main capabilities:
- User registration and authentication.
- Farm profile creation.
- Geographic farm information.
- Soil and environmental characteristics.
- Previous crop history.
- Farmer priorities and constraints.
- Comparison of crop rotation strategies.
- Explainable decision-support recommendations.

The platform supports farmer decisions and does not replace professional agronomic advice.

## 3. Official Technical Architecture

The approved architecture is:

- Frontend: Angular.
- Backend: FastAPI.
- Database: PostgreSQL with PostGIS.
- Data ingestion and processing: Python.
- Geospatial processing: appropriate Python geospatial libraries.
- Shared contracts: OpenAPI and JSON Schema where appropriate.
- Infrastructure: Docker and Docker Compose.

Angular is the official web application frontend.

Do not introduce Streamlit as an alternative primary frontend.

The frontend communicates with the backend through documented HTTP API endpoints.

Do not expose NASA credentials, private API keys, database credentials, or secrets in frontend code.

Before introducing new frameworks or dependencies, inspect the existing repository and obtain approval.

## 4. Frontend Ownership and Responsibilities

The primary frontend workstream is responsible for:

- User experience and interface design.
- Angular application structure.
- Navigation and routing.
- Reusable UI components.
- Responsive layouts.
- Interactive maps.
- Data visualization.
- Forms and validation.
- Frontend state management.
- API integration.
- Accessibility and usability.

The frontend should be developed independently of backend implementation details through clear API contracts and mock services when necessary.

Mock data must be explicitly identified as simulated.

Do not present simulated data as real NASA or Colombian institutional observations.

## 5. Visual Design Direction

The product should communicate scientific credibility, agricultural relevance, and technological innovation.

Visual principles:
- Modern scientific and geospatial aesthetic.
- Clean, professional interface.
- Earth-inspired colors.
- Consistent typography and spacing.
- Strong information hierarchy.
- Clear maps, charts, legends, and metadata.
- Responsive desktop, tablet, and mobile experiences.
- Spanish as the default interface language.

Avoid excessive decorative elements and unnecessary complexity.

Prioritize usability for farmers who may not have technical or scientific backgrounds.

## 6. Frontend Module Structure

The proposed Angular feature organization is:

- core/: configuration, authentication, HTTP services.
- features/map/: geographic visualization.
- features/crops/: crop information and rotations.
- features/analysis/: analytical results and charts.
- features/calendar/: agricultural calendar.
- shared/: reusable components.

The implementation must follow the actual existing repository structure. This is a logical organization proposal, not permission to reorganize existing files automatically.

## 7. Scientific Communication and Data Integrity

Every displayed dataset or analytical result must clearly communicate its source and limitations.

Distinguish:
- Satellite observations.
- Modeled or derived products.
- Institutional datasets.
- Ground observations.
- Farmer-provided information.
- Simulated demonstration data.
- Model outputs and assumptions.

Do not imply parcel-level accuracy when the source has coarser spatial resolution.

Do not describe an experimental or unvalidated model as a reliable prediction.

Recommendations should be explainable, evidence-based, and transparent about uncertainty.

## 8. Hosting and Domain Strategy

GoDaddy may be used for domain registration and DNS management, subject to team approval.

Domain registration and application hosting are separate decisions.

The frontend, backend, and database hosting providers must be evaluated independently.

Do not commit credentials, domain administration information, deployment secrets, or private configuration files to GitHub.

## 9. Hackathon MVP Priorities

The first implementation must prioritize:

1. A polished and functional homepage.
2. A clear public Data module.
3. A usable geographic exploration experience for Antioquia.
4. A farmer-centered Farm interface.
5. Farm profile and crop history forms.
6. Comparison of at least three rotation scenarios.
7. Transparent data sources, assumptions, and limitations.
8. A coherent end-to-end demonstration.

Avoid implementing unnecessary infrastructure or advanced machine learning features before the core demonstration works.