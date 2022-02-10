"""Image analysers based on keras neuronal networks.

Adaptations of analysers.image.ImageAnalyser for use with neural networks implemented in tensorflow
and keras. The usage of a Threadpool for the workers is helpful here, because pre/postprocessing and
the inference can take some time. This can slow down analysis, but as the threadpool only allows to
start a worker if a thread is available, analysis will keep up with acquisiton by skipping frames if
behind.
"""


import logging
import time
import numpy as np
import importlib
import inspect

from PyQt5 import QtWidgets
from PyQt5.QtCore import QObject, QRunnable, pyqtSignal
import qdarkstyle

from tensorflow import keras
from eda_plugin.analysers.image import ImageAnalyser, ImageAnalyserWorker

from eda_plugin.utility.qt_classes import QWidgetRestore
from eda_plugin.utility.event_bus import EventBus
from eda_plugin.utility import settings
from eda_plugin.analysers.image import ImageAnalyser

log = logging.getLogger("EDA")


class KerasAnalyser(ImageAnalyser):
    """ImageAnalyser that can use a neural network for analysis of the acquired images.

    Add signals to be sent out with information about the output of the network. These will be used
    by the specific GUI to be displayed.
    """

    new_network_image = pyqtSignal(np.ndarray, tuple)
    new_output_shape = pyqtSignal(tuple)

    def __init__(self, event_bus: EventBus):
        """Load and connect the GUI. Initialise settings from the GUI."""
        super().__init__(event_bus=event_bus)
        self.gui = KerasSettingsGUI()
        self.gui.new_settings.connect(self.new_settings)
        self.new_settings(self.gui.keras_settings)
        self.event_bus = event_bus

    def connect_worker_signals(self, worker: QRunnable):
        """Connect the additional worker signals."""
        worker.signals.new_network_image.connect(self.event_bus.new_network_image)
        worker.signals.new_output_shape.connect(self.event_bus.new_output_shape)
        return super().connect_worker_signals(worker)

    def _get_worker_args(self, evt):
        """For the KerasWorker, the model is passed as an additional parameter to the worker."""
        return {"model": self.model}

    def new_settings(self, new_settings):
        """Load and initialize model so first predict is fast(er)."""
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


class KerasWorker(ImageAnalyserWorker):
    """Implementation of the QRunnable ImageAnalyserWorker that inferes a neural network model."""

    def __init__(self, *args, model):
        """QRunnable, so the signals are stored in a subclass."""
        super().__init__(*args)
        self.signals = self._Signals()
        self.model = model

    def run(self):
        """Run the model.

        Prepare the images, infer the model, calculate the decision parameter and construct the
        image that will be displayed in the GUI. Preparation and postprocessing are optional and
        can be implemented by subclasses as necessary for the specific model.
        Specific implementations can be found in examples.analysers.keras
        """
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
        log.debug(
            f"Sending new_network_image {network_output.shape} at timepoint {self.timepoint}"
        )
        self.signals.new_network_image.emit(network_output, (self.timepoint, 0))

    def prepare_images(self, images: np.ndarray):
        """To be implemented by subclass if necessary for the specific model."""
        return images

    def post_process_output(self, data: np.ndarray, network_input):
        """To be implemented by subclass if necessary for the specific model."""
        return data

    class _Signals(QObject):
        new_output_shape = pyqtSignal(tuple)
        new_network_image = pyqtSignal(np.ndarray, tuple)
        new_decision_parameter = pyqtSignal(float, float, int)


class KerasSettingsGUI(QWidgetRestore):
    """Specific GUI for the KerasAnalyser."""

    new_settings = pyqtSignal(object)

    def __init__(self):
        """Set up GUI for the keras analyser.

        Get the default settings from the settings file and set up the GUI
        """
        super().__init__()
        self.setWindowTitle("KerasSettings")

        default_settings = settings.get_settings(self)
        available_workers = self._get_available_workers(default_settings)
        self.keras_settings = settings.get_settings(__class__)

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
