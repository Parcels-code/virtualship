from dataclasses import dataclass
from datetime import timedelta
from typing import ClassVar

import numpy as np

from parcels import ParticleSet, Variable
from virtualship.instruments.base import Instrument
from virtualship.instruments.types import InstrumentType, SensorType
from virtualship.models.spacetime import Spacetime
from virtualship.utils import (
    add_dummy_UV,
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
# SECTION: fixed/mechanical Particle Variables (non-sampling)
# =====================================================

_XBT_FIXED_VARIABLES = [
    Variable("max_depth", dtype=np.float32),
    Variable("min_depth", dtype=np.float32),
    Variable("fall_speed", dtype=np.float32),
    Variable("deceleration_coefficient", dtype=np.float32),
]


# =====================================================
# SECTION: Kernels
# =====================================================


def _sample_temperature(particle, fieldset, time):
    particle.temperature = fieldset.T[time, particle.depth, particle.lat, particle.lon]


_XBT_SENSOR_KERNELS: dict[SensorType, callable] = {
    SensorType.TEMPERATURE: _sample_temperature,
}


def _xbt_cast(particle, fieldset, time):
    particle_ddepth = -particle.fall_speed * particle.dt

    # update the fall speed from the quadractic fall-rate equation
    # check https://doi.org/10.5194/os-7-231-2011
    particle.fall_speed = (
        particle.fall_speed - 2 * particle.deceleration_coefficient * particle.dt
    )

    # delete particle if depth is exactly max_depth
    if particle.depth == particle.max_depth:
        particle.delete()

    # set particle depth to max depth if it's too deep
    if particle.depth + particle_ddepth < particle.max_depth:
        particle_ddepth = particle.max_depth - particle.depth


# =====================================================
# SECTION: Instrument Class
# =====================================================


@register_instrument(InstrumentType.XBT)
class XBTInstrument(Instrument):
    """XBT instrument class."""

    def __init__(self, expedition, from_data):
        """Initialize XBTInstrument."""
        variables = expedition.instruments_config.xbt_config.active_variables()
        limit_spec = {
            "spatial": True
        }  # spatial limits; lat/lon constrained to waypoint locations + buffer

        super().__init__(
            expedition,
            variables,
            add_bathymetry=True,
            allow_time_extrapolation=True,
            verbose_progress=False,
            spacetime_buffer_size=None,
            limit_spec=limit_spec,
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

        # add dummy U
        add_dummy_UV(fieldset)  # TODO: parcels v3 bodge; remove when parcels v4 is used

        # use first active field for time reference
        _time_ref_key = next(iter(self.variables))
        _time_ref_field = getattr(fieldset, _time_ref_key)
        fieldset_starttime = _time_ref_field.grid.time_origin.fulltime(
            _time_ref_field.grid.time_full[0]
        )
        fieldset_endtime = _time_ref_field.grid.time_origin.fulltime(
            _time_ref_field.grid.time_full[-1]
        )

        # deploy time for all xbts should be later than fieldset start time
        if not all(
            [
                np.datetime64(xbt.spacetime.time) >= fieldset_starttime
                for xbt in measurements
            ]
        ):
            raise ValueError("XBT deployed before fieldset starts.")

        # depth the xbt will go to. shallowest between xbt max depth and bathymetry.
        max_depths = [
            max(
                xbt.max_depth,
                fieldset.bathymetry.eval(
                    z=0,
                    y=xbt.spacetime.location.lat,
                    x=xbt.spacetime.location.lon,
                    time=0,
                ),
            )
            for xbt in measurements
        ]

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
            xbt_config.sensors, _XBT_FIXED_VARIABLES
        )

        # define xbt particles
        xbt_particleset = ParticleSet(
            fieldset=fieldset,
            pclass=_XBTParticle,
            lon=[xbt.spacetime.location.lon for xbt in measurements],
            lat=[xbt.spacetime.location.lat for xbt in measurements],
            depth=[xbt.min_depth for xbt in measurements],
            time=[xbt.spacetime.time for xbt in measurements],
            max_depth=max_depths,
            min_depth=[xbt.min_depth for xbt in measurements],
            fall_speed=[xbt.fall_speed for xbt in measurements],
        )

        out_file = xbt_particleset.ParticleFile(name=out_path, outputdt=OUTPUT_DT)

        # build kernel list from active sensors only
        sampling_kernels = [
            _XBT_SENSOR_KERNELS[sc.sensor_type]
            for sc in xbt_config.sensors
            if sc.enabled and sc.sensor_type in _XBT_SENSOR_KERNELS
        ]

        xbt_particleset.execute(
            [*sampling_kernels, _xbt_cast],
            endtime=fieldset_endtime,
            dt=DT,
            verbose_progress=self.verbose_progress,
            output_file=out_file,
        )

        # there should be no particles left, as they delete themselves when they finish profiling
        if len(xbt_particleset.particledata) != 0:
            raise ValueError(
                "Simulation ended before XBT finished profiling. This most likely means the field time dimension did not match the simulation time span."
            )
