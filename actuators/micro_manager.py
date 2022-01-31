"""
Actuators that are based purely on Micro-Manager and can be used directly with the demo config.
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
    """"""

    stop_acq_signal = pyqtSignal()
    start_acq_signal = pyqtSignal(object)
    new_interval = pyqtSignal(float)

    def __init__(
        self,
        event_bus: EventBus = None,
        acquisition_mode: MMAcquisition = None,
        gui: bool = True,
    ):
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
        self.event_bus.acquisition_ended_event.connect(self.stop_acq)
        self.start_acq_signal.connect(self.event_bus.acquisition_started_event)

    @pyqtSlot(float)
    def call_action(self, interval):
        log.info(f"=== New interval: {interval} ===")
        self.new_interval.emit(interval)

    def start_acq(self):
        self.acquisition = self.acquisition_mode(self.event_bus)

        self.acquisition.acquisition_ended.connect(self.reset_thread)
        self.stop_acq_signal.connect(self.acquisition.stop_acq)
        self.new_interval.connect(self.acquisition.change_interval)

        self.acquisition.start()
        log.info("Start new acquisition")
        self.start_acq_signal.emit(None)

    def reset_thread(self):
        self.acquisition.quit()
        time.sleep(0.5)

    def stop_acq(self):
        log.info(f"Stop acquisition {self.acquisition.__class__} in MMActuator")
        if self.acquisition is not None:
            self.stop_acq_signal.emit()
            self.acquisition.exit()
            self.acquisition.deleteLater()
            self.acquisition = None


class MMAcquisition(QThread):
    acquisition_ended = pyqtSignal()

    def __init__(self, event_bus: EventBus):
        super().__init__()
        self.studio = event_bus.studio
        self.event_bus = event_bus
        self.settings = self.studio.acquisitions().get_acquisition_settings()
        # TODO: Set interval to fast interval so it can be used when running freely
        self.settings = self.settings.copy_builder().interval_ms(0).build()
        self.channels = self.get_channel_information()
        default_settings = settings.get_settings(self)
        self.channel_switch_time = default_settings["channel_switch_time_ms"]
        self.num_channels = len(self.channels)

        self.acquisitions = self.studio.acquisitions()
        self.acq_eng = self.studio.get_acquisition_engine()

        self.stop = False

    def start(self):
        super().start()
        self.start_acq()

    def start_acq(self):
        """To be implemented by the subclass"""
        pass

    def get_channel_information(self):
        channels = []
        all_channels = self.settings.channels()
        for channel_ind in range(all_channels.size()):
            channel = all_channels.get(channel_ind)
            if not channel.use_channel():
                continue
            channels.append(channel.exposure())
        return channels


class TimerMMAcquisition(MMAcquisition):

    """An Acquisition using a timer to trigger a frame acquisition should be more stable
    for consistent framerate compared to a waiting approach"""

    def __init__(self, studio, start_interval: float = 5.0):
        super().__init__(studio)
        self.timer = QTimer()
        self.timer.timeout.connect(self.acquire)
        self.start_interval = start_interval
        self.event_bus.acquisition_started_event.connect(self.pause_acquisition)

    def start_acq(self):
        self.datastore = self.acquisitions.run_acquisition_with_settings(
            self.settings, False
        )
        self.acq_eng.set_pause(True)
        self.acquisitions.set_pause(True)
        self.timer.setInterval(self.start_interval * 1_000)
        self.timer.start()

    @pyqtSlot()
    def stop_acq(self):
        self.timer.stop()
        self.acq_eng.set_pause(True)
        self.acq_eng.shutdown()
        self.acquisition_ended.emit()
        self.datastore.freeze()

    @pyqtSlot(float)
    def change_interval(self, new_interval: float):
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
        self.acq_eng.set_pause(False)
        time.sleep(
            sum(self.channels) / 1000
            + self.channel_switch_time / 1000 * (self.num_channels - 1)
        )
        self.acq_eng.set_pause(True)
        self.check_missing_channels()

    def check_missing_channels(self):
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

    def pause_acquisition(self):
        self.acq_eng.set_pause(True)


class DirectMMAcquisition(MMAcquisition):
    # TODO also stop the acquisition if the acquisition is stopped from micro-manager

    def __init__(self):
        super().__init__()
        self.fast_react = True
        self.sleeper = threading.Event()

    def change_interval(self):
        self.sleeper.set()

    def acquire(self):
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
    """
    GUI for the MMActuator providing a Start and Stop button.

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
        self.actuator.stop_acq()
        self.start_button.setDisabled(False)
        self.stop_button.setDisabled(True)
