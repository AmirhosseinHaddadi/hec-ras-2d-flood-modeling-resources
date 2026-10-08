# ================================================================
# ERA5-LAND -> HOURLY HEC-RAS NETCDF4 FILES
#
# NO GOOGLE EARTH ENGINE
#
# Workflow:
#   AOI Shapefile
#        ↓
#   Copernicus CDS ERA5-Land
#        ↓
#   Hourly precipitation
#        ↓
#   m -> mm
#        ↓
#   Reproject to YOUR .prj
#        ↓
#   One .nc4 file for EACH hour
#
# Output example:
#   ERA5L_APCP_2023070201.nc4
#   ERA5L_APCP_2023070202.nc4
#   ...
#
# HEC-RAS:
#   Data Type = PER-CUM
#   Units = mm
#   Interval = 1 hour
#   Time reference = UTC
# ================================================================


# ================================================================
# 0. AUTO-INSTALL REQUIRED PACKAGES
# ================================================================

import sys
import subprocess
import importlib.util


def install(package, import_name=None):

    name = import_name or package

    if importlib.util.find_spec(name) is None:

        print("Installing:", package)

        subprocess.check_call([
            sys.executable,
            "-m",
            "pip",
            "install",
            package
        ])


install("cdsapi")
install("numpy")
install("pandas")
install("xarray")
install("netCDF4")
install("geopandas")
install("shapely")
install("pyproj")
install("rasterio")


# ================================================================
# 1. IMPORTS
# ================================================================

import os
import zipfile
import shutil

from pathlib import Path

import cdsapi
import numpy as np
import pandas as pd
import xarray as xr
import geopandas as gpd

from pyproj import CRS

from rasterio.transform import from_origin

from rasterio.warp import (
    reproject,
    Resampling
)

from netCDF4 import (
    Dataset,
    date2num
)


# ================================================================
# 2. USER SETTINGS
# ================================================================

# ------------------------------------------------
# YOUR AOI / BASIN SHAPEFILE
# ------------------------------------------------

AOI_SHP = r"D:\hec-ras\DEM\AOI.shp"


# ------------------------------------------------
# YOUR HEC-RAS PROJECTION FILE
# Example:
# NAD83 / UTM Zone 18N
# ------------------------------------------------

TARGET_PRJ = r"D:\hec-ras\26918.prj"


# ------------------------------------------------
# OUTPUT FOLDER
# ------------------------------------------------

OUTPUT_ROOT = Path(
    r"D:\hec-ras\Layers\precipitation"
)


# ------------------------------------------------
# COPERNICUS CDS TOKEN
#
# Get from:
# https://cds.climate.copernicus.eu/profile
#
# If you already configured ~/.cdsapirc,
# leave this empty:
#
# CDS_TOKEN = ""
# ------------------------------------------------

CDS_TOKEN = "17c4fbd2-2a2b-4d15-b3c0-d87ab3ace5e9"


# ------------------------------------------------
# HEC-RAS SIMULATION PERIOD
#
# These are BOUNDARIES of the simulation.
#
# First rainfall interval:
# 02 Jul 00:00 -> 02 Jul 01:00
#
# Last rainfall interval:
# 14 Jul 23:00 -> 15 Jul 00:00
#
# Number of hourly files = 312
# ------------------------------------------------

SIM_START = pd.Timestamp(
    "2023-07-02 00:00:00"
)

SIM_END = pd.Timestamp(
    "2023-07-15 00:00:00"
)


# ------------------------------------------------
# BUFFER AROUND AOI
# ------------------------------------------------

BUFFER_KM = 20


# ------------------------------------------------
# TARGET OUTPUT CELL SIZE
#
# ERA5-Land original spatial resolution is
# approximately 9-11 km.
#
# 10000 m is reasonable.
# ------------------------------------------------

TARGET_CELL_SIZE = 10000.0


