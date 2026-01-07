import datetime
import os
import traceback

from textual import on
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.dom import NoMatches
from textual.screen import Screen
from textual.validation import Function, Integer
from textual.widgets import (
    Button,
    Collapsible,
    Input,
    Label,
    Rule,
    Select,
    Static,
    Switch,
)

from virtualship.cli.validator_utils import (
    get_field_type,
    group_validators,
    is_valid_lat,
    is_valid_lon,
    type_to_textual,
)
from virtualship.errors import UnexpectedError, UserError
from virtualship.instruments.types import InstrumentType
from virtualship.models import (
    ADCPConfig,
    ArgoFloatConfig,
    CTD_BGCConfig,
    CTDConfig,
    DrifterConfig,
    Expedition,
    Location,
    ShipConfig,
    ShipUnderwaterSTConfig,
    Waypoint,
    XBTConfig,
)
from virtualship.utils import EXPEDITION, _get_waypoint_latlons

UNEXPECTED_MSG_ONSAVE = (
    "Please ensure that:\n"
    "\n1) All typed entries are valid (all boxes in all sections must have green borders and no warnings).\n"
    "\n2) Complete time selections (YYYY-MM-DD hh:mm) exist for all waypoints.\n"
    "\nIf the problem persists, please report this issue, with a description and the traceback, "
    "to the VirtualShip issue tracker at: https://github.com/OceanParcels/virtualship/issues"
)


def unexpected_msg_compose(e):
    return (
        f"\n\nUNEXPECTED ERROR:\n\n{e}"
        "\n\nPlease report this issue, with a description and the traceback, "
        "to the VirtualShip issue tracker at: https://github.com/OceanParcels/virtualship/issues"
    )


def log_exception_to_file(
    exception: Exception,
    path: str,
    filename: str = "virtualship_error.txt",
    context_message: str = "Error occurred:",
):
    """Log an exception and its traceback to a file."""
    error_log_path = os.path.join(path, filename)
    with open(error_log_path, "w") as f:
        f.write(f"{context_message}\n")
        traceback.print_exception(
            type(exception), exception, exception.__traceback__, file=f, chain=True
        )
        f.write("\n")


DEFAULT_TS_CONFIG = {"period_minutes": 5.0}

DEFAULT_ADCP_CONFIG = {
    "num_bins": 40,
    "period_minutes": 5.0,
}

INSTRUMENT_FIELDS = {
    "adcp_config": {
        "class": ADCPConfig,
        "title": "Onboard ADCP",
        "attributes": [
            {"name": "num_bins"},
            {"name": "period", "minutes": True},
        ],
    },
    "ship_underwater_st_config": {
        "class": ShipUnderwaterSTConfig,
        "title": "Onboard Temperature/Salinity",
        "attributes": [
            {"name": "period", "minutes": True},
        ],
    },
    "ctd_config": {
        "class": CTDConfig,
        "title": "CTD",
        "attributes": [
            {"name": "max_depth_meter"},
            {"name": "min_depth_meter"},
            {"name": "stationkeeping_time", "minutes": True},
        ],
    },
    "ctd_bgc_config": {
        "class": CTD_BGCConfig,
        "title": "CTD-BGC",
        "attributes": [
            {"name": "max_depth_meter"},
            {"name": "min_depth_meter"},
            {"name": "stationkeeping_time", "minutes": True},
        ],
    },
    "xbt_config": {
        "class": XBTConfig,
        "title": "XBT",
        "attributes": [
            {"name": "min_depth_meter"},
            {"name": "max_depth_meter"},
            {"name": "fall_speed_meter_per_second"},
            {"name": "deceleration_coefficient"},
        ],
    },
    "argo_float_config": {
        "class": ArgoFloatConfig,
        "title": "Argo Float",
        "attributes": [
            {"name": "min_depth_meter"},
            {"name": "max_depth_meter"},
            {"name": "drift_depth_meter"},
            {"name": "vertical_speed_meter_per_second"},
            {"name": "cycle_days"},
            {"name": "drift_days"},
            {"name": "stationkeeping_time", "minutes": True},
            {"name": "lifetime", "days": True},
        ],
    },
    "drifter_config": {
        "class": DrifterConfig,
        "title": "Drifter",
        "attributes": [
            {"name": "depth_meter"},
            {"name": "lifetime", "days": True},
            {"name": "stationkeeping_time", "minutes": True},
        ],
    },
}


