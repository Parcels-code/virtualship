from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml
from textual.widgets import Button, Collapsible, Input, Switch

from virtualship.cli._plan import (
    ExpeditionEditor,
    PlanApp,
    QuitConfirmScreen,
    WaypointWidget,
    _default_sensors,
    parse_waypoint_time,
)
from virtualship.instruments.sensors import SensorType
from virtualship.instruments.types import InstrumentType
from virtualship.models import (
    CTDConfig,
    Expedition,
    InstrumentsConfig,
    Location,
    Schedule,
    SensorConfig,
    Waypoint,
)
from virtualship.models.expedition import Port
from virtualship.utils import EXPEDITION, _get_example_expedition

NEW_SPEED = "8.0"
NEW_LAT = "0.015"
NEW_LON = "0.015"

# TODO: new test that the check that there's Ports works


def _make_expedition(
    tmpdir: Path,
    waypoints: list,
    instruments_config=None,
) -> None:
    """Write a minimal expedition YAML."""
    if instruments_config is None:
        instruments_config = InstrumentsConfig.model_validate(
            yaml.safe_load(_get_example_expedition()).get("instruments_config")
        )
    ship_config = yaml.safe_load(_get_example_expedition()).get("ship_config")
    Expedition(
        schedule=Schedule(waypoints=waypoints),
        instruments_config=instruments_config,
        ship_config=ship_config,
    ).to_yaml(tmpdir / EXPEDITION)


async def simulate_input(pilot, box, new_value):
    """Simulate inputs to the UI."""
    box.focus()
    await pilot.pause()
    box.clear()
    await pilot.pause()
    for char in new_value:
        await pilot.press(char)
        await pilot.pause(0.05)


async def _expand_instrument_configs(
    expedition_editor, pilot, instrument_title: str | None = None
):
    """Expand the outer 'Instrument Configurations' collapsible and the instrument-specific inner one."""
    for coll in expedition_editor.query(Collapsible):
        if "Instrument Configurations" in (coll.title or ""):
            coll.collapsed = False
            await pilot.pause()
            break
    if instrument_title is not None:
        for coll in expedition_editor.query(Collapsible):
            if instrument_title in (coll.title or ""):
                coll.collapsed = False
                await pilot.pause()
                break


async def _expand_waypoint(expedition_editor, pilot, index: int) -> WaypointWidget:
    """Expand the waypoint editor."""
    waypoints_collapsible = expedition_editor.query_one("#waypoints", Collapsible)
    if waypoints_collapsible.collapsed:
        waypoints_collapsible.collapsed = False
        await pilot.pause()
    widget = expedition_editor.waypoint_widgets[index]
    widget.query_one(Collapsible).collapsed = False
    await pilot.pause()
    return widget


def _four_waypoint_schedule() -> list:
    return [
        Port(location=None, time=None),
        Waypoint(
            location=Location(0, 0),
            time=datetime(2022, 1, 1, 0, 0, 0),
            instrument=["CTD"],
        ),
        Waypoint(
            location=Location(0.01, 0.01),
            time=datetime(2022, 1, 1, 1, 0, 0),
            instrument=["CTD"],
        ),
        Waypoint(
            location=Location(0.02, 0.02),
            time=datetime(2022, 1, 1, 2, 0, 0),
            instrument=["CTD"],
        ),
        Port(location=None, time=None),
    ]


