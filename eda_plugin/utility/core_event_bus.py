
from qtpy.QtCore import QObject, Signal
from pymmcore_plus import CMMCorePlus
from pymm_eventserver.data_structures import ParameterSet, PyImage, MMSettings
from eda_plugin.utility.core_gui import CoreMDAWidget
import numpy as np
from useq import MDASequence, MDAEvent

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
    configuration_settings_event = Signal(str, str, object)


    def __init__(self, mda_gui: CoreMDAWidget):
        """Connect to Micro-Manager using the EventThread. Pass these signals through to subs."""
        super().__init__()
        mmcore = CMMCorePlus.instance()
        mmcore.loadSystemConfiguration()

        mmcore.mda.events.frameReady.connect(self.translate_image)
        mmcore.mda.events.sequenceStarted.connect(self.acquisition_started_event)
        mmcore.mda.events.sequenceFinished.connect(self.acquisition_ended_event)
        mmcore.events.propertyChanged.connect(self.configuration_settings_event)

        #TODO: This will have to be connected to the MDA GUI that will be used.
        mda_gui.mda_settings_event.connect(self.translate_mda_settings)

        self.initialized = True
        print("EventBus ready")

    def translate_mda_settings(self, settings:MDASequence):
        new_settings = MMSettings()
        new_settings.n_channels = max(1, settings.sizes['c'])
        new_settings.n_slices = max(1, settings.sizes['z'])

        self.mda_settings_event.emit(new_settings)

    def translate_image(self, image:np.ndarray, event:MDAEvent):
        """Translate the image from the MDAEvent into a PyImage."""
        index = event.index
        self.new_image_event.emit(PyImage(image, {}, index['t'], index['c'], index['z'], 0))