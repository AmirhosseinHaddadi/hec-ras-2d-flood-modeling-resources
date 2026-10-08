# HEC-RAS 2D Flood Modeling — Data, Scripts, and Supporting Materials

This repository contains the **data sources, lookup tables, scripts, and supporting materials required to build a 2D flood model in HEC-RAS**, with emphasis on terrain preparation, land-cover-based roughness, soil-based infiltration, gridded precipitation, and event-based unsteady-flow simulation.

The repository is intended to accompany an academic HEC-RAS flood-modeling tutorial and provide a reproducible starting point for students and researchers.

## Repository purpose

The workflow supported by this repository is:

1. Prepare and project a DEM.
2. Define or delineate the modeling domain.
3. Prepare land-cover data for Manning's roughness.
4. Prepare Hydrologic Soil Group (HSG) data.
5. Combine land cover and HSG information for SCS Curve Number infiltration parameters.
6. Download and prepare gridded precipitation data.
7. Configure HEC-RAS geometry, mesh, boundary conditions, infiltration, and meteorological forcing.
8. Run an unsteady 2D flood simulation.
9. Review and validate depth, velocity, hydrographs, and inundation extent.

## Repository structure

```text
HEC-RAS-Flood-Modeling-Materials/
│
├── README.md
├── requirements.txt
├── data/
│   └── dem/
│       └── USGS_10m_DEM.zip
├── lookup_tables/
│   └── HEC_RAS_SCS_ESA_HSG_Lookup.xlsx
├── scripts/
│   └── download_era5_precipitation_nc.py
├── docs/
│   └── DATA_SOURCES.md
└── examples/
    └── README.md
```

> Replace the placeholder filenames above with the exact filenames used in your project if they differ.

---

# 1. USGS 10 m DEM

A **10 m USGS Digital Elevation Model (DEM)** is used as the primary terrain source for the hydraulic model.

Recommended preprocessing before importing the DEM into HEC-RAS:

- inspect the raster for NoData gaps and artifacts;
- fill unwanted artificial sinks where appropriate;
- verify horizontal and vertical units;
- project the DEM to the same projected coordinate system used by the HEC-RAS project;
- preserve an appropriate raster resolution during reprojection;
- verify alignment with the study-area boundary and reference basemap.

Repository location:

```text
data/dem/USGS_10m_DEM.zip
```

---

# 2. ESA WorldCover for Manning's Roughness

Land-cover information is used to create spatially variable **Manning's n** values for the 2D Flow Area.

## Google Earth Engine — Land Cover Script

https://code.earthengine.google.com/2ace2a92e705f3fbaead6e78b3cc9755

The script is intended to:

- extract ESA WorldCover for the user-defined Area of Interest (AOI);
- prepare the land-cover raster for GIS / HEC-RAS use;
- support subsequent Manning's roughness classification.

Typical ESA WorldCover classes:

| Value | Land-Cover Class |
|---:|---|
| 10 | Tree Cover |
| 20 | Shrubland |
| 30 | Grassland |
| 40 | Cropland |
| 50 | Built-up |
| 60 | Bare / Sparse Vegetation |
| 70 | Snow and Ice |
| 80 | Permanent Water Bodies |
| 90 | Herbaceous Wetland |
| 95 | Mangroves |
| 100 | Moss and Lichen |

Manning's n values should be treated as **initial estimates** and reviewed against hydraulic literature, site conditions, aerial imagery, and calibration results.

---

# 3. Hydrologic Soil Group Data

Hydrologic Soil Group (HSG) information is used for the **SCS Curve Number infiltration method**.

## Google Earth Engine — Hydrologic Soil Group Script

https://code.earthengine.google.com/a5f6c79e3627123df338feb3e8f77610

Main HSG classes:

| Group | General Hydrologic Behavior |
|---|---|
| A | High infiltration / low runoff potential |
| B | Moderate-high infiltration |
| C | Moderate-low infiltration |
| D | Low infiltration / high runoff potential |

Dual groups such as **A/D, B/D, and C/D** may occur and should be interpreted according to the adopted drainage assumptions.

---

# 4. SCS Curve Number / Infiltration Lookup Table

