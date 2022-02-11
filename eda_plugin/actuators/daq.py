"""Actuator that can be used with a National Instruments DAQ card.

The main actuator will have two sets of data for the DAQ card. One without delay for the interval,
and one with delay to match the interval set as set in the slow setting. The DAQ card will be
configured to ask for data every time before it runs out of data and the data will be written to the
output stream that corresponds to the interval set by the interpreter into this actuator.
"""

from __future__ import annotations

import copy
import logging

import nidaqmx
import nidaqmx.stream_writers
import numpy as np
from eda_plugin.utility.event_bus import EventBus
from eda_plugin.utility.data_structures import MMSettings
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot


log = logging.getLogger("EDA")


class DAQActuator(QObject):
    """Deliver new data to the DAQ with the framerate as given by the FrameRateInterpreter."""

    new_daq_data = pyqtSignal(np.ndarray)
    start_acq_signal = pyqtSignal(np.ndarray)

    def __init__(self, event_bus: EventBus):
        """Initialize the DAQ with the settings that are fixed for all modes."""
        super().__init__()

        self.sampling_rate = 500

        self.event_bus = event_bus
        settings = (
            self.event_bus.event_thread.bridge.get_studio()
            .acquisitions()
            .get_acquisition_settings()
        )
        self.settings = MMSettings(settings)

        self.sampling_rate = 500
        self._update_settings(self.settings)

        self.galvo = Galvo(self)
        self.stage = Stage(self)
        self.camera = Camera(self)
        self.aotf = AOTF(self)

        self.task = self._init_task()
        self.acq = EDAAcquisition(self, self.settings)

        # self.event_bus.mda_settings_event.connect(self.new_settings)
        self.event_bus.configuration_settings_event.connect(self.configuration_settings)
        self.event_bus.acquisition_started_event.connect(self.run_acquisition_task)
        self.event_bus.acquisition_ended_event.connect(self.acq_done)
        self.event_bus.new_interpretation.connect(self.call_action)

    def _init_task(self):
        try:
            self.task.close()
        except:
            log.info("Task close failed")
        self.task = nidaqmx.Task()
        self.task.ao_channels.add_ao_voltage_chan("Dev1/ao0")  # galvo channel
        self.task.ao_channels.add_ao_voltage_chan("Dev1/ao1")  # z stage
        self.task.ao_channels.add_ao_voltage_chan("Dev1/ao2")  # camera channel
        self.task.ao_channels.add_ao_voltage_chan("Dev1/ao3")  # aotf blanking channel
        self.task.ao_channels.add_ao_voltage_chan("Dev1/ao4")  # aotf 488 channel
        self.task.ao_channels.add_ao_voltage_chan("Dev1/ao5")  # aotf 561 channel

    def _update_settings(self, new_settings):
        # Some change needed here when different exposure times would be implemented for channels
        self.cycle_time = new_settings.channels["488"]["exposure"]
        self.sweeps_per_frame = new_settings.sweeps_per_frame
        self.frame_rate = 1 / (self.cycle_time * self.sweeps_per_frame / 1000)
        self.smpl_rate = round(
            self.sampling_rate
            * self.frame_rate
            * self.sweeps_per_frame
            * self.sweeps_per_frame
        )
        self.n_points = self.sampling_rate * self.sweeps_per_frame
        # settings for all pulses:
        self.duty_cycle = 10 / self.n_points
        self.settings = new_settings
        log.info("NI settings set")

    @pyqtSlot(object)
    def run_acquisition_task(self, _):
        """Run the acquisition by forwarding the pyqtSignal to the Acquisition instance."""
        # self.event_thread.mda_settings_event.disconnect(self.new_settings)
        # time.sleep(0.5)
        self.task.start()

    @pyqtSlot(object)
    def acq_done(self, _):
        """Acquisition was stopped, clean up."""
        # self.acq.set_z_position.emit(self.acq.orig_z_position)
        # self.event_thread.mda_settings_event.connect(self.new_settings)
        # time.sleep(1)
        self.task.stop()
        self.acq.update_settings(self.acq.settings)

    @pyqtSlot(float)
    def call_action(self, new_interval):
        """Interpreter has emitted a new interval to use, adapt the acquisition instance."""
        self.acq.interval = new_interval
        log.info(f"=== New interval: {new_interval}===")

    @pyqtSlot(object)
    def new_settings(self, new_settings: MMSettings):
        """There are new settings, most likely in the MDA window in MM, adapt internal settings."""
        self.settings = new_settings
        self._update_settings(new_settings)
        self.acq.update_settings(new_settings)
        log.info("NEW SETTINGS")

    @pyqtSlot(str, str, str)
    def configuration_settings(self, device, prop, value):
        """Table settings in MM changed, adapt internal settings."""
        if device == "488_AOTF" and prop == r"Power (% of max)":
            self.aotf.power_488 = float(value)
        elif device == "561_AOTF" and prop == r"Power (% of max)":
            self.aotf.power_561 = float(value)
        elif device == "exposure":
            self.settings.channels["488"]["exposure"] = float(value)
            self._update_settings(self.settings)
        elif device == "PrimeB_Camera" and prop == "TriggerMode":
            brightfield = True if value == "Internal Trigger" else False
            self.brightfield_control.toggle_flippers(brightfield)

        elif device == "EDA" and prop == "Label":
            eda = self.core.get_property("EDA", "Label")
            self.eda = False if eda == "Off" else True

        if device in ["561_AOTF", "488_AOTF", "exposure"]:
            self.live.make_daq_data()
        log.info(f"{device}.{prop} -> {value}")

    def _generate_one_timepoint(self):
        """One timepoint, at the moment only in slices first, channels second."""
        iter_slices = copy.deepcopy(self.settings.slices)
        iter_slices_rev = copy.deepcopy(iter_slices)
        iter_slices_rev.reverse()

        galvo = self.galvo.one_frame(self.settings)
        camera = self.camera.one_frame(self.settings)

        z_iter = 0
        channels_data = []
        for channel in self.settings.channels.values():
            if channel["use"]:
                slices_data = []
                slices = iter_slices if not np.mod(z_iter, 2) else iter_slices_rev
                for sli in slices:
                    aotf = self.aotf.one_frame(self.settings, channel)
                    offset = sli - self.settings.slices[0]
                    stage = self.stage.one_frame(self.settings, offset)
                    data = np.vstack((galvo, stage, camera, aotf))
                    slices_data.append(data)
                z_iter += 1
                data = np.hstack(slices_data)
                channels_data.append(data)
        timepoint = np.hstack(channels_data)
        return timepoint


