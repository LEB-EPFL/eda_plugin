"""An actuator that saves two settings from the MDA window to switch between"""
from re import S
from unittest import mock
from eda_plugin.utility.event_bus import EventBus
from daq import DAQActuator
from qtpy import QtWidgets, QtCore
from eda_plugin.utility.qt_classes import QWidgetRestore
from pymm_eventserver.data_structures import MMSettings
from pycromanager import Studio, Core
from collections import defaultdict
studio = Studio()
core = Core()

class DAQPresetsActuator(DAQActuator):
    """Actuator that saves two MM settings to toggle between for screening and imaging."""

    def __init__(self, event_bus: EventBus = EventBus()):
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
        if self.active_settings == "screen":
            self.screen_config_settings[device][prop] = value
        if self.active_settings == "image":
            self.image_config_settings[device][prop] = value


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
        for device, device_dict in settings.items():
            self._set_device_settings(device, device_dict)
        studio.app().refresh_gui()
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