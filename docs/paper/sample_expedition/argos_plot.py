# %%
import copernicusmarine
import numpy as np
import plotly.graph_objects as go
import xarray as xr

from virtualship.utils import BATHYMETRY_ID

# %%
bathy_ds = copernicusmarine.open_dataset(BATHYMETRY_ID)

# %%
argo_ds = xr.open_zarr("./ARGOS/results/argo_float.zarr")
# argo_ds = xr.open_zarr(
#     "~/Documents/test_expeditions/argos/ARGO/results/argo_float.zarr"
# )

WHICH_ARGO = 0  # index of the argo float to plot
PLOT_VARIABLE = "temperature"  # "temperature" or "salinity"

fig = go.Figure()

VARIABLES = {
    "temperature": {
        "cmap": "Inferno",
        "label": "Temperature (°C)",
        "ds_name": "temperature",
    },
    "salinity": {
        "cmap": "haline",
        "label": "Salinity (psu)",
        "ds_name": "salinity",
    },
}

argo_n = argo_ds["trajectory"][WHICH_ARGO]

lons = argo_ds["lon"][:].sel(trajectory=argo_n).squeeze()
lats = argo_ds["lat"][:].sel(trajectory=argo_n).squeeze()
depth = argo_ds["z"][:].sel(trajectory=argo_n).squeeze()
var = argo_ds[VARIABLES[PLOT_VARIABLE]["ds_name"]][:].sel(trajectory=argo_n).squeeze()

# vertical sampling locations, mask out NaNs (temp/salinity not recorded when drifting)
mask = ~np.isnan(var)
lons_vertical = np.array(lons)[mask]
lats_vertical = np.array(lats)[mask]
depth_vertical = np.array(depth)[mask]
var_vertical = np.array(var)[mask]

# trajectory locations outside of vertical profile points
cycle_phase = argo_ds["cycle_phase"][:].sel(trajectory=argo_n).squeeze()
drift_mask = np.where(cycle_phase != 4, True, False)
lons_traj = np.array(lons)[drift_mask]
lats_traj = np.array(lats)[drift_mask]
depth_traj = np.array(depth)[drift_mask]

MARKERSIZE = 7.5

# waypoint/release location
fig.add_trace(
    go.Scatter3d(
        x=[lons_traj[0]],
        y=[lats_traj[0]],
        z=[0],
        mode="markers",
        marker=dict(
            size=MARKERSIZE,
            color="white",
            line=dict(color="black", width=4),
        ),
    )
)

# trajectory
fig.add_trace(
    go.Scatter3d(
        x=lons_traj,
        y=lats_traj,
        z=depth_traj,
        mode="markers",
        marker=dict(
            size=MARKERSIZE * 0.3,
            color="gray",
        ),
    )
)

# vertical profiles
fig.add_trace(
    go.Scatter3d(
        x=lons_vertical,
        y=lats_vertical,
        z=depth_vertical,
        mode="markers",
        marker=dict(
            size=MARKERSIZE,
            color=var_vertical,
            colorscale=VARIABLES[PLOT_VARIABLE]["cmap"],
            colorbar=dict(
                title=VARIABLES[PLOT_VARIABLE]["label"], orientation="h", y=-0.25, x=0.5
            ),
            opacity=1.0,
        ),
        name=f"Argo {WHICH_ARGO + 1}",
        customdata=np.stack([var], axis=-1),
        hovertemplate=(
            "Lon: %{x:.3f}<br>"
            "Lat: %{y:.3f}<br>"
            "Depth: %{z:.1f} m<br>"
            f"{VARIABLES[PLOT_VARIABLE]['label']}: "
            + "%{customdata[0]:.3f}<extra></extra>"
        ),
    )
)

# bathymetry
buff = 1.0
lon_bathy = bathy_ds["longitude"].sel(
    longitude=slice(lons.min() - buff, lons.max() + buff)
)
lat_bathy = bathy_ds["latitude"].sel(
    latitude=slice(lats.min() - buff, lats.max() + buff)
)
z_bathy = bathy_ds["deptho"].sel(
    longitude=slice(lons.min() - buff, lons.max() + buff),
    latitude=slice(lats.min() - buff, lats.max() + buff),
)

# meshgrid for plotting
lon_grid, lat_grid = np.meshgrid(lon_bathy.values, lat_bathy.values)

fig.add_trace(
    go.Surface(
        x=lon_grid,
        y=lat_grid,
        z=-z_bathy.values,  # negative for depth
        colorscale="Earth_r",
        opacity=1.0,
        showscale=False,
        name="Bathymetry",
    )
)

fig.update_layout(
    scene=dict(
        xaxis_title="Longitude",
        yaxis_title="Latitude",
        zaxis_title="Depth (m)",
        yaxis=dict(autorange="reversed"),  # north is up from plot viewpoint
        xaxis=dict(autorange="reversed"),  # north is up from plot viewpoint
    ),
    width=800,
    height=800,
    showlegend=False,
)

fig.show()

# %%
