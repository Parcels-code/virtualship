from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from typing import TYPE_CHECKING, Literal

import numpy as np

from parcels import Variable

if TYPE_CHECKING:
    pass


class SensorType(str, Enum):
    """Sensors available. Different intstruments mix and match these sensors as needed."""

    TEMPERATURE = "TEMPERATURE"
    SALINITY = "SALINITY"
    VELOCITY = "VELOCITY"
    OXYGEN = "OXYGEN"
    CHLOROPHYLL = "CHLOROPHYLL"
    NITRATE = "NITRATE"
    PHOSPHATE = "PHOSPHATE"
    PH = "PH"
    PHYTOPLANKTON = "PHYTOPLANKTON"
    PRIMARY_PRODUCTION = "PRIMARY_PRODUCTION"


@dataclass(frozen=True)
class _Sensor:
    type_: SensorType
    fs_key: str  # map to Parcels fieldset variables
    copernicus_var: str  # map to Copernicus Marine Service variable names
    category: Literal[
        "phys", "bgc"
    ]  # physical vs. biogeochemical variable, used for product ID selection logic
    particle_vars: list[Variable]  # particle variable(s) produced by this sensor


@lru_cache(maxsize=1)  # cache here so same dict is not rebuilt on every access
def SENSOR_REGISTRY() -> dict[SensorType, _Sensor]:
    """Cached accessor for the sensor registry (lazily via _build_sensor_registry, avoids circular import errors)."""
    return _build_sensor_registry()


# the copernicus_var field below is the bridge between this registry the Copernicus product-ID selection logic (PRODUCT_IDS, BGC_ANALYSIS_IDS, MONTHLY_BGC_REANALYSIS_IDS, etc.)
def _build_sensor_registry() -> dict[SensorType, _Sensor]:
    return {
        s.type_: s
        for s in [
            _Sensor(
                type_=SensorType.TEMPERATURE,
                fs_key="T",
                copernicus_var="thetao",
                category="phys",
                particle_vars=[
                    Variable("temperature", dtype=np.float32, initial=np.nan)
                ],
            ),
            _Sensor(
                type_=SensorType.SALINITY,
                fs_key="S",
                copernicus_var="so",
                category="phys",
                particle_vars=[Variable("salinity", dtype=np.float32, initial=np.nan)],
            ),
            _Sensor(
                type_=SensorType.VELOCITY,
                fs_key="UV",
                copernicus_var="uo",  # uo is primary var here... active_variables() in ADCPConfig expands to both uo and vo
                category="phys",
                particle_vars=[
                    Variable("U", dtype=np.float32, initial=np.nan),
                    Variable("V", dtype=np.float32, initial=np.nan),
                ],  # two particle variables associated with one sensor
            ),
            _Sensor(
                type_=SensorType.OXYGEN,
                fs_key="o2",
                copernicus_var="o2",
                category="bgc",
                particle_vars=[Variable("o2", dtype=np.float32, initial=np.nan)],
            ),
            _Sensor(
                type_=SensorType.CHLOROPHYLL,
                fs_key="chl",
                copernicus_var="chl",
                category="bgc",
                particle_vars=[Variable("chl", dtype=np.float32, initial=np.nan)],
            ),
            _Sensor(
                type_=SensorType.NITRATE,
                fs_key="no3",
                copernicus_var="no3",
                category="bgc",
                particle_vars=[Variable("no3", dtype=np.float32, initial=np.nan)],
            ),
            _Sensor(
                type_=SensorType.PHOSPHATE,
                fs_key="po4",
                copernicus_var="po4",
                category="bgc",
                particle_vars=[Variable("po4", dtype=np.float32, initial=np.nan)],
            ),
            _Sensor(
                type_=SensorType.PH,
                fs_key="ph",
                copernicus_var="ph",
                category="bgc",
                particle_vars=[Variable("ph", dtype=np.float32, initial=np.nan)],
            ),
            _Sensor(
                type_=SensorType.PHYTOPLANKTON,
                fs_key="phyc",
                copernicus_var="phyc",
                category="bgc",
                particle_vars=[Variable("phyc", dtype=np.float32, initial=np.nan)],
            ),
            _Sensor(
                type_=SensorType.PRIMARY_PRODUCTION,
                fs_key="nppv",
                copernicus_var="nppv",
                category="bgc",
                particle_vars=[Variable("nppv", dtype=np.float32, initial=np.nan)],
            ),
        ]
    }
