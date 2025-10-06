from dataclasses import dataclass
from typing import ClassVar

from virtualship.models import instruments

## TODO: __init__.py will also need updating!
# + therefore instructions for adding new instruments will also involve adding to __init__.py as well as the new instrument script + update InstrumentType in instruments.py


@dataclass
class Underwater_ST:
    """Underwater_ST configuration."""

    name: ClassVar[str] = "Underwater_ST"


# ---------------
# TODO: KERNELS
# ---------------


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


class Underwater_STInstrument(instruments.Instrument):
    """Underwater_ST instrument class."""

    def __init__(
        self,
        config,
        input_dataset,
        kernels,
    ):
        """Initialise with instrument's name."""
        super().__init__(Underwater_ST.name, config, input_dataset, kernels)

    def simulate(self):
        """Simulate measurements."""
        ...
