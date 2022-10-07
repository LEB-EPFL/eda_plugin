import os
from pymm_eventserver.data_structures import MMSettings


def test_datastore(mock_datastore, datastore_save_path):
    assert mock_datastore.get_save_path() is None
    assert datastore_save_path.get_save_path() == os.path.dirname(__file__) + "/../data/FOV"


def test_java_settings(java_settings_mock):
    settings = MMSettings(java_settings_mock)
    print(settings)
    assert settings.n_channels == 2