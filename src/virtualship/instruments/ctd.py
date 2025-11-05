from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, ClassVar

import numpy as np

from parcels import JITParticle, ParticleSet, Variable
from virtualship.instruments.base import InputDataset, Instrument
from virtualship.instruments.types import InstrumentType

if TYPE_CHECKING:
    from virtualship.models.spacetime import Spacetime
from virtualship.utils import add_dummy_UV, register_input_dataset, register_instrument

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
# SECTION: Particle Class
# =====================================================

_CTDParticle = JITParticle.add_variables(
    [
        Variable("salinity", dtype=np.float32, initial=np.nan),
        Variable("temperature", dtype=np.float32, initial=np.nan),
        Variable("raising", dtype=np.int8, initial=0.0),  # bool. 0 is False, 1 is True.
        Variable("max_depth", dtype=np.float32),
        Variable("min_depth", dtype=np.float32),
        Variable("winch_speed", dtype=np.float32),
    ]
)


# =====================================================
# SECTION: Kernels
# =====================================================


def _sample_temperature(particle, fieldset, time):
    particle.temperature = fieldset.T[time, particle.depth, particle.lat, particle.lon]


def _sample_salinity(particle, fieldset, time):
    particle.salinity = fieldset.S[time, particle.depth, particle.lat, particle.lon]


def _ctd_cast(particle, fieldset, time):
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
# SECTION: InputDataset Class
# =====================================================


@register_input_dataset(InstrumentType.CTD)
class CTDInputDataset(InputDataset):
    """Input dataset for CTD instrument."""

    DOWNLOAD_BUFFERS: ClassVar[dict] = {
        "latlon_degrees": 0.0,
        "days": 0.0,
    }  # CTD data requires no buffers

    def __init__(self, data_dir, credentials, space_time_region):
        """Initialise with instrument's name."""
        super().__init__(
            CTD.name,
            self.DOWNLOAD_BUFFERS["latlon_degrees"],
            self.DOWNLOAD_BUFFERS["days"],
            space_time_region.spatial_range.minimum_depth,
            space_time_region.spatial_range.maximum_depth,
            data_dir,
            credentials,
            space_time_region,
        )

    def get_datasets_dict(self) -> dict:
        """Get variable specific args for instrument."""
        return {
            "Sdata": {
                "physical": True,
                "variables": ["so"],
                "output_filename": f"{self.name}_s.nc",
            },
            "Tdata": {
                "physical": True,
                "variables": ["thetao"],
                "output_filename": f"{self.name}_t.nc",
            },
        }


# =====================================================
# SECTION: Instrument Class
# =====================================================


@register_instrument(InstrumentType.CTD)
class CTDInstrument(Instrument):
    """CTD instrument class."""

    def __init__(self, expedition, directory, from_copernicusmarine):
        """Initialize CTDInstrument."""
        filenames = {
            "S": f"{CTD.name}_s.nc",
            "T": f"{CTD.name}_t.nc",
        }
        variables = {"S": "so", "T": "thetao"}

        super().__init__(
            CTD.name,
            expedition,
            directory,
            filenames,
            variables,
            add_bathymetry=True,
            allow_time_extrapolation=True,
            verbose_progress=False,
            from_copernicusmarine=from_copernicusmarine,
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

        # add dummy U
        add_dummy_UV(fieldset)  # TODO: parcels v3 bodge; remove when parcels v4 is used

        fieldset_starttime = fieldset.T.grid.time_origin.fulltime(
            fieldset.T.grid.time_full[0]
        )
        fieldset_endtime = fieldset.T.grid.time_origin.fulltime(
            fieldset.T.grid.time_full[-1]
        )

        # deploy time for all ctds should be later than fieldset start time
        if not all(
            [
                np.datetime64(ctd.spacetime.time) >= fieldset_starttime
                for ctd in measurements
            ]
        ):
            raise ValueError("CTD deployed before fieldset starts.")

        # depth the ctd will go to. shallowest between ctd max depth and bathymetry.
        max_depths = [
            max(
                ctd.max_depth,
                fieldset.bathymetry.eval(
                    z=0,
                    y=ctd.spacetime.location.lat,
                    x=ctd.spacetime.location.lon,
                    time=0,
                ),
            )
            for ctd in measurements
        ]

        # CTD depth can not be too shallow, because kernel would break.
        # This shallow is not useful anyway, no need to support.
        if not all([max_depth <= -DT * WINCH_SPEED for max_depth in max_depths]):
            raise ValueError(
                f"CTD max_depth or bathymetry shallower than maximum {-DT * WINCH_SPEED}"
            )

        # define parcel particles
        ctd_particleset = ParticleSet(
            fieldset=fieldset,
            pclass=_CTDParticle,
            lon=[ctd.spacetime.location.lon for ctd in measurements],
            lat=[ctd.spacetime.location.lat for ctd in measurements],
            depth=[ctd.min_depth for ctd in measurements],
            time=[ctd.spacetime.time for ctd in measurements],
            max_depth=max_depths,
            min_depth=[ctd.min_depth for ctd in measurements],
            winch_speed=[WINCH_SPEED for _ in measurements],
        )

        # define output file for the simulation
        out_file = ctd_particleset.ParticleFile(name=out_path, outputdt=OUTPUT_DT)

        # execute simulation
        ctd_particleset.execute(
            [_sample_salinity, _sample_temperature, _ctd_cast],
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
