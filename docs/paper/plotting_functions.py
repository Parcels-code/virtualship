import cartopy.crs as ccrs
import cmocean.cm as cmo
import matplotlib.colors as mcolors
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
from cartopy import feature as cfeature
from matplotlib.collections import LineCollection

# =====================================================
# plotting
# =====================================================


# Drifters
def plot_drifters(drifter_ds, ax, vmin, vmax, PLOT_VARIABLE="temperature"):
    """Plot drifter trajectories; cmap by temperature."""
    MARKERSIZE = 45.0  # for release location marking
    PROJ = ccrs.PlateCarree()
    LATLON_BUFFER = 1.0  # degrees (adjust this to 'zoom' in/out in the plot)

    for i, traj in enumerate(drifter_ds["trajectory"]):
        # extract trajectory data
        lons = drifter_ds["lon"][:].sel(trajectory=traj).squeeze().values
        lats = drifter_ds["lat"][:].sel(trajectory=traj).squeeze().values
        var = drifter_ds[PLOT_VARIABLE][:].sel(trajectory=traj).squeeze().values

        # segments for LineCollection
        points = np.array([lons, lats]).T.reshape(-1, 1, 2)
        segments = np.concatenate([points[:-1], points[1:]], axis=1)

        # coloured by temperature
        lc = LineCollection(
            segments,
            cmap=cmo.thermal,
            norm=mcolors.Normalize(vmin=vmin, vmax=vmax),
            array=var[:-1],
            linewidth=1.5,
            zorder=3,
            transform=PROJ,
        )
        ax.add_collection(lc)

        # add release location
        ax.scatter(
            lons[0],
            lats[0],
            marker="o",
            s=MARKERSIZE,
            color="white",
            edgecolor="black",
            zorder=4,
            transform=PROJ,
            label="Waypoint" if i == 0 else None,  # only label first for legend
        )

    # additional map features
    ax.set_extent(
        [
            drifter_ds.lon.min() - LATLON_BUFFER,
            drifter_ds.lon.max() + LATLON_BUFFER,
            drifter_ds.lat.min() - LATLON_BUFFER,
            drifter_ds.lat.max() + LATLON_BUFFER,
        ],
        crs=PROJ,
    )
    ax.coastlines(linewidth=0.5, color="black")
    ax.add_feature(cfeature.LAND, facecolor="tan")

    gl = ax.gridlines(
        draw_labels=True,
        linewidth=0.5,
        color="gainsboro",
        alpha=1.0,
        linestyle="-",
        zorder=0,
    )
    gl.top_labels = False
    gl.right_labels = False

    # add colorbar
    _add_cmap(
        drifter_ds[PLOT_VARIABLE], cmo.thermal, ax, "Temperature (°C)", vmin, vmax
    )

    # legend
    ax.legend(loc="best", fontsize=10)


# CTDs
def plot_ctd(ds, ax, plot_variable, vmin, vmax, axes_labels=False):
    MAP_VARNAMES = {"temperature": "temperature", "oxygen": "o2"}

    MAP_CMAPS = {
        "temperature": cmo.thermal,
        "oxygen": cmo.oxy,
    }
    MAP_LABELS = {
        "temperature": "Temperature (°C)",
        "oxygen": "Oxygen (mmol m$^{-3}$)",
    }

    ctd_distance = _ctd_distance_along_expedition(ds)

    # exract descent-only data
    z_down = _ctd_descent_only(ctd_distance, "z")
    d_down = _ctd_descent_only(ctd_distance, "distance")
    var_down = _ctd_descent_only(ctd_distance, MAP_VARNAMES[plot_variable])

    # 1d array of depth dimension (from deepest trajectory)
    traj_idx, obs_idx = np.where(z_down == np.nanmin(z_down))
    z1d = z_down.values[traj_idx[0], :]

    # distance as 1d array
    distance_1d = d_down.isel(obs=0)

    # regularised transect
    profile_indices, distance_regular = _get_profile_indices(distance_1d)
    var_masked = _build_masked_array(var_down, profile_indices, len(distance_regular))

    # plot regularised transect
    ax.grid(
        True, which="both", color="lightgrey", linestyle="-", linewidth=0.7, alpha=0.5
    )

    pm = ax.pcolormesh(
        distance_regular / 1000,  # distance in km
        z1d,
        var_masked.T,
        cmap=MAP_CMAPS[plot_variable],
        vmin=vmin,
        vmax=vmax,
    )

    _add_cmap(
        ds[MAP_VARNAMES[plot_variable]],
        MAP_CMAPS[plot_variable],
        ax,
        MAP_LABELS[plot_variable],
        shrink=1.00,
        vmin=vmin,
        vmax=vmax,
    )

    if axes_labels:
        ax.set_ylabel("Depth (m)")
        ax.set_xlabel("Distance from start (km)")

    return pm, distance_regular, var_masked


