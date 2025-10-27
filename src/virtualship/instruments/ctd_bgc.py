"""CTD_BGC instrument."""

from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

import numpy as np
from parcels import FieldSet, Particle, ParticleFile, ParticleSet, Variable
from parcels._core.statuscodes import StatusCode

from virtualship.models import Spacetime


@dataclass
class CTD_BGC:
    """Configuration for a single BGC CTD."""

    spacetime: Spacetime
    min_depth: float
    max_depth: float


_CTD_BGCParticle = Particle.add_variable(
    [
        Variable("o2", dtype=np.float32, initial=np.nan),
        Variable("chl", dtype=np.float32, initial=np.nan),
        Variable("no3", dtype=np.float32, initial=np.nan),
        Variable("po4", dtype=np.float32, initial=np.nan),
        Variable("ph", dtype=np.float32, initial=np.nan),
        Variable("phyc", dtype=np.float32, initial=np.nan),
        Variable("zooc", dtype=np.float32, initial=np.nan),
        Variable("nppv", dtype=np.float32, initial=np.nan),
        Variable("raising", dtype=np.int8, initial=0.0),  # bool. 0 is False, 1 is True.
        Variable("max_depth", dtype=np.float32),
        Variable("min_depth", dtype=np.float32),
        Variable("winch_speed", dtype=np.float32),
    ]
)


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


def _sample_zooplankton(particles, fieldset):
    particles.zooc = fieldset.zooc[
        particles.time, particles.z, particles.lat, particles.lon
    ]


def _sample_primary_production(particles, fieldset):
    particles.nppv = fieldset.nppv[
        particles.time, particles.z, particles.lat, particles.lon
    ]


def _ctd_bgc_sinking(particles, fieldset):
    def ctd_lowering(p):
        p.dz = -particles.winch_speed * p.dt / np.timedelta64(1, "s")
        p.raising = np.where(p.z + p.dz < p.max_depth, 1, p.raising)
        p.dz = np.where(p.z + p.dz < p.max_depth, -p.dz, p.dz)

    ctd_lowering(particles[particles.raising == 0])


def _ctd_bgc_rising(particles, fieldset):
    def ctd_rising(p):
        p.dz = p.winch_speed * p.dt / np.timedelta64(1, "s")
        p.state = np.where(p.z + p.dz > p.min_depth, StatusCode.Delete, p.state)

    ctd_rising(particles[particles.raising == 1])


def simulate_ctd_bgc(
    fieldset: FieldSet,
    out_path: str | Path,
    ctd_bgcs: list[CTD_BGC],
    outputdt: timedelta,
) -> None:
    """
    Use Parcels to simulate a set of BGC CTDs in a fieldset.

    :param fieldset: The fieldset to simulate the BGC CTDs in.
    :param out_path: The path to write the results to.
    :param ctds: A list of BGC CTDs to simulate.
    :param outputdt: Interval which dictates the update frequency of file output during simulation
    :raises ValueError: Whenever provided BGC CTDs, fieldset, are not compatible with this function.
    """
    WINCH_SPEED = 1.0  # sink and rise speed in m/s
    DT = 10  # dt of CTD simulation integrator

    if len(ctd_bgcs) == 0:
        print(
            "No BGC CTDs provided. Parcels currently crashes when providing an empty particle set, so no BGC CTD simulation will be done and no files will be created."
        )
        # TODO when Parcels supports it this check can be removed.
        return

    # deploy time for all ctds should be later than fieldset start time
    if not all(
        [
            np.datetime64(ctd_bgc.spacetime.time) >= fieldset.time_interval.left
            for ctd_bgc in ctd_bgcs
        ]
    ):
        raise ValueError("BGC CTD deployed before fieldset starts.")

    # depth the bgc ctd will go to. shallowest between bgc ctd max depth and bathymetry.
    max_depths = [
        max(
            ctd_bgc.max_depth,
            fieldset.bathymetry.eval(
                z=np.array([0], dtype=np.float32),
                y=np.array([ctd_bgc.spacetime.location.lat], dtype=np.float32),
                x=np.array([ctd_bgc.spacetime.location.lon], dtype=np.float32),
                time=fieldset.time_interval.left,
            ),
        )
        for ctd_bgc in ctd_bgcs
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
        lon=[ctd_bgc.spacetime.location.lon for ctd_bgc in ctd_bgcs],
        lat=[ctd_bgc.spacetime.location.lat for ctd_bgc in ctd_bgcs],
        z=[ctd_bgc.min_depth for ctd_bgc in ctd_bgcs],
        time=[np.datetime64(ctd_bgc.spacetime.time) for ctd_bgc in ctd_bgcs],
        max_depth=max_depths,
        min_depth=[ctd_bgc.min_depth for ctd_bgc in ctd_bgcs],
        winch_speed=[WINCH_SPEED for _ in ctd_bgcs],
    )

    # define output file for the simulation
    out_file = ParticleFile(store=out_path, outputdt=outputdt)

    # execute simulation
    ctd_bgc_particleset.execute(
        [
            _sample_o2,
            _sample_chlorophyll,
            _sample_nitrate,
            _sample_phosphate,
            _sample_ph,
            _sample_phytoplankton,
            _sample_zooplankton,
            _sample_primary_production,
            _ctd_bgc_sinking,
            _ctd_bgc_rising,
        ],
        endtime=fieldset.time_interval.right,
        dt=np.timedelta64(DT, "s"),
        verbose_progress=False,
        output_file=out_file,
    )

    # there should be no particles left, as they delete themselves when they resurface
    if len(ctd_bgc_particleset) != 0:
        raise ValueError(
            "Simulation ended before BGC CTD resurfaced. This most likely means the field time dimension did not match the simulation time span."
        )
