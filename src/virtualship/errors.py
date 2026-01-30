class CredentialFileError(Exception):
    """Exception raised for errors in the input file format."""

    pass


class IncompleteDownloadError(Exception):
    """Exception raised for incomplete downloads."""

    pass


class CheckpointError(RuntimeError):
    """An error in the checkpoint."""

    pass


class ScheduleError(RuntimeError):
    """An error in the schedule."""

    pass


class InstrumentsConfigError(RuntimeError):
    """An error in the InstrumentsConfig."""

    pass


class UserError(Exception):
    """Error raised when there is an user error."""

    pass


class UnexpectedError(Exception):
    """Error raised when there is an unexpected problem."""

    pass


class UnderwayConfigsError(Exception):
    """Error raised when underway instrument configurations (ADCP or underwater ST) are missing."""

    pass


class CopernicusCatalogueError(Exception):
    """Error raised when a relevant product is not found in the Copernicus Catalogue."""

    pass
