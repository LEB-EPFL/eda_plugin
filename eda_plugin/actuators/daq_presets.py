"""An actuator that saves two settings from the MDA window to switch between"""
from unittest import mock
from eda_plugin.actuators.daq import EDAAcquisition
from eda_plugin.utility.event_bus import EventBus
from eda_plugin.actuators.daq import DAQActuator
from qtpy import QtWidgets, QtCore
from eda_plugin.utility.qt_classes import QWidgetRestore
from pymm_eventserver.data_structures import MMSettings
from pycromanager import Studio, Core
from collections import defaultdict
import logging
import time
import nidaqmx
import numpy as np

log = logging.getLogger("EDA")
studio = Studio()
core = Core()


class DAQPresetsActuator(DAQActuator):
    """Actuator that saves two MM settings to toggle between for screening and imaging."""

    def __init__(self, event_bus: EventBus = EventBus):
        super().__init__(event_bus)
        settings = studio.acquisitions().get_acquisition_settings()

        #TODO: Load this from saved settings
        self.screen_settings = MMSettings(settings, post_delay = 0)
        self.image_settings = MMSettings(settings, post_delay = 0)
        self.screen_config_settings = defaultdict(lambda: defaultdict(str))
        self.image_config_settings = defaultdict(lambda: defaultdict(str))
        self.initialize_laser_settings()

        self.gui = DAQPresetsActuatorGUI(self)

        studio.acquisitions().set_acquisition_settings(self.screen_settings.java_settings)
        self.active_settings = "screen"
        self._connect_events()
        self.event_bus.exposure_changed_event.connect(self.configuration_settings)

        self.acq = DAQPresetsAcquisition(self, settings)

    @QtCore.Slot(object)
    def new_settings(self, new_settings:  MMSettings):
        print("New settings before!")
        try:
            super().new_settings(new_settings)
        except AttributeError:
            # There is no daq_data_fast for updating the settings
            pass
        self.acq.update_settings(new_settings, write=False)
        print("New Settings!")
        if self.active_settings == "screen":
            self.screen_settings = new_settings
        elif self.active_settings == "image":
            self.image_settings = new_settings
        # self.acq.make_daq_data()


    @QtCore.Slot(str, str, str)
    def configuration_settings(self, device, prop, value):
        super().configuration_settings(device, prop, value)
        print(device, value)
        if device in ["EDA"]:
            return
        if self.active_settings == "screen":
            self.screen_config_settings[device][prop] = float(value)
        if self.active_settings == "image":
            self.image_config_settings[device][prop] = float(value)
        # self.acq.make_daq_data()

    def initialize_laser_settings(self):
        self.screen_config_settings['488_AOTF'][ r"Power (% of max)"] = 20.0
        self.screen_config_settings['561_AOTF'][ r"Power (% of max)"] = 0
        self.image_config_settings['488_AOTF'][ r"Power (% of max)"] = 20.0
        self.image_config_settings['561_AOTF'][ r"Power (% of max)"] = 50.0

    def update_settings_in_devices(self):
        """Send the config settings to the devices.

        When the GUI is updating the settings in Micro-Manager, we are blocking events to not get
        confused about which setting they belong to. So do this 'manually'."""
        if self.active_settings == "screen":
            settings = self.screen_config_settings
        else:
            settings = self.image_config_settings
        new_488_power = settings['488_AOTF'][r"Power (% of max)"]
        print(f"RESETING 488 POWER to {new_488_power}")
        print(settings)
        self.aotf.power_488 = float(settings['488_AOTF'][ r"Power (% of max)"])
        self.aotf.power_561 = float(settings['561_AOTF'][ r"Power (% of max)"])

    def _connect_events(self):
        self.event_bus.configuration_settings_event.connect(self.configuration_settings)
        self.event_bus.acquisition_started_event.connect(self.run_acquisition_task)
        self.event_bus.acquisition_ended_event.connect(self.acq_done)
        self.event_bus.new_interpretation.connect(self.call_action)
        self.event_bus.mda_settings_event.connect(self.new_settings)

    @QtCore.Slot(object)
    def run_acquisition_task(self, _):
        """Run the acquisition by forwarding the pyqtSignal to the Acquisition instance."""
        if not self.acq.running:
            self.event_bus.mda_settings_event.disconnect(self.new_settings)
            print("====================================== ACQ started Evt")
            self.acq.make_daq_data()
            self.stream.write_many_sample(self.acq.daq_data_screen)
            time.sleep(2)
            self.acq.running = True
            self.task.start()

    @QtCore.Slot(object)
    def acq_done(self, _):
        """Acquisition was stopped, clean up."""
        # self.acq.set_z_position.emit(self.acq.orig_z_position)
        self.event_bus.mda_settings_event.connect(self.new_settings)
        # time.sleep(1)
        self.task.stop()
        self.acq.running = False

    @QtCore.Slot(float)
    def call_action(self, new_interval):
        """Interpreter has emitted a new interval to use, adapt the acquisition instance."""
        print(f"=== CALLING ACTION === mode {new_interval}")
        if new_interval == 0:
            self.acq.mode = 'screen'
            self.daq_data_shape = self.acq.daq_data_screen.shape
        elif new_interval == 1:
            self.acq.mode = "image"
            self.daq_data_shape = self.acq.daq_data_image.shape

            # if self.acq.running:
            #     t0 = time.perf_counter()
            #     self.task.stop()
            #     self.task.close()
            #     print(f"TIME TO CLOSE TASK {time.perf_counter() - t0}")
            #     self.acq.update_settings(None, False)
            #     self.acq.get_new_data()
            #     self.task.start()
            #     print(f"TIME TO SWITCH TASKS {time.perf_counter() - t0}")
            self.acq.get_new_data()
        else:
            log.warning(f"interval {new_interval} does not match Actuator!")
        log.info(f"=== New interval: {new_interval} ===")


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
        self.mode = "screen"
        self.screen_delays = 0
        self.running = False

    # @QtCore.Slot(str)
    # def call_action(self, mode):
    #     """Interpreter has emitted a new interval to use, adapt the acquisition instance."""
    #     self.mode = mode
    #     print("CALL ACTION WITH MODE", mode)
    #     if self.mode == "screen":
    #         self.ni.task.register_every_n_samples_transferred_from_buffer_event(
    #         self.daq_data_screen.shape[1], self.get_new_data
    #         )
    #     else:
    #         self.ni.task.register_every_n_samples_transferred_from_buffer_event(
    #         self.daq_data_image.shape[1], self.get_new_data
    #         )
    #     log.info(f"=== Mode switched to {mode} ===")

    def get_new_data(self, *_):
        """Pass new data to the DAQ card.

        This function was called because the DAQ card is running out of samples to write to the
        outputs. The additional parameters have information about the event that we don't use here.
        """
        log.info(f"Sending new data for mode {self.mode}")
        if self.mode == "screen":
            if 0 < self.screen_delays <= self.n_delays_screen:
                print("SENDING WAIT DATA")
                self.ni.stream.write_many_sample(self.delay_data_screen)
                self.screen_delays += 1
            else:
                print("SENDING SCREEN DATA")
                self.ni.stream.write_many_sample(self.daq_data_screen)
                self.screen_delays = 1
        elif self.mode == "image":
            print("SENDING IMAGING DATA")
            self.ni.stream.write_many_sample(self.daq_data_image)
            self.screen_delays = 0
        else:
            log.warning("Intervals have changes please restart the acquisition")
        return 0

    def make_daq_data(self):
        """Prepare the two versions of daq_data to be passed later to the DAQ stream."""
        self.ni._disconnect_events()
        originally_active = self.ni.active_settings

        self.ni.active_settings = "image"
        self.ni.new_settings(self.ni.image_settings)
        self.ni.update_settings_in_devices()
        timepoint = self.ni._generate_one_timepoint()
        print(f"IMAGE SETTINGS INTERVAL {self.ni.image_settings.interval_ms}")
        self.daq_data_image = self.add_interval(timepoint, self.ni.image_settings.interval_ms)

        self.ni.active_settings = "screen"
        self.ni.new_settings(self.ni.screen_settings)
        self.ni.update_settings_in_devices()
        timepoint = self.ni._generate_one_timepoint()
        full_length_screen = self.add_interval(timepoint, self.ni.screen_settings.interval_ms)
        full_length_screen = full_length_screen.shape[1]
        # Extend to the length of the imaging frame
        extension = np.tile(timepoint[:, -1][..., None],
                            self.daq_data_image.shape[1] - timepoint.shape[1])
        self.daq_data_screen = np.hstack([timepoint, extension])
        self.delay_data_screen = np.tile(self.daq_data_screen[:, -1][..., None],
                                         self.daq_data_screen.shape[1])
        self.n_delays_screen = int(round(full_length_screen/self.daq_data_image.shape[1] - 1))

        self.active_settings = originally_active
        self.daq_data_shape = self.daq_data_image.shape
        self.ni._disconnect_events(False)


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