# ------------------------------------------------
# OUTPUT EXTENSION
# ------------------------------------------------

OUTPUT_EXTENSION = ".nc4"


# ================================================================
# 3. CREATE FOLDERS
# ================================================================

RAW_DIR = (
    OUTPUT_ROOT
    / "_CDS_RAW"
)

HOURLY_DIR = (
    OUTPUT_ROOT
    / "ERA5_HOURLY_NC4"
)


OUTPUT_ROOT.mkdir(
    parents=True,
    exist_ok=True
)

RAW_DIR.mkdir(
    parents=True,
    exist_ok=True
)

HOURLY_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ================================================================
# 4. READ TARGET .PRJ
# ================================================================

print("\n" + "=" * 75)
print("READING TARGET PROJECTION")
print("=" * 75)


with open(
    TARGET_PRJ,
    "r",
    encoding="utf-8",
    errors="ignore"
) as f:

    prj_wkt = f.read()


if not prj_wkt.strip():

    raise RuntimeError(
        "Target .prj file is empty."
    )


TARGET_CRS = CRS.from_wkt(
    prj_wkt
)


TARGET_EPSG = (
    TARGET_CRS.to_epsg()
)


print("Projection:")

print(
    TARGET_CRS.name
)


print("\nEPSG:")

print(
    TARGET_EPSG
)


if not TARGET_CRS.is_projected:

    raise RuntimeError(
        "Target .prj must be a projected CRS."
    )


# ================================================================
# 5. READ AOI
# ================================================================

print("\n" + "=" * 75)
print("READING AOI")
print("=" * 75)


aoi = gpd.read_file(
    AOI_SHP
)


if aoi.empty:

    raise RuntimeError(
        "AOI shapefile is empty."
    )


if aoi.crs is None:

    raise RuntimeError(
        "AOI shapefile has no CRS."
    )


print(
    "AOI CRS:",
    aoi.crs
)


# Keep geometry only

aoi = aoi[
    ["geometry"]
].copy()


# Repair geometry

try:

    aoi["geometry"] = (
        aoi.geometry.make_valid()
    )

except Exception:

    aoi["geometry"] = (
        aoi.geometry.buffer(0)
    )


# Dissolve all polygons

aoi = aoi.dissolve()


# ================================================================
# 6. PROJECT AOI TO TARGET CRS
# ================================================================

aoi_target = aoi.to_crs(
    TARGET_CRS
)


# Buffer in metres

aoi_target[
    "geometry"
] = aoi_target.geometry.buffer(
    BUFFER_KM * 1000
)


target_bounds = (
    aoi_target.total_bounds
)


target_minx = float(
    target_bounds[0]
)

target_miny = float(
    target_bounds[1]
)

target_maxx = float(
    target_bounds[2]
)

target_maxy = float(
    target_bounds[3]
)


print("\nTarget AOI + buffer:")

print(
    target_minx,
    target_miny,
    target_maxx,
    target_maxy
)


# ================================================================
# 7. CONVERT AOI TO WGS84 FOR CDS
# ================================================================

aoi_wgs = aoi_target.to_crs(
    "EPSG:4326"
)


west, south, east, north = (
    aoi_wgs.total_bounds
)


# A small extra margin around the CDS request

margin = 0.15


west -= margin
east += margin
south -= margin
north += margin


CDS_AREA = [

    float(north),

    float(west),

    float(south),

    float(east)
]


print("\nCDS AREA:")

print(
    "North:",
    north
)

print(
    "West:",
    west
)

print(
    "South:",
    south
)

print(
    "East:",
    east
)


# ================================================================
# 8. CDS CLIENT
# ================================================================

print("\n" + "=" * 75)
print("CONNECTING TO COPERNICUS CDS")
print("=" * 75)


if (
    CDS_TOKEN
    and
    "PASTE_YOUR" not in CDS_TOKEN
):

    client = cdsapi.Client(

        url=(
            "https://cds.climate."
            "copernicus.eu/api"
        ),

        key=CDS_TOKEN
    )

