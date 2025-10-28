from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

import numpy as np

from parcels import ParticleSet, ScipyParticle, Variable
from virtualship.instruments.base import InputDataset, Instrument
from virtualship.instruments.types import InstrumentType
from virtualship.models.spacetime import Spacetime
from virtualship.utils import register_input_dataset, register_instrument


@dataclass
class ADCP:
    """ADCP configuration."""

    name: ClassVar[str] = "ADCP"


# we specifically use ScipyParticle because we have many small calls to execute
# there is some overhead with JITParticle and this ends up being significantly faster
_ADCPParticle = ScipyParticle.add_variables(
    [
        Variable("U", dtype=np.float32, initial=np.nan),
        Variable("V", dtype=np.float32, initial=np.nan),
    ]
)


def _sample_velocity(particle, fieldset, time):
    particle.U, particle.V = fieldset.UV.eval(
        time, particle.depth, particle.lat, particle.lon, applyConversion=False
    )


@register_input_dataset(InstrumentType.ADCP)
class ADCPInputDataset(InputDataset):
    """Input dataset for ADCP instrument."""

    DOWNLOAD_BUFFERS: ClassVar[dict] = {
        "latlon_degrees": 0.0,
        "days": 0.0,
    }  # ADCP data requires no buffers

    DOWNLOAD_LIMITS: ClassVar[dict] = {"min_depth": 1}

    def __init__(self, data_dir, credentials, space_time_region):
        """Initialise with instrument's name."""
        super().__init__(
            ADCP.name,
            self.DOWNLOAD_BUFFERS["latlon_degrees"],
            self.DOWNLOAD_BUFFERS["days"],
            space_time_region.spatial_range.minimum_depth,
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
                "output_filename": f"{self.name}_uv.nc",
            },
        }


@register_instrument(InstrumentType.ADCP)
class ADCPInstrument(Instrument):
    """ADCP instrument class."""

    def __init__(
        self,
        input_dataset: InputDataset,
    ):
        """Initialize ADCPInstrument."""
        filenames = {
            "UV": input_dataset.data_dir.joinpath(f"{input_dataset.name}_uv.nc"),
        }
        variables = {"UV": ["uo", "vo"]}
        super().__init__(
            input_dataset,
            filenames,
            variables,
            add_bathymetry=False,
            allow_time_extrapolation=True,
        )

    def simulate(
        self,
        out_path: str | Path,
        max_depth: float,
        min_depth: float,
        num_bins: int,
        sample_points: list[Spacetime],
    ) -> None:
        """Simulate ADCP measurements."""
        sample_points.sort(key=lambda p: p.time)

        fieldset = self.load_input_data()

        bins = np.linspace(max_depth, min_depth, num_bins)
        num_particles = len(bins)
        particleset = ParticleSet.from_list(
            fieldset=fieldset,
            pclass=_ADCPParticle,
            lon=np.full(num_particles, 0.0),
            lat=np.full(num_particles, 0.0),
            depth=bins,
            time=0,
        )

        out_file = particleset.ParticleFile(name=out_path, outputdt=np.inf)

        for point in sample_points:
            particleset.lon_nextloop[:] = point.location.lon
            particleset.lat_nextloop[:] = point.location.lat
            particleset.time_nextloop[:] = fieldset.time_origin.reltime(
                np.datetime64(point.time)
            )

            particleset.execute(
                [_sample_velocity],
                dt=1,
                runtime=1,
                verbose_progress=False,
                output_file=out_file,
            )
