"""Actuators for a Zeiss AiryScan running on ZEN 2

Win32Com and clr have to be installed additionally for this to work.
Also change the path to the Zen Software location below.
"""

from qtpy.QtWidgets import QWidget, QVBoxLayout, QPushButton, QApplication, QComboBox, QLabel
from qtpy.QtCore import QThread, QObject, Signal, Slot
from eda_plugin.utility.qt_classes import QWidgetRestore
import win32com.client
from eda_plugin.utility.event_bus import EventBus
import pythoncom
import pyautogui
import pywinauto
import time
import re

from pymm_eventserver.data_structures import MMSettings, EDAEvent

import logging
import clr
clr.AddReference("C:/Program Files/Carl Zeiss/ZEN 2/ZEN 2 (blue edition)/Zeiss.Micro.Scripting.dll")
log = logging.getLogger("EDA")

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
        self.event_bus.new_interpretation.connect(self.call_action)
        self.event_bus.new_decision_parameter.connect(self.collect_position)

        self.screen = None
        self.image = None
        self.mode = 0  # screen, 1: image
        self.last_offset = (0, 0)
        self.gui.init_exps()
        pythoncom.CoInitialize()
        self.zen = win32com.client.GetActiveObject("Zeiss.Micro.Scripting.ZenWrapperLM")

    def start_screen(self):
        self.move_stage(self.last_offset)
        settings = MMSettings(n_channels=1, n_slices=1)
        self.event_bus.mda_settings_event.emit(settings)
        self.mode = 0
        self.event_bus.acquisition_started_event.emit(settings)
        print("---START SCREEN")
        self.screen.start()
        self.event_bus.reset_data.emit()

    def start_image(self, position):
        self.move_stage(position)
        settings = MMSettings(n_channels=4, n_slices=1)
        self.event_bus.mda_settings_event.emit(settings)
        self.mode = 1
        self.event_bus.acquisition_started_event.emit(settings)
        print("---START IMAGE")
        self.image.start()
        self.event_bus.reset_data.emit()

    @Slot(str)
    def set_screen(self, experiment_name: str):
        self.screen = ZenAcquisition(experiment_name, self.event_bus)
        self.screen_name = experiment_name
        time.sleep(1)
        # self.screen.finished.connect(self.start_image)

    @Slot(str)
    def set_image(self, experiment_name: str):
        self.image = ZenAcquisition(experiment_name, self.event_bus)
        self.image_name = experiment_name
        self.image.finished.connect(self.start_screen)
        time.sleep(1)

    @Slot(float)
    def call_action(self, mode: float):
        if mode == self.mode:
            log.warning(f"Already in mode {self.mode}")
            return
        log.info(f"New event, mode: {mode}")
        self.stop_acquisition()
        if mode == 0:
            self.image.finished.disconnect(self.start_screen)
            self.mode = 0
            self.set_screen(self.screen_name)
            self.start_screen()
        elif mode == 1:
            self.mode = 1
            offset = self.pixel_to_micron(self.pos)
            go_to = offset
            self.last_offset = (-offset[0], -offset[1])
            self.set_image(self.image_name)
            self.start_image(go_to)
        else:
            log.warning(f"Binary actuator, {mode} mode not recognized")

    # @Slot(float, float, int, tuple)
    def collect_position(self, evt:EDAEvent):
        self.pos = evt.position

    def stop_acquisition(self):
        t1 = time.perf_counter()
        # app = pywinauto.application.Application(backend="uia").connect(title_re=r".*ZEN.*", top_level_only=True)
        # print(f" Time to locate window: {time.perf_counter()-t1}")
        # window = app.top_window()
        # print(f" Time to choose top_window: {time.perf_counter()-t1}")
        # window.set_focus()
        # time.sleep(0.2)
        # Find the button, click it and move the mouse back.
        loc = pyautogui.locateOnScreen('stop_button.png', grayscale=False, confidence=.5)
        original_pos = pyautogui.position()
        pyautogui.click(loc.left + loc.width/2, loc.top + loc.height/2)
        pyautogui.moveTo(original_pos[0], original_pos[1])
        # Let other parts of the plugin know that acquisition has ended
        self.event_bus.acquisition_ended_event.emit(None)
        print(f" Time to press stop button: {time.perf_counter()-t1}")
        time.sleep(3)

    def move_stage(self, offset, steps=10):
        #TODO: steps + sleep -> speed
        print("OFFSET", offset)
        if max(offset) == 0:
            return
        stage = self.zen.Devices.Stage
        start_position = (stage.ActualPositionX, stage.ActualPositionY)
        for i in range(steps):
            print("Moving Stage...")
            stage.moveTo(start_position[0] + (i+1)*offset[0]/steps, 
                        start_position[1] + (i+1)*offset[1]/steps)
            time.sleep(0.5)
        print("Stage in Position")

    def extract_pixel_size(self, meta_string: str):
        """Get pixel size from czi metadata."""
        pattern = re.compile('X=(\d.\d*).*Y=(\d.\d*).*')
        match = pattern.match(meta_string)
        return float(match.group(1)), float(match.group(2))

    def pixel_to_micron(self, offset):
        meta = self.zen.Application.Documents.Item(self.zen.Application.Documents.Count - 1).Metadata
        calib = self.extract_pixel_size(str(meta.ScalingMicron))
        return (offset[0]*calib[0], offset[1]*calib[1])

class ZenAcquisition(QThread):
    """Experiment in Zen that can be started in a second thread."""
    finished = Signal()

    def __init__(self, experiment_name: str, event_bus):
        super().__init__()
        # self.started.connect(self.run)
        self.experiment_name = experiment_name
        self.event_bus = event_bus

    def run(self):
        pythoncom.CoInitialize()
        self.zen = win32com.client.GetActiveObject("Zeiss.Micro.Scripting.ZenWrapperLM")
        print(self.experiment_name)
        screen_exp = self.zen.Acquisition.Experiments.GetByname(self.experiment_name)
        screen_exp.SetActive()
        self.zen.Acquisition.Run(screen_exp)
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

    def closeEvent(self, e):
        pythoncom.CoUninitialize()
        super().closeEvent(e)
