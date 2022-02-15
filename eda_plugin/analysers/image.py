"""Basic analyser implementation for images.

This basic analyser is set up to receive images from the EventBus, analyse them using basic image
analysis functions and send a decision parameter back to the EventBus to be handed on to an
interpreter.
"""

import logging
import numpy as np
import time

from PyQt5.QtCore import pyqtSignal, pyqtSlot, QThreadPool, QObject, QRunnable
from eda_plugin.utility.event_bus import EventBus
from eda_plugin.utility.data_structures import PyImage, MMSettings
from eda_plugin.utility import settings


log = logging.getLogger("EDA")


class ImageAnalyser(QObject):
    """Basic image analyser.

    Receives and gathers the needed amount of images as set in settings.json. Once all are received
    it tries to start a worker in a threadpool to analyse the image. The worker itself will pass the
    value it calculated on to any expecting interpreters.
    """

    new_decision_parameter = pyqtSignal(float, float, int)

    def __init__(self, event_bus: EventBus):
        """Get settings from settings.json, set up the threadpool and connect signals."""
        super().__init__()

        self.shape = None
        self.time = None
        self.images = None
        self.start_time = None

        settings = event_bus.studio.acquisitions().get_acquisition_settings()
        settings = MMSettings(settings)
        self.new_mda_settings(settings)

        # Attach the standard worker, subclasses can replace this.
        self.worker = ImageAnalyserWorker

        # We will use a threadpool, this allows us to skip ahead if no thread is available
        # if acquisition is faster than analysis
        self.threadpool = QThreadPool(parent=self)
        self.threadpool.setMaxThreadCount(5)

        # Emitted events
        self.new_decision_parameter.connect(event_bus.new_decision_parameter)

        # Connect incoming events
        self.connect_incoming_events(event_bus)

    def connect_incoming_events(self, event_bus: EventBus) -> None:
        """Connect the events here, so subclasses can choose to not do so."""
        event_bus.acquisition_started_event.connect(self._reset_time)
        event_bus.new_image_event.connect(self.start_analysis)
        event_bus.mda_settings_event.connect(self.new_mda_settings)

    @pyqtSlot(PyImage)
    def start_analysis(self, evt: PyImage):
        """Image arrived, see if all images were gathered and if so, start analysis."""
        ready = self.gather_images(evt)
        if not ready:
            return

        # Get the worker arguments from a different function so only that can be overwritten by
        # subclasses
        worker_args = self._get_worker_args(evt)

        local_images = self.images.copy()
        worker = self.worker(
            local_images, evt.timepoint, self.start_time, **worker_args
        )
        # Connect the signals to push through
        self.connect_worker_signals(worker)
        started = self.threadpool.tryStart(worker)
        log.info(f"timepoint {evt.timepoint} -> {worker.__class__.__name__}: {started}")

    def connect_worker_signals(self, worker: QRunnable):
        """Connect worker signals in extra method, so that this can be overwritten independently."""
        worker.signals.new_decision_parameter.connect(self.new_decision_parameter)

    def new_mda_settings(self, new_settings: MMSettings):
        self.channels = new_settings.n_channels
        self.slices = new_settings.n_slices
        log.info(f"New settings: {self.channels} channels & {self.slices} slices")

    def gather_images(self, py_image: PyImage) -> bool:
        """Gather the amount of images needed."""

        try:
            self.images[:, :, py_image.channel, py_image.z_slice] = py_image.raw_image
        except (ValueError, TypeError, IndexError):
            self._reset_shape(py_image)
            self.images[:, :, py_image.channel, py_image.z_slice] = py_image.raw_image

        self.time = py_image.timepoint
        if py_image.channel < self.channels - 1 or py_image.z_slice < self.slices - 1:
            return False
        else:
            return True

    def _get_worker_args(self, evt):
        return {}

    def _reset_shape(self, image: PyImage):
        self.shape = image.raw_image.shape
        self.images = np.ndarray([*self.shape, self.channels, self.slices])

    def _reset_time(self):
        log.debug(f"start_time reset in {self.__class__.__name__}")
        self.start_time = round(time.time() * 1000)


class ImageAnalyserWorker(QRunnable):
    """Worker to be executed in the threadpool of the ImageAnalyser."""

    def __init__(self, local_images: np.ndarray, timepoint: int, start_time: int):
        """Initialise worker."""
        super().__init__()
        self.signals = self._Signals()
        self.local_images = local_images
        self.timepoint = timepoint
        self.start_time = start_time
        self.autoDelete = True

    def run(self):
        """Get the first pixel value of the passed images and return."""
        decision_parameter = self.extract_decision_parameter(self.local_images)
        elapsed_time = round(time.time() * 1000) - self.start_time
        self.signals.new_decision_parameter.emit(
            decision_parameter, elapsed_time / 1000, self.timepoint
        )

    def extract_decision_parameter(self, network_output: np.ndarray):
        """Return the first value of the ndarray."""
        return float(network_output.flatten()[0])

    class _Signals(QObject):
        """Signals have to be separate because QRunnable can't have its own."""

        new_decision_parameter = pyqtSignal(float, float, int)


class PycroImageAnalyser(ImageAnalyser):
    def __init__(self, event_bus):
        super().__init__(event_bus)

    def connect_incoming_events(self, event_bus: EventBus) -> None:
        """Do not connect the MDA and acquisition events, we need the info from magellan"""
        event_bus.new_image_event.connect(self.start_analysis)
        event_bus.new_magellan_settings.connect(self.new_magellan_settings)

    def new_magellan_settings(self, new_settings: dict):
        self.channels = len(new_settings["channels"])

        try:
            slices = (
                abs(new_settings["z_end"] - new_settings["z_start"])
                / new_settings["z_step"]
            )
            if slices % 1 == 0:
                self.slices = int(slices) + 2
            else:
                self.slices = int(np.ceil(slices)) + 1
        except:
            self.slices = 1

        log.info(
            f"Magellan settings in Analyser: {self.channels} channels & {self.slices} slices"
        )
        self.start_time = time.time()
        if self.images is not None:
            self._reset_shape(PyImage(self.images[0], 0, 0, 0, 0))
