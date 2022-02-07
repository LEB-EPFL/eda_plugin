Creating Custom components
==========================

You may want to adapt one of the components to your needs, here are some hints on how to do this.

Actuators
---------
Actators are seperated into the main class for basic parameters and control and Acquisition classes
responsible for a started acquisition. The actuator should at least be able to receive a signal from
an interpreter, here normally implemented in the pyqtSlot ``call_action``. Depending on the
implementation of image recording, it might also be responsible to hand new images over to the
analyser. This is the case for example in the ``PycroAcquisition`` class.
The ``InjectedPycroAcquistion`` class used in the ``pyro`` example is a subclass of the more basic
``actuators.pycromanager.PycroAcquisition`` with the additional image injection.

.. code-block:: python

    class InjectedPycroAcquisition(PycroAcquisition):

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            tif_file = "./180420_120_comp.tif"
            self.frame_time = 0.15  # s
            self.tif = tifffile.imread(tif_file)
            self.start_time = time.perf_counter()
            self.timepoint = 0
            log.info(f"{tif_file} loaded with shape {self.tif.shape}")

In this example, the function ``receive_image`` of ``PycroAcquisition`` is overwritten to inject the
image. Later, the original ``receive_image`` is called by ``super().receive_image(image, metadata)``
with the modified image.

.. code-block:: python

    def receive_image(self, image, metadata):
        for idx, c in enumerate(self.channels):
            if metadata["Channel"] == c["config"]:
                channel = idx

        if channel == 0:
            now = time.perf_counter()
            elapsed = now - self.start_time
            timepoint = round(elapsed / self.frame_time)
            timepoint = np.max([timepoint, self.timepoint + 1])
            self.timepoint = np.mod(timepoint, self.tif.shape[0])

        image = self.tif[self.timepoint, channel, :, :]
        # Send this image to the main receive_image function of PycroAcquisition
        return super().receive_image(image, metadata)

Additionally to the actuators that are based on Micro-Manager controlling the microscope, we also
implemented an actuator for our NI DAQ driven microscope ``actuators.daq.DAQActuator``. This can be
a starting point for a very different implementation of an actuator.

Analysers
---------
Analysers are seperated into a main QObject (e.g. ``analysers.image.ImageAnalyser``) for the main settings and the interaction with the other
EDA components. They also start a QThreadpool, these threads are used to start asynchronous analysis
of the recorded images in a QRunnable (e.g. ``analysers.image.ImageAnalyserWorker``). The
implementation using a thread pool also ensures, that the analysis keeps up with the acquisition, as
analysis tasks that can't be handed to a free thread are skipped automatically.
In this role, analysers should be able to receive images and are responsible to send a new result to
the interpreter.

The ``KerasAnalyser`` using the model that was reported in the original paper is a subclass of the very basic
``ImageAnalyser``. It uses workers that are themselves subclasses of ``ImageAnalyserWorker``.
``examples.analysers.kers`` shows two workers that modify the pre and post processing of the images.
To accomodate workers with potentially different inputs and signals, the functions ``_get_worker_args``
and ``connect_worker_signals`` can be overwritten seperately without having to rewrite the whole
worker delivery logic.

Interpreters
------------
Interpreter implementations are responsible to translate the results of analysers to a specific
action for the actuator. They therefore have to receive the information from the analyser and send
the request for some action to the actuator.