from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

import numpy as np

from parcels import FieldSet, ParticleSet, ScipyParticle, Variable
from virtualship.instruments.master import InputDataset
from virtualship.models.spacetime import Spacetime


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


# TODO: uncomment when ready for new simulation logic!
# class ADCPInstrument(instruments.Instrument):
#     """ADCP instrument class."""

#     def __init__(
#         self,
#         config,
#         input_dataset,
#         kernels,
#     ):
#         """Initialise with instrument's name."""
#         super().__init__(ADCP.name, config, input_dataset, kernels)

#     def simulate(self):
#         """Simulate measurements."""
#         ...


# TODO: to be replaced with new simulation logic
## -- old simulation code


def simulate_adcp(
    fieldset: FieldSet,
    out_path: str | Path,
    max_depth: float,
    min_depth: float,
    num_bins: int,
    sample_points: list[Spacetime],
) -> None:
    """
    Use Parcels to simulate an ADCP in a fieldset.

    :param fieldset: The fieldset to simulate the ADCP in.
    :param out_path: The path to write the results to.
    :param max_depth: Maximum depth the ADCP can measure.
    :param min_depth: Minimum depth the ADCP can measure.
    :param num_bins: How many samples to take in the complete range between max_depth and min_depth.
    :param sample_points: The places and times to sample at.
    """
    sample_points.sort(key=lambda p: p.time)

    bins = np.linspace(max_depth, min_depth, num_bins)
    num_particles = len(bins)
    particleset = ParticleSet.from_list(
        fieldset=fieldset,
        pclass=_ADCPParticle,
        lon=np.full(
            num_particles, 0.0
        ),  # initial lat/lon are irrelevant and will be overruled later.
        lat=np.full(num_particles, 0.0),
        depth=bins,
        time=0,  # same for time
    )

    # define output file for the simulation
    # outputdt set to infinite as we just want to write at the end of every call to 'execute'
    out_file = particleset.ParticleFile(name=out_path, outputdt=np.inf)

    for point in sample_points:
        particleset.lon_nextloop[:] = point.location.lon
        particleset.lat_nextloop[:] = point.location.lat
        particleset.time_nextloop[:] = fieldset.time_origin.reltime(
            np.datetime64(point.time)
        )

        # perform one step using the particleset
        # dt and runtime are set so exactly one step is made.
        particleset.execute(
            [_sample_velocity],
            dt=1,
            runtime=1,
            verbose_progress=False,
            output_file=out_file,
        )
