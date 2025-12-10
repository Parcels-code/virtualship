---
title: "VirtualShip for simulating oceanographic fieldwork anywhere in the global ocean"
tags:
  - Python
  - oceanography
  - fieldwork simulation
  - Lagrangian modelling
  - data ingestion
authors:
  - name: Jamie R. C. Atkins
    orcid: 0000-0002-5735-3312
    corresponding: true
    affiliation: 1
  - name: Emma Daniels
    orcid: 0009-0005-9805-5257
    affiliation: 1
  - name: Nick Hodgskin
    affiliation: 1
  - name: Aart Stuurman
  - name: Iury Simoes-Sousa
    orcid: 0000-0002-2484-510X
    affiliation: 2
  - given-name: Erik
    dropping-particle: van
    surname: van Sebille
    orcid: 0000-0003-2041-0704
    affiliation: 1

affiliations:
  - name: Institute for Marine and Atmospheric Research, Utrecht University, the Netherlands
    index: 1
  - name: Woods Hole Oceanographic Institution, Falmouth, MA, USA
    index: 2
date: 4 December 2025
bibliography: paper.bib
---

<!-- TODO: check all co-authors would like to be on the paper -->

# Summary

`VirtualShip` is a Python-based package which exploits the customisability of the open-source `Parcels` Lagrangian simulation framework [@Lange2017; @Delandmeter2019] to simulate measurements as if they were coming from real-life oceanographic instruments. The software builds a virtual ocean world by streaming data from the [Copernicus Marine Data Store](https://marine.copernicus.eu/) on-the-fly, facilitating virtual expeditions anywhere on the globe.

# Statement of need

Marine science relies on fieldwork for data collection, yet sea-going opportunities are limited due to financial costs, logistical constraints, and environmental burdens. We present an alternative means, namely `VirtualShip`, for training scientists to conduct oceanographic fieldwork in an authentic manner, planning future expeditions and deployments, and comparing directly observational strategies with model data.

<!-- TODO: VirtualFleet mention? -->

`VirtualShip` goes beyond simply extracting grid-cell averaged values from climate model output. Instead, it uses sophisticated interpolation techniques (with `Parcels` underpinnings) to access data in exact locations and timings, as if they were being collected by real-world instruments. `VirtualShip` shares some functionality with existing tools, such as `OceanSpy` [@Almansi2019] and `VirtualFleet` [@Maze2023], but extends capabilities to mesh many different instrument deployments, with programmable behaviours, into a unified expedition simulation framework. Moreover, `VirtualShip` exploits readily available, streamable data, via the Copernicus Marine Data Store, removing the need for users to download and manage large datasets locally and/or arrange for access to remote servers.

# Functionality

`VirtualShip` simulates the deployment of virtual instruments commonly used in oceanographic fieldwork, with empahsis on realism in how users plan and execute expeditions. For example, users must consider ship speed and instrument deployment/recovery times to ensure their expedition is feasible within given time constraints. Possible instrument implementations include surface `Drifter`, `CTD` (Conductivity-Temperature-Depth), `Argo float`, `XBT` (Expendable Bathythermograph), underway `ADCP` (Acoustic Doppler Current Profiler) and underway `Underwater_temperature/salinity` probes. More detail on each instrument is available in the [documentation](https://virtualship.readthedocs.io/en/latest/user-guide/assignments/Research_proposal_intro.html#Measurement-Options).

\autoref{fig:fig1} shows an example expedition around the Agulhas Current and South Eastern Atlantic, deploying a suite of instruments to sample physical and biogeochemical properties. Notable oceanographic features, such as the strong Agulhas Current and Agulhas Retroflection (drifters retroflecting back into the Indian Ocean), are clearly visible via the underway ADCP measurements and drifter releases in the early waypoints (\autoref{fig:fig1}b and c). CTD profiles (\autoref{fig:fig1}d and e) also capture the vertical structure of temperature and oxygen across the expedition route, including the warmer surface waters of the Agulhas region (early waypoints) and the Oxygen Minimum Zone in the South Eastern Atlantic (final waypoints).

<!-- TODO: may add an example Argo plot here, instead of the CTD (temperature) -->

![Example VirtualShip expedition simulated in July/August 2023. Expedition waypoints (a), Underway ADCP measurements across the expedition route (b), Surface drifter releases per waypoint (c; 90-day lifetime per drifter), and CTD vertical profiles per waypoint (as a function of cumulative distance across the expedition) for temperature (d) and oxygen (e). Black triangles in b), d) and e) mark locations of waypoints across expedition route, corresponding to the purple markers in a).\label{fig:fig1}](figure1.png)

