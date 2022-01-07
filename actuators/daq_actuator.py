from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot
import numpy as np



class DAQActuator(QObject):
    """ Deliver new data to the DAQ with the framerate as given by the FrameRateInterpreter."""

    new_daq_data = pyqtSignal(np.ndarray)
    start_acq_signal = pyqtSignal(np.ndarray)

    def __init__(self):
        super().__init__()
        self.state = None

    @pyqtSlot(float)
    def call_action(self, interval):
        print('=== New interval: ', interval)