@pytest.mark.asyncio
async def test_UI_changes(tmp_path):
    """Test making changes to UI inputs and saving to YAML (simulated botton presses and typing inputs)."""
    waypoints = [
        Port(
            location=None,
            time=None,
        ),
        Waypoint(
            location=Location(0, 0),
            time=datetime(2022, 1, 1, 0, 0, 0),
            instrument=["CTD"],
        ),
        Waypoint(
            location=Location(0.01, 0.01),
            time=datetime(2022, 1, 1, 1, 0, 0),
            instrument=["CTD"],
        ),
        Waypoint(
            location=Location(0.02, 0.02),
            time=datetime(2022, 1, 1, 2, 0, 0),
            instrument=["CTD"],
        ),
        Port(
            location=None,
            time=None,
        ),
    ]
    _make_expedition(tmp_path, waypoints)

    app = PlanApp(path=tmp_path)

    async with app.run_test(size=(120, 100)) as pilot:
        await pilot.pause(0.5)

        plan_screen = pilot.app.screen
        expedition_editor = plan_screen.query_one(ExpeditionEditor)

        # get mock of UI notify method
        plan_screen.notify = MagicMock()

        # change ship speed
        speed_collapsible = expedition_editor.query_one(
            "#speed_collapsible", Collapsible
        )
        if speed_collapsible.collapsed:
            speed_collapsible.collapsed = False
            await pilot.pause()
        ship_speed_input = expedition_editor.query_one("#speed", Input)
        await simulate_input(pilot, ship_speed_input, NEW_SPEED)

        # change waypoint lat/lon (second waypoint)
        waypoints_collapsible = expedition_editor.query_one("#waypoints", Collapsible)
        if waypoints_collapsible.collapsed:
            waypoints_collapsible.collapsed = False
            await pilot.pause()
        wp2 = await _expand_waypoint(expedition_editor, pilot, 2)
        lat_input, lon_input = (
            wp2.query_one("#lat", Input),
            wp2.query_one("#lon", Input),
        )
        await simulate_input(pilot, lat_input, NEW_LAT)
        await simulate_input(pilot, lon_input, NEW_LON)

        # toggle CTD and XBT on first waypoint
        wp1 = await _expand_waypoint(expedition_editor, pilot, 1)
        wp1.query_one("#CTD", Switch).toggle()
        await pilot.pause(0.1)
        wp1.query_one("#XBT", Switch).toggle()
        await pilot.pause(0.1)

        # re-collapse widget editors to make save button visible on screen
        waypoints_collapsible.collapsed = True
        await pilot.pause()

        # press save button
        save_button = plan_screen.query_one("#save_button", Button)
        await pilot.click(save_button)
        await pilot.pause(0.5)

        # verify success notification received in UI (also useful for displaying potential debugging messages)
        calls = plan_screen.notify.call_args_list
        assert any(
            call[0][0] == "Changes saved successfully"
            and call[1].get("severity") == "information"
            for call in calls
        )

        # verify changes to speed, lat, lon in saved YAML
        with open(tmp_path / EXPEDITION) as f:
            saved_expedition = yaml.safe_load(f)

        assert saved_expedition["ship_config"]["ship_speed_knots"] == float(NEW_SPEED)

        saved_wps = Expedition.from_yaml(tmp_path / EXPEDITION).schedule.waypoints
        assert saved_wps[2].location.lat == float(NEW_LAT)
        assert saved_wps[2].location.lon == float(NEW_LON)
        assert saved_wps[1].instrument == [InstrumentType.XBT]

        # check schedule.verify() methods are working by purposefully making invalid schedule (i.e. ship speed too slow to reach waypoints)
        invalid_speed = "0.0001"
        await simulate_input(pilot, ship_speed_input, invalid_speed)
        await pilot.click(save_button)
        await pilot.pause(0.5)

        args, _ = plan_screen.notify.call_args
        assert "*** Error saving changes ***" in args[0]


@pytest.mark.asyncio
async def test_UI_opens_with_null_time_and_instrument(tmp_path):
    """Test that the UI opens correctly when waypoints have time: null and instrument: null."""
    waypoints = [
        Port(location=None, time=None),
        Waypoint(
            location=Location(0, 0),
            time=datetime(2022, 1, 1, 0, 0, 0),
            instrument=["CTD"],
        ),
        Waypoint(location=Location(0.01, 0.01), time=None, instrument=None),
        Waypoint(location=Location(0.02, 0.02), time=None, instrument=None),
        Port(location=None, time=None),
    ]
    _make_expedition(tmp_path, waypoints)

    app = PlanApp(path=tmp_path)

    async with app.run_test(size=(120, 100)) as pilot:
        await pilot.pause(0.5)

        plan_screen = pilot.app.screen
        expedition_editor = plan_screen.query_one(ExpeditionEditor)

        # verify the app opened without errors by checking the editor loaded
        assert expedition_editor is not None


