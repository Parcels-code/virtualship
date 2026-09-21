"""Location class. See class description."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Location:
    """A location on a sphere."""

    latitude: float | None = None
    longitude: float | None = None

    def __post_init__(self) -> None:
        """
        Verify this location has valid latitude and longitude if provided.

        :raises ValueError: If latitude and/or longitude are not valid.
        """
        if self.lat is not None:
            if self.lat < -90:
                raise ValueError("Latitude cannot be smaller than -90.")
            if self.lat > 90:
                raise ValueError("Latitude cannot be larger than 90.")

        if self.lon is not None:
            if self.lon < -180:
                raise ValueError("Longitude cannot be smaller than -180.")
            if self.lon > 360:
                raise ValueError("Longitude cannot be larger than 360.")

    @property
    def lat(self) -> float | None:
        """
        Shorthand for latitude variable.

        :returns: Latitude variable.
        """
        return self.latitude

    @property
    def lon(self) -> float | None:
        """
        Shorthand for longitude variable.

        :returns: Longitude variable.
        """
        return self.longitude
