# %%

import cartopy.crs as ccrs
import matplotlib.gridspec as gridspec
import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
from plotting_functions import (
    _ctd_distance_from_start,
    plot_adcp,
    plot_ctd,
    plot_drifters,
)

SAMPLE_DIR = "sample_expedition/"
CONFIG = "expedition.yaml"
EXPEDITION = "MY_EXPEDITION"

# %%

# VirtualShip output
ctd_ds = xr.open_dataset(f"{SAMPLE_DIR}{EXPEDITION}/results/ctd.zarr")
ctd_bgc_ds = xr.open_dataset(f"{SAMPLE_DIR}{EXPEDITION}/results/ctd_bgc.zarr")
drifter_ds = xr.open_dataset(f"{SAMPLE_DIR}{EXPEDITION}/results/drifter.zarr")
adcp_ds = xr.open_dataset(f"{SAMPLE_DIR}{EXPEDITION}/results/adcp.zarr")


# %%


# TODO: fix waypoint markers!

PROJ = ccrs.PlateCarree()

waypoint_distances = np.unique(_ctd_distance_from_start(ctd_ds)["distance"])


def add_waypoint_markers(ax, distances, offset=0):
    ax.scatter(
        (distances / 1000) + offset,
        np.zeros_like(distances),
        marker="v",
        color="black",
        edgecolors="white",
        s=100,
    )


# fig
fig = plt.figure(figsize=(12, 12), dpi=300)

# custom layout
gs = gridspec.GridSpec(3, 2, height_ratios=[1, 1, 1])
ax0 = fig.add_subplot(gs[0, :])
ax1 = fig.add_subplot(gs[1, 0])
ax2 = fig.add_subplot(gs[1, 1], projection=PROJ)
ax3 = fig.add_subplot(gs[2, 0])
ax4 = fig.add_subplot(gs[2, 1])

# overview image
ax0.set_title(r"$\bf{a}$" + ") MFP expedition overview")
img = mpimg.imread(f"{SAMPLE_DIR}expedition_overview.png")
ax0.imshow(img)
ax0.axis("off")

# adcp
ax1.set_title(r"$\bf{b}$" + ") ADCP (flow velocity)")
ax1.set_ylabel("Depth (m)")
ax1.set_xlabel("Distance from start (km)")
plot_adcp(adcp_ds, ax1)
add_waypoint_markers(ax1, waypoint_distances, offset=0)

# drifters
ax2.set_title(r"$\bf{c}$" + ") Surface drifters")
plot_drifters(
    drifter_ds,
    ax2,
    vmin=drifter_ds.temperature.min(),
    vmax=drifter_ds.temperature.max(),
)

# CTD (temperature)
ax3.set_title(r"$\bf{d}$" + ") CTD (temperature)")
ax3.set_ylabel("Depth (m)")
ax3.set_xlabel("Distance from start (km)")
plot_ctd(
    ctd_ds,
    ax3,
    plot_variable="temperature",
    vmin=ctd_ds.temperature.min(),
    vmax=ctd_ds.temperature.max(),
)
add_waypoint_markers(ax3, waypoint_distances, offset=25)

# CTD (oxygen)
ax4.set_title(r"$\bf{e}$" + ") CTD (oxygen)")
ax4.set_xlabel("Distance from start (km)")
plot_ctd(
    ctd_bgc_ds, ax4, plot_variable="oxygen", vmin=0, vmax=ctd_bgc_ds.o2.max()
)  # vmin tailored to mark red as approximate oxygen minimum zone (~ 45 mmol/m-3)
add_waypoint_markers(ax4, waypoint_distances, offset=0)


plt.tight_layout()
plt.show()

fig.savefig("figure1.png", dpi=300)

# %%