else:

    # Uses ~/.cdsapirc

    client = cdsapi.Client()


print("Connected.")


# ================================================================
# 9. DOWNLOAD RAW ERA5-LAND
#
# We download a little more data than needed,
# then create the exact 312 hourly files locally.
#
# This is MUCH better than sending 312 separate
# requests to CDS.
# ================================================================

print("\n" + "=" * 75)
print("DOWNLOADING ERA5-LAND")
print("=" * 75)


fetch_start = SIM_START

fetch_end = SIM_END


months = pd.period_range(

    fetch_start,

    fetch_end,

    freq="M"
)


raw_nc_files = []


for month_period in months:

    year = (
        month_period.year
    )

    month = (
        month_period.month
    )


    first_month_day = pd.Timestamp(

        year=year,

        month=month,

        day=1
    )


    last_month_day = (

        first_month_day

        + pd.offsets.MonthEnd(1)

    )


    request_start = max(

        fetch_start.normalize(),

        first_month_day
    )


    request_end = min(

        fetch_end.normalize(),

        last_month_day
    )


    dates = pd.date_range(

        request_start,

        request_end,

        freq="D"
    )


    day_list = [

        d.strftime("%d")

        for d in dates
    ]


    hour_list = [

        f"{h:02d}:00"

        for h in range(24)
    ]


    download_file = (

        RAW_DIR

        / f"ERA5Land_"
          f"{year}"
          f"{month:02d}.download"
    )


    if download_file.exists():

        download_file.unlink()


    request = {

        "variable": [
            "total_precipitation"
        ],

        "year":
            str(year),

        "month":
            f"{month:02d}",

        "day":
            day_list,

        "time":
            hour_list,

        "data_format":
            "netcdf",

        "download_format":
            "unarchived",

        "area":
            CDS_AREA
    }


    print(
        "\nDownloading:",
        f"{year}-{month:02d}"
    )


    result = client.retrieve(

        "reanalysis-era5-land",

        request
    )


    result.download(

        str(
            download_file
        )
    )


    # ============================================================
    # CDS MAY RETURN ZIP OR NETCDF
    # ============================================================

    if zipfile.is_zipfile(
        download_file
    ):

        extract_dir = (

            RAW_DIR

            / (
                f"ERA5Land_"
                f"{year}"
                f"{month:02d}"
            )
        )


        if extract_dir.exists():

            shutil.rmtree(
                extract_dir
            )


        extract_dir.mkdir()


        with zipfile.ZipFile(
            download_file,
            "r"
        ) as z:

            z.extractall(
                extract_dir
            )


        found = sorted(

            extract_dir.rglob(
                "*.nc"
            )
        )


        if not found:

            raise RuntimeError(
                "CDS ZIP contained no NetCDF."
            )


        raw_nc_files.extend(
            found
        )


    else:

        nc_file = (

            RAW_DIR

            / (
                f"ERA5Land_"
                f"{year}"
                f"{month:02d}.nc"
            )
        )


        if nc_file.exists():

            nc_file.unlink()


        download_file.rename(
            nc_file
        )


        raw_nc_files.append(
            nc_file
        )


print("\nRaw files:")

for f in raw_nc_files:

    print(
        f
    )


# ================================================================
# 10. FIND PRECIPITATION VARIABLE
# ================================================================

def find_precip_variable(ds):

    for name in [

        "tp",

        "total_precipitation"

    ]:

        if name in ds.data_vars:

            return name


    for name in ds.data_vars:

        lower = name.lower()

        if (
            "precipitation" in lower
            or
            lower == "tp"
        ):

            return name


    raise RuntimeError(

        "Total precipitation variable "
        "was not found.\n"

        f"Available variables: "
        f"{list(ds.data_vars)}"
    )