def test_default_sensors_returns_declared_defaults():
    """_default_sensors() should mirror the config class's default sensor list."""
    ctd_sensors = _default_sensors(CTDConfig)
    types = {sc.sensor_type for sc in ctd_sensors}
    assert SensorType.TEMPERATURE in types
    assert SensorType.SALINITY in types


@pytest.mark.asyncio
async def test_sensor_toggle_saved_to_yaml(tmp_path):
    """Toggling a sensor switch off and saving should persist only the enabled sensors."""
    _make_expedition(
        tmp_path,
        [
            Port(location=None, time=None),
            Waypoint(
                location=Location(0, 0),
                time=datetime(2022, 1, 1, 0, 0, 0),
                instrument=["CTD"],
            ),
            Waypoint(
                location=Location(0.01, 0.01),
                time=datetime(2022, 1, 1, 1, 0, 0),
                instrument=None,
            ),
            Port(location=None, time=None),
        ],
    )

    app = PlanApp(path=tmp_path)
    async with app.run_test(size=(160, 120)) as pilot:
        await pilot.pause(0.5)
        plan_screen = pilot.app.screen
        plan_screen.notify = MagicMock()
        expedition_editor = plan_screen.query_one(ExpeditionEditor)
        await _expand_instrument_configs(expedition_editor, pilot, "CTD")

        # turn off SALINITY on CTD
        sal_switch = expedition_editor.query_one("#ctd_config_sensor_SALINITY", Switch)
        await pilot.click(sal_switch)
        await pilot.pause(0.2)

        await pilot.click(plan_screen.query_one("#save_button", Button))
        await pilot.pause(0.5)

        calls = plan_screen.notify.call_args_list
        assert any(
            call[0][0] == "Changes saved successfully"
            and call[1].get("severity") == "information"
            for call in calls
        )

    with open(tmp_path / EXPEDITION) as f:
        saved = yaml.safe_load(f)
    saved_sensors = saved["instruments_config"]["ctd_config"]["sensors"]
    assert "SALINITY" not in saved_sensors
    assert "TEMPERATURE" in saved_sensors


@pytest.mark.asyncio
async def test_deselecting_all_sensors_on_active_instrument_blocks_save(tmp_path):
    """Removing all sensors from an instrument used in the schedule should show an error."""
    _make_expedition(
        tmp_path,
        [
            Port(location=None, time=None),
            Waypoint(
                location=Location(0, 0),
                time=datetime(2022, 1, 1, 0, 0, 0),
                instrument=["XBT"],
            ),
            Waypoint(
                location=Location(0.01, 0.01),
                time=datetime(2022, 1, 1, 1, 0, 0),
                instrument=None,
            ),
            Port(location=None, time=None),
        ],
    )

    app = PlanApp(path=tmp_path)
    async with app.run_test(size=(160, 120)) as pilot:
        await pilot.pause(0.5)
        plan_screen = pilot.app.screen
        plan_screen.notify = MagicMock()
        expedition_editor = plan_screen.query_one(ExpeditionEditor)
        await _expand_instrument_configs(expedition_editor, pilot, "XBT")

        # XBT only has TEMPERATURE, deselect it
        temp_switch = expedition_editor.query_one(
            "#xbt_config_sensor_TEMPERATURE", Switch
        )
        await pilot.click(temp_switch)
        await pilot.pause(0.2)

        await pilot.click(plan_screen.query_one("#save_button", Button))
        await pilot.pause(0.5)

        args, _ = plan_screen.notify.call_args
        assert "*** Error saving changes ***" in args[0]
        assert "XBT" in args[0]


