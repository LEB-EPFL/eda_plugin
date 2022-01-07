from PyQt5 import QtWidgets, QtCore, QtGui


class QWidgetRestore(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.settings = QtCore.QSettings( 'EDA', self.__class__.__name__)
        # Initial window size/pos last saved. Use default values for first time
        self.resize(self.settings.value("size", QtCore.QSize(270, 225)))
        self.move(self.settings.value("pos", QtCore.QPoint(50, 50)))

    def closeEvent(self, e):
        # Write window size and position to config file
        self.settings.setValue("size", self.size())
        self.settings.setValue("pos", self.pos())
        # Close all other windows too
        app = QtGui.QApplication.instance()
        app.closeAllWindows()
        e.accept()