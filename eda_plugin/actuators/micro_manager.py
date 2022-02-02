"""
Actuators that are based purely on Micro-Manager and can be used directly with the demo config.

This is interesting, if you already have set up a lot of details about your acquisition and maybe
make extensive use of the on-the-fly pipeline in Micro-Manager. If this is not the case, have a look
at the actuators.pycro implementation that gives some tighter control of the acquisition.

Actuator
These actuators rely on the PythonEventServer plugin for micro-manager to receive events about user
interaction with the Java GUI or ongoing acquisition events. The server is actually not directly
link to this, but an EventBus is, that organizes and distributes event from the server itself. See
utility.event_thread and utility event_bus for more details. Here, we connect to events on the
EventBus and also emit events there for communication between the different parts of the EDA loop.

MMActuatorGUI
A GUI to start and stop the acquisition from outside Micro-Manager. The actuator can be called
without GUI and EDA will start with every acquisition as long as the plugin is running.
"""

from __future__ import annotations
import threading
import time
from PyQt5.QtCore import QObject, QThread, QTimer, pyqtSignal, pyqtSlot
from PyQt5 import QtWidgets
import qdarkstyle
from utility.event_bus import EventBus
from utility.qt_classes import QWidgetRestore
from utility import settings

import logging

log = logging.getLogger("EDA")


class MMActuator(QObject):
    """Micro-Manager based actuator.

    An actuator that uses a standard Micro-Manager acquisition to run EDA on. Micro-Manager is
    contacted via pycromanager and the actuator receives events like AcquisitionStartedEvent via the
    EventBus.
    """

    stop_acq_signal = pyqtSignal()
    start_acq_signal = pyqtSignal(object)
    new_interval = pyqtSignal(float)

    def __init__(
        self,
        event_bus: EventBus = None,
        acquisition_mode: MMAcquisition = None,
        gui: bool = True,
    ):
        """Set up the communication with the EventBus and load the MMAcquisition & GUI."""
        super().__init__()

        self.event_bus = event_bus
        self.studio = event_bus.studio
        self.interval = 5
        self.acquisition = None
        self.acquisition_mode = (
            TimerMMAcquisition if acquisition_mode is None else acquisition_mode
        )

        self.gui = MMActuatorGUI(self) if gui else None

        self.event_bus.new_interpretation.connect(self.call_action)
        self.event_bus.acquisition_ended_event.connect(self._stop_acq)
        self.start_acq_signal.connect(self.event_bus.acquisition_started_event)

    @pyqtSlot(float)
    def call_action(self, interval):
        """Information received from the interpreter, change the interval."""
        log.info(f"=== New interval: {interval} ===")
        self.new_interval.emit(interval)

    def start_acq(self):
        """Construct an MMAcquisition object, connect the relevant events to it and start."""
        self.acquisition = self.acquisition_mode(self.event_bus)

        self.acquisition.acquisition_ended.connect(self.reset_thread)
        self.stop_acq_signal.connect(self.acquisition.stop_acq)
        self.new_interval.connect(self.acquisition.change_interval)

        self.acquisition.start()
        log.info("Start new acquisition")
        self.start_acq_signal.emit(None)

    def reset_thread(self):
        """Stop and close the MMAcquisition object based on QThread."""
        self.acquisition.quit()
        time.sleep(0.5)

    def _stop_acq(self):
        log.info(f"Stop acquisition {self.acquisition.__class__} in MMActuator")
        if self.acquisition is not None:
            self.stop_acq_signal.emit()
            self.acquisition.exit()
            self.acquisition.deleteLater()
            self.acquisition = None


