from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import numpy as np
import parcels
import pyproj
import pytest
import xarray as xr

from virtualship.errors import InstrumentsConfigError, ScheduleError
from virtualship.instruments.types import InstrumentType
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


def _with_schedule(base_expedition, schedule) -> Expedition:
    """An expedition using the given schedule, with the shared ship and instrument configs."""
    return Expedition(
        schedule=schedule,
        instruments_config=base_expedition.instruments_config,
        ship_config=base_expedition.ship_config,
    )


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
    base_expedition.verify_schedule(ignore_land_test=True)

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


def test_stationkeeping_time_uses_slowest_deployment(expedition) -> None:
    """Deployments run concurrently while the ship is stopped, so the slowest one governs."""
    ship_config = expedition.ship_config
    ctd_config = expedition.instruments_config.ctd_config

    waypoint = Waypoint(
        location=Location(0, 0),
        sea_depth_meter=-500.0,
        instrument=[
            InstrumentType.CTD,
            InstrumentType.ARGO_FLOAT,
            InstrumentType.XBT,
            InstrumentType.DRIFTER,
            InstrumentType.DRIFTER,  # two drifter deployments
        ],
    )

    # only the CTD holds the ship; it is winched to the seabed at 500 m and hauled back
    cast = timedelta(
        seconds=2
        * abs(-500.0 - ctd_config.min_depth_meter)
        / ctd_config.winch_speed_meter_per_second
    )
    expected = (
        ship_config.waypoint_slowdown_time + cast + ship_config.waypoint_speedup_time
    )

    assert expedition.stationkeeping_time(waypoint) == expected


def test_stationkeeping_time_capped_by_sea_depth(expedition) -> None:
    """A CTD cannot be winched below the seabed, so a shallow waypoint is quicker."""
    deep = Waypoint(
        location=Location(0, 0), instrument=InstrumentType.CTD, sea_depth_meter=-3000.0
    )
    shallow = Waypoint(
        location=Location(0, 0), instrument=InstrumentType.CTD, sea_depth_meter=-100.0
    )

    # deep waypoint is limited by the CTD's own configured maximum, not the seabed
    unbounded = Waypoint(location=Location(0, 0), instrument=InstrumentType.CTD)

    assert expedition.stationkeeping_time(shallow) < expedition.stationkeeping_time(
        deep
    )
    assert expedition.stationkeeping_time(deep) == expedition.stationkeeping_time(
        unbounded
    )


def test_stationkeeping_time_single_instrument(expedition) -> None:
    """A bare (non-list) InstrumentType value is handled the same as a single element list."""
    bare = Waypoint(
        location=Location(0, 0), instrument=InstrumentType.CTD, sea_depth_meter=-500.0
    )
    listed = Waypoint(
        location=Location(0, 0), instrument=[InstrumentType.CTD], sea_depth_meter=-500.0
    )

    assert expedition.stationkeeping_time(bare) == expedition.stationkeeping_time(
        listed
    )


def test_stationkeeping_time_xbt_does_not_stop_ship(expedition) -> None:
    """An XBT is launched from a moving ship, so alone it costs no stationkeeping time."""
    ship_config = expedition.ship_config
    xbt_only = Waypoint(location=Location(0, 0), instrument=InstrumentType.XBT)
    xbt_and_drifter = Waypoint(
        location=Location(0, 0),
        instrument=[InstrumentType.XBT, InstrumentType.DRIFTER],
    )

    assert expedition.stationkeeping_time(xbt_only) == timedelta(0)
    # another instrument at the same waypoint still makes the ship stop, and the XBT adds nothing on top
    assert expedition.stationkeeping_time(xbt_and_drifter) == (
        ship_config.waypoint_slowdown_time + ship_config.waypoint_speedup_time
    )


