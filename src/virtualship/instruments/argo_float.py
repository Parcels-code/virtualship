import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import ClassVar

import numpy as np

from parcels import (
    AdvectionRK4,
    JITParticle,
    ParticleSet,
    StatusCode,
    Variable,
)
from virtualship.instruments.base import InputDataset, Instrument
from virtualship.instruments.types import InstrumentType
from virtualship.models.spacetime import Spacetime
from virtualship.utils import register_input_dataset, register_instrument


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
    ]
)


def _argo_float_vertical_movement(particle, fieldset, time):
    if particle.cycle_phase == 0:
        # Phase 0: Sinking with vertical_speed until depth is drift_depth
        particle_ddepth += (  # noqa Parcels defines particle_* variables, which code checkers cannot know.
            particle.vertical_speed * particle.dt
        )
        if particle.depth + particle_ddepth <= particle.drift_depth:
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
        if particle.depth + particle_ddepth <= particle.max_depth:
            particle_ddepth = particle.max_depth - particle.depth
            particle.cycle_phase = 3

    elif particle.cycle_phase == 3:
        # Phase 3: Rising with vertical_speed until at surface
        particle_ddepth -= particle.vertical_speed * particle.dt
        particle.cycle_age += (
            particle.dt
        )  # solve issue of not updating cycle_age during ascent
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


@register_input_dataset(InstrumentType.ARGO_FLOAT)
class ArgoFloatInputDataset(InputDataset):
    """Input dataset for ArgoFloat instrument."""

    DOWNLOAD_BUFFERS: ClassVar[dict] = {
        "latlon_degrees": 3.0,
        "days": 21.0,
    }

    DOWNLOAD_LIMITS: ClassVar[dict] = {"min_depth": 1}

    def __init__(self, data_dir, credentials, space_time_region):
        """Initialise with instrument's name."""
        super().__init__(
            ArgoFloat.name,
            self.DOWNLOAD_BUFFERS["latlon_degrees"],
            self.DOWNLOAD_BUFFERS["days"],
            self.DOWNLOAD_LIMITS["min_depth"],
            space_time_region.spatial_range.maximum_depth,
            data_dir,
            credentials,
            space_time_region,
        )

    def get_datasets_dict(self) -> dict:
        """Get variable specific args for instrument."""
        return {
            "UVdata": {
                "dataset_id": "cmems_mod_glo_phy-cur_anfc_0.083deg_PT6H-i",
                "variables": ["uo", "vo"],
                "output_filename": "argo_float_uv.nc",
            },
            "Sdata": {
                "dataset_id": "cmems_mod_glo_phy-so_anfc_0.083deg_PT6H-i",
                "variables": ["so"],
                "output_filename": "argo_float_s.nc",
            },
            "Tdata": {
                "dataset_id": "cmems_mod_glo_phy-thetao_anfc_0.083deg_PT6H-i",
                "variables": ["thetao"],
                "output_filename": "argo_float_t.nc",
            },
        }


@register_instrument(InstrumentType.ARGO_FLOAT)
class ArgoFloatInstrument(Instrument):
    """ArgoFloat instrument class."""

    def __init__(
        self,
        input_dataset: InputDataset,
    ):
        """Initialize ArgoFloatInstrument."""
        filenames = {
            "UV": input_dataset.data_dir.joinpath("argo_float_uv.nc"),
            "S": input_dataset.data_dir.joinpath("argo_float_s.nc"),
            "T": input_dataset.data_dir.joinpath("argo_float_t.nc"),
        }
        variables = {"UV": ["uo", "vo"], "S": "so", "T": "thetao"}
        super().__init__(
            input_dataset,
            filenames,
            variables,
            add_bathymetry=False,
            allow_time_extrapolation=False,
        )

    def simulate(
        self,
        argo_floats: list[ArgoFloat],
        out_path: str | Path,
        outputdt: timedelta,
        endtime: datetime | None = None,
    ) -> None:
        """Simulate Argo float measurements."""
        DT = 10.0  # dt of Argo float simulation integrator

        if len(argo_floats) == 0:
            print(
                "No Argo floats provided. Parcels currently crashes when providing an empty particle set, so no argo floats simulation will be done and no files will be created."
            )
            # TODO when Parcels supports it this check can be removed.
            return

        fieldset = self.load_input_data()

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
                _argo_float_vertical_movement,
                AdvectionRK4,
                _keep_at_surface,
                _check_error,
            ],
            endtime=actual_endtime,
            dt=DT,
            output_file=out_file,
            verbose_progress=True,
        )
