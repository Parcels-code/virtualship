"""N.B. Quick (under active development) version whilst experimenting best approaches!"""  # noqa: D400
# TODO: WORK IN PROGRESS

# %%
import os
from glob import glob

import cmocean.cm as cmo
import matplotlib as mpl
import numpy as np
import plotly.graph_objs as go
import xarray as xr

var = "primary_production"  # change this to your chosen variable


base_dir = os.getcwd()
filename = "ctd.zarr" if var in ["temperature", "salinity"] else "ctd_bgc.zarr"
grp_dirs = sorted(glob(os.path.join(base_dir, "GRP????/results/", filename)))


VARIABLES = {
    "temperature": {
        "cmap": cmo.thermal,
        "label": "Temperature (°C)",
        "ds_name": "temperature",
    },
    "salinity": {
        "cmap": cmo.haline,
        "label": "Salinity (PSU)",
        "ds_name": "salinity",
    },
    "oxygen": {
        "cmap": cmo.oxy,
        "label": r"Dissolved oxygen (mmol m<sup>-3</sup>)",
        "ds_name": "o2",
    },
    "nitrate": {
        "cmap": cmo.matter,
        "label": r"Nitrate (mmol m<sup>-3</sup>)",
        "ds_name": "no3",
    },
    "phosphate": {
        "cmap": cmo.matter,
        "label": r"Phosphate (mmol m<sup>-3</sup>)",
        "ds_name": "po4",
    },
    "ph": {
        "cmap": cmo.balance,
        "label": "pH",
        "ds_name": "ph",
    },
    "phytoplankton": {
        "cmap": cmo.algae,
        "label": r"Total phytoplankton (mmol m<sup>-3</sup>)",
        "ds_name": "phyc",
    },
    "primary_production": {
        "cmap": cmo.matter,
        "label": "Total primary production of phytoplankton (mg m<sup>-3</sup> day<sup>-1</sup>)",
        "ds_name": "nppv",
    },
    "chlorophyll": {
        "cmap": cmo.algae,
        "label": "Chlorophyll (mg m<sup>-3</sup>)",
        "ds_name": "chl",
    },
}


def haversine(lon1, lat1, lon2, lat2):
    """Great-circle distance (meters) between two points."""
    lon1, lat1, lon2, lat2 = map(np.radians, [lon1, lat1, lon2, lat2])
    dlon, dlat = lon2 - lon1, lat2 - lat1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    return 6371000 * c


def distance_from_start(ds):
    """Add 'distance' variable: meters from first waypoint."""
    lon0, lat0 = (
        ds.isel(trajectory=0)["lon"].values[0],
        ds.isel(trajectory=0)["lat"].values[0],
    )
    d = np.zeros_like(ds["lon"].values, dtype=float)
    for ob, (lon, lat) in enumerate(zip(ds["lon"], ds["lat"], strict=False)):
        d[ob] = haversine(lon, lat, lon0, lat0)
    ds["distance"] = xr.DataArray(
        d,
        dims=ds["lon"].dims,
        attrs={"long_name": "distance from first waypoint", "units": "m"},
    )
    return ds


def descent_only(ds, variable):
    """Extract descending CTD data (downcast), pad with NaNs for alignment."""
    min_z_idx = ds["z"].argmin("obs")
    da_clean = []
    for i, traj in enumerate(ds["trajectory"].values):
        idx = min_z_idx.sel(trajectory=traj).item()
        descent_vals = ds[variable][
            i, : idx + 1
        ]  # take values from surface to min_z_idx (inclusive)
        da_clean.append(descent_vals)
    max_len = max(len(arr[~np.isnan(arr)]) for arr in da_clean)
    da_padded = np.full((ds["trajectory"].size, max_len), np.nan)
    for i, arr in enumerate(da_clean):
        da_dropna = arr[~np.isnan(arr)]
        da_padded[i, : len(da_dropna)] = da_dropna
    return xr.DataArray(
        da_padded,
        dims=["trajectory", "obs"],
        coords={"trajectory": ds["trajectory"], "obs": np.arange(max_len)},
    )


def build_masked_array(data_up, profile_indices, n_profiles):
    arr = np.full((n_profiles, data_up.shape[1]), np.nan)
    for i, idx in enumerate(profile_indices):
        if idx is not None:
            arr[i, :] = data_up.values[idx, :]
    return arr


