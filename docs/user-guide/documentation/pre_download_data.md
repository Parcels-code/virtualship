# Pre-downloading data

By default, VirtualShip will automatically 'stream' data from the Copernicus Marine Service via the [copernicusmarine toolbox](https://github.com/mercator-ocean/copernicus-marine-toolbox?tab=readme-ov-file). However, for users who wish to manage data locally, it is possible to pre-download the required datasets and feed them into VirtualShip simulations.

<!-- TODO: quickstart guide needs full update! -->

As outlined in the [Quickstart Guide](https://virtualship.readthedocs.io/en/latest/user-guide/quickstart.html), the `virtualship run` command supports an optional `--from-data` argument, which allows users to specify a local directory containing the necessary data files.

```{tip}
See the [for example...](#for-example) section for an example data download workflow.
```

### Data requirements

For pre-downloaded data, VirtualShip only supports daily and monthly resolution physical and biogeochemical data, along with a static bathymetry file.

In addition, all pre-downloaded data must be split into separate files per timestep (i.e. one .nc file per day or month).

```{note}
**Monthly data**: when using monthly data, ensure that your final .nc file download is for the month *after* your expedition schedule end date. This is to ensure that a Parcels FieldSet can be generated under-the-hood which fully covers the expedition period. For example, if your expedition runs from 1st May to 15th May, your final monthly data file should be in June. Daily data files only need to cover the expedition period exactly.
```

Further, VirtualShip expects pre-downloaded data to be organised in a specific directory & filename structure within the specified local data directory. The expected structure is as outlined in the subsequent sections.

#### Directory structure

Assuming the local data directory (as supplied in the `--from-data` argument) is named `data/`, the expected subdirectory structure is:

```bash
.
└── data
    ├── bathymetry # containing the singular bathymetry .nc file
    ├── bgc # containing biogeochemical .nc files
    └── phys # containing physical .nc files
```

#### Filename conventions

Within these subdirectories, the expected filename conventions are:

- Physical data files (in `data/phys/`) should be named as follows:
  - `<COPERNICUS_DATESET_NOMENCLATURE>_<YYYY_MM_DD>.nc`
    - e.g. `cmems_mod_glo_phy-all_my_0.25deg_P1D-m_1998_05_01.nc` and so on for each timestep.
- Biogeochemical data files (in `data/bgc/`) should be named as follows:
  - `<COPERNICUS_DATESET_NOMENCLATURE>_<YYYY_MM_DD>.nc`
    - e.g. `cmems_mod_glo_bgc_my_0.25deg_P1M-m_1998_05_01.nc` and so on for each timestep.
- Bathymetry data file (in `data/bathymetry/`) should be named as follows:
  - `cmems_mod_glo_phy_anfc_0.083deg_static_bathymetry.nc`

```{tip}
Take care to use an underscore (`_`) as the separator between date components in the filenames (i.e. `YYYY_MM_DD`).
```

```{note}
Using the `<COPERNICUS_DATESET_NOMENCLATURE>` in the filenames is vital in order to correctly identify the temporal resolution of the data (daily or monthly). The `P1D` in the example above indicates daily data, whereas `P1M` would indicate monthly data.

See [here](https://help.marine.copernicus.eu/en/articles/6820094-how-is-the-nomenclature-of-copernicus-marine-data-defined#h_34a5a6f21d) for more information on Copernicus dataset nomenclature.

See also our own [documentation](https://virtualship.readthedocs.io/en/latest/user-guide/documentation/copernicus_products.html#data-availability) on the Copernicus datasets used natively by VirtualShip when 'streaming' data if you wish to use the same datasets for pre-download.
```

```{note}
**Monthly data**: the `DD` component of the date in the filename for monthly .nc files should always be `01`, representing the first day of the month. This ensures that a Parcels FieldSet can be generated under-the-hood which fully covers the expedition period from the start.
```

#### Further assumptions

The following assumptions are also made about the data:

1. All pre-downloaded data files must be in NetCDF format (`.nc`).
2. Physical data files must contain the following variables: `uo`, `vo`, `so`, `thetao`
   - Or these strings must appear as substrings within the variable names (e.g. `uo_glor` is acceptable for `uo`).
3. If using BGC instruments (e.g. `CTD_BGC`), the relevant biogeochemical data files must contain the following variables: `o2`, `chl`, `no3`, `po4`, `nppv`, `ph`, `phyc`.
   - Or these strings must appear as substrings within the variable names (e.g. `o2_glor` is acceptable for `o2`).
4. Bathymetry data files must contain a variable named `deptho`.

#### Also of note

1. Whilst not mandatory to use data downloaded only from the Copernicus Marine Service (any existing data you may hold can be re-organised accordingly), the assumptions made by VirtualShip regarding directory structure and filename conventions are motivated by alignment with the Copernicus Marine Service's practices.
   - If you want to use pre-existing data with VirtualShip, which you may have accessed from a different source, it is possible to do so by restructuring and/or renaming your data files as necessary.
2. The whole VirtualShip pre-downloaded data workflow should support global data or subsets thereof, provided the data files contain the necessary variables and are structured as outlined above.

#### For example...

Example Python code for automating the data download from Copernicus Marine can be found in [Example Copernicus Download](example_copernicus_download.ipynb).

<!-- TODO: replace with URL? -->
