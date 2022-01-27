from PyQt5 import QtWidgets

from analysers.keras import KerasAnalyser
from interpreters.frame_rate import BinaryFrameRateInterpreter
from actuators.micro_manager import MMActuator
from actuators.micro_manager import TimerMMAcquisition
from examples.actuators.pycro import InjectedPycroAcquisition
from eda_gui import EDAMainGUI
import sys
from utility.event_bus import EventBus
import utility.settings





def main_isim():
    utility.settings.setup_logging()
    app = QtWidgets.QApplication(sys.argv)

    event_bus = EventBus()
    gui = EDAMainGUI(event_bus, viewer=True)
    actuator = MMActuator(event_bus, TimerMMAcquisition)


def main_test():
    utility.settings.setup_logging()

    app = QtWidgets.QApplication(sys.argv)

    event_bus = EventBus()

    gui = EDAMainGUI(event_bus, viewer=True)
    actuator = MMActuator(event_bus, TimerMMAcquisition)
    # actuator = MMActuator(event_bus, InjectedPycroAcquisition)
    analyser = KerasAnalyser(event_bus)
    interpreter = BinaryFrameRateInterpreter(event_bus)

    gui.show()
    actuator.gui.show()
    interpreter.gui.show()
    analyser.gui.show()

    # viewer = NapariImageViewer()
    # event_bus.new_network_image.connect(viewer.add_network_image)

    sys.exit(app.exec_())




if __name__ == "__main__":
    main_test()