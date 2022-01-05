import threading
import time
from PyQt5 import QtCore
from PyQt5.QtCore import QObject, QThread, QTimer, pyqtSignal, pyqtSlot
from PyQt5 import QtWidgets
import numpy as np
import winsound


from isimgui.EventThread import EventThread
from eda_gui import EDAParameterForm
import pycromanager


class DAQActuator(QObject):
    """ Deliver new data to the DAQ with the framerate as given by the FrameRateInterpreter."""

    new_daq_data = pyqtSignal(np.ndarray)
    start_acq_signal = pyqtSignal(np.ndarray)

    def __init__(self):
        super().__init__()
        self.state = None

    @pyqtSlot(float)
    def call_action(self, interval):
        print('=== New interval: ', interval)


class MMActuator(QObject):
    """ Once an acquisition is started from the """

    start_acq_signal = pyqtSignal()
    new_interval = pyqtSignal(float)
    stop_acq_signal = pyqtSignal()

    def __init__(self, event_thread: EventThread = None, acquisition_mode: str = 'timer'):
        super().__init__()
        if event_thread is None:
            self.event_thread = EventThread()
            self.event_thread.start(daemon=True)
        else:
            self.event_thread = event_thread
        self.bridge = self.event_thread.bridge
        self.core = self.bridge.get_core()
        self.studio = self.bridge.get_studio()
        self.acquisition_engine = self.studio.get_acquisition_engine()

        self.acquisition_mode = acquisition_mode


        self.interval = 5
        self.channels = 2
        # Do this so the thread does not go out of scope
        self.threads = []
        self.worker = None
        self.thread = None


    @pyqtSlot(float)
    def call_action(self, interval):
        print('=== New interval: ', interval)
        self.interval = interval
        self.new_interval.emit(interval)


    def start_acq(self):
        if self.acquisition_mode.lower() == 'timer':
            self.worker = TimerMMAcquisition(self)
        elif self.acquisition_mode.lower() == 'direct':
            self.worker = DirectMMAcquisition(self)
        else:
            raise RuntimeError('Acquisition Mode in Actuator call not known!')
        self.thread = QThread()
        self.thread.setObjectName('Acquisition')
        self.worker.moveToThread(self.thread)
        self.worker.new_image.connect(self.new_image)
        self.worker.acquisition_ended.connect(self.reset_thread)
        # self.worker.start_acq_signal.connect(self.start_acq)
        self.thread.start()
        self.start_acq_signal.emit()


    def reset_thread(self):
        self.thread.quit()
        time.sleep(0.5)
        self.thread = None
        self.worker = None

    def stop_acq(self):
        self.stop_acq_signal.emit()

    def new_image(self, image):
        self.event_thread.new_image_event.emit(image)


class MMAcquisition(QThread):
    new_image = pyqtSignal(object)
    acquisition_ended = pyqtSignal()

    def __init__(self, actuator: MMActuator):
        self.fast_react = True

        super().__init__()
        self.studio = actuator.studio
        self.core = actuator.core
        self.bridge = actuator.event_thread.bridge
        self.actuator = actuator
        self.actuator.start_acq_signal.connect(self.start_acq)
        self.actuator.stop_acq_signal.connect(self.stop_acq)
        self.actuator.new_interval.connect(self.change_interval)

        num_frames = 1000
        intervals = [10000] # + [0 for i in range(num_frames-1)]
        custom_intervals = self.bridge.construct_java_object('java.util.ArrayList')
        [custom_intervals.add(i) for i in intervals]
        settings = self.studio.acquisitions().get_acquisition_settings()
        settings_builder = settings.copy_builder().custom_intervals_ms(custom_intervals)
        settings_builder.use_custom_intervals(False).num_frames(100)
        if settings.num_frames() < 2:
            settings = settings_builder.num_frames(num_frames)
        self.settings_builder = settings_builder
        self.settings = settings_builder.build()
        self.datastore = self.studio.acquisitions().run_acquisition_with_settings(self.settings, False)
        self.acquisition_engine = self.studio.get_acquisition_engine2010()
        self.pos_list_manager = self.studio.get_position_list_manager()

        # self.acquisition_engine.set_pause(True)
        # self.studio.acquisitions().set_pause(True)
        # self.pipeline = self.studio.data().copy_application_pipeline(self.datastore, False)
        self.image = self.studio.acquisitions().snap().get(0)
        self.coords_builder = self.image.get_coords().copy_builder()
        self.acquisition_manager = self.studio.acquisitions()
        self.stop = False
        self.core.snap_image()

    def stop_acq(self, stop: bool = True):
        self.stop = stop

    @pyqtSlot()
    def start_acq(self):
        self.acquire()

    def acquire(self):
        pass

    @pyqtSlot(float)
    def change_interval(self, new_interval: float):\
        pass


