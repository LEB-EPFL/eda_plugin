from __future__ import annotations
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot
import numpy as np
import copy
import time

import nidaqmx
import nidaqmx.stream_writers
from utility.event_bus import EventBus


#MMSettings imports
from dataclasses import dataclass
import numpy as np
from typing import List, Any
from pathlib import Path

import logging
log = logging.getLogger("EDA")

class DAQActuator(QObject):
    """ Deliver new data to the DAQ with the framerate as given by the FrameRateInterpreter."""

    new_daq_data = pyqtSignal(np.ndarray)
    start_acq_signal = pyqtSignal(np.ndarray)

    def __init__(self, event_bus: EventBus):
        super().__init__()

        self.sampling_rate = 500

        self.event_bus = event_bus
        settings = self.event_bus.event_thread.bridge.get_studio().acquisitions().get_acquisition_settings()
        self.settings = MMSettings(settings)

        self.sampling_rate = 500
        self.update_settings(self.settings)

        self.galvo = Galvo(self)
        self.stage = Stage(self)
        self.camera = Camera(self)
        self.aotf = AOTF(self)

        self.task = self.init_task()
        self.acq = EDAAcquisition(self, self.settings)

        # self.event_bus.mda_settings_event.connect(self.new_settings)
        self.event_bus.configuration_settings_event.connect(self.configuration_settings)
        self.event_bus.acquisition_started_event.connect(self.run_acquisition_task)
        self.event_bus.acquisition_ended_event.connect(self.acq_done)
        self.event_bus.new_interpretation.connect(self.call_action)

    def init_task(self):
        try: self.task.close()
        except: log.info("Task close failed")
        self.task = nidaqmx.Task()
        self.task.ao_channels.add_ao_voltage_chan('Dev1/ao0') # galvo channel
        self.task.ao_channels.add_ao_voltage_chan('Dev1/ao1') # z stage
        self.task.ao_channels.add_ao_voltage_chan('Dev1/ao2') # camera channel
        self.task.ao_channels.add_ao_voltage_chan('Dev1/ao3') # aotf blanking channel
        self.task.ao_channels.add_ao_voltage_chan('Dev1/ao4') # aotf 488 channel
        self.task.ao_channels.add_ao_voltage_chan('Dev1/ao5') # aotf 561 channel

    def update_settings(self, new_settings):
        self.cycle_time = new_settings.channels['488']['exposure']
        self.sweeps_per_frame = new_settings.sweeps_per_frame
        self.frame_rate = 1/(self.cycle_time*self.sweeps_per_frame/1000)
        self.smpl_rate = round(self.sampling_rate*self.frame_rate*self.sweeps_per_frame*self.sweeps_per_frame)
        self.n_points = self.sampling_rate*self.sweeps_per_frame
        #settings for all pulses:
        self.duty_cycle = 10/self.n_points
        self.settings = new_settings
        log.info('NI settings set')

    @pyqtSlot(object)
    def run_acquisition_task(self, _):
        # self.event_thread.mda_settings_event.disconnect(self.new_settings)
        # time.sleep(0.5)
        self.acq.run_acquisition()

    @pyqtSlot(object)
    def acq_done(self, _):
        # self.acq.set_z_position.emit(self.acq.orig_z_position)
        # self.event_thread.mda_settings_event.connect(self.new_settings)
        # time.sleep(1)
        self.task.stop()
        self.acq.update_settings(self.acq.settings)


    @pyqtSlot(float)
    def call_action(self, new_interval):
        self.acq.interval = new_interval
        log.info(f"=== New interval: {new_interval}===")

    @pyqtSlot(object)
    def new_settings(self, new_settings: MMSettings):
        self.settings = new_settings
        self.update_settings(new_settings)
        self.acq.update_settings(new_settings)
        log.info('NEW SETTINGS')

    @pyqtSlot(str, str, str)
    def configuration_settings(self, device, prop, value):
        if device == "488_AOTF" and prop == r"Power (% of max)":
            self.aotf.power_488 = float(value)
        elif device == "561_AOTF" and prop == r"Power (% of max)":
            self.aotf.power_561 = float(value)
        elif device == "exposure":
            self.settings.channels['488']['exposure'] = float(value)
            self.update_settings(self.settings)
        elif device == 'PrimeB_Camera' and prop == "TriggerMode":
            brightfield = True if value == "Internal Trigger" else False
            self.brightfield_control.toggle_flippers(brightfield)

        elif device == "EDA" and prop == "Label":
            eda = self.core.get_property('EDA', "Label")
            self.eda = False if eda == "Off" else True

        if device in ["561_AOTF", "488_AOTF", 'exposure']:
            self.live.make_daq_data()
        log.info(f"{device}.{prop} -> {value}")

    def generate_one_timepoint(self):
        iter_slices = copy.deepcopy(self.settings.slices)
        iter_slices_rev = copy.deepcopy(iter_slices)
        iter_slices_rev.reverse()

        galvo = self.galvo.one_frame(self.settings)
        camera = self.camera.one_frame(self.settings)

        z_iter = 0
        channels_data = []
        for channel in self.settings.channels.values():
            if channel['use']:
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
    def __init__(self, ni:DAQActuator, settings:MMSettings):
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
        self.ni.init_task()
        self.ni.task.timing.cfg_samp_clk_timing(rate=self.ni.smpl_rate,
                                             sample_mode=nidaqmx.constants.AcquisitionType.CONTINUOUS,
                                             samps_per_chan=self.daq_data_fast.shape[1])
        self.ni.task.out_stream.regen_mode = nidaqmx.constants.RegenerationMode.DONT_ALLOW_REGENERATION
        self.ni.stream = nidaqmx.stream_writers.AnalogMultiChannelWriter(self.ni.task.out_stream,
                                                                         auto_start=False)
        self.ni.stream.write_many_sample(self.daq_data_fast)
        self.ni.task.register_every_n_samples_transferred_from_buffer_event(self.daq_data_fast.shape[1], self.get_new_data)

    def get_new_data(self, task_handle, every_n_samples_event_type, number_of_samples, callback_data):
        log.info(self.interval)
        if self.interval == self.interval_fast:
            self.ni.stream.write_many_sample(self.daq_data_fast)
        elif self.interval == self.interval_slow:
            self.ni.stream.write_many_sample(self.daq_data_slow)
        else:
            log.warning('Intervals have changes please restart the acquisition')
        return 0

    def make_daq_data(self):
        timepoint = self.ni.generate_one_timepoint()
        self.daq_data_fast = self.add_interval(timepoint, self.interval_fast*1000)
        self.daq_data_slow = self.add_interval(timepoint, self.interval_slow*1000)

    def add_interval(self, timepoint, interval_ms):
        if interval_ms > 0:
            missing_samples = round(self.ni.smpl_rate * interval_ms/1000-timepoint.shape[1])
            galvo = np.ones(missing_samples) * self.ni.galvo.parking_voltage
            rest = np.zeros((timepoint.shape[0] - 1, missing_samples))
            delay = np.vstack([galvo, rest])
            timepoint = np.hstack([timepoint, delay])
        print("INTERVAL: ", interval_ms)
        return timepoint

    def run_acquisition(self):
        self.ni.task.start()