class ExpeditionEditor(Static):
    def __init__(self, path: str):
        super().__init__()
        self.path = path
        self.expedition = None

    def compose(self) -> ComposeResult:
        try:
            self.expedition = Expedition.from_yaml(self.path.joinpath(EXPEDITION))
        except Exception as e:
            raise UserError(
                f"There is an issue in {self.path.joinpath(EXPEDITION)}:\n\n{e}"
            ) from None

        try:
            ## 1) SHIP SPEED & INSTRUMENTS CONFIG EDITOR

            yield Label(
                "[b]Ship & Instruments Config Editor[/b]",
                id="title_ship_instruments_config",
                markup=True,
            )
            yield Rule(line_style="heavy")

            # SECTION: "Ship Speed & Onboard Measurements"

            with Collapsible(
                title="[b]Ship Speed & Onboard Measurements[/b]",
                id="speed_collapsible",
                collapsed=False,
            ):
                attr = "ship_speed_knots"
                validators = group_validators(ShipConfig, attr)
                with Horizontal(classes="ship_speed"):
                    yield Label("[b]Ship Speed (knots):[/b]")
                    yield Input(
                        id="speed",
                        type=type_to_textual(get_field_type(ShipConfig, attr)),
                        validators=[
                            Function(
                                validator,
                                f"INVALID: value must be {validator.__doc__.lower()}",
                            )
                            for validator in validators
                        ],
                        classes="ship_speed_input",
                        placeholder="knots",
                        value=str(
                            self.expedition.ship_config.ship_speed_knots
                            if self.expedition.ship_config.ship_speed_knots
                            else ""
                        ),
                    )
                yield Label("", id="validation-failure-label-speed", classes="-hidden")

                with Horizontal(classes="ts-section"):
                    yield Label("[b]Onboard Temperature/Salinity:[/b]")
                    yield Switch(
                        value=bool(
                            self.expedition.instruments_config.ship_underwater_st_config
                        ),
                        id="has_onboard_ts",
                    )

                with Horizontal(classes="adcp-section"):
                    yield Label("[b]Onboard ADCP:[/b]")
                    yield Switch(
                        value=bool(self.expedition.instruments_config.adcp_config),
                        id="has_adcp",
                    )

                # adcp type selection
                with Horizontal(id="adcp_type_container", classes="-hidden"):
                    is_deep = (
                        self.expedition.instruments_config.adcp_config
                        and self.expedition.instruments_config.adcp_config.max_depth_meter
                        == -1000.0
                    )
                    yield Label("       OceanObserver:")
                    yield Switch(value=is_deep, id="adcp_deep")
                    yield Label("   SeaSeven:")
                    yield Switch(value=not is_deep, id="adcp_shallow")
                    yield Button("?", id="info_button", variant="warning")

            ## SECTION: "Instrument Configurations""

            with Collapsible(
                title="[b]Instrument Configurations[/b] (advanced users only)",
                collapsed=True,
            ):
                for instrument_name, info in INSTRUMENT_FIELDS.items():
                    config_class = info["class"]
                    attributes = info["attributes"]
                    config_instance = getattr(
                        self.expedition.instruments_config, instrument_name, None
                    )
                    title = info.get("title", instrument_name.replace("_", " ").title())
                    with Collapsible(
                        title=f"[b]{title}[/b]",
                        collapsed=True,
                    ):
                        if instrument_name in (
                            "adcp_config",
                            "ship_underwater_st_config",
                        ):
                            yield Label(
                                f"NOTE: entries will be ignored here if {info['title']} is OFF in Ship Speed & Onboard Measurements."
                            )
                        with Container(classes="instrument-config"):
                            for attr_meta in attributes:
                                attr = attr_meta["name"]
                                is_minutes, is_days = (
                                    attr_meta.get("minutes", False),
                                    attr_meta.get("days", False),
                                )
                                validators = group_validators(config_class, attr)
                                if config_instance:
                                    raw_value = getattr(config_instance, attr, "")
                                    if is_minutes and raw_value != "":
                                        try:
                                            value = str(
                                                raw_value.total_seconds() / 60.0
                                            )
                                        except AttributeError:
                                            value = str(raw_value)
                                    elif is_days and raw_value != "":
                                        try:
                                            value = str(
                                                raw_value.total_seconds() / 86400.0
                                            )
                                        except AttributeError:
                                            value = str(raw_value)
                                    else:
                                        value = str(raw_value)
                                else:
                                    value = ""
                                label = f"{attr.replace('_', ' ').title()}:"
                                if is_minutes:
                                    label = label.replace(":", " Minutes:")
                                elif is_days:
                                    label = label.replace(":", " Days:")
                                yield Label(label)
                                yield Input(
                                    id=f"{instrument_name}_{attr}",
                                    type=type_to_textual(
                                        get_field_type(config_class, attr)
                                    ),
                                    validators=[
                                        Function(
                                            validator,
                                            f"INVALID: value must be {validator.__doc__.lower()}",
                                        )
                                        for validator in validators
                                    ],
                                    value=value,
                                )
                                yield Label(
                                    "",
                                    id=f"validation-failure-label-{instrument_name}_{attr}",
                                    classes="-hidden validation-failure",
                                )

            ## 2) SCHEDULE EDITOR

            yield Label("[b]Schedule Editor[/b]", id="title_schedule", markup=True)
            yield Rule(line_style="heavy")

            # SECTION: "Waypoints & Instrument Selection"
            with Collapsible(
                title="[b]Waypoints & Instrument Selection[/b]",
                id="waypoints",
                collapsed=True,
            ):
                yield Horizontal(
                    Button("Add Waypoint", id="add_waypoint", variant="primary"),
                    Button(
                        "Remove Last Waypoint",
                        id="remove_waypoint",
                        variant="error",
                    ),
                )

                yield VerticalScroll(id="waypoint_list", classes="waypoint-list")

        except Exception as e:
            raise UnexpectedError(unexpected_msg_compose(e)) from None

    def on_mount(self) -> None:
        self.refresh_waypoint_widgets()
        adcp_present = (
            getattr(self.expedition.instruments_config, "adcp_config", None)
            if self.expedition.instruments_config
            else False
        )
        self.show_hide_adcp_type(bool(adcp_present))

    def refresh_waypoint_widgets(self):
        waypoint_list = self.query_one("#waypoint_list", VerticalScroll)
        waypoint_list.remove_children()
        for i, waypoint in enumerate(self.expedition.schedule.waypoints):
            waypoint_list.mount(WaypointWidget(waypoint, i))

    def save_changes(self) -> bool:
        """Save changes to expedition.yaml."""
        try:
            self._update_ship_speed()
            self._update_instrument_configs()
            self._update_schedule()
            self.expedition.to_yaml(self.path.joinpath(EXPEDITION))
            return True
        except Exception as e:
            log_exception_to_file(
                e,
                self.path,
                context_message=f"Error saving {self.path.joinpath(EXPEDITION)}:",
            )
            raise UnexpectedError(
                UNEXPECTED_MSG_ONSAVE
                + f"\n\nTraceback will be logged in {self.path}/virtualship_error.txt. Please attach this/copy the contents to any issue submitted."
            ) from None

    def _update_ship_speed(self):
        attr = "ship_speed_knots"
        field_type = get_field_type(type(self.expedition.ship_config), attr)
        value = field_type(self.query_one("#speed").value)
        ShipConfig.model_validate(
            {**self.expedition.ship_config.model_dump(), attr: value}
        )
        self.expedition.ship_config.ship_speed_knots = value

    def _update_instrument_configs(self):
        for instrument_name, info in INSTRUMENT_FIELDS.items():
            config_class = info["class"]
            attributes = info["attributes"]
            kwargs = {}
            # special handling for onboard ADCP and T/S
            if instrument_name == "adcp_config":
                has_adcp = self.query_one("#has_adcp", Switch).value
                if not has_adcp:
                    setattr(self.expedition.instruments_config, instrument_name, None)
                    continue
            if instrument_name == "ship_underwater_st_config":
                has_ts = self.query_one("#has_onboard_ts", Switch).value
                if not has_ts:
                    setattr(self.expedition.instruments_config, instrument_name, None)
                    continue
            for attr_meta in attributes:
                attr = attr_meta["name"]
                is_minutes = attr_meta.get("minutes", False)
                is_days = attr_meta.get("days", False)
                input_id = f"{instrument_name}_{attr}"
                value = self.query_one(f"#{input_id}").value
                field_type = get_field_type(config_class, attr)
                if is_minutes and field_type is datetime.timedelta:
                    value = datetime.timedelta(minutes=float(value))
                elif is_days and field_type is datetime.timedelta:
                    value = datetime.timedelta(days=float(value))
                else:
                    value = field_type(value)
                kwargs[attr] = value
            # ADCP max_depth_meter based on deep/shallow switch
            if instrument_name == "adcp_config":
                if self.query_one("#adcp_deep", Switch).value:
                    kwargs["max_depth_meter"] = -1000.0
                else:
                    kwargs["max_depth_meter"] = -150.0
            setattr(
                self.expedition.instruments_config,
                instrument_name,
                config_class(**kwargs),
            )

    def _update_schedule(self):
        for i, wp in enumerate(self.expedition.schedule.waypoints):
            wp.location = Location(
                latitude=float(self.query_one(f"#wp{i}_lat").value),
                longitude=float(self.query_one(f"#wp{i}_lon").value),
            )
            wp.time = datetime.datetime(
                int(self.query_one(f"#wp{i}_year").value),
                int(self.query_one(f"#wp{i}_month").value),
                int(self.query_one(f"#wp{i}_day").value),
                int(self.query_one(f"#wp{i}_hour").value),
                int(self.query_one(f"#wp{i}_minute").value),
                0,
            )
            wp.instrument = []
            for instrument in [inst for inst in InstrumentType if not inst.is_underway]:
                switch_on = self.query_one(f"#wp{i}_{instrument.value}").value
                if instrument.value == "DRIFTER" and switch_on:
                    count_str = self.query_one(f"#wp{i}_drifter_count").value
                    count = int(count_str)
                    assert count > 0
                    wp.instrument.extend([InstrumentType.DRIFTER] * count)
                elif switch_on:
                    wp.instrument.append(instrument)

    @on(Input.Changed)
    def show_invalid_reasons(self, event: Input.Changed) -> None:
        input_id = event.input.id
        label_id = f"validation-failure-label-{input_id}"

        # avoid errors when button pressed too rapidly
        try:
            label = self.query_one(f"#{label_id}", Label)
        except NoMatches:
            return

        if input_id.endswith("_drifter_count"):
            wp_index = int(input_id.split("_")[0][2:])
            drifter_switch = self.query_one(f"#wp{wp_index}_DRIFTER")
            if not drifter_switch.value:
                label.update("")
                label.add_class("-hidden")
                label.remove_class("validation-failure")
                event.input.remove_class("-valid")
                event.input.remove_class("-invalid")
                return
        if not event.validation_result.is_valid:
            message = (
                "\n".join(event.validation_result.failure_descriptions)
                if isinstance(event.validation_result.failure_descriptions, list)
                else str(event.validation_result.failure_descriptions)
            )
            label.update(message)
            label.remove_class("-hidden")
            label.add_class("validation-failure")
        else:
            label.update("")
            label.add_class("-hidden")
            label.remove_class("validation-failure")

    @on(Button.Pressed, "#add_waypoint")
    def add_waypoint(self) -> None:
        """Add a new waypoint to the schedule. Copies time from last waypoint if possible (Lat/lon and instruments blank)."""
        try:
            if self.expedition.schedule.waypoints:
                last_wp = self.expedition.schedule.waypoints[-1]
                new_time = last_wp.time if last_wp.time else None
                new_wp = Waypoint(
                    location=Location(
                        latitude=0.0,
                        longitude=0.0,
                    ),
                    time=new_time,
                    instrument=[],
                )
            else:
                new_wp = Waypoint(
                    location=Location(latitude=0.0, longitude=0.0),
                    time=None,
                    instrument=[],
                )
            self.expedition.schedule.waypoints.append(new_wp)
            self.refresh_waypoint_widgets()

        except Exception as e:
            raise UnexpectedError(unexpected_msg_compose(e)) from None

    @on(Button.Pressed, "#remove_waypoint")
    def remove_waypoint(self) -> None:
        """Remove the last waypoint from the schedule."""
        try:
            if self.expedition.schedule.waypoints:
                self.expedition.schedule.waypoints.pop()
                self.refresh_waypoint_widgets()
            else:
                self.notify("No waypoints to remove.", severity="error", timeout=5)

        except Exception as e:
            raise UnexpectedError(unexpected_msg_compose(e)) from None

    @on(Button.Pressed, "#info_button")
    def info_pressed(self) -> None:
        self.notify(
            "[b]SeaSeven[/b]:\nShallow ADCP profiler capable of providing information to a depth of 150 m every 4 meters (300kHz)"
            "\n\n[b]OceanObserver[/b]:\nLong-range ADCP profiler capable of providing ~ 1000m of range every 24 meters (38kHz)",
            severity="warning",
            timeout=20,
        )

    def show_hide_adcp_type(self, show: bool) -> None:
        container = self.query_one("#adcp_type_container")
        if show:
            container.remove_class("-hidden")
        else:
            container.add_class("-hidden")

    def _set_adcp_default_values(self):
        self.query_one("#adcp_config_num_bins").value = str(
            DEFAULT_ADCP_CONFIG["num_bins"]
        )
        self.query_one("#adcp_config_period").value = str(
            DEFAULT_ADCP_CONFIG["period_minutes"]
        )
        self.query_one("#adcp_shallow").value = False
        self.query_one("#adcp_deep").value = True

    def _set_ts_default_values(self):
        self.query_one("#ship_underwater_st_config_period").value = str(
            DEFAULT_TS_CONFIG["period_minutes"]
        )

    @on(Switch.Changed, "#has_adcp")
    def on_adcp_toggle(self, event: Switch.Changed) -> None:
        self.show_hide_adcp_type(event.value)
        if event.value and not self.expedition.instruments_config.adcp_config:
            # ADCP was turned on and was previously null
            self._set_adcp_default_values()

    @on(Switch.Changed, "#has_onboard_ts")
    def on_ts_toggle(self, event: Switch.Changed) -> None:
        if (
            event.value
            and not self.expedition.instruments_config.ship_underwater_st_config
        ):
            # T/S was turned on and was previously null
            self._set_ts_default_values()

    @on(Switch.Changed, "#adcp_deep")
    def deep_changed(self, event: Switch.Changed) -> None:
        if event.value:
            shallow = self.query_one("#adcp_shallow", Switch)
            shallow.value = False

    @on(Switch.Changed, "#adcp_shallow")
    def shallow_changed(self, event: Switch.Changed) -> None:
        if event.value:
            deep = self.query_one("#adcp_deep", Switch)
            deep.value = False


