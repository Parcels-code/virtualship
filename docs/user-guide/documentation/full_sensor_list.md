# Full list of available instrument sensors

The following table provides a comprehensive list of available sensors for each instrument. These sensors can be specified via the `virtualship plan` tool (see the [Quickstart guide](../quickstart.md)) or in the `sensors` section of the respective instrument configuration in the `expedition.yaml` file (see the [working with expedition.yaml tutorial](../tutorials/working_with_expedition_yaml.md)).

```{note}
Trying to add a sensor to an instrument that does not support it will result in errors in VirtualShip. Always refer to this table to check which sensors are available for each instrument.
```

| Instrument             | Sensor Name        | Description                                         | Units                                | Category        |
| :--------------------- | :----------------- | :-------------------------------------------------- | :----------------------------------- | :-------------- |
| **ADCP**               | VELOCITY           | Current velocities (eastward (u) and northward (v)) | m/s                                  | Physical        |
| **Ship Underwater ST** | TEMPERATURE        | Temperature                                         | °C                                   | Physics         |
|                        | SALINITY           | Salinity                                            | psu                                  | Physics         |
| **CTD**                | TEMPERATURE        | Temperature                                         | °C                                   | Physics         |
|                        | SALINITY           | Salinity                                            | psu                                  | Physics         |
|                        | OXYGEN             | Oxygen concentration                                | mmol m<sup>-3</sup>                  | Biogeochemistry |
|                        | CHLOROPHYLL        | Chlorophyll concentration                           | mmol m<sup>-3</sup>                  | Biogeochemistry |
|                        | NITRATE            | Nitrate concentration                               | mmol m<sup>-3</sup>                  | Biogeochemistry |
|                        | PHOSPHATE          | Phosphate concentration                             | mmol m<sup>-3</sup>                  | Biogeochemistry |
|                        | PH                 | pH                                                  | -                                    | Biogeochemistry |
|                        | PHYTOPLANKTON      | Phytoplankton concentration in carbon               | mmol m<sup>-3</sup>                  | Biogeochemistry |
|                        | PRIMARY_PRODUCTION | Net primary production                              | mmol m<sup>-3</sup> day<sup>-1</sup> | Biogeochemistry |
| **ARGO_FLOAT**         | TEMPERATURE        | Temperature                                         | °C                                   | Physics         |
|                        | SALINITY           | Salinity                                            | psu                                  | Physics         |
| **DRIFTER**            | TEMPERATURE        | Temperature                                         | °C                                   | Physics         |
| **XBT**                | TEMPERATURE        | Temperature                                         | °C                                   | Physics         |
