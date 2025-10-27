"""Argo float instrument."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
from parcels import (
    FieldSet,
    Particle,
    ParticleSet,
    StatusCode,
    Variable,
)
from parcels.kernels import AdvectionRK4

from virtualship.models import Spacetime


@dataclass
class ArgoFloat:
    """Configuration for a single Argo float."""

    spacetime: Spacetime
    min_depth: float
    max_depth: float
    drift_depth: float
    vertical_speed: float
    cycle_days: float
    drift_days: float


_ArgoParticle = Particle.add_variable(
    [
        Variable("cycle_phase", dtype=np.int32, initial=0.0),
        Variable("cycle_age", dtype=np.float32, initial=0.0),
        Variable("drift_age", dtype=np.float32, initial=0.0),
        Variable("salinity", dtype=np.float32, initial=np.nan),
        Variable("temperature", dtype=np.float32, initial=np.nan),
        Variable("min_depth", dtype=np.float32),
        Variable("max_depth", dtype=np.float32),
        Variable("drift_depth", dtype=np.float32),
        Variable("vertical_speed", dtype=np.float32),
        Variable("cycle_days", dtype=np.int32),
        Variable("drift_days", dtype=np.int32),
    ]
)


def ArgoPhase1(particles, fieldset):
    dt = particles.dt / np.timedelta64(1, "s")  # convert dt to seconds

    def SinkingPhase(p):
        """Phase 0: Sinking with p.vertical_speed until depth is driftdepth."""
        p.dz += p.verticle_speed * dt
        p.cycle_phase = np.where(p.z + p.dz >= p.drift_depth, 1, p.cycle_phase)
        p.dz = np.where(p.z + p.dz >= p.drift_depth, p.drift_depth - p.z, p.dz)

    SinkingPhase(particles[particles.cycle_phase == 0])


def ArgoPhase2(particles, fieldset):
    dt = particles.dt / np.timedelta64(1, "s")  # convert dt to seconds

    def DriftingPhase(p):
        """Phase 1: Drifting at depth for drift_time seconds."""
        p.drift_age += dt
        p.cycle_phase = np.where(p.drift_age >= p.drift_time, 2, p.cycle_phase)
        p.drift_age = np.where(p.drift_age >= p.drift_time, 0, p.drift_age)

    DriftingPhase(particles[particles.cycle_phase == 1])


def ArgoPhase3(particles, fieldset):
    dt = particles.dt / np.timedelta64(1, "s")  # convert dt to seconds

    def SecondSinkingPhase(p):
        """Phase 2: Sinking further to max_depth."""
        p.dz += p.vertical_speed * dt
        p.cycle_phase = np.where(p.z + p.dz >= p.max_depth, 3, p.cycle_phase)
        p.dz = np.where(p.z + p.dz >= p.max_depth, p.max_depth - p.z, p.dz)

    SecondSinkingPhase(particles[particles.cycle_phase == 2])


def ArgoPhase4(particles, fieldset):
    dt = particles.dt / np.timedelta64(1, "s")  # convert dt to seconds

    def RisingPhase(p):
        """Phase 3: Rising with p.vertical_speed until at surface."""
        p.dz -= p.vertical_speed * dt
        p.temp = fieldset.temp[p.time, p.z, p.lat, p.lon]
        p.cycle_phase = np.where(p.z + p.dz <= fieldset.mindepth, 4, p.cycle_phase)

    RisingPhase(particles[particles.cycle_phase == 3])


def ArgoPhase5(particles, fieldset):
    def TransmittingPhase(p):
        """Phase 4: Transmitting at surface until cycletime (cycle_days * 86400 [seconds]) is reached."""
        p.cycle_phase = np.where(p.cycle_age >= p.cycle_days * 86400, 0, p.cycle_phase)
        p.cycle_age = np.where(p.cycle_age >= p.cycle_days * 86400, 0, p.cycle_age)

    TransmittingPhase(particles[particles.cycle_phase == 4])


def ArgoPhase6(particles, fieldset):
    dt = particles.dt / np.timedelta64(1, "s")  # convert dt to seconds
    particles.cycle_age += dt  # update cycle_age


def _keep_at_surface(particles, fieldset):
    # Prevent error when float reaches surface
    particles.z = np.where(
        particles.state == StatusCode.ErrorThroughSurface,
        particles.min_depth,
        particles.z,
    )
    particles.state = np.where(
        particles.state == StatusCode.ErrorThroughSurface,
        StatusCode.Success,
        particles.state,
    )


def _check_error(particles, fieldset):
    particles.state = np.where(
        particles.state >= 50, StatusCode.Delete, particles.state
    )  # captures all errors


def simulate_argo_floats(
    fieldset: FieldSet,
    out_path: str | Path,
    argo_floats: list[ArgoFloat],
    outputdt: timedelta,
    endtime: datetime | None,
) -> None:
    """
    Use Parcels to simulate a set of Argo floats in a fieldset.

    :param fieldset: The fieldset to simulate the Argo floats in.
    :param out_path: The path to write the results to.
    :param argo_floats: A list of Argo floats to simulate.
    :param outputdt: Interval which dictates the update frequency of file output during simulation
    :param endtime: Stop at this time, or if None, continue until the end of the fieldset.
    """
    DT = 10.0  # dt of Argo float simulation integrator

    if len(argo_floats) == 0:
        print(
            "No Argo floats provided. Parcels currently crashes when providing an empty particle set, so no argo floats simulation will be done and no files will be created."
        )
        # TODO when Parcels supports it this check can be removed.
        return

    # define parcel particles
    argo_float_particleset = ParticleSet(
        fieldset=fieldset,
        pclass=_ArgoParticle,
        lat=[argo.spacetime.location.lat for argo in argo_floats],
        lon=[argo.spacetime.location.lon for argo in argo_floats],
        depth=[argo.min_depth for argo in argo_floats],
        time=[argo.spacetime.time for argo in argo_floats],
        min_depth=[argo.min_depth for argo in argo_floats],
        max_depth=[argo.max_depth for argo in argo_floats],
        drift_depth=[argo.drift_depth for argo in argo_floats],
        vertical_speed=[argo.vertical_speed for argo in argo_floats],
        cycle_days=[argo.cycle_days for argo in argo_floats],
        drift_days=[argo.drift_days for argo in argo_floats],
    )

    # define output file for the simulation
    out_file = argo_float_particleset.ParticleFile(
        name=out_path, outputdt=outputdt, chunks=[len(argo_float_particleset), 100]
    )

    # get earliest between fieldset end time and provide end time
    fieldset_endtime = fieldset.time_origin.fulltime(fieldset.U.grid.time_full[-1])
    if endtime is None:
        actual_endtime = fieldset_endtime
    elif endtime > fieldset_endtime:
        print("WARN: Requested end time later than fieldset end time.")
        actual_endtime = fieldset_endtime
    else:
        actual_endtime = np.timedelta64(endtime)

    # execute simulation
    argo_float_particleset.execute(
        [
            ArgoPhase1,
            ArgoPhase2,
            ArgoPhase3,
            ArgoPhase4,
            ArgoPhase5,
            ArgoPhase6,
            AdvectionRK4,
            _keep_at_surface,
            _check_error,
        ],
        endtime=actual_endtime,
        dt=DT,
        output_file=out_file,
        verbose_progress=True,
    )