class WaypointWidget(Static):
    def __init__(self, waypoint: Waypoint, index: int):
        super().__init__()
        self.waypoint = waypoint
        self.index = index

    def compose(self) -> ComposeResult:
        try:
            with Collapsible(
                title=f"[b]Waypoint {self.index + 1}[/b]",
                collapsed=True,
                id=f"wp{self.index + 1}",
            ):
                if self.index > 0:
                    yield Button(
                        "Copy Time & Instruments from Previous",
                        id=f"wp{self.index}_copy",
                        variant="warning",
                    )
                yield Label("Location:")
                yield Label("    Latitude:")
                yield Input(
                    id=f"wp{self.index}_lat",
                    value=str(self.waypoint.location.lat)
                    if self.waypoint.location.lat
                    is not None  # is not None to handle if lat is 0.0
                    else "",
                    validators=[
                        Function(
                            is_valid_lat,
                            f"INVALID: value must be {is_valid_lat.__doc__.lower()}",
                        )
                    ],
                    type="number",
                    placeholder="°N",
                    classes="latitude-input",
                )
                yield Label(
                    "",
                    id=f"validation-failure-label-wp{self.index}_lat",
                    classes="-hidden validation-failure",
                )

                yield Label("    Longitude:")
                yield Input(
                    id=f"wp{self.index}_lon",
                    value=str(self.waypoint.location.lon)
                    if self.waypoint.location.lon
                    is not None  # is not None to handle if lon is 0.0
                    else "",
                    validators=[
                        Function(
                            is_valid_lon,
                            f"INVALID: value must be {is_valid_lon.__doc__.lower()}",
                        )
                    ],
                    type="number",
                    placeholder="°E",
                    classes="longitude-input",
                )
                yield Label(
                    "",
                    id=f"validation-failure-label-wp{self.index}_lon",
                    classes="-hidden validation-failure",
                )

                yield Label("Time:")
                with Horizontal():
                    yield Label("Year:")
                    yield Select(
                        [
                            (str(year), year)
                            for year in range(
                                1993,
                                datetime.datetime.now().year + 1,
                            )
                        ],
                        id=f"wp{self.index}_year",
                        value=int(self.waypoint.time.year)
                        if self.waypoint.time
                        else Select.BLANK,
                        prompt="YYYY",
                        classes="year-select",
                    )
                    yield Label("Month:")
                    yield Select(
                        [(f"{m:02d}", m) for m in range(1, 13)],
                        id=f"wp{self.index}_month",
                        value=int(self.waypoint.time.month)
                        if self.waypoint.time
                        else Select.BLANK,
                        prompt="MM",
                        classes="month-select",
                    )
                    yield Label("Day:")
                    yield Select(
                        [(f"{d:02d}", d) for d in range(1, 32)],
                        id=f"wp{self.index}_day",
                        value=int(self.waypoint.time.day)
                        if self.waypoint.time
                        else Select.BLANK,
                        prompt="DD",
                        classes="day-select",
                    )
                    yield Label("Hour:")
                    yield Select(
                        [(f"{h:02d}", h) for h in range(24)],
                        id=f"wp{self.index}_hour",
                        value=int(self.waypoint.time.hour)
                        if self.waypoint.time
                        else Select.BLANK,
                        prompt="hh",
                        classes="hour-select",
                    )
                    yield Label("Min:")
                    yield Select(
                        [(f"{m:02d}", m) for m in range(0, 60, 5)],
                        id=f"wp{self.index}_minute",
                        value=int(self.waypoint.time.minute)
                        if self.waypoint.time
                        else Select.BLANK,
                        prompt="mm",
                        classes="minute-select",
                    )

                yield Label("Instruments:")
                for instrument in [i for i in InstrumentType if not i.is_underway]:
                    is_selected = instrument in (self.waypoint.instrument or [])
                    with Horizontal():
                        yield Label(instrument.value)
                        yield Switch(
                            value=is_selected, id=f"wp{self.index}_{instrument.value}"
                        )

                        if instrument.value == "DRIFTER":
                            yield Label("Count")
                            yield Input(
                                id=f"wp{self.index}_drifter_count",
                                value=str(
                                    self.get_drifter_count() if is_selected else ""
                                ),
                                type="integer",
                                placeholder="# of drifters",
                                validators=Integer(
                                    minimum=1,
                                    failure_description="INVALID: value must be > 0",
                                ),
                                classes="drifter-count-input",
                            )
                            yield Label(
                                "",
                                id=f"validation-failure-label-wp{self.index}_drifter_count",
                                classes="-hidden validation-failure",
                            )

        except Exception as e:
            raise UnexpectedError(unexpected_msg_compose(e)) from None

    def get_drifter_count(self) -> int:
        return sum(
            1 for inst in self.waypoint.instrument if inst == InstrumentType.DRIFTER
        )

    def copy_from_previous(self) -> None:
        """Copy inputs from previous waypoint widget (time and instruments only, not lat/lon)."""
        try:
            if self.index > 0:
                schedule_editor = self.parent
                if schedule_editor:
                    time_components = ["year", "month", "day", "hour", "minute"]
                    for comp in time_components:
                        prev = schedule_editor.query_one(f"#wp{self.index - 1}_{comp}")
                        curr = self.query_one(f"#wp{self.index}_{comp}")
                        if prev and curr:
                            curr.value = prev.value

                    for instrument in [
                        inst for inst in InstrumentType if not inst.is_underway
                    ]:
                        prev_switch = schedule_editor.query_one(
                            f"#wp{self.index - 1}_{instrument.value}"
                        )
                        curr_switch = self.query_one(
                            f"#wp{self.index}_{instrument.value}"
                        )
                        if prev_switch and curr_switch:
                            curr_switch.value = prev_switch.value
        except Exception as e:
            raise UnexpectedError(unexpected_msg_compose(e)) from None

    @on(Button.Pressed, "Button")
    def button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == f"wp{self.index}_copy":
            self.copy_from_previous()

    @on(Switch.Changed)
    def on_switch_changed(self, event: Switch.Changed) -> None:
        if event.switch.id == f"wp{self.index}_DRIFTER":
            drifter_count_input = self.query_one(
                f"#wp{self.index}_drifter_count", Input
            )
            if not event.value:
                drifter_count_input.value = ""
            else:
                if not drifter_count_input.value:
                    drifter_count_input.value = "1"


