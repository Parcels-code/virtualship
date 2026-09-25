import copy
import datetime
import os
import traceback
from collections import Counter
from typing import ClassVar

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.dom import NoMatches
from textual.message import Message
from textual.screen import ModalScreen, Screen
from textual.validation import Function, Integer
from textual.widgets import (
    Button,
    Collapsible,
    Footer,
    Input,
    Label,
    MaskedInput,
    Rule,
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
    CTDConfig,
    DrifterConfig,
    Expedition,
    Location,
    SensorConfig,
    ShipConfig,
    ShipUnderwaterSTConfig,
    Waypoint,
    XBTConfig,
)
from virtualship.models.expedition import Port
from virtualship.utils import EXPEDITION, INCOMPLETE_PORT_MSG

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


def _default_sensors(config_class) -> list:
    """List of SensorConfig instances from the config class's sensors default_factory."""
    sensors_field = config_class.model_fields.get("sensors")
    if sensors_field is None or sensors_field.default_factory is None:
        return []
    return sensors_field.default_factory()


WAYPOINT_TIME_FORMAT = "%Y-%m-%d %H:%M"
WAYPOINT_TIME_TEMPLATE = "9999-99-99 99:99"
WAYPOINT_TIME_INVALID_MSG = (
    "INVALID: time must be a complete, real date and time (YYYY-MM-DD hh:mm)"
)

# waypoint time adjustment buttons (button id, label, variant, step)
TIME_STEPS = (
    ("plus_one_day", "+1 day", "primary", datetime.timedelta(days=1)),
    ("plus_one_hour", "+1 hour", "primary", datetime.timedelta(hours=1)),
    ("plus_thirty_minutes", "+30 minutes", "primary", datetime.timedelta(minutes=30)),
    ("minus_one_day", "-1 day", "default", -datetime.timedelta(days=1)),
    ("minus_one_hour", "-1 hour", "default", -datetime.timedelta(hours=1)),
    ("minus_thirty_minutes", "-30 minutes", "default", -datetime.timedelta(minutes=30)),
)

DEPLOYABLE_INSTRUMENTS = [inst for inst in InstrumentType if not inst.is_underway]


def parse_waypoint_time(text: str) -> datetime.datetime | None:
    """Parse 'YYYY-MM-DD hh:mm' string."""
    if text.strip() == "":
        return None
    return datetime.datetime.strptime(text, WAYPOINT_TIME_FORMAT)


def format_waypoint_time(time: datetime.datetime | None) -> str:
    return time.strftime(WAYPOINT_TIME_FORMAT) if time else ""


def is_valid_waypoint_time(text: str) -> bool:
    try:
        parse_waypoint_time(text)
    except ValueError:
        return False
    return True


def show_validation_result(label: Label, validation_result) -> None:
    """Show validation failure messages in `label`, or hide it if valid."""
    is_invalid = validation_result is not None and not validation_result.is_valid
    message = "\n".join(validation_result.failure_descriptions) if is_invalid else ""
    # only edit label when something changes
    if label.content != message:
        label.update(message)
    label.set_class(not is_invalid, "-hidden")
    label.set_class(is_invalid, "validation-failure")


def _failure_label(input_id: str) -> Label:
    """Label that shows validation failures for the input id."""
    return Label(
        "",
        id=f"validation-failure-label-{input_id}",
        classes="-hidden validation-failure",
    )


def _field_validators(model_class, attr: str) -> list[Function]:
    """Textual input validators for a model field, derived from its pydantic constraints."""
    return [
        Function(validator, f"INVALID: value must be {validator.__doc__.lower()}")
        for validator in group_validators(model_class, attr)
    ]


def _instrument_title(instrument_name: str, info: dict) -> str:
    return info.get("title", instrument_name.replace("_", " ").title())


def _time_unit(attr_meta: dict) -> tuple[str, str, float] | None:
    """(label suffix, timedelta keyword, seconds per unit) for attributes entered in minutes or days."""
    if attr_meta.get("minutes", False):
        return " Minutes", "minutes", 60.0
    if attr_meta.get("days", False):
        return " Days", "days", 86400.0
    return None


def _config_display_value(config_instance, attr_meta: dict) -> str:
    """The value to show in an instrument config input (timedeltas in minutes/days)."""
    if not config_instance:
        return ""
    raw_value = getattr(config_instance, attr_meta["name"], "")
    unit = _time_unit(attr_meta)
    if unit and raw_value != "":
        try:
            return str(raw_value.total_seconds() / unit[2])
        except AttributeError:
            pass
    return str(raw_value)


def _raise_logged_unexpected(e: Exception, path, context_message: str):
    """Log error to expedition directory and raise a user-facing UnexpectedError."""
    log_exception_to_file(e, path, context_message=context_message)
    raise UnexpectedError(
        UNEXPECTED_MSG_ONSAVE
        + f"\n\nTraceback will be logged in {path}/virtualship_error.txt. Please attach this/copy the contents to any issue submitted."
    ) from None


