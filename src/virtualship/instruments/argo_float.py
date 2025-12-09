import math
from dataclasses import dataclass
from datetime import timedelta
from typing import ClassVar

import numpy as np

from parcels import (
    AdvectionRK4,
    JITParticle,
    ParticleSet,
    StatusCode,
    Variable,
)
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

_ArgoParticle = JITParticle.add_variables(
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


def _argo_float_vertical_movement(particle, fieldset, time):
    if particle.cycle_phase == 0:
        # Phase 0: Sinking with vertical_speed until depth is drift_depth
        particle_ddepth += (  # noqa
            particle.vertical_speed * particle.dt
        )

        # bathymetry at particle location
        loc_bathy = fieldset.bathymetry.eval(
            time, particle.depth, particle.lat, particle.lon
        )
        if particle.depth + particle_ddepth <= loc_bathy:
            particle_ddepth = loc_bathy - particle.depth + 50.0  # 50m above bathy
            particle.cycle_phase = 1
            particle.grounded = 1
            print(
                "Shallow bathymetry warning: Argo float grounded at bathymetry depth during sinking to drift depth. Raising by 50m above bathymetry and continuing cycle."
            )

        elif particle.depth + particle_ddepth <= particle.drift_depth:
            particle_ddepth = particle.drift_depth - particle.depth
            particle.cycle_phase = 1

    elif particle.cycle_phase == 1:
        # Phase 1: Drifting at depth for drifttime seconds
        particle.drift_age += particle.dt
        if particle.drift_age >= particle.drift_days * 86400:
            particle.drift_age = 0  # reset drift_age for next cycle
            particle.cycle_phase = 2

    elif particle.cycle_phase == 2:
        # Phase 2: Sinking further to max_depth
        particle_ddepth += particle.vertical_speed * particle.dt
        loc_bathy = fieldset.bathymetry.eval(
            time, particle.depth, particle.lat, particle.lon
        )
        if particle.depth + particle_ddepth <= loc_bathy:
            particle_ddepth = loc_bathy - particle.depth + 50.0  # 50m above bathy
            particle.cycle_phase = 3
            particle.grounded = 1
            print(
                "Shallow bathymetry warning: Argo float grounded at bathymetry depth during sinking to max depth. Raising by 50m above bathymetry and continuing cycle."
            )
        elif particle.depth + particle_ddepth <= particle.max_depth:
            particle_ddepth = particle.max_depth - particle.depth
            particle.cycle_phase = 3

    elif particle.cycle_phase == 3:
        # Phase 3: Rising with vertical_speed until at surface
        particle_ddepth -= particle.vertical_speed * particle.dt
        particle.cycle_age += (
            particle.dt
        )  # solve issue of not updating cycle_age during ascent
        particle.grounded = 0
        if particle.depth + particle_ddepth >= particle.min_depth:
            particle_ddepth = particle.min_depth - particle.depth
            particle.temperature = (
                math.nan
            )  # reset temperature to NaN at end of sampling cycle
            particle.salinity = math.nan  # idem
            particle.cycle_phase = 4
        else:
            particle.temperature = fieldset.T[
                time, particle.depth, particle.lat, particle.lon
            ]
            particle.salinity = fieldset.S[
                time, particle.depth, particle.lat, particle.lon
            ]

    elif particle.cycle_phase == 4:
        # Phase 4: Transmitting at surface until cycletime is reached
        if particle.cycle_age > particle.cycle_days * 86400:
            particle.cycle_phase = 0
            particle.cycle_age = 0

    if particle.state == StatusCode.Evaluate:
        particle.cycle_age += particle.dt  # update cycle_age


def _keep_at_surface(particle, fieldset, time):
    # Prevent error when float reaches surface
    if particle.state == StatusCode.ErrorThroughSurface:
        particle.depth = particle.min_depth
        particle.state = StatusCode.Success


def _check_error(particle, fieldset, time):
    if particle.state >= 50:  # This captures all Errors
        particle.delete()


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
            "time": 21.0,  # [days]
        }

        super().__init__(
            expedition,
            variables,
            add_bathymetry=True,
            allow_time_extrapolation=False,
            verbose_progress=True,
            spacetime_buffer_size=spacetime_buffer_size,
            limit_spec=None,
            from_data=from_data,
        )

    def simulate(self, measurements, out_path) -> None:
        """Simulate Argo float measurements."""
        DT = 10.0  # dt of Argo float simulation integrator
        OUTPUT_DT = timedelta(minutes=5)
        ENDTIME = None

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

        # get earliest between fieldset end time and provide end time
        fieldset_endtime = fieldset.time_origin.fulltime(fieldset.U.grid.time_full[-1])
        if ENDTIME is None:
            actual_endtime = fieldset_endtime
        elif ENDTIME > fieldset_endtime:
            print("WARN: Requested end time later than fieldset end time.")
            actual_endtime = fieldset_endtime
        else:
            actual_endtime = np.timedelta64(ENDTIME)

        # execute simulation
        argo_float_particleset.execute(
            [
                _argo_float_vertical_movement,
                AdvectionRK4,
                _keep_at_surface,
                _check_error,
            ],
            endtime=actual_endtime,
            dt=DT,
            output_file=out_file,
            verbose_progress=self.verbose_progress,
        )
