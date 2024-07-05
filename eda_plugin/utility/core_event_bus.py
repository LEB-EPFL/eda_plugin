
from qtpy.QtCore import QObject, Signal
from pymmcore_plus import CMMCorePlus
from pymm_eventserver.data_structures import ParameterSet, PyImage, MMSettings
from eda_plugin.utility.core_gui import CoreMDAWidget
import numpy as np
from useq import MDASequence, MDAEvent
import logging

log = logging.getLogger("EDA")
class CoreEventBus(QObject):
    """A hub for events that does not use the events from the Micro-Manager Java GUI, but from
    pymmcore-plus direclty."""
    # Interpreter Events
    new_interpretation = Signal(float)
    new_parameters = Signal(ParameterSet)

    # Analyser Events
    new_decision_parameter = Signal(float, float, int)
    new_output_shape = Signal(tuple)
    new_network_image = Signal(np.ndarray, tuple)
    new_prepared_image = Signal(np.ndarray, int)

    # Magellan Events
    new_magellan_settings = Signal(dict)

    # Events from pymmcore-plus
    new_acquisition_started_event = Signal(object)
    acquisition_started_event = Signal(object)
    acquisition_ended_event = Signal(object)
    new_image_event = Signal(PyImage)
    mda_settings_event = Signal(object)
    useq_settings_event = Signal(object)
    eda_useq_event = Signal(object)
    configuration_settings_event = Signal(str, str, object)
    new_mask_event = Signal(np.ndarray)


    def __init__(self, mmcore:CMMCorePlus, mda_gui: CoreMDAWidget, eda_gui, preview=None):
        """Connect to Micro-Manager using the EventThread. Pass these signals through to subs."""
        super().__init__()
        mmcore.mda.events.frameReady.connect(self.translate_image)
        mmcore.mda.events.sequenceStarted.connect(self.acquisition_started_event.emit)
        mmcore.mda.events.sequenceFinished.connect(self.acquisition_ended_event.emit)
        mmcore.events.propertyChanged.connect(self.configuration_settings_event.emit)

        #TODO: This will have to be connected to the MDA GUI that will be used.
        mda_gui.mda_settings_event.connect(self.translate_mda_settings)
        mda_gui.mda_settings_event.connect(self.useq_settings_event.emit)
        

        try:
            eda_gui.mda_settings_event.connect(self.eda_useq_event.emit)
        except:
            log.warning("No EDA GUI connected!")

        if preview is not None:
            preview.new_mask.connect(self.new_mask_event.emit)

        self.initialized = True
        print("EventBus ready")

    def translate_mda_settings(self, settings:MDASequence):
        new_settings = MMSettings()
        new_settings.n_channels = max(1, settings.sizes['c'])
        new_settings.n_slices = max(1, settings.sizes['z'])
        channels = {}
        for channel in settings.channels:
            channels[channel.config] = 100
        new_settings.channels = channels
        self.mda_settings_event.emit(new_settings)

    def translate_image(self, image:np.ndarray, event:MDAEvent):
        """Translate the image from the MDAEvent into a PyImage."""
        index = event.index
        self.new_image_event.emit(PyImage(image, {}, index.get('t', 0), index.get('c', 0), index.get('z', 0), 0))