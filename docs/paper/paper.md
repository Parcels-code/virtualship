---
title: "VirtualShip for simulating oceanographic fieldwork in the global ocean"
tags:
  - Python
  - oceanography
  - fieldwork simulation
  - (under)graduate training
  - Lagrangian modelling
  - instrument and sampling design
authors:
  - name: Jamie R. C. Atkins
    orcid: 0000-0002-5735-3312
    corresponding: true
    affiliation: "1, 2"
  - name: Emma E. Daniels
    orcid: 0009-0005-9805-5257
    affiliation: 1
  - name: Nick Hodgskin
    affiliation: 2
  - name: Aart C. Stuurman
    affiliation: 1
  - name: Iury Simoes-Sousa
    orcid: 0000-0002-2484-510X
    affiliation: 3
  - name: Erik van Sebille
    orcid: 0000-0003-2041-0704
    affiliation: "1, 2"

affiliations:
  - name: Freudenthal Institute, Utrecht University, the Netherlands
    index: 1
  - name: Institute for Marine and Atmospheric Research, Utrecht University, the Netherlands
    index: 2
  - name: Woods Hole Oceanographic Institution, Falmouth, MA, USA
    index: 3
date: 5 January 2026
bibliography: paper.bib
---

# Summary

`VirtualShip` is a Python-based package for simulating measurements as if they were coming from real-life oceanographic instruments, facilitating student training, expedition planning, and design of sampling/instrument strategies. The software exploits the customisability of the open-source `Parcels` Lagrangian simulation framework [@Lange2017; @Delandmeter2019] and builds a virtual ocean by streaming data from the [Copernicus Marine Data Store](https://marine.copernicus.eu/) on-the-fly, enabling expeditions anywhere on the globe.

# Statement of need

Marine science relies on fieldwork for data collection, yet sea-going opportunities are limited due to financial costs, logistical constraints, and environmental burdens. We present an alternative means, namely `VirtualShip`, for training scientists to conduct oceanographic fieldwork in an authentic manner, to plan future expeditions and deployments, and to directly compare observational and instrumentational strategies with model data.

`VirtualShip` goes beyond simply extracting grid-cell values from model output. Instead, it uses programmable behaviours and sophisticated interpolation techniques (with `Parcels` underpinnings) to access data in exact locations and timings, as if they were being collected by real-world instruments. `VirtualShip` shares some functionality with existing tools, such as `OceanSpy` [@Almansi2019] and `VirtualFleet` [@Maze2023], but extends capabilities to mesh many different instrument deployments into a unified expedition simulation framework. Moreover, `VirtualShip` exploits readily available, streamable data via the Copernicus Marine Data Store, removing the need for users to download and manage large datasets locally and/or arrange for access to remote servers. `VirtualShip` can also integrate coordinate files exported from the [Marine Facilities Planning](https://www.marinefacilitiesplanning.com/cruiselocationplanning#) (MFP) tool, giving users the option to define expedition waypoints via an intuitive web-based mapping interface.

# Functionality

`VirtualShip` simulates the deployment of virtual instruments commonly used in oceanographic fieldwork, with emphasis on realism in how users plan and execute expeditions. For example, users must consider ship speed and instrument deployment/recovery times to ensure their expedition is feasible within given time constraints. Possible instrument selections include surface `Drifter` [@Lumpkin2017], `CTD` (Conductivity-Temperature-Depth; @Johnson2007), `Argo float` [@Jayne2017], `XBT` (Expendable Bathythermograph; @Goni2019), underway `ADCP` (Acoustic Doppler Current Profiler; @Kostaschuk2005), and underway `Underwater_temperature/salinity` [@Gordon2014] probes. More detail on each instrument is available in the [documentation](https://virtualship.readthedocs.io/en/latest/user-guide/assignments/Research_proposal_intro.html#Measurement-Options).

The software can simulate complex multidisciplinary expeditions. One example is a virtual expedition across the Agulhas Current and the South Eastern Atlantic that deploys a suite of instruments to sample physical and biogeochemical properties (\autoref{fig:fig1}). Key circulation features appear early in the expedition track, with enhanced ADCP speeds marking the strong Agulhas Current (\autoref{fig:fig1}b) and drifters that turn back toward the Indian Ocean indicating the Agulhas Retroflection (\autoref{fig:fig1}c). The CTD profiles capture the vertical structure of temperature and oxygen along the route, including the warmer surface waters of the Agulhas region (\autoref{fig:fig1}d, early waypoints) and the Oxygen Minimum Zone in the South Eastern Atlantic (\autoref{fig:fig1}e, final waypoints).

![Example VirtualShip expedition simulated in July/August 2023. Expedition waypoints displayed via the MFP tool (a), Underway ADCP measurements (b), Surface drifter releases (c; 90-day lifetime per drifter), and CTD vertical profiles for temperature (d) and oxygen (e). Black triangles in b), d) and e) mark waypoint locations across the expedition route, corresponding to the purple markers in a).\label{fig:fig1}](figure1.png)

