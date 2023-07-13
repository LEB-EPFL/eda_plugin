"""QtWidgets that can be used as main GUI components for the EDA loop."""

from typing import Tuple
from PyQt5 import QtWidgets, QtCore, QtGui
import pyqtgraph as pg
import numpy as np
from pyqtgraph.graphicsItems.PlotCurveItem import PlotCurveItem
from qimage2ndarray import array2qimage, gray2qimage
import time
from pathlib import Path

from pymm_eventserver.data_structures import ParameterSet, PyImage
from .event_bus import EventBus
from .qt_classes import QMainWindowRestore, QWidgetRestore
import qdarkstyle

# import matplotlib.pyplot as plt

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
        self.central_widget.setLayout(QtWidgets.QHBoxLayout())


        self.central_widget.layout().addWidget(self.plot)
        self.setCentralWidget(self.central_widget)
        self.dock_widgets = []
        self.widgets = []

        self.setStyleSheet(qdarkstyle.load_stylesheet(qt_api="pyqt5"))

        if viewer:
            self.viewer = NetworkImageViewer()
            self.add_dock_widget(self.viewer, "Viewer", 2)
            event_bus.new_network_image.connect(self.viewer.add_network_image)
            event_bus.new_prepared_image.connect(self.viewer.add_image)
        # Make docking to this window possible
        # self.dockers = QtWidgets.QDockWidget("Dockable", self)
        # self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, self.dockers)

        # Establish communication between the different parts
        event_bus.acquisition_started_event.connect(self.plot._reset_plot)
        event_bus.new_decision_parameter.connect(self.plot.add_datapoint)
        event_bus.new_parameters.connect(self.plot._set_thr_lines)

    def add_dock_widget(self, widget: QWidgetRestore, name = None, area: int = 1):
        dock_widget = QtWidgets.QDockWidget(name, self)
        dock_widget.setWidget(widget)
        self.dock_widgets.append(dock_widget)
        self.widgets.append(widget)
        self.addDockWidget(QtCore.Qt.DockWidgetArea(area), dock_widget)


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

    def _set_thr_lines(self, params: ParameterSet):
        self.thrLine1.setPos(params.lower_threshold)
        self.thrLine2.setPos(params.upper_threshold)


class NetworkImageViewer(QtWidgets.QGraphicsView):
    """Display a grayscale np.ndarray."""

    def __init__(self):
        """Set up with the default image size and initialise with a dummy pixmap."""
        super(NetworkImageViewer, self).__init__(QtWidgets.QGraphicsScene())
        self.pixmap = QtGui.QPixmap(512, 512)
        self.setSceneRect(0, 0, 512, 512)
        image = np.random.randint(0, 255, (512, 512, 3), dtype=np.uint8)
        # self.image = self.scene().addPixmap(self.pixmap)
        image = array2qimage(image)
        self.image = self.scene().addPixmap(QtGui.QPixmap.fromImage(image))
        self.original_image = None
        self.network_image = None
        self.stacked = np.zeros((512, 512, 3), dtype=np.float16)
        self.setDragMode(QtWidgets.QGraphicsView.ScrollHandDrag)
        self.red_lut = self.inferno_colormap()
        self.gray_lut = [QtGui.qRgb(i, i, i) for i in range(256)]
    
    def inferno_colormap(self, n=256):
        inferno = np.genfromtxt(Path(__file__).parent / "inferno.csv", delimiter=",")[1:,1:]
        inferno = inferno.astype(np.uint8)
        qt_inferno = [QtGui.qRgb(color[0], color[1], color[2]) for color in inferno]
        return qt_inferno

    def _reset_scene_rect(self, shape: Tuple):
        self.setSceneRect(0, 0, *shape)
        self.pixmap = QtGui.QPixmap(*shape)
        self.fitInView(0, 0, *shape, mode=QtCore.Qt.KeepAspectRatio)
        self.setBackgroundBrush(QtGui.QColor("#222222"))

    @QtCore.pyqtSlot(np.ndarray, tuple)
    def add_network_image(self, image: np.ndarray, dims: tuple):
        """Translate the input image into a QImage and display in the scene."""
        t0 = time.perf_counter()
        self.network_image = image
        # qimage = self.screen_images()
        # self.image.setPixmap(QtGui.QPixmap.fromImage(qimage))


        self.pixmap.fill(QtGui.QColor("transparent"))

        self.painter = QtGui.QPainter()

        # here the two images are drawn into the pixmap
        self.painter.begin(self.pixmap)
        self.painter.setCompositionMode(QtGui.QPainter.CompositionMode.CompositionMode_Screen)

        norm_image = self.original_image / (np.max(self.original_image)/255)
        norm_net_image = self.network_image / (np.max(self.network_image)/255)

        # choose composition mode
        qimage_1 = gray2qimage(norm_image.astype(np.uint8))
        qimage_2 = gray2qimage(norm_net_image.astype(np.uint8))
        qimage_1.setColorTable(self.gray_lut)
        qimage_2.setColorTable(self.red_lut)
        self.painter.drawImage(0,0, qimage_1)
        self.painter.drawImage(0,0, qimage_2)
        self.painter.end()

        self.image.setPixmap(self.pixmap)
        log.info(f"Screening took {time.perf_counter() - t0} seconds =======")
        log.info(f"{norm_net_image.max()}")

    @QtCore.pyqtSlot(np.ndarray, int)
    def add_image(self, image: np.ndarray, timepoint):
        """Translate the input image into a QImage and display in the scene."""
        self.original_image = image
        print(image.shape)
        if timepoint == 0:
            self.stacked = np.zeros(list(self.original_image.shape) + [3], dtype=np.float16)
            self._reset_scene_rect(self.original_image.shape)

    def screen_images(self):
        """Take both images and combine them into one false color image."""
        norm_image = self.original_image - self.original_image.min()
        norm_net_image = self.network_image - self.network_image.min()
        norm_image = norm_image / np.max(norm_image)
        norm_net_image = norm_net_image / np.max(norm_net_image)

        self.stacked[..., 0] = norm_net_image*10 # set the red channel to the second grayscale image
        self.stacked[..., 1] = norm_image # set the green channel to zero
        false_color_image = (self.stacked * 255.0).astype(np.uint8)
        return array2qimage(false_color_image)

    def wheelEvent(self, event):
        if event.modifiers() & QtCore.Qt.ControlModifier:
            # zoom
            anchor = self.transformationAnchor()
            self.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
            angle = event.angleDelta().y()
            factor = 1.1 if angle > 0 else 0.9
            self.scale(factor, factor)
            self.setTransformationAnchor(anchor)
        else:
            QtWidgets.QGraphicsView.wheelEvent(self, event)


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
