"""Protocols to avoid direct inheritance."""

from typing import Protocol
from PyQt5.QtCore import pyqtSignal, pyqtSlot
import numpy as np

from utility.data_structures import ParameterSet

# TODO Check if we use this somewhere and think about if we want to redo this.
# class ImageAnalyser(Protocol):
#     """An Image analyser that puts out the events below when it has analysed a new
#     image. This Protocol has to be implemented by the analysers."""

#     new_network_image = pyqtSignal(np.ndarray)
#     new_output_shape = pyqtSignal(tuple)
#     new_decision_parameter = pyqtSignal(float, int)

#     @property
#     def name():
#         ...


# class Interpreter(Protocol):
#     """Interprets the output given from an ImageAnalyser"""

#     new_interpretation = pyqtSignal(float)
#     new_parameters = pyqtSignal(float)

#     @pyqtSlot(float, int)
#     def calculate_interpretation(new_value: float, time: int):
#         ...

#     @pyqtSlot(object)
#     def update_parameters(self, param_form: ParameterSet):
#         ...

#     @property
#     def slow_interval():
#         ...


# class Actuator(Protocol):
#     """Calls some action on the microscope depending on the output from a Interpreter"""

#     new_action = pyqtSignal(object)

#     def call_action(self, parameters):
#         ...


# class ParameterForm(Protocol):
#     """Gives one common form for general EDA parameters used by many EDA implementations."""

#     new_parameters = pyqtSignal(object)

#     def update_parameters(self):
#         ...
