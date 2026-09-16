# Researchers

```{caution}
Coming soon! This is a work in progress.
```

`VirtualShip` is open-source software that enables researchers to authentically _dry-run_ expeditions in a digital replica of the global ocean. It can be used to design, test, and optimise sampling strategies before conducting fieldwork, with potential applications in field campaign planning, Observation System Simulation Experiments (OSSEs), adaptive sampling, and like-for-like comparison of modelled and observed data.

The software by default streams cloud-native reanalysis/analysis data from the [Copernicus Marine Data Store](https://data.marine.copernicus.eu/products?disc=facets), and depends on the [Parcels](https://Parcels-code.org/) framework for Lagrangian particle tracking to authentically simulate the movement of oceanographic instruments through the water column. Instruments currently supported include:

- ADCP (currents)
- CTD (conductivity and temperature + biogeochemical variables)
- XBT (temperature)
- Ship-mounted underwater measurements (salinity and temperature)
- Surface drifters (temperature)
- Argo floats (salinity and temperature)

Different combinations of instruments can be deployed in a single expedition across multiple waypoints, whilst realism in e.g. the scheduling is preserved to ensure an authentic digital replica of the expedition pipeline. Expeditions can be designed via the [Marine Facilities Planning](https://marinefacilitiesplanning.com/cruiselocationplanning#) website, as in real-life, and seamlessly integrated into the `VirtualShip` software.

## Getting started

Once you have installed the software, you can get started by following the [Quickstart guide](../../quickstart.md) in our documentation (see below). This will walk you through the process of creating a new expedition, planning your sampling strategy, and running the simulation to see how your instruments would perform in the real ocean.

```{nbgallery}

../../quickstart.md

```

```{tip}
<!-- TODO -->
See below for instructions on how to use the VirtualShip workspace (GitHub Codespaces) if you cannot, or prefer not to, install the software locally.
```

## Using the VirtualShip workspace (GitHub Codespaces)

<!-- TODO: -->

If you cannot, or prefer not to, install the software locally, you can use the [VirtualShip workspace](
