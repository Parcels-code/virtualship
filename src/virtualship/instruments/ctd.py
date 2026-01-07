from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, ClassVar

import numpy as np

from parcels import Particle, ParticleFile, ParticleSet, Variable
from parcels._core.statuscodes import StatusCode
from virtualship.instruments.base import Instrument
from virtualship.instruments.types import InstrumentType

if TYPE_CHECKING:
    from virtualship.models.spacetime import Spacetime
from virtualship.utils import register_instrument

# =====================================================
# SECTION: Dataclass
# =====================================================


@dataclass
class CTD:
    """CTD configuration."""

    name: ClassVar[str] = "CTD"
    spacetime: "Spacetime"
    min_depth: float
    max_depth: float


# =====================================================
# SECTION: Particle Class
# =====================================================

_CTDParticle = Particle.add_variable(
    [
        Variable("salinity", dtype=np.float32, initial=np.nan),
        Variable("temperature", dtype=np.float32, initial=np.nan),
        Variable("raising", dtype=np.int8, initial=0.0),  # bool. 0 is False, 1 is True.
        Variable("max_depth", dtype=np.float32),
        Variable("min_depth", dtype=np.float32),
        Variable("winch_speed", dtype=np.float32),
    ]
)


# =====================================================
# SECTION: Kernels
# =====================================================


def _sample_temperature(particles, fieldset):
    particles.temperature = fieldset.T[
        particles.time, particles.z, particles.lat, particles.lon
    ]


def _sample_salinity(particles, fieldset):
    particles.salinity = fieldset.S[
        particles.time, particles.z, particles.lat, particles.lon
    ]


# TODO: these kernels are not the same as CTD_BGC?!


def _ctd_sinking(particles, fieldset):
    for i in range(len(particles)):
        if particles[i].raising == 0:
            particles[i].dz = (
                -particles[i].winch_speed * particles[i].dt / np.timedelta64(1, "s")
            )
            if particles[i].z + particles[i].dz < particles[i].max_depth:
                particles[i].raising = 1
                particles[i].dz = -particles[i].dz


def _ctd_rising(particles, fieldset):
    for i in range(len(particles)):
        if particles[i].raising == 1:
            particles[i].dz = (
                particles[i].winch_speed * particles[i].dt / np.timedelta64(1, "s")
            )
            if particles[i].z + particles[i].dz > particles[i].min_depth:
                particles[i].state = StatusCode.Delete


# =====================================================
# SECTION: Instrument Class
# =====================================================


@register_instrument(InstrumentType.CTD)
class CTDInstrument(Instrument):
    """CTD instrument class."""

    def __init__(self, expedition, from_data):
        """Initialize CTDInstrument."""
        variables = {"S": "so", "T": "thetao"}
        limit_spec = {
            "spatial": True
        }  # spatial limits; lat/lon constrained to waypoint locations + buffer

        super().__init__(
            expedition,
            variables,
            add_bathymetry=True,
            allow_time_extrapolation=True,
            verbose_progress=False,
            spacetime_buffer_size=None,
            limit_spec=limit_spec,
            from_data=from_data,
        )

    def simulate(self, measurements, out_path) -> None:
        """Simulate CTD measurements."""
        WINCH_SPEED = 1.0  # sink and rise speed in m/s
        DT = 10  # dt of CTD simulation integrator
        OUTPUT_DT = timedelta(seconds=10)  # output dt for CTD simulation

        if len(measurements) == 0:
            print(
                "No CTDs provided. Parcels currently crashes when providing an empty particle set, so no CTD simulation will be done and no files will be created."
            )
            # TODO when Parcels supports it this check can be removed.
            return

        fieldset = self.load_input_data()

        # deploy time for all ctds should be later than fieldset start time
        if not all(
            [
                np.datetime64(ctd.spacetime.time) >= fieldset.time_interval.left
                for ctd in measurements
            ]
        ):
            raise ValueError("CTD deployed before fieldset starts.")

        # depth the ctd will go to. shallowest between ctd max depth and bathymetry.
        # TODO: update with the SampleBathy kernel as before in edito-hackathon branch?
        max_depths = [
            max(
                ctd.max_depth,
                fieldset.bathymetry.eval(
                    z=np.array([0], dtype=np.float32),
                    y=np.array([ctd.spacetime.location.lat], dtype=np.float32),
                    x=np.array([ctd.spacetime.location.lon], dtype=np.float32),
                    time=fieldset.time_interval.left,
                ),
            )
            for ctd in measurements
        ]

        # CTD depth can not be too shallow, because kernel would break.
        # This shallow is not useful anyway, no need to support.
        if not all([max_depth <= -DT * WINCH_SPEED for max_depth in max_depths]):
            raise ValueError(
                f"CTD max_depth or bathymetry shallower than maximum {-DT * WINCH_SPEED}"
            )

        # define parcel particles
        ctd_particleset = ParticleSet(
            fieldset=fieldset,
            pclass=_CTDParticle,
            lon=[ctd.spacetime.location.lon for ctd in measurements],
            lat=[ctd.spacetime.location.lat for ctd in measurements],
            z=[ctd.min_depth for ctd in measurements],
            time=[np.datetime64(ctd.spacetime.time) for ctd in measurements],
            max_depth=max_depths,
            min_depth=[ctd.min_depth for ctd in measurements],
            winch_speed=[WINCH_SPEED for _ in measurements],
        )

        # define output file for the simulation
        out_file = ParticleFile(store=out_path, outputdt=OUTPUT_DT)

        # execute simulation
        ctd_particleset.execute(
            [_sample_salinity, _sample_temperature, _ctd_sinking, _ctd_rising],
            endtime=fieldset.time_interval.right,
            dt=np.timedelta64(DT, "s"),
            verbose_progress=self.verbose_progress,
            output_file=out_file,
        )

        # there should be no particles left, as they delete themselves when they resurface
        if len(ctd_particleset) != 0:
            raise ValueError(
                "Simulation ended before CTD resurfaced. This most likely means the field time dimension did not match the simulation time span."
            )
