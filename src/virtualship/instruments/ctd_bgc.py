from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import ClassVar

import numpy as np

from parcels import JITParticle, ParticleSet, Variable
from virtualship.instruments.base import Instrument
from virtualship.instruments.sensors import SensorType
from virtualship.instruments.types import InstrumentType
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
class CTD_BGC:
    """CTD_BGC configuration."""

    name: ClassVar[str] = "CTD_BGC"
    spacetime: Spacetime
    min_depth: float
    max_depth: float


# =====================================================
# SECTION: non-sensor Particle Variables (non-sampling)
# =====================================================

_CTD_BGC_NONSENSOR_VARIABLES = [
    Variable("raising", dtype=np.int8, initial=0.0),  # bool. 0 is False, 1 is True.
    Variable("max_depth", dtype=np.float32),
    Variable("min_depth", dtype=np.float32),
    Variable("winch_speed", dtype=np.float32),
]

# =====================================================
# SECTION: Kernels
# =====================================================


def _sample_o2(particle, fieldset, time):
    particle.o2 = fieldset.o2[time, particle.depth, particle.lat, particle.lon]


def _sample_chlorophyll(particle, fieldset, time):
    particle.chl = fieldset.chl[time, particle.depth, particle.lat, particle.lon]


def _sample_nitrate(particle, fieldset, time):
    particle.no3 = fieldset.no3[time, particle.depth, particle.lat, particle.lon]


def _sample_phosphate(particle, fieldset, time):
    particle.po4 = fieldset.po4[time, particle.depth, particle.lat, particle.lon]


def _sample_ph(particle, fieldset, time):
    particle.ph = fieldset.ph[time, particle.depth, particle.lat, particle.lon]


def _sample_phytoplankton(particle, fieldset, time):
    particle.phyc = fieldset.phyc[time, particle.depth, particle.lat, particle.lon]


def _sample_primary_production(particle, fieldset, time):
    particle.nppv = fieldset.nppv[time, particle.depth, particle.lat, particle.lon]


def _ctd_bgc_cast(particle, fieldset, time):
    # lowering
    if particle.raising == 0:
        particle_ddepth = -particle.winch_speed * particle.dt
        if particle.depth + particle_ddepth < particle.max_depth:
            particle.raising = 1
            particle_ddepth = -particle_ddepth
    # raising
    else:
        particle_ddepth = particle.winch_speed * particle.dt
        if particle.depth + particle_ddepth > particle.min_depth:
            particle.delete()


# =====================================================
# SECTION: Instrument Class
# =====================================================


@register_instrument(InstrumentType.CTD_BGC)
class CTD_BGCInstrument(Instrument):
    """CTD_BGC instrument class."""

    sensor_kernels: ClassVar[dict[SensorType, Callable]] = {
        SensorType.OXYGEN: _sample_o2,
        SensorType.CHLOROPHYLL: _sample_chlorophyll,
        SensorType.NITRATE: _sample_nitrate,
        SensorType.PHOSPHATE: _sample_phosphate,
        SensorType.PH: _sample_ph,
        SensorType.PHYTOPLANKTON: _sample_phytoplankton,
        SensorType.PRIMARY_PRODUCTION: _sample_primary_production,
    }

    def __init__(self, expedition, from_data):
        """Initialize CTD_BGCInstrument."""
        variables = expedition.instruments_config.ctd_bgc_config.active_variables()
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
        """Simulate BGC CTD measurements using Parcels."""
        WINCH_SPEED = 1.0  # sink and rise speed in m/s
        DT = 10.0  # dt of CTD_BGC simulation integrator
        OUTPUT_DT = timedelta(seconds=10)  # output dt for CTD_BGC simulation

        if len(measurements) == 0:
            print(
                "No BGC CTDs provided. Parcels currently crashes when providing an empty particle set, so no BGC CTD simulation will be done and no files will be created."
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

        # deploy time for all ctds should be later than fieldset start time
        if not all(
            [
                np.datetime64(ctd_bgc.spacetime.time) >= fieldset_starttime
                for ctd_bgc in measurements
            ]
        ):
            raise ValueError("BGC CTD deployed before fieldset starts.")

        # depth the bgc ctd will go to. shallowest between bgc ctd max depth and bathymetry.
        max_depths = [
            max(
                ctd_bgc.max_depth,
                fieldset.bathymetry.eval(
                    z=0,
                    y=ctd_bgc.spacetime.location.lat,
                    x=ctd_bgc.spacetime.location.lon,
                    time=0,
                ),
            )
            for ctd_bgc in measurements
        ]

        # CTD depth can not be too shallow, because kernel would break.
        # This shallow is not useful anyway, no need to support.
        if not all([max_depth <= -DT * WINCH_SPEED for max_depth in max_depths]):
            raise ValueError(
                f"BGC CTD max_depth or bathymetry shallower than maximum {-DT * WINCH_SPEED}"
            )

        # build dynamic particle class from the active sensors
        ctd_bgc_config = self.expedition.instruments_config.ctd_bgc_config
        _CTD_BGCParticle = build_particle_class_from_sensors(
            ctd_bgc_config.sensors, _CTD_BGC_NONSENSOR_VARIABLES, JITParticle
        )

        # define parcel particles
        ctd_bgc_particleset = ParticleSet(
            fieldset=fieldset,
            pclass=_CTD_BGCParticle,
            lon=[ctd_bgc.spacetime.location.lon for ctd_bgc in measurements],
            lat=[ctd_bgc.spacetime.location.lat for ctd_bgc in measurements],
            depth=[ctd_bgc.min_depth for ctd_bgc in measurements],
            time=[ctd_bgc.spacetime.time for ctd_bgc in measurements],
            max_depth=max_depths,
            min_depth=[ctd_bgc.min_depth for ctd_bgc in measurements],
            winch_speed=[WINCH_SPEED for _ in measurements],
        )

        # define output file for the simulation
        out_file = ctd_bgc_particleset.ParticleFile(name=out_path, outputdt=OUTPUT_DT)

        # build kernel list from active sensors only
        sampling_kernels = [
            self.sensor_kernels[sc.sensor_type]
            for sc in ctd_bgc_config.sensors
            if sc.enabled and sc.sensor_type in self.sensor_kernels
        ]

        # execute simulation
        ctd_bgc_particleset.execute(
            [*sampling_kernels, _ctd_bgc_cast],
            endtime=fieldset_endtime,
            dt=DT,
            verbose_progress=self.verbose_progress,
            output_file=out_file,
        )

        # there should be no particles left, as they delete themselves when they resurface
        if len(ctd_bgc_particleset.particledata) != 0:
            raise ValueError(
                "Simulation ended before BGC CTD resurfaced. This most likely means the field time dimension did not match the simulation time span."
            )
