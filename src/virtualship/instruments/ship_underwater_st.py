from dataclasses import dataclass
from typing import ClassVar

import numpy as np
from parcels import ParticleSet, ScipyParticle, Variable

from virtualship.instruments.base import Instrument
from virtualship.instruments.types import InstrumentType
from virtualship.utils import add_dummy_UV, register_instrument

# =====================================================
# SECTION: Dataclass
# =====================================================


@dataclass
class Underwater_ST:
    """Underwater_ST configuration."""

    name: ClassVar[str] = "Underwater_ST"


# =====================================================
# SECTION: Particle Class
# =====================================================

_ShipSTParticle = ScipyParticle.add_variables(
    [
        Variable("S", dtype=np.float32, initial=np.nan),
        Variable("T", dtype=np.float32, initial=np.nan),
    ]
)

# =====================================================
# SECTION: Kernels
# =====================================================


# define function sampling Salinity
def _sample_salinity(particle, fieldset, time):
    particle.S = fieldset.S[time, particle.depth, particle.lat, particle.lon]


# define function sampling Temperature
def _sample_temperature(particle, fieldset, time):
    particle.T = fieldset.T[time, particle.depth, particle.lat, particle.lon]


# =====================================================
# SECTION: Instrument Class
# =====================================================


@register_instrument(InstrumentType.UNDERWATER_ST)
class Underwater_STInstrument(Instrument):
    """Underwater_ST instrument class."""

    def __init__(self, expedition, from_data):
        """Initialize Underwater_STInstrument."""
        variables = {"S": "so", "T": "thetao"}
        spacetime_buffer_size = {
            "latlon": 0.25,  # [degrees]
            "time": 0.0,  # [days]
        }

        super().__init__(
            expedition,
            variables,
            add_bathymetry=False,
            allow_time_extrapolation=True,
            verbose_progress=False,
            spacetime_buffer_size=spacetime_buffer_size,
            limit_spec=None,
            from_data=from_data,
        )

    def simulate(self, measurements, out_path) -> None:
        """Simulate underway salinity and temperature measurements."""
        DEPTH = -2.0

        measurements.sort(key=lambda p: p.time)

        fieldset = self.load_input_data()

        # add dummy U
        add_dummy_UV(fieldset)  # TODO: parcels v3 bodge; remove when parcels v4 is used

        particleset = ParticleSet.from_list(
            fieldset=fieldset,
            pclass=_ShipSTParticle,
            lon=0.0,
            lat=0.0,
            depth=DEPTH,
            time=0,
        )

        out_file = particleset.ParticleFile(name=out_path, outputdt=np.inf)

        for point in measurements:
            particleset.lon_nextloop[:] = point.location.lon
            particleset.lat_nextloop[:] = point.location.lat
            particleset.time_nextloop[:] = fieldset.time_origin.reltime(
                np.datetime64(point.time)
            )

            particleset.execute(
                [_sample_salinity, _sample_temperature],
                dt=1,
                runtime=1,
                verbose_progress=self.verbose_progress,
                output_file=out_file,
            )
