
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot
from PyQt5 import QtWidgets
from data_structures import ParameterSet
import time
from event_bus import EventBus
from utility.qt_classes import QWidgetRestore

DEFAULT_VALUES = ParameterSet(slow_interval=5,
                              fast_interval=0,
                              lower_threshold=75,
                              upper_threshold=110)


class BinaryFrameRateParameterForm(QWidgetRestore):
    new_parameters = pyqtSignal(object)

    def __init__(self):
        super().__init__()

        self.slow_interval_input = QtWidgets.QLineEdit()
        self.fast_interval_input = QtWidgets.QLineEdit()
        self.lower_threshold_input = QtWidgets.QLineEdit()
        self.upper_threshold_input = QtWidgets.QLineEdit()

        self.slow_interval_input.setMaximumWidth(50)
        self.fast_interval_input.setMaximumWidth(50)
        self.lower_threshold_input.setMaximumWidth(50)
        self.upper_threshold_input.setMaximumWidth(50)

        self.slow_interval_input.setText(str(DEFAULT_VALUES.slow_interval))
        self.fast_interval_input.setText(str(DEFAULT_VALUES.fast_interval))
        self.lower_threshold_input.setText(str(DEFAULT_VALUES.lower_threshold))
        self.upper_threshold_input.setText(str(DEFAULT_VALUES.upper_threshold))

        self.slow_interval_input.editingFinished.connect(self.update_parameters)
        self.fast_interval_input.editingFinished.connect(self.update_parameters)
        self.lower_threshold_input.editingFinished.connect(self.update_parameters)
        self.upper_threshold_input.editingFinished.connect(self.update_parameters)

        param_layout = QtWidgets.QFormLayout(self)
        param_layout.addRow('Slow Interval [s]', self.slow_interval_input)
        param_layout.addRow('Fast Interval [s]', self.fast_interval_input)
        param_layout.addRow('Lower Threshold', self.lower_threshold_input)
        param_layout.addRow('Upper Threshold', self.upper_threshold_input)

        self.param_set = DEFAULT_VALUES

    def update_parameters(self):
        self.param_set.slow_interval = float(str(self.slow_interval_input.text()))
        self.param_set.fast_interval = float(str(self.fast_interval_input.text()))
        self.param_set.lower_threshold = int(str(self.lower_threshold_input.text()))
        self.param_set.upper_threshold = int(str(self.upper_threshold_input.text()))

        self.new_parameters.emit(self.param_set)


class BinaryFrameRateInterpreter(QObject):
    """ Take the output calcualted by an ImageAnalyser and
    Decide which imaging speed to use next."""

    new_interpretation = pyqtSignal(float)
    new_parameters = pyqtSignal(ParameterSet)

    def __init__(self, event_bus:EventBus, gui: bool = True):
        super().__init__()
        self.gui = BinaryFrameRateParameterForm() if gui else None
        self.gui.show()
        self.gui.new_parameters.connect(self.update_parameters)

        self.params = DEFAULT_VALUES
        self.interval = DEFAULT_VALUES.slow_interval

        self.num_fast_frames = 0
        self.min_fast_frames = 4

        # Emitted signals register at event_bus
        self.new_interpretation.connect(event_bus.new_interpretation)
        self.new_parameters.connect(event_bus.new_parameters)

        # Incoming events
        event_bus.new_decision_parameter.connect(self.calculate_interpretation)
        self.new_parameters.emit(self.params)

    @pyqtSlot(object)
    def update_parameters(self, new_params: ParameterSet):
        if self.interval == self.params.slow_interval:
            self.interval = new_params.slow_interval
        elif self.interval == self.params.fast_interval:
            self.interval = new_params.fast_interval
        else:
            self.interval = new_params.slow_interval
        self.params = new_params
        self.new_interpretation.emit(self.interval)
        self.new_parameters.emit(self.params)

    @pyqtSlot(float, float, int)
    def calculate_interpretation(self, new_value: float, _, timepoint: int):
        self.define_imaging_speed(new_value)
        print("DECISION              ", time.perf_counter(), timepoint)

    def define_imaging_speed(self, new_value: float):
        # Only change interval if necessary
        old_interval = self.interval

        if self.interval == self.params.fast_interval:
            if all((new_value < self.params.lower_threshold,
                   self.num_fast_frames >= self.min_fast_frames)):
                self.interval = self.params.slow_interval
        elif self.interval == self.params.slow_interval:
            if new_value > self.params.upper_threshold:
                self.interval = self.params.fast_interval

        # Increase the number of fast_frames if we are in fast mode, else reset
        if self.interval == self.params.fast_interval:
            self.num_fast_frames += 1
        else:
            self.num_fast_frames = 0

        if not self.interval == old_interval:
            self.new_interpretation.emit(self.interval)
