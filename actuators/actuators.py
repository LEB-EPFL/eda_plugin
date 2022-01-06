import threading
from PyQt5.QtCore import QObject, QThread, pyqtSignal, pyqtSlot
import numpy as np

import pycromanager


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



class PycroAcquisition(QThread):
    """ This tries to use the inbuilt Acquisition function in pycromanager. Unfortunately, these
    acquisitions don't start with the default Micro-Manager interface and the acquisition also
    doesn't seem to be saved in a perfect format, so that Micro-Manager would detect the correct
    parameters to show the channels upon loading for example. The Acquisitions also don't emit any
    of the standard Micro-Manager events. Stashed for now because of this"""
    new_image = pyqtSignal(object)
    acquisition_ended = pyqtSignal()
    def __init__(self, actuator: MMActuator):
        super().__init__()
        self.studio = actuator.studio
        self.acquisition = pycromanager.Acquisition(directory='C:/Users/stepp/Desktop/eda_save', name='acquisition_name')
        self.events = pycromanager.multi_d_acquisition_events(
                                    num_time_points=100, time_interval_s=0.5,
                                    channel_group='Channel', channels=['DAPI', 'FITC'],
                                    order='ct')
        self.sleeper = threading.Event()  # Might actually not be needed here

    def start_acq(self):
        self.acquire()

    def acquire(self):
        self.acquisition.acquire(self.events)

    def send_image(self):

        self.new_image.emit()






# Do this instead as it gives events and all the rest
# Does still give some errors when done by hand but maybe works otherwise
# The datastore should also be available from a AcquisitionStartedEvent
# Could also be adjusted with the AcquisitionButtonHijack Plugin to adjust the delayu
# self.datastore = self.studio.acquisitions().run_acquisition_nonblocking()
# self.pipeline = self.studio.data().copy_application_pipeline(self.datastore, False)
# self.datastore.set_storage(self.bridge.construct_java_object('org.micromanager.data.internal.
# StorageRAM', args=[self.datastore]))
# self.pipeline.insert_image(image)