DEFAULT_TS_CONFIG = {"period_minutes": 5.0}

DEFAULT_ADCP_CONFIG = {
    "num_bins": 40,
    "period_minutes": 5.0,
}

# on/off switches for the underway instruments (set to null in the config when off)
UNDERWAY_SWITCH_IDS = {
    "adcp_config": "#has_adcp",
    "ship_underwater_st_config": "#has_onboard_ts",
}


INSTRUMENT_FIELDS = {
    "adcp_config": {
        "class": ADCPConfig,
        "title": "Onboard ADCP",
        "attributes": [
            {"name": "num_bins"},
            {"name": "period", "minutes": True},
        ],
        # underway instrument, so active/inactive is controlled by the on/off toggle, not the schedule (therefore no instrument_type key)
    },
    "ship_underwater_st_config": {
        "class": ShipUnderwaterSTConfig,
        "title": "Onboard Temperature/Salinity",
        "attributes": [
            {"name": "period", "minutes": True},
        ],
        # underway instrument, so active/inactive is controlled by the on/off toggle, not the schedule (therefore no instrument_type key)
    },
    "ctd_config": {
        "class": CTDConfig,
        "title": "CTD",
        "instrument_type": InstrumentType.CTD,
        "attributes": [
            {"name": "max_depth_meter"},
            {"name": "min_depth_meter"},
            {"name": "stationkeeping_time", "minutes": True},
        ],
    },
    "xbt_config": {
        "class": XBTConfig,
        "title": "XBT",
        "instrument_type": InstrumentType.XBT,
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
        "instrument_type": InstrumentType.ARGO_FLOAT,
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
        "instrument_type": InstrumentType.DRIFTER,
        "attributes": [
            {"name": "depth_meter"},
            {"name": "lifetime", "days": True},
            {"name": "stationkeeping_time", "minutes": True},
        ],
    },
}


