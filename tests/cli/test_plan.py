import os
import shutil
import tempfile
from importlib.resources import files
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml
from textual.widgets import Button, Collapsible, Input

from virtualship.cli._plan import ConfigEditor, PlanApp, ScheduleEditor

NEW_SPEED = "8.0"
NEW_LAT = "0.05"
NEW_LON = "0.05"


async def simulate_input(pilot, box, new_value):
    """Simulate inputs to the UI."""
    box.focus()
    await pilot.pause()
    box.clear()
    await pilot.pause()
    for char in new_value:
        await pilot.press(char)
        await pilot.pause(0.05)


@pytest.mark.asyncio
async def test_UI_changes():
    """Test making changes to UI inputs and saving to YAML (simulated botton presses and typing inputs)."""
    tmpdir = Path(tempfile.mkdtemp())

    shutil.copy(
        files("virtualship.static").joinpath("ship_config.yaml"),
        tmpdir / "ship_config.yaml",
    )
    shutil.copy(
        files("virtualship.static").joinpath("schedule.yaml"),
        tmpdir / "schedule.yaml",
    )

    app = PlanApp(path=tmpdir)

    async with app.run_test(size=(120, 100)) as pilot:
        await pilot.pause(0.5)

        plan_screen = pilot.app.screen
        config_editor = plan_screen.query_one(ConfigEditor)
        schedule_editor = plan_screen.query_one(ScheduleEditor)

        # get mock of UI notify method
        plan_screen.notify = MagicMock()

        # change ship speed
        speed_collapsible = config_editor.query_one("#speed_collapsible", Collapsible)
        if speed_collapsible.collapsed:
            speed_collapsible.collapsed = False
            await pilot.pause()
        ship_speed_input = config_editor.query_one("#speed", Input)
        await simulate_input(pilot, ship_speed_input, NEW_SPEED)

        # change waypoint lat/lon (e.g. first waypoint)
        waypoints_collapsible = schedule_editor.query_one("#waypoints", Collapsible)
        if waypoints_collapsible.collapsed:
            waypoints_collapsible.collapsed = False
            await pilot.pause()
        wp_collapsible = waypoints_collapsible.query_one("#wp1", Collapsible)
        if wp_collapsible.collapsed:
            wp_collapsible.collapsed = False
            await pilot.pause()
        lat_input, lon_input = (
            wp_collapsible.query_one("#wp0_lat", Input),
            wp_collapsible.query_one("#wp0_lat", Input),
        )
        await simulate_input(pilot, lat_input, NEW_LAT)
        await simulate_input(pilot, lon_input, NEW_LON)

        # toggle CTD on first waypoint
        await pilot.click("#wp0_CTD")
        await pilot.pause(0.1)

        # toggle XBT on first waypoint
        await pilot.click("#wp0_XBT")
        await pilot.pause(0.1)

        # re-collapse widget editors to make save button visible on screen
        wp_collapsible.collapsed = True
        await pilot.pause()
        waypoints_collapsible.collapsed = True
        await pilot.pause()

        # press save button
        save_button = plan_screen.query_one("#save_button", Button)
        await pilot.click(save_button)
        await pilot.pause(0.5)

        # verify success notification received in UI (also useful for displaying potential debugging messages)
        plan_screen.notify.assert_called_once_with(
            "Changes saved successfully",
            severity="information",
            timeout=20,
        )

        # verify changes to speed, lat, lon in saved YAML
        ship_config_path = os.path.join(tmpdir, "ship_config.yaml")
        with open(ship_config_path) as f:
            saved_config = yaml.safe_load(f)

        assert saved_config["ship_speed_knots"] == float(NEW_SPEED)

        # check schedule.verify() methods are working by purposefully making invalid schedule (i.e. ship speed too slow to reach waypoints)
        invalid_speed = "0.0001"
        await simulate_input(pilot, ship_speed_input, invalid_speed)
        await pilot.click(save_button)
        await pilot.pause(0.5)

        args, _ = plan_screen.notify.call_args
        assert "*** Error saving changes ***" in args[0]

    # cleanup
    shutil.rmtree(tmpdir)
