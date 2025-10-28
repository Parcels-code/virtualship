from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import ClassVar

import numpy as np

from parcels import AdvectionRK4, JITParticle, ParticleSet, Variable
from virtualship.instruments.base import InputDataset, Instrument
from virtualship.instruments.types import InstrumentType
from virtualship.models.spacetime import Spacetime
from virtualship.utils import register_input_dataset, register_instrument


@dataclass
class Drifter:
    """Drifter configuration."""

    name: ClassVar[str] = "Drifter"
    spacetime: Spacetime
    depth: float  # depth at which it floats and samples
    lifetime: timedelta | None  # if none, lifetime is infinite


_DrifterParticle = JITParticle.add_variables(
    [
        Variable("temperature", dtype=np.float32, initial=np.nan),
        Variable("has_lifetime", dtype=np.int8),  # bool
        Variable("age", dtype=np.float32, initial=0.0),
        Variable("lifetime", dtype=np.float32),
    ]
)


def _sample_temperature(particle, fieldset, time):
    particle.temperature = fieldset.T[time, particle.depth, particle.lat, particle.lon]


def _check_lifetime(particle, fieldset, time):
    if particle.has_lifetime == 1:
        particle.age += particle.dt
        if particle.age >= particle.lifetime:
            particle.delete()


@register_input_dataset(InstrumentType.DRIFTER)
class DrifterInputDataset(InputDataset):
    """Input dataset for Drifter instrument."""

    DOWNLOAD_BUFFERS: ClassVar[dict] = {
        "latlon_degrees": 3.0,
        "days": 21.0,
    }

    DOWNLOAD_LIMITS: ClassVar[dict] = {"min_depth": 1, "max_depth": 1}

    def __init__(self, data_dir, credentials, space_time_region):
        """Initialise with instrument's name."""
        super().__init__(
            Drifter.name,
            self.DOWNLOAD_BUFFERS["latlon_degrees"],
            self.DOWNLOAD_BUFFERS["days"],
            self.DOWNLOAD_LIMITS["min_depth"],
            self.DOWNLOAD_LIMITS["max_depth"],
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
                "output_filename": "drifter_uv.nc",
            },
            "Tdata": {
                "dataset_id": "cmems_mod_glo_phy-thetao_anfc_0.083deg_PT6H-i",
                "variables": ["thetao"],
                "output_filename": "drifter_t.nc",
            },
        }


@register_instrument(InstrumentType.DRIFTER)
class DrifterInstrument(Instrument):
    """Drifter instrument class."""

    def __init__(
        self,
        input_dataset: InputDataset,
    ):
        """Initialize DrifterInstrument."""
        filenames = {
            "UV": input_dataset.data_dir.joinpath("drifter_uv.nc"),
            "T": input_dataset.data_dir.joinpath("drifter_t.nc"),
        }
        variables = {"UV": ["uo", "vo"], "T": "thetao"}
        super().__init__(
            input_dataset,
            filenames,
            variables,
            add_bathymetry=False,
            allow_time_extrapolation=False,
        )

    def simulate(
        self,
        drifters: list[Drifter],
        out_path: str | Path,
        outputdt: timedelta,
        dt: timedelta,
        endtime: datetime | None = None,
    ) -> None:
        """Simulate Drifter measurements."""
        if len(drifters) == 0:
            print(
                "No drifters provided. Parcels currently crashes when providing an empty particle set, so no drifter simulation will be done and no files will be created."
            )
            # TODO when Parcels supports it this check can be removed.
            return

        fieldset = self.load_input_data()

        # define parcel particles
        drifter_particleset = ParticleSet(
            fieldset=fieldset,
            pclass=_DrifterParticle,
            lat=[drifter.spacetime.location.lat for drifter in drifters],
            lon=[drifter.spacetime.location.lon for drifter in drifters],
            depth=[drifter.depth for drifter in drifters],
            time=[drifter.spacetime.time for drifter in drifters],
            has_lifetime=[
                1 if drifter.lifetime is not None else 0 for drifter in drifters
            ],
            lifetime=[
                0 if drifter.lifetime is None else drifter.lifetime.total_seconds()
                for drifter in drifters
            ],
        )

        # define output file for the simulation
        out_file = drifter_particleset.ParticleFile(
            name=out_path, outputdt=outputdt, chunks=[len(drifter_particleset), 100]
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
        drifter_particleset.execute(
            [AdvectionRK4, _sample_temperature, _check_lifetime],
            endtime=actual_endtime,
            dt=dt,
            output_file=out_file,
            verbose_progress=True,
        )

        # if there are more particles left than the number of drifters with an indefinite endtime, warn the user
        if len(drifter_particleset.particledata) > len(
            [d for d in drifters if d.lifetime is None]
        ):
            print(
                "WARN: Some drifters had a life time beyond the end time of the fieldset or the requested end time."
            )
