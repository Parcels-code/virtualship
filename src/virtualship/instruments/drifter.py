from dataclasses import dataclass
from datetime import timedelta
from typing import ClassVar

from virtualship.models import Spacetime, instruments

## TODO: __init__.py will also need updating!
# + therefore instructions for adding new instruments will also involve adding to __init__.py as well as the new instrument script + update InstrumentType in instruments.py


@dataclass
class Drifter:
    """Drifter configuration."""

    name: ClassVar[str] = "Drifter"
    spacetime: Spacetime
    depth: float  # depth at which it floats and samples
    lifetime: timedelta | None  # if none, lifetime is infinite


# ---------------
# TODO: KERNELS
# ---------------


class DrifterInputDataset(instruments.InputDataset):
    """Input dataset for Drifter instrument."""

    DOWNLOAD_BUFFERS: ClassVar[dict] = {
        "latlon_degrees": 3.0,
        "days": 21.0,
    }

    DOWNLOAD_LIMITS: ClassVar[dict] = {"min_depth": 1, "max_depth": 1}

    def __init__(self, data_dir, credentials, space_time_region):
        """Initialise with instrument's name."""
        super().__init__(
            Drifter.name,
            self.DOWNLOAD_BUFFERS["latlon_degrees"],
            self.DOWNLOAD_BUFFERS["days"],
            self.DOWNLOAD_LIMITS["min_depth"],
            self.DOWNLOAD_LIMITS["max_depth"],
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
                "output_filename": "drifter_uv.nc",
            },
            "Tdata": {
                "dataset_id": "cmems_mod_glo_phy-thetao_anfc_0.083deg_PT6H-i",
                "variables": ["thetao"],
                "output_filename": "drifter_t.nc",
            },
        }


class DrifterInstrument(instruments.Instrument):
    """Drifter instrument class."""

    def __init__(
        self,
        config,
        input_dataset,
        kernels,
    ):
        """Initialise with instrument's name."""
        super().__init__(Drifter.name, config, input_dataset, kernels)

    def simulate(self):
        """Simulate measurements."""
        ...
