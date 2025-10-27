import abc
from collections.abc import Callable
from datetime import timedelta
from enum import Enum
from pathlib import Path

import copernicusmarine
from yaspin import yaspin

from virtualship.models.space_time_region import SpaceTimeRegion
from virtualship.utils import ship_spinner


class InstrumentType(Enum):
    """Types of the instruments."""

    # TODO: scope for this to evaporate in the future...?

    CTD = "CTD"
    CTD_BGC = "CTD_BGC"
    DRIFTER = "DRIFTER"
    ARGO_FLOAT = "ARGO_FLOAT"
    XBT = "XBT"
    ADCP = "ADCP"
    UNDERWATER_ST = "UNDERWATER_ST"

    @property
    def is_underway(self) -> bool:
        """Return True if instrument is an underway instrument (ADCP, UNDERWATER_ST)."""
        return self in {InstrumentType.ADCP, InstrumentType.UNDERWATER_ST}


def get_instruments_registry():
    # local imports to avoid circular import issues
    from virtualship.instruments.adcp import ADCPInputDataset
    from virtualship.instruments.argo_float import ArgoFloatInputDataset
    from virtualship.instruments.ctd import CTDInputDataset
    from virtualship.instruments.ctd_bgc import CTD_BGCInputDataset
    from virtualship.instruments.drifter import DrifterInputDataset
    from virtualship.instruments.ship_underwater_st import Underwater_STInputDataset
    from virtualship.instruments.xbt import XBTInputDataset

    _input_class_map = {
        "CTD": CTDInputDataset,
        "CTD_BGC": CTD_BGCInputDataset,
        "DRIFTER": DrifterInputDataset,
        "ARGO_FLOAT": ArgoFloatInputDataset,
        "XBT": XBTInputDataset,
        "ADCP": ADCPInputDataset,
        "UNDERWATER_ST": Underwater_STInputDataset,
    }

    return {
        inst: {
            "input_class": _input_class_map.get(inst.value),
        }
        for inst in InstrumentType
        if _input_class_map.get(inst.value) is not None
    }


# Base classes


class InputDataset(abc.ABC):
    """Base class for instrument input datasets."""

    def __init__(
        self,
        name: str,
        latlon_buffer: float,
        datetime_buffer: float,
        min_depth: float,
        max_depth: float,
        data_dir: str,
        credentials: dict,
        space_time_region: SpaceTimeRegion,
    ):
        """Initialise input dataset."""
        self.name = name
        self.latlon_buffer = latlon_buffer
        self.datetime_buffer = datetime_buffer
        self.min_depth = min_depth
        self.max_depth = max_depth
        self.data_dir = data_dir
        self.credentials = credentials
        self.space_time_region = space_time_region

    @abc.abstractmethod
    def get_datasets_dict(self) -> dict:
        """Get parameters for instrument's variable(s) specific data download."""
        ...

    def download_data(self) -> None:
        """Download data for the instrument using copernicusmarine."""
        parameter_args = dict(
            minimum_longitude=self.space_time_region.spatial_range.minimum_longitude
            - self.latlon_buffer,
            maximum_longitude=self.space_time_region.spatial_range.maximum_longitude
            + self.latlon_buffer,
            minimum_latitude=self.space_time_region.spatial_range.minimum_latitude
            - self.latlon_buffer,
            maximum_latitude=self.space_time_region.spatial_range.maximum_latitude
            + self.latlon_buffer,
            start_datetime=self.space_time_region.time_range.start_time,
            end_datetime=self.space_time_region.time_range.end_time
            + timedelta(days=self.datetime_buffer),
            minimum_depth=abs(self.min_depth),
            maximum_depth=abs(self.max_depth),
            output_directory=self.data_dir,
            username=self.credentials["username"],
            password=self.credentials["password"],
            overwrite=True,
            coordinates_selection_method="outside",
        )

        datasets_args = self.get_datasets_dict()

        for dataset in datasets_args.values():
            download_args = {**parameter_args, **dataset}
            copernicusmarine.subset(**download_args)


class Instrument(abc.ABC):
    """Base class for instruments."""

    def __init__(
        self,
        name: str,
        config,
        input_dataset: InputDataset,
        kernels: list[Callable],
    ):
        """Initialise instrument."""
        self.name = name
        self.config = config
        self.input_data = input_dataset
        self.kernels = kernels

    # def load_fieldset(self):
    #     """Load fieldset for simulation."""
    #     # paths = self.input_data.get_fieldset_paths()
    #     ...

    def get_output_path(self, output_dir: Path) -> Path:
        """Get output path for results."""
        return output_dir / f"{self.name}.zarr"

    def run(self):
        """Run instrument simulation."""
        with yaspin(
            text=f"Simulating {self.name} measurements... ",
            side="right",
            spinner=ship_spinner,
        ) as spinner:
            self.simulate()
            spinner.ok("✅")

    @abc.abstractmethod
    def simulate(self):
        """Simulate instrument measurements."""
        ...