class TimerMMAcquisition(MMAcquisition):
    """ An Acquisition using a timer to trigger a frame acquisition should be more stable
    for consistent framerate compared to a waiting approach"""

    def __init__(self, actuator: MMActuator):
        super().__init__(actuator)
        self.frame = None
        self.timers = []


    @pyqtSlot()
    def start_acq(self):
        print('START')
        self.timer = QTimer(self)
        self.timers.append(self.timer)
        self.timer.setTimerType(QtCore.Qt.PreciseTimer)
        self.timer.timeout.connect(self.acquire)
        self.timer.setInterval(self.actuator.interval * 1_000)
        self.frame = 0
        self.t0 = time.perf_counter()
        self.timer.start()

    @pyqtSlot()
    def stop_acq(self):
        print('STOP')
        self.timer.stop()
        self.studio.get_acquisition_engine().shutdown()
        self.acquisition_ended.emit()
        self.datastore.freeze()

    @pyqtSlot(float)
    def change_interval(self, new_interval: float):
        new_interval = new_interval*1_000
        min_interval = sum([self.settings.channels().get(i).exposure() for i in range(self.actuator.channels)])
        adjusted_interval = max([new_interval, min_interval])
        print('INTERVAL ', adjusted_interval)
        self.timer.setInterval(new_interval)
        # intervals = [new_interval for i in range(10)]

        # custom_intervals = self.bridge.construct_java_object('java.util.ArrayList')
        # [custom_intervals.add(i) for i in intervals]
        # new_settings = self.settings_builder.custom_intervals_ms(custom_intervals).build()
        # self.acquisition_engine.set_sequence_settings(new_settings)

    def acquire(self):
        # for channel in range(self.actuator.channels):
            # image = self.acquisition_manager.snap().get(0)
        settings = self.settings_builder.use_custom_intervals(False).interval_ms(1000).num_frames(1).build()
        pos_list = self.pos_list_manager.get_position_list()
        autofocus = self.studio.get_autofocus_manager().get_autofocus_method()
        # xy_stage =
        stage_position = self.bridge.construct_java_object('org.micromanager.MultiStagePosition',
                                                           args=[self.core.get_xy_stage_device(), 0, 0,
                                                                 self.core.get_focus_device(),0])
        pos_list.add_position(stage_position)
        print(pos_list.get_number_of_positions())
        self.acquisition_engine.run(settings, False, pos_list, autofocus)
        # self.acquisition_engine.settings_changed()
        # self.acquisition_engine
        # self.acquisition_engine.set_pause(False)
        winsound.Beep(500, 150)
            # new_coords = self.coords_builder.time_point(self.frame).channel(channel).build()
            # self.pipeline.insert_image(image.copy_at_coords(new_coords))
        # print('frames timer ', time.perf_counter()-self.t0)
        # self.acquisition_engine.set_pause(True)
        self.frame += 1


class DirectMMAcquisition(MMAcquisition):
    # TODO also stop the acquisition if the acquisition is stopped from micro-manager

    def __init__(self, actuator: MMActuator):
        super().__init__(actuator)
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


