from dataclasses import dataclass
from typing import ClassVar

from virtualship.models import instruments

## TODO: __init__.py will also need updating!
# + therefore instructions for adding new instruments will also involve adding to __init__.py as well as the new instrument script + update InstrumentType in instruments.py


@dataclass
class ADCP:
    """ADCP configuration."""

    name: ClassVar[str] = "ADCP"


# ---------------
# TODO: KERNELS
# ---------------


class ADCPInputDataset(instruments.InputDataset):
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


class ADCPInstrument(instruments.Instrument):
    """ADCP instrument class."""

    def __init__(
        self,
        config,
        input_dataset,
        kernels,
    ):
        """Initialise with instrument's name."""
        super().__init__(ADCP.name, config, input_dataset, kernels)

    def simulate(self):
        """Simulate measurements."""
        ...
