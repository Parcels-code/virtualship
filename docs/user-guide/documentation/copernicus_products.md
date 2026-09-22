# Copernicus Marine Service products

VirtualShip supports running experiments anywhere in the global ocean from 1993 through to the present day (and approximately two weeks into the future), using the suite of products available from the [Copernicus Marine Data Store](https://data.marine.copernicus.eu/products).

The data sourcing task is handled by the `virtualship run` command, which in turn relies on the [copernicusmarine toolbox](https://github.com/mercator-ocean/copernicus-marine-toolbox?tab=readme-ov-file) for 'streaming' data from the Copernicus Marine Data Store. The two products relied on in `run` to source data for all [VirtualShip instruments](https://virtualship.readthedocs.io/en/latest/user-guide/assignments/Research_proposal_intro.html#Measurement-Options) (both physical and biogeochemical) are:

1. **Reanalysis** (or "hindcast" for biogeochemistry).
2. **Analysis & Forecast**.

```{tip}
The Copernicus Marine Service describe the differences between these products in greater detail [here](https://help.marine.copernicus.eu/en/articles/4872705-what-are-the-main-differences-between-nearrealtime-and-multiyear-products).
```

As a general rule of thumb the two different products span different periods across the historical period to present and are intended to allow for continuity across the previous ~ 30 years.

```{note}
The ethos for automated dataset selection in `virtualship run` is to prioritise the Reanalysis/Hindcast products where possible (the 'work horse'), and then fill the near-present (and near-future) temporal range with the Analysis & Forecast products.
```

### Data availability

The following tables summarise which Copernicus product is selected by `virtualship run` per combination of time period and variable (see legend below).

For biogeochemical variables `ph` and `phyc`, monthly products are required for the hindcast period. For all other variables, daily products are available.

#### Physical products

| Period              | Dataset ID                              | Temporal Resolution | Typical Years Covered                 | Variables                  |
| :------------------ | :-------------------------------------- | :------------------ | :------------------------------------ | :------------------------- |
| Reanalysis          | `cmems_mod_glo_phy_my_0.083deg_P1D-m`   | Daily               | ~30 years ago to ~2-4 months ago      | `uo`, `vo`, `so`, `thetao` |
| Analysis & Forecast | `cmems_mod_glo_phy_anfc_0.083deg_P1D-m` | Daily               | ~2-4 months ago to ~2 weeks in future | `uo`, `vo`, `so`, `thetao` |

---

#### Biogeochemical products

| Period                        | Dataset ID                                 | Temporal Resolution | Typical Years Covered                 | Variables                         | Notes                                  |
| :---------------------------- | :----------------------------------------- | :------------------ | :------------------------------------ | :-------------------------------- | :------------------------------------- |
| Hindcast                      | `cmems_mod_glo_bgc_my_0.25deg_P1D-m`       | Daily               | ~30 years ago to ~2-4 months ago      | `o2`, `chl`, `no3`, `po4`, `nppv` | Most BGC variables except `ph`, `phyc` |
| Hindcast (monthly)            | `cmems_mod_glo_bgc_my_0.25deg_P1M-m`       | Monthly             | ~30 years ago to ~4-6 months ago      | `ph`, `phyc`                      | Only `ph`, `phyc` (monthly only)       |
| Analysis & Forecast (O2)      | `cmems_mod_glo_bgc-bio_anfc_0.25deg_P1D-m` | Daily               | ~2-4 months ago to ~2 weeks in future | `o2`                              |                                        |
| Analysis & Forecast (Chl)     | `cmems_mod_glo_bgc-pft_anfc_0.25deg_P1D-m` | Daily               | ~2-4 months ago to ~2 weeks in future | `chl`, `phyc`                     |                                        |
| Analysis & Forecast (NO3/PO4) | `cmems_mod_glo_bgc-nut_anfc_0.25deg_P1D-m` | Daily               | ~2-4 months ago to ~2 weeks in future | `no3`, `po4`                      |                                        |
| Analysis & Forecast (PH)      | `cmems_mod_glo_bgc-car_anfc_0.25deg_P1D-m` | Daily               | ~2-4 months ago to ~2 weeks in future | `ph`                              |                                        |
| Analysis & Forecast (NPPV)    | `cmems_mod_glo_bgc-bio_anfc_0.25deg_P1D-m` | Daily               | ~2-4 months ago to ~2 weeks in future | `nppv`                            |                                        |

---

```{note}
* "Typical Years Covered" are approximate and subject to change with new Copernicus data releases.
* For the most up-to-date information, always consult the Copernicus Marine product documentation.
* Certain BGC variables (`ph`, `phyc`) are only available as monthly products in the hindcast period.
```

##### Copernicus Marine Service variables legend

| Variable Code | Full Variable Name                                            | Category       |
| :------------ | :------------------------------------------------------------ | :------------- |
| **uo**        | Eastward Sea Water Velocity                                   | Physical       |
| **vo**        | Northward Sea Water Velocity                                  | Physical       |
| **so**        | Sea Water Salinity                                            | Physical       |
| **thetao**    | Sea Water Potential Temperature                               | Physical       |
| **o2**        | Mole Concentration of Dissolved Molecular Oxygen in Sea Water | Biogeochemical |
| **chl**       | Mass Concentration of Chlorophyll a in Sea Water              | Biogeochemical |
| **no3**       | Mole Concentration of Nitrate in Sea Water                    | Biogeochemical |
| **po4**       | Mole Concentration of Phosphate in Sea Water                  | Biogeochemical |
| **nppv**      | Net Primary Production of Biomass                             | Biogeochemical |
| **ph**        | Sea Water pH                                                  | Biogeochemical |
| **phyc**      | Mole Concentration of Phytoplankton                           | Biogeochemical |
