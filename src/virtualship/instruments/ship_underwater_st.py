from dataclasses import dataclass
from typing import ClassVar

import numpy as np

from parcels import ParticleSet, ScipyParticle
from virtualship.instruments.base import Instrument
from virtualship.instruments.sensors import SensorType
from virtualship.instruments.types import InstrumentType
from virtualship.utils import (
    add_dummy_UV,
    build_particle_class_from_sensors,
    register_instrument,
)

# =====================================================
# SECTION: Dataclass
# =====================================================


@dataclass
class Underwater_ST:
    """Underwater_ST configuration."""

    name: ClassVar[str] = "Underwater_ST"


# =====================================================
# SECTION: fixed/mechanical Particle Variables (non-sampling)
# =====================================================

# Underwater ST has no fixed/mechanical variables, only sensor variables.
_ST_FIXED_VARIABLES: list = []


# =====================================================
# SECTION: Kernels
# =====================================================


# define function sampling Salinity
def _sample_salinity(particle, fieldset, time):
    particle.salinity = fieldset.S[time, particle.depth, particle.lat, particle.lon]


# define function sampling Temperature
def _sample_temperature(particle, fieldset, time):
    particle.temperature = fieldset.T[time, particle.depth, particle.lat, particle.lon]


_ST_SENSOR_KERNELS: dict[SensorType, callable] = {
    SensorType.TEMPERATURE: _sample_temperature,
    SensorType.SALINITY: _sample_salinity,
}


# =====================================================
# SECTION: Instrument Class
# =====================================================


@register_instrument(InstrumentType.UNDERWATER_ST)
class Underwater_STInstrument(Instrument):
    """Underwater_ST instrument class."""

    def __init__(self, expedition, from_data):
        """Initialize Underwater_STInstrument."""
        variables = (
            expedition.instruments_config.ship_underwater_st_config.active_variables()
        )
        spacetime_buffer_size = {
            "latlon": 0.25,  # [degrees]
            "time": 0.0,  # [days]
        }
        limit_spec = {
            "spatial": True
        }  # spatial limits; lat/lon constrained to waypoint locations + buffer

        super().__init__(
            expedition,
            variables,
            add_bathymetry=False,
            allow_time_extrapolation=True,
            verbose_progress=False,
            spacetime_buffer_size=spacetime_buffer_size,
            limit_spec=limit_spec,
            from_data=from_data,
        )

    def simulate(self, measurements, out_path) -> None:
        """Simulate underway salinity and temperature measurements."""
        DEPTH = -2.0

        measurements.sort(key=lambda p: p.time)

        fieldset = self.load_input_data()

        # add dummy U
        add_dummy_UV(fieldset)  # TODO: parcels v3 bodge; remove when parcels v4 is used

        # build dynamic particle class from the active sensors
        st_config = self.expedition.instruments_config.ship_underwater_st_config
        _ShipSTParticle = build_particle_class_from_sensors(
            st_config.sensors, _ST_FIXED_VARIABLES, ScipyParticle
        )

        particleset = ParticleSet.from_list(
            fieldset=fieldset,
            pclass=_ShipSTParticle,
            lon=0.0,
            lat=0.0,
            depth=DEPTH,
            time=0,
        )

        out_file = particleset.ParticleFile(name=out_path, outputdt=np.inf)

        # build kernel list from active sensors only
        sampling_kernels = [
            _ST_SENSOR_KERNELS[sc.sensor_type]
            for sc in st_config.sensors
            if sc.enabled and sc.sensor_type in _ST_SENSOR_KERNELS
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