def test_stationkeeping_time_no_instruments(expedition) -> None:
    """The ship doesn't slows down where nothing is deployed, therefore ports and bare waypoints cost nothing."""
    assert expedition.stationkeeping_time(
        Waypoint(location=Location(0, 0), instrument=None)
    ) == timedelta(0)
    assert expedition.stationkeeping_time(
        Waypoint(location=Location(0, 0), instrument=[])
    ) == timedelta(0)
    assert expedition.stationkeeping_time(Port(location=Location(0, 0))) == timedelta(0)


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
            _with_schedule(base_expedition, schedule).verify_schedule(
                ignore_land_test=False, from_data=None
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
            "Schedule has no active waypoints",
            id="NoActiveWaypoints",
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
            r"Waypoint\(s\) #3: each waypoint should be timed after all previous waypoints",
            id="SequentialWaypoints",
        ),
        pytest.param(
            [
                Port(location=Location(0, 0), time=datetime(2022, 1, 1, 0, 0, 0)),
                Waypoint(location=Location(0, 0), time=datetime(2022, 1, 2, 0, 0, 0)),
                Port(location=Location(1, 0), time=datetime(2022, 1, 1, 12, 0, 0)),
            ],
            ScheduleError,
            r"Waypoint\(s\) Port of Arrival: each waypoint should be timed after all previous waypoints",
            id="SequentialWaypointsArrivalPort",
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
        pytest.param(
            [
                Port(location=Location(None, None), time=None),
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
            id="NotEnoughTimePlaceholderDeparturePort",
        ),
    ],
)
def test_verify_schedule_errors(base_expedition, waypoints: list, error, match) -> None:
    with pytest.raises(error, match=match):
        schedule = Schedule(waypoints=waypoints)
        _with_schedule(base_expedition, schedule).verify_schedule(ignore_land_test=True)


def test_verify_schedule_ports_only(base_expedition) -> None:
    """A schedule with only active Ports (no non-port waypoints) is valid."""
    schedule = Schedule(
        waypoints=[
            Port(location=Location(0, 0), time=datetime(2022, 1, 1, 0, 0, 0)),
            Port(location=Location(1, 0), time=datetime(2022, 1, 2, 0, 0, 0)),
        ]
    )
    _with_schedule(base_expedition, schedule).verify_schedule(ignore_land_test=True)

    assert schedule._verified, "Schedule with only active ports should be accepted."


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
            "Expedition includes instrument 'XBT', but instruments_config does not provide configuration for it.",
        ),
        (
            "ctd_config",
            "Expedition includes instrument 'CTD', but instruments_config does not provide configuration for it.",
        ),
        (
            "argo_float_config",
            "Expedition includes instrument 'ARGO_FLOAT', but instruments_config does not provide configuration for it.",
        ),
        (
            "drifter_config",
            "Expedition includes instrument 'DRIFTER', but instruments_config does not provide configuration for it.",
        ),
        (
            "adcp_config",
            r"Underway instrument config attribute\(s\) are missing from YAML\. Must be <Instrument>Config object or None\.",
        ),
        (
            "ship_underwater_st_config",
            r"Underway instrument config attribute\(s\) are missing from YAML\. Must be <Instrument>Config object or None\.",
        ),
    ]
)
def missing_instrument_config(request, expedition):
    attr_name, error_match = request.param
    delattr(expedition.instruments_config, attr_name)
    return expedition.instruments_config, error_match


def test_verify_instruments_config(expedition) -> None:
    expedition.verify_instruments_config()


def test_verify_instruments_config_no_instrument(expedition, expedition_no_xbt) -> None:
    expedition.instruments_config.verify(expedition_no_xbt.get_instruments())


def test_verify_instruments_config_errors(
    expedition, missing_instrument_config
) -> None:
    instruments_config, match = missing_instrument_config
    with pytest.raises(InstrumentsConfigError, match=match):
        instruments_config.verify(expedition.get_instruments())


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


def test_annotate_waypoint_number_comments(base_expedition) -> None:
    """Expedition._annotate() should provide one comment per waypoint, matching each waypoint's type (Port vs Waypoint) and number."""
    schedule = base_expedition.schedule
    annotated = base_expedition._annotate()

    comments = [line.strip() for line in annotated if line.strip().startswith("#")]

    expected = []
    waypoint_number = 0
    for wp_index, wp in enumerate(schedule.waypoints):
        if isinstance(wp, Port):
            arrival_departure = "Departure" if wp_index == 0 else "Arrival"
            expected.append(f"# Port of {arrival_departure}")
        else:
            waypoint_number += 1
            expected.append(f"# Waypoint {waypoint_number}")

    assert comments == expected


