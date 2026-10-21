# Full list of available instrument sensors

The following table provides a comprehensive list of available sensors for each instrument. These sensors can be specified via the `virtualship plan` tool (see the [Quickstart guide](../quickstart.md)) or in the `sensors` section of the respective instrument configuration in the `expedition.yaml` file (see the [working with expedition.yaml tutorial](../tutorials/working_with_expedition_yaml.md)).

The source data associated with these instrument sensor variables are described in the [Copernicus Marine products](copernicus_products.md) page.

```{note}
Trying to add a sensor to an instrument that does not support it will result in errors in VirtualShip. Always refer to this table to check which sensors are available for each instrument.
```

<!-- NOTE: is important that the entries in the 'Instrument' column below match the enum values in the code (instruments/types.py), and that these parts are **bold**, for the tests to work (test_utils.py::test_allowed_sensors_matches_docs) -->

| Instrument                             | Sensor Name        | Description                                                                               | Units                                | Category       |
| :------------------------------------- | :----------------- | :---------------------------------------------------------------------------------------- | :----------------------------------- | :------------- |
| **ADCP**                               | VELOCITY           | Current velocities (Eastward Sea Water Velocity (U) and Northward Sea Water Velocity (V)) | m/s                                  | Physical       |
| **UNDERWATER_ST** (Ship Underwater ST) | TEMPERATURE        | Sea Water Potential Temperature                                                           | °C                                   | Physical       |
|                                        | SALINITY           | Sea Water Salinity                                                                        | psu                                  | Physical       |
| **CTD**                                | TEMPERATURE        | Sea Water Potential Temperature                                                           | °C                                   | Physical       |
|                                        | SALINITY           | Sea Water Salinity                                                                        | psu                                  | Physical       |
|                                        | OXYGEN             | Mole Concentration of Dissolved Molecular Oxygen in Sea Water                             | mmol m<sup>-3</sup>                  | Biogeochemical |
|                                        | CHLOROPHYLL        | Mass Concentration of Chlorophyll a in Sea Water                                          | mmol m<sup>-3</sup>                  | Biogeochemical |
|                                        | NITRATE            | Mole Concentration of Nitrate in Sea Water                                                | mmol m<sup>-3</sup>                  | Biogeochemical |
|                                        | PHOSPHATE          | Mole Concentration of Phosphate in Sea Water                                              | mmol m<sup>-3</sup>                  | Biogeochemical |
|                                        | PH                 | Sea Water pH                                                                              | -                                    | Biogeochemical |
|                                        | PHYTOPLANKTON      | Mole Concentration of Phytoplankton                                                       | mmol m<sup>-3</sup>                  | Biogeochemical |
|                                        | PRIMARY_PRODUCTION | Net Primary Production of Biomass                                                         | mmol m<sup>-3</sup> day<sup>-1</sup> | Biogeochemical |
| **ARGO_FLOAT**                         | TEMPERATURE        | Sea Water Potential Temperature                                                           | °C                                   | Physical       |
|                                        | SALINITY           | Sea Water Salinity                                                                        | psu                                  | Physical       |
|                                        | OXYGEN             | Mole Concentration of Dissolved Molecular Oxygen in Sea Water (off by default)            | mmol m<sup>-3</sup>                  | Biogeochemical |
|                                        | CHLOROPHYLL        | Mass Concentration of Chlorophyll a in Sea Water (off by default)                         | mmol m<sup>-3</sup>                  | Biogeochemical |
|                                        | NITRATE            | Mole Concentration of Nitrate in Sea Water (off by default)                               | mmol m<sup>-3</sup>                  | Biogeochemical |
|                                        | PH                 | Sea Water pH (off by default)                                                             | -                                    | Biogeochemical |
| **DRIFTER**                            | TEMPERATURE        | Sea Water Potential Temperature                                                           | °C                                   | Physical       |
|                                        | SALINITY           | Sea Water Salinity                                                                        | psu                                  | Physical       |
| **XBT**                                | TEMPERATURE        | Sea Water Potential Temperature                                                           | °C                                   | Physical       |

```{note}
The `ARGO_FLOAT` BGC sensors (oxygen, chlorophyll, nitrate, pH) are off by default. Each extra sensor adds another variable for the simulation to load and sample, which can make the already-computationally intensive Argo float simulations even more intensive. When needed though, they can be turned on in the `virtualship plan` tool or by adding them to the `sensors` list of `argo_float_config` in `expedition.yaml`.

Only BGC variables that real-life [BGC-Argo](https://biogeochemical-argo.org/) floats measure are available for the Argo floats in VirtualShip.
```
