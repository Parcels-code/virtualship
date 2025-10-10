from pathlib import Path

import pytest

from virtualship.errors import ConfigError
from virtualship.models import Schedule, ShipConfig
from virtualship.utils import get_example_config, get_example_schedule

expedition_dir = Path("expedition_dir")


@pytest.fixture
def schedule(tmp_file):
    with open(tmp_file, "w") as file:
        file.write(get_example_schedule())
    return Schedule.from_yaml(tmp_file)


@pytest.fixture
def schedule_no_xbt(schedule):
    for waypoint in schedule.waypoints:
        if waypoint.instrument and any(
            instrument.name == "XBT" for instrument in waypoint.instrument
        ):
            waypoint.instrument = [
                instrument
                for instrument in waypoint.instrument
                if instrument.name != "XBT"
            ]

    return schedule


@pytest.fixture
def ship_config(tmp_file):
    with open(tmp_file, "w") as file:
        file.write(get_example_config())
    return ShipConfig.from_yaml(tmp_file)


@pytest.fixture
def ship_config_no_xbt(ship_config):
    delattr(ship_config, "xbt_config")
    return ship_config


@pytest.fixture
def ship_config_no_ctd(ship_config):
    delattr(ship_config, "ctd_config")
    return ship_config


@pytest.fixture
def ship_config_no_ctd_bgc(ship_config):
    delattr(ship_config, "ctd_bgc_config")
    return ship_config


@pytest.fixture
def ship_config_no_argo_float(ship_config):
    delattr(ship_config, "argo_float_config")
    return ship_config


@pytest.fixture
def ship_config_no_drifter(ship_config):
    delattr(ship_config, "drifter_config")
    return ship_config


def test_import_export_ship_config(ship_config, tmp_file) -> None:
    ship_config.to_yaml(tmp_file)
    ship_config_2 = ShipConfig.from_yaml(tmp_file)
    assert ship_config == ship_config_2


def test_verify_ship_config(ship_config, schedule) -> None:
    ship_config.verify(schedule)


def test_verify_ship_config_no_instrument(ship_config, schedule_no_xbt) -> None:
    ship_config.verify(schedule_no_xbt)


@pytest.mark.parametrize(
    "ship_config_fixture,error,match",
    [
        pytest.param(
            "ship_config_no_xbt",
            ConfigError,
            "Planning has a waypoint with XBT instrument, but configuration does not configure XBT.",
            id="ShipConfigNoXBT",
        ),
        pytest.param(
            "ship_config_no_ctd",
            ConfigError,
            "Planning has a waypoint with CTD instrument, but configuration does not configure CTD.",
            id="ShipConfigNoCTD",
        ),
        pytest.param(
            "ship_config_no_ctd_bgc",
            ConfigError,
            "Planning has a waypoint with CTD_BGC instrument, but configuration does not configure CTD_BGCs.",
            id="ShipConfigNoCTD_BGC",
        ),
        pytest.param(
            "ship_config_no_argo_float",
            ConfigError,
            "Planning has a waypoint with Argo float instrument, but configuration does not configure Argo floats.",
            id="ShipConfigNoARGO_FLOAT",
        ),
        pytest.param(
            "ship_config_no_drifter",
            ConfigError,
            "Planning has a waypoint with drifter instrument, but configuration does not configure drifters.",
            id="ShipConfigNoDRIFTER",
        ),
    ],
)
def test_verify_ship_config_errors(
    request, schedule, ship_config_fixture, error, match
) -> None:
    ship_config = request.getfixturevalue(ship_config_fixture)

    with pytest.raises(error, match=match):
        ship_config.verify(schedule)
