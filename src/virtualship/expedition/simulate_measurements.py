"""simulate_measurements function."""

from __future__ import annotations

import logging
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from yaspin import yaspin

from virtualship.instruments.adcp import simulate_adcp
from virtualship.instruments.argo_float import simulate_argo_floats
from virtualship.instruments.ctd import simulate_ctd
from virtualship.instruments.ctd_bgc import simulate_ctd_bgc
from virtualship.instruments.drifter import simulate_drifters
from virtualship.instruments.ship_underwater_st import simulate_ship_underwater_st
from virtualship.instruments.xbt import simulate_xbt
from virtualship.models import InstrumentsConfig
from virtualship.utils import ship_spinner

from .simulate_schedule import MeasurementsToSimulate

if TYPE_CHECKING:
    from .input_data import InputData

# parcels logger (suppress INFO messages to prevent log being flooded)
external_logger = logging.getLogger("parcels.tools.loggers")
external_logger.setLevel(logging.WARNING)


def simulate_measurements(
    expedition_dir: str | Path,
    instruments_config: InstrumentsConfig,
    input_data: InputData,
    measurements: MeasurementsToSimulate,
) -> None:
    """
    Simulate measurements using Parcels.

    Saves everything in expedition_dir/results.

    :param expedition_dir: Base directory of the expedition.
    :param input_data: Input data for simulation.
    :param measurements: The measurements to simulate.
    :raises RuntimeError: In case fieldsets of configuration is not provided. Make sure to check this before calling this function.
    """
    if isinstance(expedition_dir, str):
        expedition_dir = Path(expedition_dir)

    if len(measurements.ship_underwater_sts) > 0:
        if instruments_config.ship_underwater_st_config is None:
            raise RuntimeError("No configuration for ship underwater ST provided.")
        if input_data.ship_underwater_st_fieldset is None:
            raise RuntimeError("No fieldset for ship underwater ST provided.")
        with yaspin(
            text="Simulating onboard temperature and salinity measurements... ",
            side="right",
            spinner=ship_spinner,
        ) as spinner:
            simulate_ship_underwater_st(
                fieldset=input_data.ship_underwater_st_fieldset,
                out_path=expedition_dir.joinpath("results", "ship_underwater_st.zarr"),
                depth=-2,
                sample_points=measurements.ship_underwater_sts,
            )
            spinner.ok("✅")

    if len(measurements.adcps) > 0:
        if instruments_config.adcp_config is None:
            raise RuntimeError("No configuration for ADCP provided.")
        if input_data.adcp_fieldset is None:
            raise RuntimeError("No fieldset for ADCP provided.")
        with yaspin(
            text="Simulating onboard ADCP... ", side="right", spinner=ship_spinner
        ) as spinner:
            simulate_adcp(
                fieldset=input_data.adcp_fieldset,
                out_path=expedition_dir.joinpath("results", "adcp.zarr"),
                max_depth=instruments_config.adcp_config.max_depth_meter,
                min_depth=-5,
                num_bins=instruments_config.adcp_config.num_bins,
                sample_points=measurements.adcps,
            )
            spinner.ok("✅")

    if len(measurements.ctds) > 0:
        if instruments_config.ctd_config is None:
            raise RuntimeError("No configuration for CTD provided.")
        if input_data.ctd_fieldset is None:
            raise RuntimeError("No fieldset for CTD provided.")
        with yaspin(
            text="Simulating CTD casts... ", side="right", spinner=ship_spinner
        ) as spinner:
            simulate_ctd(
                out_path=expedition_dir.joinpath("results", "ctd.zarr"),
                fieldset=input_data.ctd_fieldset,
                ctds=measurements.ctds,
                outputdt=timedelta(seconds=10),
            )
            spinner.ok("✅")

    if len(measurements.ctd_bgcs) > 0:
        if instruments_config.ctd_bgc_config is None:
            raise RuntimeError("No configuration for CTD_BGC provided.")
        if input_data.ctd_bgc_fieldset is None:
            raise RuntimeError("No fieldset for CTD_BGC provided.")
        with yaspin(
            text="Simulating BGC CTD casts... ", side="right", spinner=ship_spinner
        ) as spinner:
            simulate_ctd_bgc(
                out_path=expedition_dir.joinpath("results", "ctd_bgc.zarr"),
                fieldset=input_data.ctd_bgc_fieldset,
                ctd_bgcs=measurements.ctd_bgcs,
                outputdt=timedelta(seconds=10),
            )
            spinner.ok("✅")

    if len(measurements.xbts) > 0:
        if instruments_config.xbt_config is None:
            raise RuntimeError("No configuration for XBTs provided.")
        if input_data.xbt_fieldset is None:
            raise RuntimeError("No fieldset for XBTs provided.")
        with yaspin(
            text="Simulating XBTs... ", side="right", spinner=ship_spinner
        ) as spinner:
            simulate_xbt(
                out_path=expedition_dir.joinpath("results", "xbts.zarr"),
                fieldset=input_data.xbt_fieldset,
                xbts=measurements.xbts,
                outputdt=timedelta(seconds=1),
            )
            spinner.ok("✅")

    if len(measurements.drifters) > 0:
        print("Simulating drifters... ")
        if instruments_config.drifter_config is None:
            raise RuntimeError("No configuration for drifters provided.")
        if input_data.drifter_fieldset is None:
            raise RuntimeError("No fieldset for drifters provided.")
        simulate_drifters(
            out_path=expedition_dir.joinpath("results", "drifters.zarr"),
            fieldset=input_data.drifter_fieldset,
            drifters=measurements.drifters,
            outputdt=timedelta(hours=5),
            dt=timedelta(minutes=5),
            endtime=None,
        )

    if len(measurements.argo_floats) > 0:
        print("Simulating argo floats... ")
        if instruments_config.argo_float_config is None:
            raise RuntimeError("No configuration for argo floats provided.")
        if input_data.argo_float_fieldset is None:
            raise RuntimeError("No fieldset for argo floats provided.")
        simulate_argo_floats(
            out_path=expedition_dir.joinpath("results", "argo_floats.zarr"),
            argo_floats=measurements.argo_floats,
            fieldset=input_data.argo_float_fieldset,
            outputdt=timedelta(minutes=5),
            endtime=None,
        )
