import os

import pandas as pd
import pytest

from virtualship.models import Expedition
from virtualship.utils import mfp_to_yaml


def valid_mfp_data():
    return pd.DataFrame(
        {
            "Station Type": ["A", "B", "C"],
            "Name": ["Station1", "Station2", "Station3"],
            "Latitude": [30.8, 31.2, 32.5],
            "Longitude": [-44.3, -45.1, -46.7],
        }
    )


# Fixture for Excel file
@pytest.fixture
def valid_excel_mfp_file(tmp_path):
    path = tmp_path / "file.xlsx"
    valid_mfp_data().to_excel(path, index=False)
    return path


# Fixture for CSV file
@pytest.fixture
def valid_csv_mfp_file(tmp_path):
    path = tmp_path / "file.csv"
    valid_mfp_data().to_csv(path, index=False)
    return path


@pytest.fixture
def valid_csv_mfp_file_with_commas(tmp_path):
    path = tmp_path / "file.csv"
    valid_mfp_data().to_csv(path, decimal=",", index=False)
    return path


@pytest.fixture
def invalid_mfp_file(tmp_path):
    path = tmp_path / "file.csv"
    valid_mfp_data().to_csv(path, decimal=",", sep="|", index=False)

    return path


@pytest.fixture
def unsupported_extension_mfp_file(tmp_path):
    path = tmp_path / "file.unsupported"
    valid_mfp_data().to_csv(path, index=False)

    return path


@pytest.fixture
def nonexistent_mfp_file(tmp_path):
    path = tmp_path / "non_file.csv"

    return path


@pytest.fixture
def missing_columns_mfp_file(tmp_path):
    path = tmp_path / "file.xlsx"
    valid_mfp_data().drop(columns=["Longitude"]).to_excel(path, index=False)
    return path


@pytest.fixture
def unexpected_header_mfp_file(tmp_path):
    path = tmp_path / "file.xlsx"
    df = valid_mfp_data()
    df["Unexpected Column"] = ["Extra1", "Extra2", "Extra3"]
    df.to_excel(path, index=False)
    yield path


@pytest.mark.parametrize(
    "fixture_name",
    ["valid_excel_mfp_file", "valid_csv_mfp_file", "valid_csv_mfp_file_with_commas"],
)
def test_mfp_to_yaml_success(request, fixture_name, tmp_path):
    """Test that mfp_to_yaml correctly processes a valid MFP file."""
    valid_mfp_file = request.getfixturevalue(fixture_name)

    yaml_output_path = tmp_path / "expedition.yaml"

    # Run function (No need to mock open() for YAML, real file is created)
    mfp_to_yaml(valid_mfp_file, yaml_output_path)

    # Ensure the YAML file was written
    assert yaml_output_path.exists()

    # Load YAML and validate contents
    data = Expedition.from_yaml(yaml_output_path)

    assert len(data.schedule.waypoints) == 3


@pytest.mark.parametrize(
    "fixture_name,error,match",
    [
        pytest.param(
            "nonexistent_mfp_file",
            FileNotFoundError,
            os.path.basename("/non_file.csv"),
            id="FileNotFound",
        ),
        pytest.param(
            "unsupported_extension_mfp_file",
            RuntimeError,
            "Could not read coordinates data from the provided file. Ensure it is either a csv or excel file.",
            id="UnsupportedExtension",
        ),
        pytest.param(
            "invalid_mfp_file",
            ValueError,
            r"Error: Found columns \['Station Type\|Name\|Latitude\|Longitude'\], but expected columns \[.*('Station Type'|'Longitude'|'Latitude'|'Name').*\]. Are you sure that you're using the correct export from MFP\?",
            id="InvalidFile",
        ),
        pytest.param(
            "missing_columns_mfp_file",
            ValueError,
            (
                r"Error: Found columns \[.*?('Station Type'| 'Name'| 'Latitude').*?\], "
                r"but expected columns \[.*?('Station Type'| 'Name'| 'Latitude'| 'Longitude').*?\]."
            ),
            id="MissingColumns",
        ),
    ],
)
def test_mfp_to_yaml_exceptions(request, fixture_name, error, match, tmp_path):
    """Test that mfp_to_yaml raises an error when input file is not valid."""
    fixture = request.getfixturevalue(fixture_name)

    yaml_output_path = tmp_path / "expedition.yaml"

    with pytest.raises(error, match=match):
        mfp_to_yaml(fixture, yaml_output_path)


def test_mfp_to_yaml_extra_headers(unexpected_header_mfp_file, tmp_path):
    """Test that mfp_to_yaml prints a warning when extra columns are found."""
    yaml_output_path = tmp_path / "expedition.yaml"

    with pytest.warns(UserWarning, match="Found additional unexpected columns.*"):
        mfp_to_yaml(unexpected_header_mfp_file, yaml_output_path)
