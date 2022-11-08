"""Actuators for a Zeiss AiryScan running on ZEN 2

Win32Com and clr have to be installed additionally for this to work.
Also change the path to the Zen Software location below.
"""

from qtpy.QtWidgets import QWidget, QVBoxLayout, QPushButton, QApplication, QComboBox, QLabel
from qtpy.QtCore import QThread, QObject, Signal, Slot
from eda_plugin.utility.qt_classes import QWidgetRestore
import win32com.client
from eda_plugin.utility.event_bus import EventBus

import clr
clr.AddReference("C:/Program Files/Carl Zeiss/ZEN 2/ZEN 2 (blue edition)/Zeiss.Micro.Scripting.dll")


class ZenActuator(QObject):
    """Zen based actuator.
    
    Interacts with the ZEN software via the COM interface to run a special version of EDA. This version
    switches between two presets upon a signal from the interpreter. Communication will have to be 
    established in a special way to get images from the software to analyze etc.
    See https://inquisitive-top-fc1.notion.site/KISS-da33af96378d44b08ac44d9f72f7cd84
    """

    stop_acq_signal = Signal()
    start_acq_signal = Signal(object)
    new_mode = Signal(float)

    def __init__(self, event_bus: EventBus):
        """Get information from Zen and set up GUI."""
        super().__init__()

        self.exp_setting_time = 5
        self.move_steps = 5
        self.offset = None
        self.stop = False
        # self.zen = win32com.client.GetActiveObject("Zeiss.Micro.Scripting.ZenWrapperLM")
        self.gui = ZenActuatorGUI()
        self.gui.start_acq.connect(self.start_screen)
        self.gui.new_screen_exp.connect(self.set_screen)
        self.gui.new_image_exp.connect(self.set_image)

        self.event_bus = event_bus
        self.screen = None
        self.image = None
        self.gui.init_exps()

    def start_screen(self):
        self.screen.start()
        #TODO: Maybe this should be done with a signal ideally
        self.event_bus.reset_data.emit()

    def start_image(self):
        self.image.start()
        self.event_bus.reset_data.emit()

    @Slot(str)
    def set_screen(self, experiment_name: str):
        self.screen = ZenAcquisition(experiment_name)
        self.screen.finished.connect(self.start_image)

    @Slot(str)
    def set_image(self, experiment_name: str):
        self.image = ZenAcquisition(experiment_name)
        self.image.finished.connect(self.start_screen)


class ZenAcquisition(QThread):
    """Experiment in Zen that can be started in a second thread."""
    finished = Signal()

    def __init__(self, experiment_name: str):
        super().__init__()
        # self.started.connect(self.run)
        self.experiment_name = experiment_name

    def run(self):
        Zen = win32com.client.GetActiveObject("Zeiss.Micro.Scripting.ZenWrapperLM")
        print(self.experiment_name)
        screen_exp = Zen.Acquisition.Experiments.GetByname(self.experiment_name)
        screen_exp.SetActive()
        Zen.Acquisition.Run(screen_exp)
        self.finished.emit()


class ZenActuatorGUI(QWidgetRestore):
    """GUI to choose the presets to switch between."""
    start_acq = Signal()
    stop_acq = Signal()
    new_screen_exp = Signal(str)
    new_image_exp = Signal(str)

    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.start_button = QPushButton("Start")
        self.start_button.clicked.connect(self.start)
        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop)

        self.layout.addWidget(self.start_button)
        self.layout.addWidget(self.stop_button)

        self.screen_label = QLabel("Screen")
        self.screen_select = QComboBox()
        self.screen_select.currentTextChanged.connect(self.new_screen_exp)
        #TODO: Make this search for experiments in Zen at some point. Set defaults for now.
        self.screen_select.addItem('smart_screen')
        
        self.image_label = QLabel("Image")
        self.image_select = QComboBox()
        self.image_select.currentTextChanged.connect(self.new_image_exp)
        self.image_select.addItem('smart_imaging')
                
        self.layout.addWidget(self.screen_label)
        self.layout.addWidget(self.screen_select)
        self.layout.addWidget(self.image_label)
        self.layout.addWidget(self.image_select)

    def start(self):
        self.start_acq.emit()

    def stop(self):
        self.stop_acq.emit()

    def init_exps(self):
        self.new_screen_exp.emit('smart_screen')
        self.new_image_exp.emit('smart_imaging')
