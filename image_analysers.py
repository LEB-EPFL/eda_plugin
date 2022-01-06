
from PyQt5 import QtWidgets
from PyQt5 import QtCore
from PyQt5.QtCore import QEventLoop, QObject, QRunnable, QThread, QThreadPool, pyqtSignal, pyqtSlot
import threading
from typing import Protocol
import numpy as np
import sys
from isimgui.data_structures import PyImage
from eda_original.SmartMicro.NNfeeder import prepareNNImages
from eda_original.SmartMicro.ImageTiles import stitchImage
from isimgui.EventThread import EventThread
from tensorflow import keras
from numbers import Number
import time

from protocols import Actuator


class KerasAnalyser(QObject):
    """ Analyze the last image using the neural network and image the output
    This has to implement the ImageAnalyser Protocol to be able to be used in the
    EDAMainGUI."""

    new_output_shape = pyqtSignal(tuple)
    new_network_image = pyqtSignal(np.ndarray)
    new_decision_parameter = pyqtSignal(float, int)

    def __init__(self, actuator: Actuator = None):
        super().__init__()
        self.name = "KerasAnalyser"
        self.shape = None
        self.time = None
        self.images = None
        self.start_time = None
        self.actuator = actuator

        self.threadpool = QThreadPool(parent=self)
        self.threadpool.setMaxThreadCount(5)
        # Load and initialize model so first predict is fast(er)
        self.model_path = "//lebnas1.epfl.ch/microsc125/Watchdog/Model/model_Dora.h5"
        self.model = keras.models.load_model(self.model_path, compile=True)
        self.channels = self.model.layers[0].input_shape[0][3]

        if actuator is None:
            self.event_thread = EventThread()
            self.event_thread.start(daemon=True)
        else:
            self.event_thread = actuator.event_thread

        self.init_model()
        self.event_thread.new_image_event.connect(self.start_analysis)
        self.event_thread.acquisition_started_event.connect(self.start)
        self.event_thread.acquisition_ended_event.connect(self.stop)
        print('Image Analyser Running')
        self.frame_counter = None
        self.frame_counter_active = False


    @pyqtSlot(object)
    def start_analysis(self, evt: PyImage):
        # Skip the timepoint if a newer timepoint is already there. Analysis is lagging behind.
        if evt.timepoint < self.frame_counter.frame_counter.frame_counter:
            print('SKIPPED ', evt.timepoint)
            return
        ready = self.gather_images(evt, )
        if not ready:
            return
        print('All channels acquired ', int(evt.timepoint))
        local_images = self.images.copy()
        worker = ImageAnalyser(self.model, local_images, evt.timepoint, self.start_time)
        # # Connect the signals to push through
        worker.signals.new_decision_parameter.connect(self.new_decision_parameter)
        worker.signals.new_network_image.connect(self.new_network_image)
        worker.signals.new_output_shape.connect(self.new_output_shape)
        self.threadpool.tryStart(worker)

    def gather_images(self, py_image: PyImage) -> bool:
        """ If there is more than one channel gather all the channels for one timepoint and return
        if all channels are there or not. """

        time, channel = py_image.timepoint, py_image.channel
        # If this is the first image of an acquisition reset the shape of the images.
        if time == 0 and channel == 0:
            self.reset_shape(py_image)
            self.reset_time()

        self.images[channel] = py_image.raw_image
        self.time = time
        if channel < self.channels - 1:
            return False
        else:
            return True

    def reset_shape(self, image: PyImage):
        self.shape = image.raw_image.shape
        self.images = np.ndarray([self.channels, *self.shape])
        print("=== RESETTING SHAPE ===")
        print(self.shape)

    def reset_time(self):
        self.start_time = round(time.time() * 1000)

    def init_model(self):
        print('Initialize the model')
        if self.model.layers[0].input_shape[0][1] is None:
            size = 512
        else:
            size = self.model.layers[0].input_shape[0][1]
        self.model(np.random.randint(
            10, size=[1, size, size, self.channels]))

    def start(self):
        if not self.frame_counter_active:
            self.frame_counter = FrameCounterThread(self, self.event_thread)
            self.frame_counter.setObjectName('FrameCounterThread')
            self.frame_counter.start()
            self.frame_counter_active = True

    def stop(self):
        self.frame_counter.frame_counter.loop.exit()
        self.frame_counter.exit()
        self.frame_counter_active = False


class FrameCounterThread(QThread):
    def __init__(self, parent, event_thread):
        super().__init__(parent=parent)
        self.frame_counter = self.FrameCounter(event_thread)
        # After the following call the slots will be executed in the thread
        self.frame_counter.moveToThread(self)


    class FrameCounter(QObject):
        def __init__(self, event_thread:EventThread):
            super().__init__()
            self.loop = QEventLoop(self)
            self.event_thread = event_thread
            self.event_thread.new_image_event.connect(self.increase_frame_counter)
            self.frame_counter = 0

        @pyqtSlot(PyImage)
        def increase_frame_counter(self, evt):
            self.frame_counter = evt.timepoint

        def start(self):
            self.loop.exec()


class ImageAnalyser(QRunnable):

    def __init__(self, model, local_images: np.ndarray, timepoint: int, start_time: float):
        super(ImageAnalyser, self).__init__()
        self.signals = Signals()
        self.model = model
        self.local_images = local_images
        self.timepoint = timepoint
        self.start_time = start_time
        self.autoDelete = True

    @pyqtSlot(int, np.ndarray)
    def run(self):
        network_input, positions = self.prepare_images(self.local_images)
        network_output = self.model.predict_on_batch(network_input)

        # The simple maximum decision parameter can be calculated without stiching
        decision_parameter = self.extract_decision_parameter(network_output)
        # This should be evt.time once we can set the metadata on the image
        elapsed_time = round(time.time() * 1000) - self.start_time
        self.signals.new_decision_parameter.emit(decision_parameter, elapsed_time)

        # Also construct the image so it can be displayed
        network_output = self.post_process_output(network_output, positions)
        if self.timepoint ==  0:
            self.signals.new_output_shape.emit(network_output.shape)
        self.signals.new_network_image.emit(network_output)

    def extract_decision_parameter(self, network_output: np.ndarray) -> Number:
        return float(np.max(network_output))

    def post_process_output(self, data: np.ndarray, positions) -> np.ndarray:
        if self.model.layers[0].input_shape[0][1] is None:
            return data[0, :, :, 0]
        else:
            return stitchImage(data, positions)

    def prepare_images(self, images):
        return prepareNNImages(images[0], images[1], self.model)

class Signals(QObject):
    new_output_shape = pyqtSignal(tuple)
    new_network_image = pyqtSignal(np.ndarray)
    new_decision_parameter = pyqtSignal(float, int)


def main():
    import isimgui.MicroManagerControl as MicroManagerControl
    from isimgui.GUIWidgets import LiveView
    mm_interface = MicroManagerControl.MicroManagerControl()
    app = QtWidgets.QApplication(sys.argv)
    analyzer = KerasAnalyser()
    live_view = LiveView()

    def print_parameter(param, time):
        print(f'param {param} at time {time}')

    def show_image(image: np.ndarray):
        q_image = mm_interface.convert_image(image, normalize=True)
        live_view.set_qimage(q_image)

    analyzer.new_network_image.connect(show_image)
    analyzer.new_decision_parameter.connect(print_parameter)
    analyzer.new_output_shape.connect(live_view.reset_scene_rect)
    live_view.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