def make_pulse(ni, start, end, offset):
    up = np.ones(round(ni.duty_cycle*ni.n_points))*start
    down = np.ones(ni.n_points-round(ni.duty_cycle*ni.n_points))*end
    pulse = np.concatenate((up,down)) + offset
    return pulse

class Galvo:
    def __init__(self, ni: DAQActuator):
        self.ni = ni
        self.offset_0= -0.15
        self.amp_0 = 0.75
        self.parking_voltage = -3

    def one_frame(self, settings):
        self.n_points = self.ni.sampling_rate*settings.sweeps_per_frame
        down1 = np.linspace(0,-self.amp_0,round(self.n_points/(4*settings.sweeps_per_frame)))
        up = np.linspace(-self.amp_0,self.amp_0,round(self.n_points/(2*settings.sweeps_per_frame)))
        down2 = np.linspace(self.amp_0,0,round(self.n_points/settings.sweeps_per_frame) -
                            round(self.n_points/(4*settings.sweeps_per_frame)) -
                            round(self.n_points/(2*settings.sweeps_per_frame)))
        galvo_frame = np.concatenate((down1, up, down2))
        galvo_frame = np.tile(galvo_frame, settings.sweeps_per_frame)
        galvo_frame = galvo_frame + self.offset_0
        galvo_frame = galvo_frame[0:self.n_points]
        galvo_frame = self.add_delays(galvo_frame, settings)
        return galvo_frame

    def add_delays(self, frame, settings):
        if settings.post_delay > 0:
            delay = np.ones(round(self.ni.smpl_rate * settings.post_delay)) * self.parking_voltage
            frame = np.hstack([frame, delay])

        if settings.pre_delay > 0:
            delay = np.ones(round(self.ni.smpl_rate * settings.pre_delay)) * self.parking_voltage
            frame = np.hstack([delay, frame])

        return frame


