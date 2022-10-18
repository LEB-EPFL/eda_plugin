from collections import defaultdict, OrderedDict
import logging
from typing import Union

from qtpy import QtCore, QtWidgets
import qdarkstyle
from eda_plugin.utility.qt_classes import QWidgetRestore

from eda_plugin.utility.event_bus import EventBus

log = logging.getLogger("EDA")


class PresetsInterpreter(QtCore.QObject):
    """Take the output calcualted by an ImageAnalyser and decide which imaging speed to use next."""

    new_interpretation = QtCore.Signal(float)
    new_parameters = QtCore.Signal(dict)

    def __init__(self, event_bus: EventBus, gui: bool = True):
        """Load the default values, start the GUI and connect the events."""
        super().__init__()
        self.gui = ParameterForm("PresetsInterpreter") if gui else None
        if gui:
            self.gui.new_parameters.connect(self.update_parameters)
            self.params = self.gui.params
        else:
            self.params = {}

        # To keep the paramater sent numerical, 0: screen, 1:image
        self.mode = 0
        # self.num_fast_frames = 0

        # Emitted signals register at event_bus
        self.new_interpretation.connect(event_bus.new_interpretation)
        self.new_parameters.connect(event_bus.new_parameters)

        # Incoming events
        event_bus.new_decision_parameter.connect(self.calculate_interpretation)
        self.new_parameters.emit(self.params)
        self.new_interpretation.emit(self.mode)

    @QtCore.Slot(object)
    def update_parameters(self, new_params):
        """Update the settings with the new parameters received from the GUI."""
        self.params = new_params
        self.new_interpretation.emit(self.mode)
        self.new_parameters.emit(self.params)

    @QtCore.Slot(float, float, int)
    def calculate_interpretation(self, new_value: float, _, timepoint: int):
        """Calculate the new interval. Emit if changed and increase/reset the fast image counter."""
        old_mode = self.mode
        self.mode = self._define_mode(new_value)
        if not self.mode == old_mode:
            self.new_interpretation.emit(self.mode)

        self._set_fast_count()
        log.info(f"timepoint {timepoint} decision: {new_value} -> {self.mode} interval")

    def _define_mode(self, new_value: float):
        new_mode = self.mode
        # Only change interval if necessary
        if self.mode == 1:
            if all(
                (
                    new_value < self.params['lower_threshold'],
                    self.num_fast_frames >= self.params['min_image_frames'],
                )
            ):
                new_mode = 0
        elif self.mode == 0:
            if new_value > self.params['upper_threshold']:
                new_mode= 1

        return new_mode

    def _set_fast_count(self):
        # Increase the number of fast_frames if we are in fast mode, else reset
        if self.mode == 1:
            self.num_fast_frames += 1
        else:
            self.num_fast_frames = 0


class ParameterForm(QWidgetRestore):
    """GUI for input/update of the parameters used for a change between two frame rates."""

    new_parameters = QtCore.Signal(object)

    def __init__(self,  form_name: str, params: Union[dict, None] = None):
        """Set up the PyQt GUI with all the parameters needed for interpretation."""
        super().__init__()

        # Load previous settings if available
        self.form_name = form_name
        self.settings = QtCore.QSettings("EDA", "Interpreter")
        if params is None:
            self.params = self.settings.value(form_name, {})
            print(self.params)
        else:
            self.params = OrderedDict(params)

        # Build the form for this dictionary of values
        self.rows = defaultdict(lambda: defaultdict(str))
        param_layout = QtWidgets.QFormLayout(self)

        for idx, (key, value) in enumerate(self.params.items()):
            self.rows[idx]['name'] = key
            self.rows[idx]['input'] = QtWidgets.QLineEdit()
            self.rows[idx]['input'].setText(str(value))
            self.rows[idx]['input'].setMaximumWidth(50)
            param_layout.addRow(key, self.rows[idx]['input'])
            self.rows[idx]['input'].editingFinished.connect(self._update_parameters)

        self.new_parameters.emit(self.params)
        # self.setStyleSheet(qdarkstyle.load_stylesheet(qt_api="pyqt5"))

    def closeEvent(self, e):
        self.settings.setValue(self.form_name, self.params)
        super().closeEvent(e)

    def _update_parameters(self):
        for idx in self.rows.keys():
            self.params[self.rows[idx]['name']] = float(self.rows[idx]['input'].text())
        self.new_parameters.emit(self.params)



if __name__ == "__main__":
    import sys

    app = QtWidgets.QApplication(sys.argv)
    # event_bus = EventBus()
    my_params = {'upper_threshold': 0.9,
                 'lower_threshold': 0.7,
                 'min_image_frames': 30}
    gui = ParameterForm('presets_interpreter', None)

    gui.show()
    # actuator.gui.show()
    sys.exit(app.exec_())