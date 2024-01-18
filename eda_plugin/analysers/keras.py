"""Image analysers based on keras neuronal networks.

Adaptations of analysers.image.ImageAnalyser for use with neural networks implemented in tensorflow
and keras. The usage of a Threadpool for the workers is helpful here, because pre/postprocessing and
the inference can take some time. This can slow down analysis, but as the threadpool only allows to
start a worker if a thread is available, analysis will keep up with acquisiton by skipping frames if
behind.
"""

import os
import re
import logging
import time
import numpy as np
import importlib
import inspect
from collections import defaultdict

from qtpy import QtWidgets
from qtpy.QtCore import QObject, QRunnable, Signal
import qdarkstyle

from pymm_eventserver.data_structures import PyImage
from tensorflow import keras
from eda_plugin.analysers.image import ImageAnalyser, ImageAnalyserWorker

from eda_plugin.utility.qt_classes import QWidgetRestore
from eda_plugin.utility.event_bus import EventBus
from eda_plugin.utility import settings
from eda_plugin.analysers.image import ImageAnalyser
from pymm_eventserver.data_structures import MMSettings

log = logging.getLogger("EDA")


class KerasAnalyser(ImageAnalyser):
    """ImageAnalyser that can use a neural network for analysis of the acquired images.

    Add signals to be sent out with information about the output of the network. These will be used
    by the specific GUI to be displayed.
    """

    new_network_image = Signal(np.ndarray, tuple)
    new_output_shape = Signal(tuple)
    settings_changed = Signal(dict)

    def __init__(self, event_bus: EventBus):
        """Load and connect the GUI. Initialise settings from the GUI."""
        super().__init__(event_bus=event_bus)
        self.event_bus = event_bus
        self.model_path = None
        self.mda_settings = MMSettings()

        self.gui = KerasSettingsGUI()
        self.gui.new_settings.connect(self.new_settings)
        self.settings_changed.connect(self.gui._set_state)
        self.new_settings(self.gui.keras_settings, init_model=False)

    def connect_worker_signals(self, worker: QRunnable):
        """Connect the additional worker signals."""
        worker.signals.new_network_image.connect(self.event_bus.new_network_image)
        worker.signals.new_prepared_image.connect(self.event_bus.new_prepared_image)
        worker.signals.new_output_shape.connect(self.event_bus.new_output_shape)
        return super().connect_worker_signals(worker)

    def _get_worker_args(self, evt):
        """For the KerasWorker, the model is passed as an additional parameter to the worker."""
        return {"model": self.model}

    def gather_images(self, py_image: PyImage) -> bool:
        """Limit the gathering to only the channels in channel_choosers and rearrange"""
        print(py_image.channel)
        print(list(self.mda_settings.channels.keys()))
        image_channel_name = list(self.mda_settings.channels.keys())[py_image.channel]
        if image_channel_name in self.keras_settings['channels_to_use']:
            py_image.channel = self.keras_settings['channels_to_use'].index(image_channel_name)
            return super().gather_images(py_image)

    def new_settings(self, new_settings, init_model=True):
        """Load and initialize model so first predict is fast(er)."""
        self.keras_settings = new_settings
        self.worker = new_settings["worker"]
        print("Worker set", self.worker)
        if self.model_path == new_settings["model"] or not init_model:
            return
        self.model_path = new_settings["model"]
        try:
            # self.model = keras.models.load_model(self.model_path, compile=True)
            self.model = keras.models.load_model(self.model_path)
            self.model_channels = self.model.layers[0].input_shape[0][3]
            self._init_model()
            self._compare_model_mda()
        except OSError:
            log.warning("Model not found at this location")
            log.info(self.model_path)

    def _init_model(self):
        if self.model.layers[0].input_shape[0][1] is None:
            size = 512
        else:
            size = self.model.layers[0].input_shape[0][1]
        model_channels, model_slices = self._inspect_model(self.model)
        if model_slices > 1:
            self.model(np.random.randint(10, size=[1, size, size, model_channels, model_slices]))
        else:
            self.model(np.random.randint(10, size=[1, size, size, model_channels]))
        log.info("New model initialised")

    def _inspect_model(self, model):
        try:
            self.model_channels = self.model.layers[0].input_shape[0][3]
        except:
            self.model_channels = 1
        try:
            self.model_slices = self.model.layers[0].input_shape[0][4]
        except:
            self.model_slices = 1
        return self.model_channels, self.model_slices

    def new_mda_settings(self, new_settings: MMSettings):
        """Skip settting the number of slices or channels from the MDA settings."""
        self.mda_settings = new_settings
        pass

    def _compare_model_mda(self):
        """Compare the model and the MDA settings and add info to GUI so the values can be chosen"""
        self.model_channels, model_slices = self._inspect_model(self.model)
        # Check if there might be timepoints in this model
        if self.keras_settings["manual_timepoints"] and self.keras_settings["timepoints"]:
            self.n_timepoints, model_slices = self._inspect_model(self.model)
            self.model_channels = 1
        else:
            timepoint_search = re.search(r'_n(\d*)_f[0-9.]{1,3}', self.keras_settings["model"])
            if timepoint_search:
                self.n_timepoints = int(timepoint_search.groups()[0])
                self.model_channels = 1
                self.keras_settings["timepoints"] = True
            else:
                self.keras_settings["timepoints"] = False
            self.settings_changed.emit(self.keras_settings)
        if self.model_channels <= self.mda_settings.n_channels:
            self.gui.add_channel_chooser(self.model_channels, self.mda_settings.channels)
            self.channels = self.model_channels
            self.slices = model_slices
            self.images = None
        else:
            warning_text = f"Model and MDA Settings don't match.<br> \
                      channels, slices<br>\
                Model:          {self.model_channels},   {model_slices} <br>\
                MDA  :          {self.channels},    {self.slices}<br>"
            log.warning(warning_text)
            msg = QtWidgets.QMessageBox()
            msg.setIcon(2)
            msg.setText(warning_text)
            msg.exec()


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
        network_output = self.model.predict(network_input["pixels"])
        # The simple maximum decision parameter can be calculated without stiching
        decision_parameter = self.extract_decision_parameter(network_output)
        elapsed_time = round(time.time() * 1000) - self.start_time
        log.info(f"timepoint {self.timepoint} KerasWorker -> Interpreter")
        self.signals.new_decision_parameter.emit(
            decision_parameter, elapsed_time / 1000, self.timepoint
        )
        # Also construct the image so it can be displayed
        network_output = self.post_process_output(network_output, network_input)
        log.debug(f"Sending new_network_image {network_output.shape} at timepoint {self.timepoint}")
        self.signals.new_prepared_image.emit(network_input['pixels'][0,:,:,0], self.timepoint)
        self.signals.new_network_image.emit(network_output, (self.timepoint, 0))
        # self.signals.new_network_image.emit(network_input["pixels"][0, :, :], (self.timepoint, 0))

    def prepare_images(self, images: np.ndarray):
        """To be implemented by subclass if necessary for the specific model."""
        return images

    def post_process_output(self, data: np.ndarray, network_input):
        """To be implemented by subclass if necessary for the specific model."""
        return data

    class _Signals(QObject):
        new_output_shape = Signal(tuple)
        new_network_image = Signal(np.ndarray, tuple)
        new_decision_parameter = Signal(float, float, int)
        new_prepared_image = Signal(np.ndarray, int)

