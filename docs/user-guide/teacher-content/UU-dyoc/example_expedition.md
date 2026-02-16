# VirtualShip Example Expedition

In this guide we will conduct an example virtual expedition. This expedition is not intended to be an in-depth tutorial on how to use all features of VirtualShip, but rather a general overview of the main steps of running the code itself, in preparation for your own expeditions. You will become more familiar with the SURF virtual environment, the command line interface and VirtualShip configuration files.

---

```{important}
This guide assumes you have already logged into and set up (initialised conda) the SURF virtual environment.
```

## 1) Create a new directory for your VirtualShip expeditions

First, you should navigate to the shared storage directory on the virtual machine (e.g. `cd data/virtualship_storage/`) and create a new directory for your group's VirtualShip expeditions (e.g. `mkdir {group_name}`, replacing `{group_name}` with your actual group name). This is where you will run your expeditions and store the results.

## 2) Expedition initialisation

```{note}
For your real expeditions, there will be a more involved expedition planning stage before this, including route planning and scheduling. Here, we are just going to use the default VirtualShip example expedition route and schedule.
```

You should now navigate to your group's directory (i.e. `cd data/virtualship_storage/{group_name}/`). Then run the following command in the terminal:

```
virtualship init EXPEDITION_NAME
```

This will create an expedition folder/directory called `EXPEDITION_NAME` (or change the name as desired) with a single file: `expedition.yaml` containing details on the ship and instrument configurations, as well as an _example_ expedition route and schedule.

## 3) Expedition planning and the `expedition.yaml` file

```{important}
For the purposes of this example expedition, you do not need to make any _edits_ to the `expedition.yaml`! This section is just to introduce you to the file and its purpose.
```

Navigate to the `expedition.yaml` file and open it in the (Jupyter Lab) text editor. This is where the configuration of your expedition is stored and where you can make changes to the expedition route, schedule and ship/instrument configurations.

You will see that the default is a basic route comprised of five waypoints on or near the equator, chosen for no particular scientific reason but just as an example, with deployment of a variety of different instruments (CTDs, Argo floats, Drifters etc.).

```{tip}
See [here](../../tutorials/working_with_expedition_yaml.md) for more detail on the `expedition.yaml`: what it is, how to edit it, and how to ultimately use it to configure your own expeditions.
```

Alternatively, you can view and edit the `expedition.yaml` file using the command:

```
virtualship plan EXPEDITION_NAME
```

This will launch a planning tool with an intuitive user interface to make changes to the expedition schedule and instrument selection. Changes made in the planning tool will be automatically saved to the `expedition.yaml` file.

For long and complex expeditions, it is often easier to edit the `expedition.yaml` file directly, but the planning tool can be useful for smaller expeditions, quick checks, or for small edits to the schedule and instrument selection.

## 4) Run the expedition

You are now ready to run your example expedition! This stage will simulate the measurements taken by the instruments selected at each waypoint in your expedition schedule, using input data sourced from the [Copernicus Marine Data Store](https://data.marine.copernicus.eu/products).

You will need to register for Copernicus Marine Service account (see [here](https://data.marine.copernicus.eu/register)), but the data access in VirtualShip will be automated.

You can run your expedition simulation using the command:

```
virtualship run EXPEDITION_NAME
```

If this is your first time running VirtualShip, you will be prompted to enter your own Copernicus Marine Data Store credentials (these will be saved automatically for future use).

For the example expedition, you can expect the simulation to take approximately 20 minutes, but this can vary depending on different factors including the machine set-up, system performance, and internet connection. Waiting for simulation is a great time to practice your level of patience. A skill much needed in oceanographic fieldwork ;-)

Why not browse through previous real-life [blogs and expedition reports](https://virtualship.readthedocs.io/en/latest/user-guide/assignments/Sail_the_ship.html#Reporting) in the meantime?!

## 5) Results

Upon successfully completing the simulation, results from the expedition will be stored in the `EXPEDITION_NAME/results` directory, written as [Zarr](https://zarr.dev/) files.

From here you will be able to carry on your analysis. We won't go into this here for the example expedition, but when it comes to your own expeditions, you will be expected to analyse, derive quantities and visualise your results, and to ultimately present your findings.