class MMAcquisition(QThread):
    """Thread that represents a running acquisition.

    This QThread will be started from MMActuator to start an acquisition. It sets the properties
    that are relevant for all MMAcquisition, but specific acquisition types are implemented
    separately. See TimerMMAcquisition and DirectMMAcquisition. The other responsibility of this is
    to check how many channels are active in MM, which is not directly obvious from the settings.
    The only settings that has be set by the user is the channel_switch_time, that should be the
    time in ms that MM takes to change between two channels used. This can be set in the
    settings.json.
    """

    acquisition_ended = pyqtSignal()

    def __init__(self, event_bus: EventBus):
        """Get the settings from MM and settings.json and store."""
        super().__init__()
        self.studio = event_bus.studio
        self.event_bus = event_bus
        self.settings = self.studio.acquisitions().get_acquisition_settings()
        # TODO: Set interval to fast interval so it can be used when running freely
        self.settings = self.settings.copy_builder().interval_ms(0).build()
        self.channels = self.get_channel_information()

        default_settings = settings.get_settings(__class__)
        self.channel_switch_time = default_settings["channel_switch_time_ms"]
        self.num_channels = len(self.channels)

        self.acquisitions = self.studio.acquisitions()
        self.acq_eng = self.studio.get_acquisition_engine()

        self.stop = False

    def start(self):
        """Start the QThread first, then yourself."""
        super().start()
        self.start_acq()

    def start_acq(self):
        """To be implemented by the subclass."""
        pass

    def get_channel_information(self):
        """Get channel information from the MM table and count how many channels are active."""
        channels = []
        all_channels = self.settings.channels()
        for channel_ind in range(all_channels.size()):
            channel = all_channels.get(channel_ind)
            if not channel.use_channel():
                continue
            channels.append(channel.exposure())
        return channels


class TimerMMAcquisition(MMAcquisition):
    """An acquisition using a timer in slow mode to 'open; acquisition in specific intervals.

    A mechanism is used where the acquisition in Micro-Manager is paused for the interval time and
    resarted for a short time period to allow for the acquisition of the necessary frames. The time
    that this takes is tried to be estimated and depends on the channel_switch_time from the
    MMAcquisition. As this can be wrong and not all slices/channels might have been recorded,
    check_missing_channels opens up the acquisition again to get additional frames as necessary.
    """

    def __init__(self, studio, start_interval: float = 5.0):
        """Initialise the QTimer and connect signals."""
        super().__init__(studio)
        self.timer = QTimer()
        self.timer.timeout.connect(self.acquire)
        self.start_interval = start_interval
        self.event_bus.acquisition_started_event.connect(self._pause_acquisition)

    def start_acq(self):
        """Start the acquisition with the current settings."""
        self.datastore = self.acquisitions.run_acquisition_with_settings(
            self.settings, False
        )
        self.acq_eng.set_pause(True)
        self.acquisitions.set_pause(True)
        self.timer.setInterval(self.start_interval * 1_000)
        self.timer.start()

    @pyqtSlot()
    def stop_acq(self):
        """Stop received from MM or GUI, stop."""
        self.timer.stop()
        self.acq_eng.set_pause(True)
        self.acq_eng.shutdown()
        self.acquisition_ended.emit()
        self.datastore.freeze()

    @pyqtSlot(float)
    def change_interval(self, new_interval: float):
        """Information received by MMACtuator from the interpreter, change internal interval.

        Here, the acquisition is originally set up in the fast interval, so we will stop any special
        intervention if we go into fast mode and just let the acquisition run. If we set up slow
        mode, we will set the timer to temporarily let the acquisition run on a frequency the
        represents the slow interval.
        """
        # TODO use fast_interval instead of 0
        if new_interval == 0:
            self.timer.stop()
            self.acq_eng.set_pause(False)
            return

        self.acq_eng.set_pause(True)
        self.check_missing_channels()
        self.timer.setInterval(new_interval * 1_000)
        if not self.timer.isActive():
            self.timer.start()

    def acquire(self):
        """Open acquisition for a short time in slow mode."""
        self.acq_eng.set_pause(False)
        time.sleep(
            sum(self.channels) / 1000
            + self.channel_switch_time / 1000 * (self.num_channels - 1)
        )
        self.acq_eng.set_pause(True)
        self.check_missing_channels()

    def check_missing_channels(self):
        """Get missing images.

        Check if there are all images of the last timepoint in the datastore. If not, acquisition
        was closed too early, open up the acquisiton again for a shorter time to gather the missing
        images.
        It could be helpful to increase channel_switch_time automatically if this happens often for
        acquisiton.
        """
        time.sleep(0.2)
        missing_images = self.datastore.get_num_images() % self.num_channels
        tries = 0
        while missing_images > 0 and tries < 3:
            log.debug(f"Getting additional image")
            self.acq_eng.set_pause(False)
            time.sleep(
                sum(self.channels[-missing_images:]) / 1000
                + self.channel_switch_time / 1000 * (missing_images - 0.5)
            )
            self.acq_eng.set_pause(True)
            time.sleep(0.2)
            missing_images = self.datastore.get_num_images() % self.num_channels
            tries = +tries

    def _pause_acquisition(self):
        self.acq_eng.set_pause(True)