class KerasSettingsGUI(QWidgetRestore):
    """Specific GUI for the KerasAnalyser."""

    new_settings = Signal(object)

    def __init__(self):
        """Set up GUI for the keras analyser.

        Get the default settings from the settings file and set up the GUI
        """
        super().__init__()
        self.setWindowTitle("KerasSettings")

        default_settings = settings.get_settings(self)
        available_workers = self._get_available_workers(default_settings)
        self.keras_settings = settings.get_settings(__class__)
        print("SETTINGS", self.keras_settings)

        self.worker = QtWidgets.QComboBox()
        for worker in available_workers:
            self.worker.addItem(worker[1].__name__, worker[1])
        self.keras_settings["worker"] = available_workers[0][1]
        self.worker.currentIndexChanged.connect(self._select_worker)

        self.model_label = QtWidgets.QLabel("Model")
        self.model = QtWidgets.QLineEdit(self.keras_settings.get("model", ""))
        if not os.path.isfile(self.keras_settings.get("model", "")):
            corrected_path = os.path.join(
                os.path.dirname(np.__path__[0]), self.keras_settings.get("model", "")
            )
            self._select_model(corrected_path)
        self.model_select = QtWidgets.QPushButton("Select")
        self.model_select.clicked.connect(self._select_model)

        self.timepoints_chbx = QtWidgets.QCheckBox("Timepoints")
        self.timepoints_chbx.stateChanged.connect(self._timepoints_changed)

        self.setLayout(QtWidgets.QVBoxLayout())
        self.layout().addWidget(self.worker)
        self.layout().addWidget(self.model_label)
        self.layout().addWidget(self.model)
        self.layout().addWidget(self.model_select)
        self.layout().addWidget(self.timepoints_chbx)
        self.setStyleSheet(qdarkstyle.load_stylesheet(qt_api="pyqt5"))

        self.channel_choosers_title = QtWidgets.QLabel("Choose Channels to use:")
        self.channel_choosers = {}

        self.model_load_dir = self.keras_settings.get("model", os.path.join(
            os.path.abspath(os.path.join(__file__, "..", "..")), "utility", "models", "fake"))
        self.model_load_dir = os.path.dirname(self.model_load_dir)


    def _get_available_workers(self, settings):
        modules = settings.get("worker_modules", ["eda_plugin.examples.analysers"])
        available_workers = []
        for module in modules:
            module = importlib.import_module(module)
            workers = inspect.getmembers(
                module,
                lambda member: inspect.isclass(member) and member.__module__ == module.__name__,
            )
            # for worker in workers:
            #     importlib.import_module(worker[1])
            available_workers = available_workers + workers
        return available_workers

    def _select_model(self, model_path=None):
        if model_path is None or type(model_path) == bool:
            new_model = QtWidgets.QFileDialog().getOpenFileName(directory=self.model_load_dir)[0]
        else:
            new_model = model_path
        self.model_load_dir = os.path.dirname(new_model)
        self.keras_settings["model"] = new_model
        self.model.setText(new_model)
        self.keras_settings["manual_timepoints"] = False
        self.new_settings.emit(self.keras_settings)

    def _select_worker(self, index):
        self.keras_settings["worker"] = self.worker.currentData()
        self.new_settings.emit(self.keras_settings)

    def _reset_choosers(self):
        self.layout().removeWidget(self.channel_choosers_title)
        for channel_chooser in self.channel_choosers.values():
            self.layout().removeWidget(channel_chooser['widget'])

    def add_channel_chooser(self, n_channels, channels):
        print("ADDING CHANNELS", n_channels, channels)
        self._reset_choosers()
        self.channel_choosers = defaultdict(lambda: defaultdict())
        self.layout().addWidget(self.channel_choosers_title)
        for idx in range(n_channels):
            self.channel_choosers[idx]['widget']  = QtWidgets.QComboBox()
            self.channel_choosers[idx]['widget'].currentIndexChanged.connect(
                self._update_channels_to_use)
            for channel in channels:
                self.channel_choosers[idx]['widget'].addItem(channel)
            self.channel_choosers[idx]['widget'].setCurrentIndex(idx)
            self.layout().addWidget(self.channel_choosers[idx]['widget'])

    def _update_channels_to_use(self, ):
        self.keras_settings['channels_to_use'] = []
        for channel_chooser in self.channel_choosers.values():
           self.keras_settings['channels_to_use'].append(channel_chooser['widget'].currentText())
        self.new_settings.emit(self.keras_settings)

    def _timepoints_changed(self, value):
        if value == 2:
            self.keras_settings["timepoints"] = True
        else:
            self.keras_settings["timepoints"] = False
        self.keras_settings["manual_timepoints"] = True
        self.new_settings.emit(self.keras_settings)

    def _set_state(self, settings: dict):
        self.keras_settings = settings
        self.timepoints_chbx.setChecked(settings["timepoints"])

    def closeEvent(self, e):
        self.keras_settings['worker'] = str(self.keras_settings["worker"].__class__)
        settings.set_settings(self.keras_settings, calling_class=__class__)
        print("KERAS SETTINGS", self.keras_settings)
        return super().closeEvent(e)