@pytest.mark.asyncio
async def test_deselecting_all_sensors_on_inactive_instrument(tmp_path):
    """Removing all sensors from an instrument NOT in the schedule should not block saving."""
    # only CTD waypoints, XBT is inactive
    _make_expedition(
        tmp_path,
        [
            Port(location=None, time=None),
            Waypoint(
                location=Location(0, 0),
                time=datetime(2022, 1, 1, 0, 0, 0),
                instrument=["CTD"],
            ),
            Waypoint(
                location=Location(0.01, 0.01),
                time=datetime(2022, 1, 1, 1, 0, 0),
                instrument=None,
            ),
            Port(location=None, time=None),
        ],
    )

    app = PlanApp(path=tmp_path)
    async with app.run_test(size=(160, 120)) as pilot:
        await pilot.pause(0.5)
        plan_screen = pilot.app.screen
        plan_screen.notify = MagicMock()
        expedition_editor = plan_screen.query_one(ExpeditionEditor)
        await _expand_instrument_configs(expedition_editor, pilot, "XBT")

        # deselect XBT's only sensor even though XBT is not in the schedule
        temp_switch = expedition_editor.query_one(
            "#xbt_config_sensor_TEMPERATURE", Switch
        )
        await pilot.click(temp_switch)
        await pilot.pause(0.2)

        await pilot.click(plan_screen.query_one("#save_button", Button))
        await pilot.pause(0.5)

        calls = plan_screen.notify.call_args_list
        assert any(
            call[0][0] == "Changes saved successfully"
            and call[1].get("severity") == "information"
            for call in calls
        )


@pytest.mark.asyncio
async def test_sensor_initial_state_reflects_config(tmp_path):
    """Sensor switches should reflect the enabled sensors already stored in the config."""
    ctd_config = CTDConfig(
        stationkeeping_time_minutes=50,
        min_depth_meter=-11.0,
        max_depth_meter=-2000.0,
        sensors=[SensorConfig(sensor_type=SensorType.TEMPERATURE)],
    )
    instruments_config = InstrumentsConfig.model_validate(
        yaml.safe_load(_get_example_expedition()).get("instruments_config")
    )
    instruments_config.ctd_config = ctd_config
    _make_expedition(
        tmp_path,
        [
            Port(location=None, time=None),
            Waypoint(
                location=Location(0, 0),
                time=datetime(2022, 1, 1, 0, 0, 0),
                instrument=["CTD"],
            ),
            Waypoint(
                location=Location(0.01, 0.01),
                time=datetime(2022, 1, 1, 1, 0, 0),
                instrument=None,
            ),
            Port(location=None, time=None),
        ],
        instruments_config,
    )

    app = PlanApp(path=tmp_path)
    async with app.run_test(size=(160, 120)) as pilot:
        await pilot.pause(0.5)
        expedition_editor = pilot.app.screen.query_one(ExpeditionEditor)

        temp_switch = expedition_editor.query_one(
            "#ctd_config_sensor_TEMPERATURE", Switch
        )
        sal_switch = expedition_editor.query_one("#ctd_config_sensor_SALINITY", Switch)
        assert temp_switch.value is True, "TEMPERATURE should be ON"
        assert sal_switch.value is False, "SALINITY should be OFF (not in saved config)"


@pytest.mark.asyncio
async def test_adcp_type_always_exactly_one_selected(tmp_path):
    """Switching one ADCP type off selects the other, so both can never be off/on together."""
    _make_expedition(tmp_path, _four_waypoint_schedule())

    app = PlanApp(path=tmp_path)
    async with app.run_test(size=(120, 100)) as pilot:
        await pilot.pause(0.5)
        plan_screen = pilot.app.screen
        plan_screen.notify = MagicMock()
        expedition_editor = plan_screen.query_one(ExpeditionEditor)
        deep = expedition_editor.query_one("#adcp_deep", Switch)
        shallow = expedition_editor.query_one("#adcp_shallow", Switch)
        assert expedition_editor.query_one("#has_adcp", Switch).value

        for switch in (deep, shallow, deep, shallow):
            switch.value = not switch.value
            await pilot.pause()
            assert deep.value != shallow.value

        # whichever is selected is what gets saved
        await plan_screen.run_action("save")
        await pilot.pause(0.5)
        saved = Expedition.from_yaml(tmp_path / EXPEDITION)
        expected = -1000.0 if deep.value else -150.0
        assert saved.instruments_config.adcp_config.max_depth_meter == expected


