from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import copernicusmarine
from parcels import FieldSet

from virtualship.models import Expedition

# TODO: very bodgy
#! Toggle on for first time running in session...
# copernicusmarine.login()

PHYS_REANALYSIS_ID = "cmems_mod_glo_phy_my_0.083deg_P1D-m"
BGC_RENALYSIS_ID = "cmems_mod_glo_bgc_my_0.25deg_P1D-m"


@dataclass
class InputData:
    """A collection of fieldsets that function as input data for simulation."""

    adcp_fieldset: FieldSet | None
    argo_float_fieldset: FieldSet | None
    ctd_fieldset: FieldSet | None  # TODO
    ctd_bgc_fieldset: FieldSet | None  # TODO
    drifter_fieldset: FieldSet | None  # TODO
    xbt_fieldset: FieldSet | None
    ship_underwater_st_fieldset: FieldSet | None

    @classmethod
    def load(
        cls,
        directory: str | Path,
        load_adcp: bool,
        load_argo_float: bool,
        load_ctd: bool,
        load_ctd_bgc: bool,
        load_drifter: bool,
        load_xbt: bool,
        load_ship_underwater_st: bool,
        expedition: Expedition,
    ) -> InputData:
        """Create an instance of this class from copernicusmarine-sourced ds."""
        directory = Path(directory)

        if load_drifter:
            drifter_fieldset = cls._load_drifter_fieldset(expedition)
        else:
            drifter_fieldset = None
        if load_argo_float:
            argo_float_fieldset = cls._load_argo_float_fieldset(directory)
        else:
            argo_float_fieldset = None
        if load_ctd_bgc:
            ctd_bgc_fieldset = cls._load_ctd_bgc_fieldset(expedition)
        else:
            ctd_bgc_fieldset = None
        if load_adcp or load_ctd or load_ship_underwater_st or load_xbt:
            ship_fieldset = cls._load_ship_fieldset(expedition)
        if load_adcp:
            adcp_fieldset = ship_fieldset
        else:
            adcp_fieldset = None
        if load_ctd:
            ctd_fieldset = ship_fieldset
        else:
            ctd_fieldset = None
        if load_ship_underwater_st:
            ship_underwater_st_fieldset = ship_fieldset
        else:
            ship_underwater_st_fieldset = None
        if load_xbt:
            xbt_fieldset = ship_fieldset
        else:
            xbt_fieldset = None

        return InputData(
            adcp_fieldset=adcp_fieldset,
            argo_float_fieldset=argo_float_fieldset,
            ctd_fieldset=ctd_fieldset,
            ctd_bgc_fieldset=ctd_bgc_fieldset,
            drifter_fieldset=drifter_fieldset,
            xbt_fieldset=xbt_fieldset,
            ship_underwater_st_fieldset=ship_underwater_st_fieldset,
        )

    # TODO
    @classmethod
    def _load_ship_fieldset(cls, expedition: Expedition) -> FieldSet:
        ds = copernicusmarine.open_dataset(
            dataset_id=PHYS_REANALYSIS_ID,
            dataset_part="default",  # no idea what this means tbh
            minimum_longitude=expedition.schedule.space_time_region.spatial_range.minimum_longitude,
            maximum_longitude=expedition.schedule.space_time_region.spatial_range.maximum_longitude,
            minimum_latitude=expedition.schedule.space_time_region.spatial_range.minimum_latitude,
            maximum_latitude=expedition.schedule.space_time_region.spatial_range.maximum_latitude,
            variables=["uo", "vo", "so", "thetao"],
            start_datetime=expedition.schedule.space_time_region.time_range.start_time,
            end_datetime=expedition.schedule.space_time_region.time_range.end_time,
            coordinates_selection_method="outside",
        )

        variables = {"U": "uo", "V": "vo", "S": "so", "T": "thetao"}
        dimensions = {
            "lon": "longitude",
            "lat": "latitude",
            "time": "time",
            "depth": "depth",
        }

        # create the fieldset and set interpolation methods
        fieldset = FieldSet.from_xarray_dataset(
            ds, variables, dimensions, allow_time_extrapolation=True
        )
        fieldset.T.interp_method = "linear_invdist_land_tracer"
        fieldset.S.interp_method = "linear_invdist_land_tracer"

        # make depth negative
        for g in fieldset.gridset.grids:
            g.negate_depth()

        # add bathymetry data
        ds_bathymetry = copernicusmarine.open_dataset(
            dataset_id="cmems_mod_glo_phy_my_0.083deg_static",
            # dataset_part="default",  # no idea what this means tbh
            minimum_longitude=expedition.schedule.space_time_region.spatial_range.minimum_longitude,
            maximum_longitude=expedition.schedule.space_time_region.spatial_range.maximum_longitude,
            minimum_latitude=expedition.schedule.space_time_region.spatial_range.minimum_latitude,
            maximum_latitude=expedition.schedule.space_time_region.spatial_range.maximum_latitude,
            variables=["deptho"],
            start_datetime=expedition.schedule.space_time_region.time_range.start_time,
            end_datetime=expedition.schedule.space_time_region.time_range.end_time,
            coordinates_selection_method="outside",
        )
        bathymetry_variables = {"bathymetry": "deptho"}
        bathymetry_dimensions = {"lon": "longitude", "lat": "latitude"}
        bathymetry_field = FieldSet.from_xarray_dataset(
            ds_bathymetry, bathymetry_variables, bathymetry_dimensions
        )
        # make depth negative
        bathymetry_field.bathymetry.data = -bathymetry_field.bathymetry.data
        fieldset.add_field(bathymetry_field.bathymetry)

        return fieldset

    # TODO
    @classmethod
    def _load_ctd_bgc_fieldset(cls, expedition: Expedition) -> FieldSet:
        ds = copernicusmarine.open_dataset(
            dataset_id=BGC_RENALYSIS_ID,
            # dataset_part="default",  # no idea what this means tbh
            minimum_longitude=expedition.schedule.space_time_region.spatial_range.minimum_longitude,
            maximum_longitude=expedition.schedule.space_time_region.spatial_range.maximum_longitude,
            minimum_latitude=expedition.schedule.space_time_region.spatial_range.minimum_latitude,
            maximum_latitude=expedition.schedule.space_time_region.spatial_range.maximum_latitude,
            # variables=["o2", "chl", "no3", "po4", "ph", "phyc", "nppv"],
            variables=["o2", "chl", "no3", "po4", "nppv"],
            start_datetime=expedition.schedule.space_time_region.time_range.start_time,
            end_datetime=expedition.schedule.space_time_region.time_range.end_time,
            coordinates_selection_method="outside",
        )

        variables = {
            "o2": "o2",
            "chl": "chl",
            "no3": "no3",
            "po4": "po4",
            # "ph": "ph",
            # "phyc": "phyc",
            "nppv": "nppv",
        }
        dimensions = {
            "lon": "longitude",
            "lat": "latitude",
            "time": "time",
            "depth": "depth",
        }

        fieldset = FieldSet.from_xarray_dataset(
            ds, variables, dimensions, allow_time_extrapolation=True
        )
        fieldset.o2.interp_method = "linear_invdist_land_tracer"
        fieldset.chl.interp_method = "linear_invdist_land_tracer"
        fieldset.no3.interp_method = "linear_invdist_land_tracer"
        fieldset.po4.interp_method = "linear_invdist_land_tracer"
        # fieldset.ph.interp_method = "linear_invdist_land_tracer"
        # fieldset.phyc.interp_method = "linear_invdist_land_tracer"
        fieldset.nppv.interp_method = "linear_invdist_land_tracer"

        # add bathymetry data
        ds_bathymetry = copernicusmarine.open_dataset(
            dataset_id="cmems_mod_glo_phy_my_0.083deg_static",
            # dataset_part="default",  # no idea what this means tbh
            minimum_longitude=expedition.schedule.space_time_region.spatial_range.minimum_longitude,
            maximum_longitude=expedition.schedule.space_time_region.spatial_range.maximum_longitude,
            minimum_latitude=expedition.schedule.space_time_region.spatial_range.minimum_latitude,
            maximum_latitude=expedition.schedule.space_time_region.spatial_range.maximum_latitude,
            variables=["deptho"],
            start_datetime=expedition.schedule.space_time_region.time_range.start_time,
            end_datetime=expedition.schedule.space_time_region.time_range.end_time,
            coordinates_selection_method="outside",
        )
        bathymetry_variables = {"bathymetry": "deptho"}
        bathymetry_dimensions = {"lon": "longitude", "lat": "latitude"}
        bathymetry_field = FieldSet.from_xarray_dataset(
            ds_bathymetry, bathymetry_variables, bathymetry_dimensions
        )
        # make depth negative
        bathymetry_field.bathymetry.data = -bathymetry_field.bathymetry.data
        fieldset.add_field(bathymetry_field.bathymetry)

        return fieldset

    # TODO
    @classmethod
    def _load_drifter_fieldset(cls, expedition: Expedition) -> FieldSet:
        ds = copernicusmarine.open_dataset(
            dataset_id=PHYS_REANALYSIS_ID,
            dataset_part="default",  # no idea what this means tbh
            minimum_longitude=expedition.schedule.space_time_region.spatial_range.minimum_longitude,
            maximum_longitude=expedition.schedule.space_time_region.spatial_range.maximum_longitude,
            minimum_latitude=expedition.schedule.space_time_region.spatial_range.minimum_latitude,
            maximum_latitude=expedition.schedule.space_time_region.spatial_range.maximum_latitude,
            variables=["uo", "vo", "thetao"],
            start_datetime=expedition.schedule.space_time_region.time_range.start_time,
            end_datetime=expedition.schedule.space_time_region.time_range.end_time,
            coordinates_selection_method="outside",
        )

        variables = {"U": "uo", "V": "vo", "T": "thetao"}
        dimensions = {
            "lon": "longitude",
            "lat": "latitude",
            "time": "time",
            "depth": "depth",
        }

        fieldset = FieldSet.from_xarray_dataset(
            ds, variables, dimensions, allow_time_extrapolation=False
        )
        fieldset.T.interp_method = "linear_invdist_land_tracer"

        # make depth negative
        for g in fieldset.gridset.grids:
            g.negate_depth()

        return fieldset

    @classmethod
    def _load_argo_float_fieldset(cls, directory: Path) -> FieldSet:
        filenames = {
            "U": directory.joinpath("argo_float_uv.nc"),
            "V": directory.joinpath("argo_float_uv.nc"),
            "S": directory.joinpath("argo_float_s.nc"),
            "T": directory.joinpath("argo_float_t.nc"),
        }
        variables = {"U": "uo", "V": "vo", "S": "so", "T": "thetao"}
        dimensions = {
            "lon": "longitude",
            "lat": "latitude",
            "time": "time",
            "depth": "depth",
        }

        fieldset = FieldSet.from_netcdf(
            filenames, variables, dimensions, allow_time_extrapolation=False
        )
        fieldset.T.interp_method = "linear_invdist_land_tracer"
        fieldset.S.interp_method = "linear_invdist_land_tracer"

        # make depth negative
        for g in fieldset.gridset.grids:
            if max(g.depth) > 0:
                g.negate_depth()

        # read in data already
        fieldset.computeTimeChunk(0, 1)

        return fieldset
