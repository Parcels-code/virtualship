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
from virtualship.utils import register_instrument

# =====================================================
# SECTION: Kernels
# =====================================================


# N.B. underway 'kernels' are special cases, where the particleset is not needed, and the kernel is not passed to `pset.execute()` as would be done for a typical Parcels workflow.
# Instead, the 'kernel' function is used only once to evaluate the fieldset at given times, depths, lats, lons.


def _sample_underway_velocity(fieldset: parcels.FieldSet, coords: UnderwayCoordinates):
    # eval
    u, v = fieldset.UV.eval(
        t=coords.times, z=coords.depths, x=coords.lons, y=coords.lats
    )

    # convert from degrees s-1 to metres s-1
    u = u * 1852 * 60 * np.cos(np.deg2rad(coords.lats))
    v = v * 1852 * 60

    return u, v


# =====================================================
# SECTION: Instrument Class
# =====================================================


@register_instrument(InstrumentType.ADCP)
class ADCPInstrument(UnderwayInstrument):
    """ADCP instrument class."""

    sensor_kernels: ClassVar[dict[SensorType, Callable]] = {
        SensorType.VELOCITY: _sample_underway_velocity,
    }

    def __init__(self, expedition, from_data):
        """Initialize ADCPInstrument."""
        variables = expedition.instruments_config.adcp_config.active_variables()

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
        """Simulate ADCP measurements."""
        adcp_config = self.expedition.instruments_config.adcp_config

        config_max_depth = adcp_config.max_depth_meter

        if config_max_depth < -1600.0:
            print(
                f"\n\n⚠️  Warning: The configured ADCP max depth of {abs(config_max_depth)} m exceeds the 1600 m limit for the technology (e.g. https://www.geomar.de/en/research/fb1/fb1-po/observing-systems/adcp)."
                "\n\n This expedition will continue using the prescribed configuration. However, note, the results will not necessarily represent authentic ADCP instrument readings and could also lead to slower simulations ."
                "\n\n If this was unintented, consider re-adjusting your ADCP configuration in your expedition.yaml or via `virtualship plan`.\n\n"
            )

        MAX_DEPTH = config_max_depth
        MIN_DEPTH = -5.0
        NUM_BINS = adcp_config.num_bins

        measurements.sort(key=lambda p: p.time)

        fieldset = self.load_input_data()

        # use first active field for time reference
        _time_ref_key = next(iter(self.variables))
        _time_ref_field = getattr(fieldset, _time_ref_key)
        fieldset_starttime = _time_ref_field.data.time.isel(time=0).values

        # times in seconds since fieldset time origin, expanded across depth bins
        times = np.array(
            [
                (np.datetime64(point.time) - fieldset_starttime)
                / np.timedelta64(1, "s")
                for point in measurements
            ]
        )

        lons = np.array([point.location.lon for point in measurements])
        lats = np.array([point.location.lat for point in measurements])
        bins = np.linspace(MAX_DEPTH, MIN_DEPTH, NUM_BINS)

        # full sampling coordinates
        coords = UnderwayCoordinates(
            times=np.repeat(times, NUM_BINS),
            lons=np.repeat(lons, NUM_BINS),
            lats=np.repeat(lats, NUM_BINS),
            depths=np.tile(bins, len(times)),
        )

        sampled = self._sample_underway(
            config_sensors=adcp_config.sensors, fieldset=fieldset, coords=coords
        )

        self._to_parquet(
            dat_arrays=sampled,
            var_names=self.variables.keys(),
            fieldset_time_origin=fieldset_starttime,
            out_path=out_path,
            coords=coords,
        )