The repository includes an Excel lookup table for combining:

- ESA land-cover classes;
- Hydrologic Soil Groups;
- SCS Curve Number values;
- Initial Abstraction Ratio;
- Minimum Infiltration Rate;
- HEC-RAS infiltration classification parameters.

Repository location:

```text
lookup_tables/HEC_RAS_SCS_ESA_HSG_Lookup.xlsx
```

This table can be used as a guide when populating the **Classification Parameters** table in the HEC-RAS SCS Curve Number infiltration layer.

> These values should be treated as starting parameters and reviewed against official HEC/NRCS guidance, local soil conditions, land-cover conditions, and calibration results.

---

# 5. ERA5-Land Gridded Precipitation

A Python script is included to download **ERA5-Land hourly precipitation** from the Copernicus Climate Data Store (CDS) and prepare hourly gridded precipitation for HEC-RAS.

Repository location:

```text
scripts/download_era5_precipitation_nc.py
```

The script is intended to:

- download ERA5-Land precipitation directly from Copernicus CDS;
- use a user-defined study-area shapefile;
- subset the data to the modeling region;
- convert precipitation to the required units;
- prepare hourly precipitation grids;
- reproject outputs to the HEC-RAS project coordinate system;
- save the results as NetCDF / NetCDF4 files suitable for gridded meteorological input.

Typical hourly output:

```text
ERA5L_APCP_2023070201.nc4
ERA5L_APCP_2023070202.nc4
ERA5L_APCP_2023070203.nc4
...
```

Suggested HEC-RAS import settings:

| Parameter | Setting |
|---|---|
| Variable | `APCP_surface` |
| Data Type | `PER-CUM` |
| Units | `mm` |
| First Timestep Duration | `1 hour` |
| Time Shift | `0 hr` when all model data are in UTC |

Always verify the imported precipitation in **RAS Mapper → Event Conditions → Precipitation** before running the model.

---

# 6. Recommended HEC-RAS Modeling Workflow

## Terrain preparation

```text
Download DEM
→ Fill / clean DEM
→ Define correct source CRS
→ Project Raster
→ Check units and alignment
→ Create HEC-RAS Terrain
```

## Watershed / modeling domain

```text
DEM
→ Flow Direction
→ Flow Accumulation
→ Pour Point
→ Snap Pour Point
→ Watershed
→ Raster to Polygon
```

## Land cover and Manning's n

```text
ESA WorldCover
→ Clip to AOI
→ Export raster
→ Build HEC-RAS Land Cover layer
→ Assign Manning's n values
```

## Soil and infiltration

```text
Hydrologic Soil Group
+
Land Cover
→ SCS Curve Number classification
→ HEC-RAS Infiltration Layer
```

## 2D geometry

```text
Create 2D Flow Area
→ Generate computational mesh
→ Add breaklines
→ Add refinement regions
→ Review cell quality
```

## Boundary conditions

Typical event-based setup:

- **Upstream:** Flow Hydrograph
- **Downstream:** Normal Depth or Stage Hydrograph, depending on available data

## Meteorological forcing

```text
ERA5-Land hourly precipitation
→ NetCDF / NetCDF4
→ Gridded Precipitation
```

## Simulation and results

Configure the simulation time window, computation interval, output intervals, numerical settings, initial conditions, and meteorological forcing. Review water depth, velocity, inundation extent, water-surface elevation, profile-line time series, and hydrographs.

---

# 7. Coordinate-System Consistency

All spatial inputs should be checked for consistent projection and units, including:

- DEM;
- watershed / AOI;
- land cover;
- soil / HSG;
- breaklines;
- refinement regions;
- boundary-condition lines;
- precipitation grids.

A projected coordinate system appropriate for the study area is generally preferred for HEC-RAS modeling.

Do not use **Define Projection** to intentionally convert coordinates. Use a true reprojection tool such as **Project Raster** or **Project** when coordinate values must be transformed.

---

# 8. Time-Series Consistency

For event-based simulations, ensure that these datasets use a consistent time reference:

- upstream flow hydrograph;
- precipitation;
- observed stage;
- downstream time series;
- simulation start/end time.

