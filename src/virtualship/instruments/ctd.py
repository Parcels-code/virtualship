from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, ClassVar

import numpy as np
from parcels import ParticleFile, ParticleSet, Variable
from parcels._core.statuscodes import StatusCode

from virtualship.instruments.base import Instrument
from virtualship.instruments.sensors import SensorType
from virtualship.instruments.types import InstrumentType
from virtualship.utils import (
    _compute_max_depths,
    build_particle_class_from_sensors,
    register_instrument,
)

if TYPE_CHECKING:
    from virtualship.models.spacetime import Spacetime

# =====================================================
# SECTION: Dataclass
# =====================================================


@dataclass
class CTD:
    """CTD configuration."""

    name: ClassVar[str] = "CTD"
    spacetime: "Spacetime"
    min_depth: float
    max_depth: float


# =====================================================
# SECTION: non-sensor Particle Variables (non-sampling)
# =====================================================

_CTD_NONSENSOR_VARIABLES = [
    Variable("raising", dtype=np.int8, initial=0.0),  # bool. 0 is False, 1 is True.
    Variable("max_depth", dtype=np.float32),
    Variable("min_depth", dtype=np.float32),
    Variable("winch_speed", dtype=np.float32),
]


# =====================================================
# SECTION: Kernels
# =====================================================

## physical variables


def _sample_temperature(particles, fieldset):
    particles.temperature = fieldset.T[
        particles.time, particles.z, particles.lat, particles.lon
    ]


def _sample_salinity(particles, fieldset):
    particles.salinity = fieldset.S[
        particles.time, particles.z, particles.lat, particles.lon
    ]


## bgc variables


def _sample_o2(particles, fieldset):
    particles.o2 = fieldset.o2[
        particles.time, particles.z, particles.lat, particles.lon
    ]


def _sample_chlorophyll(particles, fieldset):
    particles.chl = fieldset.chl[
        particles.time, particles.z, particles.lat, particles.lon
    ]


def _sample_nitrate(particles, fieldset):
    particles.no3 = fieldset.no3[
        particles.time, particles.z, particles.lat, particles.lon
    ]


def _sample_phosphate(particles, fieldset):
    particles.po4 = fieldset.po4[
        particles.time, particles.z, particles.lat, particles.lon
    ]


def _sample_ph(particles, fieldset):
    particles.ph = fieldset.ph[
        particles.time, particles.z, particles.lat, particles.lon
    ]


def _sample_phytoplankton(particles, fieldset):
    particles.phyc = fieldset.phyc[
        particles.time, particles.z, particles.lat, particles.lon
    ]


def _sample_primary_production(particles, fieldset):
    particles.nppv = fieldset.nppv[
        particles.time, particles.z, particles.lat, particles.lon
    ]


## cast


def _ctd_cast(particles, fieldset):
    particles_lowering = particles[particles.raising == 0]
    particles_raising = particles[particles.raising == 1]

    # TODO: change to boolean masking, like with Argo Floats?
    # TODO: different handling of positive down for z now?! Doing positive down now... think kernels need adjusting...
    # TODO: need to check on all other instrument kernels as well...
    # TODO: plus how the configs are inputted in e.g. expedition.yaml

    # lowering
    particles_lowering.dz = -particles_lowering.winch_speed * particles_lowering.dt
    particles_lowering.raising = np.where(
        particles_lowering.z + particles_lowering.dz < particles_lowering.max_depth,
        1,
        particles_lowering.raising,
    )

    # raising
    particles_raising.dz = particles_raising.winch_speed * particles_raising.dt
    particles_raising.state = np.where(
        particles_raising.z + particles_raising.dz > particles_raising.min_depth,
        StatusCode.Delete,
        particles_raising.state,
    )


# =====================================================
# SECTION: Instrument Class
# =====================================================


