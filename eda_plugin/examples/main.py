"""Main functions that assemble a full EDA pipeline."""

import sys
sys.coinit_flags = 0

import eda_plugin.utility.settings
# from eda_plugin.actuators.micro_manager import TimerMMAcquisition

from eda_plugin.utility.eda_gui import EDAMainGUI
from eda_plugin.utility.event_bus import EventBus
from eda_plugin.utility.writers import Writer
from PyQt5 import QtWidgets
import logging

logging.basicConfig(level=logging.DEBUG)


def basic():
    """EDA loop that can be used to test without a microscope and without CUDA installation."""
    from eda_plugin.actuators.micro_manager import MMActuator, TimerMMAcquisition
    from eda_plugin.interpreters.frame_rate import BinaryFrameRateInterpreter
    from eda_plugin.analysers.image import ImageAnalyser

    eda_plugin.utility.settings.setup_logging()

    # Construct the QApplication environment, that the GUIs and event loop runs in.
    app = QtWidgets.QApplication(sys.argv)

    # Start an additional zmq server that works together with the PythonEventServer Plugin
    # for both communication between the EDA components and Micro-Manager.
    event_bus = EventBus()

    # Call the main components of the EDA loop (TimerMMAcquisition is also the default)
    actuator = MMActuator(event_bus, TimerMMAcquisition)
    analyser = ImageAnalyser(event_bus)
    interpreter = BinaryFrameRateInterpreter(event_bus)

    # Start the main GUI showing the EDA plot and the controls for the specific components
    gui = EDAMainGUI(event_bus, viewer=False)
    gui.show()
    actuator.gui.show()
    interpreter.gui.show()

    # Start the event loop
    sys.exit(app.exec_())


# This could also be used with a Napari Viewer:
# viewer = NapariImageViewer()
# event_bus.new_network_image.connect(viewer.add_network_image)


def pyro():
    """EDA loop thay can be used to test without a microscope and without CUDA installation."""
    from eda_plugin.actuators.micro_manager import MMActuator
    from eda_plugin.actuators.pycromanager import PycroAcquisition
    from eda_plugin.analysers.image import PycroImageAnalyser
    from eda_plugin.interpreters.frame_rate import BinaryFrameRateInterpreter

    eda_plugin.utility.settings.setup_logging()

    app = QtWidgets.QApplication(sys.argv)
    event_bus = EventBus()

    gui = EDAMainGUI(event_bus, viewer=False)
    actuator = MMActuator(event_bus, PycroAcquisition)
    analyser = PycroImageAnalyser(event_bus)
    interpreter = BinaryFrameRateInterpreter(event_bus)

    gui.show()
    actuator.gui.show()
    interpreter.gui.show()

    sys.exit(app.exec_())


def keras():
    """EDA loop using a neural network analyser that can be used for testing."""
    from eda_plugin.actuators.micro_manager import MMActuator
    from eda_plugin.analysers.keras import KerasAnalyser
    from eda_plugin.interpreters.frame_rate import BinaryFrameRateInterpreter

    eda_plugin.utility.settings.setup_logging()

    app = QtWidgets.QApplication(sys.argv)
    event_bus = EventBus()

    gui = EDAMainGUI(event_bus, viewer=True)
    actuator = MMActuator(event_bus)
    analyser = KerasAnalyser(event_bus)
    interpreter = BinaryFrameRateInterpreter(event_bus)
    writer = Writer(event_bus)

    gui.add_dock_widget(actuator.gui, "Actuator")
    gui.add_dock_widget(interpreter.gui, "Interpreter")
    gui.add_dock_widget(analyser.gui, "Analyser")
    gui.add_dock_widget(writer.gui, "Save Data")

    gui.show()
    # actuator.gui.show()
    # interpreter.gui.show()
    # analyser.gui.show()

    sys.exit(app.exec_())


def pyro_keras():
    """EDA loop thay can be used to test without a microscope and without CUDA installation."""
    from eda_plugin.actuators.micro_manager import MMActuator
    from eda_plugin.analysers.keras import KerasAnalyser
    from eda_plugin.interpreters.frame_rate import BinaryFrameRateInterpreter

    from .actuators import InjectedPycroAcquisition

    eda_plugin.utility.settings.setup_logging()

    app = QtWidgets.QApplication(sys.argv)
    event_bus = EventBus()

    gui = EDAMainGUI(event_bus, viewer=True)
    actuator = MMActuator(event_bus, InjectedPycroAcquisition)
    analyser = KerasAnalyser(event_bus)
    interpreter = BinaryFrameRateInterpreter(event_bus)

    gui.show()
    actuator.gui.show()
    analyser.gui.show()
    interpreter.gui.show()

    sys.exit(app.exec_())


def main_isim():
    """EDA loop used on the iSIM."""
    from eda_plugin.actuators.daq import DAQActuator
    from eda_plugin.analysers.keras import KerasAnalyser
    from eda_plugin.interpreters.frame_rate import BinaryFrameRateInterpreter

    eda_plugin.utility.settings.setup_logging()
    app = QtWidgets.QApplication(sys.argv)

    event_bus = EventBus()
    gui = EDAMainGUI(event_bus, viewer=True)

    actuator = DAQActuator(event_bus)
    analyser = KerasAnalyser(event_bus)
    interpreter = BinaryFrameRateInterpreter(event_bus)
    # writer = Writer(event_bus)

    # gui.add_dock_widget(actuator.gui)
    gui.add_dock_widget(interpreter.gui)
    gui.add_dock_widget(analyser.gui)
    # gui.add_dock_widget(writer.gui, "Save Data")

    gui.show()
    # actuator.gui.show()
    sys.exit(app.exec_())

def zen():
    from unittest.mock import MagicMock
    import pythoncom
    import win32com
    from eda_plugin.actuators.zeiss import ZenActuator
    from eda_plugin.analysers.position import PositionAnalyser
    from eda_plugin.utility.event_threads import ZenEventThread
    from eda_plugin.interpreters.frame_rate import BinaryFrameRateInterpreter
    from pymm_eventserver.data_structures import ParameterSet

    app = QtWidgets.QApplication(sys.argv)

    # myStream = pythoncom.CreateStreamOnHGlobal()   
    # zen_id =pythoncom.CoMarshalInterThreadInterfaceInStream(pythoncom.IID_IDispatch, zen)
    pythoncom.CoInitialize()

    event_bus = EventBus(event_thread=ZenEventThread, subscribe_to=zen)
    gui = EDAMainGUI(event_bus, viewer=True)
    actuator = ZenActuator(event_bus)
    analyser = PositionAnalyser(event_bus)
    interpreter = BinaryFrameRateInterpreter(event_bus)
    params = ParameterSet(slow_interval = 0, fast_interval = 1, lower_threshold = 80, upper_threshold = 250)
    interpreter.gui.new_external_parameters(params)
    interpreter.min_fast_frames = 0
    interpreter.update_parameters(params)
    # from eda_plugin.analysers.fusion_focus import My_GUI
    # gui.add_dock_widget(My_GUI())

    gui.add_dock_widget(actuator.gui)
    gui.add_dock_widget(interpreter.gui)
    gui.show()

    sys.exit(app.exec_())


flavours = {"pyro": pyro, "keras": keras, "pyro_keras": pyro_keras, "main_isim": main_isim, "zen": zen}
try:
    flavour = flavours[sys.argv[1]]
except (IndexError, KeyError) as e:
    flavour = zen

if __name__ == "__main__":
    flavour()
