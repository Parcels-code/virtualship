import pydantic
import pytest

from virtualship.instruments.sensors import (
    SensorType,
)
from virtualship.instruments.types import InstrumentType
from virtualship.models.expedition import SENSOR_REGISTRY, SensorConfig
from virtualship.utils import get_supported_sensors

EXPECTED_SENSOR_MEMBERS = {
    "TEMPERATURE",
    "SALINITY",
    "VELOCITY",
    "OXYGEN",
    "CHLOROPHYLL",
    "NITRATE",
    "PHOSPHATE",
    "PH",
    "PHYTOPLANKTON",
    "PRIMARY_PRODUCTION",
}


def test_sensor_registry_keys_match_sensor_type():
    """SENSOR_REGISTRY keys must be exactly the set of SensorType members."""
    assert set(SENSOR_REGISTRY().keys()) == set(SensorType)


@pytest.mark.parametrize(
    "sensor_type",
    [
        SensorType.OXYGEN,
        SensorType.CHLOROPHYLL,
        SensorType.NITRATE,
        SensorType.PHOSPHATE,
        SensorType.PH,
        SensorType.PHYTOPLANKTON,
        SensorType.PRIMARY_PRODUCTION,
    ],
)
def test_sensor_registry_bgc_entries_category(sensor_type):
    """All BGC sensors must have category 'bgc'."""
    assert SENSOR_REGISTRY()[sensor_type].category == "bgc"


def test_sensor_registry_unique_fs_keys():
    """No two sensors should share an fs_key."""
    fs_keys = [meta.fs_key for meta in SENSOR_REGISTRY().values()]
    assert len(fs_keys) == len(set(fs_keys)), (
        "Duplicate fs_key found in SENSOR_REGISTRY"
    )


def test_sensor_type_all_members_exist():
    """All expected SensorType members are present."""
    actual = {m.name for m in SensorType}
    assert actual == EXPECTED_SENSOR_MEMBERS


def test_sensor_type_lookup_by_value():
    """Can construct a SensorType from its string value."""
    assert SensorType("SALINITY") is SensorType.SALINITY


def test_sensor_type_invalid_value_error():
    """Invalid string raises ValueError."""
    with pytest.raises(ValueError):
        SensorType("NOT_A_SENSOR")


def test_all_allowlists_are_frozenset():
    """All per-instrument supported sensor sets must be frozensets (immutable)."""
    for itype in InstrumentType:
        allowlist = get_supported_sensors(itype)
        assert isinstance(allowlist, frozenset)


def test_sensor_config_basic_construction():
    """Standard construction with SensorType enum."""
    sc = SensorConfig(sensor_type=SensorType.TEMPERATURE)
    assert sc.sensor_type is SensorType.TEMPERATURE
    assert sc.enabled is True


def test_sensor_config_disabled():
    """Can explicitly set enabled=False."""
    sc = SensorConfig(sensor_type=SensorType.SALINITY, enabled=False)
    assert sc.enabled is False


def test_sensor_config_from_string_shorthand():
    """A bare string should be accepted as shorthand."""
    sc = SensorConfig.model_validate("TEMPERATURE")
    assert sc.sensor_type is SensorType.TEMPERATURE
    assert sc.enabled is True


def test_sensor_config_invalid_string_error():
    """An unknown sensor name should raise error."""
    with pytest.raises(pydantic.ValidationError):
        SensorConfig.model_validate("NOT_REAL")


def test_serialize_sensor_list_disabled_excluded():
    """Disabled sensors are excluded from serialisation."""
    sensors = [
        SensorConfig(sensor_type=SensorType.TEMPERATURE, enabled=True),
        SensorConfig(sensor_type=SensorType.SALINITY, enabled=False),
    ]
    assert SensorConfig.serialize_list(sensors) == ["TEMPERATURE"]


def test_check_sensor_compatibility_unsupported_error():
    """Unsupported sensor fails."""
    sensors = [SensorConfig(sensor_type=SensorType.OXYGEN)]
    with pytest.raises(ValueError, match="does not support sensor"):
        SensorConfig.check_compatibility(sensors, InstrumentType.DRIFTER, "Drifter")


def test_check_sensor_compatibility_all_disabled_error():
    """All sensors disabled fails."""
    sensors = [SensorConfig(sensor_type=SensorType.TEMPERATURE, enabled=False)]
    with pytest.raises(ValueError, match="no enabled sensors"):
        SensorConfig.check_compatibility(sensors, InstrumentType.DRIFTER, "Drifter")


def test_check_sensor_compatibility_empty_error():
    """Empty sensor list fails."""
    with pytest.raises(ValueError, match="no enabled sensors"):
        SensorConfig.check_compatibility([], InstrumentType.DRIFTER, "Drifter")


def test_check_sensor_compatibility_mixed_error():
    """Mix of valid and invalid sensors fails."""
    sensors = [
        SensorConfig(sensor_type=SensorType.TEMPERATURE),
        SensorConfig(sensor_type=SensorType.OXYGEN),
    ]
    with pytest.raises(ValueError, match="does not support"):
        SensorConfig.check_compatibility(sensors, InstrumentType.DRIFTER, "Drifter")
