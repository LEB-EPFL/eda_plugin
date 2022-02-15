"""Main functions that assemble a full EDA pipeline."""

import sys
from PyQt5 import QtWidgets
from eda_plugin.actuators.micro_manager import TimerMMAcquisition

from eda_plugin.utility.event_bus import EventBus
from eda_plugin.utility.eda_gui import EDAMainGUI
from eda_plugin.interpreters.frame_rate import BinaryFrameRateInterpreter
import eda_plugin.utility.settings


def basic():
    """EDA loop that can be used to test without a microscope and without CUDA installation."""
    from eda_plugin.analysers.image import ImageAnalyser
    from eda_plugin.actuators.micro_manager import MMActuator, TimerMMAcquisition

    eda_plugin.utility.settings.setup_logging()

    app = QtWidgets.QApplication(sys.argv)
    event_bus = EventBus()

    gui = EDAMainGUI(event_bus, viewer=False)
    actuator = MMActuator(event_bus, TimerMMAcquisition)
    analyser = ImageAnalyser(event_bus)
    interpreter = BinaryFrameRateInterpreter(event_bus)

    gui.show()
    actuator.gui.show()
    interpreter.gui.show()

    # This could also be used with a Napari Viewer:
    # viewer = NapariImageViewer()
    # event_bus.new_network_image.connect(viewer.add_network_image)

    sys.exit(app.exec_())


def pyro():
    """EDA loop thay can be used to test without a microscope and without CUDA installation."""
    from eda_plugin.analysers.image import PycroImageAnalyser
    from eda_plugin.actuators.pycromanager import PycroAcquisition
    from eda_plugin.actuators.micro_manager import MMActuator

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
    from eda_plugin.analysers.keras import KerasAnalyser
    from eda_plugin.actuators.micro_manager import MMActuator

    eda_plugin.utility.settings.setup_logging()

    app = QtWidgets.QApplication(sys.argv)
    event_bus = EventBus()

    gui = EDAMainGUI(event_bus, viewer=True)
    actuator = MMActuator(event_bus)
    analyser = KerasAnalyser(event_bus)
    interpreter = BinaryFrameRateInterpreter(event_bus)

    gui.show()
    actuator.gui.show()
    interpreter.gui.show()
    analyser.gui.show()

    sys.exit(app.exec_())


def pyro_keras():
    """EDA loop thay can be used to test without a microscope and without CUDA installation."""
    from eda_plugin.analysers.keras import KerasAnalyser
    from .actuators import InjectedPycroAcquisition
    from eda_plugin.actuators.micro_manager import MMActuator

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
    from eda_plugin.analysers.image import ImageAnalyser

    eda_plugin.utility.settings.setup_logging()
    app = QtWidgets.QApplication(sys.argv)

    event_bus = EventBus()
    gui = EDAMainGUI(event_bus, viewer=True)
    actuator = DAQActuator(event_bus)
    analyser = ImageAnalyser(event_bus)
    interpreter = BinaryFrameRateInterpreter(event_bus)

    gui.show()
    # actuator.gui.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    pyro_keras()
