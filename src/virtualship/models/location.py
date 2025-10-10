"""Location class. See class description."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Location:
    """A location on a sphere."""

    latitude: float
    longitude: float

    def __post_init__(self) -> None:
        """
        Verify this location has valid latitude and longitude.

        :raises ValueError: If latitude and/or longitude are not valid.
        """
        if self.lat < -90:
            raise ValueError("Latitude cannot be smaller than -90.")
        if self.lat > 90:
            raise ValueError("Latitude cannot be larger than 90.")
        if self.lon < -180:
            raise ValueError("Longitude cannot be smaller than -180.")
        if self.lon > 360:
            raise ValueError("Longitude cannot be larger than 360.")

    @property
    def lat(self) -> float:
        """
        Shorthand for latitude variable.

        :returns: Latitude variable.
        """
        return self.latitude

    @property
    def lon(self) -> float:
        """
        Shorthand for longitude variable.

        :returns: Longitude variable.
        """
        return self.longitude