The software is designed to be highly accessible to the user. It is wrapped into three high-level command line interface commands (using [Click](https://click.palletsprojects.com/en/stable/)):

1. `init`: Initialises the expedition directory structure and a `expedition.yaml` configuration file, which controls the expedition route, instrument choices and deployment timings. A common workflow is for users to first define expedition waypoint locations via the external [NIOZ Marine Facilities Planning](https://nioz.marinefacilitiesplanning.com/cruiselocationplanning#) (MFP) mapping tool. The coordinates can be exported and fed into `init` via the `--from-mfp` CLI flag.
2. `plan`: Launches a user-friendly Terminal-based expedition planning User Interface (UI), built using [`Textual`](https://textual.textualize.io/). This allows users to intuitively modify their expedition waypoint locations, timings and instrument selections.
3. `run`: Executes the virtual expedition according the planned configuration. This includes streaming data via the Copernicus Marine Data Store, simulating the instrument beahviours and sampling, and saving the resulting data in [`Zarr`](https://zarr.dev/) format.

A full example workflow is outlined in the [Quickstart Guide](https://virtualship.readthedocs.io/en/latest/user-guide/quickstart.html) documentation.

# Implementation

Under the hood, `VirtualShip` is modular and extensible. The workflows are designed around `Instrument` base classes and instrument-specific subclasses and methods. This means the platform can be easily extended to add new instrument types. Instrument behaviours are encoded as `Parcels` kernels, which allows for extensive customisability. For example, a `Drifter` advects passively with ocean currents, a `CTD` performs vertical profiling in the water column and an `ArgoFloat` cycles between ascent, descent and drift phases, all whilst sampling physical and/or biogeochemical fields at their respective locations and times.

Moreover, the data ingestion system, relies on streaming Analysis-Ready and Cloud-Optimized (ARCO; https://www.frontiersin.org/journals/climate/articles/10.3389/fclim.2021.782909/full, [@Abernathey2021]) data directly from the Copernicus Marine Data Store, via the [`copernicusmarine`](https://github.com/mercator-ocean/copernicus-marine-toolbox) Python toolbox. This means users can simulate expeditions anywhere in the global ocean without downloading large datasets by default. Leveraging the suite of [physics and biogeochemical products](https://virtualship.readthedocs.io/en/latest/user-guide/documentation/copernicus_products.html) available on the Copernicus plaform, expeditions are possible from 1993 to present day and forecasted two weeks into the future. There is also an option for the user to specify local `NetCDF` files for data ingestion, if preferred, with the necessary file stuctures and naming conventions outlined in the relevant [documentation](https://virtualship.readthedocs.io/en/latest/user-guide/documentation/example_copernicus_download.html).

# Applications and future outlook

`VirtualShip` has already been extensvely applied in Master's teaching settings at Utrecht University as part of the "VirtualShip Classroom" initiative. Educational assignments and tutorials have been developed alongside to integrate the tool into coursework, including projects where students design their own research question(s) and execute their fieldwork and analysis using `VirtualShip`. Its application has been shown to be successful, with students reporting increased self-efficacy and knowledge in executing oceanographic fieldwork [@Daniels2025].

We encourage researchers to use `VirtualShip` a cost-effective means to plan future expeditions, as tool for accessing ocean model data in a realistic manner, and to compare models to observations in a like-for-like manner. Both the customisability of the `VirtualShip` platform and the exciting potential for new ARCO-based data hosting services in domains beyond oceanography (e.g., [atmospheric science](https://climate.copernicus.eu/work-progress-our-data-stores-turn-arco)) means there is potential to extend VirtualShip (or "VirtualShip-like" tools) to other domains in the future.

As the `Parcels` underpinnings in themselves continue to evolve, with a future (at time of writing) [v4.0 release](https://docs.oceanparcels.org/en/v4-dev/v4/) focussed on alignment with [Pangeo](https://pangeo.io/) standards and `xarray` data structures, `VirtualShip` will also benefit from these improvements, further enhancing its capabilities, extensibility and compatability with modern cloud-based data pipelines.

# Acknowledgements

<!-- TODO: Do co-authors have anyone else they want to acknowledge? -->

The VirtualShip project is funded through the Utrecht University-NIOZ (Royal Netherlands Institute for Sea Research) collaboration.

# References
