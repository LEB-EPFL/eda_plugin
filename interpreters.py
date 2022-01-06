
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot
from data_structures import ParameterSet
import time
from protocols import ParameterForm
from event_bus import EventBus

class BinaryFrameRateInterpreter(QObject):
    """ Take the output calcualted by an ImageAnalyser and
    Decide which imaging speed to use next."""

    new_interpretation = pyqtSignal(float)
    new_parameters = pyqtSignal(ParameterSet)

    def __init__(self, param_form: ParameterForm, event_bus:EventBus):
        super().__init__()
        self.param_form = param_form
        self.param_form.new_parameters.connect(self.update_parameters)

        self.interval = 5
        self.params = ParameterSet(slow_interval=5,
                                   fast_interval=0,
                                   lower_threshold=80,
                                   upper_threshold=100)
        self.num_fast_frames = 0
        self.min_fast_frames = 4

        # Connect event bus
        self.new_interpretation.connect(event_bus.new_interpretation)


    @pyqtSlot(object)
    def update_parameters(self, params: ParameterSet):
        if self.interval == self.params.fast_interval:
            self.interval = params.fast_interval
        else:
            self.interval = params.slow_interval
        self.params = params
        self.new_interpretation.emit(self.interval)
        self.new_parameters.emit(self.params)

    @pyqtSlot(float, int)
    def calculate_interpretation(self, new_value: float, _: int):
        self.define_imaging_speed(new_value)

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
        print("DECISION              ", time.perf_counter())