class EDAAcquisition(QObject):
    """An acquisition that can be run from the main Actuator instance.

    This setup of a separate object for the Acquisition comes from the isimgui, where there are two
    different classes for the live mode and the mda acquisition. Here it could be included in the
    main class, but to keep things consistent it will remain in its own class.
    """

    def __init__(self, ni: DAQActuator, settings: MMSettings):
        """Initialize with the standard settings."""
        super().__init__()
        self.settings = settings
        self.ni = ni
        self.interval = 5
        self.interval_fast = 0
        self.daq_data_fast = None
        self.interval_slow = 5
        self.daq_data_slow = None
        self.make_daq_data()
        self.update_settings(self.settings)

    def update_settings(self, new_settings):
        """Update the settings according to the daq_data that the acquisition has generated."""
        self.ni._init_task()
        self.ni.task.timing.cfg_samp_clk_timing(
            rate=self.ni.smpl_rate,
            sample_mode=nidaqmx.constants.AcquisitionType.CONTINUOUS,
            samps_per_chan=self.daq_data_fast.shape[1],
        )
        self.ni.task.out_stream.regen_mode = (
            nidaqmx.constants.RegenerationMode.DONT_ALLOW_REGENERATION
        )
        self.ni.stream = nidaqmx.stream_writers.AnalogMultiChannelWriter(
            self.ni.task.out_stream, auto_start=False
        )
        self.ni.stream.write_many_sample(self.daq_data_fast)
        self.ni.task.register_every_n_samples_transferred_from_buffer_event(
            self.daq_data_fast.shape[1], self.get_new_data
        )

    def get_new_data(self, *_):
        """Pass new data to the DAQ card.

        This function was called because the DAQ card is running out of samples to write to the
        outputs. The additional parameters have information about the event that we don't use here.
        """
        log.info(self.interval)
        if self.interval == self.interval_fast:
            self.ni.stream.write_many_sample(self.daq_data_fast)
        elif self.interval == self.interval_slow:
            self.ni.stream.write_many_sample(self.daq_data_slow)
        else:
            log.warning("Intervals have changes please restart the acquisition")
        return 0

    def make_daq_data(self):
        """Prepare the two versions of daq_data so they can be pass fast later to the DAQ stream."""
        timepoint = self.ni._generate_one_timepoint()
        self.daq_data_fast = self.add_interval(timepoint, self.interval_fast * 1000)
        self.daq_data_slow = self.add_interval(timepoint, self.interval_slow * 1000)

    def add_interval(self, timepoint, interval_ms):
        """Fastest timepoint possible, now add parking data to match the specified interval."""
        if interval_ms > 0:
            missing_samples = round(
                self.ni.smpl_rate * interval_ms / 1000 - timepoint.shape[1]
            )
            galvo = np.ones(missing_samples) * self.ni.galvo.parking_voltage
            rest = np.zeros((timepoint.shape[0] - 1, missing_samples))
            delay = np.vstack([galvo, rest])
            timepoint = np.hstack([timepoint, delay])
        print("INTERVAL: ", interval_ms)
        return timepoint


