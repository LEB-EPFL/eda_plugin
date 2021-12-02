
from PyQt5 import QtWidgets
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot
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


class KerasAnalyser(QObject):
    """ Analyze the last image using the neural network and image the output
    This has to implement the ImageAnalyser Protocol to be able to be used in the
    EDAMainGUI."""

    new_output_shape = pyqtSignal(tuple)
    new_network_image = pyqtSignal(np.ndarray)
    new_decision_parameter = pyqtSignal(float, int)

    def __init__(self, event_thread: EventThread = None):
        super().__init__()
        self.name = "KerasAnalyser"
        self.images = None
        self.shape = None
        self.time = None
        self.start_time = None

        # Load and initialize model so first predict is fast
        self.model_path = "//lebnas1.epfl.ch/microsc125/Watchdog/Model/model_Dora.h5"
        self.model = keras.models.load_model(self.model_path, compile=True)
        self.channels = self.model.layers[0].input_shape[0][3]
        self.init_model()

        if event_thread is None:
            self.event_thread = EventThread()
            self.event_thread.start(daemon=True)
        else:
            self.event_thread = event_thread
        print(self.event_thread)

        self.event_thread.new_image_event.connect(self.start_analysis)
        print('Image Analyser Running')

    @pyqtSlot(object)
    def start_analysis(self, evt: PyImage):
        self.thread = threading.Thread(target=self.analyse_images, args=(evt, ),
                                       daemon=True)
        self.thread.start()

    def analyse_images(self, evt: PyImage):
        # First gather all of the images and only continue if all channels are there
        ready = self.gather_images(evt)
        if not ready:
            return False

        print('All channels acquired ', int(self.time))

        network_input, positions = self.prepare_images(self.images)
        network_output = self.model.predict_on_batch(network_input)
        network_output = self.post_process_output(network_output, positions)
        if evt.timepoint == 0:
            self.new_output_shape.emit(network_output.shape)
        self.new_network_image.emit(network_output)
        decision_parameter = self.extract_decision_parameter(network_output)
        # This should be evt.time once we can set the metadata on the image
        elapsed_time = round(time.time() * 1000) - self.start_time
        self.new_decision_parameter.emit(decision_parameter, elapsed_time)

    def extract_decision_parameter(self, network_output: np.ndarray) -> Number:
        return float(np.max(network_output))

    def post_process_output(self, data: np.ndarray, positions) -> np.ndarray:
        if self.model.layers[0].input_shape[0][1] is None:
            return data[0, :, :, 0]
        else:
            return stitchImage(data, positions)

    def prepare_images(self, images):
        return prepareNNImages(images[0], images[1], self.model)

    def gather_images(self, py_image: PyImage) -> bool:
        """ If there is more thatn one channel gather all the channels for one timepoint and return
        if all channels are there or not. """

        time, channel = py_image.timepoint, py_image.channel
        # print("time %d, channel %d".format(time, channel))
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
