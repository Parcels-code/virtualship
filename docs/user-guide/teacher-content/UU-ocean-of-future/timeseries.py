# %%

"""N.B. Quick, inflexible (under active development) version whilst experimenting best approaches!"""  # noqa: D400
# TODO: WORK IN PROGRESS!

import glob
import os

import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

# TODO: incorporate uncertainty estimates in the plots, box plots per year/expedition

# TODO: build conmplexity of plots, single points -> lines -> uncertainty/boxplots -> colour boxplots by month of the (half) year

# TODO: timeseries - can just do it for surface...

# TODO: 3D plots of CTD Transects!

variables = ["phyc", "temperature", "salinity", "o2", "no3", "po4"]

base_dir = os.getcwd()

dict_vars = {}
for var in variables:
    print(f"Processing variable: {var}")
    filename = "ctd.zarr" if var in ["temperature", "salinity"] else "ctd_bgc.zarr"
    grp_dirs = sorted(glob.glob(os.path.join(base_dir, "GRP????/results/", filename)))

    var_values = []
    times = []

    tmp = {}
    for zarr_path in grp_dirs:
        ds = xr.open_zarr(zarr_path)

        # extract variable values and time
        var_values.append(ds[var].values.flatten())
        times.append(ds["time"].values[0][0])

    # organise to dict
    tmp["values"], tmp["time"] = var_values, times

    # master dict
    dict_vars[var] = tmp

# %%

plot_dict = {
    "phyc": {
        "label": "Phytoplankton",
        "units": "mmol m$^{-3}$",
        "color": "forestgreen",
    },
    "temperature": {
        "label": "Temperature",
        "units": "°C",
        "color": "crimson",
    },
    "salinity": {
        "label": "Salinity",
        "units": "PSU",
        "color": "lightseagreen",
    },
    "o2": {
        "label": "Oxygen",
        "units": "mmol m$^{-3}$",
        "color": "dodgerblue",
    },
    "no3": {
        "label": "Nitrate",
        "units": "mmol m$^{-3}$",
        "color": "darkorchid",
    },
    "po4": {
        "label": "Phosphate",
        "units": "mmol m$^{-3}$",
        "color": "coral",
    },
}

# %%

combined_vars = [v for v in variables if v not in ["no3", "po4"]] + ["no3_po4"]
fig, axs = plt.subplots(
    len(combined_vars), 1, figsize=(10, 10), dpi=96, sharex=True, sharey=False
)

for i, ax in enumerate(axs):
    if i < len(combined_vars) - 1:
        var = combined_vars[i]
        color = plot_dict[var]["color"]

        ax.scatter(
            dict_vars[var]["time"],
            [np.nanmean(values) for values in dict_vars[var]["values"]],
            color=color,
            zorder=3,
            s=50,
        )

        ax.plot(
            dict_vars[var]["time"],
            [np.nanmean(values) for values in dict_vars[var]["values"]],
            linestyle="dotted",
            alpha=1.0,
            color=color,
            lw=2.25,
        )

        ax.set_title(f"{plot_dict[var]['label']}", fontsize=12)
        ax.set_ylabel(plot_dict[var]["units"], fontsize=11)
    else:
        color_no3 = plot_dict["no3"]["color"]
        color_po4 = plot_dict["po4"]["color"]

        ax.scatter(
            dict_vars["no3"]["time"],
            [np.nanmean(values) for values in dict_vars["no3"]["values"]],
            color=color_no3,
            zorder=3,
            s=50,
            label=plot_dict["no3"]["label"],
        )
        ax.plot(
            dict_vars["no3"]["time"],
            [np.nanmean(values) for values in dict_vars["no3"]["values"]],
            linestyle="dotted",
            alpha=1.0,
            color=color_no3,
            lw=2.25,
        )
        ax.set_ylabel(plot_dict["no3"]["units"], fontsize=11, color=color_no3)
        ax.tick_params(axis="y", labelcolor=color_no3)

        ax2 = ax.twinx()
        ax2.scatter(
            dict_vars["po4"]["time"],
            [np.nanmean(values) for values in dict_vars["po4"]["values"]],
            color=color_po4,
            zorder=3,
            s=50,
            label=plot_dict["po4"]["label"],
        )
        ax2.plot(
            dict_vars["po4"]["time"],
            [np.nanmean(values) for values in dict_vars["po4"]["values"]],
            linestyle="dotted",
            alpha=1.0,
            color=color_po4,
            lw=2.25,
        )
        ax2.set_ylabel(plot_dict["po4"]["units"], fontsize=11, color=color_po4)
        ax2.tick_params(axis="y", labelcolor=color_po4)

        ax.set_title("Nutrients", fontsize=12)

        handles, labels = [], []
        for a in [ax, ax2]:
            h, label = a.get_legend_handles_labels()
            handles += h
            labels += label
        ax.legend(handles, labels, loc="upper right")

    ax.set_xlim(np.datetime64("1993-01-01"), np.datetime64("2025-12-31"))

    if i == len(axs) - 1:  # bottom panel only for single column of subplots
        ax.set_xlabel("Time")

    ax.set_facecolor("gainsboro")
    ax.grid(color="white", linewidth=1.0)


plt.tight_layout()
plt.show()
# %%
