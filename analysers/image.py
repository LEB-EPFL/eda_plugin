
from email.policy import default
import logging
import numpy as np
import time

from PyQt5.QtCore import pyqtSignal, pyqtSlot, QThreadPool
from utility.event_bus import EventBus
from utility.data_structures import PyImage
from utility import settings


log = logging.getLogger("EDA")

class ImageAnalyser(QObject):
    """Analyze the last image using the neural network and image the output
    This has to implement the ImageAnalyser Protocol to be able to be used in the
    EDAMainGUI."""

    new_output_shape = pyqtSignal(tuple)
    new_network_image = pyqtSignal(np.ndarray, tuple)
    new_decision_parameter = pyqtSignal(float, float, int)

    def __init__(self, event_bus: EventBus):
        super().__init__()
        self.name = "ImageAnalyser"
        self.shape = None
        self.time = None
        self.images = None
        self.start_time = None

        default_settings = settings.get_settings(self)
        self.channels = default_settings["channels"]
        self.z_slices = default_settings["z_slices"]

        # We will use a threadpool, this allows us to skip ahead if no thread is available
        # if acquisition is faster than analysis
        self.threadpool = QThreadPool(parent=self)
        self.threadpool.setMaxThreadCount(5)

        # Emitted events
        self.new_decision_parameter.connect(event_bus.new_decision_parameter)
        self.new_network_image.connect(event_bus.new_network_image)

        # Connect incoming events
        event_bus.acquisition_started_event.connect(self.reset_time)
        event_bus.new_image_event.connect(self.start_analysis)

    @pyqtSlot(PyImage)
    def start_analysis(self, evt: PyImage):
        # Get the worker arguments from a different function so only that can be overwritten by
        # subclasses
        worker_args = self._get_worker_args(evt)
        ready = self.gather_images(
            evt,
        )
        if not ready:
            return

        local_images = self.images.copy()
        worker = self.worker(local_images, *worker_args)
        # Connect the signals to push through
        worker.signals.new_decision_parameter.connect(self.new_decision_parameter)
        worker.signals.new_network_image.connect(self.new_network_image)
        worker.signals.new_output_shape.connect(self.new_output_shape)
        started = self.threadpool.tryStart(worker)
        log.info(f"timepoint {evt.timepoint} -> {worker.__class__.__name__}: {started}")

    def gather_images(self, py_image: PyImage) -> bool:
        """Gather the amount of images needed."""
        # TODO: Also make this work for z-slices
        try:
            self.images[:, :, py_image.channel] = py_image.raw_image
        except (ValueError, TypeError):
            self._reset_shape(py_image)
            self.images[:, :, py_image.channel] = py_image.raw_image

        self.time = py_image.timepoint
        if py_image.channel < self.channels - 1:
            return False
        else:
            return True

    def _get_worker_args(self):
        return []

    def _reset_shape(self, image: PyImage):
        self.shape = image.raw_image.shape
        self.images = np.ndarray([*self.shape, self.channels])

    def reset_time(self):
        log.debug(f"start_time reset in {self.__class__.__name__}")
        self.start_time = round(time.time() * 1000)

    # def new_settings(self, new_settings):
    #     # Load and initialize model so first predict is fast(er)
    #     self.model_path = new_settings["model"]
    #     self.model = keras.models.load_model(self.model_path, compile=True)
    #     self.channels = self.model.layers[0].input_shape[0][3]
    #     self.worker = new_settings["worker"]
    #     self._init_model()

    # def _init_model(self):
    #     if self.model.layers[0].input_shape[0][1] is None:
    #         size = 512
    #     else:
    #         size = self.model.layers[0].input_shape[0][1]
    #     self.model(np.random.randint(10, size=[1, size, size, self.channels]))
    #     log.info("New model initialised")