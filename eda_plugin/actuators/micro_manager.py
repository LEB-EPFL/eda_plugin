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
import numpy as np
from PyQt5.QtCore import QObject, QThread, QTimer, pyqtSignal, pyqtSlot
from PyQt5 import QtWidgets
import qdarkstyle
from eda_plugin.utility.event_bus import EventBus
from eda_plugin.utility.qt_classes import QWidgetRestore
from eda_plugin.utility import settings


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

        try:
            self.acquisition_mode.calibrate
            self.calibration = True
        except:
            self.calibration = False

        self.gui = MMActuatorGUI(self, self.calibration) if gui else None

        self.calibrated_wait_time = None

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
        if self.studio.acquisitions().is_acquisition_running():
            warning_text = "Acquisition is already running, please stop first."
            log.warning(warning_text)
            msg = QtWidgets.QMessageBox()
            msg.setIcon(2)
            msg.setText(warning_text)
            msg.exec()
            return False
        if self.calibration:
            self.acquisition = self.acquisition_mode(
                self.event_bus, calibrated_wait_time=self.calibrated_wait_time
            )
        else:
            self.acquisition = self.acquisition_mode(self.event_bus)
        self.acquisition.acquisition_ended.connect(self.reset_thread)
        self.stop_acq_signal.connect(self.acquisition.stop_acq)
        self.new_interval.connect(self.acquisition.change_interval)

        self.acquisition.start()
        log.info("Start new acquisition")
        self.start_acq_signal.emit(None)
        return True

    def reset_thread(self):
        """Stop and close the MMAcquisition object based on QThread."""
        self.acquisition.quit()
        time.sleep(0.5)

    def _stop_acq(self):
        if self.acquisition is not None:
            log.info(f"Stop acquisition {self.acquisition.__class__} in MMActuator")
            self.stop_acq_signal.emit()
            try:
                self.calibrated_wait_time = self.acquisition.calibrated_wait_time
                self.gui.calib_edit.setText(str(int(self.calibrated_wait_time)))
            except (AttributeError, TypeError):
                log.debug(
                    f"{self.acquisition_mode} does not have a calibration feature"
                )
            self.acquisition.exit()
            self.acquisition.deleteLater()
            self.acquisition = None

    def _calibrate(self):
        self.acquisition = self.acquisition_mode(self.event_bus)
        self.calibrated_wait_time = self.acquisition.calibrate()
        self.gui.calib_edit.setText(str(int(self.calibrated_wait_time)))


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
        self.channels = self.get_channel_information()
        # This has to be higher for 1 channel, otherwise it will be a burst acq that can't be paused

        default_settings = settings.get_settings(__class__)
        self.channel_switch_time = default_settings["channel_switch_time_ms"]
        self.num_channels = len(self.channels)
        self.slices = self.settings.slices().size()
        self.slices = 1 if self.slices == 0 else self.slices
        log.info(f"Settings: {self.slices} slices & {self.num_channels} channels")

        num_frames = self.num_channels * self.slices
        interval = 0 if num_frames > 1 else self.channels[0] + 1
        log.info(f"Interval {interval}")
        self.settings = self.settings.copy_builder().interval_ms(interval).build()

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
    that this takes should be calibrated by calling calibrate. If this is not called, the time to
    wait is estimated and depends on the channel_switch_time defined in the
    MMAcquisition. As this can be wrong and not all slices/channels might have been recorded,
    check_missing_channels opens up the acquisition again to get additional frames as necessary. It
    also increases the wait_time for the next time, if it was calibrated. This will fine-adjust the
    wait time and make the acquisition more consistent. The updated wait_time is also saved into
    MMActuator for the next acquisition.
    """

    def __init__(
        self, studio, start_interval: float = 5.0, calibrated_wait_time: float = None
    ):
        """Initialise the QTimer and connect signals."""
        super().__init__(studio)
        self.timer = QTimer()
        self.timer.timeout.connect(self.acquire)
        self.start_interval = start_interval
        self.event_bus.acquisition_started_event.connect(self._pause_acquisition)
        self.calibrated_wait_time = calibrated_wait_time
        self.acquire_num = 0
        self.last_adjust = 0

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

        # TODO: Add support for z slices
        # TODO: think about a calibration scheme for the waiting time.
        self.acq_eng.set_pause(True)
        self.acquisitions.set_pause(True)
        self.check_missing_channels(adjust=False)
        self.timer.setInterval(new_interval * 1_000)
        if not self.timer.isActive():
            self.timer.start()
        log.debug("New interval set in actuator")

    def acquire(self):
        """Open acquisition for a short time in slow mode."""
        log.debug(f"acquire {self.calibrated_wait_time}")
        self.acquire_num += 1
        if self.calibrated_wait_time is None:
            wait_time = sum(self.channels) / 1000 + self.channel_switch_time / 1000 * (
                self.num_channels - 1
            )
            wait_time = wait_time if wait_time > 0.015 else wait_time + 0.01
        else:
            wait_time = self.calibrated_wait_time / 1000

        self.acquisitions.set_pause(False)

        time.sleep(wait_time)

        self.acquisitions.set_pause(True)
        if self.num_channels > 1 or self.slices > 1:
            self.check_missing_channels(adjust=True)

    def check_missing_channels(self, adjust: bool = False):
        """Get missing images.

        Check if there are all images of the last timepoint in the datastore. If not, acquisition
        was closed too early, open up the acquisiton again for a shorter time to gather the missing
        images.
        It could be helpful to increase channel_switch_time automatically if this happens often for
        acquisiton.
        """
        # TODO: Increase the channel_wait_time if a channel is missing.
        time.sleep(0.2)
        num_frames = self.num_channels * self.slices
        missing_images = num_frames - (self.datastore.get_num_images() % num_frames)
        missing_images = 0 if missing_images == num_frames else missing_images
        tries = 0
        while missing_images > 0 and tries < 3:
            log.debug(
                f"Getting additional images: {missing_images}, {self.channels[-missing_images:]}"
            )
            if self.calibrated_wait_time is None:
                wait_time = sum(
                    self.channels[-missing_images:]
                ) / 1000 + self.channel_switch_time / 1000 * (missing_images - 0.5)
            elif missing_images > 1:
                wait_time = (
                    self.calibrated_wait_time * (missing_images / num_frames) / 1000
                )
                if adjust and tries == 0 and self.acquire_num > 1:
                    self.calibrated_wait_time += (
                        self.calibrated_wait_time / num_frames / 5
                    )
            else:
                if self.slices == 1:
                    wait_time = 0.02
                else:
                    wait_time = 0.05

                if adjust and tries == 0 and self.acquire_num >= self.last_adjust + 10:
                    self.last_adjust = self.acquire_num
                elif adjust and tries == 0 and self.acquire_num > 1:
                    self.calibrated_wait_time += self.channels[-1] / 10
                    self.last_adjust = self.acquire_num

            self.acq_eng.set_pause(False)
            time.sleep(wait_time)
            self.acq_eng.set_pause(True)
            time.sleep(0.2)
            missing_images = num_frames - (self.datastore.get_num_images() % num_frames)
            missing_images = 0 if missing_images == num_frames else missing_images
            log.debug(f"Images still missing {missing_images}")
            tries = tries + 1

    def _pause_acquisition(self):
        self.acq_eng.set_pause(True)

    def calibrate(self):
        """Take a short sequence and measure the time to open acquisition for each frame."""
        log.info("Starting calibration")
        num_timepoints = 5
        old_settings = self.studio.acquisitions().get_acquisition_settings()
        self.settings = (
            old_settings.copy_builder()
            .interval_ms(3000)
            .num_frames(num_timepoints)
            .build()
        )
        self.datastore = self.acquisitions.run_acquisition_with_settings(
            self.settings, True
        )
        log.debug("calibration sequence recorded")
        coord_builder = self.datastore.get_any_image().get_coords().copy_builder()
        time_per_timepoint = []
        for i in range(1, num_timepoints):
            coords0 = coord_builder.c(0).z(0).t(i).build()
            image0 = self.datastore.get_image(coords0)
            coords = (
                coord_builder.c(self.num_channels - 1).z(self.slices - 1).t(i).build()
            )
            image1 = self.datastore.get_image(coords)
            time0 = image0.get_metadata().get_elapsed_time_ms()
            time1 = image1.get_metadata().get_elapsed_time_ms()
            time_per_timepoint.append(time1 - time0)
            log.debug(f"timepoint time: {time1 - time0}")
        self.calibrated_wait_time = np.mean(time_per_timepoint)
        log.info(f"Calibrated wait time: {self.calibrated_wait_time}")
        self.studio.acquisitions().set_acquisition_settings(old_settings)
        return self.calibrated_wait_time


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

    def __init__(self, actuator: MMActuator, calibrate: bool = False):
        """Pyqt GUI as a widget that could also be added to a bigger MainWindow."""
        super().__init__()
        self.actuator = actuator
        self.start_button = QtWidgets.QPushButton("Start")
        self.start_button.clicked.connect(self._start_acq)
        self.stop_button = QtWidgets.QPushButton("Stop")
        self.stop_button.clicked.connect(self._stop_acq)
        self.stop_button.setDisabled(True)

        if calibrate:
            self.calib_button = QtWidgets.QPushButton("Calibrate")
            self.calib_button.clicked.connect(self._calib)
            self.calib_edit = QtWidgets.QTextEdit("0")
            self.calib_check = QtWidgets.QCheckBox()
            self.calib_check.setChecked(True)

        grid = QtWidgets.QFormLayout(self)
        grid.addRow(self.start_button)
        grid.addRow(self.stop_button)

        if calibrate:
            grid.addRow(self.calib_button)
            grid.addRow("Calibration [ms]", self.calib_edit)
            grid.addRow("Auto-adjust", self.calib_check)

        self.setStyleSheet(qdarkstyle.load_stylesheet(qt_api="pyqt5"))
        self.setWindowTitle("EDA Actuator Plugin")

        self.actuator.event_bus.acquisition_ended_event.connect(self._stop_acq)

    def _start_acq(self):
        self.start_button.setDisabled(True)
        success = self.actuator.start_acq()
        if success:
            self.stop_button.setDisabled(False)
        else:
            self.start_button.setDisabled(False)

    def _stop_acq(self):
        self.actuator._stop_acq()
        self.start_button.setDisabled(False)
        self.stop_button.setDisabled(True)

    def _calib(self):
        self.actuator._calibrate()
