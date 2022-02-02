Usage
=====

.. _installation:

Installation
------------

Install using pip:

.. code-block:: console

   (.venv) $ pip install event-driven-acquisition

Add the PythonEventServer.jar to the mmplugins folder in the Micro-Manager2.0 folder that you are
going to use.


Running the test environment
----------------------------
Open Micro-Manager and run the PythonEventServer at Plugins -> Developer Tools -> Python Event
Server.
Run the test environment from the examples:

>>> import eda_plugin as eda
>>> eda.examples.main.main_test()


Creating recipes
----------------

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