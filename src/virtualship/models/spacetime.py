"""Location class. See class description."""

from dataclasses import dataclass
from datetime import datetime

from .location import Location


@dataclass
class Spacetime:
    """A location and time."""

    location: Location
    time: datetime
