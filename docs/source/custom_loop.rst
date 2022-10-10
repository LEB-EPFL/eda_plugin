.. _customloop:

=======================
Custom Loop Compilation
=======================

Every full EDA loop consists of at least three components. An actuator, an analyser and an
interpreter. To run your own EDA loop, you also have to supply an EventBus for communication
between the different components and you have to construct a QApplication for the Qt GUI
to run in.

This is the basic example:

.. literalinclude:: ../../eda_plugin/examples/main.py
    :lines: 3-40



The normal use case for custom situation will be to replace one of the main components, `actuator`,
`analyser` or `interpreter`. If implemented correctly, compatible components should be exchangable
individually.

For available components in the original package see the :doc:`api`.