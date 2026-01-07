<p align="center">
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="./docs/_static/virtual_ship_logo_inverted.png">
  <img alt="VirtualShipParcels logo'" width="200" src="./docs/_static/virtual_ship_logo.png">
</picture>
</p>

<!-- Badges -->

[![Anaconda-release](https://anaconda.org/conda-forge/virtualship/badges/version.svg)](https://anaconda.org/conda-forge/virtualship/)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/virtualship)
[![DOI](https://zenodo.org/badge/682478059.svg)](https://doi.org/10.5281/zenodo.14013931)
[![unit-tests](https://github.com/OceanParcels/virtualship/actions/workflows/ci.yml/badge.svg)](https://github.com/OceanParcels/virtualship/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/OceanParcels/virtualship/graph/badge.svg?token=SLGLN8QBLW)](https://codecov.io/gh/OceanParcels/virtualship)

<!-- Zenodo badge -->

---

<!-- SPHINX-START -->
<table>
    <tr>
        <th>Project Owner</th>
        <td>Emma Daniels (e.e.daniels1@uu.nl)</td>
    </tr>
    <tr>
        <!-- Should mirror pyproject.toml. Use one of the "Development status" flags from https://pypi.org/classifiers/-->
        <th>Development status</th>
        <td>Alpha</td>
    </tr>
</table>

<!-- TODO: README needs updating for v1-dev! -->

<!-- Insert catchy summary -->

VirtualShipParcels is a command line simulator allowing students to plan and conduct a virtual research expedition, receiving measurements as if they were coming from actual oceanographic instruments including:

- ADCP (currents)
- CTD (conductivity and temperature + biogeochemical variables)
- XBT (temperature)
- Ship-mounted underwater measurements (salinity and temperature)
- Surface drifters
- Argo float deployments

<!-- TODO: future. Along the way students will encounter difficulties such as: -->

## Installation

For a normal installation do:

```bash
conda create -n ship -c conda-forge virtualship
conda activate ship
```

which creates an environment named `ship` with the latest version of `virtualship`. You can replace `ship` with any name you like.

For a development installation, please follow the instructions detailed in the [contributing page](https://virtualship.readthedocs.io/en/latest/contributing/index.html).

## Usage

> [!TIP]
> See the [Quickstart guide](https://virtualship.readthedocs.io/en/latest/user-guide/quickstart.html) in our documentation for a step-by-step introduction to using VirtualShip.

You can run the VirtualShip via the command line interface (CLI) using the `virtualship` command. It has three subcommands: `init`, `plan`, and `run`.

```console
$ virtualship --help
Usage: virtualship [OPTIONS] COMMAND [ARGS]...

Options:
  --version  Show the version and exit.
  --help     Show this message and exit.

Commands:
  init  Initialize a directory for a new expedition, with an...
  plan  Launch UI to help build expedition configuration (YAML) file.
  run   Execute the expedition simulations.
```

```console
$ virtualship init --help
Usage: virtualship init [OPTIONS] PATH

  Initialize a directory for a new expedition, with an expedition.yaml file.

  If --mfp-file is provided, it will generate the expedition.yaml from the MPF
  file instead.

Options:
  --from-mfp TEXT  Partially initialise a project from an exported xlsx or csv
                   file from NIOZ' Marine Facilities Planning tool
                   (specifically the "Export Coordinates > DD" option). User
                   edits are required after initialisation.
  --help           Show this message and exit.
```

```console

$ virtualship plan --help
Usage: virtualship plan [OPTIONS] PATH

  Launch UI to help build expedition configuration (YAML) file.

  Should you encounter any issues with using this tool, please report an issue
  describing the problem to the VirtualShip issue tracker at:
  https://github.com/OceanParcels/virtualship/issues"

Options:
  --help  Show this message and exit.
```

```console
$ virtualship run --help
Usage: virtualship run [OPTIONS] PATH

  Execute the expedition simulations.

Options:
  --from-data TEXT  Use pre-downloaded data, saved to disk, for expedition,
                    instead of streaming directly via Copernicus Marine
                    Assumes all data is stored in prescribed directory, and
                    all variables (as listed below) are present. Required
                    variables are: {'phyc', 'o2', 'so', 'uo', 'po4', 'thetao',
                    'no3', 'vo', 'chl', 'ph', 'nppv'} Assumes that variable
                    names at least contain the standard Copernicus Marine
                    variable name as a substring. Will also take the first
                    file found containing the variable name substring. CAUTION
                    if multiple files contain the same variable name
                    substring.
  --help            Show this message and exit.
```

For examples of VirtualShip simulation output post-processing, see [the tutorials section of our documentation](https://virtualship.readthedocs.io/en/latest/user-guide/tutorials/index.html).

## Input data

The scripts are written to work with [A-grid ocean data from the Copernicus Marine Service](https://data.marine.copernicus.eu/product/GLOBAL_ANALYSISFORECAST_PHY_001_024/description).

## Source code

The code for this project is [hosted on GitHub](https://github.com/OceanParcels/virtualship).

### Contributors

<a href="https://github.com/oceanparcels/virtualship/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=oceanparcels/virtualship" />
</a>

**All contributions are welcome! See the [contributing page](https://virtualship.readthedocs.io/en/latest/contributing/index.html) in our documentation to see how to get involved.**
Image made with [contrib.rocks](https://contrib.rocks).
