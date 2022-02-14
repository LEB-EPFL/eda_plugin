"""Interpreters and corresponding GUIs for frame rate modification.

BinaryFrame rate interpreter that receives information from an analyser and computes the decision
about which frame rate to use for further imaging. This information is sent on the the actuator to
modify furhter imaging.
"""

import logging

from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot
from PyQt5 import QtWidgets
import qdarkstyle

from eda_plugin.utility.data_structures import ParameterSet
from eda_plugin.utility.event_bus import EventBus
from eda_plugin.utility.qt_classes import QWidgetRestore
from eda_plugin.utility import settings

log = logging.getLogger("EDA")


class BinaryFrameRateInterpreter(QObject):
    """Take the output calcualted by an ImageAnalyser and decide which imaging speed to use next."""

    new_interpretation = pyqtSignal(float)
    new_parameters = pyqtSignal(ParameterSet)

    def __init__(self, event_bus: EventBus, gui: bool = True):
        """Load the default values, start the GUI and connect the events."""
        super().__init__()
        self.gui = BinaryFrameRateParameterForm() if gui else None
        self.gui.show()
        self.gui.new_parameters.connect(self.update_parameters)

        self.params = ParameterSet(settings.get_settings(self))
        self.interval = self.params.slow_interval

        self.num_fast_frames = 0
        self.min_fast_frames = 4

        # Emitted signals register at event_bus
        self.new_interpretation.connect(event_bus.new_interpretation)
        self.new_parameters.connect(event_bus.new_parameters)

        # Incoming events
        event_bus.new_decision_parameter.connect(self.calculate_interpretation)
        self.new_parameters.emit(self.params)
        self.new_interpretation.emit(self.interval)

    @pyqtSlot(object)
    def update_parameters(self, new_params: ParameterSet):
        """Update the settings with the new parameters received from the GUI."""
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
        """Calculate the new interval. Emit if changed and increase/reset the fast image counter."""
        old_interval = self.interval
        self.interval = self._define_imaging_speed(new_value)
        if not self.interval == old_interval:
            self.new_interpretation.emit(self.interval)

        self._set_fast_count()
        log.info(f"timepoint {timepoint} decision: {new_value}")

    def _define_imaging_speed(self, new_value: float):
        new_interval = self.interval
        # Only change interval if necessary
        if self.interval == self.params.fast_interval:
            if all(
                (
                    new_value < self.params.lower_threshold,
                    self.num_fast_frames >= self.min_fast_frames,
                )
            ):
                new_interval = self.params.slow_interval
        elif self.interval == self.params.slow_interval:
            if new_value > self.params.upper_threshold:
                new_interval = self.params.fast_interval

        return new_interval

    def _set_fast_count(self):
        # Increase the number of fast_frames if we are in fast mode, else reset
        if self.interval == self.params.fast_interval:
            self.num_fast_frames += 1
        else:
            self.num_fast_frames = 0


class FrameRateInterpreter(BinaryFrameRateInterpreter):
    def __init__(self, event_bus: EventBus, gui: bool = True):
        super().__init__(event_bus, gui)

    def _define_imaging_speed(self, new_value: float):
        new_interval = new_value * 10
        return new_interval


class BinaryFrameRateParameterForm(QWidgetRestore):
    """GUI for input/update of the parameters used for a change between two frame rates."""

    new_parameters = pyqtSignal(object)

    def __init__(self):
        """Set up the PyQt GUI with all the parameters needed for interpretation."""
        super().__init__()

        self.slow_interval_input = QtWidgets.QLineEdit()
        self.fast_interval_input = QtWidgets.QLineEdit()
        self.lower_threshold_input = QtWidgets.QLineEdit()
        self.upper_threshold_input = QtWidgets.QLineEdit()

        self.slow_interval_input.setMaximumWidth(50)
        self.fast_interval_input.setMaximumWidth(50)
        self.lower_threshold_input.setMaximumWidth(50)
        self.upper_threshold_input.setMaximumWidth(50)

        DEFAULT_VALUES = settings.get_settings(self)
        self.slow_interval_input.setText(str(DEFAULT_VALUES["slow_interval"]))
        self.fast_interval_input.setText(str(DEFAULT_VALUES["fast_interval"]))
        self.lower_threshold_input.setText(str(DEFAULT_VALUES["lower_threshold"]))
        self.upper_threshold_input.setText(str(DEFAULT_VALUES["upper_threshold"]))

        self.slow_interval_input.editingFinished.connect(self._update_parameters)
        self.fast_interval_input.editingFinished.connect(self._update_parameters)
        self.lower_threshold_input.editingFinished.connect(self._update_parameters)
        self.upper_threshold_input.editingFinished.connect(self._update_parameters)

        param_layout = QtWidgets.QFormLayout(self)
        param_layout.addRow("Slow Interval [s]", self.slow_interval_input)
        param_layout.addRow("Fast Interval [s]", self.fast_interval_input)
        param_layout.addRow("Lower Threshold", self.lower_threshold_input)
        param_layout.addRow("Upper Threshold", self.upper_threshold_input)

        self.setStyleSheet(qdarkstyle.load_stylesheet(qt_api="pyqt5"))
        self.param_set = ParameterSet(**DEFAULT_VALUES)

    def _update_parameters(self):
        self.param_set.slow_interval = float(str(self.slow_interval_input.text()))
        self.param_set.fast_interval = float(str(self.fast_interval_input.text()))
        self.param_set.lower_threshold = float(str(self.lower_threshold_input.text()))
        self.param_set.upper_threshold = float(str(self.upper_threshold_input.text()))

        self.new_parameters.emit(self.param_set)
