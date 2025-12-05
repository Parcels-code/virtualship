import numpy as np
import xarray as xr


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


def ctd_descent_only(ds, variable):
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
