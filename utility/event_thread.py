from xmlrpc.client import boolean
from pycromanager import Bridge
import threading
import re
import zmq
import json
from PyQt5.QtCore import QObject, pyqtSignal, QThread, pyqtSlot
import time
import logging

from utility.data_structures import PyImage

#TODO: decide if this should have the events for the DAQ also.

log = logging.getLogger("EDA")
SOCKET = '5556'

class EventThread(QObject):
    """Thread that receives events from Micro-Manager and relays them to the main program."""

    def __init__(self):
        super().__init__()

        self.bridge = Bridge(debug=False)

        # Make sockets that events circle through to always have a ready socket
        self.event_sockets = []
        self.num_sockets = 5
        for socket in range(self.num_sockets):
            socket_provider = self.bridge.construct_java_object('org.micromanager.Studio',
                                                                new_socket=True)
            self.event_sockets.append(socket_provider._socket)

        # PUB/SUB
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.SUB)
        self.socket.connect("tcp://localhost:5556")
        self.socket.setsockopt(zmq.RCVTIMEO, 1000)  # Timeout for the recv() function

        self.thread_stop = False

        self.topics = ["StandardEvent", "GUIRefreshEvent", "ImageEvent"]
        for topic in self.topics:
            self.socket.setsockopt_string(zmq.SUBSCRIBE, topic)

        self.thread = QThread()
        self.listener = EventListener(self.socket, self.event_sockets, self.bridge, self.thread)
        self.listener.moveToThread(self.thread)
        self.thread.started.connect(self.listener.start)
        self.listener.stop_thread_event.connect(self.stop)
        self.thread.start()

    def stop(self):
        self.thread.exit()
        while self.thread.isRunning():
            time.sleep(0.05)

        print('Closing socket')
        self.socket.close()
        for socket in self.event_sockets:
            socket.close()
        self.context.term()

class EventListener(QObject):
    xy_stage_position_changed_event = pyqtSignal(tuple)
    stage_position_changed_event = pyqtSignal(float)
    acquisition_started_event = pyqtSignal(object)
    acquisition_ended_event = pyqtSignal(object)
    new_image_event = pyqtSignal(PyImage)
    configuration_settings_event = pyqtSignal(str, str, str)
    mda_settings_event = pyqtSignal(object)
    live_mode_event = pyqtSignal(bool)
    stop_thread_event = pyqtSignal()

    def __init__(self, socket, event_sockets, bridge: Bridge, thread: QThread):
        super().__init__()
        self.loop_stop = False
        self.socket = socket
        self.event_sockets = event_sockets
        self.bridge = bridge
        self.thread = thread
        # Record times for events that we receive twice
        self.last_acq_started = time.perf_counter()
        self.last_custom_mda = time.perf_counter()
        self.last_stage_position = time.perf_counter()
        self.blockZ = False
        self.blockImages = False

    pyqtSlot()
    def start(self):
        instance = 0
        while not self.loop_stop:
            instance = instance + 1 if instance < 100 else 0
            try:
                #  Get the reply.
                reply = str(self.socket.recv())
                # topic = re.split(' ', reply)[0][2:]

                message = json.loads(re.split(' ', reply)[1][0:-1])
                socket_num = instance % len(self.event_sockets)
                pre_evt = self.bridge._class_factory.create(message)

                evt = pre_evt(
                    socket=self.event_sockets[socket_num],
                                                            serialized_object=message,
                                                            bridge=self.bridge)

                eventString = message['class'].split(r'.')[-1]
                log.info(eventString)
                # if 'ExposureChangedEvent' in eventString:
                #     print(evt.get_new_exposure_time())
                if 'DefaultAcquisitionStartedEvent' in eventString:
                    if time.perf_counter() - self.last_acq_started > 0.2:
                        self.acquisition_started_event.emit(evt)
                    else:
                        print('SKIPPED')
                    self.last_acq_started = time.perf_counter()
                elif 'DefaultAcquisitionEndedEvent' in eventString:
                    self.acquisition_ended_event.emit(evt)
                # elif 'DefaultStagePositionChangedEvent' in eventString:
                #     if self.blockZ > 0 or time.perf_counter() - self.last_stage_position < 0.05:
                #         print("BLOCKED ", self.blockZ)
                #     else:
                #         self.stage_position_changed_event.emit(evt.get_pos()*100)
                #     self.last_stage_position = time.perf_counter()
                #     self.blockZ = False
                # elif 'XYStagePositionChangedEvent' in eventString:
                #     self.xy_stage_position_changed_event.emit((evt.get_x_pos(), evt.get_y_pos()))
                elif 'DefaultNewImageEvent' in eventString:
                    if self.blockImages:
                        return
                    image = evt.get_image()
                    py_image = PyImage(image.get_raw_pixels().reshape([image.get_width(),
                                                                       image.get_height()]),
                                       image.get_coords().get_t(),
                                       image.get_coords().get_c(),
                                       image.get_coords().get_z(),
                                       image.get_metadata().get_elapsed_time_ms())
                                    #  0) # no elapsed time
                    self.new_image_event.emit(py_image)

                elif 'CustomSettingsEvent' in eventString:
                    self.configuration_settings_event.emit(evt.get_device(), evt.get_property(), evt.get_value())
                # elif 'CustomMDAEvent' in eventString:
                #     if time.perf_counter() - self.last_custom_mda > 0.2:
                #         settings = evt.get_settings()
                #         # print(dir(settings))
                #         settings = MMSettings(java_settings=settings)
                #         self.mda_settings_event.emit(settings)
                #     else:
                #         print('SKIPPED')
                #     self.last_custom_mda = time.perf_counter()

                # elif "DefaultLiveModeEvent" in eventString:
                #     self.blockImages = evt.get_is_on()
                #     self.live_mode_event.emit(self.blockImages)
                    # print("Blocking images in live: ", self.blockImages)
            except zmq.error.Again:
                pass

    pyqtSlot()
    def stop(self):
        # Thread was stopped, let's also close the socket then
        self.loop_stop = True
        self.stop_thread_event.emit()
        while self.thread.isRunning():
            time.sleep(0.05)




def main():
    thread = EventThread()
    while True:
        try:
            time.sleep(0.01)
        except KeyboardInterrupt:
            thread.listener.stop()
            print('Stopping')
            break

if __name__ == '__main__':
    main()