from typing import Tuple
from PyQt5 import QtWidgets, QtCore, QtGui
import pyqtgraph as pg
import numpy as np
from pyqtgraph.graphicsItems.PlotCurveItem import PlotCurveItem
from qimage2ndarray import gray2qimage
from actuators.micro_manager import InjectedPycroAcquisition, PycroAcquisition, TimerMMAcquisition
from data_structures import ParameterSet
from event_bus import EventBus
from utility.qt_classes import QWidgetRestore
import qdarkstyle

import napari

# Adjust for different screen sizes
QtWidgets.QApplication.setAttribute(QtCore.Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)


class EDAMainGUI(QWidgetRestore):

    def __init__(self, event_bus: EventBus, viewer:bool=False):
        super().__init__()
        self.setWindowTitle('MainGUI')
        self.plot = EDAPlot()

        self.setLayout(QtWidgets.QVBoxLayout())
        if viewer:
            self.viewer = NetworkImageViewer()
            self.layout().addWidget(self.viewer)
            event_bus.new_network_image.connect(self.viewer.add_network_image)
        self.layout().addWidget(self.plot)
        self.setStyleSheet(qdarkstyle.load_stylesheet(qt_api='pyqt5'))
        # Establish communication between the different parts
        event_bus.acquisition_started_event.connect(self.plot.reset_plot)
        event_bus.new_decision_parameter.connect(self.plot.add_datapoint)
        event_bus.new_parameters.connect(self.plot.set_thr_lines)


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

    @QtCore.pyqtSlot(float, float, int)
    def add_datapoint(self, y: float, x: float, _):
        self.x_data.append(x)
        self.y_data.append(y)
        self.refresh_plot()

    def refresh_plot(self):
        self.output_line.setData(self.x_data, self.y_data)
        self.output_scatter.setData(self.x_data, self.y_data)
        self.enableAutoRange()

    def reset_plot(self):
        self.x_data = []
        self.y_data = []
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

    @QtCore.pyqtSlot(np.ndarray, tuple)
    def add_network_image(self, image: np.ndarray, dims:tuple):
        if dims[0] == 0:
            self.reset_scene_rect(image.shape)
        image = gray2qimage(image, normalize=True)
        self.image.setPixmap(QtGui.QPixmap.fromImage(image))
        self.update()


class NapariImageViewer(QtWidgets.QWidget):
    """ Simple implementation showing the output of the neural network.
    This could be extended to also show the images received from micro-manager or the preprocessed
    versions of those.
    Calling this can lead to the other Qt images being very scaled down."""
    def __init__(self):
        super().__init__()
        self.viewer = napari.Viewer()
        self.layer = None
        self.timepoints = 300

    @QtCore.pyqtSlot(np.ndarray, tuple)
    def add_network_image(self, image, dims:tuple):
        if dims[0] == 0 or self.layer is None:
            self.data = np.ndarray([self.timepoints, *image.shape])
            self.data[0, :, :] = image
            self.layer = self.viewer.add_image(self.data)
        else:
            self.data[dims[0] :, :] = image
            self.layer.data = self.data
            self.viewer.dims.set_point(0,dims[0])



def main():
    from image_analysers import KerasAnalyser
    from interpreters import BinaryFrameRateInterpreter
    from actuators.micro_manager import MMActuator
    import sys

    app = QtWidgets.QApplication(sys.argv)

    event_bus = EventBus()



    gui = EDAMainGUI(event_bus, viewer=True)
    # actuator = MMActuator(event_bus, TimerMMAcquisition)
    actuator = MMActuator(event_bus, InjectedPycroAcquisition)
    analyser = KerasAnalyser(event_bus)
    interpreter = BinaryFrameRateInterpreter(event_bus)

    gui.show()
    actuator.gui.show()
    interpreter.gui.show()
    analyser.gui.show()

    # viewer = NapariImageViewer()
    # event_bus.new_network_image.connect(viewer.add_network_image)

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
