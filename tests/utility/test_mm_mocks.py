import pytest
from unittest import mock
import importlib
import os


@pytest.fixture
def mock_datastore():
    mockup = mock.MagicMock()
    mockup.get_save_path.return_value = None
    yield mockup


@pytest.fixture
def datastore_save_path():
    mockup = mock.MagicMock()
    mockup.get_save_path.return_value = os.path.dirname(__file__) + "/../data/FOV_"
    yield mockup


def test_datastore(mock_datastore, datastore_save_path):
    assert mock_datastore.get_save_path() is None
    assert datastore_save_path.get_save_path() == os.path.dirname(__file__) + "/../data/FOV_"
