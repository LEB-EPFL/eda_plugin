============================================================
Using custom neural networks with :py:class:`.KerasAnalyser`
============================================================

If you plan to use your own neural network with :py:class:`.KerasAnalyser`, consider the internal
structure of the analysis pipeline.

.. mermaid::

    flowchart LR
        KerasAnalyser -- ImageStack --> QThreadpool;
        QThreadpool --> QRunnable1;
        QThreadpool --> QRunnable2;
        QThreadpool --> QRunnable3;
        QRunnable1 -- Computation --> Interpreter;
        QRunnable2 -- Computation --> Interpreter;
        QRunnable3 -- Computation --> Interpreter;

The :py:class:`.ImageAnalyser` is responsible for collecting the necessary amount of images and only
starting analysis if all images have been received. :py:class:`.KerasAnalyser` will notify you if
you load a model that does not fit the settings in the acquisition.
These image stacks are forwarded to QRunnables in a QThreadpool that can concurrently analyse the
images and send the results to the interpreter.

Computation
-----------

Depening on your neural network you might need a special QRunnable that allows for some
functionality around the model. This can be subclassed from :py:class:`.KerasWorker`. See examples
in :py:mod:`.examples.analysers` like :py:class:`.KerasTilingWorker` and
:py:class:`.KerasRescaleWorker`. The dataflow is visualized here:

.. mermaid::

    flowchart TB
        ImageStack --> prep[/prepare_images/] -- "data['pixels']" --> Inference
        data("data:<br> {'pixels': network_input,<br> 'e.g. tile_positions': xxx}")
        event>pyqtSignal]
        Inference --> extr[/extract_decision_parameter/] -->   ev1>"new_decision_parameter.emit()"]
        --EventBus --> Interpreter
        Inference --> post[/post_process_output/] --> ev2>"new_network_image.emit()"] --> GUI
        Inference(<b>Model</b><br>predict_on_batch)
        prep -- data --> post

If you want your worker to be available in the AnalyserGUI, you can add its location to the
settings.json file.

.. code-block:: json

    "eda_plugin": {
        "analysers": {
            "keras": {
                "worker_modules": [
                    "eda_plugin.examples.analysers"
                ],
    }}}

Resource allocation
-------------------
Resource allocation is handeled by a `QThreadpool <https://doc.qt.io/qt-5/qthreadpool.html>`_, using
its :py:meth:`tryStart` method, this ensures that images are skipped if no resources are available
for analysis. The number of availble threads can be overwritten by subclassing the KerasAnalyser and
setting ``self.threadpool.setMaxThreadCount(5)``.