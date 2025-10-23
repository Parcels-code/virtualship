"""InputData class."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import xarray as xr
from parcels import Field, FieldSet


@dataclass
class InputData:
    """A collection of fieldsets that function as input data for simulation."""

    adcp_fieldset: FieldSet | None
    argo_float_fieldset: FieldSet | None
    ctd_fieldset: FieldSet | None
    ctd_bgc_fieldset: FieldSet | None
    drifter_fieldset: FieldSet | None
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
    ) -> InputData:
        """
        Create an instance of this class from netCDF files.

        For now this function makes a lot of assumption about file location and contents.

        :param directory: Input data directory.
        :param load_adcp: Whether to load the ADCP fieldset.
        :param load_argo_float: Whether to load the argo float fieldset.
        :param load_ctd: Whether to load the CTD fieldset.
        :param load_ctd_bgc: Whether to load the CTD BGC fieldset.
        :param load_drifter: Whether to load the drifter fieldset.
        :param load_ship_underwater_st: Whether to load the ship underwater ST fieldset.
        :returns: An instance of this class with loaded fieldsets.
        """
        directory = Path(directory)
        if load_drifter:
            drifter_fieldset = cls._load_drifter_fieldset(directory)
        else:
            drifter_fieldset = None
        if load_argo_float:
            argo_float_fieldset = cls._load_argo_float_fieldset(directory)
        else:
            argo_float_fieldset = None
        if load_ctd_bgc:
            ctd_bgc_fieldset = cls._load_ctd_bgc_fieldset(directory)
        else:
            ctd_bgc_fieldset = None
        if load_adcp or load_ctd or load_ship_underwater_st or load_xbt:
            ship_fieldset = cls._load_ship_fieldset(directory)
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

    @classmethod
    def _load_ship_fieldset(cls, directory: Path) -> FieldSet:
        filenames = {
            "U": directory.joinpath("ship_uv.nc"),
            "V": directory.joinpath("ship_uv.nc"),
            "S": directory.joinpath("ship_s.nc"),
            "T": directory.joinpath("ship_t.nc"),
            "bathymetry": directory.joinpath("bathymetry.nc"),
        }
        ds = xr.open_mfdataset(
            [filenames["U"], filenames["T"], filenames["S"], filenames["bathymetry"]]
        )
        ds = ds.rename_vars({"deptho": "bathymetry"})
        ds["bathymetry"] = -ds["bathymetry"]
        ds["depth"] = -ds["depth"]
        ds = ds.rename({"so": "S", "thetao": "T"})
        ds.time.attrs["axis"] = "T"
        fieldset = FieldSet.from_copernicusmarine(ds)
        return fieldset

    @classmethod
    def _load_ctd_bgc_fieldset(cls, directory: Path) -> FieldSet:
        filenames = {
            "U": directory.joinpath("ship_uv.nc"),
            "V": directory.joinpath("ship_uv.nc"),
            "o2": directory.joinpath("ctd_bgc_o2.nc"),
            "chl": directory.joinpath("ctd_bgc_chl.nc"),
            "no3": directory.joinpath("ctd_bgc_no3.nc"),
            "po4": directory.joinpath("ctd_bgc_po4.nc"),
            "ph": directory.joinpath("ctd_bgc_ph.nc"),
            "phyc": directory.joinpath("ctd_bgc_phyc.nc"),
            "zooc": directory.joinpath("ctd_bgc_zooc.nc"),
            "nppv": directory.joinpath("ctd_bgc_nppv.nc"),
        }
        variables = {
            "U": "uo",
            "V": "vo",
            "o2": "o2",
            "chl": "chl",
            "no3": "no3",
            "po4": "po4",
            "ph": "ph",
            "phyc": "phyc",
            "zooc": "zooc",
            "nppv": "nppv",
        }
        dimensions = {
            "lon": "longitude",
            "lat": "latitude",
            "time": "time",
            "depth": "depth",
        }

        fieldset = FieldSet.from_netcdf(
            filenames, variables, dimensions, allow_time_extrapolation=True
        )
        fieldset.o2.interp_method = "linear_invdist_land_tracer"
        fieldset.chl.interp_method = "linear_invdist_land_tracer"
        fieldset.no3.interp_method = "linear_invdist_land_tracer"
        fieldset.po4.interp_method = "linear_invdist_land_tracer"
        fieldset.ph.interp_method = "linear_invdist_land_tracer"
        fieldset.phyc.interp_method = "linear_invdist_land_tracer"
        fieldset.zooc.interp_method = "linear_invdist_land_tracer"
        fieldset.nppv.interp_method = "linear_invdist_land_tracer"

        # make depth negative
        for g in fieldset.gridset.grids:
            g.negate_depth()

        # add bathymetry data
        bathymetry_file = directory.joinpath("bathymetry.nc")
        bathymetry_variables = ("bathymetry", "deptho")
        bathymetry_dimensions = {"lon": "longitude", "lat": "latitude"}
        bathymetry_field = Field.from_netcdf(
            bathymetry_file, bathymetry_variables, bathymetry_dimensions
        )
        # make depth negative
        bathymetry_field.data = -bathymetry_field.data
        fieldset.add_field(bathymetry_field)

        # read in data already
        fieldset.computeTimeChunk(0, 1)

        return fieldset

    @classmethod
    def _load_drifter_fieldset(cls, directory: Path) -> FieldSet:
        filenames = {
            "U": directory.joinpath("drifter_uv.nc"),
            "V": directory.joinpath("drifter_uv.nc"),
            "T": directory.joinpath("drifter_t.nc"),
        }
        ds = xr.open_mfdataset([filenames["U"], filenames["T"]])
        ds = ds.rename({"thetao": "T"})
        ds.time.attrs["axis"] = "T"
        fieldset = FieldSet.from_copernicusmarine(ds)
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
