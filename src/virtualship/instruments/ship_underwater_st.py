from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

import numpy as np
from parcels import FieldSet, ParticleSet, ScipyParticle, Variable

from virtualship.models import Spacetime, instruments


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


class Underwater_STInputDataset(instruments.InputDataset):
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
                "dataset_id": "cmems_mod_glo_phy-so_anfc_0.083deg_PT6H-i",
                "variables": ["so"],
                "output_filename": f"{self.name}_s.nc",
            },
            "Tdata": {
                "dataset_id": "cmems_mod_glo_phy-thetao_anfc_0.083deg_PT6H-i",
                "variables": ["thetao"],
                "output_filename": f"{self.name}_t.nc",
            },
        }


# class Underwater_STInstrument(instruments.Instrument):
#     """Underwater_ST instrument class."""

#     def __init__(
#         self,
#         config,
#         input_dataset,
#         kernels,
#     ):
#         """Initialise with instrument's name."""
#         super().__init__(Underwater_ST.name, config, input_dataset, kernels)

#     def simulate(self):
#         """Simulate measurements."""
#         ...


def simulate_ship_underwater_st(
    fieldset: FieldSet,
    out_path: str | Path,
    depth: float,
    sample_points: list[Spacetime],
) -> None:
    """
    Use Parcels to simulate underway data, measuring salinity and temperature at the given depth along the ship track in a fieldset.

    :param fieldset: The fieldset to simulate the sampling in.
    :param out_path: The path to write the results to.
    :param depth: The depth at which to measure. 0 is water surface, negative is into the water.
    :param sample_points: The places and times to sample at.
    """
    sample_points.sort(key=lambda p: p.time)

    particleset = ParticleSet.from_list(
        fieldset=fieldset,
        pclass=_ShipSTParticle,
        lon=0.0,  # initial lat/lon are irrelevant and will be overruled later
        lat=0.0,
        depth=depth,
        time=0,  # same for time
    )

    # define output file for the simulation
    # outputdt set to infinie as we want to just want to write at the end of every call to 'execute'
    out_file = particleset.ParticleFile(name=out_path, outputdt=np.inf)

    # iterate over each point, manually set lat lon time, then
    # execute the particle set for one step, performing one set of measurement
    for point in sample_points:
        particleset.lon_nextloop[:] = point.location.lon
        particleset.lat_nextloop[:] = point.location.lat
        particleset.time_nextloop[:] = fieldset.time_origin.reltime(
            np.datetime64(point.time)
        )

        # perform one step using the particleset
        # dt and runtime are set so exactly one step is made.
        particleset.execute(
            [_sample_salinity, _sample_temperature],
            dt=1,
            runtime=1,
            verbose_progress=False,
            output_file=out_file,
        )
