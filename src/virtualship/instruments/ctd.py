from dataclasses import dataclass
from typing import ClassVar

import numpy as np
from parcels import FieldSet, ParticleSet

from virtualship.models.spacetime import Spacetime


@dataclass
class CTD:
    """CTD configuration."""

    name: ClassVar[str] = "CTD"
    spacetime: Spacetime
    min_depth: float
    max_depth: float


# ---------------
# TODO: KERNELS
# ---------------


class CTDInputDataset(instruments.InputDataset):
    """Input dataset for CTD instrument."""

    DOWNLOAD_BUFFERS: ClassVar[dict] = {
        "latlon_degrees": 0.0,
        "days": 0.0,
    }  # CTD data requires no buffers

    def __init__(self, data_dir, credentials, space_time_region):
        """Initialise with instrument's name."""
        super().__init__(
            CTD.name,
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


class CTDInstrument(Instrument):
    """CTD instrument class."""

    def __init__(self, config, schedule, input_dataset, kernels):
        """Initialize CTDInstrument."""
        filenames = {
            "S": input_dataset.data_dir.joinpath(f"{input_dataset.name}_s.nc"),
            "T": input_dataset.data_dir.joinpath(f"{input_dataset.name}_t.nc"),
        }
        variables = {"S": "so", "T": "thetao"}

        super().__init__(
            config,
            schedule,
            input_dataset,
            kernels,
            filenames,
            variables,
            add_bathymetry=True,
            allow_time_extrapolation=True,
        )

    def simulate(self):
        """Simulate measurements."""
        ...


### ---------------------------------------------------------------------------------------


def simulate_ctd(
    fieldset: FieldSet,
    out_path: str | Path,
    ctds: list[CTD],
    outputdt: timedelta,
) -> None:
    """
    Use Parcels to simulate a set of CTDs in a fieldset.

    :param fieldset: The fieldset to simulate the CTDs in.
    :param out_path: The path to write the results to.
    :param ctds: A list of CTDs to simulate.
    :param outputdt: Interval which dictates the update frequency of file output during simulation
    :raises ValueError: Whenever provided CTDs, fieldset, are not compatible with this function.
    """
    WINCH_SPEED = 1.0  # sink and rise speed in m/s
    DT = 10.0  # dt of CTD simulation integrator

    if len(ctds) == 0:
        print(
            "No CTDs provided. Parcels currently crashes when providing an empty particle set, so no CTD simulation will be done and no files will be created."
        )
        # TODO when Parcels supports it this check can be removed.
        return

    fieldset_starttime = fieldset.time_origin.fulltime(fieldset.U.grid.time_full[0])
    fieldset_endtime = fieldset.time_origin.fulltime(fieldset.U.grid.time_full[-1])

    # deploy time for all ctds should be later than fieldset start time
    if not all(
        [np.datetime64(ctd.spacetime.time) >= fieldset_starttime for ctd in ctds]
    ):
        raise ValueError("CTD deployed before fieldset starts.")

    # depth the ctd will go to. shallowest between ctd max depth and bathymetry.
    max_depths = [
        max(
            ctd.max_depth,
            fieldset.bathymetry.eval(
                z=0, y=ctd.spacetime.location.lat, x=ctd.spacetime.location.lon, time=0
            ),
        )
        for ctd in ctds
    ]

    # CTD depth can not be too shallow, because kernel would break.
    # This shallow is not useful anyway, no need to support.
    if not all([max_depth <= -DT * WINCH_SPEED for max_depth in max_depths]):
        raise ValueError(
            f"CTD max_depth or bathymetry shallower than maximum {-DT * WINCH_SPEED}"
        )

    # define parcel particles
    ctd_particleset = ParticleSet(
        fieldset=fieldset,
        pclass=_CTDParticle,
        lon=[ctd.spacetime.location.lon for ctd in ctds],
        lat=[ctd.spacetime.location.lat for ctd in ctds],
        depth=[ctd.min_depth for ctd in ctds],
        time=[ctd.spacetime.time for ctd in ctds],
        max_depth=max_depths,
        min_depth=[ctd.min_depth for ctd in ctds],
        winch_speed=[WINCH_SPEED for _ in ctds],
    )

    # define output file for the simulation
    out_file = ctd_particleset.ParticleFile(name=out_path, outputdt=outputdt)

    # execute simulation
    ctd_particleset.execute(
        [_sample_salinity, _sample_temperature, _ctd_cast],
        endtime=fieldset_endtime,
        dt=DT,
        verbose_progress=False,
        output_file=out_file,
    )

    # there should be no particles left, as they delete themselves when they resurface
    if len(ctd_particleset.particledata) != 0:
        raise ValueError(
            "Simulation ended before CTD resurfaced. This most likely means the field time dimension did not match the simulation time span."
        )
