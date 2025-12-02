from dataclasses import dataclass
from datetime import timedelta
from typing import ClassVar

import numpy as np

from parcels import AdvectionRK4, JITParticle, ParticleSet, Variable
from virtualship.instruments.base import Instrument
from virtualship.instruments.types import InstrumentType
from virtualship.models.spacetime import Spacetime
from virtualship.utils import _random_noise, register_instrument

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
# SECTION: Particle Class
# =====================================================

_DrifterParticle = JITParticle.add_variables(
    [
        Variable("temperature", dtype=np.float32, initial=np.nan),
        Variable("has_lifetime", dtype=np.int8),  # bool
        Variable("age", dtype=np.float32, initial=0.0),
        Variable("lifetime", dtype=np.float32),
    ]
)

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


# =====================================================
# SECTION: Instrument Class
# =====================================================


@register_instrument(InstrumentType.DRIFTER)
class DrifterInstrument(Instrument):
    """Drifter instrument class."""

    def __init__(self, expedition, from_data):
        """Initialize DrifterInstrument."""
        variables = {"U": "uo", "V": "vo", "T": "thetao"}
        spacetime_buffer_size = {
            "latlon": 12.0,  # [degrees]
            "time": 63.0,  # [days]
        }
        limit_spec = {
            "depth_min": 1.0,  # [meters]
            "depth_max": 1.0,  # [meters]
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
        ENDTIME = None

        if len(measurements) == 0:
            print(
                "No drifters provided. Parcels currently crashes when providing an empty particle set, so no drifter simulation will be done and no files will be created."
            )
            # TODO when Parcels supports it this check can be removed.
            return

        fieldset = self.load_input_data()

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

        # get earliest between fieldset end time and prescribed end time
        fieldset_endtime = fieldset.time_origin.fulltime(fieldset.U.grid.time_full[-1])
        if ENDTIME is None:
            actual_endtime = fieldset_endtime
        elif ENDTIME > fieldset_endtime:
            print("WARN: Requested end time later than fieldset end time.")
            actual_endtime = fieldset_endtime
        else:
            actual_endtime = np.timedelta64(ENDTIME)

        # execute simulation
        drifter_particleset.execute(
            [AdvectionRK4, _sample_temperature, _check_lifetime],
            endtime=actual_endtime,
            dt=DT,
            output_file=out_file,
            verbose_progress=self.verbose_progress,
        )

        # if there are more particles left than the number of drifters with an indefinite endtime, warn the user
        if len(drifter_particleset.particledata) > len(
            [d for d in measurements if d.lifetime is None]
        ):
            print(
                "WARN: Some drifters had a life time beyond the end time of the fieldset or the requested end time."
            )
