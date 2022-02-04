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

4) Run micro-manager with the zmq server (`pycromanager installation<https://github.com/micro-manager/pycro-manager/blob/master/README.md>`_`)
5) Run the PythonEventServer from Plugins -> Developer Tools -> Python Event Server

Running the test environment
----------------------------
Run the test environment from the examples:

>>> import eda_plugin as eda
>>> eda.examples.main.main_test()




.. TODO: Delete this!

To retrieve a list of random ingredients,
you can use the ``lumache.get_random_ingredients()`` function:

.. autofunction:: lumache.get_random_ingredients

The ``kind`` parameter should be either ``"meat"``, ``"fish"``,
or ``"veggies"``. Otherwise, :py:func:`lumache.get_random_ingredients`
will raise an exception.

.. autoexception:: lumache.InvalidKindError

For example:

>>> import lumache
>>> lumache.get_random_ingredients()
['shells', 'gorgonzola', 'parsley']