class PycroAcquisition(QThread):
    """ This tries to use the inbuilt Acquisition function in pycromanager. Unfortunately, these
    acquisitions don't start with the default Micro-Manager interface and the acquisition also
    doesn't seem to be saved in a perfect format, so that Micro-Manager would detect the correct
    parameters to show the channels upon loading for example. The Acquisitions also don't emit any
    of the standard Micro-Manager events. Stashed for now because of this"""
    new_image = pyqtSignal(object)
    acquisition_ended = pyqtSignal()
    def __init__(self, actuator: MMActuator):
        super().__init__()
        self.studio = actuator.studio
        self.acquisition = pycromanager.Acquisition(directory='C:/Users/stepp/Desktop/eda_save', name='acquisition_name')
        self.events = pycromanager.multi_d_acquisition_events(
                                    num_time_points=100, time_interval_s=0.5,
                                    channel_group='Channel', channels=['DAPI', 'FITC'],
                                    order='ct')
        self.sleeper = threading.Event()  # Might actually not be needed here

    def start_acq(self):
        self.acquire()

    def acquire(self):
        self.acquisition.acquire(self.events)

    def send_image(self):

        self.new_image.emit()


# class Acquisition(QObject):
#     new_image = pyqtSignal(object)

#     def __init__(self, actuator: MMActuator):
#         super().__init__()
#         self.studio = actuator.studio
#         self.core = actuator.core
#         self.actuator = actuator
#         self.datastore = self.studio.data().create_rewritable_ram_datastore()
#         self.pipeline = self.studio.data().copy_application_pipeline(self.datastore, False)
#         self.display = self.studio.get_display_manager().create_display(self.datastore)
#         self.studio.get_display_manager().manage(self.datastore)
#         self.display.add_listener(self.studio.get_display_manager(), 0)

#     def acquire(self):
#         start_time = time.perf_counter()
#         for frame in range(100):
#             print('asking MM for images')
#             for channel in range(self.actuator.channels):
#                 self.core.snap_image()
#                 frame_time = (time.perf_counter() - start_time)*1000
#                 image = self.studio.data().convert_tagged_image(self.core.get_tagged_image())
#                 coords_builder = image.get_coords().copy_builder()
#                 new_coords = coords_builder.t(frame*2+channel).build()
#                 image = image.copy_at_coords(new_coords)
#                 self.pipeline.insert_image(image)
#                 # For the simulation we have to get the image again
#                 # as it was changed in the pipeline
#                 time.sleep(0.2)
#                 new_coords = coords_builder.t(frame).c(channel).build()
#                 image = self.datastore.get_image(new_coords)
#                 py_image = PyImage(image.get_raw_pixels().reshape([image.get_width(),
#                                                                    image.get_height()]),
#                                    frame,
#                                    channel,
#                                    frame_time)
#                 self.new_image.emit(py_image)
#             time.sleep(self.actuator.interval)
#         print("Acquisition Ended")


class MMActuatorGUI(QtWidgets.QWidget):
    """Specific GUI for the MMActuator, because this needs a Start and Stop
    Button for now."""

    start_acq_signal = pyqtSignal()

    def __init__(self, actuator: MMActuator):
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

        self.param_form = EDAParameterForm()
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


# Do this instead as it gives events and all the rest
# Does still give some errors when done by hand but maybe works otherwise
# The datastore should also be available from a AcquisitionStartedEvent
# Could also be adjusted with the AcquisitionButtonHijack Plugin to adjust the delayu
# self.datastore = self.studio.acquisitions().run_acquisition_nonblocking()
# self.pipeline = self.studio.data().copy_application_pipeline(self.datastore, False)
# self.datastore.set_storage(self.bridge.construct_java_object('org.micromanager.data.internal.
# StorageRAM', args=[self.datastore]))
# self.pipeline.insert_image(image)