def get_profile_indices(distance_1d):
    """
    Returns regular distance bins and profile indices for CTD transect plotting.

    Bin size is set to one order of magnitude lower than max distance.
    """
    dist_min, dist_max = float(distance_1d.min()), float(distance_1d.max())
    if dist_max > 1e6:
        dist_step = 1e5
    elif dist_max > 1e5:
        dist_step = 1e4
    elif dist_max > 1e4:
        dist_step = 1e3
    else:
        dist_step = 1e2  # fallback for very short transects

    distance_regular = np.arange(dist_min, dist_max + dist_step, dist_step)
    threshold = dist_step / 2
    profile_indices = [
        np.argmin(np.abs(distance_1d.values - d))
        if np.min(np.abs(distance_1d.values - d)) < threshold
        else None
        for d in distance_regular
    ]
    return profile_indices, distance_regular


# %%

# pre processing, concat to 3D array
expeditions = []
times = []
for i, path in enumerate(grp_dirs):
    ctd_ds = xr.open_dataset(path)

    # add distance from start
    ctd_distance = distance_from_start(ctd_ds)

    # extract descent-only data
    if i == 0:
        z_up = descent_only(ctd_distance, "z")
        d_up = descent_only(ctd_distance, "distance")
    var_up = descent_only(ctd_distance, VARIABLES[var]["ds_name"])

    # append
    expeditions.append(var_up)
    times.append(ctd_ds["time"][0][0].values)

# concat
var_concat = xr.concat(expeditions, dim="expedition")
var_concat["expedition"] = times

# 1d array of depth dimension (from deepest trajectory)
traj_idx, obs_idx = np.where(z_up == np.nanmin(z_up))
z1d = z_up.values[traj_idx[0], :]

# distance as 1d array
distance_1d = d_up.isel(obs=0)

# %%

## plotting (interactive with Plotly)

depth_lim = -200  # [m]

# trim to upper 600m
var_trim = var_concat.where(z_up >= depth_lim)


# Prepare colorscale for Plotly from matplotlib colormap
def mpl_to_plotly(cmap, n=256):
    return [[i / (n - 1), mpl.colors.rgb2hex(cmap(i / (n - 1)))] for i in range(n)]


plotly_cmap = mpl_to_plotly(VARIABLES[var]["cmap"])

# Prepare slider steps
steps = []
data = []
for t in range(var_trim.shape[0]):
    seabed = xr.where(np.isnan(var_trim[t]), 1, None).T

    # main cross-section
    trace = go.Heatmap(
        z=var_trim[t].T,
        x=distance_1d / 1000.0,  # distance in km
        y=z1d,
        zmin=np.nanmin(var_trim.values),
        zmax=np.nanmax(var_trim.values),
        colorscale=plotly_cmap,
        colorbar=dict(title=VARIABLES[var]["label"]),
        showscale=True,
        visible=(t == 0),
        customdata=None,
        hovertemplate="Distance: %{x:.2f} km<br>Depth: %{z:.1f} m<br>Value: %{value:.2f}<extra></extra>",
    )
    # Seabed overlay (tan color)
    seabed_trace = go.Heatmap(
        z=seabed,
        x=distance_1d / 1000.0,  # distance in km
        y=z1d,
        colorscale=[[0, "tan"], [1, "tan"]],
        showscale=False,
        opacity=1.0,
        visible=(t == 0),
        name="Land / sea bed",
        hoverinfo="skip",
    )
    data.append(trace)
    data.append(seabed_trace)
    steps.append(
        {
            "method": "update",
            "args": [
                {"visible": [i // 2 == t for i in range(2 * var_trim.shape[0])]},
                {
                    "title": f"{VARIABLES[var]['label']} (Date {np.datetime_as_string(var_trim['expedition'][t].values, unit='D')})"
                },
            ],
            "label": str(
                np.datetime_as_string(var_trim["expedition"][t].values, unit="D")
            ),
        }
    )

sliders = [
    dict(active=0, currentvalue={"prefix": "Date: "}, pad={"t": 50}, steps=steps)
]

layout = go.Layout(
    title=f"{VARIABLES[var]['label']} (Date {np.datetime_as_string(var_trim['expedition'][0].values, unit='D')})",
    xaxis=dict(
        title="Distance from start (km)",
        tickvals=(distance_1d / 1000.0),
        tickformat=".0f",
    ),
    yaxis=dict(
        title="Depth (m)",
        range=[depth_lim, np.nanmax(z1d)],
    ),
    sliders=sliders,
    legend=dict(itemsizing="constant"),
    width=900,
    height=600,
)

fig = go.Figure(data=data, layout=layout)
fig.show()

fig.write_html(f"./sample_slider_{var}.html")


# %%
