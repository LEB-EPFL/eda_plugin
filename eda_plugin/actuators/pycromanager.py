"""Actuator based on the remote acquisition capabilities of Pycromanager and Micro-Magellan.

This implementation uses the post_hardware_hook_fn and image_process_fn hooks in
pycromanager.Acquisition to change the interval and receive images from Micro-Manager.

See also:
pycromanager (https://github.com/micro-manager/pycro-manager)
Micro-Magellan (https://micro-manager.org/MicroMagellan)
"""

from typing import List
import pycromanager
import copy
import queue
import logging
from PyQt5.QtCore import pyqtSignal

from eda_plugin.utility.data_structures import PyImage
from eda_plugin.actuators.micro_manager import MMAcquisition
from eda_plugin.utility.event_bus import EventBus


log = logging.getLogger("EDA")


class PycroAcquisition(MMAcquisition):
    """MMAcquisition that can be used with actuators.micro_manager.MMActuator.

    This implementation of a MMAcquisition uses the remote acquisition interplay between
    pycromanager (https://github.com/micro-manager/pycro-manager) and Micro-Magellan
    (https://micro-manager.org/MicroMagellan). An image_process_fn receives the images recorded and
    sends them to the analyser. A post_hardware_hook gives the possibility to change a capture
    event. This is used to add another image event with the interval that is currently requested by
    the interpreter.
    """

    new_image = pyqtSignal(PyImage)
    acquisition_started_event = pyqtSignal(object)

    def __init__(self, event_bus: EventBus, start_interval: float = 5.0, settings=None):
        """Set default settings, set up first acquisiton events connect signals."""
        super().__init__(event_bus)
        self.event_bus = event_bus
        self.dir = None

        if settings is None:
            self.settings = self._get_new_settings()
        else:
            self.settings = settings
        self.events = pycromanager.multi_d_acquisition_events(**self.settings)
        self.start_timepoints = self.settings["num_time_points"]
        self.channel_names = self.settings["channels"]

        self.interval = start_interval
        self.stop_acq_condition = False
        self.last_arrival_time = None
        self.new_image.connect(self.event_bus.new_image_event)

    def start_acq(self):
        """Start acquisition."""

        self.acquisition = pycromanager.Acquisition(
            directory=self.dir,
            name="EDA",
            # magellan_acq_index=0, activating this unfortunately throws and error
            post_hardware_hook_fn=self.post_hardware,
            image_process_fn=self.receive_image,
            show_display=True,
        )
        self.acquisition.acquire(self.events)

    def stop_acq(self):
        """Stop acquisition.

        If there would still be many events in the acquisition queue, this would not be trivial.
        Works here, as this implementation only generates the next event and can then pass None.
        https://github.com/micro-manager/pycro-manager/issues/340
        """
        self.stop_acq_condition = True
        self.acquisition_ended.emit()

    def post_hardware(self, event, _, event_queue: queue.Queue):
        """Return the event, unless acquisition was stopped.

        If acquisition continues running, add another event with the interval present in the moment.
        """
        # Check if acquisition was stopped
        if self.stop_acq_condition:
            event_queue.put(None)
            return None

        # Add another event with the interval that is set at the moment
        try:
            z_decision = event["axes"]["z"] == self.events[-1]["axes"]["z"]
        except:
            z_decision = True

        try:
            channel_decision = event["channel"] == self.events[-1]["channel"]
        except:
            channel_decision = True

        if all(
            [
                event["axes"]["time"] >= self.start_timepoints - 1,
                channel_decision,
                z_decision,
            ]
        ):
            if self.interval > 0:
                new_start_time = event["min_start_time"] + self.interval
            else:
                new_start_time = self.last_arrival_time + self.interval

            one_timepoint = copy.deepcopy(self.settings)
            one_timepoint["num_time_points"] = 1
            new_events = pycromanager.multi_d_acquisition_events(**one_timepoint)
            for new_event in new_events:
                new_event["axes"]["time"] = event["axes"]["time"] + 1
                new_event["min_start_time"] = new_start_time
                event_queue.put(copy.deepcopy(new_event))
        return event

    def receive_image(self, image, metadata):
        """Extract relevant metadata, make utility.data_sctructures.PyImage and notify EventBus."""
        for idx, c in enumerate(self.channel_names):
            if metadata["Channel"] == c:
                channel = idx

        try:
            z = metadata["Axes"]["z"]
        except:
            z = 0

        py_image = PyImage(
            image,
            metadata["Axes"]["time"],
            channel,
            z,
            metadata["ElapsedTime-ms"],
        )
        self.new_image.emit(py_image)
        self.last_arrival_time = metadata["ElapsedTime-ms"] / 1000
        log.debug(f"timepoint {py_image.timepoint} - new image c{channel}, z{z}")
        return image, metadata

    def change_interval(self, new_interval):
        """Change the internal interval."""
        self.interval = new_interval

    def _get_magellan_channels(self, settings) -> List:
        channels = []
        for channel_idx in range(settings.channels_.get_channel_names().size()):
            if settings.channels_.get_channel_list_setting(channel_idx).use_:
                channels.append(settings.channels_.get_channel_names().get(channel_idx))
        return channels

    def _calc_interval_s(self, settings) -> float:
        unit = settings.timeIntervalUnit_
        interval = settings.timePointInterval_
        if unit == 0:
            interval = interval / 1000
        elif unit == 2:
            interval = interval * 60
        return interval

    def _get_new_settings(self):
        self.magellan_settings = (
            self.event_bus.event_thread.bridge.get_magellan().get_acquisition_settings(
                0
            )
        )
        self.dir = self.magellan_settings.dir_

        # Running the Acquisition with the GUI settings does not work (see start_acq above)
        # So translate manually
        if self.magellan_settings.spaceMode_ != 4:
            # 3D
            settings = {
                "num_time_points": self.magellan_settings.numTimePoints_,
                "time_interval_s": self._calc_interval_s(self.magellan_settings),
                "channel_group": self.magellan_settings.channels_.get_channel_group(),
                "channels": self._get_magellan_channels(self.magellan_settings),
                "z_start": self.magellan_settings.zStart_,
                "z_end": self.magellan_settings.zEnd_,
                "z_step": self.magellan_settings.zStep_,
            }
        else:
            settings = {
                "num_time_points": self.magellan_settings.numTimePoints_,
                "time_interval_s": self._calc_interval_s(self.magellan_settings),
                "channel_group": self.magellan_settings.channels_.get_channel_group(),
                "channels": self._get_magellan_channels(self.magellan_settings),
            }
        self.channels = self._get_magellan_channels(self.magellan_settings)
        self.event_bus.new_magellan_settings.emit(settings)
        return settings
