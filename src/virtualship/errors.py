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


class ConfigError(RuntimeError):
    """An error in the config."""

    pass


class UserError(Exception):
    """Error raised when there is an user error."""

    pass


class UnexpectedError(Exception):
    """Error raised when there is an unexpected problem."""

    pass