# ================================================================
# 11. READ AND STANDARDIZE RAW DATA
# ================================================================

arrays = []


for file in raw_nc_files:

    print(
        "\nReading:",
        file
    )


    ds = xr.open_dataset(

        file,

        engine="netcdf4"
    )


    pvar = (
        find_precip_variable(
            ds
        )
    )


    da = ds[
        pvar
    ]


    print(
        "Variable:",
        pvar
    )


    print(
        "Units:",
        da.attrs.get(
            "units",
            "unknown"
        )
    )


    # ------------------------------------------------------------
    # Handle expver if present
    # ------------------------------------------------------------

    if "expver" in da.dims:

        parts = []

        for i in range(
            da.sizes[
                "expver"
            ]
        ):

            parts.append(

                da.isel(

                    expver=i,

                    drop=True
                )
            )


        merged = parts[0]


        for part in parts[1:]:

            merged = (
                merged.combine_first(
                    part
                )
            )


        da = merged


    # ------------------------------------------------------------
    # Standardize coordinate names
    # ------------------------------------------------------------

    rename = {}


    if "valid_time" in da.coords:

        rename[
            "valid_time"
        ] = "time"


    if "lat" in da.coords:

        rename[
            "lat"
        ] = "latitude"


    if "lon" in da.coords:

        rename[
            "lon"
        ] = "longitude"


    if rename:

        da = da.rename(
            rename
        )


    if "time" not in da.coords:

        raise RuntimeError(
            "Time coordinate not found."
        )


    if "latitude" not in da.coords:

        raise RuntimeError(
            "Latitude coordinate not found."
        )


    if "longitude" not in da.coords:

        raise RuntimeError(
            "Longitude coordinate not found."
        )


    # ------------------------------------------------------------
    # Drop unused singleton dimensions
    # ------------------------------------------------------------

    for dim in list(
        da.dims
    ):

        if (
            dim
            not in
            [
                "time",
                "latitude",
                "longitude"
            ]
            and
            da.sizes[dim] == 1
        ):

            da = da.isel(

                {
                    dim: 0
                },

                drop=True
            )


    da = da.transpose(

        "time",

        "latitude",

        "longitude"
    )


    da.load()


    arrays.append(
        da
    )


    ds.close()


# ================================================================
# 12. CONCATENATE DATA
# ================================================================

raw = xr.concat(

    arrays,

    dim="time"
)


raw = raw.sortby(
    "time"
)


raw_times = pd.DatetimeIndex(

    pd.to_datetime(
        raw.time.values
    )
)


# Remove duplicate timestamps

_, unique_indices = np.unique(

    raw_times,

    return_index=True
)


raw = raw.isel(

    time=np.sort(
        unique_indices
    )
)


raw_times = pd.DatetimeIndex(

    pd.to_datetime(
        raw.time.values
    )
)


print("\nRaw time range:")

print(
    raw_times[0]
)

print(
    raw_times[-1]
)


# ================================================================
# 13. VERIFY HOURLY CONTINUITY
# ================================================================

expected_raw_times = pd.date_range(

    raw_times[0],

    raw_times[-1],

    freq="1h"
)


missing = expected_raw_times.difference(

    raw_times
)


if len(missing) > 0:

    raise RuntimeError(

        "Missing ERA5 timestamps:\n"

        + "\n".join(

            str(x)

            for x in missing
        )
    )


# ================================================================
# 14. DE-ACCUMULATE ERA5-LAND
#
# ECMWF ERA5-Land total precipitation:
#
# 01:00 = accumulation 00 -> 01
# 02:00 = accumulation 00 -> 02
# ...
# 23:00 = accumulation 00 -> 23
# 00:00 = accumulation of full PREVIOUS day
#
# Therefore:
#
# hour 01:
#    hourly = cumulative(01)
#
# hour 02..23:
#    hourly = cumulative(t) - cumulative(t-1)
#
# hour 00:
#    hourly = cumulative(00) - cumulative(previous 23)
#
# ================================================================

