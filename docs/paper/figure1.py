import os
import subprocess

SAMPLE_DIR = "sample_expedition/"
CONFIG = "expedition.yaml"
EXPEDITION = "MY_EXPEDITION"

# =====================================================
# `virtualship run` execution
# =====================================================

# execute simulation for prescribed expedition
if os.path.exists(f"{SAMPLE_DIR}{EXPEDITION}/results"):
    print("NOTE: Expedition already run, skipping execution.")
else:
    process = subprocess.run(["virtualship", "run", f"{SAMPLE_DIR}{EXPEDITION}"])


# =====================================================
# plotting
# =====================================================

# # VirtualShip output
# ctd_ds = xr.open_dataset(f"{SAMPLE_DIR}{EXPEDITION}/results/ctd.zarr")
# ctd_bgc = xr.open_dataset(f"{SAMPLE_DIR}{EXPEDITION}/results/ctd_bgc.zarr")
# # drifter_ds = xr.open_dataset(f"{SAMPLE_DIR}{EXPEDITION}/results/drifter.zarr")
# adcp_ds = xr.open_dataset(f"{SAMPLE_DIR}{EXPEDITION}/results/adcp.zarr")


# # plotting
# def plot_ctd(distance, z, data, cmap, ax):
#     ax.pcolormesh(
#         distance,
#         z,
#         data.T,
#         cmap=cmap,
#     )

#     ax.grid(
#         True, which="both", color="lightgrey", linestyle="-", linewidth=0.7, alpha=0.5
#     )

#     ax.set_ylabel("Depth (m)")
#     ax.set_xlabel("Distance from start (km)")
