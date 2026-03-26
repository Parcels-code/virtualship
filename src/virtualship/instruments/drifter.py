from dataclasses import dataclass
from datetime import timedelta
from typing import ClassVar

import numpy as np

from parcels import AdvectionRK4, ParticleSet, Variable
from virtualship.instruments.base import Instrument
from virtualship.instruments.types import InstrumentType, SensorType
from virtualship.models.spacetime import Spacetime
from virtualship.utils import (
    _random_noise,
    build_particle_class_from_sensors,
    register_instrument,
)

# =====================================================
# SECTION: Dataclass
# =====================================================


@dataclass
class Drifter:
    """Drifter configuration."""

    name: ClassVar[str] = "Drifter"
    spacetime: Spacetime
    depth: float  # depth at which it floats and samples
    lifetime: timedelta | None  # if none, lifetime is infinite


# =====================================================
# SECTION: fixed/mechanical Particle Variables (non-sampling)
# =====================================================

_DRIFTER_FIXED_VARIABLES = [
    Variable("has_lifetime", dtype=np.int8),  # bool
    Variable("age", dtype=np.float32, initial=0.0),
    Variable("lifetime", dtype=np.float32),
]

# =====================================================
# SECTION: Kernels
# =====================================================


def _sample_temperature(particle, fieldset, time):
    particle.temperature = fieldset.T[time, particle.depth, particle.lat, particle.lon]


def _check_lifetime(particle, fieldset, time):
    if particle.has_lifetime == 1:
        particle.age += particle.dt
        if particle.age >= particle.lifetime:
            particle.delete()


_DRIFTER_SENSOR_KERNELS: dict[SensorType, callable] = {
    SensorType.TEMPERATURE: _sample_temperature,
}


# =====================================================
# SECTION: Instrument Class
# =====================================================


@register_instrument(InstrumentType.DRIFTER)
class DrifterInstrument(Instrument):
    """Drifter instrument class."""

    def __init__(self, expedition, from_data):
        """Initialize DrifterInstrument."""
        sensor_variables = (
            expedition.instruments_config.drifter_config.active_variables()
        )
        variables = {
            "U": "uo",
            "V": "vo",
            **sensor_variables,
        }  # advection variables (U and V) are always required for argo float simulation; sensor variables come from config
        spacetime_buffer_size = {
            "latlon": None,
            "time": expedition.instruments_config.drifter_config.lifetime.total_seconds()
            / (24 * 3600),  # [days]
        }
        limit_spec = {
            "spatial": False,  # no spatial limits; generate global fieldset
            "depth_min": abs(
                expedition.instruments_config.drifter_config.depth_meter
            ),  # [meters]
            "depth_max": abs(
                expedition.instruments_config.drifter_config.depth_meter
            ),  # [meters]
        }

        super().__init__(
            expedition,
            variables,
            add_bathymetry=False,
            allow_time_extrapolation=False,
            verbose_progress=True,
            spacetime_buffer_size=spacetime_buffer_size,
            limit_spec=limit_spec,
            from_data=from_data,
        )

    def simulate(self, measurements, out_path) -> None:
        """Simulate Drifter measurements."""
        OUTPUT_DT = timedelta(hours=5)
        DT = timedelta(minutes=5)

        if len(measurements) == 0:
            print(
                "No drifters provided. Parcels currently crashes when providing an empty particle set, so no drifter simulation will be done and no files will be created."
            )
            # TODO when Parcels supports it this check can be removed.
            return

        fieldset = self.load_input_data()

        # build dynamic particle class from the active sensors
        drifter_config = self.expedition.instruments_config.drifter_config
        _DrifterParticle = build_particle_class_from_sensors(
            drifter_config.sensors, _DRIFTER_FIXED_VARIABLES
        )

        # define parcel particles
        lat_release = [
            drifter.spacetime.location.lat + _random_noise() for drifter in measurements
        ]  # with small random noise to get different trajectories for multiple drifters released at same waypoint
        lon_release = [
            drifter.spacetime.location.lon + _random_noise() for drifter in measurements
        ]

        drifter_particleset = ParticleSet(
            fieldset=fieldset,
            pclass=_DrifterParticle,
            lat=lat_release,
            lon=lon_release,
            depth=[drifter.depth for drifter in measurements],
            time=[drifter.spacetime.time for drifter in measurements],
            has_lifetime=[
                1 if drifter.lifetime is not None else 0 for drifter in measurements
            ],
            lifetime=[
                0 if drifter.lifetime is None else drifter.lifetime.total_seconds()
                for drifter in measurements
            ],
        )

        # define output file for the simulation
        out_file = drifter_particleset.ParticleFile(
            name=out_path,
            outputdt=OUTPUT_DT,
            chunks=[len(drifter_particleset), 100],
        )

        # determine end time for simulation, from fieldset (which itself is controlled by drifter lifetimes)
        endtime = fieldset.time_origin.fulltime(fieldset.U.grid.time_full[-1])

        # build kernel list from active sensors only
        sample_kernels = [
            _DRIFTER_SENSOR_KERNELS[sc.sensor_type]
            for sc in drifter_config.sensors
            if sc.enabled and sc.sensor_type in _DRIFTER_SENSOR_KERNELS
        ]

        # execute simulation
        drifter_particleset.execute(
            [AdvectionRK4, *sample_kernels, _check_lifetime],
            endtime=endtime,
            dt=DT,
            output_file=out_file,
            verbose_progress=self.verbose_progress,
        )
