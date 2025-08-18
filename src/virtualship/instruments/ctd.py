from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from virtualship.models import Spacetime, instruments
from virtualship.models.spacetime import Spacetime

MYINSTRUMENT = "CTD"


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

    def __init__(self):
        """Initialise with instrument's name."""
        super().__init__(MYINSTRUMENT)

    def download_data(self, name: str) -> None:
        """Download CTD data."""
        ...

    def get_dataset_path(self, name: str) -> Path:
        """Get path to CTD dataset."""
        ...


class CTDInstrument(instruments.Instrument):
    """CTD instrument class."""

    def __init__(
        self,
        config,
        input_dataset: CTDInputDataset,
        kernels,
    ):
        """Initialise with instrument's name."""
        super().__init__(MYINSTRUMENT, config, input_dataset, kernels)

    def load_fieldset(self):
        """Load fieldset."""
        ...

    def simulate(self):
        """Simulate measurements."""
        ...
