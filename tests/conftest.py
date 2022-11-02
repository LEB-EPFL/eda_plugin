import pytest
from unittest import mock
import importlib
import os
from pymm_eventserver.data_structures import MMSettings
from eda_plugin.utility.event_bus import EventBus

from eda_plugin.actuators.micro_manager import MMActuator, TimerMMAcquisition
from eda_plugin.analysers.image import ImageAnalyser
import eda_plugin

from eda_plugin.interpreters.frame_rate import BinaryFrameRateInterpreter

from eda_plugin.utility.eda_gui import EDAMainGUI



@pytest.fixture
def MMSettings_mock(java_settings_mock):
    settings = MMSettings(java_settings_mock)
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
    mockup.get_save_path.return_value = os.path.dirname(__file__) + "/data/FOV"
    yield mockup


@pytest.fixture
def event_bus(qtbot):
    widget = EventBus(mock.MagicMock())
    yield widget


@pytest.fixture
def basic_config(event_bus, qtbot):
    eda_plugin.utility.settings.setup_logging()

    actuator = MMActuator(event_bus, TimerMMAcquisition)
    analyser = ImageAnalyser(event_bus)
    interpreter = BinaryFrameRateInterpreter(event_bus)
    writer = eda_plugin.utility.writers.Writer(event_bus)
    gui = EDAMainGUI(event_bus, viewer=False)
    gui.add_dock_widget(actuator.gui, "Actuator")
    gui.add_dock_widget(interpreter.gui, "Interpreter")
    gui.add_dock_widget(writer.gui, "Save Info")
    # gui.add_dock_widget(analyser.gui, "Analyser")
    yield gui





@pytest.fixture
def java_settings_event(mock_datastore, java_settings_mock):
    mockup = mock.MagicMock()
    mockup.get_settings.return_value = java_settings_mock
    mockup.get_datastore.return_value = mock_datastore
    yield mockup


@pytest.fixture
def java_settings_event_w_save_loc(datastore_save_path, java_settings_mock):
    mockup = mock.MagicMock()
    mockup.get_settings.return_value = java_settings_mock
    mockup.get_datastore.return_value = datastore_save_path
    yield mockup