def make_pulse(ni, start, end, offset):
    """Trigger pulse e.g. for the camera."""
    up = np.ones(round(ni.duty_cycle * ni.n_points)) * start
    down = np.ones(ni.n_points - round(ni.duty_cycle * ni.n_points)) * end
    pulse = np.concatenate((up, down)) + offset
    return pulse


class Galvo:
    """This represents the Galvo mirror, with it's DAQ logic and some default parameters."""

    def __init__(self, ni: DAQActuator):
        """Initialize default settings.

        offset is due to the not perfectly centralized position that the mirror is put into the
        setup. The Amplitude is set to make the swing big enough to make one grid iteration overlap.
        The parking voltage should put the mirror somewhere where we get the least amount of light
        the camera.
        """
        self.ni = ni
        self.offset_0 = -0.15
        self.amp_0 = 0.75
        self.parking_voltage = -3

    def one_frame(self, settings: MMSettings) -> np.ndarray:
        """Generate one frame with the sawtooth pattern according to the settings passed."""
        self.n_points = self.ni.sampling_rate * settings.sweeps_per_frame
        down1 = np.linspace(
            0, -self.amp_0, round(self.n_points / (4 * settings.sweeps_per_frame))
        )
        up = np.linspace(
            -self.amp_0,
            self.amp_0,
            round(self.n_points / (2 * settings.sweeps_per_frame)),
        )
        down2 = np.linspace(
            self.amp_0,
            0,
            round(self.n_points / settings.sweeps_per_frame)
            - round(self.n_points / (4 * settings.sweeps_per_frame))
            - round(self.n_points / (2 * settings.sweeps_per_frame)),
        )
        galvo_frame = np.concatenate((down1, up, down2))
        galvo_frame = np.tile(galvo_frame, settings.sweeps_per_frame)
        galvo_frame = galvo_frame + self.offset_0
        galvo_frame = galvo_frame[0 : self.n_points]
        galvo_frame = self._add_delays(galvo_frame, settings)
        return galvo_frame

    def _add_delays(self, frame, settings):
        if settings.post_delay > 0:
            delay = (
                np.ones(round(self.ni.smpl_rate * settings.post_delay))
                * self.parking_voltage
            )
            frame = np.hstack([frame, delay])

        if settings.pre_delay > 0:
            delay = (
                np.ones(round(self.ni.smpl_rate * settings.pre_delay))
                * self.parking_voltage
            )
            frame = np.hstack([delay, frame])

        return frame


