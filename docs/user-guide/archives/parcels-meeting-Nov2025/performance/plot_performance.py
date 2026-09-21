import numpy as np
import pandas as pd
from matplotlib import pyplot as plt

# data
df_default = pd.read_csv("results/performance_results.csv")
df_fromdata = pd.read_csv("results/performance_results_fromdata.csv")

## plot
fig, ax = plt.subplots(1, 1, figsize=(12, 7), dpi=96)

MARKERSIZE = 75
LINEWIDTH = 2.5
ymin, ymax, interval = 0, 800, 100

FROM_DATA = True
LAST_POINT = True

SHOW_UNDERWAY_FROMDATA = False

xticks = [
    "Just CTD",
    "CTD + CTD_BGC",
    "CTD + CTD_BGC \n+ Drifters",
    "CTD + CTD_BGC \n+ Drifters + Argo Floats",
    "CTD + CTD_BGC \n+ Drifters + Argo Floats \n+ ADCP/Underway S/T",
]

# default
ax.scatter(
    df_default["Directory"],
    df_default["Time (s)"],
    label="on-the-fly (via copernicusmarine)",
    color="dodgerblue",
    s=MARKERSIZE,
    zorder=3,
)
ax.plot(
    df_default["Directory"],
    df_default["Time (s)"],
    lw=LINEWIDTH,
    ls="dotted",
    color="dodgerblue",
    zorder=3,
)

# fromdata
if FROM_DATA:
    ax.scatter(
        df_fromdata["Directory"] if LAST_POINT else df_fromdata["Directory"][:-1],
        df_fromdata["Time (s)"] if LAST_POINT else df_fromdata["Time (s)"][:-1],
        label="from-data (pre-downloaded data)",
        color="crimson",
        s=MARKERSIZE,
        zorder=3,
    )
    ax.plot(
        df_fromdata["Directory"] if LAST_POINT else df_fromdata["Directory"][:-1],
        df_fromdata["Time (s)"] if LAST_POINT else df_fromdata["Time (s)"][:-1],
        lw=LINEWIDTH,
        ls="dotted",
        color="crimson",
        zorder=3,
    )

# x/y ticks/lims
if not SHOW_UNDERWAY_FROMDATA:
    ax.set_ylim(ymin, ymax + interval)
    yticks = np.arange(ymin, ymax + 1, interval)
elif SHOW_UNDERWAY_FROMDATA:
    ax.set_ylim(ymin, ymax * 5 + interval)
    yticks = np.arange(ymin, ymax * 5 + 1, 5 * interval)
ax.set_yticks(yticks)
ax.set_yticklabels([round(val, 0) for val in yticks / 60.0])  # [minutes]
ax.set_xticks(range(len(xticks)))
ax.set_xticklabels(xticks, rotation=45, ha="right")

# axes labels
ax.set_ylabel("Time (minutes)")

# grid
ax.set_facecolor("gainsboro")
ax.grid(True, alpha=1.0, color="white")

# title
# ax.set_title("MHW expedition performance [64GB RAM, 8 cores]")

plt.legend(loc="upper left")

plt.tight_layout()
plt.show()


# TODO: add machine spec info to plot (annotate or whatever)
