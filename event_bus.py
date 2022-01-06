from PyQt5.QtCore import QEventLoop, QObject, pyqtSignal

from isimgui.EventThread import EventThread
from isimgui.data_structures import PyImage


class EventBus(QObject):

    new_interpretation = pyqtSignal(float)
    acquisition_started_event = pyqtSignal(object)
    acquisition_ended_event = pyqtSignal(object)
    new_image_event = pyqtSignal(PyImage)

    def __init__(self):
        super().__init__()
        self.event_thread = EventThread()
        self.event_thread.start()
        self.studio = self.event_thread.bridge.get_studio()

        self.event_thread.acquisition_started_event.connect(self.acquisition_started_event)
        self.event_thread.acquisition_ended_event.connect(self.acquisition_ended_event)
        self.event_thread.new_image_event.connect(self.new_image_event)