*****
Usage
*****

.. _install:

Installation
============

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

Note: This installation does not include tensorflow needed for analysers using neural networks.
Please refer to :ref:`tensorflowinstall` to set your system up.

Running the test environment
============================

With Micro-Manager, the zmq server and PythonEventServer open, run the test environment from the
examples:

>>> import eda_plugin
>>> eda_plugin.examples.basic()


Camera settings
---------------

If you are in the Demo configuration of Micro-Manager, acquisitions will normally result in a moving
stripe pattern. The analyser in this basic implementation uses the intensity of the first pixel, so
the readout will also be a wave. If you start an acquisition from the MDA window, you should see the
range of values in the main plot. If the frequency of the wave pattern is very high, you can set
Devices -> Device Property Browser -> Camera-StripeWidth to a smaller value.

.. raw:: html

   <iframe src="https://player.vimeo.com/video/678707620?h=8f5231bf54" width="640" height="350"
   frameborder="0" allow="autoplay; fullscreen" allowfullscreen></iframe>

Change in Wave pattern upon demo camera adjustment

Calibration
-----------

The actuator pauses acquisition to match the requested interval. After each interval it opens
acquisition to acquire one timepoint. To be flexible for many systems, the time to open acquisition
can be calibrated using the Calibration button. The EDA-plugin triggers a 5 timepoint acquisition
and calculates the time to open acquisition from the image arrival times. It then runs a ramp of
waiting time to further adjust to capture the correct number of frames.

Once calibration has finished, custom_intervals might still be enabled in the MDA window.
Unfortunately you might have to restart Micro-Manager to disable it. So, note the calibration value
in the Actuator. If the calibrated value does not yet capture all frames all the time, you can
enable the auto-adjust checkbox for an acquisition, and see if this improves.

.. raw:: html

  <iframe src="https://player.vimeo.com/video/679096472?h=fb679f5efe" width="640" height="350" frameborder="0" allow="autoplay; fullscreen" allowfullscreen></iframe>

Calibration procedure for three channels

Acquisition
-----------

If you start acquisition from the Actuator GUI, EDA will be active. Set the thresholds to be in the
range that you have observed for the analyser to be in and click the Start button.

.. raw:: html

   <iframe src="https://player.vimeo.com/video/680354826?h=d831663237" width="640" height="350" frameborder="0" allow="autoplay; fullscreen" allowfullscreen></iframe>
