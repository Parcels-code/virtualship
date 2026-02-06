# VirtualShip Quickstart Guide 🚢

Welcome to this Quickstart to using VirtualShip. In this guide we will conduct a virtual expedition in the North Sea. Note, however, that you can plan your own expedition anywhere in the global ocean and conduct whatever set of measurements you wish!

This Quickstart is available as an instructional video below, or you can continue with the step-by-step guide.

```{caution}
Please note the video below may show output from an earlier version of VirtualShip, as the codebase is in active development. The instructions in the video are still generally applicable for the current version. However, for the most up-to-date instructions, please follow the text in this Quickstart guide.
```

<iframe width="720" height="400" src="https://www.youtube.com/embed/yymj5fImnRc?si=04Nt3YEhGRMBcEBI" title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe>

---

This guide is intended to give a basic overview of how to plan, initialise and execute a virtual expedition. Data post-processing, analysis and visualisation advice is provided in other sections of the documentation (see [Results](#results) section).

## 1) Expedition route planning

```{note}
This section describes the _custom_ expedition route planning procedure. There is also an option to proceed without your own route and you can instead use an example route, schedule and selection of measurements (see [Expedition initialisation](#expedition-initialisation) for more details).
```

### NIOZ MFP tool

The first step is to plan the expedition route. This can be created with the online [ NIOZ MFP tool](https://nioz.marinefacilitiesplanning.com/cruiselocationplanning#). Documentation on how to use the website can be found [here](https://surfdrive.surf.nl/files/index.php/s/84TFmsAAzcSD56F). Alternatively, you can watch this [video](https://www.youtube.com/watch?v=yIpYX2xCvsM&list=PLE-LzO7kk1gLM74U4PLDh8RywYXmZcloz&ab_channel=VirtualShipClassroom), which runs through how to use the MFP tool.

Below is a screenshot of a North Sea expedition. This example expedition departs from Southampton, UK; conducts measurements at one sampling site in the southern North Sea, three in the Dogger Bank region and a further three around the Norwegian Trench before ending in Bergen, Norway.

Feel free to design your expedition as you wish! There is no need to copy these sampling sites in your own expeditions.

![MFP North Sea cruise plan screenshot](image-1.png)

### Export the coordinates

Once you have finalised your MFP expedition route, select "Export" on the right hand side of the window --> "Export Coordinates" --> "DD". This will download your coordinates as an .xlsx (Excel) file, which we will later feed into the VirtualShip protocol to initialise the expedition.

## 2) Expedition initialisation

```{note}
VirtualShip is a command line interface (CLI) based tool. From this point on in the Quickstart we will be working predominantly via the command line in the Terminal. If you are unfamiliar with what a CLI is, see [here](https://www.w3schools.com/whatis/whatis_cli.asp) for more information.
```

You should now navigate to where you would like your expedition to be run on your (virtual) machine (i.e. `cd path/to/expedition/dir/`). Then run the following command in your CLI:

```
virtualship init EXPEDITION_NAME --from-mfp CoordinatesExport.xlsx
```

```{tip}
The `CoordinatesExport.xlsx` in the `virtualship init` command refers to the .xlsx file exported from MFP. Replace the filename with the name of your exported .xlsx file (and make sure to move it from the Downloads to the folder/directory in which you are running the expedition).
```

This will create a folder/directory called `EXPEDITION_NAME` with a single file: `expedition.yaml` containing details on the ship and instrument configurations, as well as the expedition schedule based on the sampling site coordinates that you specified in your MFP export. The `--from-mfp` flag indicates that the exported coordinates will be used.

```{note}
For advanced users: it is also possible to run the expedition initialisation step without an MFP .xlsx export file. In this case you should simply run `virtualship init EXPEDITION_NAME` in the CLI. This will write an example `expedition.yaml` file in the `EXPEDITION_NAME` folder/directory. This file contains example waypoints, timings, instrument selections, and ship configuration, but can be edited or propagated through the rest of the workflow unedited to run a sample expedition.
```

## 3) Expedition scheduling & ship configuration

The next step is to finalise the expedition schedule plan, including setting times and instrument selection choices for each waypoint, as well as configuring the ship (such as its speed and underway measurement instruments). The easiest way to do so is to use the bespoke VirtualShip planning tool via the following command:

```
virtualship plan EXPEDITION_NAME
```

```{tip}
Using the `virtualship plan` tool is optional. Advanced users can also edit the `expedition.yaml` file directly if preferred.
```

The planning tool should look something like this and offers an intuitive way to make your selections:

![example_plan_app](example_plan_app.gif)

### Ship speed

In the planning tool, under _Ship Config Editor_ > _Ship Speed & Onboard Measurements_, there is an option to change the ship speed. In most cases it is best to leave this as the default 10 knots value.

### Underway measurements

VirtualShip is capable of taking underway temperature and salinity measurements, as well as onboard ADCP measurements, as the ship sails across the length of the expedition (see [here](https://virtualship.readthedocs.io/en/latest/user-guide/assignments/Research_proposal_intro.html#Underway-Data) for more detail). These underway measurements can be switched on/off under _Ship Config Editor_ > _Ship Speed & Onboard Measurements_ as well.

For the underway ADCP, there is a choice of using the 38 kHz OceanObserver or the 300 kHz SeaSeven version (see [here](https://virtualship.readthedocs.io/en/latest/user-guide/assignments/Research_proposal_intro.html#ADCP) for more detail on the two ADCP types).

### Waypoint datetimes

<!-- TODO: change this to a reference to `Run the data` instead of `Fetch the data` and talk a bit about data in the run step -->

```{note}
VirtualShip supports simulating experiments in the years 1993 through to the present day (and up to two weeks in the future) by leveraging the suite of products available Copernicus Marine Data Store (see [Run the expedition](#run-the-expedition)). The data access is automated based on the time period selected in the schedule. Different periods will rely on different products from the Copernicus Marine catalogue (see [Documentation](documentation/copernicus_products.md)).
```

You will need to enter dates and times for each of the sampling stations/waypoints selected in the MFP route planning stage. This can be done under _Schedule Editor_ > _Waypoints & Instrument Selection_ in the planning tool.

Each waypoint has its own sub-panel for parameter inputs (click on it to expand the selection options). Here, the time for each waypoint can be inputted. There is also an option to adjust the latitude/longitude coordinates and you can add or remove waypoints.

```{note}
It is important to ensure that the timings for each station are realistic. There must be enough time for the ship to travel to each site at a realistic speed (~ 10 knots). The expedition schedule (and the ship's configuration) will be automatically verified when you press _Save Changes_ in the planning tool.
```

```{tip}
The MFP route planning tool will give estimated durations of sailing between sites, usually at an assumed 10 knots sailing speed. This can be useful to refer back to when planning the expedition timings and entering these into the `virtualship plan` tool.
```

### Instrument selection

You should now consider which measurements are to be taken at each sampling site, and therefore which instruments need to be selected in the planning tool.

```{tip}
Click [here](https://virtualship.readthedocs.io/en/latest/user-guide/assignments/Research_proposal_intro.html#Measurement-Options) for more information on what measurement options are available, and a brief introduction to each instrument.
```

You can make instrument selections for each waypoint in the same sub-panels as the [waypoint time](#waypoint-datetimes) selection by simply switching each on or off. Multiple instruments are allowed at each waypoint.

```{note}
For advanced users: you can also make further customisations to behaviours of all instruments under _Ship Config Editor_ > _Instrument Configurations_.
```

### Save changes

When you are happy with your ship configuration and schedule plan, press _Save Changes_.

```{note}
On pressing _Save Changes_ the tool will check the selections are valid (for example that the ship will be able to reach each waypoint in time). If they are, the changes will be saved to the `expedition.yaml` file, ready for the next steps. If your selections are invalid you should be provided with information on how to fix them.
```

```{caution}
The `virtualship plan` tool will check that the ship can reach each waypoint according to the prescribed ship speed. However, before the ultimate [simulation step](#run-the-expedition) there will be a final, automated check that the schedule also accounts for the time taken to conduct the measurements at each site (e.g. a CTD cast in deeper waters will take longer). Therefore, we recommend to take this extra time into account at this stage of the planning by estimating how long each measurement will take and adding this time on.
```

## 4) Run the expedition

You are now ready to run your virtual expedition! This stage will simulate the measurements taken by the instruments you selected at each waypoint in your expedition schedule, using input data sourced from the [Copernicus Marine Data Store](https://data.marine.copernicus.eu/products).

You will need to register for Copernicus Marine Service account (see [here](https://data.marine.copernicus.eu/register)), but the data access in VirtualShip will be automated.

You can run your expedition simulation using the command:

```
virtualship run EXPEDITION_NAME
```

If this is your first time running VirtualShip, you will be prompted to enter your own Copernicus Marine Data Store credentials (these will be saved automatically for future use).

Your command line output should look something like this...

![GIF of example VirtualShip log output](example_log_instruments.gif)

Small simulations (e.g. small space-time domains and fewer instrument deployments) will be relatively fast. For large, complex expeditions, it _could_ take up to an hour to simulate the measurements depending on your choices. Waiting for simulation is a great time to practice your level of patience. A skill much needed in oceanographic fieldwork ;-)

Why not browse through previous real-life [blogs and expedition reports](https://virtualship.readthedocs.io/en/latest/user-guide/assignments/Sail_the_ship.html#Reporting) in the meantime?!

#### Encountering 'problems' during the expediton (configurable)

By default, VirtualShip will encounter 'problems' during the expedition, which simulate the various challenges and unexpected events that can occur during real-life oceanographic expeditions (e.g. instrument and/or equipment failure, logistical challenges etc.) and may require your intervention to ensure your expedition schedule can continue.

The 'problems' add authenticity to the simulation. However, if you require a 'problem'-free expedition, you can run the simulation with the "problem level" (`prob-level`) set to 0 (i.e. `virtualship run EXPEDITION_NAME --prob-level 0`).

```{tip}
For maximum authenticity, you can set `--prob-level 2`, which will scale the number of problems encountered by the complexity of your expedition (longer duration, more waypoints, more instruments will lead to more problems). By default, the `prob-level` = 1, which limits the number of problems to a maximum of 2, regardless of the expedition complexity.
```

#### Using pre-downloaded data (optional)

By default, VirtualShip will stream data 'on-the-fly' from the Copernicus Marine Data Store, meaning no prior data download is necessary. However, if you prefer to use pre-downloaded data instead (e.g. due to limited internet connection or wanting to use different input data) you can do so by running `virtualship run EXPEDITION_NAME --from-data <PATH_TO_DATA_DIR>`.

Enter `virtualship run --help` to see the full description of the `--from-data` flag and its usage.

See the relevant [documentation](https://virtualship.readthedocs.io/en/latest/user-guide/documentation/pre_download_data.html#) for more detail on how to prepare data for offline use.

## 5) Results

Upon successfully completing the simulation, results from the expedition will be stored in the `EXPEDITION_NAME/results` directory, written as [Zarr](https://zarr.dev/) files.

From here you can carry on your analysis (offline). We encourage you to explore and analyse these data using [Xarray](https://docs.xarray.dev/en/stable/). We also provide various further [VirtualShip tutorials](https://virtualship.readthedocs.io/en/latest/user-guide/tutorials/index.html) which provide examples of how to visualise data recorded by the VirtualShip instruments.