@pytest.mark.asyncio
async def test_collapse_all(tmp_path):
    """The collapse-all button and Escape collapse every section and waypoint."""
    _make_expedition(tmp_path, _four_waypoint_schedule())

    app = PlanApp(path=tmp_path)
    async with app.run_test(size=(120, 100)) as pilot:
        await pilot.pause(0.5)
        plan_screen = pilot.app.screen
        expedition_editor = plan_screen.query_one(ExpeditionEditor)

        for trigger in ("button", "escape"):
            await _expand_instrument_configs(expedition_editor, pilot, "CTD")
            await _expand_waypoint(expedition_editor, pilot, 1)
            await _expand_waypoint(expedition_editor, pilot, 2)
            assert any(not c.collapsed for c in plan_screen.query(Collapsible))

            if trigger == "button":
                plan_screen.query_one("#collapse_all_button", Button).press()
            else:
                await pilot.press("escape")
            await pilot.pause()
            assert all(c.collapsed for c in plan_screen.query(Collapsible))


def test_parse_waypoint_time():
    assert parse_waypoint_time("") is None
    assert parse_waypoint_time("2023-06-15 10:30") == datetime(2023, 6, 15, 10, 30)
    for invalid in ("2023-06-", "2023-02-30 10:00", "2023-06-15 25:00"):
        with pytest.raises(ValueError):
            parse_waypoint_time(invalid)


@pytest.mark.asyncio
async def test_waypoint_controls_built_lazily(tmp_path):
    """Waypoint controls are only built when a waypoint is first expanded."""
    _make_expedition(tmp_path, _four_waypoint_schedule())

    app = PlanApp(path=tmp_path)
    async with app.run_test(size=(120, 100)) as pilot:
        await pilot.pause(0.5)
        expedition_editor = pilot.app.screen.query_one(ExpeditionEditor)

        widgets = expedition_editor.waypoint_widgets
        assert len(widgets) == 5
        assert all(w.body is None for w in widgets)
        assert not list(expedition_editor.query("#lat"))

        wp2 = await _expand_waypoint(expedition_editor, pilot, 2)
        assert wp2.body is not None
        assert wp2.query_one("#lat", Input).value == "0.01"
        assert wp2.query_one("#time", Input).value == "2022-01-01 01:00"
        assert sum(w.body is not None for w in expedition_editor.waypoint_widgets) == 1


@pytest.mark.asyncio
async def test_add_and_remove_waypoints_renumber(tmp_path):
    """Adding/removing waypoints updates the schedule and renumbers titles without rebuilding the others."""
    _make_expedition(tmp_path, _four_waypoint_schedule())

    app = PlanApp(path=tmp_path)
    async with app.run_test(size=(120, 100)) as pilot:
        await pilot.pause(0.5)
        plan_screen = pilot.app.screen
        expedition_editor = plan_screen.query_one(ExpeditionEditor)
        schedule = expedition_editor.expedition.schedule

        # an expanded waypoint keeps its controls through add/remove
        wp3 = await _expand_waypoint(expedition_editor, pilot, 3)

        await expedition_editor.add_waypoint()
        await pilot.pause()
        titles = [w.get_title() for w in expedition_editor.waypoint_widgets]
        assert titles == [
            "Port of Departure",
            "Waypoint 1",
            "Waypoint 2",
            "Waypoint 3",
            "Waypoint 4",
            "Port of Arrival",
        ]
        assert len(schedule.waypoints) == 6
        # new waypoint copies the last waypoint's time, just before the arrival port
        assert schedule.waypoints[4].time == datetime(2022, 1, 1, 2, 0, 0)

        # remove waypoint 1 via its remove button, confirming in the dialog
        wp1 = await _expand_waypoint(expedition_editor, pilot, 1)
        wp1.query_one("#remove", Button).press()
        await pilot.pause()
        await pilot.click("#confirm-yes")
        await pilot.pause()

        widgets = expedition_editor.waypoint_widgets
        assert len(widgets) == 5
        assert len(schedule.waypoints) == 5
        assert [w.get_title() for w in widgets][1:4] == [
            "Waypoint 1",
            "Waypoint 2",
            "Waypoint 3",
        ]
        # the previously-expanded waypoint 3 is now waypoint 2, with the same controls
        assert widgets[2] is wp3
        assert wp3.query_one(Collapsible).title == "Waypoint 2"
        assert schedule.waypoints[1].location.lat == 0.01

        # remove last waypoint
        await expedition_editor.remove_waypoint()
        await pilot.pause()
        assert len(schedule.waypoints) == 4

        # reset restores the schedule as loaded
        await expedition_editor.reset_changes()
        await pilot.pause()
        assert len(expedition_editor.waypoint_widgets) == 5
        assert expedition_editor.expedition.schedule.waypoints[1].location.lat == 0.0


