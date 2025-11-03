from virtualship.models.expedition import Expedition
from virtualship.utils import get_example_expedition


def test_get_example_expedition():
    assert len(get_example_expedition()) > 0


def test_valid_example_expedition(tmp_path):
    path = tmp_path / "test.yaml"
    with open(path, "w") as file:
        file.write(get_example_expedition())

    Expedition.from_yaml(path)


def test_instrument_registry_updates():
    from virtualship import utils

    class DummyInputDataset:
        pass

    class DummyInstrument:
        pass

    utils.register_input_dataset("DUMMY_TYPE")(DummyInputDataset)
    utils.register_instrument("DUMMY_TYPE")(DummyInstrument)

    assert utils.INPUT_DATASET_MAP["DUMMY_TYPE"] is DummyInputDataset
    assert utils.INSTRUMENT_CLASS_MAP["DUMMY_TYPE"] is DummyInstrument
