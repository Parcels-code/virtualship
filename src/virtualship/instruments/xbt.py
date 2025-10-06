from dataclasses import dataclass
from datetime import timedelta
from typing import ClassVar

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


# ---------------
# TODO: KERNELS
# ---------------


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


class XBTInstrument(instruments.Instrument):
    """XBT instrument class."""

    def __init__(
        self,
        config,
        input_dataset,
        kernels,
    ):
        """Initialise with instrument's name."""
        super().__init__(XBT.name, config, input_dataset, kernels)

    def simulate(self):
        """Simulate measurements."""
        ...