# ADCP
def plot_adcp(ds, ax, axes_labels=False):
    """Absolute velocity plot."""
    CMAP = cmo.tempo

    distance_1d = _adcp_distance_along_expedition(ds.isel(trajectory=0))
    vel, _, _, _ = calc_velocities(ds)
    landmask = xr.where(((ds["U"] == 0) & (ds["V"] == 0)), 1, np.nan)

    # adcp data
    ax.pcolormesh(
        distance_1d / 1000,
        ds["z"],
        vel,
        cmap=CMAP,
    )

    # seabed
    ax.pcolormesh(
        distance_1d / 1000,  # distance in km
        ds["z"],
        landmask,
        cmap=mcolors.ListedColormap([mcolors.to_rgba("tan"), mcolors.to_rgba("white")]),
    )

    ax.set_xlim(0, distance_1d.max() / 1000)

    # legend for sea bed
    tan_patch = mpatches.Patch(color=mcolors.to_rgba("tan"), label="Seabed")
    ax.legend(handles=[tan_patch], loc="lower right")

    _add_cmap(
        vel,
        CMAP,
        ax,
        "Speed (m s$^{-1}$)",
        vel.min(),
        vel.max(),
        shrink=1.00,
    )

    # axis labels
    if axes_labels:
        ax.set_ylabel("Depth (m)")
        ax.set_xlabel("Distance from start (km)")


# =====================================================
# utility
# =====================================================


def _add_cmap(
    da,
    cmap,
    ax,
    label,
    vmin,
    vmax,
    orientation="horizontal",
    shrink=0.90,
):
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=mcolors.Normalize(vmin, vmax))
    sm._A = []
    plt.colorbar(
        sm,
        ax=ax,
        orientation=orientation,
        label=label,
        shrink=shrink,
    )


def _haversine(lon1, lat1, lon2, lat2):
    """Great-circle distance (meters) between two points."""
    lon1, lat1, lon2, lat2 = map(np.radians, [lon1, lat1, lon2, lat2])
    dlon, dlat = lon2 - lon1, lat2 - lat1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    return 6371000 * c


def _ctd_distance_along_expedition(ds):
    """Add 'distance' variable: cumulative meters travelled."""
    # cumulative distance travelled along waypoints

    d = np.zeros_like(ds["lon"], dtype=float)
    for ob in range(1, len(ds["lon"])):
        d[ob] = d[ob - 1] + _haversine(
            ds["lon"][ob - 1], ds["lat"][ob - 1], ds["lon"][ob], ds["lat"][ob]
        )
    ds["distance"] = xr.DataArray(
        d,
        dims=ds["lon"].dims,
        attrs={"long_name": "cumulative distance travelled", "units": "m"},
    )
    return ds


def _adcp_distance_along_expedition(ds):
    """Array of cumulative meters travelled along ADCP waypoints."""
    d = np.zeros_like(ds["lon"], dtype=float)
    for ob in range(1, len(ds["lon"])):
        d[ob] = d[ob - 1] + _haversine(
            ds["lon"][ob - 1], ds["lat"][ob - 1], ds["lon"][ob], ds["lat"][ob]
        )
    return d


def _ctd_descent_only(ds, variable):
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


def _build_masked_array(data_up, profile_indices, n_profiles):
    arr = np.full((n_profiles, data_up.shape[1]), np.nan)
    for i, idx in enumerate(profile_indices):
        if idx is not None:
            arr[i, :] = data_up.values[idx, :]
    return arr


def _get_profile_indices(distance_1d):
    """
    Returns regular distance bins and profile indices for CTD transect plotting.

    Bin size is set to one order of magnitude lower than max distance.
    """
    dist_min, dist_max = float(distance_1d.min()), float(distance_1d.max())
    if dist_max > 1e6:
        dist_step = 1.5e5
    elif dist_max > 1e5:
        dist_step = 1.5e4
    elif dist_max > 1e4:
        dist_step = 1.5e3
    else:
        dist_step = 1.5e2  # fallback for very short transects

    distance_regular = np.arange(dist_min, dist_max + dist_step, dist_step)
    threshold = dist_step / 2
    profile_indices = [
        np.argmin(np.abs(distance_1d.values - d))
        if np.min(np.abs(distance_1d.values - d)) < threshold
        else None
        for d in distance_regular
    ]
    return profile_indices, distance_regular


def calc_velocities(ds):
    """From U and V, calculate absolute, parallel and perpendicular (to the ship trajectory) velocities, as well as (compass) direction of flow."""
    Uabs = np.sqrt(ds["U"] ** 2 + ds["V"] ** 2)
    ds_surface = ds.isel(trajectory=0)
    dlon = np.deg2rad(ds_surface["lon"].differentiate("obs"))
    dlat = np.deg2rad(ds_surface["lat"].differentiate("obs"))
    lat = np.deg2rad(ds_surface["lat"])
    alpha = np.arctan(dlat / (dlon * np.cos(lat))).mean("obs")  # cruise direction angle
    Uparallel = np.cos(alpha) * ds["U"] + np.sin(alpha) * ds["V"]
    Uperp = -np.sin(alpha) * ds["U"] + np.cos(alpha) * ds["V"]
    direction_rad = np.arctan2(
        ds["U"], ds["V"]
    )  # direction of flow [degrees from north]
    direction_deg = (np.degrees(direction_rad) + 360) % 360

    return Uabs, Uparallel, Uperp, direction_deg
