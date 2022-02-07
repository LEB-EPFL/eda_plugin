# Event-driven acquisition (EDA)

'event-driven-acquisition' is a Python library for advanced microscope control routines to enable
acquisitions to react to specific biological events of interest.

More information on the project it was first used on can be found in the [bioRxiv article](https://www.biorxiv.org/content/10.1101/2021.10.04.463102v1).

See the [Documentation](https://event-driven-acquisition.readthedocs.io/en/latest/index.html) for more details.

## Components of EDA


### Analyzers
Analyzers receive an image or images from the microscope. Their task is to reduce the information in
these images to a single or a set of parameters. These parameters are passed on to interpreters.

### Interpreters
An interpreter receives parameters from an analyzer and uses these to take a decision for how to
proceed with acquisition. This decision is passed on to an actuator. The interpretation can for
example take into account the temporal context of results from the analyzer.

### Actuators
The responsibility of an actuator is both to handle start/stop of acquisitions and to apply the
decisions from an interpreter to the ongoing acquisition.


## Installing Event-driven acquisition

1) Install the latest version of [micro-manager2.0](https://micro-manager.org/wiki/Micro-Manager_Nightly_Builds)
2) `pip install eda_plugin`
3) Install the Micro-Manager plugins:
   1) `>>> import eda_plugin`
   2) `>>> eda_plugin.install_mm_plugins()`
   3) Choose the main Micro-Manager folder in the file dialog (e.g. C:\Program Files\Micro-Manager-2.0)
4) Run micro-manager with the zmq server ([pycromanager installation](https://github.com/micro-manager/pycro-manager/blob/master/README.md))
5) Run the PythonEventServer from Plugins -> Developer Tools -> Python Event Server

Now you can run one of the examples
```python
import eda_plugin
eda_plugin.examples.basic()
# or if you have CUDA and tensorflow installed
eda_plugin.examples.pyro()
```

Or construct your own EDA loop e.g.
```python
    import sys
    from PyQt5 import QtWidgets

    from eda_plugin.utility.event_bus import EventBus
    import eda_plugin.utility.settings
    from eda_plugin.eda_gui import EDAMainGUI

    from eda_plugin.interpreters.frame_rate import BinaryFrameRateInterpreter
    from eda_plugin.analysers.image import ImageAnalyser
    from eda_plugin.actuators.micro_manager import MMActuator, TimerMMAcquisition

    eda_plugin.utility.settings.setup_logging()

    app = QtWidgets.QApplication(sys.argv)
    event_bus = EventBus()

    gui = EDAMainGUI(event_bus, viewer=True)
    actuator = MMActuator(event_bus, TimerMMAcquisition)
    analyser = ImageAnalyser(event_bus)
    interpreter = BinaryFrameRateInterpreter(event_bus)

    gui.show()
    actuator.gui.show()
    interpreter.gui.show()

    sys.exit(app.exec_())
```