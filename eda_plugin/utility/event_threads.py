from qtpy.QtCore import QThread, Signal, Slot, QObject
from qtpy.QtWidgets import QApplication
import numpy as np
import time
import re
from pymm_eventserver.data_structures import PyImage


import win32com.client
import clr
import logging

clr.AddReference("C:/Program Files/Carl Zeiss/ZEN 2/ZEN 2 (blue edition)/Zeiss.Micro.Scripting.dll")
log = logging.getLogger("EDA")

class ZenEventThread(QObject):
    """Class to host a ZenEventListener and have it run in a separate thread."""

    def __init__(self, event_bus, topics = None):
        super().__init__()
        self.last_document = -1
        self.start_new_thread()

        self.event_bus = event_bus
        self.event_bus.reset_data.connect(self.reset_listener)

    def reset_listener(self):
        self.listener.loop_stop = True
        self.stop()
        self.start_new_thread()

    def start_new_thread(self):
        self.thread = QThread()
        self.listener = ZenEventListener(self.thread, self.last_document)
        self.listener.moveToThread(self.thread)
        self.thread.started.connect(self.listener.run)
        self.listener.stop_thread_event.connect(self.stop)
        self.listener.document_detected.connect(self.set_last_document)
        self.thread.start()

    def set_last_document(self, last_document: int):
        self.last_document = last_document

    def stop(self):
        self.thread.exit()
        while self.thread.isRunning():
            time.sleep(0.05)     

class ZenEventListener(QObject):
    """An event thread that gets information and images from the Zeiss Zen software"""
    new_image_event = Signal(PyImage)
    document_detected = Signal(int)
    stop_thread_event = Signal()

    def __init__(self, thread: QThread, last_document: int):
        super().__init__()
        self.zen = win32com.client.GetActiveObject("Zeiss.Micro.Scripting.ZenWrapperLM")
        self.loop_stop = False
        self.last_document = last_document
        self.thread = thread

    def run(self):
        self.loop_stop = False
        self.zen = win32com.client.GetActiveObject("Zeiss.Micro.Scripting.ZenWrapperLM")

        # Wait for the new experiment to have started in Zen
        extra_wait = False
        while self.zen.Application.Documents.Count - 1 == self.last_document:
            print("waiting for experiment to start")
            extra_wait = True
            time.sleep(0.5)
        if extra_wait:
            time.sleep(2)
        self.last_document = self.zen.Application.Documents.Count - 1
        self.document_detected.emit(self.last_document)

        self.data = self.zen.Application.Documents.Item(self.last_document)
        last_time_count = -1
        while not self.loop_stop:
            time.sleep(0.1)
            meta = self.data.Metadata
            # Check if there is new data in Zen
            if int(meta.TimeSeriesCount) == last_time_count:
                continue
            last_time_count = int(meta.TimeSeriesCount)
            print(f"Timepoint {last_time_count}")
            # Get the data
            data_clone = self.data.Clone()
            time_re = "\d* Frames \((\d*.\d*) s\)"
            time_search = re.search(time_re, meta.TimeSeriesInfo, re.IGNORECASE)
            if time_search is not None:
                time_ms = int(float(time_search.group(1))*1000)
            else:
                log.warning("No time found, setting 0")
                time_ms = None

            subsetString = "T(" + str(int(meta.TimeSeriesCount)) +")" #+ "|C(2)"
            pixels = data_clone.CopyPixelsToArray(subsetString, meta.PixelType)
            #TODO: not set up for z_stacks yet
            image_array = np.reshape(np.asarray(pixels), [int(meta.ChannelCount)] + [int(np.sqrt(pixels.shape[0]//int(meta.ChannelCount)))]*2)
            for channel in range(image_array.shape[0]):
                # print(f"Channel {channel}")
                py_image = PyImage(image_array[channel], int(last_time_count) - 1, channel, 0, time_ms)
                self.new_image_event.emit(py_image)

    @Slot()
    def stop(self):
        """Thread was stopped, let's also close the socket then."""
        self.loop_stop = True
        self.stop_thread_event.emit()
        while self.thread.isRunning():
            time.sleep(0.05)


if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    zen_event_thread = ZenEventThread()
    sys.exit(app.exec_())