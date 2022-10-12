"""An actuator that saves two settings from the MDA window to switch between"""
from unittest import mock
from eda_plugin.actuators.daq import EDAAcquisition
from eda_plugin.utility.event_bus import EventBus
from daq import DAQActuator
from qtpy import QtWidgets, QtCore
from eda_plugin.utility.qt_classes import QWidgetRestore
from pymm_eventserver.data_structures import MMSettings
from pycromanager import Studio, Core
from collections import defaultdict
import logging

log = logging.getLogger("EDA")
studio = Studio()
core = Core()


class DAQPresetsActuator(DAQActuator):
    """Actuator that saves two MM settings to toggle between for screening and imaging."""

    def __init__(self, event_bus: EventBus = EventBus):
        super().__init__(event_bus, mock.MagicMock)
        settings = studio.acquisitions().get_acquisition_settings()

        #TODO: Load this from saved settings
        self.screen_settings = MMSettings(settings)
        self.image_settings = MMSettings(settings)
        self.screen_config_settings = defaultdict(lambda: defaultdict(str))
        self.image_config_settings = defaultdict(lambda: defaultdict(str))

        studio.acquisitions().set_acquisition_settings(self.screen_settings.java_settings)
        self.active_settings = "screen"
        self._connect_events()
        self.event_bus.exposure_changed_event.connect(self.configuration_settings)

    @QtCore.Slot(object)
    def new_settings(self, new_settings:  MMSettings):
        super().new_settings(new_settings)
        if self.active_settings == "screen":
            self.screen_settings = new_settings
        elif self.active_settings == "image":
            self.image_settings = new_settings

    @QtCore.Slot(str, str, str)
    def configuration_settings(self, device, prop, value):
        super().configuration_settings(device, prop, value)
        print(device, value)
        if self.active_settings == "screen":
            self.screen_config_settings[device][prop] = value
        if self.active_settings == "image":
            self.image_config_settings[device][prop] = value

    def update_settings_in_devices(self):
        """Send the config settings to the devices.

        When the GUI is updating the settings in Micro-Manager, we are blocking events to not get
        confused about which setting they belong to. So do this 'manually'."""
        if self.active_screen == "screen":
            settings = self.screen_config_settings
        else:
            settings = self.image_config_settings
        self.aotf.power_488 = settings['488_AOTF'][ r"Power (% of max)"]
        self.aotf.power_561 = settings['561_AOTF'][ r"Power (% of max)"]


class DAQPresetsAcquisition(EDAAcquisition):
    """An acquisition that switches between two DAQ datasets generated for two different MMSettings

    Make two daq datastreams for the two settings in the actuator and switch between the two upon
    demanded by the interpreter.
    """
    def __init__(self, ni:DAQPresetsActuator, settings:MMSettings):
        super().__init__(ni, settings, None)
        self.daq_data_screen = None
        self.daq_data_image = None
        self.make_daq_data()

    @QtCore.Slot(str)
    def call_action(self, mode):
        """Interpreter has emitted a new interval to use, adapt the acquisition instance."""
        self.acq.mode = mode
        log.info(f"=== Mode switched to {mode} ===")

    def get_new_data(self, *_):
        """Pass new data to the DAQ card.

        This function was called because the DAQ card is running out of samples to write to the
        outputs. The additional parameters have information about the event that we don't use here.
        """
        log.info(self.mode)
        if self.mode == "screen":
            # timeout = max(self.interval_fast - 10, 10)
            self.ni.stream.write_many_sample(self.daq_data_screen)
        elif self.mode == "image":
            self.ni.stream.write_many_sample(self.daq_data_image)
        else:
            log.warning("Intervals have changes please restart the acquisition")
        return 0

    def make_daq_data(self):
        """Prepare the two versions of daq_data to be passed later to the DAQ stream."""
        originally_active = self.ni.active_settings
        self.ni.active_settings = "screen"
        self.ni.new_settings(self.ni.screen_settings)
        self.ni.update_settings_in_devices()
        self.daq_data_screen = self.ni._generate_one_timepoint()
        self.ni.active_settings = "image"
        self.ni.new_settings(self.ni.screen_settings)
        self.ni.update_settings_in_devices()
        self.daq_data_image = self.ni._generate_one_timepoint()
        self.active_settings = originally_active
        self.daq_data_shape = self.daq_data_image.shape


class DAQPresetsActuatorGUI(QWidgetRestore):
    """GUI with buttons to do the settings in MM"""

    def __init__(self, actuator: DAQPresetsActuator):
        """Gui widget that will be added to the bigger EDA window."""
        super().__init__()
        self.actuator = actuator

        self.screen_button = QtWidgets.QPushButton("Screen")
        self.screen_button.clicked.connect(self._activate_screen)
        self.screen_button.setEnabled(False)
        self.image_button = QtWidgets.QPushButton("Image")
        self.image_button.clicked.connect(self._activate_image)
        self.image_button.setEnabled(True)

        grid = QtWidgets.QFormLayout(self)
        grid.addRow(self.screen_button)
        grid.addRow(self.image_button)

    def _activate_screen(self):
        self.image_button.setEnabled(True)
        self.screen_button.setEnabled(False)
        self.actuator.active_settings = "screen"
        studio.acquisitions().set_acquisition_settings(self.actuator.screen_settings.java_settings)
        self._set_settings(self.actuator.screen_config_settings)

    def _activate_image(self):
        self.screen_button.setEnabled(True)
        self.image_button.setEnabled(False)
        self.actuator.active_settings = "image"
        studio.acquisitions().set_acquisition_settings(self.actuator.image_settings.java_settings)
        self._set_settings(self.actuator.image_config_settings)

    def _set_settings(self, settings: dict):
        self.actuator._disconnect_events()
        print(settings)
        for device, device_dict in settings.items():
            self._set_device_settings(device, device_dict)
        studio.app().refresh_gui()
        self.actuator.update_settings_in_devices()
        self.actuator._disconnect_events(False)

    def _set_device_settings(self, device, device_dict: dict):
        if device == "exposure":
            core.set_exposure(float(device_dict['time_ms']))
            return
        for setting, value in device_dict.items():
            core.set_property(device, setting, value)

if __name__ == "__main__":
    import sys

    app = QtWidgets.QApplication(sys.argv)
    event_bus = EventBus()

    gui = DAQPresetsActuatorGUI(DAQPresetsActuator(event_bus))

    gui.show()
    # actuator.gui.show()
    sys.exit(app.exec_())