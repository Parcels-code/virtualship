from dataclasses import dataclass
from typing import ClassVar

from virtualship.models import Spacetime, instruments


@dataclass
class CTD_BGC:
    """CTD_BGC configuration."""

    name: ClassVar[str] = "CTD_BGC"
    spacetime: Spacetime
    min_depth: float
    max_depth: float


# ---------------
# TODO: KERNELS
# ---------------


class CTD_BGCInputDataset(instruments.InputDataset):
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

    def datasets_dir(self) -> dict:
        """Variable specific args for instrument."""
        return {
            "o2data": {
                "dataset_id": "cmems_mod_glo_bgc-bio_anfc_0.25deg_P1D-m",
                "variables": ["o2"],
                "output_filename": "ctd_bgc_o2.nc",
            },
            "chlorodata": {
                "dataset_id": "cmems_mod_glo_bgc-pft_anfc_0.25deg_P1D-m",
                "variables": ["chl"],
                "output_filename": "ctd_bgc_chl.nc",
            },
            "nitratedata": {
                "dataset_id": "cmems_mod_glo_bgc-nut_anfc_0.25deg_P1D-m",
                "variables": ["no3"],
                "output_filename": "ctd_bgc_no3.nc",
            },
            "phosphatedata": {
                "dataset_id": "cmems_mod_glo_bgc-nut_anfc_0.25deg_P1D-m",
                "variables": ["po4"],
                "output_filename": "ctd_bgc_po4.nc",
            },
            "phdata": {
                "dataset_id": "cmems_mod_glo_bgc-car_anfc_0.25deg_P1D-m",
                "variables": ["ph"],
                "output_filename": "ctd_bgc_ph.nc",
            },
            "phytoplanktondata": {
                "dataset_id": "cmems_mod_glo_bgc-pft_anfc_0.25deg_P1D-m",
                "variables": ["phyc"],
                "output_filename": "ctd_bgc_phyc.nc",
            },
            "zooplanktondata": {
                "dataset_id": "cmems_mod_glo_bgc-plankton_anfc_0.25deg_P1D-m",
                "variables": ["zooc"],
                "output_filename": "ctd_bgc_zooc.nc",
            },
            "primaryproductiondata": {
                "dataset_id": "cmems_mod_glo_bgc-bio_anfc_0.25deg_P1D-m",
                "variables": ["nppv"],
                "output_filename": "ctd_bgc_nppv.nc",
            },
        }


class CTD_BGCInstrument(instruments.Instrument):
    """CTD_BGC instrument class."""

    def __init__(
        self,
        config,
        input_dataset,
        kernels,
    ):
        """Initialise with instrument's name."""
        super().__init__(CTD_BGC.name, config, input_dataset, kernels)

    def simulate(self):
        """Simulate measurements."""
        ...