@pytest.mark.asyncio
async def test_waypoint_time_entry_and_adjust(tmp_path):
    """Typed times and the +/- buttons update the waypoint, and invalid times block saving."""
    _make_expedition(tmp_path, _four_waypoint_schedule())

    app = PlanApp(path=tmp_path)
    async with app.run_test(size=(120, 100)) as pilot:
        await pilot.pause(0.5)
        plan_screen = pilot.app.screen
        plan_screen.notify = MagicMock()
        expedition_editor = plan_screen.query_one(ExpeditionEditor)
        wp = expedition_editor.expedition.schedule.waypoints

        wp3 = await _expand_waypoint(expedition_editor, pilot, 3)
        time_input = wp3.query_one("#time", Input)
        await simulate_input(pilot, time_input, "202201011015")
        await pilot.pause()
        assert time_input.value == "2022-01-01 10:15"
        assert wp[3].time == datetime(2022, 1, 1, 10, 15)

        wp3.query_one("#plus_one_hour", Button).press()
        await pilot.pause()
        wp3.query_one("#minus_thirty_minutes", Button).press()
        await pilot.pause()
        assert time_input.value == "2022-01-01 10:45"
        assert wp[3].time == datetime(2022, 1, 1, 10, 45)

        # a non-existent date is flagged and blocks saving
        await simulate_input(pilot, time_input, "202202301000")
        await pilot.pause()
        assert "time" in wp3.errors
        await plan_screen.run_action("save")
        await pilot.pause()
        args, _ = plan_screen.notify.call_args
        assert "*** Error saving changes ***" in args[0]
        assert "Waypoint 3" in args[0]

        # copy from previous copies time and instruments, not location
        wp[2].instrument = [InstrumentType.XBT]
        wp3.query_one("#copy", Button).press()
        await pilot.pause()
        assert time_input.value == "2022-01-01 01:00"
        assert wp[3].time == datetime(2022, 1, 1, 1, 0)
        assert wp[3].instrument == [InstrumentType.XBT]
        assert wp3.query_one("#XBT", Switch).value is True
        assert wp[3].location.lat == 0.02
        assert not wp3.errors


@pytest.mark.asyncio
async def test_save_shortcut_and_unsaved_changes_prompt(tmp_path):
    """ctrl+s saves, quitting with unsaved changes asks first, quitting after saving does not."""
    _make_expedition(tmp_path, _four_waypoint_schedule())

    app = PlanApp(path=tmp_path)
    async with app.run_test(size=(120, 100)) as pilot:
        await pilot.pause(0.5)
        plan_screen = pilot.app.screen
        plan_screen.notify = MagicMock()
        expedition_editor = plan_screen.query_one(ExpeditionEditor)

        # opening/expanding alone is not an unsaved change
        await _expand_waypoint(expedition_editor, pilot, 1)
        assert not expedition_editor.has_unsaved_changes()

        wp1 = expedition_editor.waypoint_widgets[1]
        await simulate_input(pilot, wp1.query_one("#lat", Input), "0.005")
        await pilot.pause()
        assert expedition_editor.has_unsaved_changes()

        await pilot.press("ctrl+q")
        await pilot.pause()
        assert isinstance(pilot.app.screen, QuitConfirmScreen)
        await pilot.click("#confirm-no")
        await pilot.pause()
        assert pilot.app.screen is plan_screen

        await pilot.press("ctrl+s")
        await pilot.pause(0.5)
        assert any(
            call[0][0] == "Changes saved successfully"
            for call in plan_screen.notify.call_args_list
        )
        assert not expedition_editor.has_unsaved_changes()
        saved = Expedition.from_yaml(tmp_path / EXPEDITION)
        assert saved.schedule.waypoints[1].location.lat == 0.005

        # a ship/instrument config edit also counts as unsaved
        await simulate_input(pilot, expedition_editor.query_one("#speed", Input), "9.0")
        assert expedition_editor.has_unsaved_changes()