class Stage:
    def __init__(self, ni: DAQActuator):
        self.ni = ni
        self.pulse_voltage = 5
        self.calibration = 202.161
        self.max_v = 10

    def one_frame(self, settings, height_offset):
        height_offset = self.convert_z(height_offset)
        stage_frame = make_pulse(self.ni, height_offset, height_offset, 0)
        stage_frame = self.add_delays(stage_frame, settings)
        return stage_frame

    def convert_z(self, z_um):
        return (z_um/self.calibration) * self.max_v

    def add_delays(self, frame, settings):
        delay = np.ones(round(self.ni.smpl_rate * settings.post_delay))
        delay = delay * frame[-1]
        if settings.post_delay > 0:
            frame = np.hstack([frame, delay])

        if settings.pre_delay > 0:
            frame = np.hstack([delay, frame])

        return frame


class Camera:
    def __init__(self, ni: DAQActuator):
        self.ni = ni
        self.pulse_voltage = 5

    def one_frame(self, settings):
        camera_frame = make_pulse(self.ni, 5, 0, 0)
        camera_frame = self.add_delays(camera_frame, settings)
        return camera_frame

    def add_delays(self, frame, settings):
        if settings.post_delay > 0:
            delay = np.zeros(round(self.ni.smpl_rate * settings.post_delay))
            frame = np.hstack([frame, delay])

        if settings.pre_delay > 0:
            delay = np.zeros(round(self.ni.smpl_rate * settings.pre_delay))
            #TODO whty is predelay after camera trigger?
            # Maybe because the camera 'stores' the trigger?
            frame = np.hstack([frame, delay])

        return frame


class AOTF:
    def __init__(self, ni:DAQActuator):
        self.ni = ni
        self.blank_voltage = 10
        core = self.ni.event_bus.event_thread.bridge.get_core()
        self.power_488 = float(core.get_property('488_AOTF',r"Power (% of max)"))
        self.power_561 = float(core.get_property('561_AOTF',r"Power (% of max)"))

    def one_frame(self, settings:MMSettings, channel:dict):
        blank = make_pulse(self.ni, 0, self.blank_voltage, 0)
        if channel['name'] == '488':
            aotf_488 = make_pulse(self.ni, 0, self.power_488/10, 0)
            aotf_561 = make_pulse(self.ni, 0, 0, 0)
        elif channel['name'] == '561':
            aotf_488 = make_pulse(self.ni, 0, 0, 0)
            aotf_561 = make_pulse(self.ni, 0, self.power_561/10, 0)
        aotf = np.vstack((blank, aotf_488, aotf_561))
        aotf = self.add_delays(aotf, settings)
        return aotf

    def add_delays(self, frame:np.ndarray, settings: MMSettings):
        if settings.post_delay > 0:
            delay = np.zeros((frame.shape[0], round(self.ni.smpl_rate * settings.post_delay)))
            frame = np.hstack([frame, delay])

        if settings.pre_delay > 0:
            delay = np.zeros((frame.shape[0], round(self.ni.smpl_rate * settings.pre_delay)))
            frame = np.hstack([delay, frame])

        return frame


@dataclass
class MMChannel:
    name: str
    active: bool
    power: float
    exposure_ms: int

@dataclass
class MMSettings:
    java_settings: Any = None

    timepoints: int =  11
    interval_ms: int = 1000

    pre_delay: float = 0.0
    post_delay: float = 0.03

    java_channels: Any = None
    use_channels = True
    channels: List[MMChannel] = None
    n_channels: int = 0

    slices_start: float = None
    slices_end: float = None
    slices_step: float = None
    slices: List[float] = None
    use_slices: bool = False

    save_path: Path = None
    prefix: str = None

    sweeps_per_frame: int = 1

    acq_order: str = None

    def __post_init__(self):

        if self.java_settings is not None:
            # print(dir(self.java_settings))
            self.interval_ms = self.java_settings.interval_ms()
            self.timepoints = self.java_settings.num_frames()
            self.java_channels = self.java_settings.channels()
            self.acq_order = self.java_settings.acq_order_mode()
            self.use_channels = self.java_settings.use_channels()

        try:
            self.java_channels.size()
        except:
            return

        self.channels = {}
        self.n_channels = 0
        for channel_ind in range(self.java_channels.size()):
            channel = self.java_channels.get(channel_ind)
            config = channel.config()
            self.channels[config] = {'name': config,
                                     'use': channel.use_channel(),
                                     'exposure': channel.exposure(),
                                     'z_stack': channel.do_z_stack(),
                                     }
            if self.channels[config]['use']:
                self.n_channels += 1

        self.use_slices = self.java_settings.use_slices()
        self.java_slices = self.java_settings.slices()
        self.slices = []
        for slice_num in range(self.java_settings.slices().size()):
            self.slices.append(self.java_slices.get(slice_num))
        if len(self.slices) == 0:
            self.slices = [0]