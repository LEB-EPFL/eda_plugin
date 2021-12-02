import threading
import time
from PyQt5.QtCore import QObject, QThread, pyqtSignal, pyqtSlot
from PyQt5 import QtWidgets
import numpy as np

from isimgui.EventThread import EventThread
from eda_gui import EDAParameterForm
# from isimgui.data_structures import PyImage


class DAQActuator(QObject):
    """ Deliver new data to the DAQ with the framerate as given by the FrameRateInterpreter."""

    new_daq_data = pyqtSignal(np.ndarray)

    def __init__(self):
        super().__init__()
        self.state = None

    @pyqtSlot(float)
    def call_action(self, interval):
        print('=== New interval: ', interval)


class MMActuator(QObject):
    """ Once an acquisition is started from the """

    new_daq_data = pyqtSignal(np.ndarray)

    def __init__(self, event_thread: EventThread):
        super().__init__()
        self.bridge = event_thread.bridge
        self.core = self.bridge.get_core()
        self.studio = self.bridge.get_studio()
        self.event_thread = event_thread
        self.interval = 1
        self.channels = 2
        # Do this so the thread does not go out of scope
        self.threads = []
        self.worker = None
        self.thread = None

    @pyqtSlot(float)
    def call_action(self, interval):
        print('=== New interval: ', interval)
        self.interval = interval
        self.worker.sleeper.set()

    def start_acq(self):
        self.worker = Acquisition2(self)
        self.thread = QThread()
        self.thread.setObjectName('Acquisition')
        self.worker.moveToThread(self.thread)
        self.worker.new_image.connect(self.new_image)
        self.worker.acquisition_ended.connect(self.reset_thread)
        self.thread.started.connect(self.worker.start_acq)
        self.thread.start()

    def reset_thread(self):
        self.thread.quit()
        time.sleep(0.5)
        self.thread = None
        self.worker = None

    def stop_acq(self):
        self.worker.stop_acq()

    def new_image(self, image):
        self.event_thread.new_image_event.emit(image)


class Acquisition2(QThread):
    new_image = pyqtSignal(object)
    acquisition_ended = pyqtSignal()

    def __init__(self, actuator: MMActuator):
        super().__init__()
        self.studio = actuator.studio
        self.core = actuator.core
        self.bridge = actuator.event_thread.bridge
        self.actuator = actuator
        settings = self.studio.acquisitions().get_acquisition_settings()
        settings = settings.copy_builder().interval_ms(100_000_000).build()
        self.datastore = self.studio.acquisitions().run_acquisition_with_settings(settings, False)
        # self.studio.acquisitions().set_pause(True)
        self.pipeline = self.studio.data().copy_application_pipeline(self.datastore, False)
        self.image = self.studio.acquisitions().snap().get(0)
        self.coords_builder = self.image.get_coords().copy_builder()
        self.stop = False
        self.sleeper = threading.Event()
        self.fast_react = True
        self.core.snap_image()
        core_image = self.core.get_tagged_image()
        metadata = core_image.tags
        print(metadata)
        print(dir(metadata))

    def stop_acq(self, stop: bool = True):
        self.stop = stop

    def start_acq(self):
        self.acquire()

    def acquire(self):
        # start_time = time.perf_counter()
        frame = 1
        acq_time = 0
        while not self.stop:
            # Handle this better with an event
            # https://stackoverflow.com/questions/5114292/break-interrupt-a-time-sleep-in-python
            if self.fast_react:
                self.sleeper.wait(max([0, self.actuator.interval - acq_time]))
                self.sleeper.clear()
            else:
                time.sleep(max([0, self.actuator.interval - acq_time]))
            acq_start = time.perf_counter()
            print('frame ', frame)
            for channel in range(self.actuator.channels):
                new_coords = self.coords_builder.time_point(frame).channel(channel).build()
                # new_meta = self.metadata_builder.elapsed_time_ms(elapsed).build()
                # self.image = self.studio.acquisitions().snap().get(0)
                self.pipeline.insert_image(self.image.copy_at_coords(new_coords))
                time.sleep(0.1)
            frame += 1
            acq_time = time.perf_counter() - acq_start
        self.studio.get_acquisition_engine().shutdown()
        self.acquisition_ended.emit()
        self.datastore.freeze()


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
