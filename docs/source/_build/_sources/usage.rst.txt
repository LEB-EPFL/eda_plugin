Usage
=====

.. _installation:

Installation
------------

1) Install using pip:

.. code-block:: console

   (.venv) $ pip install eda_plugin

2) Install the latest release of `micro-manager2.0 <https://micro-manager.org/wiki/Micro-Manager_Nightly_Builds>`_
3) Install the Micro-Manager plugins:

>>> import eda_plugin
>>> eda_plugin.install_mm_plugins()
# Choose the main Micro-Manager folder in the file dialog (e.g. C:\Program Files\Micro-Manager-2.0)

4) Run micro-manager with the zmq server (Tools -> Options -> Run server on port 4827) (`pycromanager installation <https://github.com/micro-manager/pycro-manager/blob/master/README.md>`_)
5) Run the PythonEventServer from Plugins -> Developer Tools -> Python Event Server



Running the test environment
----------------------------
Run the test environment from the examples:

>>> import eda_plugin as eda
>>> eda.examples.main.basic()

For this version you can use the ImageInjector Plugin that was copied above to test EDA on a
dataset of your choice. (Plugins -> On-the-fly image processing -> ImageInjector)

An example dataset can be found at (TODO insert link) of mitochondria and Drp1. For this dataset,
Micro-Manager should be set to 2 channels and no Z slices.

If you are used to Micro-Magellan acquisitions, then the implementation using pycromanagers
``Acquisition`` class to start a remote Micro-Magellan acquisition might be interesting for you:

>>> eda.examples.main.pyro()

Here, an TODO: link image_process_fn is used to replace the image from the DemoCamera with an
image of your choice.

If you have CUDA, cuDNN and tensorflow installed you can run the analyser that uses the neural
network for image analysis

>>> eda.examples.main.keras()
# or
>>> eda.examples.main.pyro_keras()

These guides can help for tensorflow installation:

- `Tensorflow install <https://www.tensorflow.org/install>`_
- `Compatibility <https://www.tensorflow.org/install/source_windows#tested_build_configurations>`_
- `Towardsdatascience blog post <https://towardsdatascience.com/setting-up-tensorflow-gpu-with-cuda-and-anaconda-onwindows-2ee9c39b5c44>`_

For more advanced things, have a look at :doc:`custom_loop`