print("\n" + "=" * 75)
print("CALCULATING TRUE HOURLY PRECIPITATION")
print("=" * 75)


cum_m = raw.values.astype(
    np.float64
)


hourly_m = np.full_like(

    cum_m,

    np.nan,

    dtype=np.float64
)


for i, timestamp in enumerate(
    raw_times
):


    # ------------------------------------------------------------
    # First accumulation after midnight
    # ------------------------------------------------------------

    if timestamp.hour == 1:

        hourly_m[i] = (
            cum_m[i]
        )


    else:

        if i == 0:

            continue


        time_difference = (

            raw_times[i]

            - raw_times[i - 1]
        )


        if time_difference != pd.Timedelta(
            hours=1
        ):

            raise RuntimeError(

                "Non-hourly data near "

                f"{timestamp}"
            )


        hourly_m[i] = (

            cum_m[i]

            - cum_m[i - 1]
        )


# Remove tiny numerical negatives

hourly_m[

    (hourly_m < 0)

    &

    (hourly_m > -1e-7)

] = 0.0


minimum = np.nanmin(
    hourly_m
)


if minimum < -1e-6:

    print(

        "WARNING: negative precipitation "
        "was detected."
    )

    print(
        "Minimum:",
        minimum
    )


    hourly_m = np.maximum(

        hourly_m,

        0.0
    )


# ================================================================
# 15. METRES -> MILLIMETRES
# ================================================================

hourly_mm = (

    hourly_m

    * 1000.0
)


# ================================================================
# 16. PREPARE SOURCE GRID
# ================================================================

lat = np.asarray(

    raw.latitude.values,

    dtype=float
)


lon = np.asarray(

    raw.longitude.values,

    dtype=float
)


# Longitude must be ascending

if lon[0] > lon[-1]:

    lon = lon[::-1]

    hourly_mm = hourly_mm[
        :,
        :,
        ::-1
    ]


# Latitude must be NORTH -> SOUTH

if lat[0] < lat[-1]:

    lat = lat[::-1]

    hourly_mm = hourly_mm[
        :,
        ::-1,
        :
    ]


lon_res = abs(

    float(

        np.median(
            np.diff(
                lon
            )
        )
    )
)


lat_res = abs(

    float(

        np.median(
            np.diff(
                lat
            )
        )
    )
)


SOURCE_TRANSFORM = from_origin(

    lon.min()
    - lon_res / 2,

    lat.max()
    + lat_res / 2,

    lon_res,

    lat_res
)


SOURCE_CRS = CRS.from_epsg(
    4326
)


# ================================================================
# 17. CREATE ONE FIXED TARGET GRID
# ================================================================

xmin = (

    np.floor(

        target_minx

        / TARGET_CELL_SIZE

    )

    * TARGET_CELL_SIZE
)


ymin = (

    np.floor(

        target_miny

        / TARGET_CELL_SIZE

    )

    * TARGET_CELL_SIZE
)


xmax = (

    np.ceil(

        target_maxx

        / TARGET_CELL_SIZE

    )

    * TARGET_CELL_SIZE
)


ymax = (

    np.ceil(

        target_maxy

        / TARGET_CELL_SIZE

    )

    * TARGET_CELL_SIZE
)


WIDTH = int(

    round(

        (xmax - xmin)

        / TARGET_CELL_SIZE
    )
)


HEIGHT = int(

    round(

        (ymax - ymin)

        / TARGET_CELL_SIZE
    )
)


TARGET_TRANSFORM = from_origin(

    xmin,

    ymax,

    TARGET_CELL_SIZE,

    TARGET_CELL_SIZE
)


print("\nTarget grid:")

print(
    "Columns:",
    WIDTH
)

print(
    "Rows:",
    HEIGHT
)

print(
    "Cell size:",
    TARGET_CELL_SIZE
)


