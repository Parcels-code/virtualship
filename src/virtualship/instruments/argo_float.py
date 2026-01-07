from dataclasses import dataclass
from datetime import timedelta
from typing import ClassVar

import numpy as np

from parcels import (
    Particle,
    ParticleSet,
    StatusCode,
    Variable,
)
from parcels.kernels import AdvectionRK4
from virtualship.instruments.base import Instrument
from virtualship.instruments.types import InstrumentType
from virtualship.models.spacetime import Spacetime
from virtualship.utils import register_instrument

# =====================================================
# SECTION: Dataclass
# =====================================================


@dataclass
class ArgoFloat:
    """Argo float configuration."""

    name: ClassVar[str] = "ArgoFloat"
    spacetime: Spacetime
    min_depth: float
    max_depth: float
    drift_depth: float
    vertical_speed: float
    cycle_days: float
    drift_days: float


# =====================================================
# SECTION: Particle Class
# =====================================================

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
        Variable("grounded", dtype=np.int32, initial=0),
    ]
)

# =====================================================
# SECTION: Kernels
# =====================================================


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


# =====================================================
# SECTION: Instrument Class
# =====================================================


@register_instrument(InstrumentType.ARGO_FLOAT)
class ArgoFloatInstrument(Instrument):
    """ArgoFloat instrument class."""

    def __init__(self, expedition, from_data):
        """Initialize ArgoFloatInstrument."""
        variables = {"U": "uo", "V": "vo", "S": "so", "T": "thetao"}
        spacetime_buffer_size = {
            "latlon": 3.0,  # [degrees]
            "time": expedition.instruments_config.argo_float_config.lifetime.total_seconds()
            / (24 * 3600),  # [days]
        }
        limit_spec = {
            "spatial": True,  # spatial limits; lat/lon constrained to waypoint locations + buffer
        }

        super().__init__(
            expedition,
            variables,
            add_bathymetry=True,
            allow_time_extrapolation=False,
            verbose_progress=True,
            spacetime_buffer_size=spacetime_buffer_size,
            limit_spec=limit_spec,
            from_data=from_data,
        )

    def simulate(self, measurements, out_path) -> None:
        """Simulate Argo float measurements."""
        DT = 10.0  # dt of Argo float simulation integrator
        OUTPUT_DT = timedelta(minutes=5)

        if len(measurements) == 0:
            print(
                "No Argo floats provided. Parcels currently crashes when providing an empty particle set, so no argo floats simulation will be done and no files will be created."
            )
            # TODO when Parcels supports it this check can be removed.
            return

        fieldset = self.load_input_data()

        shallow_waypoints = {}
        for i, m in enumerate(measurements):
            loc_bathy = fieldset.bathymetry.eval(
                time=0,
                z=0,
                y=m.spacetime.location.lat,
                x=m.spacetime.location.lon,
            )
            if abs(loc_bathy) < 50.0:
                shallow_waypoints[f"Waypoint {i + 1}"] = f"{abs(loc_bathy):.2f}m depth"

        if len(shallow_waypoints) > 0:
            raise ValueError(
                f"{self.__class__.__name__} cannot be deployed in waters shallower than 50m. The following waypoints are too shallow: {shallow_waypoints}."
            )

        # define parcel particles
        argo_float_particleset = ParticleSet(
            fieldset=fieldset,
            pclass=_ArgoParticle,
            lat=[argo.spacetime.location.lat for argo in measurements],
            lon=[argo.spacetime.location.lon for argo in measurements],
            depth=[argo.min_depth for argo in measurements],
            time=[argo.spacetime.time for argo in measurements],
            min_depth=[argo.min_depth for argo in measurements],
            max_depth=[argo.max_depth for argo in measurements],
            drift_depth=[argo.drift_depth for argo in measurements],
            vertical_speed=[argo.vertical_speed for argo in measurements],
            cycle_days=[argo.cycle_days for argo in measurements],
            drift_days=[argo.drift_days for argo in measurements],
        )

        # define output file for the simulation
        out_file = argo_float_particleset.ParticleFile(
            name=out_path,
            outputdt=OUTPUT_DT,
            chunks=[len(argo_float_particleset), 100],
        )

        # endtime
        endtime = fieldset.time_origin.fulltime(fieldset.U.grid.time_full[-1])

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
            endtime=endtime,
            dt=DT,
            output_file=out_file,
            verbose_progress=self.verbose_progress,
        )
