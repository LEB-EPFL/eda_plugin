"""QtWidgets that can be used as main GUI components for the EDA loop."""

from typing import Tuple, Union
from PyQt5 import QtWidgets, QtCore, QtGui
import PyQt5
import pyqtgraph as pg
import numpy as np
from pyqtgraph.graphicsItems.PlotCurveItem import PlotCurveItem
from qimage2ndarray import gray2qimage

from pymm_eventserver.data_structures import ParameterSet
from .event_bus import EventBus
from .qt_classes import QMainWindowRestore, QWidgetRestore
import qdarkstyle


import logging

log = logging.getLogger("EDA")

# Adjust for different screen sizes
QtWidgets.QApplication.setAttribute(QtCore.Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)


class EDAMainGUI(QMainWindowRestore):
    """Assemble different Widgets to have a main window for the GUI."""

    def __init__(self, event_bus: EventBus, viewer: bool = False):
        """Set up GUI and establish communication with the EventBus."""
        super().__init__()
        self.setWindowTitle("Event Driven Acquisition")
        self.plot = EDAPlot()
        self.central_widget = QtWidgets.QWidget()
        self.central_widget.setLayout(QtWidgets.QVBoxLayout())

        if viewer:
            self.viewer = NetworkImageViewer()
            self.central_widget.layout().addWidget(self.viewer)
            event_bus.new_network_image.connect(self.viewer.add_network_image)

        self.central_widget.layout().addWidget(self.plot)
        self.setCentralWidget(self.central_widget)
        self.dock_widgets = []
        self.widgets = []

        self.setStyleSheet(qdarkstyle.load_stylesheet(qt_api="pyqt5"))

        # Make docking to this window possible
        # self.dockers = QtWidgets.QDockWidget("Dockable", self)
        # self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, self.dockers)

        # Establish communication between the different parts
        event_bus.acquisition_started_event.connect(self.plot._reset_plot)
        event_bus.new_decision_parameter.connect(self.plot.add_datapoint)
        event_bus.new_parameters.connect(self.plot._set_thr_lines)

    def add_dock_widget(self, widget: QWidgetRestore, name=None):
        dock_widget = QtWidgets.QDockWidget(name, self)
        dock_widget.setWidget(widget)
        self.dock_widgets.append(dock_widget)
        self.widgets.append(widget)
        self.addDockWidget(QtCore.Qt.DockWidgetArea(1), dock_widget)

    def closeEvent(self, e):
        for widget in self.widgets:
            widget.closeEvent(e)


class EDAPlot(pg.PlotWidget):
    """Displays output of an analyser over time and the decision parameters of the interpreter."""

    def __init__(self, *args, **kwargs):
        """Initialise the main plot and the horizontal lines showing the thresholds.

        The lines are used to show the current parameters of a BinaryFrameRateInterpreter.
        """
        super().__init__(*args, **kwargs)

        self.output_line = PlotCurveItem([], pen="w")
        self.output_scatter = pg.ScatterPlotItem([], symbol="o", pen=None)

        self.thresholds = [80, 100]
        pen = pg.mkPen(color="#FF0000", style=QtCore.Qt.DashLine)
        self.thrLine1 = pg.InfiniteLine(pos=80, angle=0, pen=pen)
        self.thrLine2 = pg.InfiniteLine(pos=100, angle=0, pen=pen)
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
        """Add a datapoint that is received from the analyser."""
        self.x_data.append(x)
        self.y_data.append(y)
        self._refresh_plot()

    def _refresh_plot(self):
        self.output_line.setData(self.x_data, self.y_data)
        self.output_scatter.setData(self.x_data, self.y_data)
        self.enableAutoRange()

    def _reset_plot(self):
        self.x_data = []
        self.y_data = []
        self._refresh_plot()

    QtCore.pyqtSlot(ParameterSet)
    def _set_thr_lines(self, params: Union[dict, ParameterSet]):
        try:
            self.thrLine1.setPos(params.lower_threshold)
            self.thrLine2.setPos(params.upper_threshold)
        except AttributeError:
            self.thrLine1.setPos(params['lower_threshold'])
            self.thrLine2.setPos(params['upper_threshold'])


class NetworkImageViewer(QtWidgets.QGraphicsView):
    """Display a grayscale np.ndarray."""

    def __init__(self):
        """Set up with the default image size and initialise with a dummy pixmap."""
        super(NetworkImageViewer, self).__init__(QtWidgets.QGraphicsScene())
        self.pixmap = QtGui.QPixmap(512, 512)
        self.setSceneRect(0, 0, 512, 512)
        self.image = self.scene().addPixmap(self.pixmap)

    def _reset_scene_rect(self, shape: Tuple):
        self.setSceneRect(0, 0, *shape)
        self.fitInView(0, 0, *shape, mode=QtCore.Qt.KeepAspectRatio)
        self.setBackgroundBrush(QtGui.QColor("#222222"))

    @QtCore.pyqtSlot(np.ndarray, tuple)
    def add_network_image(self, image: np.ndarray, dims: tuple):
        """Translate the input image into a QImage and display in the scene."""
        log.debug(f"New image in ImageViewer with shape {image.shape}")
        if dims[0] == 0:
            self._reset_scene_rect(image.shape)
        image = gray2qimage(image, normalize=True)
        self.image.setPixmap(QtGui.QPixmap.fromImage(image))
        self.update()


class NapariImageViewer(QtWidgets.QWidget):
    """Simple implementation showing the output of the neural network.

    This could be extended to also show the images received from micro-manager or the preprocessed
    versions of those. Calling this can lead to the other Qt widgets being very scaled down. Napari
    is not installed with the module, so you have to install it yourself.
    """

    def __init__(self):
        """Open a napari viewer."""
        try:
            import napari
        except:
            log.warning("Napari was most likely not installed in this environment, please install")

        super().__init__()
        self.viewer = napari.Viewer()
        self.layer = None
        self.timepoints = 300

    @QtCore.pyqtSlot(np.ndarray, tuple)
    def add_network_image(self, image, dims: tuple):
        """Add the image received to the respective layer, or make a new layer."""
        if dims[0] == 0 or self.layer is None:
            self.data = np.ndarray([self.timepoints, *image.shape])
            self.data[0, :, :] = image
            self.layer = self.viewer.add_image(self.data)
        else:
            self.data[dims[0] :, :] = image
            self.layer.data = self.data
            self.viewer.dims.set_point(0, dims[0])
