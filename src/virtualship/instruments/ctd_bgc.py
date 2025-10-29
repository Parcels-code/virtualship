from dataclasses import dataclass
from datetime import timedelta
from typing import ClassVar

import numpy as np

from parcels import JITParticle, ParticleSet, Variable
from virtualship.instruments.base import InputDataset, Instrument
from virtualship.instruments.types import InstrumentType
from virtualship.models.spacetime import Spacetime
from virtualship.utils import register_input_dataset, register_instrument


@dataclass
class CTD_BGC:
    """CTD_BGC configuration."""

    name: ClassVar[str] = "CTD_BGC"
    spacetime: Spacetime
    min_depth: float
    max_depth: float


_CTD_BGCParticle = JITParticle.add_variables(
    [
        Variable("o2", dtype=np.float32, initial=np.nan),
        Variable("chl", dtype=np.float32, initial=np.nan),
        Variable("no3", dtype=np.float32, initial=np.nan),
        Variable("po4", dtype=np.float32, initial=np.nan),
        Variable("ph", dtype=np.float32, initial=np.nan),
        Variable("phyc", dtype=np.float32, initial=np.nan),
        Variable("nppv", dtype=np.float32, initial=np.nan),
        Variable("raising", dtype=np.int8, initial=0.0),  # bool. 0 is False, 1 is True.
        Variable("max_depth", dtype=np.float32),
        Variable("min_depth", dtype=np.float32),
        Variable("winch_speed", dtype=np.float32),
    ]
)


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


@register_input_dataset(InstrumentType.CTD_BGC)
class CTD_BGCInputDataset(InputDataset):
    """Input dataset object for CTD_BGC instrument."""

    DOWNLOAD_BUFFERS: ClassVar[dict] = {
        "latlon_degrees": 0.0,
        "days": 0.0,
    }  # CTD_BGC data requires no buffers

    def __init__(self, data_dir, credentials, space_time_region):
        """Initialise with instrument's name."""
        super().__init__(
            CTD_BGC.name,
            self.DOWNLOAD_BUFFERS["latlon_degrees"],
            self.DOWNLOAD_BUFFERS["days"],
            space_time_region.spatial_range.minimum_depth,
            space_time_region.spatial_range.maximum_depth,
            data_dir,
            credentials,
            space_time_region,
        )

    def get_datasets_dict(self) -> dict:
        """Variable specific args for instrument."""
        return {
            "o2data": {
                "physical": False,
                "variables": ["o2"],
                "output_filename": f"{self.name}_o2.nc",
            },
            "chlorodata": {
                "physical": False,
                "variables": ["chl"],
                "output_filename": f"{self.name}_chl.nc",
            },
            "nitratedata": {
                "physical": False,
                "variables": ["no3"],
                "output_filename": f"{self.name}_no3.nc",
            },
            "phosphatedata": {
                "physical": False,
                "variables": ["po4"],
                "output_filename": f"{self.name}_po4.nc",
            },
            "phdata": {
                "physical": False,
                "variables": ["ph"],
                "output_filename": f"{self.name}_ph.nc",
            },
            "phytoplanktondata": {
                "physical": False,
                "variables": ["phyc"],
                "output_filename": f"{self.name}_phyc.nc",
            },
            "primaryproductiondata": {
                "physical": False,
                "variables": ["nppv"],
                "output_filename": f"{self.name}_nppv.nc",
            },
        }


@register_instrument(InstrumentType.CTD_BGC)
class CTD_BGCInstrument(Instrument):
    """CTD_BGC instrument class."""

    def __init__(self, expedition, directory):
        """Initialize CTD_BGCInstrument."""
        filenames = {
            "o2": f"{CTD_BGC.name}_o2.nc",
            "chl": f"{CTD_BGC.name}_chl.nc",
            "no3": f"{CTD_BGC.name}_no3.nc",
            "po4": f"{CTD_BGC.name}_po4.nc",
            "ph": f"{CTD_BGC.name}_ph.nc",
            "phyc": f"{CTD_BGC.name}_phyc.nc",
            "nppv": f"{CTD_BGC.name}_nppv.nc",
        }
        variables = {
            "o2": "o2",
            "chl": "chl",
            "no3": "no3",
            "po4": "po4",
            "ph": "ph",
            "phyc": "phyc",
            "nppv": "nppv",
        }
        super().__init__(
            CTD_BGC.name,
            expedition,
            directory,
            filenames,
            variables,
            add_bathymetry=True,
            allow_time_extrapolation=True,
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

        fieldset_starttime = fieldset.time_origin.fulltime(fieldset.U.grid.time_full[0])
        fieldset_endtime = fieldset.time_origin.fulltime(fieldset.U.grid.time_full[-1])

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
            for ctd_bgc in self.measurements
        ]

        # CTD depth can not be too shallow, because kernel would break.
        # This shallow is not useful anyway, no need to support.
        if not all([max_depth <= -DT * WINCH_SPEED for max_depth in max_depths]):
            raise ValueError(
                f"BGC CTD max_depth or bathymetry shallower than maximum {-DT * WINCH_SPEED}"
            )

        # define parcel particles
        ctd_bgc_particleset = ParticleSet(
            fieldset=fieldset,
            pclass=_CTD_BGCParticle,
            lon=[ctd_bgc.spacetime.location.lon for ctd_bgc in self.measurements],
            lat=[ctd_bgc.spacetime.location.lat for ctd_bgc in self.measurements],
            depth=[ctd_bgc.min_depth for ctd_bgc in self.measurements],
            time=[ctd_bgc.spacetime.time for ctd_bgc in self.measurements],
            max_depth=max_depths,
            min_depth=[ctd_bgc.min_depth for ctd_bgc in self.measurements],
            winch_speed=[WINCH_SPEED for _ in self.measurements],
        )

        # define output file for the simulation
        out_file = ctd_bgc_particleset.ParticleFile(name=out_path, outputdt=OUTPUT_DT)

        # execute simulation
        ctd_bgc_particleset.execute(
            [
                _sample_o2,
                _sample_chlorophyll,
                _sample_nitrate,
                _sample_phosphate,
                _sample_ph,
                _sample_phytoplankton,
                _sample_primary_production,
                _ctd_bgc_cast,
            ],
            endtime=fieldset_endtime,
            dt=DT,
            verbose_progress=False,
            output_file=out_file,
        )

        # there should be no particles left, as they delete themselves when they resurface
        if len(ctd_bgc_particleset.particledata) != 0:
            raise ValueError(
                "Simulation ended before BGC CTD resurfaced. This most likely means the field time dimension did not match the simulation time span."
            )
