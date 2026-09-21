# Researchers

## Introduction to VirtualShip

`VirtualShip` is open-source software that enables researchers to authentically _dry-run_ expeditions in a digital replica of the global ocean. It can be used to design, test, and optimise sampling strategies before conducting fieldwork, with potential applications in field campaign planning, Observation System Simulation Experiments (OSSEs), adaptive sampling, and like-for-like comparison of modelled and observed data.

The software, by default, streams cloud-native reanalysis/analysis data from the [Copernicus Marine Data Store](https://data.marine.copernicus.eu/products?disc=facets), and depends on the [Parcels](https://Parcels-code.org/) framework for Lagrangian particle tracking to authentically simulate the movement of oceanographic instruments through the water column. Instrument deployments currently supported include:

- ADCP (currents)
- CTD (conductivity and temperature + biogeochemical variables)
- XBT (temperature)
- Ship-mounted underwater measurements (salinity and temperature)
- Surface drifters (temperature)
- Argo floats (salinity and temperature)

Different combinations of instruments can be deployed in a single expedition across multiple waypoints, whilst realism in e.g. the scheduling is preserved to ensure an authentic digital replica of the expedition pipeline. Expeditions can be designed via the [Marine Facilities Planning](https://marinefacilitiesplanning.com/cruiselocationplanning#) website, as in real-life, and seamlessly integrated into the `VirtualShip` software.

## Getting started

```{tip}
See the guide [below](#setting-up-your-environment-computing-considerations ) for instructions on how to set up your programming environment for using the VirtualShip software.
```

Once you have installed the software, you can get started by following the [Quickstart guide](../../quickstart.md) below. This is the starting point for using VirtualShip. It will walk you through the process of creating a new expedition, planning your sampling strategy, and running the simulation to see how your instruments would perform in a digital twin ocean.

```{nbgallery}

../../quickstart.md

```

## Setting up your environment & computing considerations

### Local installation

If you prefer a local (or institutional server/HPC) installation, the following commands will create a new conda environment called virtualship and install the software from the conda-forge channel:

```bash
# create a new conda environment called 'virtualship' and install the software from the conda-forge channel
conda create -n virtualship -c conda-forge virtualship

# activate the environment
conda activate virtualship
```

### GitHub Codespaces

If you'd prefer not to install anything locally, or want to try `VirtualShip` before committing to a local setup, a pre-configured cloud environment is available via [GitHub Codespaces](https://github.com/features/codespaces) (see the [Simulation Workspace Guide](../../tutorials/codespaces_guide.md)).

```{note}
Bear in mind this is a free-tier service with limited monthly compute and RAM (see [Compute & performance considerations](#compute-performance-considerations) below), so it's best suited to smaller or occasional runs rather than intensive research pipelines.
```

### Working at scale: pre-downloaded data

By default, `VirtualShip` streams data on-demand from the [Copernicus Marine Data Store](https://data.marine.copernicus.eu/products?disc=facets) for each run. However, you may prefer to pre-download all the data you need once and reuse it.

See [Pre-downloading data](../../documentation/pre_download_data.md) for the required directory structure and filename conventions, and [Example Copernicus Download](../../documentation/example_copernicus_download.ipynb) for example code to automate the download. Once downloaded, you can ingest your local data via the `--from-data` option on `virtualship run`.

### Compute & performance considerations

The most compute/RAM-intensive instruments are those that move and/or sample across the full lat/lon/depth space over time, namely Argo floats and CTDs, since these require larger volumes of data to be retrieved and processed. This is more pronounced the further apart (in space and/or time) your waypoints are.

```{tip}
If you're running into memory issues (particularly likely on constrained environments like the free-tier GitHub Codespaces configuration), consider:

- Reducing the spatial/temporal spread between Argo Float/CTD deployments where possible.
- Running locally or on an institutional server/HPC with more available RAM, rather than a free-tier cloud environment.
```

## Post-processing Tutorials

We provide a set of tutorials for analysing **output** from `VirtualShip` expeditions, which you can use as a starting point for your own post-processing analysis.

```{nbgallery}
---
maxdepth: 1
---
../../tutorials/Drifter_data_tutorial.ipynb
../../tutorials/Argo_data_tutorial.ipynb
../../tutorials/CTD_transects.ipynb
../../tutorials/ADCP_transects.ipynb
../../tutorials/xbt_plotting.ipynb
../../tutorials/Ship_underwater_ST_plotting.ipynb
```
