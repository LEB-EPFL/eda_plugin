"""Main functions that assemble a full EDA pipeline."""

import sys
from PyQt5 import QtWidgets

from utility.event_bus import EventBus
from eda_gui import EDAMainGUI
from interpreters.frame_rate import BinaryFrameRateInterpreter
import utility.settings


def main_test():
    """EDA loop thay can be used to test without a microscope and without CUDA installation."""
    from analysers.image import ImageAnalyser
    from examples.actuators.pycro import InjectedPycroAcquisition
    from actuators.micro_manager import MMActuator

    utility.settings.setup_logging()

    app = QtWidgets.QApplication(sys.argv)
    event_bus = EventBus()

    gui = EDAMainGUI(event_bus, viewer=True)
    actuator = MMActuator(event_bus, InjectedPycroAcquisition)
    analyser = ImageAnalyser(event_bus)
    interpreter = BinaryFrameRateInterpreter(event_bus)

    gui.show()
    actuator.gui.show()
    interpreter.gui.show()
    analyser.gui.show()

    # This could also be used with a Napari Viewer:
    # viewer = NapariImageViewer()
    # event_bus.new_network_image.connect(viewer.add_network_image)

    sys.exit(app.exec_())


def main_keras():
    """EDA loop using a neural network analyser that can be used for testing."""
    from analysers.keras import KerasAnalyser
    from examples.actuators.pycro import InjectedPycroAcquisition
    from actuators.micro_manager import MMActuator

    utility.settings.setup_logging()

    app = QtWidgets.QApplication(sys.argv)
    event_bus = EventBus()

    gui = EDAMainGUI(event_bus, viewer=True)
    actuator = MMActuator(event_bus, InjectedPycroAcquisition)
    analyser = KerasAnalyser(event_bus)
    interpreter = BinaryFrameRateInterpreter(event_bus)

    gui.show()
    actuator.gui.show()
    interpreter.gui.show()
    analyser.gui.show()

    sys.exit(app.exec_())


def main_isim():
    """EDA loop used on the iSIM."""
    from actuators.daq import DAQActuator
    from analysers.image import ImageAnalyser

    utility.settings.setup_logging()
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
    main_test()
