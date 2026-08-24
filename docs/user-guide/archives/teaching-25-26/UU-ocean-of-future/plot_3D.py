"""N.B. Quick, inflexible (under active development) version whilst experimenting best approaches!"""  # noqa: D400
# TODO: WORK IN PROGRESS

# %%
import os
from glob import glob

import cmocean.cm as cmo
import matplotlib as mpl
import numpy as np
import plotly.graph_objects as go
import xarray as xr

var = "temperature"  # change this to your chosen variable


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
        "label": "Salinity (psu)",
        "ds_name": "salinity",
    },
    "oxygen": {
        "cmap": cmo.oxy,
        "label": r"Dissolved oxygen (mmol m$^{-3}$)",
        "ds_name": "o2",
    },
    "nitrate": {
        "cmap": cmo.matter,
        "label": r"Nitrate (mmol m$^{-3}$)",
        "ds_name": "no3",
    },
    "phosphate": {
        "cmap": cmo.matter,
        "label": r"Phosphate (mmol m$^{-3}$)",
        "ds_name": "po4",
    },
    "ph": {
        "cmap": cmo.balance,
        "label": "pH",
        "ds_name": "ph",
    },
    "phytoplankton": {
        "cmap": cmo.algae,
        "label": r"Total phytoplankton (mmol m$^{-3}$)",
        "ds_name": "phyc",
    },
    "primary_production": {
        "cmap": cmo.matter,
        "label": r"Total primary production of phytoplankton (mg m$^{-3}$ day$^{-1}$)",
        "ds_name": "nppv",
    },
    "chlorophyll": {
        "cmap": cmo.algae,
        "label": r"Chlorophyll (mg m$^{-3}$)",
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


# 1d array of depth dimension (from deepest trajectory)
traj_idx, obs_idx = np.where(z_up == np.nanmin(z_up))
z1d = z_up.values[traj_idx[0], :]

# distance as 1d array
distance_1d = d_up.isel(obs=0)

# %%

## plotting

# trim to upper 600m
var_trim = var_concat.where(z_up >= -600)

# Convert cmo.thermal to Plotly colorscale
thermal_cmap = cmo.thermal
thermal_colorscale = [
    [i / 255, mpl.colors.rgb2hex(thermal_cmap(i / 255))] for i in range(256)
]

# meshgrid for 3D plotting
expeditions = var_trim["expedition"].values
trajectories = distance_1d.values
depths = z1d

xx, yy, zz = np.meshgrid(expeditions, trajectories, depths, indexing="ij")

# values
values = var_trim.values  # shape: (expedition, trajectory, obs)
valid_values = values[~np.isnan(values)]
isomin = np.nanpercentile(valid_values, 2.5)
isomax = np.nanpercentile(valid_values, 97.5)

fig = go.Figure(
    data=go.Volume(
        x=xx.flatten(),
        y=yy.flatten() / 1000.0,  # convert to km
        z=zz.flatten(),
        value=np.nan_to_num(values, nan=-9999).flatten(),
        isomin=isomin,
        isomax=isomax,
        opacity=0.3,
        surface_count=21,
        # opacityscale=[[2, 0.2], [5, 0.5], [5, 0.5], [8, 1]],
        # opacityscale="extremes",
        # colorscale=thermal_colorscale,
        caps=dict(x_show=False, y_show=False, z_show=False),  # Hide caps for clarity
    )
)

fig.update_layout(
    scene=dict(
        zaxis=dict(title="Depth (m)", range=[-600, 0]),
        yaxis=dict(
            title="Distance from start (km)",
            range=[0, np.nanmax(trajectories) / 1000.0],
        ),
        xaxis=dict(
            title="Year",
            tickvals=np.array([i for i in range(len(expeditions))])[::-1],
            ticktext=[
                str(np.datetime64(times[i], "Y")) for i in range(len(expeditions))
            ][::-1],
        ),
    ),
    margin=dict(l=0, r=0, b=0, t=40),
    title="3D Volume Plot of " + VARIABLES[var]["label"],
)

fig.show()

fig.write_html(f"./sample_3D_{var}.html")
