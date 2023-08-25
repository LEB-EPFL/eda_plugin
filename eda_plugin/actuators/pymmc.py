from qtpy import QtCore, QtWidgets
from eda_plugin.utility.core_event_bus import CoreEventBus
from pymmcore_plus import CMMCorePlus
from queue import Queue
from useq import MDAEvent

class CoreActuator(QtCore.QObject):
    """Actuator that works on pymmcore directly without the need for the micro-manager Java side."""

    stop_acq_signal = QtCore.Signal()
    start_acq_signal = QtCore.Signal(object)
    new_interval = QtCore.Signal(float)

    def __init__(self, event_bus: CoreEventBus):
        super().__init__()

        self.event_bus = event_bus

        self.start_acq_signal.connect(self.event_bus.acquisition_started_event)

        self.acquisition = CoreAcquisition(event_bus, CMMCorePlus.instance())
        self.gui = CoreActuatorGUI(self)


class CoreAcquisition(QtCore.QThread):
    """Acquisition that works on pymmcore directly without the need for the micro-manager Java."""

    def __init__(self, event_bus: CoreEventBus, mmc: CMMCorePlus):
        super().__init__()

        self.event_bus = event_bus
        self._mmc = mmc

        self._queue = Queue()
        self.STOP_EVENT = object()
        self.event_bus.new_interpretation.connect(self.on_new_interpretation)

        self.timepoint = 0

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.acquire_on_timeout)
        self.timer.setInterval(2000)


    def run(self):
        self.timepoint = 0
        seq: Iterable[MDAEvent] = iter(self._queue.get, self.STOP_EVENT)
        self._mmc.run_mda(seq)  # Non-blocking
        event = MDAEvent(exposure=10, index={"t": 0, "z": 0, "c": 0})
        self._queue.put(event)
        event = MDAEvent(exposure=10, index={"t": 0, "z": 0, "c": 1})
        self._queue.put(event)
        self.timer.start()

    def acquire_on_timeout(self):
        self.timepoint += 1
        self._queue.put(MDAEvent(exposure=10, index={"t": self.timepoint, "z": 0, "c": 0}))
        self._queue.put(MDAEvent(exposure=10, index={"t": self.timepoint, "z": 0, "c": 1}))

    def on_new_interpretation(self, new_interval: float):
        """Add a new event to the queue with the new interval."""
        self.timer.setInterval(int(new_interval * 1000))

    def stop_acq(self):
        self._queue.put(self.STOP_EVENT)


class CoreActuatorGUI(QtWidgets.QWidget):
    def __init__(self, actuator: CoreActuator):
        super().__init__()
        self.actuator = actuator
        self.init_ui()


    def init_ui(self):
        self.start_btn = QtWidgets.QPushButton("Start")
        self.stop_btn = QtWidgets.QPushButton("Stop")

        self.start_btn.clicked.connect(self.actuator.acquisition.run)
        self.stop_btn.clicked.connect(self.actuator.acquisition.stop_acq)

        self.setLayout(QtWidgets.QVBoxLayout())
        self.layout().addWidget(self.start_btn)
        self.layout().addWidget(self.stop_btn)



if __name__ == "__main__":
    import sys
    import time
    from eda_plugin.analysers.image import ImageAnalyser

    # eda_plugin.utility.settings.setup_logging()
    app = QtWidgets.QApplication(sys.argv)

    event_bus = CoreEventBus()
    actuator = CoreActuator(event_bus)
    analyser = ImageAnalyser(event_bus)
    interpreter = BinaryFrameRateInterpreter(event_bus)

    gui = EDAMainGUI(event_bus, viewer=True)
    gui.add_dock_widget(actuator.gui, "Actuator")
    gui.add_dock_widget(interpreter.gui, "Interpreter")
    gui.add_dock_widget(analyser.gui, "Analyser")
    gui.show()

    sys.exit(app.exec_())