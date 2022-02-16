Examples
========

Based on `pycromanager <https://github.com/micro-manager/pycro-manager>`_
-------------------------------------------------------------------------

If you are used to Micro-Magellan acquisitions, then the actuator implementation using pycromanagers
``Acquisition`` class to start a remote Micro-Magellan acquisition might be interesting for you:

>>> eda_plugin.examples.main.pyro()

For this implementation no calibration is necessary as described in the basic example. However, all
settings have to be done in the Micro-Magellan GUI: Plugins -> Micro-Magellan.

CUDA
----

If you have CUDA, cuDNN and tensorflow installed you can run the analyser that uses the neural
network for image analysis as described in the article.

>>> eda_plugin.examples.main.keras()

To get an image that the neural network can process, use the ImageInjector plugin installed during
the setup process in the on-the-fly processor pipeline in Micro-Manager.


As this only uses a different Analyser, it can just as well be used with the pycro-manager based
actuator:

>>> eda.examples.main.pyro_keras()

In this example the actuator is modified as described in :ref:`Custom Actuators` to allow for image
injection, as the Micro-Magellan plugins don't work with the on-the-fly processors.


.. _tensorflow_installation:
**Tensorflow installation**

These guides can help for tensorflow installation:

- `Tensorflow install <https://www.tensorflow.org/install>`_
- `Compatibility <https://www.tensorflow.org/install/source_windows#tested_build_configurations>`_
- `Towardsdatascience blog post <https://towardsdatascience.com/setting-up-tensorflow-gpu-with-cuda-and-anaconda-onwindows-2ee9c39b5c44>`_

For more advanced things, have a look at :doc:`custom_loop`