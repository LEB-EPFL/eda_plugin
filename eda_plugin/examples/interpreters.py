from eda_plugin.interpreters.frame_rate import BinaryFrameRateInterpreter
from eda_plugin.utility.event_bus import EventBus

class FrameRateInterpreter(BinaryFrameRateInterpreter):
    def __init__(self, event_bus: EventBus, gui: bool = True):
        super().__init__(event_bus, gui)

    def _define_imaging_speed(self, new_value: float):
        new_interval = new_value * 10
        return new_interval