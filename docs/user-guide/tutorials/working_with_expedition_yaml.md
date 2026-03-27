## Working with the `expedition.yaml` file

This tutorial will guide you through the structure of the `expedition.yaml` file and how to modify it.

The `expedition.yaml` file is ingested by `virtualship run` and is used to configure expeditions. It contains metadata and settings that define the parameters of an expedition, including information about ship speed, instrument configurations, waypoint timings and instrument selections.

This tutorial describes an alternative means to using the `virtualship plan` command, which provides a user-friendly interface for interacting with `expedition.yaml` but can become cumbersome for long, complex expeditions with many waypoints and instruments. Interacting with the `expedition.yaml` file directly tends to be faster for larger expeditions and experienced users.

### Editing the file

The `expedition.yaml` file can be opened and edited using any text editor that supports YAML format. Make your changes and save the file to write the changes to your expedition directory.

```{tip}
The `expedition.yaml` file can also be opened and edited in Jupyter Lab environments using the built-in text editor. Simply navigate to the file in the file browser and (double) click to open it in a new tab.
```

```{important}
The `expedition.yaml` file is highly sensitive to indentation and formatting, so please ensure that you maintain the correct formatting (as described [below](#specifics-for-each-section)) when making modifications.
```

### Structure

The `expedition.yaml` file is written in [YAML](https://en.wikipedia.org/wiki/YAML) format, which is a human-readable data serialization standard. Below is an annotated example of a simple `expedition.yaml` file with two waypoints:

```yaml
# EXAMPLE EXPEDITION.YAML
#
schedule: # <-- 1. expedition schedule section
  waypoints:
    - instrument: # <-- Waypoint 1
        - CTD
        - CTD_BGC
        - ARGO_FLOAT
        - DRIFTER
      location:
        latitude: 45.604174
        longitude: -43.886739
      time: 1998-03-08 03:37:00
    - instrument: # <-- Waypoint 2
        - ARGO_FLOAT
        - DRIFTER
        - XBT
      location:
        latitude: 48.185988
        longitude: -32.988302
      time: 1998-03-10 03:05:00
#
instruments_config: # <-- 2. instrument configuration section
  adcp_config:
    num_bins: 40
    max_depth_meter: -1000.0
    period_minutes: 5.0
  ship_underwater_st_config:
    period_minutes: 5.0
  argo_float_config: ...
  ctd_bgc_config: ...
  ctd_config: ...
  drifter_config: ...
  xbt_config: ...
#
ship_config: # <-- 3. ship configuration section
  ship_speed_knots: 10.0
```

```{note}
In the example above, some instrument configuration parameters are replaced by ellipses (`...`) for brevity. In a real `expedition.yaml` file, these sections would contain detailed configuration settings for each instrument.
```

### Specifics for each section

#### 1. `schedule`

This section contains a list of `waypoints` that define the expedition's route. Each waypoint includes:

- **Instruments (`instrument`)**: A list of instruments to be deployed at that waypoint. Add or remove instruments by adding or deleting entries on _new lines_. The instrument selection can also be left empty (i.e., no instruments deployed at that waypoint) by setting the parameter to: `instrument: null`.

```{tip}
Full list of instruments supported for deployment at waypoints (case-sensitive): `CTD`, `CTD_BGC`, `DRIFTER`, `ARGO_FLOAT`, `XBT` (or `null`).
```

```{tip}
You can do multiple `DRIFTER` deployments at the same waypoint by adding multiple `DRIFTER` entries in the list (on separate lines). Note, this is not the case for other instruments, e.g. `CTD`, which can only be deployed once at a given waypoint.
```

- **Location (`location`)**: The geographical coordinates (latitude and longitude) of the waypoint. These must be in decimal degrees (DD) format and within valid ranges: latitude between -90 and 90, longitude between -180 and 180.

- **Time (`time`)**: The scheduled time for reaching the waypoint, specifically in YYYY-MM-DD HH:MM:SS format.

#### 2. `instruments_config`

This section defines the configuration settings for each instrument used in the expedition. Each instrument has its own subsection where specific parameters can be set.

Because **underway instruments** (e.g., ADCP, Ship Underwater ST) collect data continuously while the ship is moving, their deployment is not tied to specific waypoints. Instead, the presence of their configuration sections in `instruments_config` indicates that they will be active throughout the expedition. This means that if you wish to turn off an underway instrument, you can remove its configuration section or simply set it to `null`, for example:

```yaml
instruments_config:
  adcp_config: null
  ship_underwater_st_config: null
```

For **all other instruments**, e.g. CTD, ARGO_FLOAT etc., the parameters can often be left as the default values unless advanced customisations are required.

#### 3. `ship_config`

This section contains setting related to the ship itself, specifically:

- **Ship speed (`ship_speed_knots`)**: The speed of the ship in knots (nautical miles per hour; where 1 knot = 1.852 km/h). Note in most cases this should be left as the default value unless there is a specific reason to change it.

<!-- TODO: more details on ship configuration if added in the future -->
