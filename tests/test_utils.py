from virtualship.models import Expedition
from virtualship.utils import get_example_expedition


def test_get_example_expedition():
    assert len(get_example_expedition()) > 0


def test_valid_example_expedition(tmp_path):
    path = tmp_path / "test.yaml"
    with open(path, "w") as file:
        file.write(get_example_expedition())

    Expedition.from_yaml(path)
