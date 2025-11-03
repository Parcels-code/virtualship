from dataclasses import dataclass
from datetime import timedelta
from typing import ClassVar

import numpy as np
from parcels import AdvectionRK4, JITParticle, ParticleSet, Variable

from virtualship.instruments.base import InputDataset, Instrument
from virtualship.instruments.types import InstrumentType
from virtualship.models.spacetime import Spacetime
from virtualship.utils import register_input_dataset, register_instrument

# =====================================================
# SECTION: Dataclass
# =====================================================


@dataclass
class Drifter:
    """Drifter configuration."""

    name: ClassVar[str] = "Drifter"
    spacetime: Spacetime
    depth: float  # depth at which it floats and samples
    lifetime: timedelta | None  # if none, lifetime is infinite


# =====================================================
# SECTION: Particle Class
# =====================================================

_DrifterParticle = JITParticle.add_variables(
    [
        Variable("temperature", dtype=np.float32, initial=np.nan),
        Variable("has_lifetime", dtype=np.int8),  # bool
        Variable("age", dtype=np.float32, initial=0.0),
        Variable("lifetime", dtype=np.float32),
    ]
)

# =====================================================
# SECTION: Kernels
# =====================================================


def _sample_temperature(particle, fieldset, time):
    particle.temperature = fieldset.T[time, particle.depth, particle.lat, particle.lon]


def _check_lifetime(particle, fieldset, time):
    if particle.has_lifetime == 1:
        particle.age += particle.dt
        if particle.age >= particle.lifetime:
            particle.delete()


# =====================================================
# SECTION: InputDataset Class
# =====================================================


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
                "physical": True,
                "variables": ["uo", "vo"],
                "output_filename": f"{self.name}_uv.nc",
            },
            "Tdata": {
                "physical": True,
                "variables": ["thetao"],
                "output_filename": f"{self.name}_t.nc",
            },
        }


# =====================================================
# SECTION: Instrument Class
# =====================================================


@register_instrument(InstrumentType.DRIFTER)
class DrifterInstrument(Instrument):
    """Drifter instrument class."""

    def __init__(self, expedition, directory):
        """Initialize DrifterInstrument."""
        filenames = {
            "U": f"{Drifter.name}_uv.nc",
            "V": f"{Drifter.name}_uv.nc",
            "T": f"{Drifter.name}_t.nc",
        }
        variables = {"U": "uo", "V": "vo", "T": "thetao"}
        super().__init__(
            Drifter.name,
            expedition,
            directory,
            filenames,
            variables,
            add_bathymetry=False,
            allow_time_extrapolation=False,
            verbose_progress=True,
        )

    def simulate(self, measurements, out_path) -> None:
        """Simulate Drifter measurements."""
        OUTPUT_DT = timedelta(hours=5)
        DT = timedelta(minutes=5)
        ENDTIME = None

        if len(measurements) == 0:
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
            lat=[drifter.spacetime.location.lat for drifter in measurements],
            lon=[drifter.spacetime.location.lon for drifter in measurements],
            depth=[drifter.depth for drifter in measurements],
            time=[drifter.spacetime.time for drifter in measurements],
            has_lifetime=[
                1 if drifter.lifetime is not None else 0 for drifter in measurements
            ],
            lifetime=[
                0 if drifter.lifetime is None else drifter.lifetime.total_seconds()
                for drifter in measurements
            ],
        )

        # define output file for the simulation
        out_file = drifter_particleset.ParticleFile(
            name=out_path,
            outputdt=OUTPUT_DT,
            chunks=[len(drifter_particleset), 100],
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
        drifter_particleset.execute(
            [AdvectionRK4, _sample_temperature, _check_lifetime],
            endtime=actual_endtime,
            dt=DT,
            output_file=out_file,
            verbose_progress=self.verbose_progress,
        )

        # if there are more particles left than the number of drifters with an indefinite endtime, warn the user
        if len(drifter_particleset.particledata) > len(
            [d for d in measurements if d.lifetime is None]
        ):
            print(
                "WARN: Some drifters had a life time beyond the end time of the fieldset or the requested end time."
            )
