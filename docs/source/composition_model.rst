.. mermaid::
    classDiagram
        EDA <|-- Analyser
        EDA <|-- Interpreter
        EDA <|-- Actuator
        EDA <|-- Writer


.. mermaid::


    classDiagram
        ImageAnalyser <|-- KerasAnalyser
        ImageAnalyser <|-- PycroImageAnalyser
        KerasWorker <|-- KerasRescaleWorker
        KerasWorker <|-- Keras1CWorker
        KerasWorker <|-- KerasTilingWorker
        KerasWorker <|-- FtsWWorker


        class ImageAnalyser{
        + ImageAnalyserWorker
        }

        class KerasAnalyser{
        + KerasWorker
        }


.. mermaid::

    classDiagram

        ImageAnalyserWorker <|-- KerasWorker
        KerasWorker <|-- KerasRescaleWorker
        KerasWorker <|-- Keras1CWorker
        KerasWorker <|-- KerasTilingWorker

        class ImageAnalyserWorker{
        +np.ndarray local_images
        +int timepoint
        +int start_time
        +class _Signals
        +run()
        +extract_decision_parameter()
        }


        class KerasWorker{
        +network model
        +prepare_images()
        +post_process_output()
        +run()
        +class _Signals
        }

        class KerasRescaleWorker{
        +prepare_images()
        +extract_decision_parameter()
        +post_process_output()
        }

        class Keras1CWorker{
        +prepare_images()
        +extract_decision_parameter()
        +post_process_output()
        }

        class KerasTilingWorker{
        +prepare_images()
        +extract_decision_parameter()
        +post_process_output()
        }