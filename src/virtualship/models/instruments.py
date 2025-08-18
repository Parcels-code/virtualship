import abc
from collections.abc import Callable
from pathlib import Path

from yaspin import yaspin

from virtualship.utils import (
    ship_spinner,
)

# TODO
# how much detail needs to be fed into InputDataset (i.e. how much it differs per instrument)
# may impact whether need a child class (e.g. CTDInputDataset) as well as just InputDataset
# or whether it could just be fed a `name` ... ?

# ++ abc.abstractmethods could be useful for testing purposes...e.g. will fail if an instrumnet implementation doesn't adhere to the `Instrument` class standards


class InputDataset(abc.ABC):
    """Base class for instrument input datasets."""

    def __init__(self, name):
        """Initialise input dataset."""
        self.name = name

    @abc.abstractmethod
    def download_data(self, name: str) -> None:
        """Download data for the instrument."""
        pass

    @abc.abstractmethod
    def get_dataset_path(self, name: str) -> Path:
        """Get path to the dataset."""
        pass


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
        self.input_dataset = input_dataset
        self.kernels = kernels

    @abc.abstractmethod
    def load_fieldset(self):
        """Load fieldset for simulation."""
        pass

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
        pass


# e.g. pseudo-code ...
# TODO: (necessary?) how to dynamically assemble list of all instruments defined so that new instruments can be added only by changes in one place...?
available_instruments: list = ...
# for instrument in available_instruments:
#     MyInstrument(instrument)
