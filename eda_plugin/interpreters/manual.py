from qtpy.QtCore import Signal, QObject
from qtpy.QtWidgets import QPushButton
from eda_plugin.utility.event_bus import EventBus

class ManualInterpreter(QObject):
    """Take the output calcualted by an ImageAnalyser and decide which imaging speed to use next."""

    new_interpretation = Signal(float)
    new_parameters = Signal(dict)

    def __init__(self, event_bus: EventBus, gui: bool = True):
        """Load the default values, start the GUI and connect the events."""
        super().__init__()

        self.gui = QPushButton("Change Mode")
        self.gui.clicked.connect(self.change_mode)


        # To keep the paramater sent numerical, 0: screen, 1:image
        self.mode = 1
        self.num_fast_frames = 0

        # Emitted signals register at event_bus
        self.new_interpretation.connect(event_bus.new_interpretation)


        # Incoming events
        self.new_interpretation.emit(self.mode)

    def change_mode(self):
        self.mode = 1 if self.mode == 0 else 0
        self.new_interpretation.emit(self.mode)
