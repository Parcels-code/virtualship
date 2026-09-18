import pandas as pd
import pytest

from virtualship.cli._initialise import _load_mfp_export, _mfp_to_yaml
from virtualship.models import Expedition, Port, Waypoint
from virtualship.utils import _get_example_expedition


def test_get_example_expedition():
    assert len(_get_example_expedition()) > 0


def test_valid_example_expedition(tmp_path):
    path = tmp_path / "test.yaml"
    with open(path, "w") as file:
        file.write(_get_example_expedition())

    Expedition.from_yaml(path)


def valid_mfp_data():
    return pd.DataFrame(
        {
            "Station": [
                "Departure Port",
                "Station1",
                "Station2",
                "Station3",
                "Arrival Port",
            ],
            "Type": ["Departure Port", "CTD", "CTD", "CTD", "Arrival Port"],
            "Latitude": [30.8, 31.2, 32.5, 33.1, 34.0],
            "Longitude": [-44.3, -45.1, -46.7, -47.2, -48.0],
            "Sea Depth": [100, 200, 300, 400, 500],
            "Time at Station": [
                "0d 00h 00m",
                "0d 01h 00m",
                "0d 01h 00m",
                "0d 01h 00m",
                "0d 00h 00m",
            ],
            "Travel Time to Next": [
                "0d 05h 00m",
                "0d 06h 00m",
                "0d 04h 00m",
                "0d 03h 00m",
                None,
            ],
            "Distance to Next (NM)": [50, 60, 40, 30, None],
            "Ship Speed (kn)": [10, 10, 10, 10, None],
            "EEZ": ["EEZ1", "EEZ1", "EEZ2", "EEZ2", "EEZ2"],
        }
    )


@pytest.fixture
def valid_excel_mfp_file(tmp_path):
    path = tmp_path / "file.xlsx"
    valid_mfp_data().to_excel(path, index=False)
    return path


@pytest.fixture
def valid_excel_mfp_file_with_commas(tmp_path):
    path = tmp_path / "file.xlsx"
    df = valid_mfp_data()
    df["Latitude"] = df["Latitude"].astype(str).str.replace(".", ",")
    df["Longitude"] = df["Longitude"].astype(str).str.replace(".", ",")
    df.to_excel(path, index=False)
    return path


@pytest.fixture
def invalid_mfp_file(tmp_path):
    """File missing required MFP columns."""
    path = tmp_path / "file.xlsx"
    df = pd.DataFrame({"WrongColumn": [1, 2, 3]})
    df.to_excel(path, index=False)
    return path


@pytest.fixture
def unsupported_extension_mfp_file(tmp_path):
    path = tmp_path / "file.unsupported"
    valid_mfp_data().to_csv(path, index=False)
    return path


@pytest.fixture
def nonexistent_mfp_file(tmp_path):
    return tmp_path / "non_file.xlsx"


@pytest.fixture
def missing_columns_mfp_file(tmp_path):
    path = tmp_path / "file.xlsx"
    valid_mfp_data().drop(columns=["Longitude"]).to_excel(path, index=False)
    return path


@pytest.fixture
def missing_ports_mfp_file(tmp_path):
    path = tmp_path / "file.xlsx"
    # remove rows marked as departure or arrival ports
    df = valid_mfp_data()
    df = df[~df["Station"].str.contains("Port")]
    df.to_excel(path, index=False)
    return path


@pytest.fixture
def all_ports_mfp_file(tmp_path):
    """MFP export with only ports, i.e. no waypoint stations."""
    path = tmp_path / "file.xlsx"
    df = valid_mfp_data()
    df["Station"] = ["Departure Port", "Port", "Port", "Port", "Arrival Port"]
    df["Type"] = df["Station"]
    df.to_excel(path, index=False)
    return path


@pytest.fixture
def unexpected_header_mfp_file(tmp_path):
    path = tmp_path / "file.xlsx"
    df = valid_mfp_data()
    df["Unexpected Column"] = ["Extra1", "Extra2", "Extra3", "Extra4", "Extra5"]
    df.to_excel(path, index=False)
    return path


@pytest.fixture
def mfp_file_with_junk_columns(tmp_path):
    """MFP export containing pandas-generated 'Unnamed' junk columns."""
    path = tmp_path / "file.xlsx"
    df = valid_mfp_data()
    df[""] = range(len(df))  # empty column with no name
    df.to_excel(path, index=True)  # index=True creates an 'Unnamed: 0' column
    return path