If precipitation is stored in UTC, either keep all forcing data and the simulation in UTC or apply a documented and consistent time conversion.

---

# 9. Recommended Quality-Control Checks

Before running HEC-RAS:

- verify terrain elevation and units;
- verify all spatial layers overlap correctly;
- check 2D mesh quality;
- confirm breaklines align with hydraulic controls;
- confirm BC Lines connect to appropriate 2D cell faces;
- verify upstream and downstream BC locations;
- inspect Manning's n values;
- inspect infiltration parameters;
- confirm precipitation grids are visible in RAS Mapper;
- verify precipitation timestamps;
- confirm flow-hydrograph coverage;
- check simulation start/end dates;
- verify computation timestep and model stability.

---

# 10. Validation

Where observations are available, compare model results against:

- measured discharge;
- observed stage;
- high-water marks;
- flood-inundation extent;
- satellite-derived flood maps;
- field observations.

A model should not be considered validated solely because it produces a visually reasonable flood map.

---

# 11. Software and Data Sources

Typical tools and providers used in this workflow include:

- HEC-RAS / RAS Mapper
- ArcMap / ArcGIS Pro
- QGIS
- Google Earth Engine
- Python
- Copernicus Climate Data Store
- USGS
- ESA WorldCover
- HEC-DSS / DSSVue, when required

---

# 12. Python Environment

Typical Python dependencies:

```text
cdsapi
numpy
pandas
xarray
netCDF4
geopandas
shapely
pyproj
rasterio
```

Install them with:

```bash
pip install -r requirements.txt
```

---

# 13. Large Files and Data Distribution

Large binary datasets such as DEM ZIP files, GeoTIFFs, NetCDF precipitation files, and HEC-RAS result HDF files can make a Git repository unnecessarily large.

For public distribution, consider:

- Git LFS;
- Zenodo;
- institutional storage;
- Google Drive / OneDrive;
- official source-download links.

If a dataset cannot legally be redistributed, store only the download instructions, source URL, processing script, and required metadata.

---

# 14. Suggested Citation / Acknowledgment

If this repository is used in academic work, cite the original software and data providers as applicable, including:

- U.S. Army Corps of Engineers — HEC-RAS;
- U.S. Geological Survey — elevation and streamflow data;
- European Space Agency — WorldCover;
- ECMWF / Copernicus Climate Change Service — ERA5-Land;
- the original HSG data provider;
- NRCS / HEC guidance used for SCS Curve Number parameters.

---

# 15. Disclaimer

This repository is intended for **research, education, and model-development support**.

Hydraulic and hydrologic parameters such as Manning's n, Curve Number, infiltration rate, boundary slopes, computational timestep, and mesh resolution are site-dependent. Example values and scripts should therefore be treated as **initial modeling guidance** and reviewed, calibrated, and validated for the specific study area before engineering or risk-management decisions are made.

---

# 16. Resource Index

| Resource | Description | Location / Link |
|---|---|---|
| ESA WorldCover Script | Land-cover extraction for the AOI | https://code.earthengine.google.com/2ace2a92e705f3fbaead6e78b3cc9755 |
| Hydrologic Soil Group Script | HSG extraction for the AOI | https://code.earthengine.google.com/a5f6c79e3627123df338feb3e8f77610 |
| USGS 10 m DEM | Terrain input | `data/dem/USGS_10m_DEM.zip` |
| SCS / HSG Lookup Table | HEC-RAS infiltration-classification guidance | `lookup_tables/HEC_RAS_SCS_ESA_HSG_Lookup.xlsx` |
| ERA5-Land Python Script | Hourly NetCDF precipitation preparation | `scripts/download_era5_precipitation_nc.py` |

---

## Suggested repository name

```text
hec-ras-2d-flood-modeling-resources
```

## Suggested GitHub description

> Reproducible data sources, GIS workflows, lookup tables, and Python scripts for HEC-RAS 2D flood modeling, including USGS DEM preparation, ESA WorldCover, Hydrologic Soil Groups, SCS Curve Number infiltration, and ERA5-Land gridded precipitation.

---

## Acknowledgment

This repository was developed as supporting material for academic training and research in **HEC-RAS 2D flood modeling**.
