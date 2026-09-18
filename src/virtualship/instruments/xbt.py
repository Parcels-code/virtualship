from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import ClassVar

import numpy as np
from parcels import ParticleFile, ParticleSet, Variable
from parcels._core.statuscodes import StatusCode

from virtualship.instruments.base import FetchSpec, Instrument
from virtualship.instruments.sensors import SensorType
from virtualship.instruments.types import InstrumentType
from virtualship.models.spacetime import Spacetime
from virtualship.utils import (
    _compute_max_depths,
    build_particle_class_from_sensors,
    register_instrument,
)

# =====================================================
# SECTION: Dataclass
# =====================================================


@dataclass
class XBT:
    """XBT configuration."""

    name: ClassVar[str] = "XBT"
    spacetime: Spacetime
    min_depth: float
    max_depth: float
    fall_speed: float
    deceleration_coefficient: float


# =====================================================
# SECTION: non-sensor Particle Variables (non-sampling)
# =====================================================

_XBT_NONSENSOR_VARIABLES = [
    Variable("max_depth", dtype=np.float32),
    Variable("min_depth", dtype=np.float32),
    Variable("fall_speed", dtype=np.float32),
    Variable("deceleration_coefficient", dtype=np.float32),
]


# =====================================================
# SECTION: Kernels
# =====================================================


def _sample_temperature(particles, fieldset):
    particles.temperature = fieldset.T[particles]


def _xbt_cast(particles, fieldset):
    particles.dz = -particles.fall_speed * particles.dt

    # update the fall speed from the quadractic fall-rate equation
    # check https://doi.org/10.5194/os-7-231-2011
    particles.fall_speed = (
        particles.fall_speed - 2 * particles.deceleration_coefficient * particles.dt
    )

    # delete particle if depth is exactly max_depth
    finished = particles.z == particles.max_depth
    particles.state[finished] = StatusCode.Delete

    # set particle depth to max depth if it's too deep
    too_deep = particles.z + particles.dz < particles.max_depth
    particles.dz[too_deep] = particles.max_depth - particles.z[too_deep]


# =====================================================
# SECTION: Instrument Class
# =====================================================


@register_instrument(InstrumentType.XBT)
class XBTInstrument(Instrument):
    """XBT instrument class."""

    sensor_kernels: ClassVar[dict[SensorType, Callable]] = {
        SensorType.TEMPERATURE: _sample_temperature,
    }

    def __init__(self, expedition, from_data):
        """Initialize XBTInstrument."""
        variables = expedition.instruments_config.xbt_config.active_variables()
        fetch_spec = FetchSpec(
            depth_min=expedition.instruments_config.xbt_config.min_depth_meter,
            depth_max=expedition.instruments_config.xbt_config.max_depth_meter,
        )

        super().__init__(
            expedition,
            variables,
            add_bathymetry=True,
            verbose_progress=False,
            fetch_spec=fetch_spec,
            from_data=from_data,
        )

    def simulate(self, measurements, out_path) -> None:
        """Simulate XBT measurements."""
        DT = 10.0  # dt of XBT simulation integrator
        OUTPUT_DT = timedelta(seconds=10)

        if len(measurements) == 0:
            print(
                "No XBTs provided. Parcels currently crashes when providing an empty particle set, so no XBT simulation will be done and no files will be created."
            )
            # TODO when Parcels supports it this check can be removed.
            return

        fieldset = self.load_input_data()

        fieldset_starttime = fieldset.time_interval.left
        fieldset_endtime = fieldset.time_interval.right

        # deploy time for all xbts should be later than fieldset start time
        if not all(
            [
                np.datetime64(xbt.spacetime.time) >= fieldset_starttime
                for xbt in measurements
            ]
        ):
            raise ValueError("XBT deployed before fieldset starts.")

        # depth the xbt will go to. shallowest between xbt max depth and bathymetry.
        max_depths = _compute_max_depths(measurements, fieldset)

        # initial fall speeds
        initial_fall_speeds = [xbt.fall_speed for xbt in measurements]

        # XBT depth can not be too shallow, because kernel would break.
        for max_depth, fall_speed in zip(max_depths, initial_fall_speeds, strict=False):
            if not max_depth <= -DT * fall_speed:
                raise ValueError(
                    f"XBT max_depth or bathymetry shallower than minimum {-DT * fall_speed}. It is likely the XBT cannot be deployed in this area, which is too shallow."
                )

        # build dynamic particle class from the active sensors
        xbt_config = self.expedition.instruments_config.xbt_config
        _XBTParticle = build_particle_class_from_sensors(
            xbt_config.sensors, _XBT_NONSENSOR_VARIABLES
        )

        # define xbt particles
        xbt_particleset = ParticleSet(
            fieldset=fieldset,
            pclass=_XBTParticle,
            x=[xbt.spacetime.location.lon for xbt in measurements],
            y=[xbt.spacetime.location.lat for xbt in measurements],
            z=[xbt.min_depth for xbt in measurements],
            t=[xbt.spacetime.time for xbt in measurements],
            max_depth=max_depths,
            min_depth=[xbt.min_depth for xbt in measurements],
            fall_speed=[xbt.fall_speed for xbt in measurements],
            deceleration_coefficient=[
                xbt.deceleration_coefficient for xbt in measurements
            ],
        )

        # add initial conditions to sampling variables
        self._sample_initial(xbt_particleset, fieldset, xbt_config.sensors)

        out_file = ParticleFile(path=out_path, outputdt=OUTPUT_DT)

        # build kernel list from active sensors only
        sampling_kernels = [
            self.sensor_kernels[sc.sensor_type]
            for sc in xbt_config.sensors
            if sc.enabled and sc.sensor_type in self.sensor_kernels
        ]

        xbt_particleset.execute(
            [*sampling_kernels, _xbt_cast],
            endtime=fieldset_endtime,
            dt=DT,
            verbose_progress=self.verbose_progress,
            output_file=out_file,
        )

        # there should be no particles left, as they delete themselves when they finish profiling
        if len(xbt_particleset._data["x"]) != 0:
            raise ValueError(
                "Simulation ended before XBT finished profiling. This most likely means the field time dimension did not match the simulation time span."
            )
