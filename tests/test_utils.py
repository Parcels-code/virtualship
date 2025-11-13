from virtualship.models import Schedule, ShipConfig
from virtualship.utils import get_example_config, get_example_schedule


def test_get_example_config():
    assert len(get_example_config()) > 0


def test_get_example_schedule():
    assert len(get_example_schedule()) > 0


def test_valid_example_config(tmp_path):
    path = tmp_path / "test.yaml"
    with open(path, "w") as file:
        file.write(get_example_config())

    ShipConfig.from_yaml(path)


def test_valid_example_schedule(tmp_path):
    path = tmp_path / "test.yaml"
    with open(path, "w") as file:
        file.write(get_example_schedule())

    Schedule.from_yaml(path)
