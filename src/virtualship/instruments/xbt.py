from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import ClassVar

import numpy as np
from parcels import FieldSet, JITParticle, ParticleSet, Variable

from virtualship.models import Spacetime, instruments

## TODO: __init__.py will also need updating!
# + therefore instructions for adding new instruments will also involve adding to __init__.py as well as the new instrument script + update InstrumentType in instruments.py


@dataclass
class XBT:
    """XBT configuration."""

    name: ClassVar[str] = "XBT"
    spacetime: Spacetime
    depth: float  # depth at which it floats and samples
    lifetime: timedelta | None  # if none, lifetime is infinite


_XBTParticle = JITParticle.add_variables(
    [
        Variable("temperature", dtype=np.float32, initial=np.nan),
        Variable("max_depth", dtype=np.float32),
        Variable("min_depth", dtype=np.float32),
        Variable("fall_speed", dtype=np.float32),
        Variable("deceleration_coefficient", dtype=np.float32),
    ]
)


def _sample_temperature(particle, fieldset, time):
    particle.temperature = fieldset.T[time, particle.depth, particle.lat, particle.lon]


def _xbt_cast(particle, fieldset, time):
    particle_ddepth = -particle.fall_speed * particle.dt

    # update the fall speed from the quadractic fall-rate equation
    # check https://doi.org/10.5194/os-7-231-2011
    particle.fall_speed = (
        particle.fall_speed - 2 * particle.deceleration_coefficient * particle.dt
    )

    # delete particle if depth is exactly max_depth
    if particle.depth == particle.max_depth:
        particle.delete()

    # set particle depth to max depth if it's too deep
    if particle.depth + particle_ddepth < particle.max_depth:
        particle_ddepth = particle.max_depth - particle.depth


class XBTInputDataset(instruments.InputDataset):
    """Input dataset for XBT instrument."""

    DOWNLOAD_BUFFERS: ClassVar[dict] = {
        "latlon_degrees": 3.0,
        "days": 21.0,
    }

    DOWNLOAD_LIMITS: ClassVar[dict] = {"min_depth": 1}

    def __init__(self, data_dir, credentials, space_time_region):
        """Initialise with instrument's name."""
        super().__init__(
            XBT.name,
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
                "output_filename": "ship_uv.nc",
            },
            "Sdata": {
                "dataset_id": "cmems_mod_glo_phy-so_anfc_0.083deg_PT6H-i",
                "variables": ["so"],
                "output_filename": "ship_s.nc",
            },
            "Tdata": {
                "dataset_id": "cmems_mod_glo_phy-thetao_anfc_0.083deg_PT6H-i",
                "variables": ["thetao"],
                "output_filename": "ship_t.nc",
            },
        }


# class XBTInstrument(instruments.Instrument):
#     """XBT instrument class."""

#     def __init__(
#         self,
#         config,
#         input_dataset,
#         kernels,
#     ):
#         """Initialise with instrument's name."""
#         super().__init__(XBT.name, config, input_dataset, kernels)

#     def simulate(self):
#         """Simulate measurements."""
#         ...


def simulate_xbt(
    fieldset: FieldSet,
    out_path: str | Path,
    xbts: list[XBT],
    outputdt: timedelta,
) -> None:
    """
    Use Parcels to simulate a set of XBTs in a fieldset.

    :param fieldset: The fieldset to simulate the XBTs in.
    :param out_path: The path to write the results to.
    :param xbts: A list of XBTs to simulate.
    :param outputdt: Interval which dictates the update frequency of file output during simulation
    :raises ValueError: Whenever provided XBTs, fieldset, are not compatible with this function.
    """
    DT = 10.0  # dt of XBT simulation integrator

    if len(xbts) == 0:
        print(
            "No XBTs provided. Parcels currently crashes when providing an empty particle set, so no XBT simulation will be done and no files will be created."
        )
        # TODO when Parcels supports it this check can be removed.
        return

    fieldset_starttime = fieldset.time_origin.fulltime(fieldset.U.grid.time_full[0])
    fieldset_endtime = fieldset.time_origin.fulltime(fieldset.U.grid.time_full[-1])

    # deploy time for all xbts should be later than fieldset start time
    if not all(
        [np.datetime64(xbt.spacetime.time) >= fieldset_starttime for xbt in xbts]
    ):
        raise ValueError("XBT deployed before fieldset starts.")

    # depth the xbt will go to. shallowest between xbt max depth and bathymetry.
    max_depths = [
        max(
            xbt.max_depth,
            fieldset.bathymetry.eval(
                z=0, y=xbt.spacetime.location.lat, x=xbt.spacetime.location.lon, time=0
            ),
        )
        for xbt in xbts
    ]

    # initial fall speeds
    initial_fall_speeds = [xbt.fall_speed for xbt in xbts]

    # XBT depth can not be too shallow, because kernel would break.
    # This shallow is not useful anyway, no need to support.
    for max_depth, fall_speed in zip(max_depths, initial_fall_speeds, strict=False):
        if not max_depth <= -DT * fall_speed:
            raise ValueError(
                f"XBT max_depth or bathymetry shallower than maximum {-DT * fall_speed}"
            )

    # define xbt particles
    xbt_particleset = ParticleSet(
        fieldset=fieldset,
        pclass=_XBTParticle,
        lon=[xbt.spacetime.location.lon for xbt in xbts],
        lat=[xbt.spacetime.location.lat for xbt in xbts],
        depth=[xbt.min_depth for xbt in xbts],
        time=[xbt.spacetime.time for xbt in xbts],
        max_depth=max_depths,
        min_depth=[xbt.min_depth for xbt in xbts],
        fall_speed=[xbt.fall_speed for xbt in xbts],
    )

    # define output file for the simulation
    out_file = xbt_particleset.ParticleFile(name=out_path, outputdt=outputdt)

    # execute simulation
    xbt_particleset.execute(
        [_sample_temperature, _xbt_cast],
        endtime=fieldset_endtime,
        dt=DT,
        verbose_progress=False,
        output_file=out_file,
    )

    # there should be no particles left, as they delete themselves when they finish profiling
    if len(xbt_particleset.particledata) != 0:
        raise ValueError(
            "Simulation ended before XBT finished profiling. This most likely means the field time dimension did not match the simulation time span."
        )
