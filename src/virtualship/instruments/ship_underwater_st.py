from dataclasses import dataclass
from typing import ClassVar

import numpy as np

from parcels import ParticleSet, ScipyParticle, Variable
from virtualship.instruments.base import InputDataset, Instrument
from virtualship.instruments.types import InstrumentType
from virtualship.utils import add_dummy_UV, register_input_dataset, register_instrument


@dataclass
class Underwater_ST:
    """Underwater_ST configuration."""

    name: ClassVar[str] = "Underwater_ST"


_ShipSTParticle = ScipyParticle.add_variables(
    [
        Variable("S", dtype=np.float32, initial=np.nan),
        Variable("T", dtype=np.float32, initial=np.nan),
    ]
)


# define function sampling Salinity
def _sample_salinity(particle, fieldset, time):
    particle.S = fieldset.S[time, particle.depth, particle.lat, particle.lon]


# define function sampling Temperature
def _sample_temperature(particle, fieldset, time):
    particle.T = fieldset.T[time, particle.depth, particle.lat, particle.lon]


@register_input_dataset(InstrumentType.UNDERWATER_ST)
class Underwater_STInputDataset(InputDataset):
    """Input dataset for Underwater_ST instrument."""

    DOWNLOAD_BUFFERS: ClassVar[dict] = {
        "latlon_degrees": 0.0,
        "days": 0.0,
    }  # Underwater_ST data requires no buffers

    DOWNLOAD_LIMITS: ClassVar[dict] = {"min_depth": 1}

    def __init__(self, data_dir, credentials, space_time_region):
        """Initialise with instrument's name."""
        super().__init__(
            Underwater_ST.name,
            self.DOWNLOAD_BUFFERS["latlon_degrees"],
            self.DOWNLOAD_BUFFERS["days"],
            -2.0,  # is always at 2m depth
            -2.0,  # is always at 2m depth
            data_dir,
            credentials,
            space_time_region,
        )

    def get_datasets_dict(self) -> dict:
        """Get variable specific args for instrument."""
        return {
            "Sdata": {
                "physical": True,
                "variables": ["so"],
                "output_filename": f"{self.name}_s.nc",
            },
            "Tdata": {
                "physical": True,
                "variables": ["thetao"],
                "output_filename": f"{self.name}_t.nc",
            },
        }


@register_instrument(InstrumentType.UNDERWATER_ST)
class Underwater_STInstrument(Instrument):
    """Underwater_ST instrument class."""

    def __init__(self, expedition, directory):
        """Initialize Underwater_STInstrument."""
        filenames = {
            "S": f"{Underwater_ST.name}_s.nc",
            "T": f"{Underwater_ST.name}_t.nc",
        }
        variables = {"S": "so", "T": "thetao"}

        super().__init__(
            Underwater_ST.name,
            expedition,
            directory,
            filenames,
            variables,
            add_bathymetry=False,
            allow_time_extrapolation=True,
        )

    def simulate(self, measurements, out_path) -> None:
        """Simulate underway salinity and temperature measurements."""
        DEPTH = -2.0

        measurements.sort(key=lambda p: p.time)

        fieldset = self.load_input_data()

        # add dummy U
        add_dummy_UV(fieldset)  # TODO: parcels v3 bodge; remove when parcels v4 is used

        particleset = ParticleSet.from_list(
            fieldset=fieldset,
            pclass=_ShipSTParticle,
            lon=0.0,
            lat=0.0,
            depth=DEPTH,
            time=0,
        )

        out_file = particleset.ParticleFile(name=out_path, outputdt=np.inf)

        for point in measurements:
            particleset.lon_nextloop[:] = point.location.lon
            particleset.lat_nextloop[:] = point.location.lat
            particleset.time_nextloop[:] = fieldset.time_origin.reltime(
                np.datetime64(point.time)
            )

            particleset.execute(
                [_sample_salinity, _sample_temperature],
                dt=1,
                runtime=1,
                verbose_progress=False,
                output_file=out_file,
            )
