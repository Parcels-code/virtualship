from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import numpy as np
import parcels
import pyproj
import pytest
import xarray as xr
import yaml

from virtualship.errors import InstrumentsConfigError, ScheduleError
from virtualship.models import (
    Expedition,
    Location,
    Schedule,
    Waypoint,
    _InstrumentConfigMixin,
)
from virtualship.models.expedition import Port
from virtualship.utils import (
    EXPEDITION,
    _get_example_expedition,
    _get_expedition,
)

projection = pyproj.Geod(ellps="WGS84")

expedition_dir = Path("expedition_dir")


@pytest.fixture
def base_expedition():
    """Shared expedition instance loaded directly from expedition_dir."""
    return _get_expedition(expedition_dir)


def test_import_export_expedition(tmpdir, base_expedition) -> None:
    out_path = tmpdir.join(EXPEDITION)

    expedition = Expedition(
        schedule=base_expedition.schedule,
        instruments_config=base_expedition.instruments_config,
        ship_config=base_expedition.ship_config,
    )
    expedition.to_yaml(out_path)

    expedition2 = Expedition.from_yaml(out_path)
    assert expedition == expedition2


def test_verify_schedule(base_expedition) -> None:
    schedule = base_expedition.schedule
    schedule.verify(
        base_expedition.ship_config.ship_speed_knots,
        base_expedition.instruments_config,
        ignore_land_test=True,
    )

    assert schedule._verified, (
        "Schedule should be marked as verified after successful verification."
    )


def test_get_instruments(base_expedition) -> None:
    expedition = Expedition(
        schedule=base_expedition.schedule,
        instruments_config=base_expedition.instruments_config,
        ship_config=base_expedition.ship_config,
    )
    assert set(instrument.name for instrument in expedition.get_instruments()) == {
        "CTD",
        "UNDERWATER_ST",
        "ADCP",
        "ARGO_FLOAT",
        "DRIFTER",
    }


def test_verify_on_land(base_expedition):
    """Test that schedule verification raises error for waypoints on land (0.0 m bathymetry)."""
    lat = np.array([0, 1.0, 2.0])
    lon = np.array([0, 1.0, 2.0])
    bathymetry = np.array(
        [
            [100, 0.0, 100],
            [100, 100, 0.0],
            [0.0, 100, 100],
        ]
    )

    ds_bathymetry = xr.Dataset(
        {"deptho": (("lat", "lon"), bathymetry)},
        coords={
            "lon": (("lon"), lon, {"units": "degrees_east"}),
            "lat": (("lat"), lat, {"units": "degrees_north"}),
        },
    )

    ds_fset = parcels.convert.copernicusmarine_to_sgrid(
        fields={"bathymetry": ds_bathymetry["deptho"]},
    )
    bathymetry_fieldset = parcels.FieldSet.from_sgrid_conventions(ds_fset)

    schedule = Schedule(
        waypoints=[
            Port(location=Location(0, 0), time=datetime(2022, 1, 1, 1, 0, 0)),
            Waypoint(location=Location(0.0, 1.0), time=datetime(2022, 1, 2, 1, 0, 0)),
            Waypoint(location=Location(1.0, 2.0), time=datetime(2022, 1, 3, 1, 0, 0)),
            Waypoint(location=Location(2.0, 0.0), time=datetime(2022, 1, 4, 1, 0, 0)),
            Port(location=Location(1, 0), time=datetime(2022, 1, 5, 1, 0, 0)),
        ]
    )

    with patch(
        "virtualship.models.expedition._get_bathy_data",
        return_value=bathymetry_fieldset,
    ):
        with pytest.raises(
            ScheduleError,
            match=r"The following waypoint\(s\) throw\(s\) error\(s\):",
        ):
            schedule.verify(
                base_expedition.ship_config.ship_speed_knots,
                base_expedition.instruments_config,
                ignore_land_test=False,
                from_data=None,
            )


