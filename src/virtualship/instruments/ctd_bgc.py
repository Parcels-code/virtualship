from dataclasses import dataclass
from datetime import timedelta
from typing import ClassVar

import numpy as np

from parcels import Particle, ParticleSet, Variable
from parcels._core.statuscodes import StatusCode
from virtualship.instruments.base import Instrument
from virtualship.instruments.types import InstrumentType
from virtualship.models.spacetime import Spacetime
from virtualship.utils import register_instrument

# =====================================================
# SECTION: Dataclass
# =====================================================


@dataclass
class CTD_BGC:
    """CTD_BGC configuration."""

    name: ClassVar[str] = "CTD_BGC"
    spacetime: Spacetime
    min_depth: float
    max_depth: float


# =====================================================
# SECTION: Particle Class
# =====================================================

_CTD_BGCParticle = Particle.add_variable(
    [
        Variable("o2", dtype=np.float32, initial=np.nan),
        Variable("chl", dtype=np.float32, initial=np.nan),
        Variable("no3", dtype=np.float32, initial=np.nan),
        Variable("po4", dtype=np.float32, initial=np.nan),
        Variable("ph", dtype=np.float32, initial=np.nan),
        Variable("phyc", dtype=np.float32, initial=np.nan),
        Variable("nppv", dtype=np.float32, initial=np.nan),
        Variable("raising", dtype=np.int8, initial=0.0),  # bool. 0 is False, 1 is True.
        Variable("max_depth", dtype=np.float32),
        Variable("min_depth", dtype=np.float32),
        Variable("winch_speed", dtype=np.float32),
    ]
)

# =====================================================
# SECTION: Kernels
# =====================================================


def _sample_o2(particles, fieldset):
    particles.o2 = fieldset.o2[
        particles.time, particles.z, particles.lat, particles.lon
    ]


def _sample_chlorophyll(particles, fieldset):
    particles.chl = fieldset.chl[
        particles.time, particles.z, particles.lat, particles.lon
    ]


def _sample_nitrate(particles, fieldset):
    particles.no3 = fieldset.no3[
        particles.time, particles.z, particles.lat, particles.lon
    ]


def _sample_phosphate(particles, fieldset):
    particles.po4 = fieldset.po4[
        particles.time, particles.z, particles.lat, particles.lon
    ]


def _sample_ph(particles, fieldset):
    particles.ph = fieldset.ph[
        particles.time, particles.z, particles.lat, particles.lon
    ]


def _sample_phytoplankton(particles, fieldset):
    particles.phyc = fieldset.phyc[
        particles.time, particles.z, particles.lat, particles.lon
    ]


def _sample_primary_production(particles, fieldset):
    particles.nppv = fieldset.nppv[
        particles.time, particles.z, particles.lat, particles.lon
    ]


def _ctd_bgc_cast(particles, fieldset):
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


@register_instrument(InstrumentType.CTD_BGC)
class CTD_BGCInstrument(Instrument):
    """CTD_BGC instrument class."""

    def __init__(self, expedition, from_data):
        """Initialize CTD_BGCInstrument."""
        variables = {
            "o2": "o2",
            "chl": "chl",
            "no3": "no3",
            "po4": "po4",
            "ph": "ph",
            "phyc": "phyc",
            "nppv": "nppv",
        }
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
        """Simulate BGC CTD measurements using Parcels."""
        WINCH_SPEED = 1.0  # sink and rise speed in m/s
        DT = 10.0  # dt of CTD_BGC simulation integrator
        OUTPUT_DT = timedelta(seconds=10)  # output dt for CTD_BGC simulation

        if len(measurements) == 0:
            print(
                "No BGC CTDs provided. Parcels currently crashes when providing an empty particle set, so no BGC CTD simulation will be done and no files will be created."
            )
            # TODO when Parcels supports it this check can be removed.
            return

        fieldset = self.load_input_data()

        # # add dummy U
        # add_dummy_UV(fieldset)  # TODO: parcels v3 bodge; remove when parcels v4 is used

        fieldset_starttime = fieldset.o2.grid.time_origin.fulltime(
            fieldset.o2.grid.time_full[0]
        )
        fieldset_endtime = fieldset.o2.grid.time_origin.fulltime(
            fieldset.o2.grid.time_full[-1]
        )

        # deploy time for all ctds should be later than fieldset start time
        if not all(
            [
                np.datetime64(ctd_bgc.spacetime.time) >= fieldset_starttime
                for ctd_bgc in measurements
            ]
        ):
            raise ValueError("BGC CTD deployed before fieldset starts.")

        # depth the bgc ctd will go to. shallowest between bgc ctd max depth and bathymetry.
        max_depths = [
            max(
                ctd_bgc.max_depth,
                fieldset.bathymetry.eval(
                    z=0,
                    y=ctd_bgc.spacetime.location.lat,
                    x=ctd_bgc.spacetime.location.lon,
                    time=0,
                ),
            )
            for ctd_bgc in measurements
        ]

        # CTD depth can not be too shallow, because kernel would break.
        # This shallow is not useful anyway, no need to support.
        if not all([max_depth <= -DT * WINCH_SPEED for max_depth in max_depths]):
            raise ValueError(
                f"BGC CTD max_depth or bathymetry shallower than maximum {-DT * WINCH_SPEED}"
            )

        # define parcel particles
        ctd_bgc_particleset = ParticleSet(
            fieldset=fieldset,
            pclass=_CTD_BGCParticle,
            lon=[ctd_bgc.spacetime.location.lon for ctd_bgc in measurements],
            lat=[ctd_bgc.spacetime.location.lat for ctd_bgc in measurements],
            depth=[ctd_bgc.min_depth for ctd_bgc in measurements],
            time=[ctd_bgc.spacetime.time for ctd_bgc in measurements],
            max_depth=max_depths,
            min_depth=[ctd_bgc.min_depth for ctd_bgc in measurements],
            winch_speed=[WINCH_SPEED for _ in measurements],
        )

        # define output file for the simulation
        out_file = ctd_bgc_particleset.ParticleFile(name=out_path, outputdt=OUTPUT_DT)

        # execute simulation
        ctd_bgc_particleset.execute(
            [
                _sample_o2,
                _sample_chlorophyll,
                _sample_nitrate,
                _sample_phosphate,
                _sample_ph,
                _sample_phytoplankton,
                _sample_primary_production,
                _ctd_bgc_cast,
            ],
            endtime=fieldset_endtime,
            dt=DT,
            verbose_progress=self.verbose_progress,
            output_file=out_file,
        )

        # there should be no particles left, as they delete themselves when they resurface
        if len(ctd_bgc_particleset.particledata) != 0:
            raise ValueError(
                "Simulation ended before BGC CTD resurfaced. This most likely means the field time dimension did not match the simulation time span."
            )
