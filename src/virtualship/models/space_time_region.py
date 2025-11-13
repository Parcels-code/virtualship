"""SpaceTimeRegion class."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, model_validator
from typing_extensions import Self

Longitude = Annotated[float, Field(..., ge=-180, le=180)]
Latitude = Annotated[float, Field(..., ge=-90, le=90)]
Depth = float  # TODO: insert a minimum depth here? e.g., `Annotated[float, Field(..., ge=0)]`
# TODO: is_valid_depth in validator_utils.py will alse need to be updated if this TODO is implemented


class SpatialRange(BaseModel):
    """Defines geographic boundaries."""

    minimum_longitude: Longitude
    maximum_longitude: Longitude
    minimum_latitude: Latitude
    maximum_latitude: Latitude
    minimum_depth: Depth | None = None
    maximum_depth: Depth | None = None

    @model_validator(mode="after")
    def _check_lon_lat_domain(self) -> Self:
        if not self.minimum_longitude < self.maximum_longitude:
            raise ValueError("minimum_longitude must be less than maximum_longitude")
        if not self.minimum_latitude < self.maximum_latitude:
            raise ValueError("minimum_latitude must be less than maximum_latitude")

        if sum([self.minimum_depth is None, self.maximum_depth is None]) == 1:
            raise ValueError("Both minimum_depth and maximum_depth must be provided.")

        if self.minimum_depth is None:
            return self

        if not self.minimum_depth < self.maximum_depth:
            raise ValueError("minimum_depth must be less than maximum_depth")
        return self


class TimeRange(BaseModel):
    """Defines the temporal boundaries for a space-time region."""

    #! TODO: Remove the `| None` for `start_time` and `end_time`, and have the MFP functionality not use pydantic (with testing to avoid codebase drift)
    start_time: datetime | None = None
    end_time: datetime | None = None

    @model_validator(mode="after")
    def _check_time_range(self) -> Self:
        if (
            self.start_time and self.end_time
        ):  #! TODO: remove this check once `start_time` and `end_time` are required
            if not self.start_time < self.end_time:
                raise ValueError("start_time must be before end_time")
        return self


class SpaceTimeRegion(BaseModel):
    """An space-time region with spatial and temporal boundaries."""

    spatial_range: SpatialRange
    time_range: TimeRange
