from dataclasses import dataclass
from typing import ClassVar

import numpy as np
from parcels import ParticleSet, ScipyParticle

from virtualship.instruments.base import Instrument
from virtualship.instruments.sensors import SensorType
from virtualship.instruments.types import InstrumentType
from virtualship.utils import build_particle_class_from_sensors, register_instrument

# =====================================================
# SECTION: Dataclass
# =====================================================


@dataclass
class ADCP:
    """ADCP configuration."""

    name: ClassVar[str] = "ADCP"


# =====================================================
# SECTION: fixed/mechanical Particle Variables (non-sampling)
# =====================================================

# ADCP has no fixed/mechanical variables, only sensor variables.
_ADCP_FIXED_VARIABLES: list = []


# =====================================================
# SECTION: Kernels
# =====================================================


def _sample_velocity(particle, fieldset, time):
    particle.U, particle.V = fieldset.UV.eval(
        time, particle.depth, particle.lat, particle.lon, applyConversion=False
    )


_ADCP_SENSOR_KERNELS: dict[SensorType, callable] = {
    SensorType.VELOCITY: _sample_velocity,
}


# =====================================================
# SECTION: Instrument Class
# =====================================================


@register_instrument(InstrumentType.ADCP)
class ADCPInstrument(Instrument):
    """ADCP instrument class."""

    def __init__(self, expedition, from_data):
        """Initialize ADCPInstrument."""
        variables = expedition.instruments_config.adcp_config.active_variables()
        limit_spec = {
            "spatial": True
        }  # spatial limits; lat/lon constrained to waypoint locations + buffer

        super().__init__(
            expedition,
            variables,
            add_bathymetry=False,
            allow_time_extrapolation=True,
            verbose_progress=False,
            spacetime_buffer_size=None,
            limit_spec=limit_spec,
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

        # build dynamic particle class from the active sensors
        adcp_config = self.expedition.instruments_config.adcp_config
        _ADCPParticle = build_particle_class_from_sensors(
            adcp_config.sensors, _ADCP_FIXED_VARIABLES, ScipyParticle
        )

        bins = np.linspace(MAX_DEPTH, MIN_DEPTH, NUM_BINS)
        num_particles = len(bins)
        particleset = ParticleSet.from_list(
            fieldset=fieldset,
            pclass=_ADCPParticle,
            lon=np.full(
                num_particles, 0.0
            ),  # initial lat/lon are irrelevant and will be overruled later.s
            lat=np.full(num_particles, 0.0),
            depth=bins,
            time=0,
        )

        out_file = particleset.ParticleFile(name=out_path, outputdt=np.inf)

        # build kernel list from active sensors only
        sampling_kernels = [
            _ADCP_SENSOR_KERNELS[sc.sensor_type]
            for sc in adcp_config.sensors
            if sc.enabled and sc.sensor_type in _ADCP_SENSOR_KERNELS
        ]

        for point in measurements:
            particleset.lon_nextloop[:] = point.location.lon
            particleset.lat_nextloop[:] = point.location.lat
            particleset.time_nextloop[:] = fieldset.time_origin.reltime(
                np.datetime64(point.time)
            )

            particleset.execute(
                sampling_kernels,
                dt=1,
                runtime=1,
                verbose_progress=self.verbose_progress,
                output_file=out_file,
            )