class DirectMMAcquisition(MMAcquisition):
    """Directly take images from the microscope by using the snap() function.

    This is the most straight-forward approach to take images, but it would be necessary to handle
    channel switching etc. So pursued any further.
    """

    def __init__(self):
        """Set up the event to break the while loop."""
        super().__init__()
        self.fast_react = True
        self.sleeper = threading.Event()

    def change_interval(self):
        """If in fast_react mode, interrupt the wait of the while loop for the next frame."""
        self.sleeper.set()

    def acquire(self):
        """Full acquisition loop.

        It could be interesting to also implement this with a QTimer to have a more consistent frame
        rate. Problem is, that with inserting images into the pipeline it works well with the image
        injector (MMplugin), but an actual image would have to be taken e.g. with snap() for a real
        acquisition and this does not handle changing channels etc. So using an already set up
        acquisition as in TimerMMAcquisition or even a Pycromanager Acquisition seems like the
        better way in the moment.
        """
        frame = 1
        acq_time = 0
        while not self.stop:

            if self.fast_react:
                self.sleeper.wait(max([0, self.actuator.interval - acq_time]))
                self.sleeper.clear()
            else:
                time.sleep(max([0, self.actuator.interval - acq_time]))
            acq_start = time.perf_counter()
            for channel in range(self.actuator.channels):
                new_coords = (
                    self.coords_builder.time_point(frame).channel(channel).build()
                )
                self.pipeline.insert_image(self.image.copy_at_coords(new_coords))
                time.sleep(self.settings.channels().get(0).exposure() / 1000)
            frame += 1
            acq_time = time.perf_counter() - acq_start
        self.studio.get_acquisition_engine().shutdown()
        self.acquisition_ended.emit()
        self.datastore.freeze()


class MMActuatorGUI(QWidgetRestore):
    """GUI for the MMActuator providing a Start and Stop button.

    The actuator could also be implemented to start/stop with an acquisition in MicroManager using
    the AcquisitionStarted/Ended events.
    """

    def __init__(self, actuator: MMActuator):
        """Pyqt GUI as a widget that could also be added to a bigger MainWindow."""
        super().__init__()
        self.actuator = actuator
        self.start_button = QtWidgets.QPushButton("Start")
        self.start_button.clicked.connect(self._start_acq)
        self.stop_button = QtWidgets.QPushButton("Stop")
        self.stop_button.clicked.connect(self._stop_acq)
        self.stop_button.setDisabled(True)

        grid = QtWidgets.QVBoxLayout(self)
        grid.addWidget(self.start_button)
        grid.addWidget(self.stop_button)
        self.setStyleSheet(qdarkstyle.load_stylesheet(qt_api="pyqt5"))
        self.setWindowTitle("EDA Actuator Plugin")

        self.actuator.event_bus.acquisition_ended_event.connect(self._stop_acq)

    def _start_acq(self):
        self.start_button.setDisabled(True)
        self.stop_button.setDisabled(False)
        self.actuator.start_acq()

    def _stop_acq(self):
        self.actuator._stop_acq()
        self.start_button.setDisabled(False)
        self.stop_button.setDisabled(True)