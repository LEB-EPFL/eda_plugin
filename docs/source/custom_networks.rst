============================================================
Using custom neural networks with :py:class:`.KerasAnalyser`
============================================================



.. mermaid::

    flowchart LR
        KerasAnalyser -- ImageStack --> QThreadpool;
        QThreadpool --> QRunnable1;
        QThreadpool --> QRunnable2;
        QThreadpool --> QRunnable3;
        QRunnable1 -- Computation --> Interpreter;
        QRunnable2 -- Computation --> Interpreter;
        QRunnable3 -- Computation --> Interpreter;






Computation
-----------


.. mermaid::

    flowchart TB
        ImageStack --> prep[/prepare_images/] -- data --> Inference
        data("data:<br> {'pixels': network_input,<br> 'e.g. tile_positions': xxx}")
        Inference --> extr[/extract_decision_parameter/] -->   ev1>"new_decision_parameter.emit()"] --> Interpreter
        Inference --> post[/post_process_output/] --> ev2>"new_network_image.emit()"] --> GUI
        prep -- data --> post