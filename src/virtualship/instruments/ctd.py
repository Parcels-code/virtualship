from dataclasses import dataclass
from typing import ClassVar

from virtualship.models import Spacetime, instruments

## TODO: __init__.py will also need updating!
# + therefore instructions for adding new instruments will also involve adding to __init__.py as well as the new instrument script + update InstrumentType in instruments.py


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


class CTDInstrument(instruments.Instrument):
    """CTD instrument class."""

    def __init__(
        self,
        config,
        input_dataset,
        kernels,
    ):
        """Initialise with instrument's name."""
        super().__init__(CTD.name, config, input_dataset, kernels)

    def simulate(self):
        """Simulate measurements."""
        ...


# # [PSEUDO-CODE] example implementation for reference
# ctd = CTDInstrument(config=CTD, data_dir=..., kernels=...)

# ctd.simulate(...)
