"""Test configuration that is run for every test."""

import pytest


@pytest.fixture
def tmp_file(tmp_path):
    file = tmp_path / "test.txt"
    file.touch()
    return file


@pytest.fixture(autouse=True)
def test_in_working_dir(request, monkeypatch):
    """
    Set the working directory for each test to the directory of that test.

    :param request: -
    :param monkeypatch: -
    """
    monkeypatch.chdir(request.fspath.dirname)
