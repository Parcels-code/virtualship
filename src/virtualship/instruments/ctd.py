"""CTD instrument."""

from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

import numpy as np
from parcels import FieldSet, ParticleSet, Variable
from parcels.particle import Particle
from parcels.tools import StatusCode

from virtualship.models import Spacetime


@dataclass
class CTD:
    """Configuration for a single CTD."""

    spacetime: Spacetime
    min_depth: float
    max_depth: float


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


def _sample_temperature(particles, fieldset):
    particles.temperature = fieldset.T[
        particles.time, particles.z, particles.lat, particles.lon
    ]


def _sample_salinity(particles, fieldset):
    particles.salinity = fieldset.S[
        particles.time, particles.z, particles.lat, particles.lon
    ]


def _ctd_sinking(particles, fieldset):
    dt = particles.dt / np.timedelta64(1, "s")  # convert dt to seconds

    def ctd_lowering(p):
        p.dz = -particles.winch_speed * dt
        p.raising = np.where(p.z + p.dz < p.max_depth, 1, p.raising)
        p.dz = np.where(p.z + p.dz < p.max_depth, -p.ddpeth, p.dz)

    ctd_lowering(particles[particles.raising == 0])


def _ctd_rising(particles, fieldset):
    dt = particles.dt / np.timedelta64(1, "s")  # convert dt to seconds

    def ctd_rising(p):
        p.dz = p.winch_speed * dt
        p.state = np.where(p.z + p.dz > p.min_depth, StatusCode.Delete, p.state)

    ctd_rising(particles[particles.raising == 1])


def simulate_ctd(
    fieldset: FieldSet,
    out_path: str | Path,
    ctds: list[CTD],
    outputdt: timedelta,
) -> None:
    """
    Use Parcels to simulate a set of CTDs in a fieldset.

    :param fieldset: The fieldset to simulate the CTDs in.
    :param out_path: The path to write the results to.
    :param ctds: A list of CTDs to simulate.
    :param outputdt: Interval which dictates the update frequency of file output during simulation
    :raises ValueError: Whenever provided CTDs, fieldset, are not compatible with this function.
    """
    WINCH_SPEED = 1.0  # sink and rise speed in m/s
    DT = 10.0  # dt of CTD simulation integrator

    if len(ctds) == 0:
        print(
            "No CTDs provided. Parcels currently crashes when providing an empty particle set, so no CTD simulation will be done and no files will be created."
        )
        # TODO when Parcels supports it this check can be removed.
        return

    fieldset_starttime = fieldset.time_origin.fulltime(fieldset.U.grid.time_full[0])
    fieldset_endtime = fieldset.time_origin.fulltime(fieldset.U.grid.time_full[-1])

    # deploy time for all ctds should be later than fieldset start time
    if not all(
        [np.datetime64(ctd.spacetime.time) >= fieldset_starttime for ctd in ctds]
    ):
        raise ValueError("CTD deployed before fieldset starts.")

    # depth the ctd will go to. shallowest between ctd max depth and bathymetry.
    max_depths = [
        max(
            ctd.max_depth,
            fieldset.bathymetry.eval(
                z=0, y=ctd.spacetime.location.lat, x=ctd.spacetime.location.lon, time=0
            ),
        )
        for ctd in ctds
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
        lon=[ctd.spacetime.location.lon for ctd in ctds],
        lat=[ctd.spacetime.location.lat for ctd in ctds],
        depth=[ctd.min_depth for ctd in ctds],
        time=[ctd.spacetime.time for ctd in ctds],
        max_depth=max_depths,
        min_depth=[ctd.min_depth for ctd in ctds],
        winch_speed=[WINCH_SPEED for _ in ctds],
    )

    # define output file for the simulation
    out_file = ctd_particleset.ParticleFile(name=out_path, outputdt=outputdt)

    # execute simulation
    ctd_particleset.execute(
        [_sample_salinity, _sample_temperature, _ctd_sinking, _ctd_rising],
        endtime=fieldset_endtime,
        dt=DT,
        verbose_progress=False,
        output_file=out_file,
    )

    # there should be no particles left, as they delete themselves when they resurface
    if len(ctd_particleset.particledata) != 0:
        raise ValueError(
            "Simulation ended before CTD resurfaced. This most likely means the field time dimension did not match the simulation time span."
        )
