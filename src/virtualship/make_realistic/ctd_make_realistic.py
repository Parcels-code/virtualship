"""ctd_make_realistic function."""

import random
from pathlib import Path

import numpy as np
import opensimplex
import xarray as xr


def ctd_make_realistic(
    zarr_path: str | Path,
    out_dir: str | Path,
    prefix: str,
) -> list[Path]:
    """
    Take simulated CTD data, add noise, then save in CNV format (1 file per CTD).

    :param zarr_path: Input simulated data.
    :param out_dir: Output directory for CNV file.
    :param prefix: Prefix for CNV files. Will be postnonsensor with '_{ctd_num}'.
    :returns: Paths to created file.
    """
    original = xr.open_zarr(zarr_path)

    files = []
    for ctd_i, traj in enumerate(original.trajectory):
        time = original.sel(trajectory=traj)["time"].values
        reltimesec = (time - time[0]) / np.timedelta64(1, "s")
        latitude = original.sel(trajectory=traj)["lat"].values
        longitude = original.sel(trajectory=traj)["lon"].values
        temperature = original.sel(trajectory=traj)["temperature"].values
        salinity = original.sel(trajectory=traj)["salinity"].values
        depth = original.sel(trajectory=traj)["z"].values

        temperature = _add_temperature_noise(temperature, depth)
        salinity = _add_salinity_noise(salinity, depth)

        out_file = Path(out_dir) / f"{prefix}{ctd_i}.cnv"

        files.append(out_file)

        cnv = _to_cnv(
            filename=str(out_file),
            latitudes=latitude,
            longitudes=longitude,
            times=reltimesec,
            temperatures=temperature,
            depths=depth,
            salinities=salinity,
            start_time=time[0],
        )

        with open(out_file, "w") as out_cnv:
            out_cnv.write(cnv)

    return files


def _add_temperature_noise(temperature: np.ndarray, depth: np.ndarray) -> np.ndarray:
    """
    Return the provided temperature with added noise.

    The noise is not a realistic nor based on anything physics, but simply an attempt to have the data look somewhat similar to a real CTD cast.

    :param temperature: The clean temperature.
    :param depth: Depth measured by CTD.
    :return: Temperature with added noise.
    """
    surface_noise = (
        2.0
        * (np.random.random_sample(len(temperature)) * 2.0 - 1)
        * np.exp(depth / 4.0)
    )
    noise = (
        0.05
        * np.maximum(1.0 + depth / 1000.0, 0.1)
        * np.random.random_sample(len(temperature))
    )
    drift = (
        0.3
        * (np.random.random() * 2.0 - 1)
        * np.array(range(len(temperature)))
        / len(temperature)
    )
    opensimplex.seed(np.random.randint(999999))
    noise2 = (
        2.0
        * np.maximum(1.0 + depth / 1000.0, 0.1)
        * (
            np.array([opensimplex.noise2(n / 30, 0.0) for n in range(len(temperature))])
            ** 8
        )
    )
    opensimplex.seed(np.random.randint(999999))
    noise3 = 0.1 * (
        np.array([opensimplex.noise2(n / 8, 0.0) for n in range(len(temperature))]) ** 2
    )

    return temperature + surface_noise + drift + noise + noise3 + noise2


def _add_salinity_noise(salinity: np.ndarray, depth: np.ndarray) -> np.ndarray:
    """
    Return the provided salinity with added noise.

    The noise is not a realistic nor based on anything physics, but simply an attempt to have the data look somewhat similar to a real CTD cast.

    :param salinity: The clean salinity.
    :param depth: Depth measured by CTD.
    :return: Salinity with added noise.
    """
    surface_noise = (
        2.0 * (-np.random.random_sample(len(salinity))) * np.exp(depth / 4.0)
    )
    noise = (
        0.001
        * np.maximum(1.0 + depth / 1000.0, 0.1)
        * np.random.random_sample(len(salinity))
    )
    drift = (
        0.02
        * (np.random.random() * 2.0 - 1)
        * np.array(range(len(salinity)))
        / len(salinity)
    )
    opensimplex.seed(np.random.randint(999999))
    noise2 = (
        0.07
        * np.maximum(1.0 + depth / 1000.0, 0.1)
        * (
            np.array([opensimplex.noise2(n / 30, 0.0) for n in range(len(salinity))])
            ** 8
        )
    )
    opensimplex.seed(np.random.randint(999999))
    noise3 = 0.003 * (
        np.array([opensimplex.noise2(n / 8, 0.0) for n in range(len(salinity))]) ** 2
    )

    return salinity + surface_noise + drift + noise + noise2 + noise3


def _to_cnv(
    filename: str,
    latitudes: np.ndarray,
    longitudes: np.ndarray,
    times: np.ndarray,
    temperatures: np.ndarray,
    depths: np.ndarray,
    salinities: np.ndarray,
    start_time: np.datetime64,
) -> str:
    """
    Convert data to CNV.

    :param filename: Output file name.
    :param latitudes: Latitude data.
    :param longitudes: Longitude data.
    :param times: Elapsed time since first measurement in seconds.
    :param temperatures: Temperature data.
    :param depths: Depth data.
    :param salinities: Salinity data.
    :param start_time: Start time of measuring. This will be in the header of the CNV file.
    :returns: The CNV.
    """
    formatted_time = np.datetime_as_string(start_time, unit="s")
    formatted_time = (
        np.datetime64(formatted_time)
        .astype("M8[s]")
        .item()
        .strftime("%b %d %Y %H:%M:%S")
    )

    header = rf"""
* Sea-Bird SBE 9 Data File:
* FileName = {filename}
# start_time = {formatted_time} [NMEA time, first data scan]
# bad_flag = -9.990e-29
# file_type = ascii
# name 0 = scan: Scan Count
# name 1 = timeS: Time, Elapsed [seconds]
# name 2 = latitude: Latitude [deg]
# name 3 = longitude: Longitude [deg]
# name 4 = depSM: Depth [salt water, m]
# name 5 = t090C: Temperature [ITS-90, deg C]
# name 6 = sal00: Salinity, Practical [PSU]
*END*
""".strip()

    random_time_offset = random.random()

    rows = [
        f"{_i_col(13 + 24 * n)}{_f_col(time + random_time_offset, 3)}{_f_col(lat, 5)}{_f_col(lon, 5)}{_f_col(-depth, 3)}{_f_col(temp, 4)}{_f_col(sal, 4)}"
        for n, (time, temp, lat, lon, depth, sal) in enumerate(
            zip(
                times,
                temperatures,
                latitudes,
                longitudes,
                depths,
                salinities,
                strict=False,
            )
        )
    ]

    cnv = header + "\n" + "\n".join(rows) + "\n"

    return cnv


def _make_column(val: str) -> str:
    return val.rjust(11)


def _i_col(val: int) -> str:
    return _make_column(str(val))


def _f_col(val: float, digits: int) -> str:
    return _make_column(str(round(val, digits)))
