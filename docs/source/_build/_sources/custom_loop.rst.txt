Custom Loop Compilation
=======================

Every full EDA loop consists of at least three components. An actuator, an analyser and an
interpreter. To run your own EDA loop, you also have to supply an EventBus for communication
between the different components and you have to construct a QApplication for the Qt GUI
to run.

This is the basic example:


.. code-block:: python

    import sys
    from PyQt5 import QtWidgets

    from eda_plugin.utility.event_bus import EventBus
    from eda_plugin.interpreters.frame_rate import BinaryFrameRateInterpreter
    from eda_plugin.analysers.image import ImageAnalyser
    from eda_plugin.actuators.micro_manager import MMActuator, TimerMMAcquisition

    from eda_plugin.eda_gui import EDAMainGUI

    # Construct the QApplication environment, that the GUIs and event loop runs in.
    app = QtWidgets.QApplication(sys.argv)

    # Start an additional zmq server that works together with the PythonEventServer Plugin
    # for both communication between the EDA components and Micro-Manager.
    event_bus = EventBus()

    # Call the main components of the EDA loop (TimerMMAcquisition is also the default)
    actuator = MMActuator(event_bus, TimerMMAcquisition)
    analyser = ImageAnalyser(event_bus)
    interpreter = BinaryFrameRateInterpreter(event_bus)

    # Start the main GUI showing the EDA plot and the controls for the specific components
    gui = EDAMainGUI(event_bus, viewer=True)
    gui.show()
    actuator.gui.show()
    interpreter.gui.show()

    # Start the event loop
    sys.exit(app.exec_())

The normal use case for custom situation will be to replace on of the main components, `actuator`,
`analyser` or `interpreter`. If implemented correctly, compatible components should be exchangable
individually.

For available components in the original package see the :doc:`api`.