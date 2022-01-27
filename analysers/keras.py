import logging
import time
import numpy as np
import importlib
import inspect

from PyQt5 import QtWidgets
from PyQt5.QtCore import (
    QObject,
    QRunnable,
    QThreadPool,
    pyqtSignal,
    pyqtSlot,
)
import qdarkstyle

from tensorflow import keras
from numbers import Number
from analysers.image import ImageAnalyser

from utility.qt_classes import QWidgetRestore
from utility.event_bus import EventBus
from utility import settings
from isimgui.data_structures import PyImage
from analysers.image import ImageAnalyser

log = logging.getLogger("EDA")


class KerasAnalyser(ImageAnalyser):
    """Analyze the last image using the neural network and image the output
    This has to implement the ImageAnalyser Protocol to be able to be used in the
    EDAMainGUI."""

    def __init__(self, event_bus: EventBus):
        super().__init__()
        self.name = "KerasAnalyser"

        self.gui = KerasSettingsGUI()
        self.gui.new_settings.connect(self.new_settings)
        self.new_settings(self.gui.keras_settings)

    def _get_worker_args(self, evt):
        return [self.model, evt.timepoint, self.start_time]

    def new_settings(self, new_settings):
        # Load and initialize model so first predict is fast(er)
        self.model_path = new_settings["model"]
        self.model = keras.models.load_model(self.model_path, compile=True)
        self.channels = self.model.layers[0].input_shape[0][3]
        self.worker = new_settings["worker"]
        self._init_model()

    def _init_model(self):
        if self.model.layers[0].input_shape[0][1] is None:
            size = 512
        else:
            size = self.model.layers[0].input_shape[0][1]
        self.model(np.random.randint(10, size=[1, size, size, self.channels]))
        log.info("New model initialised")


class KerasWorker(QRunnable):
    def __init__(
        self, model, local_images: np.ndarray, timepoint: int, start_time: float
    ):
        super().__init__()
        self.signals = self._Signals()
        self.model = model
        self.local_images = local_images
        self.timepoint = timepoint
        self.start_time = start_time
        self.autoDelete = True

    def run(self):
        network_input = self.prepare_images(self.local_images)

        network_output = self.model.predict_on_batch(network_input["pixels"])
        # The simple maximum decision parameter can be calculated without stiching
        decision_parameter = self.extract_decision_parameter(network_output)
        elapsed_time = round(time.time() * 1000) - self.start_time
        self.signals.new_decision_parameter.emit(
            decision_parameter, elapsed_time / 1000, self.timepoint
        )

        # Also construct the image so it can be displayed
        network_output = self.post_process_output(network_output, network_input)
        self.signals.new_network_image.emit(network_output, (self.timepoint, 0))

    def extract_decision_parameter(self, network_output: np.ndarray) -> Number:
        return float(np.max(network_output))

    def prepare_images(self, images: np.ndarray):
        return images

    def post_process_output(self, data: np.ndarray, network_input):
        return data

    class _Signals(QObject):
        new_output_shape = pyqtSignal(tuple)
        new_network_image = pyqtSignal(np.ndarray, tuple)
        new_decision_parameter = pyqtSignal(float, float, int)


class KerasSettingsGUI(QWidgetRestore):
    new_settings = pyqtSignal(object)

    def __init__(self):
        """Set up GUI for the keras analyser.

        Get the default settings from the settings file and set up the GUI
        """
        from examples.analysers.keras import KerasRescaleWorker, KerasTilingWorker

        super().__init__()
        self.setWindowTitle("KerasSettings")

        default_settings = settings.get_settings(self)
        available_workers = self._get_available_workers(default_settings)
        self.keras_settings = settings.get_settings(self)

        self.worker = QtWidgets.QComboBox()
        for worker in available_workers:
            self.worker.addItem(worker[1].__name__, worker[1])
        self.keras_settings["worker"] = available_workers[0][1]
        self.worker.currentIndexChanged.connect(self._select_worker)

        self.model_label = QtWidgets.QLabel("Model")
        self.model = QtWidgets.QLineEdit(self.keras_settings["model"])
        self.model_select = QtWidgets.QPushButton("Select")
        self.model_select.clicked.connect(self._select_model)

        self.setLayout(QtWidgets.QVBoxLayout())
        self.layout().addWidget(self.worker)
        self.layout().addWidget(self.model_label)
        self.layout().addWidget(self.model)
        self.layout().addWidget(self.model_select)
        self.setStyleSheet(qdarkstyle.load_stylesheet(qt_api="pyqt5"))

    def _get_available_workers(self, settings):
        modules = settings["worker_modules"]
        available_workers = []
        for module in modules:
            module = importlib.import_module(module)
            workers = inspect.getmembers(
                module,
                lambda member: inspect.isclass(member)
                and member.__module__ == module.__name__,
            )
            # for worker in workers:
            #     importlib.import_module(worker[1])
            available_workers = available_workers + workers
        return available_workers

    def _select_model(self):
        new_model = QtWidgets.QFileDialog().getOpenFileName()[0]
        self.keras_settings["model"] = new_model
        self.model.setText(new_model)
        self.new_settings.emit(self.keras_settings)

    def _select_worker(self, index):
        self.keras_settings["worker"] = self.worker.currentData()
        self.new_settings.emit(self.keras_settings)


def main():
    """Nothing here yet."""
    pass


if __name__ == "__main__":
    main()