# ================================================================
# 18. X/Y COORDINATES
# ================================================================

x_coordinates = (

    TARGET_TRANSFORM.c

    +

    (
        np.arange(
            WIDTH
        )
        + 0.5
    )

    * TARGET_TRANSFORM.a
)


y_coordinates = (

    TARGET_TRANSFORM.f

    +

    (
        np.arange(
            HEIGHT
        )
        + 0.5
    )

    * TARGET_TRANSFORM.e
)


# ================================================================
# 19. EXACT HOURLY OUTPUT INTERVALS
#
# Simulation:
#
# 02 Jul 00 -> 15 Jul 00
#
# Outputs:
#
# 02 Jul 01 = rain 00 -> 01
# 02 Jul 02 = rain 01 -> 02
# ...
# 15 Jul 00 = rain 14 Jul 23 -> 15 Jul 00
#
# ================================================================

output_end_times = pd.date_range(

    SIM_START
    + pd.Timedelta(hours=1),

    SIM_END,

    freq="1h"
)


print("\nExpected hourly files:")

print(
    len(output_end_times)
)


# ================================================================
# 20. HELPER TO WRITE ONE HEC-RAS NC4 FILE
# ================================================================

def write_hourly_nc4(

    output_path,

    grid,

    interval_start,

    interval_end
):

    fill_value = np.float32(
        -9999.0
    )


    # ------------------------------------------------------------
    # Create NetCDF4
    # ------------------------------------------------------------

    nc = Dataset(

        output_path,

        mode="w",

        format="NETCDF4"
    )


    # ------------------------------------------------------------
    # Global attributes
    # ------------------------------------------------------------

    nc.Conventions = "CF-1.8"

    nc.title = (
        "ERA5-Land hourly precipitation "
        "for HEC-RAS"
    )

    nc.source = (
        "Copernicus Climate Data Store - "
        "ERA5-Land"
    )

    nc.time_zone = "UTC"

    nc.data_type = "PER-CUM"

    nc.time_interval = "1 HOUR"

    nc.units = "mm"

    nc.time_coverage_start = (
        interval_start.strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
    )

    nc.time_coverage_end = (
        interval_end.strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
    )


    # ------------------------------------------------------------
    # Dimensions
    # ------------------------------------------------------------

    nc.createDimension(
        "time",
        1
    )

    nc.createDimension(
        "y",
        HEIGHT
    )

    nc.createDimension(
        "x",
        WIDTH
    )

    nc.createDimension(
        "nv",
        2
    )


    # ------------------------------------------------------------
    # TIME
    # Timestamp represents END of rainfall interval.
    # ------------------------------------------------------------

    time_var = nc.createVariable(

        "time",

        "f8",

        ("time",)
    )


    time_units = (
        "hours since "
        "1970-01-01 00:00:00 UTC"
    )


    time_var.units = time_units

    time_var.calendar = "standard"

    time_var.standard_name = "time"

    time_var.long_name = (
        "end time of precipitation interval"
    )

    time_var.axis = "T"

    time_var.bounds = "time_bounds"


    time_var[:] = date2num(

        [
            interval_end.to_pydatetime()
        ],

        units=time_units,

        calendar="standard"
    )


    # ------------------------------------------------------------
    # TIME BOUNDS
    # ------------------------------------------------------------

    time_bounds = nc.createVariable(

        "time_bounds",

        "f8",

        (
            "time",
            "nv"
        )
    )


    time_bounds.units = time_units


    time_bounds[0, :] = date2num(

        [
            interval_start.to_pydatetime(),

            interval_end.to_pydatetime()
        ],

        units=time_units,

        calendar="standard"
    )


    # ------------------------------------------------------------
    # X
    # ------------------------------------------------------------

    x_var = nc.createVariable(

        "x",

        "f8",

        ("x",)
    )


    x_var[:] = (
        x_coordinates
    )


    x_var.standard_name = (
        "projection_x_coordinate"
    )

    x_var.long_name = "Easting"

    x_var.units = "m"

    x_var.axis = "X"


    # ------------------------------------------------------------
    # Y
    # ------------------------------------------------------------

    y_var = nc.createVariable(

        "y",

        "f8",

        ("y",)
    )


    y_var[:] = (
        y_coordinates
    )


    y_var.standard_name = (
        "projection_y_coordinate"
    )

    y_var.long_name = "Northing"

    y_var.units = "m"

    y_var.axis = "Y"


    # ------------------------------------------------------------
    # CRS
    # ------------------------------------------------------------

    crs_var = nc.createVariable(

        "crs",

        "i4"
    )


    cf_attrs = (
        TARGET_CRS.to_cf()
    )


    for key, value in (
        cf_attrs.items()
    ):

        try:

            crs_var.setncattr(
                key,
                value
            )

        except Exception:

            pass


    crs_var.spatial_ref = (
        TARGET_CRS.to_wkt()
    )


    crs_var.crs_wkt = (
        TARGET_CRS.to_wkt()
    )


    if TARGET_EPSG:

        crs_var.epsg_code = (
            f"EPSG:{TARGET_EPSG}"
        )


    crs_var.GeoTransform = (

        f"{TARGET_TRANSFORM.c} "
        f"{TARGET_TRANSFORM.a} "
        f"{TARGET_TRANSFORM.b} "
        f"{TARGET_TRANSFORM.f} "
        f"{TARGET_TRANSFORM.d} "
        f"{TARGET_TRANSFORM.e}"
    )


    # ------------------------------------------------------------
    # PRECIPITATION VARIABLE
    #
    # Name intentionally similar to AORC:
    # APCP_surface
    # ------------------------------------------------------------

    rain_var = nc.createVariable(

        "APCP_surface",

        "f4",

        (
            "time",
            "y",
            "x"
        ),

        fill_value=fill_value,

        zlib=True,

        complevel=4
    )


    rain_var.long_name = (
        "1-hour total precipitation"
    )

    rain_var.standard_name = (
        "precipitation_amount"
    )

    rain_var.units = "mm"

    rain_var.grid_mapping = "crs"

    rain_var.coordinates = (
        "time y x"
    )

    rain_var.cell_methods = (
        "time: sum "
        "(interval: 1 hour)"
    )

    rain_var.data_type = (
        "PER-CUM"
    )


    clean_grid = np.where(

        np.isfinite(
            grid
        ),

        grid,

        fill_value
    ).astype(
        np.float32
    )


    rain_var[
        0,
        :,
        :
    ] = clean_grid


    nc.close()