class Stage:
    """Represents the Z-Stage with logic and default parameters."""

    def __init__(self, ni: DAQActuator):
        """Initialize the default parameters.

        Calibration is the maximum position in um that the stage can reach. It will be used together
        with the maximal voltage that can be applied to scale the voltage output to the desired
        position in um.
        """
        self.ni = ni
        self.calibration = 202.161
        self.max_v = 10

    def one_frame(self, settings, height_offset):
        """Translate the height_offset to a voltage and make a simple constant output signal."""
        height_offset = self.convert_z(height_offset)
        stage_frame = make_pulse(self.ni, height_offset, height_offset, 0)
        stage_frame = self._add_delays(stage_frame, settings)
        return stage_frame

    def convert_z(self, z_um):
        """Convert um to the corresponding voltage."""
        return (z_um / self.calibration) * self.max_v

    def _add_delays(self, frame, settings):
        delay = np.ones(round(self.ni.smpl_rate * settings.post_delay))
        delay = delay * frame[-1]
        if settings.post_delay > 0:
            frame = np.hstack([frame, delay])

        if settings.pre_delay > 0:
            frame = np.hstack([delay, frame])

        return frame


class Camera:
    """Triggering logic for the camera being in EdgeTrigger mode."""

    def __init__(self, ni: DAQActuator):
        """Pulse voltage expected as a camera trigger."""
        self.ni = ni
        self.pulse_voltage = 5

    def one_frame(self, settings):
        """Pulse to trigger the exposure in the camera as set in MM with the exposure setting."""
        camera_frame = make_pulse(self.ni, 5, 0, 0)
        camera_frame = self._add_delays(camera_frame, settings)
        return camera_frame

    def _add_delays(self, frame, settings):
        """Why is pre delay after camera trigger?."""
        if settings.post_delay > 0:
            delay = np.zeros(round(self.ni.smpl_rate * settings.post_delay))
            frame = np.hstack([frame, delay])

        if settings.pre_delay > 0:
            delay = np.zeros(round(self.ni.smpl_rate * settings.pre_delay))
            # TODO Why is pre delay after camera trigger?
            # Maybe because the camera 'stores' the trigger?
            frame = np.hstack([frame, delay])

        return frame


class AOTF:
    """Bundles the different DAQ channels used for the AOTF."""

    def __init__(self, ni: DAQActuator):
        """Initialize the default settings and the settings as set in MM at the moment.

        The devices 488_AOTF and 561_AOTF have to exist in MM for this. This can be dummy devices.
        The intensities of the lasers will be set from here by adjusting the pass through of the
        AOTF. Attention, the set point setting of the lasers can be set independently in MM, so the
        intensity here is just a relative value, nothing absolute.
        """
        self.ni = ni
        self.blank_voltage = 10
        core = self.ni.event_bus.event_thread.bridge.get_core()
        self.power_488 = float(core.get_property("488_AOTF", r"Power (% of max)"))
        self.power_561 = float(core.get_property("561_AOTF", r"Power (% of max)"))

    def one_frame(self, settings: MMSettings, channel: dict):
        """Make the elongated pulse for the laser that spans the exposure time of the camera."""
        blank = make_pulse(self.ni, 0, self.blank_voltage, 0)
        if channel["name"] == "488":
            aotf_488 = make_pulse(self.ni, 0, self.power_488 / 10, 0)
            aotf_561 = make_pulse(self.ni, 0, 0, 0)
        elif channel["name"] == "561":
            aotf_488 = make_pulse(self.ni, 0, 0, 0)
            aotf_561 = make_pulse(self.ni, 0, self.power_561 / 10, 0)
        aotf = np.vstack((blank, aotf_488, aotf_561))
        aotf = self._add_delays(aotf, settings)
        return aotf

    def _add_delays(self, frame: np.ndarray, settings: MMSettings):
        if settings.post_delay > 0:
            delay = np.zeros(
                (frame.shape[0], round(self.ni.smpl_rate * settings.post_delay))
            )
            frame = np.hstack([frame, delay])

        if settings.pre_delay > 0:
            delay = np.zeros(
                (frame.shape[0], round(self.ni.smpl_rate * settings.pre_delay))
            )
            frame = np.hstack([delay, frame])

        return frame
