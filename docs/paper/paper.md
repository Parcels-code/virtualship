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

<!-- TODO: check all co-authors would like to be on the paper! -->

# Summary

`VirtualShip` is a Python-based package which exploits the customisability of the open-source `Parcels` Lagrangian simulation framework [@Lange2017; @Delandmeter2019] to simulate measurements as if they were coming from real-life oceanographic instruments. The software builds a virtual ocean world by streaming data from the [Copernicus Marine Data Store](https://marine.copernicus.eu/) on-the-fly, facilitating virtual expeditions anywhere on the globe.

# Statement of need

Marine science relies on fieldwork for data collection, yet sea-going opportunities are limited due to financial costs, logistical constraints, and environmental burdens. We present an alternative means, namely `VirtualShip`, for training scientists to conduct oceanographic fieldwork in an authentic manner, planning future expeditions and deployments, and comparing directly observational strategies with model data.

<!-- TODO: VirtualFleet mention? -->

`VirtualShip` goes beyond simply extracting grid-cell averaged values from climate model output. Instead, it uses sophisticated interpolation techniques (with `Parcels` underpinnings) to access data in _exact_ locations and timings, as if they were being collected by real-world instruments. `VirtualShip` shares some functionality with existing ocean model data analysis tools, such as `OceanSpy` [@Almansi2019], but extends existing capabilities to mesh diverse instrument deployments, with programmable behaviours, into the same expedition simulation. Moreover, `VirtualShip` exploits readily available, streamable data, via the Copernicus Marine Data Store, removing the need for users to download and manage large datasets locally and/or arrange for access to remote servers.

# Functionality

`VirtualShip` simulates the deployment of virtual instruments commonly used in oceanographic fieldwork, with empahsis on realism and authenticity in how users plan and execute expeditions. Current instrument implementations include surface `Drifter`, `CTD` (Conductivity-Temperature-Depth), `Argo` float, `XBT` (Expendable Bathythermograph), `ADCP` (Acoustic Doppler Current Profiler) and ship-mounted `Underway` temperature/salinity instruments.

The software is designed to be accessible for the user. It is wrapped into three high-level command line interface commands (using [Click](https://click.palletsprojects.com/en/stable/)):

1. `init`
   - Initialises the expedition directory structure and a `expedition.yaml` configuration file, which controls the expedition route, instrument choices and deployment timings.
   - A common workflow is for users to first define expedition waypoint locations via the external [NIOZ Marine Facilities Planning](https://nioz.marinefacilitiesplanning.com/cruiselocationplanning#) (MFP) mapping tool. The coordinates can be exported and fed into `init` via the `--from-mfp` CLI flag.
2. `plan`
   - Launches a user-friendly Terminal-based expedition planning User Interface (UI), built using `Textual` (https://textual.textualize.io/). This allows users to intuitively modify their expedition waypoint locations, timings and instrument selections.
3. `run`
   - Executes ...

Emphasis is placed on making the expedition planning procedure as realistic as possible, with users needing to consider ship speed and instrument deployment/recovery times to ensure that their expedition is feasible within given time constraints.

A full example workflow is outlined in the [Quickstart Guide](https://virtualship.readthedocs.io/en/latest/user-guide/quickstart.html) documentation.

# Implementation

Under the hood, `VirtualShip` is highly modular and extensible. The workflows are designed around `Instrument` base classes and instrument-specific subclasses and methods. This means the platform can be easily extended to add new instrument types and behaviours. Instrument behaviours are encoded as `Parcels` kernels, which allows for customisability of behaviours and sampling strategies. For example, a `Drifter` advects passively with ocean currents, a `CTD` can perform vertical profiles and an `ArgoFloat` can cycle between ascent, descent and drift phases. All whilst sampling physical and/or biogeochemical fields at their respective locations and times.

Moreover, the data ingestion system, relies on streaming ARCO (FILL IN FULL NAME AND REF THAT ABERNATHY PAPER) data directly from the Copernicus Marine Data Store, via the [`copernicusmarine`](https://github.com/mercator-ocean/copernicus-marine-toolbox) Python toolbox. This means users can simulate expeditions anywhere in the global ocean without downloading large datasets by default. Leveraging the suite of [physics and biogeochemical products](https://virtualship.readthedocs.io/en/latest/user-guide/documentation/copernicus_products.html) available on the Copernicus plaform, expeditions are possible from 1993 to present day and forecasted two weeks into the future. There is also an option for the user to specify local `NetCDF` files for data ingestion, if preferred, with the necessary file stuctures and naming conventions outlined in the relevant [documentation](https://virtualship.readthedocs.io/en/latest/user-guide/documentation/example_copernicus_download.html).

# Applications and future directions

`VirtualShip` has already been extensvely applied in Master's teaching settings at Utrecht University as part of the "VirtualShip Classroom" initiative. Educational assignments have been developed alongside to integrate the tool into coursework, including projects where students design their own research question(s) and execute their fieldwork and analysis using `VirtualShip`. Its application has been shown to be successful, with students reporting increased self-efficacy and knowledge in executing oceanographic fieldwork [@Daniels2025].

We provide extensive documentation and tutorials to help users use `VirtualShip` and also provide a starting point for their post-processing analysis and visualisation of the virtual expedition data.

Both the customisability of the `VirtualShip` platform and the exciting potential for new ARCO-based data hosting services in domains beyond oceanography (e.g., atmospheric science; INSERT C3S ARCO BLOG POST) means there is potential to extend VirtualShip (or "VirtualShip-like" tools) to other domains in the future.

As the `Parcels` underpinnings themselves continue to evolve, with a future `v4.0` release focussed on alignment with [Pangeo](https://pangeo.io/) standards and specifically `xarray` data structures, `VirtualShip` will also benefit from these improvements, further enhancing its capabilities, extensibility and compatability with modern cloud-based data pipelines.

We also plan to soon introduce a (optional) 'problems' bolt-on module, where users must take decisions to overcome common issues encountered during real-life fieldwork, such as instrument failures, adverse weather conditions and logistical delays.

<!-- TODO: INSERT SOME IMAGES OF EXAMPLE OUTPUT; MULTI-PANEL FOR DIFFERENT INSTRUMENTS...CTDs, DRIFTERS, ADCP perhaps -->
<!-- TODO: make a python script which does this and plots up the results -->
<!-- TODO: this could be a big of a big multi-panel figure which also has an MFP screenshot of the  -->
<!-- TODO: think about extending the final waypoints to go deeper into the OMZ to show this nicely with BGC CTDs! -->

# Acknowledgements

<!-- TODO: Do co-authors have anyone else they want to acknowledge? -->

The VirtualShip project is funded through the Utrecht University-NIOZ (Royal Netherlands Institute for Sea Research) collaboration.

# References
