"""

Utils for validating inputs to Pydantic model fields in a Textual setting and generating Textual input validators.

Note, all validator functions require docstrings which describe the condition (used in error messaging). Presence is checked
by require_docstring() helper function.

"""

import datetime


def require_docstring(func):
    if func.__doc__ is None or not func.__doc__.strip():
        raise ValueError(f"Function '{func.__name__}' must have a docstring.")
    return func


# SCHEDULE INPUTS VALIDATION


@require_docstring
def is_valid_lat(value: str) -> bool:
    """(-90° < lat < 90°)."""
    try:
        v = float(value)
    except ValueError:
        return None

    return -90 < v < 90


@require_docstring
def is_valid_lon(value: str) -> bool:
    """(-180 < lon < 360)."""
    try:
        v = float(value)
    except ValueError:
        return None

    return -180 < v < 360


# SHIP CONFIG INPUTS VALIDATION

FIELD_CONSTRAINT_ATTRS = (
    "gt",
    "ge",
    "lt",
    "le",
)  # pydantic field constraint attributes used for validation and introspection


def get_field_type(model_class, field_name):
    """Get Pydantic model class data type."""
    return model_class.model_fields[field_name].annotation


def type_to_textual(field_type):
    """Convert data type to str which Textual can interpret for type = setting in Input objects."""
    if field_type in (float, datetime.timedelta):
        return "number"
    elif field_type is int:
        return "integer"
    else:
        return "text"


def get_field_conditions(model_class, field_name):
    """Determine and return what conditions (and associated reference value) a Pydantic model sets on inputs."""
    field_info = model_class.model_fields[field_name]
    conditions = {}
    for meta in field_info.metadata:
        for attr in dir(meta):
            if not attr.startswith("_") and getattr(meta, attr) is not None:
                if attr in FIELD_CONSTRAINT_ATTRS:
                    conditions[attr] = getattr(meta, attr)
                else:
                    raise ValueError(
                        f"Unexpected constraint '{attr}' found on field '{field_name}'. "
                        f"Allowed constraints: {FIELD_CONSTRAINT_ATTRS}"
                    )
    return list(conditions.keys()), list(conditions.values())


def make_validator(condition, reference, value_type):
    """
    Make a validator function based on the Pydantic model field conditions returned by get_field_conditions().

    N.B. #1, docstrings describing the conditional are required in the child functions (e.g. is_gt0), and presence is checked by require_docstring().
    Docstrings will be used to generate informative UI invalid entry messages, so them being informative and accurate is important!

    N.B. #2 Textual validator tools do not currently support additional arguments (such as 'reference' values) being fed into the validator functions (such as is_gt0) at present.
    Therefore, reference values for the conditions cannot be fed in dynamically and necessitates 'hard-coding' the condition and reference value combination.
    At present, Pydantic models in VirtualShip only require gt/ge/lt/le relative to **0.0** so the 'reference' value is always checked as being == 0.0
    Additional custom conditions can be 'hard-coded' as new condition and reference combinations if Pydantic model specifications change in the future and/or new instruments are added to VirtualShip etc.

    """

    def convert(value):
        try:
            if value_type is datetime.timedelta:
                return datetime.timedelta(minutes=float(value))
            return value_type(value)
        except Exception:
            return None

    if value_type in (float, int) and reference == 0.0:
        ref_zero = 0.0
    elif value_type is datetime.timedelta and reference == datetime.timedelta():
        ref_zero = datetime.timedelta()
    else:
        raise ValueError(
            f"Unsupported value_type/reference combination: {value_type}, {reference}"
        )

    if condition == "gt" and reference == ref_zero:

        @require_docstring
        def is_gt0(value: str) -> bool:
            """Greater than 0."""
            v = convert(value)
            return v is not None and v > ref_zero

        return is_gt0

    if condition == "ge" and reference == ref_zero:

        @require_docstring
        def is_ge0(value: str) -> bool:
            """Greater than or equal to 0."""
            v = convert(value)
            return v is not None and v >= ref_zero

        return is_ge0

    if condition == "lt" and reference == ref_zero:

        @require_docstring
        def is_lt0(value: str) -> bool:
            """Less than 0."""
            v = convert(value)
            return v is not None and v < ref_zero

        return is_lt0

    if condition == "le" and reference == ref_zero:

        @require_docstring
        def is_le0(value: str) -> bool:
            """Less than or equal to 0."""
            v = convert(value)
            return v is not None and v <= ref_zero

        return is_le0

    else:
        raise ValueError(
            f"Unknown condition: {condition} and reference value: {reference} combination."
        )


def group_validators(model, attr):
    """Bundle all validators for Input into singular list."""
    return [
        make_validator(cond, ref, get_field_type(model, attr))
        for cond, ref in zip(
            *get_field_conditions(model, attr),
            strict=False,
        )
    ]