@pytest.mark.parametrize(
    "waypoints",
    [
        pytest.param(None, id="example_schedule_with_intervening_waypoints"),
        pytest.param(
            [
                Port(location=Location(0.0, 0.0), time=datetime(1998, 5, 1)),
                Port(location=Location(0.3, 0.0), time=datetime(1998, 5, 1, 3)),
            ],
            id="only_departure_and_arrival_ports",
        ),
    ],
)
def test_annotate_no_duplicate_comments(base_expedition, waypoints) -> None:
    """Expedition._annotate() should never produce the same comment twice. E.g. there should only be one Waypoint 1, one Port of Departure, etc."""
    schedule = (
        base_expedition.schedule if waypoints is None else Schedule(waypoints=waypoints)
    )
    expedition = Expedition(
        schedule=schedule,
        instruments_config=base_expedition.instruments_config,
        ship_config=base_expedition.ship_config,
    )

    annotated = expedition._annotate()
    comments = [line.strip() for line in annotated if line.strip().startswith("#")]

    assert len(set(comments)) == len(comments)


def test_sea_depth_only_written_when_known(tmp_path, base_expedition) -> None:
    """An unknown sea depth is left out of expedition.yaml entirely (rather than written as null), and a known one is kept."""
    known = Waypoint(
        location=Location(0, 0),
        time=datetime(2022, 1, 1),
        instrument=[InstrumentType.CTD],
        sea_depth_meter=-1500.0,
    )
    unknown = Waypoint(
        location=Location(0, 0.01),
        time=datetime(2022, 1, 2),
        instrument=[InstrumentType.CTD],
    )
    expedition = _with_schedule(
        base_expedition,
        Schedule(
            waypoints=[
                Port(location=None, time=None),
                known,
                unknown,
                Port(location=None, time=None),
            ]
        ),
    )

    out_path = tmp_path / EXPEDITION
    expedition.to_yaml(out_path)
    text = out_path.read_text()

    assert text.count("sea_depth_meter") == 1
    assert "sea_depth_meter: -1500.0" in text
    # ports' null location/time are still written, so placeholders remain visible
    assert "location: null" in text

    reloaded = Expedition.from_yaml(out_path)
    assert [wp.sea_depth_meter for wp in reloaded.schedule.waypoints[1:3]] == [
        -1500.0,
        None,
    ]


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


def test_wps_in_use_asymmetric_placeholder_ports():
    """Only the inactive side (departure and/or arrival) should be excluded, not both."""
    base_time = datetime.strptime("1950-01-01", "%Y-%m-%d")
    wp1 = Waypoint(location=Location(1, 1), time=base_time + timedelta(hours=1))
    active_arrival = Port(location=Location(2, 2), time=base_time + timedelta(hours=2))

    # inactive departure, active arrival
    schedule = Schedule(waypoints=[Port(location=None, time=None), wp1, active_arrival])
    wps_in_use = schedule._get_wps_in_use()
    assert wps_in_use == [wp1, active_arrival]

    # active departure, inactive arrival
    active_departure = Port(location=Location(0, 0), time=base_time)
    schedule = Schedule(
        waypoints=[active_departure, wp1, Port(location=None, time=None)]
    )
    wps_in_use = schedule._get_wps_in_use()
    assert wps_in_use == [active_departure, wp1]


@pytest.mark.parametrize(
    "location, time, expected",
    [
        (Location(0, 0), datetime(2024, 1, 1), True),
        (None, datetime(2024, 1, 1), False),
        (Location(0, 0), None, False),
        (None, None, False),
        (Location(None, None), datetime(2024, 1, 1), False),
    ],
)
def test_port_is_in_use(location, time, expected):
    """A Port is only 'in use' when it has both a fully-specified location and a time."""
    assert Port(location=location, time=time).is_in_use is expected
