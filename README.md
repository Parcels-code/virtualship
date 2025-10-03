<p align="center">
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="./docs/_static/virtual_ship_logo_inverted.png">
  <img alt="VirtualShipParcels logo'" width="200" src="./docs/_static/virtual_ship_logo.png">
</picture>
</p>

<!-- Badges -->

[![Pixi Badge](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/prefix-dev/pixi/main/assets/badge/v0.json)](https://pixi.sh)
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

<!-- Insert catchy summary -->

VirtualShipParcels is a command line simulator allowing students to plan and conduct a virtual research expedition, receiving measurements as if they were coming from actual oceanographic instruments including:

- ADCP (currents)
- CTD (conductivity and temperature)
- XBT (temperature)
- underwater measurements (salinity and temperature)
- surface drifters
- argo float deployments

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

```console
$ virtualship --help
Usage: virtualship [OPTIONS] COMMAND [ARGS]...

Options:
  --version  Show the version and exit.
  --help     Show this message and exit.

Commands:
  fetch  Download input data for an expedition.
  init   Initialize a directory for a new expedition, with an example...
  run    Run the expedition.
```

```console
$ virtualship init --help
Usage: virtualship init [OPTIONS] PATH

  Initialize a directory for a new expedition, with an example schedule and
  ship config files.

Options:
  --help  Show this message and exit.
```

```console

$ virtualship fetch --help
Usage: virtualship fetch [OPTIONS] PATH

  Download input data for an expedition.

  Entrypoint for the tool to download data based on space-time region provided
  in the schedule file. Data is downloaded from Copernicus Marine, credentials
  for which can be obtained via registration:
  https://data.marine.copernicus.eu/register . Credentials can be provided on
  prompt, via command line arguments, or via a YAML config file. Run
  `virtualship fetch` on a expedition for more info.

Options:
  --username TEXT  Copernicus Marine username.
  --password TEXT  Copernicus Marine password.
  --help           Show this message and exit.
```

```console
$ virtualship run --help
Usage: virtualship run [OPTIONS] PATH

  Run the expedition.

Options:
  --help  Show this message and exit.
```

For examples, see [the tutorials section of our documentation](https://virtualship.readthedocs.io/en/latest/user-guide/tutorials/index.html).

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