@pytest.mark.parametrize(
    "waypoints,error,match",
    [
        pytest.param(
            [Waypoint(location=Location(0, 0))],
            ScheduleError,
            r"First and last waypoints must be Ports \(of arrival/departure\)\.",
            id="NoPorts",
        ),
        pytest.param(
            [
                Port(location=Location(0, 0)),
                Port(location=Location(1, 0)),
            ],
            ScheduleError,
            "At least one non-port waypoint must be provided.",
            id="NoWaypoints",
        ),
        pytest.param(
            [
                Port(location=Location(0, 0)),
                Waypoint(location=Location(0, 0)),
                Waypoint(location=Location(1, 0), time=datetime(2022, 1, 1, 1, 0, 0)),
                Port(location=Location(1, 0)),
            ],
            ScheduleError,
            "Waypoint 1 must have a specified time.",
            id="FirstWaypointHasTime",
        ),
        pytest.param(
            [
                Port(location=Location(0, 0), time=datetime(2022, 1, 1, 0, 0, 0)),
                Waypoint(location=Location(0, 0), time=datetime(2022, 1, 2, 1, 0, 0)),
                Waypoint(location=Location(0, 0)),
                Waypoint(location=Location(1, 0), time=datetime(2022, 1, 1, 1, 0, 0)),
                Port(location=Location(1, 0), time=datetime(2022, 1, 3, 0, 0, 0)),
            ],
            ScheduleError,
            r"Waypoint\(s\).*?: each waypoint should be timed after all previous waypoints",
            id="SequentialWaypoints",
        ),
        pytest.param(
            [
                Port(location=Location(0, 0), time=datetime(2022, 1, 1, 0, 0, 0)),
                Waypoint(
                    location=Location(0, 0),
                    time=datetime(2022, 1, 1, 1, 0, 0),
                    instrument=[],
                ),
                Waypoint(
                    location=Location(1, 0),
                    time=datetime(2022, 1, 1, 1, 1, 0),
                    instrument=[],
                ),
                Port(location=Location(1, 0), time=datetime(2022, 1, 2, 0, 0, 0)),
            ],
            ScheduleError,
            r"Waypoint planning is not valid: would arrive too late at waypoint 2\.",
            id="NotEnoughTime",
        ),
    ],
)
def test_verify_schedule_errors(base_expedition, waypoints: list, error, match) -> None:
    with pytest.raises(error, match=match):
        schedule = Schedule(waypoints=waypoints)
        schedule.verify(
            base_expedition.ship_config.ship_speed_knots,
            base_expedition.instruments_config,
            ignore_land_test=True,
        )


@pytest.fixture
def expedition(tmp_file):
    with open(tmp_file, "w") as file:
        file.write(_get_example_expedition())
    return Expedition.from_yaml(tmp_file)


@pytest.fixture
def expedition_no_xbt(expedition):
    for waypoint in expedition.schedule.waypoints:
        instruments = getattr(waypoint, "instrument", None)
        if instruments and any(instrument.name == "XBT" for instrument in instruments):
            waypoint.instrument = [inst for inst in instruments if inst.name != "XBT"]
    return expedition


@pytest.fixture(
    params=[
        (
            "xbt_config",
            "XBT",
            "Expedition includes instrument 'XBT', but instruments_config does not provide configuration for it.",
        ),
        (
            "ctd_config",
            "CTD",
            "Expedition includes instrument 'CTD', but instruments_config does not provide configuration for it.",
        ),
        (
            "argo_float_config",
            "ARGO_FLOAT",
            "Expedition includes instrument 'ARGO_FLOAT', but instruments_config does not provide configuration for it.",
        ),
        (
            "drifter_config",
            "DRIFTER",
            "Expedition includes instrument 'DRIFTER', but instruments_config does not provide configuration for it.",
        ),
        (
            "adcp_config",
            "ADCP",
            r"Underway instrument config attribute\(s\) are missing from YAML\. Must be <Instrument>Config object or None\.",
        ),
        (
            "ship_underwater_st_config",
            "UNDERWATER_ST",
            r"Underway instrument config attribute\(s\) are missing from YAML\. Must be <Instrument>Config object or None\.",
        ),
    ]
)
def missing_instrument_config(request, expedition):
    attr_name, error_match = request.param
    delattr(expedition.instruments_config, attr_name)
    return expedition.instruments_config, error_match


