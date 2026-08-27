# Sail the ship

## Welcome aboard VirtualShip!

Welcome aboard, oceanography students, to our scientific research vessel! We're thrilled to have you join us for this exciting journey into the depths of the ocean. As we embark on this voyage of exploration and discovery, there are a few things we'd like to share with you to ensure a smooth and enriching experience:

**Introduction to the Vessel:** Take some time to familiarise yourselves with the layout of the ship. Get to know key areas such as the laboratories, living quarters, dining area, and deck spaces.

**Daily Routine:** Life on a research vessel follows a structured daily routine. We'll have designated times for meals, research activities, data analysis, and downtime. It's important to maintain this routine to ensure that our work is conducted efficiently and that everyone onboard has the opportunity to rest and recharge.

**Safety Orientation:** Safety is our top priority. As we set sail, we'll conduct a comprehensive safety orientation. This will cover important topics such as emergency procedures, the location of safety equipment, and proper use of personal protective gear. Please pay close attention during this orientation to ensure your safety and the safety of others on board.

**Respect for the Environment:** As we explore the ocean, it's essential to maintain a deep respect for the marine environment. We'll adhere to strict environmental protocols to minimize our impact on marine ecosystems and wildlife. Remember to dispose of waste properly and avoid disturbing marine life whenever possible.

**Teamwork and Collaboration:** Oceanographic research is a collaborative effort that requires teamwork and cooperation. You'll be working closely with your fellow students. Embrace the opportunity to learn from each other and support one another throughout the journey.

## Emergency procedures

Before going on any research expedition you need follow a one day Safety at Sea course and get a medical check-up.

Of course this is not needed for your virtual fieldwork, but we would like to draw for your attention to the following on-board emergency procedures.

**Safety Drills:** We conduct regular safety drills to ensure that everyone on board is well-prepared in case of an emergency. Specifically, fire and boat drills are held once a week. These drills are not just routine; they are essential survival training and should be taken seriously. To minimize disruption to the research program, science party members are usually notified in advance of the scheduled drills. In the event that you must continue working during a drill, prior arrangements can be made through the Chief Scientist.

**Emergency Signal:** In the event of an emergency signal, your immediate action is crucial. Don life jackets, put on long-sleeved garments, and wear a hat or head covering if available. Then, proceed to the designated station indicated on the station card located next to your bunk.

**On-Call Readiness:** Please keep in mind that while on board the ship, you may be called upon without warning to assist during your off-watch periods. Emergencies can happen at any time, and your readiness to respond promptly and efficiently is essential to the safety of all aboard.

**Boat Drill (Abandon Ship):** The signal for abandon ship is seven or more short blasts followed by one long blast of the ship’s whistle and general alarm. When this signal is heard, report to your designated life raft station. There the Mate in charge will explain the procedures for launching and embarking into the life rafts. The rafts will not be launched during a drill.

**Fire and Emergency Drills:** The signal is one long blast on the ship’s whistle and general alarm bell, lasting for ten seconds or more. During this drill, members of the science party muster in the designated area. Attendance will be taken and reported to the bridge.

**Man Overboard:** If someone falls overboard, throw a life-ring into the water towards the person. Keep your eye on the person at all times and point towards the person. Shout “MAN OVERBOARD, STARBOARD (or PORT),” and call the bridge on the sound powered phone or squawk box to inform them without losing sight of the person if possible. If you hear someone hail "Man Overboard," pass the word to the bridge.

## Your virtual expedition...

Now let's get started on running your VirtualShip expedition. Follow the steps below to set up your coding environment, plan your expedition, and launch your simulation.

```{note}
Before that though, make sure you have had your research question approved by your instructor!
```

## 1) Register with the Copernicus Marine Data Store

