import eda_plugin
from eda_plugin.analysers.image import ImageAnalyser
from eda_plugin.analysers.keras import KerasAnalyser

import sys

import eda_plugin.utility.settings
from eda_plugin.interpreters.frame_rate import BinaryFrameRateInterpreter
from eda_plugin.utility.eda_gui import EDAMainGUI
from eda_plugin.utility.event_bus import EventBus
from PyQt5 import QtWidgets
from contrast import ContrastSwitcher


eda_plugin.utility.settings.setup_logging()

# Construct the QApplication environment, that the GUIs and event loop runs in.
app = QtWidgets.QApplication(sys.argv)

# Start an additional zmq server that works together with the PythonEventServer Plugin
# for both communication between the EDA components and Micro-Manager.
event_bus = EventBus()

# Call the main components of the EDA loop (TimerMMAcquisition is also the default)
# actuator = MMActuator(event_bus, TimerMMAcquisition)
actuator = ContrastSwitcher(event_bus)
analyser = KerasAnalyser(event_bus)
interpreter = BinaryFrameRateInterpreter(event_bus)

# Start the main GUI showing the EDA plot and the controls for the specific components
gui = EDAMainGUI(event_bus, viewer=True)
gui.add_dock_widget(interpreter.gui)
if isinstance(analyser, KerasAnalyser):
    gui.add_dock_widget(analyser.gui)
gui.show()
# actuator.gui.show()
# interpreter.gui.show()

# Start the event loop
sys.exit(app.exec_())