
from PyQt5 import QtWidgets
from PyQt5.QtCore import QEventLoop, QObject, QRunnable, QThread, QThreadPool, pyqtSignal, pyqtSlot
import numpy as np
import sys
from event_bus import EventBus
from isimgui.data_structures import PyImage
from eda_original.SmartMicro.NNfeeder import prepareNNImages
from eda_original.SmartMicro.ImageTiles import stitchImage
# from eda_original.SmartMicro import NNio
from tensorflow import keras
from numbers import Number
import time
import qdarkstyle
from skimage import exposure, filters, transform

import matplotlib.pyplot as plt

from utility.qt_classes import QWidgetRestore


class KerasAnalyser(QObject):
    """ Analyze the last image using the neural network and image the output
    This has to implement the ImageAnalyser Protocol to be able to be used in the
    EDAMainGUI."""

    new_output_shape = pyqtSignal(tuple)
    new_network_image = pyqtSignal(np.ndarray, tuple)
    new_decision_parameter = pyqtSignal(float, float, int)

    def __init__(self, event_bus: EventBus):
        super().__init__()
        self.name = "KerasAnalyser"
        self.shape = None
        self.time = None
        self.images = None
        self.start_time = None

        # We will use a threadpool, this allows us to skip ahead if no thread is available
        # If acquisition is faster then analysis
        self.threadpool = QThreadPool(parent=self)
        self.threadpool.setMaxThreadCount(5)

        self.gui = KerasSettingsGUI()
        self.gui.new_settings.connect(self.new_settings)
        self.new_settings(self.gui.keras_settings)

        # Emitted events
        self.new_decision_parameter.connect(event_bus.new_decision_parameter)
        self.new_network_image.connect(event_bus.new_network_image)

        # Connect incoming events
        event_bus.acquisition_started_event.connect(self.reset_time)
        event_bus.new_image_event.connect(self.start_analysis)
        print('Image Analyser Running')

    @pyqtSlot(PyImage)
    def start_analysis(self, evt: PyImage):
        ready = self.gather_images(evt, )
        if not ready:
            return

        local_images = self.images.copy()
        worker = self.worker(self.model, local_images, evt.timepoint, self.start_time)
        # # Connect the signals to push through
        worker.signals.new_decision_parameter.connect(self.new_decision_parameter)
        worker.signals.new_network_image.connect(self.new_network_image)
        worker.signals.new_output_shape.connect(self.new_output_shape)
        started = self.threadpool.tryStart(worker)

        if not started:
            print('SKIPPED because no free Thread was available', evt.timepoint)

    def gather_images(self, py_image: PyImage) -> bool:
        """ If there is more than one channel gather all the channels for one timepoint and return
        if all channels are there or not. """
        try:
            self.images[:, :, py_image.channel] = py_image.raw_image
        except (ValueError, TypeError):
            self.reset_shape(py_image)
            self.images[:, :, py_image.channel] = py_image.raw_image

        self.time = py_image.timepoint
        if py_image.channel < self.channels - 1:
            return False
        else:
            return True

    def reset_shape(self, image: PyImage):
        self.shape = image.raw_image.shape
        self.images = np.ndarray([*self.shape, self.channels])

    def reset_time(self):
        print('TIME RESET')
        self.start_time = round(time.time() * 1000)

    def init_model(self):
        print('Initialize the model')
        if self.model.layers[0].input_shape[0][1] is None:
            size = 512
        else:
            size = self.model.layers[0].input_shape[0][1]
        self.model(np.random.randint(
            10, size=[1, size, size, self.channels]))

    def new_settings(self, new_settings):
        # Load and initialize model so first predict is fast(er)
        self.model_path = new_settings['model']
        self.model = keras.models.load_model(self.model_path, compile=True)
        self.channels = self.model.layers[0].input_shape[0][3]
        self.worker = new_settings['worker']
        self.init_model()


