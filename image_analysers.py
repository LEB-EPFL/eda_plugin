
from PyQt5 import QtWidgets
from PyQt5.QtCore import QEventLoop, QObject, QRunnable, QThread, QThreadPool, pyqtSignal, pyqtSlot
import numpy as np
import sys
from event_bus import EventBus
from isimgui.data_structures import PyImage
from eda_original.SmartMicro.NNfeeder import prepareNNImages
from eda_original.SmartMicro.ImageTiles import stitchImage
from tensorflow import keras
from numbers import Number
import time


class KerasAnalyser(QObject):
    """ Analyze the last image using the neural network and image the output
    This has to implement the ImageAnalyser Protocol to be able to be used in the
    EDAMainGUI."""

    new_output_shape = pyqtSignal(tuple)
    new_network_image = pyqtSignal(np.ndarray)
    new_decision_parameter = pyqtSignal(float, float, int)

    def __init__(self, event_bus: EventBus):
        super().__init__()
        self.name = "KerasAnalyser"
        self.shape = None
        self.time = None
        self.images = None
        self.start_time = None

        self.threadpool = QThreadPool(parent=self)
        self.threadpool.setMaxThreadCount(5)
        # Load and initialize model so first predict is fast(er)
        self.model_path = "//lebnas1.epfl.ch/microsc125/Watchdog/Model/model_Dora.h5"
        self.model = keras.models.load_model(self.model_path, compile=True)
        self.channels = self.model.layers[0].input_shape[0][3]

        self.init_model()
        self.frame_counter = FrameCounterThread(self, event_bus)

        # Emitted events
        self.new_decision_parameter.connect(event_bus.new_decision_parameter)
        self.new_network_image.connect(event_bus.new_network_image)

        # Connect incoming events
        event_bus.acquisition_started_event.connect(self.frame_counter.start)
        event_bus.acquisition_started_event.connect(self.reset_time)
        event_bus.acquisition_ended_event.connect(self.frame_counter.exit)
        event_bus.new_image_event.connect(self.start_analysis)
        print('Image Analyser Running')

    @pyqtSlot(PyImage)
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
        worker = KerasAnalyserWorker(self.model, local_images, evt.timepoint, self.start_time)
        # # Connect the signals to push through
        worker.signals.new_decision_parameter.connect(self.new_decision_parameter)
        worker.signals.new_network_image.connect(self.new_network_image)
        worker.signals.new_output_shape.connect(self.new_output_shape)
        self.threadpool.tryStart(worker)

    def gather_images(self, py_image: PyImage) -> bool:
        """ If there is more than one channel gather all the channels for one timepoint and return
        if all channels are there or not. """
        try:
            self.images[py_image.channel] = py_image.raw_image
        except (ValueError, TypeError):
            self.reset_shape(py_image)
            self.images[py_image.channel] = py_image.raw_image

        self.time = py_image.timepoint
        if py_image.channel < self.channels - 1:
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


class FrameCounterThread(QThread):
    def __init__(self, parent, event_bus):
        super().__init__(parent=parent)
        self.frame_counter = self.FrameCounter(event_bus)
        self.frame_counter.moveToThread(self)

    def start(self):
        if not self.isRunning():
            super().start()
        self.frame_counter.start()

    def exit(self):
        self.frame_counter.stop()
        super().exit()


    class FrameCounter(QObject):
        def __init__(self, event_bus:EventBus):
            super().__init__()
            self.loop = QEventLoop(self)
            event_bus.new_image_event.connect(self.increase_frame_counter)
            self.frame_counter = 0

        @pyqtSlot(PyImage)
        def increase_frame_counter(self, evt):
            self.frame_counter = evt.timepoint

        def start(self):
            if not self.loop.isRunning():
                self.loop.exec()

        def stop(self):
            self.loop.exit()


class KerasAnalyserWorker(QRunnable):

    def __init__(self, model, local_images: np.ndarray, timepoint: int, start_time: float):
        super(KerasAnalyserWorker, self).__init__()
        self.signals = self.Signals()
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
        elapsed_time = round(time.time() * 1000) - self.start_time
        self.signals.new_decision_parameter.emit(decision_parameter, elapsed_time/1000,
                                                 self.timepoint)

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
        new_decision_parameter = pyqtSignal(float, float, int)


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
