from collections.abc import Callable
from typing import ClassVar

import numpy as np
import parcels

from virtualship.instruments.base import (
    FetchSpec,
    UnderwayCoordinates,
    UnderwayInstrument,
)
from virtualship.instruments.sensors import SensorType
from virtualship.instruments.types import InstrumentType
from virtualship.utils import (
    register_instrument,
)

# =====================================================
# SECTION: Kernels
# =====================================================

# N.B. underway 'kernels' are special cases, where the particleset is not needed, and the kernel is not passed to `pset.execute()` as would be done for a typical Parcels workflow.
# Instead, the 'kernel' function is used only once to evaluate the fieldset at given times, depths, lats, lons.


def _sample_underway_salinity(fieldset: parcels.FieldSet, coords: UnderwayCoordinates):
    return fieldset.S.eval(
        t=coords.times, z=coords.depths, x=coords.lons, y=coords.lats
    )


def _sample_underway_temperature(
    fieldset: parcels.FieldSet, coords: UnderwayCoordinates
):
    return fieldset.T.eval(
        t=coords.times, z=coords.depths, x=coords.lons, y=coords.lats
    )


# =====================================================
# SECTION: Instrument Class
# =====================================================


@register_instrument(InstrumentType.UNDERWATER_ST)
class Underwater_STInstrument(UnderwayInstrument):
    """Underwater_ST instrument class."""

    sensor_kernels: ClassVar[dict[SensorType, Callable]] = {
        SensorType.TEMPERATURE: _sample_underway_temperature,
        SensorType.SALINITY: _sample_underway_salinity,
    }

    def __init__(self, expedition, from_data):
        """Initialize Underwater_STInstrument."""
        variables = (
            expedition.instruments_config.ship_underwater_st_config.active_variables()
        )

        super().__init__(
            expedition,
            variables,
            add_bathymetry=False,
            allow_time_extrapolation=True,
            verbose_progress=False,
            fetch_spec=FetchSpec(),
            from_data=from_data,
        )

    def simulate(self, measurements, out_path) -> None:
        """Simulate underway salinity and temperature measurements."""
        st_config = self.expedition.instruments_config.ship_underwater_st_config

        DEPTH = -2.0

        measurements.sort(key=lambda p: p.time)

        fieldset = self.load_input_data()

        # sampling times and locations
        fieldset_starttime = fieldset.time_interval.left
        times = np.array(
            [
                (np.datetime64(point.time) - fieldset_starttime)
                / np.timedelta64(1, "s")
                for point in measurements
            ]
        )
        lons = np.array([point.location.lon for point in measurements])
        lats = np.array([point.location.lat for point in measurements])
        coords = UnderwayCoordinates(
            times, lons, lats, depths=np.full_like(times, DEPTH)
        )

        sampled = self._sample_underway(
            config_sensors=st_config.sensors, fieldset=fieldset, coords=coords
        )

        self._to_parquet(
            dat_arrays=sampled,
            var_names=self.variables.keys(),
            fieldset_time_origin=fieldset_starttime,
            out_path=out_path,
            coords=coords,
        )