def test_verify_instruments_config(expedition) -> None:
    expedition.instruments_config.verify(expedition)


def test_verify_instruments_config_no_instrument(expedition, expedition_no_xbt) -> None:
    expedition.instruments_config.verify(expedition_no_xbt)


def test_verify_instruments_config_errors(
    expedition, missing_instrument_config
) -> None:
    instruments_config, match = missing_instrument_config
    with pytest.raises(InstrumentsConfigError, match=match):
        instruments_config.verify(expedition)


def test_all_instrument_configs_use_mixin(expedition):
    """Every registered instrument config must inherit _InstrumentConfigMixin and define the required ClassVars."""
    instrument_configs = [
        iconfig
        for iconfig in expedition.instruments_config.__dict__.values()
        if iconfig
    ]

    for iconfig in instrument_configs:
        cls = iconfig.__class__
        assert issubclass(cls, _InstrumentConfigMixin), (
            f"{cls.__name__} does not inherit _InstrumentConfigMixin"
        )
        assert "_instrument_type" in cls.__dict__, (
            f"{cls.__name__} does not define _instrument_type"
        )
        assert "_instrument_name" in cls.__dict__, (
            f"{cls.__name__} does not define _instrument_name"
        )
        assert cls._instrument_type == iconfig._instrument_type, (
            f"{cls.__name__}._instrument_type mismatch"
        )


def test_waypoint_yaml_lines(base_expedition) -> None:
    """Each full waypoint entry in the raw YAML dump should start with '- instrument:', whereas Port waypoints should start with just '- location:'."""
    schedule = base_expedition.schedule
    raw = yaml.dump(
        {
            "schedule": {
                "waypoints": [wp.model_dump(by_alias=True) for wp in schedule.waypoints]
            }
        },
        default_flow_style=False,
    )

    standard_lines = [
        line for line in raw.splitlines() if line.lstrip().startswith("- instrument:")
    ]
    port_lines = [
        line for line in raw.splitlines() if line.lstrip().startswith("- location:")
    ]

    port_wps = [wp for wp in schedule.waypoints if isinstance(wp, Port)]
    standard_wps = [wp for wp in schedule.waypoints if not isinstance(wp, Port)]

    assert len(port_wps) == 2, (
        "There should be exactly 2 Port waypoints (departure and arrival)."
    )

    assert len(port_lines) == len(port_wps), (
        f"Expected {len(port_wps)} lines starting with '- location:' in the YAML dump, "
        f"got {len(port_lines)}. The Port/Waypoint field order or terminology may have changed. "
        "Note this can have implications for the placement of port/waypoint number comments in Expedition.to_yaml()."
    )

    assert len(standard_lines) == len(standard_wps), (
        f"Expected {len(standard_wps)} lines starting with '- instrument:' in the YAML dump, "
        f"got {len(standard_lines)}. The Waypoint field order or terminology may have changed. "
        "Note this can have implications for the placement of waypoint number comments in Expedition.to_yaml()."
    )


def test_wps_in_use(base_expedition):
    """Test that _get_wps_in_use() correctly returns waypoints excluding placeholder ports."""
    base_time = datetime.strptime("1950-01-01", "%Y-%m-%d")
    schedule = Schedule(
        waypoints=[
            Port(location=Location(None, None), time=None),
            Waypoint(location=Location(1, 1), time=base_time + timedelta(hours=1)),
            Waypoint(location=Location(2, 2), time=base_time + timedelta(hours=2)),
            Port(location=Location(None, None), time=None),
        ]
    )
    expedition = Expedition(
        schedule=schedule,
        instruments_config=base_expedition.instruments_config,
        ship_config=base_expedition.ship_config,
    )

    wps_in_use = expedition.schedule._get_wps_in_use()
    assert len(wps_in_use) == 2  # placeholder waypoints should be removed
    assert all(isinstance(wp, Waypoint) for wp in wps_in_use)
