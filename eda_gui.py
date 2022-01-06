from typing import List, Tuple, Protocol
from PyQt5 import QtWidgets, QtCore, QtGui
import pyqtgraph as pg
import numpy as np
from pyqtgraph.graphicsItems.PlotCurveItem import PlotCurveItem
from qimage2ndarray import gray2qimage
from data_structures import ParameterSet
from protocols import ImageAnalyser, Interpreter, Actuator
from event_bus import EventBus

# Adjust for different screen sizes
QtWidgets.QApplication.setAttribute(QtCore.Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)


class EDAMainGUI(QtWidgets.QWidget):

    def __init__(self, analyzer: ImageAnalyser, interpreter: Interpreter, actuator_gui: QtWidgets.QWidget):
        super().__init__()
        self.setWindowTitle(analyzer.name)
        self.analyzer = analyzer
        self.interpreter = interpreter
        self.viewer = NetworkImageViewer()
        self.plot = EDAPlot()

        self.setLayout(QtWidgets.QGridLayout())
        self.layout().addWidget(self.viewer, 0, 0)
        self.layout().addWidget(self.plot,1, 0)
        self.setStyleSheet("background-color:black;")

        self.actuator_gui = actuator_gui
        self.actuator_gui.show()

        # Establish communication between the different parts
        self.analyzer.new_output_shape.connect(self.viewer.reset_scene_rect)
        self.analyzer.new_output_shape.connect(self.plot.reset_plot)
        self.analyzer.new_network_image.connect(self.viewer.set_qimage)
        self.analyzer.new_decision_parameter.connect(self.plot.add_datapoint)

        self.analyzer.new_decision_parameter.connect(self.interpreter.calculate_interpretation)
        # self.interpreter.new_interpretation.connect(self.actuator.call_action)
        self.interpreter.new_parameters.connect(self.plot.set_thr_lines)

    def closeEvent(self, event):
        app = QtGui.QApplication.instance()
        app.closeAllWindows()
        event.accept()

class EDAPlot(pg.PlotWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.output_line = PlotCurveItem([], pen='w')
        self.output_scatter = pg.ScatterPlotItem([], symbol='o', pen=None)

        self.thresholds = [80, 100]
        pen = pg.mkPen(color='#FF0000', style=QtCore.Qt.DashLine)
        self.thrLine1 = pg.InfiniteLine(
            pos=80, angle=0, pen=pen)
        self.thrLine2 = pg.InfiniteLine(
            pos=100, angle=0, pen=pen)
        self.addItem(self.thrLine1)
        self.addItem(self.thrLine2)
        self.addItem(self.output_line)
        self.addItem(self.output_scatter)
        self.enableAutoRange()
        pg.setConfigOptions(antialias=True)

        self.x_data = []
        self.y_data = []

    def add_datapoint(self, y: float, x: int):
        self.x_data.append(x)
        self.y_data.append(y)
        self.refresh_plot()

    def refresh_plot(self):
        self.output_line.setData(self.x_data, self.y_data)
        self.output_scatter.setData(self.x_data, self.y_data)
        self.enableAutoRange()

    def reset_plot(self):
        self.x_data = [self.x_data[-1]]
        self.y_data = [self.y_data[-1]]
        self.refresh_plot()

    QtCore.pyqtSlot(ParameterSet)
    def set_thr_lines(self, params: ParameterSet):
        self.thrLine1.setPos(params.lower_threshold)
        self.thrLine2.setPos(params.upper_threshold)


class NetworkImageViewer(QtWidgets.QGraphicsView):
    def __init__(self):
        super(NetworkImageViewer, self).__init__(QtWidgets.QGraphicsScene())
        self.pixmap = QtGui.QPixmap(512, 512)
        self.setSceneRect(0, 0, 512, 512)
        self.image = self.scene().addPixmap(self.pixmap)

    def reset_scene_rect(self, shape: Tuple):
        self.setSceneRect(0, 0, *shape)
        self.fitInView(0, 0, *shape, mode=QtCore.Qt.KeepAspectRatio)
        self.setBackgroundBrush(QtGui.QColor('#222222'))

    def set_qimage(self, image: np.ndarray):
        image = gray2qimage(np.multiply(image, 6))
        self.image.setPixmap(QtGui.QPixmap.fromImage(image))
        self.update()


class EDAParameterForm(QtWidgets.QWidget):
    new_parameters = QtCore.pyqtSignal(object)

    def __init__(self):
        super().__init__()

        self.slow_interval_input = QtWidgets.QLineEdit()
        self.fast_interval_input = QtWidgets.QLineEdit()
        self.lower_threshold_input = QtWidgets.QLineEdit()
        self.upper_threshold_input = QtWidgets.QLineEdit()

        self.slow_interval_input.setMaximumWidth(50)
        self.fast_interval_input.setMaximumWidth(50)
        self.lower_threshold_input.setMaximumWidth(50)
        self.upper_threshold_input.setMaximumWidth(50)

        self.slow_interval_input.setText('5')
        self.fast_interval_input.setText('0')
        self.lower_threshold_input.setText('80')
        self.upper_threshold_input.setText('100')

        self.slow_interval_input.editingFinished.connect(self.update_parameters)
        self.fast_interval_input.editingFinished.connect(self.update_parameters)
        self.lower_threshold_input.editingFinished.connect(self.update_parameters)
        self.upper_threshold_input.editingFinished.connect(self.update_parameters)

        param_layout = QtWidgets.QFormLayout(self)
        param_layout.addRow('Slow Interval [s]', self.slow_interval_input)
        param_layout.addRow('Fast Interval [s]', self.fast_interval_input)
        param_layout.addRow('Lower Threshold', self.lower_threshold_input)
        param_layout.addRow('Upper Threshold', self.upper_threshold_input)

        self.param_set = ParameterSet(None, None, None, None)

    def update_parameters(self):
        self.param_set.slow_interval = float(str(self.slow_interval_input.text()))
        self.param_set.fast_interval = float(str(self.fast_interval_input.text()))
        self.param_set.lower_threshold = int(str(self.lower_threshold_input.text()))
        self.param_set.upper_threshold = int(str(self.upper_threshold_input.text()))

        self.new_parameters.emit(self.param_set)


def main():
    from image_analysers import KerasAnalyser
    from interpreters import BinaryFrameRateInterpreter
    from actuators.micro_manager import MMActuator, MMActuatorGUI
    import sys

    app = QtWidgets.QApplication(sys.argv)

    param_form = EDAParameterForm()
    event_bus = EventBus()
    actuator = MMActuator(event_bus=event_bus)
    actuator_gui = MMActuatorGUI(actuator, param_form)
    image_analyser = KerasAnalyser(event_bus)
    interpreter = BinaryFrameRateInterpreter(actuator_gui.param_form, event_bus)

    gui = EDAMainGUI(image_analyser, interpreter,actuator_gui)
    gui.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
