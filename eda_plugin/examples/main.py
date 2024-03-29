"""Main functions that assemble a full EDA pipeline."""

import sys
from eda_plugin.interpreters.presets import PresetsInterpreter

import eda_plugin.utility.settings
from eda_plugin.actuators.micro_manager import TimerMMAcquisition
from eda_plugin.interpreters.frame_rate import BinaryFrameRateInterpreter
from eda_plugin.utility.eda_gui import EDAMainGUI
from eda_plugin.utility.event_bus import EventBus
from eda_plugin.utility.writers import Writer
from qtpy import QtWidgets


def basic():
    """EDA loop that can be used to test without a microscope and without CUDA installation."""
    from eda_plugin.actuators.micro_manager import MMActuator, TimerMMAcquisition
    from eda_plugin.analysers.image import ImageAnalyser

    eda_plugin.utility.settings.setup_logging()

    # Construct the QApplication environment, that the GUIs and event loop runs in.
    app = QtWidgets.QApplication(sys.argv)

    # Start an additional zmq server that works together with the PythonEventServer Plugin
    # for both communication between the EDA components and Micro-Manager.
    event_bus = EventBus()

    # Call the main components of the EDA loop (TimerMMAcquisition is also the default)
    actuator = MMActuator(event_bus, TimerMMAcquisition)
    # actuator = ContrastSwitcher(event_bus)
    analyser = ImageAnalyser(event_bus)
    interpreter = BinaryFrameRateInterpreter(event_bus)

    # Start the main GUI showing the EDA plot and the controls for the specific components
    gui = EDAMainGUI(event_bus, viewer=True)
    gui.add_dock_widget(interpreter.gui, "Actuator")
    gui.add_dock_widget(analyser.gui, "Analyser")
    gui.show()

    # Start the event loop
    sys.exit(app.exec_())


# This could also be used with a Napari Viewer:
# viewer = NapariImageViewer()
# event_bus.new_network_image.connect(viewer.add_network_image)


def pyro():
    """EDA loop thay can be used to test without a microscope and without CUDA installation."""
    from eda_plugin.actuators.micro_manager import MMActuator
    from eda_plugin.actuators.pycro import PycroAcquisition
    from eda_plugin.analysers.image import PycroImageAnalyser

    eda_plugin.utility.settings.setup_logging()

    app = QtWidgets.QApplication(sys.argv)
    event_bus = EventBus()

    gui = EDAMainGUI(event_bus, viewer=False)
    actuator = MMActuator(event_bus, PycroAcquisition)
    analyser = PycroImageAnalyser(event_bus)
    interpreter = BinaryFrameRateInterpreter(event_bus)

    gui.show()
    gui.add_dock_widget(actuator.gui, "Actuator")
    gui.add_dock_widget(interpreter.gui, "Interpreter")
    # gui.add_dock_widget(analyser.gui, "Analyser")

    sys.exit(app.exec_())

def writer():
    """Just run the ome_ngff writer"""
    app = QtWidgets.QApplication(sys.argv)
    event_bus = EventBus()
    writer = Writer(event_bus)
    writer.gui.show()
    sys.exit(app.exec_())

def keras():
    """EDA loop using a neural network analyser that can be used for testing."""
    from eda_plugin.actuators.micro_manager import MMActuator
    from eda_plugin.analysers.keras import KerasAnalyser
    from eda_plugin.utility.writers import Writer


    eda_plugin.utility.settings.setup_logging()

    app = QtWidgets.QApplication(sys.argv)
    event_bus = EventBus()

    gui = EDAMainGUI(event_bus, viewer=True)
    actuator = MMActuator(event_bus)
    analyser = KerasAnalyser(event_bus)
    interpreter = BinaryFrameRateInterpreter(event_bus)
    # writer = Writer(event_bus)

    gui.add_dock_widget(actuator.gui, "Actuator")
    gui.add_dock_widget(interpreter.gui, "Interpreter")
    gui.add_dock_widget(analyser.gui, "Analyser")
    # gui.add_dock_widget(writer.gui, "Save Data")

    gui.show()

    sys.exit(app.exec_())


def pyro_keras():
    """EDA loop thay can be used to test without a microscope and without CUDA installation."""
    from eda_plugin.actuators.micro_manager import MMActuator
    from eda_plugin.analysers.keras import KerasAnalyser

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
    from eda_plugin.utility.writers import Writer
    from eda_plugin.actuators.daq import DAQActuator
    from eda_plugin.analysers.keras import KerasAnalyser

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

def presets():
    """Using the presets Actuator without DAQ."""
    """EDA loop using a neural network analyser that can be used for testing."""
    from eda_plugin.actuators.daq_presets import DAQPresetsActuator
    from eda_plugin.analysers.keras import KerasAnalyser
    from eda_plugin.analysers.image import ImageAnalyser

    eda_plugin.utility.settings.setup_logging()

    app = QtWidgets.QApplication(sys.argv)
    event_bus = EventBus()

    gui = EDAMainGUI(event_bus, viewer=True)
    print("Actuator")
    actuator = DAQPresetsActuator(event_bus)
    print("Analyser")
    analyser = KerasAnalyser(event_bus)
    print("Interpreter")
    interpreter = PresetsInterpreter(event_bus)
    # writer = Writer(event_bus)

    print("Adding dock widgets")
    gui.add_dock_widget(actuator.gui, "Actuator")
    gui.add_dock_widget(interpreter.gui, "Interpreter")
    gui.add_dock_widget(analyser.gui, "Analyser")
    # gui.add_dock_widget(writer.gui, "Save Data")

    print("Show GUI")
    gui.show()
    # actuator.gui.show()
    # interpreter.gui.show()
    # analyser.gui.show()

    sys.exit(app.exec_())


def core():
    import sys
    import time
    # from eda_plugin.analysers.keras import KerasAnalyser
    from eda_plugin.analysers.image import ImageAnalyser
    from eda_plugin.utility.core_event_bus import CoreEventBus
    from eda_plugin.actuators.pymmc import CoreActuator
    from eda_plugin.utility.core_gui import CoreMDAWidget

    eda_plugin.utility.settings.setup_logging()

    app = QtWidgets.QApplication(sys.argv)

    mda = CoreMDAWidget()
    mda.show()

    event_bus = CoreEventBus(mda)
    actuator = CoreActuator(event_bus)
    analyser = ImageAnalyser(event_bus)
    interpreter = BinaryFrameRateInterpreter(event_bus)

    gui = EDAMainGUI(event_bus, viewer=True)
    gui.add_dock_widget(actuator.gui, "Actuator")
    gui.add_dock_widget(interpreter.gui, "Interpreter")
    gui.add_dock_widget(analyser.gui, "Analyser")
    gui.show()

    sys.exit(app.exec_())


flavours = {"basic": basic, "pyro": pyro, "keras": keras, "pyro_keras": pyro_keras,
            "main_isim": main_isim, "core": core}
try:
    flavour = flavours[sys.argv[1]]
except (IndexError, KeyError) as e:
    flavour = basic

if __name__ == "__main__":
    flavour()