You will need to register for **Copernicus Marine Service** account (see [here](https://data.marine.copernicus.eu/register)), if you have not done so already. This is required to access the oceanographic data that VirtualShip uses to run your expedition.

## 2) Set up your virtual machine

You will be informed by your teacher if you will be using a cloud-based, pre-configured environment for VirtualShip (e.g., GitHub Codespaces) or if you should set up a local installation of the software. Please follow the instructions provided by your teacher to access your virtual machine accordingly.

## 3) Expedition route planning

### NIOZ MFP tool

The first step is to plan the expedition route for your chosen research question, bearing in mind the time needed for your sampling strategy, and traveling to and from a port suitable for research vessels. Remember, your approved proposal from your instructor may limit the amount of ship time you have received, so make sure to plan your route accordingly!

Your route can be created with the online [NIOZ MFP tool](https://nioz.marinefacilitiesplanning.com/cruiselocationplanning#). Documentation on how to use the website can be found [here](https://surfdrive.surf.nl/files/index.php/s/84TFmsAAzcSD56F). Alternatively, you can watch this [video](https://www.youtube.com/watch?v=yIpYX2xCvsM&list=PLE-LzO7kk1gLM74U4PLDh8RywYXmZcloz&ab_channel=VirtualShipClassroom), which runs through how to use the MFP tool.

```{note}
The MFP tool is used by professional oceanographers to plan research expeditions, so this is a great opportunity to get a feel for how real-world oceanographic research is planned!
```

### Export the coordinates from MFP

Once you have finalised your MFP expedition route, select "Export" on the right hand side of the window --> "Export Coordinates" --> "DD". This will download your coordinates as an `.xlsx` (Excel) file, which we will later feed into the VirtualShip protocol to initialise the expedition.

### _If using a cloud-based workspace_... upload the coordinates to your virtual machine

```{tip}
We suggest practicing good file management and creating a dedicated folder for your group's expedition data in the workspace. You can do so running `mkdir {your-group-name}` in the Terminal (replacing `{your-group-name}` with your actual group name) or via the File Explore panel in the Codespaces interface.
```

Navigate to the directory where your group will be running your expedition (e.g. `{your-group-name}`). Then upload the exported `.xlsx` file (it will be called something like `CruiseDataExport-20260812T1506.xlsx`) by right clicking in the File Explorer panel (ideally in the directory you created for your group's expedition data) and selecting the "Upload" option. From here you will be able to select your MFP export file.

## 4) Expedition initialisation

```{important}
When working in the Terminal, navigate to where you would like your expedition to be run on your (virtual) machine. You can do so by `cd {your-group-name}`, replacing `{your-group-name}` with your actual group name. This is where you will be working from for the rest of the session.
```

Now enter the following command in the Terminal (changing `EXPEDITION_NAME` to something more meaningful for your group's expedition):

`virtualship init EXPEDITION_NAME --from-mfp {CruiseDataExport}.xlsx`

```{tip}
The `{CruiseDataExport}.xlsx` in the command above refers to the `.xlsx` file exported from MFP and uploaded to your virtual machine earlier. Replace the filename with the name of your own file.
```

This will create a folder/directory called `EXPEDITION_NAME` (or what you have changed this to) with a single file: `expedition.yaml`. This file contains details on the ship and instrument configurations, as well as the expedition schedule based on the sampling site coordinates that you specified in your MFP export. The `--from-mfp` flag indicates that the exported coordinates should be used.

## 5) Expedition scheduling & ship configuration

```{tip}
From here, you should replace any references to `EXPEDITION_NAME` with the actual name you used for your expedition when running any `virtualship` commands.
```

<!-- TODO: some of this detail will change when [#362](https://github.com/Parcels-code/virtualship/issues/362) is implemented -->

The next step is to finalise the expedition schedule plan, including setting times and instrument selection choices for each waypoint, as well as configuring the ship (including any underway measurement instruments).

```{note}
This section describes the process of finalising the expedition schedule and instrument selection using the `virtualship plan` application. For expeditions with many waypoints, it can become cumbersome to use the planning tool (note, using VirtualShip in a remote terminal / cloud-based environment can also introduce lag in the user-interface). **In this case, you may prefer to edit the** `expedition.yaml` **file directly (see [here](../tutorials/working_with_expedition_yaml.md) for more details on how to do so)**.
```

The easiest way to do so is to use the bespoke VirtualShip planning tool. Enter the following command in Terminal: `virtualship plan EXPEDITION_NAME`.

### Ship speed

In the planning tool which appears, under _Ship Config Editor_ > _Ship Speed & Onboard Measurements_, there is an option to change the ship speed. However, for this course, you should leave this as the default **10 knots** value.

### Underway measurements

VirtualShip is capable of taking underway temperature and salinity measurements, as well as onboard ADCP measurements, as the ship sails across the length of the expedition (see [here](https://virtualship.readthedocs.io/en/latest/user-guide/assignments/Research_proposal_intro.html#Underway-Data) for more detail). These underway measurements can be switched on/off under _Ship Config Editor_ > _Ship Speed & Onboard Measurements_ as well.

For the underway ADCP, there is a choice of using the 38 kHz OceanObserver or the 300 kHz SeaSeven version (see [here](https://virtualship.readthedocs.io/en/latest/user-guide/assignments/Research_proposal_intro.html#ADCP) for more detail on the two ADCP types).

### Instrument/sensor configuration

The most important instrument configuration setting to consider is the list of **sensors** for each instrument, which controls what type of measurements/variables the instrument records in the simulation and therefore what output data you will receive for each instrument.

Sensor lists can be configured for each instrument under _Ship Config Editor_ > _Instrument Configurations_. For example, for the CTD instrument, you can specify which sensors to include in the simulation (e.g., `TEMPERATURE`, `SALINITY`, `OXYGEN`, etc.) by toggling the respective switches on or off.

```{note}
Sensor choices are only relevant for the instruments you plan to deploy as [underway measurements](#underway-measurements) or at waypoints across your expedition schedule [(see below)](#instrument-selection). For example, if you do not select to deploy a CTD at any of your waypoints, the CTD sensor choices will not affect any output data.
```

```{tip}
See [here](../documentation/full_sensor_list.md) for more information on the sensors available for each instrument.
```

There are other instrument configurations settings that can be adjusted in the editor as well (e.g. `max_depth` for the CTD), but these are more advanced and in most cases do not need to be changed from the default values.

### Waypoint datetimes

```{note}
VirtualShip supports running experiments in the years 1993 through to the present day by leveraging the suite of products available on the Copernicus Marine Data Store.
```

You will need to enter dates and times for each of the sampling stations/waypoints selected in the MFP route planning stage. This can be done under _Schedule Editor_ > _Waypoints & Instrument Selection_ in the planning tool.

Each waypoint has its own sub-panel for parameter inputs (click on it to expand the selection options). Here, the time for each waypoint can be inputted. There is also an option to adjust the latitude/longitude coordinates and you can add or remove waypoints.

```{note}
It is important to ensure that the timings for each station are realistic. There must be enough time for the ship to travel to each site at the prescribed speed (10 knots). The expedition schedule will be automatically verified when you press _Save Changes_ in the planning tool.
```

```{tip}
The MFP route planning tool will give estimated durations of sailing between sites at the 10 knots sailing speed. This can be useful to refer back to when planning the expedition timings and entering these into the `virtualship plan` tool.
```

### Instrument selection

You should now consider which measurements are to be taken at each sampling site (think about those required for your chosen research question), and therefore which instruments need to be selected in the planning tool at each waypoint.

```{tip}
Click [here](https://virtualship.readthedocs.io/en/latest/user-guide/assignments/Research_proposal_intro.html#Measurement-Options) for more information on which instruments are available in VirtualShip, and a brief introduction to each.
```

You can make instrument selections for each waypoint in the same sub-panels as the [waypoint time](#waypoint-datetimes) selection by simply switching each on or off. Multiple instruments are allowed at each waypoint.

### Save changes

When you are happy with your ship configuration and schedule plan, press _Save Changes_ at the bottom of the planning tool.

```{note}
On pressing _Save Changes_ the tool will check the selections are valid (for example that the ship will be able to reach each waypoint in time). If they are, the changes will be saved to the `expedition.yaml` file, ready for the next steps. If your selections are invalid you should be provided with information on how to fix them.
```

## 6) Run the expedition

You are now ready to run your virtual expedition! This stage will take all the measurements for each of instruments you selected at each waypoint in your expedition schedule, using input data sourced from the [Copernicus Marine Data Store](https://data.marine.copernicus.eu/products).

```{note}
You will need to register for a Copernicus Marine Service account (you can do so [here](https://data.marine.copernicus.eu/register)), if you have not done so already.
```

You can run your expedition simulation using the command:

`virtualship run EXPEDITION_NAME`

If this is your first time running VirtualShip, you will be prompted to enter your own Copernicus Marine Data Store credentials (these will be saved automatically for future use).

Small simulations (e.g. small space-time domains and fewer instrument deployments) will be relatively fast. For large, complex expeditions, it _could_ take up to an hour to simulate the measurements depending on your choices. Waiting for simulation is a great time to practice your level of patience. A skill much needed in oceanographic fieldwork ;-)

```{important}
VirtualShip may encounter 'real-life challenges' during the expedition, which simulate the various problems and unexpected events that can occur during real-life oceanographic expeditions (e.g. instrument and/or equipment failure, logistical challenges etc.). These may require your intervention to ensure your expedition schedule can continue!
```

## 7) Results

Upon successfully completing the simulation, results from the expedition will be stored in the `EXPEDITION_NAME/results` directory, written in `.parquet` [format](https://parquet.apache.org/).

From here you can carry on your analysis. In general, we encourage you to use [Parcels](https://Parcels-code.org/) (i.e. `parcels.read_particlefile()`) to read in VirtualShip output files, and tools such as [Polars](https://www.pola.rs/) and/or [Pandas](https://pandas.pydata.org/) for further data analysis. We also provide various further [VirtualShip tutorials](https://virtualship.readthedocs.io/en/latest/user-guide/tutorials/index.html) which provide examples of how to visualise data recorded by the VirtualShip instruments. Use these to help you get started!

```{tip}
We also host a [Binder](https://mybinder.org/) environment (note this is separate to the GitHub Codespaces workspace you may be using) with all the necessary post-processing tools pre-installed and all the tutorials ready to use. This might be useful as a means to explore your data at first. See [here](../tutorials/binder_workspace.md) for more detail or await further instruction from your instructor.
```

## Reporting

Reporting your journey is an essential aspect of our oceanographic research expedition. It allows us to share our experiences, communicate our findings, and contribute to the broader scientific community. After each scientific expedition a cruise report should be written (or potentially in the case of this course, a presentation).

You can find many cruise [reports](https://www.bodc.ac.uk/resources/inventories/cruise_inventory/reports/pe358.pdf) and [blogs](https://www.nioz.nl/en/news-and-blogs) online from many different cruises.

Reporting our journey allows us to validate the data collected during our research activities. It provides context for our findings and helps ensure that our results are accurately interpreted and understood. Detailed reports enable us to cross-reference our observations with environmental conditions, sampling locations, and other relevant factors, enhancing the reliability and credibility of our data.

Our reports also serve as valuable educational resources for students, educators, and the general public. They provide insights into the process of scientific inquiry, the challenges of conducting research at sea, and the significance of oceanographic discoveries.

If your course assignment involves a presentation, we look forward to seeing the impact of your collective efforts during the presentations in a few weeks time!

Please don't worry if your results are insufficient to answer your research question. Share your failure and things you would do different a next time instead!

For example:

- [Normalizing failure: when things go wrong in participatory marine social science fieldwork](https://publications.csiro.au/publications/publication/PIcsiro:EP2022-3465).
- [Emotions and failure in academic life: Normalising the experience and building resilience](https://www.cambridge.org/core/journals/journal-of-management-and-organization/article/emotions-and-failure-in-academic-life-normalising-the-experience-and-building-resilience/91FD71A50A32404D8EDFFB7886FF3521).