# ================================================================
# 21. PROCESS EVERY HOUR
# ================================================================

print("\n" + "=" * 75)
print("CREATING HOURLY HEC-RAS NC4 FILES")
print("=" * 75)


time_to_index = {

    pd.Timestamp(t):
        i

    for i, t in enumerate(
        raw_times
    )
}


created = 0


for end_time in output_end_times:


    if end_time not in time_to_index:

        raise RuntimeError(

            "ERA5 timestep missing: "

            + str(
                end_time
            )
        )


    source_index = (
        time_to_index[
            end_time
        ]
    )


    source_grid = (
        hourly_mm[
            source_index
        ]
    )


    # ------------------------------------------------------------
    # REPROJECT PRECIPITATION
    # ------------------------------------------------------------

    projected_grid = np.full(

        (
            HEIGHT,
            WIDTH
        ),

        np.nan,

        dtype=np.float32
    )


    reproject(

        source=(
            source_grid.astype(
                np.float32
            )
        ),

        destination=(
            projected_grid
        ),

        src_transform=(
            SOURCE_TRANSFORM
        ),

        src_crs=(
            SOURCE_CRS
        ),

        src_nodata=(
            np.nan
        ),

        dst_transform=(
            TARGET_TRANSFORM
        ),

        dst_crs=(
            TARGET_CRS
        ),

        dst_nodata=(
            np.nan
        ),

        # Precipitation is continuous
        resampling=(
            Resampling.bilinear
        )
    )


    # No negative rainfall

    projected_grid[

        projected_grid < 0

    ] = 0


    # ------------------------------------------------------------
    # INTERVAL
    # ------------------------------------------------------------

    start_time = (

        end_time

        - pd.Timedelta(
            hours=1
        )
    )


    # ------------------------------------------------------------
    # FILE NAME
    # ------------------------------------------------------------

    timestamp_string = (

        end_time.strftime(
            "%Y%m%d%H"
        )
    )


    filename = (

        "ERA5L_APCP_"

        + timestamp_string

        + OUTPUT_EXTENSION
    )


    output_path = (

        HOURLY_DIR

        / filename
    )


    # ------------------------------------------------------------
    # WRITE
    # ------------------------------------------------------------

    write_hourly_nc4(

        output_path,

        projected_grid,

        start_time,

        end_time
    )


    created += 1


    print(

        f"\r"
        f"{created}"
        f"/"
        f"{len(output_end_times)}"

        f"  {filename}",

        end=""
    )


