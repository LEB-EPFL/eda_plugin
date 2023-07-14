from PyQt5.QtCore import QObject, pyqtSlot
from eda_plugin.utility.event_bus import EventBus


class ContrastSwitcher(QObject):

    def __init__(self, event_bus: EventBus = None):
        super().__init__()
        self.core = event_bus.event_thread.listener.core

        self.interval = 2
        event_bus.new_interpretation.connect(self.call_action)
        # Connect to event new_acquisition_started to a function
        event_bus.acquisition_started_event.connect(self.reset)
        # Check in event_bus

    def reset(self):
        # set interval
        self.interval = 2
        # set to Brightfield contrast
        print("============================== RESET")



    @pyqtSlot(float)
    def call_action(self, new_interval):
        old_interval = self.interval
        if new_interval != old_interval:
            if new_interval == 0:
                print("============================== TAKE ACTION")
                self.core.set_property("CSUW1-Filter Wheel 2", "Label", "Cy3")
                self.core.set_property("DA TTL State Device", "State", 4)
                self.interval = new_interval

            else:
                print("============================== ChangedContrast")
                self.core.set_property("CSUW1-Filter Wheel 2", "Label", "GFP")
                self.core.set_property("DA TTL State Device", "State", 2)
                self.interval = new_interval
                
                
