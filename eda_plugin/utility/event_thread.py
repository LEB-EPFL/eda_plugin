"""ZMQ based communication to Micro-Manager via the PythonEventServer plugin.

Based on Pycromanager (https://github.com/micro-manager/pycro-manager) to facilitate receiving
events that are emitted by the different parts of Micro-Manager for GUI inputs and during
acquisition. Used with some ImageAnalysers to receive images and to react to starting and ending
acquisitions.
"""

import json
import logging
import re
import time

import zmq
from pycromanager import Bridge
from PyQt5.QtCore import QObject, QThread, pyqtSignal, pyqtSlot

from eda_plugin.utility.data_structures import MMSettings

from .data_structures import PyImage

log = logging.getLogger("EDA")
SOCKET = "5556"


class EventThread(QObject):
    """Thread that receives events from Micro-Manager and relays them to the main program.

    See https://github.com/wl-stepp/micro-manager-isim -> PythonEventServer for the other side of
    the communication.
    """

    def __init__(self):
        """Set up the bridge to Micro-Manager, ZMQ sockets and the main listener Thread."""
        super().__init__()

        self.bridge = Bridge(debug=False)

        # Make sockets that events circle through to always have a ready socket
        self.event_sockets = []
        self.num_sockets = 5
        for socket in range(self.num_sockets):
            socket_provider = self.bridge.construct_java_object(
                "org.micromanager.Studio", new_socket=True
            )
            self.event_sockets.append(socket_provider._socket)

        # PUB/SUB implementation of ZMQ
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.SUB)
        self.socket.connect("tcp://localhost:" + SOCKET)
        self.socket.setsockopt(zmq.RCVTIMEO, 1000)  # Timeout for the recv() function

        self.thread_stop = False

        self.topics = ["StandardEvent", "GUIRefreshEvent", "ImageEvent"]
        for topic in self.topics:
            self.socket.setsockopt_string(zmq.SUBSCRIBE, topic)

        # Set up the main listener Thread
        self.thread = QThread()
        self.listener = EventListener(
            self.socket, self.event_sockets, self.bridge, self.thread
        )
        self.listener.moveToThread(self.thread)
        self.thread.started.connect(self.listener.start)
        self.listener.stop_thread_event.connect(self.stop)
        self.thread.start()

    def stop(self):
        """Close the QThread and the zmq sockets."""
        self.thread.exit()
        while self.thread.isRunning():
            time.sleep(0.05)

        log.info("Closing zmq socket")
        self.socket.close()
        for socket in self.event_sockets:
            socket.close()
        self.context.term()


class EventListener(QObject):
    """Loop running in a QThread that listens to events published on the spcified zmq sockets.

    There are additional events that could be listened to. Many can be found here:
    https://valelab4.ucsf.edu/~MM/doc-2.0.0-gamma/mmstudio/org/micromanager/events/package-summary.html
    But also in the index.
    """

    acquisition_started_event = pyqtSignal(object)
    acquisition_ended_event = pyqtSignal(object)
    new_image_event = pyqtSignal(PyImage)
    configuration_settings_event = pyqtSignal(str, str, str)
    stop_thread_event = pyqtSignal()
    mda_settings_event = pyqtSignal(MMSettings)

    def __init__(self, socket, event_sockets, bridge: Bridge, thread: QThread):
        """Store passed arguments and starting time for frequency limitation of certain events."""
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

    @pyqtSlot()
    def start(self):
        """Listen on the zmq socket.

        This receives the events on the socket and translates them to the event as a python shadow
        of the java object. Using pycromanager, the relevant data can be pulled over to python. This
        is done depending on which event was originally sent from Java. PyQtSignals are then emitted
        with the data. Normally the EventBus will subscribe to these events to pass them on to the
        parts of the EDA loop.
        """
        instance = 0
        while not self.loop_stop:
            instance = instance + 1 if instance < 100 else 0
            try:
                #  Get the reply.
                reply = str(self.socket.recv())
                # topic = re.split(' ', reply)[0][2:]

                # Translate the event to a shadow object
                message = json.loads(re.split(" ", reply)[1][0:-1])
                socket_num = instance % len(self.event_sockets)
                pre_evt = self.bridge._class_factory.create(message)

                evt = pre_evt(
                    socket=self.event_sockets[socket_num],
                    serialized_object=message,
                    bridge=self.bridge,
                )

                eventString = message["class"].split(r".")[-1]
                log.info(eventString)
                if "DefaultAcquisitionStartedEvent" in eventString:
                    if time.perf_counter() - self.last_acq_started > 0.2:
                        self.acquisition_started_event.emit(evt)
                    else:
                        print("SKIPPED")
                    self.last_acq_started = time.perf_counter()
                elif "DefaultAcquisitionEndedEvent" in eventString:
                    self.acquisition_ended_event.emit(evt)
                elif "DefaultNewImageEvent" in eventString:
                    if self.blockImages:
                        return
                    image = evt.get_image()
                    py_image = PyImage(
                        image.get_raw_pixels().reshape(
                            [image.get_width(), image.get_height()]
                        ),
                        image.get_coords().get_t(),
                        image.get_coords().get_c(),
                        image.get_coords().get_z(),
                        image.get_metadata().get_elapsed_time_ms(),
                    )
                    #  0) # no elapsed time
                    self.new_image_event.emit(py_image)

                elif "CustomSettingsEvent" in eventString:
                    self.configuration_settings_event.emit(
                        evt.get_device(), evt.get_property(), evt.get_value()
                    )
                elif "CustomMDAEvent" in eventString:
                    if time.perf_counter() - self.last_custom_mda > 0.2:
                        settings = evt.get_settings()
                        settings = MMSettings(java_settings=settings)
                        self.mda_settings_event.emit(settings)
                    self.last_custom_mda = time.perf_counter()

            except zmq.error.Again:
                pass

    @pyqtSlot()
    def stop(self):
        """Thread was stopped, let's also close the socket then."""
        self.loop_stop = True
        self.stop_thread_event.emit()
        while self.thread.isRunning():
            time.sleep(0.05)


def main():
    """Start an EventThread, can be used to test PythonEventServer plugin from Micro-Manager."""
    thread = EventThread()
    while True:
        try:
            time.sleep(0.01)
        except KeyboardInterrupt:
            thread.listener.stop()
            print("Stopping")
            break


if __name__ == "__main__":
    main()