class PlanScreen(Screen):
    def __init__(self, path: str):
        super().__init__()
        self.path = path

    def compose(self) -> ComposeResult:
        try:
            with VerticalScroll():
                yield ExpeditionEditor(self.path)
                with Horizontal():
                    yield Button("Save Changes", id="save_button", variant="success")
                    yield Button("Exit", id="exit_button", variant="error")
        except Exception as e:
            raise UnexpectedError(unexpected_msg_compose(e)) from None

    def sync_ui_waypoints(self):
        """Update the waypoints models with current UI values (spacetime only) from the live UI inputs."""
        expedition_editor = self.query_one(ExpeditionEditor)
        errors = []
        for i, wp in enumerate(expedition_editor.expedition.schedule.waypoints):
            try:
                wp.location = Location(
                    latitude=float(expedition_editor.query_one(f"#wp{i}_lat").value),
                    longitude=float(expedition_editor.query_one(f"#wp{i}_lon").value),
                )
                wp.time = datetime.datetime(
                    int(expedition_editor.query_one(f"#wp{i}_year").value),
                    int(expedition_editor.query_one(f"#wp{i}_month").value),
                    int(expedition_editor.query_one(f"#wp{i}_day").value),
                    int(expedition_editor.query_one(f"#wp{i}_hour").value),
                    int(expedition_editor.query_one(f"#wp{i}_minute").value),
                    0,
                )
            except Exception as e:
                errors.append(f"Waypoint {i + 1}: {e}")
        if errors:
            log_exception_to_file(
                Exception("\n".join(errors)),
                self.path,
                context_message="Error syncing waypoints:",
            )
            raise UnexpectedError(
                UNEXPECTED_MSG_ONSAVE
                + f"\n\nTraceback will be logged in {self.path}/virtualship_error.txt. Please attach this/copy the contents to any issue submitted."
            ) from None

    @on(Button.Pressed, "#exit_button")
    def exit_pressed(self) -> None:
        self.app.exit()

    @on(Button.Pressed, "#save_button")
    def save_pressed(self) -> None:
        """Save button press."""
        expedition_editor = self.query_one(ExpeditionEditor)

        try:
            ship_speed_value = self.get_ship_speed(expedition_editor)

            self.sync_ui_waypoints()  # call to ensure waypoint inputs are synced

            # verify schedule
            wp_lats, wp_lons = _get_waypoint_latlons(
                expedition_editor.expedition.schedule.waypoints
            )
            expedition_editor.expedition.schedule.verify(
                ship_speed_value,
                ignore_land_test=True,
            )

            expedition_saved = expedition_editor.save_changes()

            if expedition_saved:
                self.notify(
                    "Changes saved successfully",
                    severity="information",
                    timeout=20,
                )

        except Exception as e:
            self.notify(
                f"*** Error saving changes ***:\n\n{e}\n",
                severity="error",
                timeout=20,
            )
            return False

    def get_ship_speed(self, expedition_editor):
        try:
            ship_speed = float(expedition_editor.query_one("#speed").value)
            assert ship_speed > 0
        except Exception as e:
            log_exception_to_file(
                e, self.path, context_message="Error saving schedule:"
            )
            raise UnexpectedError(
                UNEXPECTED_MSG_ONSAVE
                + f"\n\nTraceback will be logged in {self.path}/virtualship_error.txt. Please attach this/copy the contents to any issue submitted."
            ) from None
        return ship_speed


