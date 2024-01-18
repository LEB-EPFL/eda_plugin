from pymmcore_widgets import MDAWidget
from qtpy import QtCore, QtWidgets


class CoreMDAWidget(MDAWidget):
    mda_settings_event = QtCore.Signal(object)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for w in self.findChildren(QtWidgets.QWidget) +  [self]:
            w.installEventFilter(self)

    def eventFilter(self, obj, event):
        """Filter events from the MDAWidget and pass them on to the EventBus."""
        if event.type() == QtCore.QEvent.MouseButtonRelease:
            self.mda_settings_event.emit(self.get_state())
        if event.type() == QtCore.QEvent.KeyPress:
            self.mda_settings_event.emit(self.get_state())
        return super().eventFilter(obj, event)


if __name__ == "__main__":
    import sys
    from pymmcore_plus import CMMCorePlus
    from eda_plugin.utility.core_event_bus import CoreEventBus
    mmc = CMMCorePlus.instance()
    mmc.loadSystemConfiguration()
    app = QtWidgets.QApplication(sys.argv)
    win = CoreMDAWidget()
    win.show()
    event_bus = CoreEventBus(win)
    sys.exit(app.exec_())