class NetworkImageTester(ImageAnalyser):
    """Analyser without a network just to test the transmission of the network image"""
    new_network_image = Signal(np.ndarray, tuple)
    new_output_shape = Signal(tuple)

    def __init__(self, event_bus: EventBus):
        """Load and connect the GUI. Initialise settings from the GUI."""
        super().__init__(event_bus=event_bus)
        self.event_bus = event_bus
        self.model_path = None
        self.worker = NetworkImageTesterWorker

        self.gui = QWidgetRestore()

    def connect_worker_signals(self, worker: QRunnable):
        """Connect the additional worker signals."""
        worker.signals.new_network_image.connect(self.event_bus.new_network_image)
        worker.signals.new_prepared_image.connect(self.event_bus.new_prepared_image)
        worker.signals.new_output_shape.connect(self.event_bus.new_output_shape)
        return super().connect_worker_signals(worker)
    

class NetworkImageTesterWorker(ImageAnalyserWorker):
    def __init__(self, *args):
        super().__init__(*args)
        self.signals = self._Signals()

    def run(self):
        # print("Image Shape in network tester", self.local_images.shape)
        fake_img = np.random.random_integers(100, 5000, self.local_images.shape[:2])
        self.signals.new_network_image.emit(fake_img.astype(np.uint16), (self.timepoint, 0))

    class _Signals(QObject):
        new_output_shape = Signal(tuple)
        new_network_image = Signal(np.ndarray, tuple)
        new_decision_parameter = Signal(float, float, int)
        new_prepared_image = Signal(np.ndarray, int)

def main():
    """Nothing here yet."""
    pass


if __name__ == "__main__":
    main()