The software is designed to be highly intuitive to the user. It is wrapped into three high-level command line interface commands using [Click](https://click.palletsprojects.com/en/stable/):

1. `virtualship init`: Initialises the expedition directory structure and an `expedition.yaml` configuration file, which controls the expedition route, instrument choices and deployment timings. A common workflow is for users to import pre-determined waypoint coordinates using the `--from-mfp` flag in combination with a coordinates `.csv` or `.xlsx` file (e.g. exported from the [MFP](https://www.marinefacilitiesplanning.com/cruiselocationplanning#) tool).
2. `virtualship plan`: Launches a user-friendly Terminal-based expedition planning User Interface (UI), built using [`Textual`](https://textual.textualize.io/). This allows users to intuitively set their waypoint timings and instrument selections, and also modify their waypoint locations.
3. `virtualship run`: Executes the virtual expedition according to the planned configuration. This includes streaming data via the [Copernicus Marine Data Store](https://marine.copernicus.eu/), simulating the instrument beahviours and sampling, and saving the output in [`Zarr`](https://zarr.dev/) format.

A full example workflow is outlined in the [Quickstart Guide](https://virtualship.readthedocs.io/en/latest/user-guide/quickstart.html) documentation.

# Implementation

Under the hood, `VirtualShip` is modular and extensible. The workflows are designed around `Instrument` base classes and instrument-specific subclasses and methods. This means the platform can be easily extended to add new instrument types. Instrument behaviours are coded as `Parcels` kernels, which allows for extensive customisability. For example, a `Drifter` advects passively with ocean currents, a `CTD` performs vertical profiling in the water column and an `ArgoFloat` cycles between ascent, descent and drift phases, all whilst sampling physical and/or biogeochemical fields at their respective locations and times.

Moreover, the data ingestion system relies on Analysis-Ready and Cloud-Optimized data (ARCO; @Stern2022, @Abernathey2021) streamed directly from the Copernicus Marine Data Store, via the [`copernicusmarine`](https://github.com/mercator-ocean/copernicus-marine-toolbox) Python toolbox. This means users can simulate expeditions anywhere in the global ocean without downloading large datasets by default. Leveraging the suite of [physics and biogeochemical products](https://virtualship.readthedocs.io/en/latest/user-guide/documentation/copernicus_products.html) available on the Copernicus plaform, expeditions are possible from 1993 to present and forecasted two weeks into the future. There is also an [option](https://virtualship.readthedocs.io/en/latest/user-guide/documentation/pre_download_data.html) for the user to specify local `NetCDF` files for data ingestion, if preferred.

# Applications and future outlook

`VirtualShip` has already been extensvely applied in Master's teaching settings at Utrecht University as part of the [VirtualShip Classroom](https://www.uu.nl/en/research/sustainability/sustainable-ocean/education/virtual-ship) initiative. Educational assignments and tutorials have been developed alongside to integrate the tool into coursework, including projects where students design their own research question(s) and execute their fieldwork and analysis using `VirtualShip`. Its application has been shown to be successful, with students reporting increased self-efficacy and knowledge in executing oceanographic fieldwork [@Daniels2025].

The package opens space for many other research applications. It can support real-life expedition planning by letting users test sampling routes before going to sea. It also provides tooling to explore real-time adaptive strategies in which sampling plans shift as forecasts or observations update. The same workflow can also be used to investigate sampling efficiency, for example, examining how waypoint number or spacing shapes the ability to capture features of interest. Moreover, the software is well-suited for developing Observation System Simulation Experiments (OSSEs; e.g. @Errico2013) to test and optimise observational strategies in a cost- and time-efficient manner.
This framework further enables instrument design experiments that are relevant to autonomous observing systems. Users can prototype and test control strategies for gliders, REMUS vehicles, Saildrones, and semi autonomous platforms such as Argo floats, as well as explore concepts for new instruments at early stages of development. Future tutorials could demonstrate how to define custom instruments within this framework.
Both the customisability of the `VirtualShip` platform and the exciting potential for new ARCO-based data hosting services in domains beyond oceanography (e.g., [atmospheric science](https://climate.copernicus.eu/work-progress-our-data-stores-turn-arco)) means there is potential to extend VirtualShip (or "VirtualShip-like" tools) to other domains in the future. Furthermore, as the `Parcels` underpinnings themselves continue to evolve, with a future (at time of writing) [v4.0 release](https://docs.oceanparcels.org/en/v4-dev/v4/) focusing on alignment with [Pangeo](https://pangeo.io/) standards and `Xarray` data structures [@Hoyer2017], `VirtualShip` will also benefit from these improvements, further enhancing its capabilities, extensibility and compatability with modern cloud-based data pipelines.

# Acknowledgements

The VirtualShip project is funded through the Utrecht University-NIOZ (Royal Netherlands Institute for Sea Research) collaboration.

# References