@register_instrument(InstrumentType.CTD)
class CTDInstrument(Instrument):
    """CTD instrument class."""

    sensor_kernels: ClassVar[dict[SensorType, Callable]] = {
        SensorType.TEMPERATURE: _sample_temperature,
        SensorType.SALINITY: _sample_salinity,
        SensorType.OXYGEN: _sample_o2,
        SensorType.CHLOROPHYLL: _sample_chlorophyll,
        SensorType.NITRATE: _sample_nitrate,
        SensorType.PHOSPHATE: _sample_phosphate,
        SensorType.PH: _sample_ph,
        SensorType.PHYTOPLANKTON: _sample_phytoplankton,
        SensorType.PRIMARY_PRODUCTION: _sample_primary_production,
    }

    def __init__(self, expedition, from_data):
        """Initialize CTDInstrument."""
        variables = expedition.instruments_config.ctd_config.active_variables()
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
        """Simulate CTD measurements."""
        WINCH_SPEED = 1.0  # sink and rise speed in m/s
        DT = 10.0  # dt of CTD simulation integrator
        OUTPUT_DT = timedelta(seconds=10)  # output dt for CTD simulation

        if len(measurements) == 0:
            print(
                "No CTDs provided. Parcels currently crashes when providing an empty particle set, so no CTD simulation will be done and no files will be created."
            )
            # TODO when Parcels supports it this check can be removed.
            return

        fieldset = self.load_input_data()

        # use first active field for time reference
        _time_ref_key = next(iter(self.variables))
        _time_ref_field = getattr(fieldset, _time_ref_key)

        fieldset_starttime = _time_ref_field.data.time.isel(time=0)
        fieldset_endtime = _time_ref_field.data.time.isel(time=-1)

        # deploy time for all ctds should be later than fieldset start time
        if not all(
            [
                np.datetime64(ctd.spacetime.time) >= fieldset_starttime
                for ctd in measurements
            ]
        ):
            raise ValueError("CTD deployed before fieldset starts.")

        # depth the ctd will go to. shallowest between ctd max depth and bathymetry.
        max_depths = _compute_max_depths(measurements, fieldset)

        # CTD depth can not be too shallow, because kernel would break.
        # This shallow is not useful anyway, no need to support.
        if not all([max_depth <= -DT * WINCH_SPEED for max_depth in max_depths]):
            raise ValueError(
                f"CTD max_depth or bathymetry shallower than maximum {-DT * WINCH_SPEED}"
            )

        # build dynamic particle class from the active sensors
        ctd_config = self.expedition.instruments_config.ctd_config
        _CTDParticle = build_particle_class_from_sensors(
            ctd_config.sensors, _CTD_NONSENSOR_VARIABLES
        )

        # define parcel particles
        ctd_particleset = ParticleSet(
            fieldset=fieldset,
            pclass=_CTDParticle,
            lon=[ctd.spacetime.location.lon for ctd in measurements],
            lat=[ctd.spacetime.location.lat for ctd in measurements],
            z=[ctd.min_depth for ctd in measurements],
            time=[np.datetime64(ctd.spacetime.time) for ctd in measurements],
            max_depth=max_depths,
            min_depth=[ctd.min_depth for ctd in measurements],
            winch_speed=[WINCH_SPEED for _ in measurements],
        )

        # define output file for the simulation
        out_file = ParticleFile(path=out_path, outputdt=OUTPUT_DT)

        # build kernel list from active sensors only
        sampling_kernels = [
            self.sensor_kernels[sc.sensor_type]
            for sc in ctd_config.sensors
            if sc.enabled and sc.sensor_type in self.sensor_kernels
        ]

        # execute simulation
        ctd_particleset.execute(
            [*sampling_kernels, _ctd_cast],
            endtime=fieldset_endtime,
            dt=DT,
            verbose_progress=self.verbose_progress,
            output_file=out_file,
        )

        # there should be no particles left, as they delete themselves when they resurface
        if len(ctd_particleset.particledata) != 0:
            raise ValueError(
                "Simulation ended before CTD resurfaced. This most likely means the field time dimension did not match the simulation time span."
            )
