import threading
import time
from PyQt5.QtCore import QObject, QThread, QTimer, pyqtSignal, pyqtSlot
from PyQt5 import QtWidgets, QtGui
from eda_plugin.protocols import ParameterForm
from event_bus import EventBus


class MMAcquisition(QThread):
    acquisition_ended = pyqtSignal()

    def __init__(self, studio):
        super().__init__()
        self.studio = studio
        self.settings = self.studio.acquisitions().get_acquisition_settings()
        #TODO: Set interval to fast interval so it can be used when running freely
        self.settings = self.settings.copy_builder().interval_ms(0).build()
        self.channels = self.get_channel_information()
        self.channel_switch_time = 133  # ms
        self.num_channels = len(self.channels)

        self.acquisitions = self.studio.acquisitions()
        self.acq_eng = self.studio.get_acquisition_engine()
        self.datastore = self.acquisitions.run_acquisition_with_settings(self.settings, False)
        self.acquisitions.set_pause(True)

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
    """ An Acquisition using a timer to trigger a frame acquisition should be more stable
    for consistent framerate compared to a waiting approach"""

    def __init__(self, studio, start_interval: float = 5.):
        super().__init__(studio)
        self.timer = QTimer()
        self.timer.timeout.connect(self.acquire)
        self.start_interval = start_interval

    def start_acq(self):
        self.timer.setInterval(self.start_interval * 1_000)
        self.timer.start()
        print('START')

    @pyqtSlot()
    def stop_acq(self):
        print('STOP')
        self.timer.stop()
        self.acq_eng.shutdown()
        self.acquisition_ended.emit()
        self.datastore.freeze()

    @pyqtSlot(float)
    def change_interval(self, new_interval: float):
        #TODO use fast_interval instead of 0
        if new_interval == 0:
            self.timer.stop()
            self.acq_eng.set_pause(False)
            return

        self.acq_eng.set_pause(True)
        self.check_missing_channels()
        self.timer.setInterval(new_interval*1_000)
        if not self.timer.isActive():
            self.timer.start()

    def acquire(self):
        print("              ACQUIRE ", time.perf_counter())
        self.acq_eng.set_pause(False)
        time.sleep(sum(self.channels)/1000 + self.channel_switch_time/1000 * (self.num_channels - 1))
        self.acq_eng.set_pause(True)
        self.check_missing_channels()

    def check_missing_channels(self):
        time.sleep(0.2)
        missing_images = self.datastore.get_num_images() % self.num_channels
        tries = 0
        while missing_images > 0 and tries < 3:
            print('Trying to get 1 additional image')
            self.acq_eng.set_pause(False)
            time.sleep(sum(self.channels[-missing_images:])/1000 + self.channel_switch_time/1000 * (missing_images - 0.5))
            self.acq_eng.set_pause(True)
            time.sleep(0.2)
            missing_images = self.datastore.get_num_images() % self.num_channels
            tries =+ tries


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
            print('frame ', frame)
            for channel in range(self.actuator.channels):
                new_coords = self.coords_builder.time_point(frame).channel(channel).build()
                self.pipeline.insert_image(self.image.copy_at_coords(new_coords))
                time.sleep(self.settings.channels().get(0).exposure()/1000)
            frame += 1
            acq_time = time.perf_counter() - acq_start
        self.studio.get_acquisition_engine().shutdown()
        self.acquisition_ended.emit()
        self.datastore.freeze()


class MMActuator(QObject):
    """ Once an acquisition is started from the """
    stop_acq_signal = pyqtSignal()
    new_interval = pyqtSignal(float)

    def __init__(self,
                 event_bus: EventBus = None,
                 acquisition_mode: MMAcquisition = TimerMMAcquisition):
        super().__init__()

        self.studio = event_bus.studio
        self.acquisition_mode = acquisition_mode
        self.interval = 5
        self.acquisition = None

        # Connect incoming events
        event_bus.new_interpretation.connect(self.call_action)


    @pyqtSlot(float)
    def call_action(self, interval):
        print('=== New interval: ', interval)
        self.new_interval.emit(interval)

    def start_acq(self):
        self.acquisition = self.acquisition_mode(self.studio)

        self.acquisition.acquisition_ended.connect(self.reset_thread)
        self.stop_acq_signal.connect(self.acquisition.stop_acq)
        self.new_interval.connect(self.acquisition.change_interval)

        self.acquisition.start()

    def reset_thread(self):
        self.acquisition.quit()
        time.sleep(0.5)

    def stop_acq(self):
        self.stop_acq_signal.emit()
        self.acquisition.exit()
        self.acquisition.deleteLater()
        self.acquisition = None


class MMActuatorGUI(QtWidgets.QWidget):
    """Specific GUI for the MMActuator, because this needs a Start and Stop
    Button for now."""

    start_acq_signal = pyqtSignal()

    def __init__(self, actuator: MMActuator, parameter_form: ParameterForm):
        super().__init__()
        self.actuator = actuator
        self.start_button = QtWidgets.QPushButton('Start')
        self.start_button.clicked.connect(self.start_acq)
        self.stop_button = QtWidgets.QPushButton('Stop')
        self.stop_button.clicked.connect(self.stop_acq)
        self.stop_button.setDisabled(True)

        grid = QtWidgets.QGridLayout(self)
        grid.addWidget(self.start_button, 0, 1)
        grid.addWidget(self.stop_button, 1, 1)

        self.param_form = parameter_form
        grid.addWidget(self.param_form, 0, 0, 2, 1)

        self.setWindowTitle('EDA Actuator Plugin')

    def start_acq(self):
        self.actuator.start_acq()
        self.start_button.setDisabled(True)
        self.stop_button.setDisabled(False)

    def stop_acq(self):
        self.actuator.stop_acq()
        self.start_button.setDisabled(False)
        self.stop_button.setDisabled(True)

    def closeEvent(self, event):
        app = QtGui.QApplication.instance()
        app.closeAllWindows()
        event.accept()