@pytest.mark.parametrize(
    "fixture_name",
    ["valid_excel_mfp_file", "valid_excel_mfp_file_with_commas"],
)
def test_mfp_to_yaml_success(request, fixture_name, tmp_path):
    """Test that _mfp_to_yaml correctly processes a valid MFP Excel export."""
    valid_mfp_file = request.getfixturevalue(fixture_name)
    yaml_output_path = tmp_path / "expedition.yaml"
    start_date = "2023-10-20 01:00:00"

    _mfp_to_yaml(valid_mfp_file, start_date, yaml_output_path)

    # Ensure the YAML file was written
    assert yaml_output_path.exists()

    # Load YAML and validate contents
    data = Expedition.from_yaml(yaml_output_path)

    # 3 waypoints + 2 ports (departure & arrival)
    assert len(data.schedule.waypoints) == 5
    assert isinstance(data.schedule.waypoints[0], Port)
    assert isinstance(data.schedule.waypoints[-1], Port)
    assert isinstance(data.schedule.waypoints[1], Waypoint)


@pytest.mark.parametrize(
    "fixture_name,error,match",
    [
        pytest.param(
            "nonexistent_mfp_file",
            FileNotFoundError,
            r"File not found:",
            id="FileNotFound",
        ),
        pytest.param(
            "unsupported_extension_mfp_file",
            RuntimeError,
            "Could not read coordinates data from the provided file. Ensure it is an exported .xlsx file from MFP.",
            id="UnsupportedExtension",
        ),
        pytest.param(
            "invalid_mfp_file",
            ValueError,
            r"Error: Found columns .* but expected columns .*",
            id="InvalidFile",
        ),
        pytest.param(
            "missing_columns_mfp_file",
            ValueError,
            r"Error: Found columns .* but expected columns .*",
            id="MissingColumns",
        ),
    ],
)
def test_mfp_to_yaml_exceptions(request, fixture_name, error, match, tmp_path):
    """Test that _mfp_to_yaml raises an error when input file is not valid."""
    fixture = request.getfixturevalue(fixture_name)
    yaml_output_path = tmp_path / "expedition.yaml"
    start_date = "1998-05-01 01:00:00"

    with pytest.raises(error, match=match):
        _mfp_to_yaml(fixture, start_date, yaml_output_path)


def test_mfp_to_yaml_extra_headers(unexpected_header_mfp_file, tmp_path):
    """Test that _mfp_to_yaml prints a warning when extra columns are found."""
    yaml_output_path = tmp_path / "expedition.yaml"
    start_date = "1998-05-01 01:00:00"

    with pytest.warns(UserWarning, match="Found additional unexpected columns.*"):
        _mfp_to_yaml(unexpected_header_mfp_file, start_date, yaml_output_path)


def test_mfp_to_yaml_missing_ports_warning(missing_ports_mfp_file, tmp_path):
    """Test that _mfp_to_yaml warns when departure or arrival ports are missing."""
    yaml_output_path = tmp_path / "expedition.yaml"
    start_date = "1998-05-01 01:00:00"

    with pytest.warns(
        UserWarning,
        match="The MFP export is missing either a 'Departure Port' or 'Arrival Port'",
    ):
        _mfp_to_yaml(missing_ports_mfp_file, start_date, yaml_output_path)


def test_mfp_to_yaml_no_science_stations_warning(all_ports_mfp_file, tmp_path):
    """Test that _mfp_to_yaml warns when the MFP export contains no non-port waypoints."""
    yaml_output_path = tmp_path / "expedition.yaml"
    start_date = "1998-05-01 01:00:00"

    with pytest.warns(
        UserWarning,
        match="The MFP export contains no waypoint stations",
    ):
        _mfp_to_yaml(all_ports_mfp_file, start_date, yaml_output_path)

    data = Expedition.from_yaml(yaml_output_path)
    assert all(isinstance(wp, Port) for wp in data.schedule.waypoints)


def test_load_mfp_export_drops_junk_columns(mfp_file_with_junk_columns):
    """_load_mfp_export should drop pandas' auto-generated 'Unnamed' junk columns, whilst preserving all genuine MFP columns."""
    mfp_data = _load_mfp_export(mfp_file_with_junk_columns)

    assert not any(col.startswith("Unnamed:") for col in mfp_data.columns), (
        f"Got junk 'Unnamed' columns: {list(mfp_data.columns)}"
    )

    expected_columns = list(valid_mfp_data().columns)
    assert list(mfp_data.columns) == expected_columns, (
        f"Expected core MFP columns {expected_columns} to be preserved, got {list(mfp_data.columns)}"
    )

    mfp_data = mfp_data.reset_index(drop=True)
    expected = valid_mfp_data()
    assert list(mfp_data["Station"]) == list(expected["Station"])
    assert list(mfp_data["Latitude"]) == list(expected["Latitude"])
    assert list(mfp_data["EEZ"]) == list(expected["EEZ"])
