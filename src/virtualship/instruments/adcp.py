from collections.abc import Callable
from dataclasses import dataclass
from typing import ClassVar

import numpy as np

from virtualship.instruments.base import FetchSpec, Instrument
from virtualship.instruments.sensors import SensorType
from virtualship.instruments.types import InstrumentType
from virtualship.utils import _write_underway_to_parquet, register_instrument

# =====================================================
# SECTION: Dataclass
# =====================================================


@dataclass
class ADCP:
    """ADCP configuration."""

    name: ClassVar[str] = "ADCP"


# =====================================================
# SECTION: Kernels
# =====================================================


def _sample_velocity(particles, fieldset):
    particles.U, particles.V = fieldset.UV.eval(
        particles.t,
        particles.z,
        particles.x,
        particles.y,
    )


# =====================================================
# SECTION: Instrument Class
# =====================================================


@register_instrument(InstrumentType.ADCP)
class ADCPInstrument(Instrument):
    """ADCP instrument class."""

    sensor_kernels: ClassVar[dict[SensorType, Callable]] = {
        SensorType.VELOCITY: _sample_velocity,
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
        config_max_depth = (
            self.expedition.instruments_config.adcp_config.max_depth_meter
        )

        if config_max_depth < -1600.0:
            print(
                f"\n\n⚠️  Warning: The configured ADCP max depth of {abs(config_max_depth)} m exceeds the 1600 m limit for the technology (e.g. https://www.geomar.de/en/research/fb1/fb1-po/observing-systems/adcp)."
                "\n\n This expedition will continue using the prescribed configuration. However, note, the results will not necessarily represent authentic ADCP instrument readings and could also lead to slower simulations ."
                "\n\n If this was unintented, consider re-adjusting your ADCP configuration in your expedition.yaml or via `virtualship plan`.\n\n"
            )

        MAX_DEPTH = config_max_depth
        MIN_DEPTH = -5.0
        NUM_BINS = self.expedition.instruments_config.adcp_config.num_bins

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

        times_full = np.repeat(times, NUM_BINS)
        lons_full = np.repeat(lons, NUM_BINS)
        lats_full = np.repeat(lats, NUM_BINS)
        depths_full = np.tile(bins, len(times))

        u, v = fieldset.UV.eval(t=times_full, z=depths_full, x=lons_full, y=lats_full)

        _write_underway_to_parquet(
            dat_arrays=[u, v],
            var_names=self.variables.keys(),
            times_full=times_full,
            lons_full=lons_full,
            lats_full=lats_full,
            depths_full=depths_full,
            fieldset_time_origin=fieldset_starttime,
            out_path=out_path,
        )