class ConfirmScreen(ModalScreen):
    """Modal yes/no confirmation dialog."""

    def __init__(self, message: str):
        super().__init__()
        self.message = message

    def compose(self) -> ComposeResult:
        yield Container(
            Label(self.message, id="confirm-label"),
            Horizontal(
                Button("Yes", id="confirm-yes", variant="error"),
                Button("No", id="confirm-no", variant="primary"),
                id="confirm-buttons",
            ),
            id="confirm-container",
            classes="confirm-modal",
        )

    @on(Button.Pressed, "#confirm-yes")
    def confirm_yes(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#confirm-no")
    def confirm_no(self) -> None:
        self.dismiss(False)


class ExpeditionEditor(Static):
    def __init__(self, path: str):
        super().__init__()
        self.path = path
        self.expedition = None
        self._original_schedule = None  # as loaded, for "reset changes"
        self._saved_schedule = None  # as last saved, for the unsaved-changes check
        self._saved_config_values = {}  # config widget values as last saved
        self._validation_labels = {}  # cache input id for validation failure labels, avoid querying the whole model on every keystroke

    def compose(self) -> ComposeResult:
        try:
            self.expedition = Expedition.from_yaml(self.path.joinpath(EXPEDITION))
            self._original_schedule = copy.deepcopy(self.expedition.schedule)
            self._saved_schedule = copy.deepcopy(self.expedition.schedule)
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

            ship_config = self.expedition.ship_config
            instruments_config = self.expedition.instruments_config
            with Collapsible(
                title="[b]Ship Speed & Onboard Measurements[/b]",
                id="speed_collapsible",
                collapsed=False,
            ):
                attr = "ship_speed_knots"
                with Horizontal(classes="ship_speed"):
                    yield Label("[b]Ship Speed (knots):[/b]")
                    yield Input(
                        id="speed",
                        type=type_to_textual(get_field_type(ShipConfig, attr)),
                        validators=_field_validators(ShipConfig, attr),
                        classes="ship_speed_input",
                        placeholder="knots",
                        value=str(ship_config.ship_speed_knots or ""),
                    )
                yield Label("", id="validation-failure-label-speed", classes="-hidden")

                with Horizontal(classes="ts-section"):
                    yield Label("[b]Onboard Temperature/Salinity:[/b]")
                    yield Switch(
                        value=bool(instruments_config.ship_underwater_st_config),
                        id="has_onboard_ts",
                    )

                with Horizontal(classes="adcp-section"):
                    yield Label("[b]Onboard ADCP:[/b]")
                    yield Switch(
                        value=bool(instruments_config.adcp_config), id="has_adcp"
                    )

                # adcp type selection
                with Horizontal(id="adcp_type_container", classes="-hidden"):
                    is_deep = (
                        instruments_config.adcp_config
                        and instruments_config.adcp_config.max_depth_meter == -1000.0
                    )
                    yield Label("       OceanObserver:")
                    yield Switch(value=is_deep, id="adcp_deep")
                    yield Label("   SeaSeven:")
                    yield Switch(value=not is_deep, id="adcp_shallow")
                    yield Button("?", id="info_button", variant="warning")

            ## SECTION: "Instrument Configurations""

            with Collapsible(title="[b]Instrument Configurations[/b]", collapsed=True):
                for instrument_name, info in INSTRUMENT_FIELDS.items():
                    with Collapsible(
                        title=f"[b]{_instrument_title(instrument_name, info)}[/b]",
                        collapsed=True,
                    ):
                        yield from self._compose_instrument_config(
                            instrument_name, info
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
                    Button(
                        "Reset changes (all waypoints)",
                        id="reset_changes",
                        variant="warning",
                    ),
                )

                yield VerticalScroll(id="waypoint_list", classes="waypoint-list")

        except Exception as e:
            raise UnexpectedError(unexpected_msg_compose(e)) from None

    def _compose_instrument_config(self, instrument_name: str, info: dict):
        """Inputs (and sensor toggles) for one instrument's configuration."""
        config_class = info["class"]
        config_instance = getattr(
            self.expedition.instruments_config, instrument_name, None
        )
        if instrument_name in ("adcp_config", "ship_underwater_st_config"):
            yield Label(
                f"NOTE: entries will be ignored here if {info['title']} is OFF in Ship Speed & Onboard Measurements."
            )
        with Container(classes="instrument-config"):
            for attr_meta in info["attributes"]:
                attr = attr_meta["name"]
                unit = _time_unit(attr_meta)
                yield Label(
                    f"{attr.replace('_', ' ').title()}{unit[0] if unit else ''}:"
                )
                yield Input(
                    id=f"{instrument_name}_{attr}",
                    type=type_to_textual(get_field_type(config_class, attr)),
                    validators=_field_validators(config_class, attr),
                    value=_config_display_value(config_instance, attr_meta),
                )
                yield _failure_label(f"{instrument_name}_{attr}")
            # sensor toggles, derived from the config class's sensors default_factory
            default_sensor_configs = _default_sensors(config_class)
            if default_sensor_configs:
                yield Label("[b]Sensors:[/b]", markup=True)
                # which sensors are currently active
                if config_instance and hasattr(config_instance, "sensors"):
                    active_sensor_types = {
                        sc.sensor_type for sc in config_instance.sensors if sc.enabled
                    }
                else:
                    # if no config loaded yet, default all sensors on
                    active_sensor_types = {
                        sc.sensor_type for sc in default_sensor_configs
                    }
                for sc in default_sensor_configs:
                    with Horizontal(classes="sensor-toggle-row"):
                        yield Label(
                            f"    {sc.sensor_type.value.replace('_', ' ').title()}:"
                        )
                        yield Switch(
                            value=sc.sensor_type in active_sensor_types,
                            id=f"{instrument_name}_sensor_{sc.sensor_type.value}",
                        )

    async def on_mount(self) -> None:
        # snapshot before any waypoint bodies exist, so only ship/instrument config widgets are captured
        self._saved_config_values = self._config_values()
        await self.refresh_waypoint_widgets()
        self.show_hide_adcp_type(
            bool(getattr(self.expedition.instruments_config, "adcp_config", None))
        )

    @property
    def waypoint_widgets(self) -> list["WaypointWidget"]:
        return list(self.query_one("#waypoint_list").query_children(WaypointWidget))

    async def refresh_waypoint_widgets(self) -> None:
        """Rebuild all waypoint widgets from the schedule (only needed on load and reset)."""
        waypoint_list = self.query_one("#waypoint_list", VerticalScroll)
        with self.app.batch_update():
            await waypoint_list.remove_children()
            await waypoint_list.mount_all(
                WaypointWidget(waypoint, i)
                for i, waypoint in enumerate(self.expedition.schedule.waypoints)
            )

    def _renumber_waypoints(self) -> None:
        for i, widget in enumerate(self.waypoint_widgets):
            widget.set_index(i)

    def _config_values(self) -> dict:
        """Current values of the ship/instrument config widgets."""
        return {
            widget.id: widget.value
            for widget in self.query("Input, Switch")
            if widget.id
            and not any(isinstance(a, WaypointWidget) for a in widget.ancestors)
        }

    def has_unsaved_changes(self) -> bool:
        if self.expedition.schedule != self._saved_schedule:
            return True
        return any(
            self.query_one(f"#{widget_id}").value != value
            for widget_id, value in self._saved_config_values.items()
        )

    def waypoint_errors(self) -> list[str]:
        """Messages for waypoint entries that are invalid or incomplete."""
        return [
            f"{widget.get_title()}: {message}"
            for widget in self.waypoint_widgets
            for message in widget.errors.values()
        ]

    def save_changes(self) -> bool:
        """Save changes to expedition.yaml."""
        try:
            self._update_ship_speed()
            self._update_instrument_configs()
            self.expedition.to_yaml(self.path.joinpath(EXPEDITION))
            self._saved_schedule = copy.deepcopy(self.expedition.schedule)
            self._saved_config_values = {
                widget_id: self.query_one(f"#{widget_id}").value
                for widget_id in self._saved_config_values
            }
            return True
        except UserError:
            raise
        except Exception as e:
            _raise_logged_unexpected(
                e, self.path, f"Error saving {self.path.joinpath(EXPEDITION)}:"
            )

    def _update_ship_speed(self):
        attr = "ship_speed_knots"
        field_type = get_field_type(type(self.expedition.ship_config), attr)
        value = field_type(self.query_one("#speed").value)
        ShipConfig.model_validate(
            {**self.expedition.ship_config.model_dump(), attr: value}
        )
        self.expedition.ship_config.ship_speed_knots = value

    def _update_instrument_configs(self):
        instruments_config = self.expedition.instruments_config
        for instrument_name, info in INSTRUMENT_FIELDS.items():
            config_class = info["class"]
            title = _instrument_title(instrument_name, info)
            # onboard ADCP and T/S are removed when switched off
            switch_id = UNDERWAY_SWITCH_IDS.get(instrument_name)
            if switch_id and not self.query_one(switch_id, Switch).value:
                setattr(instruments_config, instrument_name, None)
                continue

            kwargs = {}
            for attr_meta in info["attributes"]:
                attr = attr_meta["name"]
                value = self.query_one(f"#{instrument_name}_{attr}").value
                field_type = get_field_type(config_class, attr)
                unit = _time_unit(attr_meta)
                if unit and field_type is datetime.timedelta:
                    kwargs[attr] = datetime.timedelta(**{unit[1]: float(value)})
                else:
                    kwargs[attr] = field_type(value)

            # ADCP max_depth_meter based on deep/shallow switch
            if instrument_name == "adcp_config":
                is_deep = self.query_one("#adcp_deep", Switch).value
                if is_deep == self.query_one("#adcp_shallow", Switch).value:
                    raise UserError(
                        "Onboard ADCP is ON, so exactly one ADCP type (OceanObserver or SeaSeven) must be selected."
                    )
                kwargs["max_depth_meter"] = -1000.0 if is_deep else -150.0

            # collect sensor toggles
            default_sensor_configs = _default_sensors(config_class)
            if default_sensor_configs:
                sensors = [
                    SensorConfig(sensor_type=sc.sensor_type)
                    for sc in default_sensor_configs
                    if self.query_one(
                        f"#{instrument_name}_sensor_{sc.sensor_type.value}", Switch
                    ).value
                ]
                if not sensors:
                    if self._is_instrument_in_schedule(info.get("instrument_type")):
                        raise UserError(
                            f"'{title}' has no sensors selected. "
                            f"At least one sensor must be enabled for each active instrument."
                        )
                    # fall back to the default sensors so pydantic validation passes
                    sensors = [
                        SensorConfig(sensor_type=sc.sensor_type)
                        for sc in default_sensor_configs
                    ]
                kwargs["sensors"] = sensors

            try:
                setattr(instruments_config, instrument_name, config_class(**kwargs))
            except Exception as e:
                # validation errors, e.g. drift_days >= cycle_days
                if isinstance(e, ValueError) or "ValidationError" in type(e).__name__:
                    raise UserError(f"'{title}' configuration error: {e}") from None
                raise

    def _is_instrument_in_schedule(self, instrument_type) -> bool:
        """Whether any waypoint deploys `instrument_type` (always True for underway instruments, i.e. None)."""
        return instrument_type is None or any(
            instrument_type
            in (wp.instrument if isinstance(wp.instrument, list) else [wp.instrument])
            for wp in self.expedition.schedule.waypoints
            if getattr(wp, "instrument", None)
        )

    @on(Input.Changed)
    def show_invalid_reasons(self, event: Input.Changed) -> None:
        input_id = event.input.id
        label_id = f"validation-failure-label-{input_id}"

        # cached to avoid querying the whole model on every keystroke
        label = self._validation_labels.get(label_id)
        if label is None:
            try:
                label = self.query_one(f"#{label_id}", Label)
            except NoMatches:
                return
            self._validation_labels[label_id] = label

        show_validation_result(label, event.validation_result)

    def _schedule_index(self, waypoint: Waypoint) -> int:
        return next(
            i
            for i, wp in enumerate(self.expedition.schedule.waypoints)
            if wp is waypoint
        )

    def _arrival_port_index(self) -> int:
        return next(
            i
            for i, wp in reversed(list(enumerate(self.expedition.schedule.waypoints)))
            if isinstance(wp, Port)
        )

    @on(Button.Pressed, "#add_waypoint")
    async def add_waypoint(self) -> None:
        """Add a new waypoint to the schedule (N.B. ports always remain). Copies time from last waypoint if possible (Lat/lon and instruments blank)."""
        try:
            wps = self.expedition.schedule.waypoints
            non_port_wps = [wp for wp in wps if not isinstance(wp, Port)]
            new_wp = Waypoint(
                location=Location(latitude=0.0, longitude=0.0),
                time=non_port_wps[-1].time if non_port_wps else None,
                instrument=[],
            )
            # add waypoint just before the arrival port
            insert_index = self._arrival_port_index()
            wps.insert(insert_index, new_wp)
            await self.query_one("#waypoint_list").mount(
                WaypointWidget(new_wp, insert_index),
                before=self.waypoint_widgets[insert_index],
            )
            self._renumber_waypoints()
        except Exception as e:
            raise UnexpectedError(unexpected_msg_compose(e)) from None

    async def _remove_waypoint_widget(self, widget: "WaypointWidget") -> None:
        self.expedition.schedule.waypoints.pop(self._schedule_index(widget.waypoint))
        await widget.remove()
        self._renumber_waypoints()

    @on(Button.Pressed, "#remove_waypoint")
    async def remove_waypoint(self) -> None:
        """Remove the last waypoint (non-port) from the schedule."""
        try:
            non_port_widgets = [
                w for w in self.waypoint_widgets if not isinstance(w.waypoint, Port)
            ]
            if non_port_widgets:
                await self._remove_waypoint_widget(non_port_widgets[-1])
            else:
                self.notify("No waypoints to remove.", severity="error", timeout=5)
        except Exception as e:
            raise UnexpectedError(unexpected_msg_compose(e)) from None

    @on(Button.Pressed, "#reset_changes")
    async def reset_changes(self) -> None:
        """Reset all changes to the schedule, reverting to the original loaded schedule."""
        try:
            self.expedition.schedule = copy.deepcopy(self._original_schedule)
            await self.refresh_waypoint_widgets()
        except Exception as e:
            raise UnexpectedError(unexpected_msg_compose(e)) from None

    def on_waypoint_widget_remove_requested(
        self, event: "WaypointWidget.RemoveRequested"
    ) -> None:
        """Ask for confirmation before removing a specific waypoint."""
        widget = event.widget

        async def on_confirmed(confirmed: bool) -> None:
            if confirmed and widget.is_attached:
                try:
                    await self._remove_waypoint_widget(widget)
                except Exception as e:
                    raise UnexpectedError(unexpected_msg_compose(e)) from None

        message = f"Are you sure you want to remove {widget.get_title().lower()}?"
        self.app.push_screen(ConfirmScreen(message), on_confirmed)

    def on_waypoint_widget_copy_requested(
        self, event: "WaypointWidget.CopyRequested"
    ) -> None:
        """Copy time (and instruments, between non-port waypoints) from the previous waypoint, not lat/lon."""
        try:
            widget = event.widget
            idx = self._schedule_index(widget.waypoint)
            if idx == 0:
                return
            previous, current = self.expedition.schedule.waypoints[idx - 1 : idx + 1]
            current.time = previous.time
            if not isinstance(current, Port) and not isinstance(previous, Port):
                current.instrument = list(previous.instrument or [])
            widget.load_from_model()
        except Exception as e:
            raise UnexpectedError(unexpected_msg_compose(e)) from None

    def show_hide_adcp_type(self, show: bool) -> None:
        self.query_one("#adcp_type_container").set_class(not show, "-hidden")

    @on(Switch.Changed, "#has_adcp")
    def on_adcp_toggle(self, event: Switch.Changed) -> None:
        self.show_hide_adcp_type(event.value)
        if event.value and not self.expedition.instruments_config.adcp_config:
            # use defaults when ADCP was turned on and was previously null
            self.query_one("#adcp_config_num_bins").value = str(
                DEFAULT_ADCP_CONFIG["num_bins"]
            )
            self.query_one("#adcp_config_period").value = str(
                DEFAULT_ADCP_CONFIG["period_minutes"]
            )
            self.query_one("#adcp_shallow").value = False
            self.query_one("#adcp_deep").value = True

    @on(Switch.Changed, "#has_onboard_ts")
    def on_ts_toggle(self, event: Switch.Changed) -> None:
        if (
            event.value
            and not self.expedition.instruments_config.ship_underwater_st_config
        ):
            # use defaults when T/S was turned on and was previously null
            self.query_one("#ship_underwater_st_config_period").value = str(
                DEFAULT_TS_CONFIG["period_minutes"]
            )

    # one ADCP type is always selected
    @on(Switch.Changed, "#adcp_deep")
    def deep_changed(self, event: Switch.Changed) -> None:
        self.query_one("#adcp_shallow", Switch).value = not event.value

    @on(Switch.Changed, "#adcp_shallow")
    def shallow_changed(self, event: Switch.Changed) -> None:
        self.query_one("#adcp_deep", Switch).value = not event.value

    @on(Button.Pressed, "#info_button")
    def info_pressed(self) -> None:
        self.notify(
            "[b]SeaSeven[/b]:\nShallow ADCP profiler capable of providing information to a depth of 150 m every 4 meters (300kHz)"
            "\n\n[b]OceanObserver[/b]:\nLong-range ADCP profiler capable of providing ~ 1000m of depth range every 24 meters (38kHz)",
            severity="warning",
            timeout=20,
        )


class WaypointBody(Vertical):
    """The editable contents of a WaypointWidget. Only built when the waypoint is first expanded."""

    def __init__(self, waypoint: Waypoint, show_copy_button: bool):
        super().__init__()
        self.waypoint = waypoint
        self.show_copy_button = show_copy_button

    def _yield_coordinate_input(
        self, label: str, field: str, validator_fn, placeholder: str
    ) -> ComposeResult:
        """Yields a labeled coordinate input with its validation error label."""
        val = getattr(self.waypoint.location, field, None)

        yield Label(f"    {label}:")
        yield Input(
            id=field,
            value=str(val) if val is not None else "",
            validators=[
                Function(
                    validator_fn,
                    f"INVALID: value must be {validator_fn.__doc__.lower()}",
                )
            ],
            type="number",
            placeholder=placeholder,
            classes=f"{field}itude-input",
        )
        yield _failure_label(field)

    def _yield_instrument_controls(self) -> ComposeResult:
        yield Label("Instruments:")

        for instrument in DEPLOYABLE_INSTRUMENTS:
            is_selected = instrument in (self.waypoint.instrument or [])
            with Horizontal():
                yield Label(instrument.value)
                yield Switch(value=is_selected, id=instrument.value)

                if instrument is InstrumentType.DRIFTER:
                    drifter_count = (self.waypoint.instrument or []).count(
                        InstrumentType.DRIFTER
                    )
                    yield Label("Count")
                    yield Input(
                        id="drifter_count",
                        value=str(drifter_count) if is_selected else "",
                        type="integer",
                        placeholder="# of drifters",
                        validators=Integer(
                            minimum=1,
                            failure_description="INVALID: value must be > 0",
                        ),
                        classes="drifter-count-input",
                    )
                    yield _failure_label("drifter_count")

    def compose(self) -> ComposeResult:
        if self.show_copy_button:
            yield Button(
                "Copy Time from Previous"
                if isinstance(self.waypoint, Port)
                else "Copy Time & Instruments from Previous",
                id="copy",
                variant="warning",
            )

        yield Label("Location:")
        yield from self._yield_coordinate_input("Latitude", "lat", is_valid_lat, "°N")
        yield from self._yield_coordinate_input("Longitude", "lon", is_valid_lon, "°E")

        yield Label("Time (YYYY-MM-DD hh:mm):")
        yield MaskedInput(
            template=WAYPOINT_TIME_TEMPLATE,
            value=format_waypoint_time(self.waypoint.time),
            placeholder="YYYY-MM-DD hh:mm",
            id="time",
            validators=[Function(is_valid_waypoint_time, WAYPOINT_TIME_INVALID_MSG)],
            valid_empty=True,
            classes="time-input",
        )
        yield _failure_label("time")
        yield Horizontal(
            *(
                Button(label, id=button_id, variant=variant)
                for button_id, label, variant, _ in TIME_STEPS
            ),
            classes="time-adjust-buttons",
        )

        if not isinstance(self.waypoint, Port):
            yield from self._yield_instrument_controls()
            yield Horizontal(Button("Remove Waypoint", id="remove", variant="error"))


class WaypointWidget(Static):
    """A waypoint in the schedule editor."""

    class _Request(Message):
        def __init__(self, widget: "WaypointWidget"):
            super().__init__()
            self.widget = widget

    class RemoveRequested(_Request):
        """Posted when the user asks to remove this waypoint."""

    class CopyRequested(_Request):
        """Posted when the user asks to copy time/instruments from the previous waypoint."""

    def __init__(self, waypoint: Waypoint, index: int):
        super().__init__()
        self.waypoint = waypoint
        self.index = index
        self.errors: dict[str, str] = {}
        self.body: WaypointBody | None = None

    def compose(self) -> ComposeResult:
        yield Collapsible(title=self.get_title(), collapsed=True)

    @on(Collapsible.Expanded)
    async def build_body(self, event: Collapsible.Expanded) -> None:
        event.stop()
        if self.body is None:
            try:
                self.body = WaypointBody(self.waypoint, show_copy_button=self.index > 0)
                await self.query_one(Collapsible.Contents).mount(self.body)
            except Exception as e:
                raise UnexpectedError(unexpected_msg_compose(e)) from None

    def get_title(self) -> str:
        if isinstance(self.waypoint, Port):
            return "Port of Departure" if self.index == 0 else "Port of Arrival"
        else:
            return f"Waypoint {self.index}"

    def set_index(self, index: int) -> None:
        if index != self.index:
            self.index = index
            self.query_one(Collapsible).title = self.get_title()

    def load_from_model(self) -> None:
        """Update the (built) controls to match the waypoint model's time and instruments."""
        if self.body is None:
            return  # built from the model when first expanded
        self.body.query_one("#time", MaskedInput).value = format_waypoint_time(
            self.waypoint.time
        )
        if not isinstance(self.waypoint, Port):
            instruments = self.waypoint.instrument or []
            drifter_count = instruments.count(InstrumentType.DRIFTER)
            self.body.query_one("#drifter_count", Input).value = (
                str(drifter_count) if drifter_count else ""
            )
            for instrument in DEPLOYABLE_INSTRUMENTS:
                self.body.query_one(f"#{instrument.value}", Switch).value = (
                    instrument in instruments
                )

    # model updates

    def _sync_location(self) -> None:
        lat_text = self.body.query_one("#lat", Input).value.strip()
        lon_text = self.body.query_one("#lon", Input).value.strip()
        try:
            lat = float(lat_text) if lat_text else None
            lon = float(lon_text) if lon_text else None
            if (lat is None or lon is None) and not isinstance(self.waypoint, Port):
                raise ValueError("Latitude and longitude are both required.")
            if lat is None and lon is None:
                # leave an existing null/empty location when unused port
                location = self.waypoint.location or None
                if location is not None and (
                    location.latitude is not None or location.longitude is not None
                ):
                    location = Location(latitude=None, longitude=None)
            else:
                location = Location(latitude=lat, longitude=lon)
        except ValueError as e:
            message = str(e)
            if message.startswith("could not convert"):
                message = "Latitude and longitude must be numbers."
            self.errors["location"] = message
            return
        self.errors.pop("location", None)
        if location != self.waypoint.location:
            self.waypoint.location = location

    def _sync_time(self) -> None:
        try:
            time = parse_waypoint_time(self.body.query_one("#time", MaskedInput).value)
        except ValueError:
            self.errors["time"] = (
                "Time must be a complete, real date and time (YYYY-MM-DD hh:mm)."
            )
            return
        self.errors.pop("time", None)
        current = self.waypoint.time
        # only overwrite if the minute actually changed (keeps any seconds)
        if time != (current.replace(second=0, microsecond=0) if current else None):
            self.waypoint.time = time

    def _sync_instruments(self) -> None:
        if isinstance(self.waypoint, Port):
            return
        instruments = []
        for instrument in DEPLOYABLE_INSTRUMENTS:
            if not self.body.query_one(f"#{instrument.value}", Switch).value:
                continue
            if instrument is InstrumentType.DRIFTER:
                try:
                    count = int(self.body.query_one("#drifter_count", Input).value)
                    if count < 1:
                        raise ValueError
                except ValueError:
                    self.errors["drifter_count"] = (
                        "Drifter count must be a whole number greater than 0."
                    )
                    return
                instruments.extend([instrument] * count)
            else:
                instruments.append(instrument)
        self.errors.pop("drifter_count", None)
        # compare ignoring order, so an untouched waypoint's instrument order is left as loaded
        if Counter(instruments) != Counter(self.waypoint.instrument or []):
            self.waypoint.instrument = instruments

    # event handlers

    @on(Input.Changed)
    def input_changed(self, event: Input.Changed) -> None:
        event.stop()
        input_id = event.input.id
        validation_result = event.validation_result
        if input_id in ("lat", "lon"):
            self._sync_location()
        elif input_id == "time":
            self._sync_time()
        elif input_id == "drifter_count":
            self._sync_instruments()
            if not self.body.query_one("#DRIFTER", Switch).value:
                # count is irrelevant while drifters are off
                validation_result = None
                event.input.remove_class("-valid", "-invalid")

        try:
            label = self.body.query_one(f"#validation-failure-label-{input_id}", Label)
        except NoMatches:
            return
        show_validation_result(label, validation_result)

    @on(Switch.Changed)
    def switch_changed(self, event: Switch.Changed) -> None:
        event.stop()
        if event.switch.id == "DRIFTER":
            drifter_count_input = self.body.query_one("#drifter_count", Input)
            if not event.value:
                drifter_count_input.value = ""
            elif not drifter_count_input.value:
                drifter_count_input.value = "1"
        self._sync_instruments()

    @on(Button.Pressed)
    def button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        button_id = event.button.id
        if button_id == "copy":
            self.post_message(self.CopyRequested(self))
        elif button_id == "remove":
            self.post_message(self.RemoveRequested(self))
        else:
            step = next((s[3] for s in TIME_STEPS if s[0] == button_id), None)
            if step is not None:
                self._adjust_time(step)

    def _adjust_time(self, step: datetime.timedelta) -> None:
        time_input = self.body.query_one("#time", MaskedInput)
        try:
            # from the box rather than the model, so rapid presses accumulate properly
            time = parse_waypoint_time(time_input.value)
        except ValueError:
            time = None
        if time is None:
            self.notify(
                "Cannot adjust time: a complete time is not set for this waypoint.",
                severity="error",
                timeout=20,
            )
            return
        time_input.value = format_waypoint_time(time + step)
        self._sync_time()


class QuitConfirmScreen(ConfirmScreen):
    """Confirmation before quitting with unsaved changes."""


class PlanScreen(Screen):
    BINDINGS: ClassVar[list[Binding]] = [
        Binding("ctrl+s", "save", "Save", priority=True),
        Binding("escape", "collapse_all", "Collapse all"),
    ]

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
                    yield Button(
                        "Collapse All", id="collapse_all_button", variant="default"
                    )
            yield Footer()
        except Exception as e:
            raise UnexpectedError(unexpected_msg_compose(e)) from None

    @on(Button.Pressed, "#exit_button")
    async def exit_pressed(self) -> None:
        await self.app.run_action("quit")

    @on(Button.Pressed, "#collapse_all_button")
    def action_collapse_all(self) -> None:
        """Collapse every section and waypoint, and scroll back to the top."""
        with self.app.batch_update():
            for collapsible in self.query(Collapsible):
                collapsible.collapsed = True
        self.query_one(VerticalScroll).scroll_home(animate=False)

    def action_save(self) -> None:
        self.save_pressed()

    @on(Button.Pressed, "#save_button")
    def save_pressed(self) -> None:
        """Save button press."""
        editor = self.query_one(ExpeditionEditor)
        try:
            if waypoint_errors := editor.waypoint_errors():
                raise UserError(
                    "Some waypoint entries are invalid or incomplete:\n\n"
                    + "\n".join(waypoint_errors)
                )
            ship_speed = self.get_ship_speed(editor)
            schedule = editor.expedition.schedule
            schedule.verify(
                ship_speed, editor.expedition.instruments_config, ignore_land_test=True
            )
            if editor.save_changes():
                self.notify(
                    "Changes saved successfully", severity="information", timeout=20
                )
            # check for incomplete ports and warn the user, but allow save to continue
            if not (
                schedule.departure_port.is_in_use and schedule.arrival_port.is_in_use
            ):
                self.notify(INCOMPLETE_PORT_MSG, severity="warning", timeout=20)
        except Exception as e:
            self.notify(
                f"*** Error saving changes ***:\n\n{e}\n",
                severity="error",
                timeout=20,
                markup=False,
            )
            return False

    def get_ship_speed(self, expedition_editor):
        try:
            ship_speed = float(expedition_editor.query_one("#speed").value)
            assert ship_speed > 0
        except Exception as e:
            _raise_logged_unexpected(e, self.path, "Error saving schedule:")
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

    .sensor-toggle-row {
        height: auto;
        margin: 0;
        padding: 0;
    }

    .sensor-toggle-row Label {
        width: 24;
        margin-top: 1;
        color: $text-muted;
    }

    .time-input {
        width: 24;
    }

    Label.validation-failure {
        color: $error;
    }

    .time-adjust-buttons {
        margin-left: 5;


    }

    .confirm-modal {
        align: center middle;
        width: 50;
        min-height: 9;
        border: round $primary;
        background: $panel;
        padding: 2 4;
        content-align: center middle;
        margin: 2 4;
        layout: vertical;
    }

    #confirm-label {
        content-align: center middle;
        text-align: center;
        width: 100%;
        margin-bottom: 2;
    }

    #confirm-buttons {
        align: center middle;
        width: 100%;
        margin-top: 1;
        content-align: center middle;
        layout: horizontal;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("ctrl+q", "quit", "Quit", priority=True),
    ]

    def __init__(self, path: str):
        super().__init__()
        self.path = path
        # for speed-up on remote/browser-based terminals
        self.animation_level = "none"

    def on_mount(self) -> None:
        self.push_screen(PlanScreen(self.path))
        self.theme = "textual-light"

    async def action_quit(self) -> None:
        """Quit, asking first if there are unsaved changes."""
        if isinstance(self.screen, QuitConfirmScreen):
            self.exit()
            return
        try:
            editor = self.screen.query_one(ExpeditionEditor)
        except NoMatches:
            self.exit()
            return
        if not (editor.has_unsaved_changes() or editor.waypoint_errors()):
            self.exit()
            return

        def on_confirmed(confirmed: bool) -> None:
            if confirmed:
                self.exit()

        self.push_screen(
            QuitConfirmScreen("You have unsaved changes. Quit without saving?"),
            on_confirmed,
        )


def _plan(path: str) -> None:
    """Run UI in terminal."""
    app = PlanApp(path)
    app.run()