class PlanApp(App):
    CSS = """
    Screen {
        align: center middle;
    }

    VerticalScroll {
        width: 100%;
        height: 100%;
        background: $surface;
        color: $text;
        padding: 1;
    }

    WaypointWidget {
        padding: 0;
        margin: 0;
        border: none;
    }

    WaypointWidget > Collapsible {
        margin: 1;
        background: $panel;
        border: solid $primary;
    }

    WaypointWidget > Collapsible > .collapsible--content {
        padding: 1;
    }

    Input.-valid {
        border: tall $success 60%;
    }
    Input.-valid:focus {
        border: tall $success;
    }

    Input {
        margin: 1;
    }

    Label {
        margin-top: 1;
    }

    Button {
        min-width: 16;
        margin: 1;
        color: $text;
    }

    Button.-primary {
        background: $primary;
    }

    Button.-default {
        background: $boost;
    }

    Button.-success {
        background: $success;
    }

    Button.-error {
        background: $error;
    }

    Horizontal {
        height: auto;
        align: left middle;
    }

    Vertical {
        height: auto;
    }

    Switch {
        margin: 0 1;
    }

    #title_ship_instruments_config {
        text-style: bold;
        padding: 1;
    }

    #title_schedule {
        text-style: bold;
        padding: 1;
    }

    #info_button {
        margin-top: 0;
        margin-left: 8;
    }

    #waypoint_list {
        height: auto;
    }

    .drifter-count-input {
        width: auto;
        margin-left: 1;
        margin-right: 1;
    }

    .path {
        color: $text-muted;
        text-style: italic;
    }

    Collapsible {
        background: $boost;
        margin: 1;
    }

    Collapsible > .collapsible--content {
        padding: 1;
    }

    Collapsible > .collapsible--title {
        padding: 1;
    }

    Collapsible > .collapsible--content > Collapsible {
        margin: 0 1;
        background: $panel;
    }

    .-hidden {
        display: none;
    }

    .ts-section {
        margin-bottom: 1;
    }

    .adcp-section {
        margin-bottom: 1;
    }

    .ship_speed {
        align: left middle;
        margin-bottom: 1;
    }

    .ship_speed_input {
        width: 20;
        margin: 0 4;
    }

    .instrument-config {
        margin: 1;
        padding: 0 2;
        height: auto;
    }

    .instrument-config Label {
        margin-top: 1;
        color: $text-muted;
    }

    .instrument-config Input {
        width: 30;
        margin: 0 1;
    }

    .year-select {
        width: 20;
    }

    .month-select, .day-select {
        width: 18;
    }

    .hour-select, .minute-select {
        width: 15;
    }

    Label.validation-failure {
        color: $error;
    }
    """

    def __init__(self, path: str):
        super().__init__()
        self.path = path

    def on_mount(self) -> None:
        self.push_screen(PlanScreen(self.path))
        self.theme = "textual-light"


def _plan(path: str) -> None:
    """Run UI in terminal."""
    app = PlanApp(path)
    app.run()