print("\n")


# ================================================================
# 22. FINAL VALIDATION
# ================================================================

print("\n" + "=" * 75)
print("VALIDATING OUTPUT")
print("=" * 75)


hourly_files = sorted(

    HOURLY_DIR.glob(
        "*.nc4"
    )
)


print(
    "Files created:",
    len(hourly_files)
)


if (
    len(hourly_files)
    !=
    len(output_end_times)
):

    raise RuntimeError(

        "Wrong number of hourly files."
    )


# Open first file

first_file = (
    hourly_files[0]
)


with Dataset(

    first_file,

    "r"
) as nc:


    if (
        "APCP_surface"
        not in nc.variables
    ):

        raise RuntimeError(

            "APCP_surface missing "
            "from output."
        )


    test_data = (

        nc.variables[
            "APCP_surface"
        ][:]
    )


    print(
        "\nFirst file:"
    )

    print(
        first_file
    )


    print(
        "\nVariable:"
    )

    print(
        "APCP_surface"
    )


    print(
        "\nUnits:"
    )

    print(
        nc.variables[
            "APCP_surface"
        ].units
    )


    print(
        "\nTime coverage:"
    )

    print(
        nc.time_coverage_start
    )

    print(
        "->"
    )

    print(
        nc.time_coverage_end
    )


    print(
        "\nGrid minimum:"
    )

    print(
        float(
            np.ma.min(
                test_data
            )
        )
    )


    print(
        "\nGrid maximum:"
    )

    print(
        float(
            np.ma.max(
                test_data
            )
        )
    )


# ================================================================
# 23. FINISHED
# ================================================================

print("\n" + "=" * 75)
print("FINISHED")
print("=" * 75)


print(
    "\nHourly NC4 folder:"
)

print(
    HOURLY_DIR
)


print(
    "\nNumber of files:"
)

print(
    created
)


print(
    "\nFirst:"
)

print(
    hourly_files[0].name
)


print(
    "\nLast:"
)

print(
    hourly_files[-1].name
)


print(
    "\nProjection:"
)

print(
    TARGET_CRS.name
)


print(
    "\nEPSG:"
)

print(
    TARGET_EPSG
)


print(
    "\nHEC-RAS import settings:"
)

print(
    "Source     = GDAL Raster Files"
)

print(
    "Mode       = Multiple Raster Files"
)

print(
    "Variable   = APCP_surface"
)

print(
    "Data Type  = PER-CUM"
)

print(
    "Units      = mm"
)

print(
    "First Step = 1 hour"
)

print(
    "Time Shift = 0 hour if model uses UTC"
)