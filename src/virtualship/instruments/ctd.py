from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, ClassVar

import numpy as np

from parcels import Particle, ParticleSet, Variable
from parcels._core.statuscodes import StatusCode
from virtualship.instruments.base import Instrument
from virtualship.instruments.types import InstrumentType

if TYPE_CHECKING:
    from virtualship.models.spacetime import Spacetime
from virtualship.utils import add_dummy_UV, register_instrument

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

# TODO: aim for singular _ctd_cast kernel...!


def _ctd_cast(particles, fieldset):
    particles_lowering = particles[particles.raising == 0]
    particles_raising = particles[particles.raising == 1]

    # lowering
    particles_lowering.dz = -particles_lowering.winch_speed * particles_lowering.dt
    particles_lowering.raising = np.where(
        particles_lowering.z + particles_lowering.dz < particles_lowering.max_depth,
        1,
        particles_lowering.raising,
    )

    # raising
    particles_raising.dz = particles_raising.winch_speed * particles_raising.dt
    particles_raising.state = np.where(
        particles_raising.z + particles_raising.dz > particles_raising.min_depth,
        StatusCode.Delete,
        particles_raising.state,
    )


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
        DT = 10.0  # dt of CTD simulation integrator
        OUTPUT_DT = timedelta(seconds=10)  # output dt for CTD simulation

        if len(measurements) == 0:
            print(
                "No CTDs provided. Parcels currently crashes when providing an empty particle set, so no CTD simulation will be done and no files will be created."
            )
            # TODO when Parcels supports it this check can be removed.
            return

        fieldset = self.load_input_data()

        # add dummy U
        add_dummy_UV(fieldset)  # TODO: parcels v3 bodge; remove when parcels v4 is used

        fieldset_starttime = fieldset.T.grid.time_origin.fulltime(
            fieldset.T.grid.time_full[0]
        )
        fieldset_endtime = fieldset.T.grid.time_origin.fulltime(
            fieldset.T.grid.time_full[-1]
        )

        # deploy time for all ctds should be later than fieldset start time
        if not all(
            [
                np.datetime64(ctd.spacetime.time) >= fieldset_starttime
                for ctd in measurements
            ]
        ):
            raise ValueError("CTD deployed before fieldset starts.")

        # depth the ctd will go to. shallowest between ctd max depth and bathymetry.
        max_depths = [
            max(
                ctd.max_depth,
                fieldset.bathymetry.eval(
                    z=0,
                    y=ctd.spacetime.location.lat,
                    x=ctd.spacetime.location.lon,
                    time=0,
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
            depth=[ctd.min_depth for ctd in measurements],
            time=[ctd.spacetime.time for ctd in measurements],
            max_depth=max_depths,
            min_depth=[ctd.min_depth for ctd in measurements],
            winch_speed=[WINCH_SPEED for _ in measurements],
        )

        # define output file for the simulation
        out_file = ctd_particleset.ParticleFile(name=out_path, outputdt=OUTPUT_DT)

        # execute simulation
        ctd_particleset.execute(
            [_sample_salinity, _sample_temperature, _ctd_cast],
            endtime=fieldset_endtime,
            dt=DT,
            verbose_progress=self.verbose_progress,
            output_file=out_file,
        )

        # there should be no particles left, as they delete themselves when they resurface
        if len(ctd_particleset.particledata) != 0:
            raise ValueError(
                "Simulation ended before CTD resurfaced. This most likely means the field time dimension did not match the simulation time span."
            )