class KerasWorker(QRunnable):

    def __init__(self, model, local_images: np.ndarray, timepoint: int, start_time: float):
        super().__init__()
        self.signals = self.Signals()
        self.model = model
        self.local_images = local_images
        self.timepoint = timepoint
        self.start_time = start_time
        self.autoDelete = True

    def run(self):
        time.sleep(3)
        network_input = self.prepare_images(self.local_images)

        network_output = self.model.predict_on_batch(network_input['pixels'])
        # The simple maximum decision parameter can be calculated without stiching
        decision_parameter = self.extract_decision_parameter(network_output)
        elapsed_time = round(time.time() * 1000) - self.start_time
        self.signals.new_decision_parameter.emit(decision_parameter, elapsed_time/1000,
                                                 self.timepoint)

        # Also construct the image so it can be displayed
        network_output = self.post_process_output(network_output, network_input)
        self.signals.new_network_image.emit(network_output, (self.timepoint, 0))

    def extract_decision_parameter(self, network_output: np.ndarray) -> Number:
        return float(np.max(network_output))

    def prepare_images(self, images: np.ndarray):
        return images

    def post_process_output(self, data: np.ndarray, network_input):
        return data

    class Signals(QObject):
        new_output_shape = pyqtSignal(tuple)
        new_network_image = pyqtSignal(np.ndarray, tuple)
        new_decision_parameter = pyqtSignal(float, float, int)


class KerasRescaleWorker(KerasWorker):
    def __init__(self, model, local_images: np.ndarray, timepoint: int, start_time: float):
        super().__init__(model, local_images, timepoint, start_time)

    def prepare_images(self, images: np.ndarray):
        sig = 121.5/81
        out_range = (0, 1)
        # resize_param = 56/81
        # new_images = np.ndarray([round(images.shape[0]*resize_param),
        #                          round(images.shape[1]*resize_param),
        #                          images.shape[2]])
        for idx in range(images.shape[-1]):
            image = images[:, :, idx]
            # resc_image = transform.rescale(image, resize_param)
            image = filters.gaussian(image, sig)
            if idx == 1:
                image = image - filters.gaussian(images[:, :, idx], sig*5)
            in_range = (image.min(), image.max()) if idx == 1 else (image.mean(), image.max())
            image = exposure.rescale_intensity(image, in_range, out_range=out_range)
            images[:, :, idx] = image
        data = {'pixels': np.expand_dims(images, 0)}
        return data

    def post_process_output(self, data: np.ndarray, positions):
        # Strip off the dimensions that come from the network
        return data[0, :, :, 0]


class KerasTilingWorker(KerasWorker):
    def __init__(self, model, local_images: np.ndarray, timepoint: int, start_time: float):
        super().__init__(model, local_images, timepoint, start_time)

    def post_process_output(self, network_output: np.ndarray, input_data) -> np.ndarray:
        return stitchImage(network_output, input_data['positions'])

    def prepare_images(self, images: np.ndarray):
        tiles, positions = prepareNNImages(images[:, :, 0], images[:, :, 1], self.model)
        print(tiles.shape)
        data = {'pixels': tiles, 'positions': positions}
        return data



class KerasSettingsGUI(QWidgetRestore):
    new_settings = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("KerasSettings")

        available_workers = [KerasRescaleWorker, KerasTilingWorker]
        self.keras_settings = {'available_workers': available_workers,
                         'worker': available_workers[0],
                         'model': "W:/Watchdog/Model/paramSweep6/f32_c09_b08.h5"}
                        # 'model': "//lebnas1.epfl.ch/microsc125/Watchdog/Model/model_Dora.h5"}

        self.worker = QtWidgets.QComboBox()
        for worker in self.keras_settings['available_workers']:
            self.worker.addItem(worker.__name__, worker)
        self.worker.currentIndexChanged.connect(self.select_worker)

        self.model_label = QtWidgets.QLabel("Model")
        self.model = QtWidgets.QLineEdit(self.keras_settings['model'])
        self.model_select = QtWidgets.QPushButton("Select")
        self.model_select.clicked.connect(self.select_model)

        self.setLayout(QtWidgets.QVBoxLayout())
        self.layout().addWidget(self.worker)
        self.layout().addWidget(self.model_label)
        self.layout().addWidget(self.model)
        self.layout().addWidget(self.model_select)
        self.setStyleSheet(qdarkstyle.load_stylesheet(qt_api='pyqt5'))

    def select_model(self):
        new_model = QtWidgets.QFileDialog().getOpenFileName()[0]
        self.keras_settings['model'] = new_model
        self.model.setText(new_model)
        self.new_settings.emit(self.keras_settings)

    def select_worker(self, index):
        self.keras_settings['worker'] = self.worker.currentData()


def main():
    pass


if __name__ == "__main__":
    main()
