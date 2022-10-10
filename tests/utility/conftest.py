import pytest
from unittest import mock
import importlib
import os
from pymm_eventserver.data_structures import MMSettings


@pytest.fixture
def MMSettings_mock():
    settings = MMSettings()
    config = "488"
    settings.channels[config] = {
        "name": config,
        "color": [255, 255, 255],
        "use": True,
        "exposure": 100,
        "z_stack": False,
    }
    config = "561"
    settings.channels[config] = {
        "name": config,
        "color": [255, 0, 0],
        "use": True,
        "exposure": 100,
        "z_stack": False,
    }
    settings.n_channels = 2
    yield settings


@pytest.fixture
def java_settings_mock():
    my_mock = mock.MagicMock()
    my_mock.interval_ms.return_value = 100
    my_mock.num_frames.return_value = 2
    my_mock.acq_order_mode.return_value = 'XYCZT'
    my_mock.use_channels.return_value = True
    my_mock.channel_group.return_value = "Channels"
    my_mock.interval_ms.return_value = 100
    my_mock.interval_ms.return_value = 100
    my_mock.use_slices.return_value = False
    slices_mock = mock.MagicMock()
    slices_mock.size.return_value = 0
    my_mock.slices.return_value = slices_mock

    channel_mock = mock.MagicMock()
    channel_mock.config.return_value = 'Channel_1'
    color_mock = mock.MagicMock()
    color_mock.get_red.return_value = 255
    color_mock.get_green.return_value = 255
    color_mock.get_blue.return_value = 255
    channel_mock.color.return_value = color_mock
    channel_mock.use_channel.return_value = True
    channel_mock.exposure.return_value = 80
    channel_mock.do_z_stack.return_value = False

    channel_mock1 = mock.MagicMock()
    channel_mock1.config.return_value = 'Channel_2'
    color_mock1 = mock.MagicMock()
    color_mock1.get_red.return_value = 255
    color_mock1.get_green.return_value = 0
    color_mock1.get_blue.return_value = 0
    channel_mock1.color.return_value = color_mock1
    channel_mock1.use_channel.return_value = True
    channel_mock1.exposure.return_value = 80
    channel_mock1.do_z_stack.return_value = False
    channels = {0: channel_mock, 1: channel_mock1}


    channels_mock = mock.MagicMock()
    channels_mock.size.return_value = 2
    def get_channel(index):
        return channels[index]
    channels_mock.get = mock.Mock(side_effect=get_channel)
    my_mock.channels.return_value = channels_mock
    yield my_mock


@pytest.fixture
def mock_datastore():
    mockup = mock.MagicMock()
    mockup.get_save_path.return_value = None
    yield mockup


@pytest.fixture
def datastore_save_path():
    mockup = mock.MagicMock()
    mockup.get_save_path.return_value = os.path.dirname(__file__) + "/../data/FOV"
    yield mockup