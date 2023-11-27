from pymmcore_plus.mda.events import _get_auto_MDA_callback_class
from pymmcore_plus import CMMCorePlus
from useq import MDAEvent, MDASequence, Channel
from qtpy import QtWidgets
from eda_plugin.utility.core_event_bus import CoreEventBus


from threading import Timer, Event

class RepeatTimer(Timer):
    def __init__(self, *args, immediate=False):
        super().__init__(*args)
        self.immediate = immediate
    def run(self):
        self.stopped = Event()
        if self.immediate:
            self.function(*self.args, **self.kwargs)
        while not self.finished.wait(self.interval):
            self.function(*self.args, **self.kwargs)
        self.stopped.set()


class CoreRunner():
    def __init__(self, mmc: CMMCorePlus, event_bus: CoreEventBus):
        self.mmc = mmc
        self.engine = mmc.mda.engine
        self.gui = CoreRunnerGUI(self)
        self.event_bus = event_bus
        self.sequence = None
        self.eda_sequence = None
        self.full_sequence = None
        self.timer = None
        self.mode = 1
        self.running = False
        self.event_bus.useq_settings_event.connect(self.new_settings)
        self.event_bus.eda_useq_event.connect(self.new_eda_settings)
        self.event_bus.new_interpretation.connect(self.on_new_interpretation)


    def new_settings(self, seq: MDASequence):
        self.sequence = seq
        self.combine_sequences()

    def new_eda_settings(self, seq: MDASequence):
        self.eda_sequence = seq
        self.combine_sequences()

    def combine_sequences(self):
        if not self.sequence or not self.eda_sequence:
            return
        channels = set()
        for channel in self.sequence.channels:
            channels.add(channel)
        for channel in self.eda_sequence.channels:
            channels.add(channel)
        channels = sorted(list(channels), key=lambda channel: channel.config)
        print("CHANNELS: ", channels)
        total_timepoints = self.eda_sequence.sizes.get("t", 0) + self.sequence.sizes.get("t", 0)
        max_z = max(self.eda_sequence.sizes.get("z", 1), self.sequence.sizes.get("z", 1))
        self.full_sequence = MDASequence(channels=channels, time_plan={"loops": total_timepoints, "interval": 0},
                                         metadata={"EDA": True})
        #Transfer this new information to the analyser etc
        self.event_bus.translate_mda_settings(self.full_sequence)

    def setup_sequence(self):
        self.timepoint = 0
        self.timer = RepeatTimer(self.sequence.time_plan.phases[0].interval.seconds, self.acquire_event)

    def acquire_event(self):
        try:
            events = []
            # print("n frames timepoint:", max(1, self.current_sequence.sizes.get('c', 1)) * max(1, self.current_sequence.sizes.get('z', 1)))
            for i in range(max(1, self.current_sequence.sizes.get('c', 1)) * max(1, self.current_sequence.sizes.get('z', 1))):
                events.append(next(self.current_iter))          
        except StopIteration:
            # If the current sequence does not yield additional events, lets abort.
            self.stop()
            return
        for event in events:
            my_index = dict(event.index)
            my_index['t'] = self.timepoint
            channels_list = sorted([x.config for x in self.full_sequence.channels])
            my_index['c'] = channels_list.index(event.channel.config)
            # print(my_index, event.channel.config)
            #event is immutable, so we have to make a replacement
            event = MDAEvent(
                index=my_index,
                channel=event.channel,
                exposure=event.exposure,
                min_start_time=0, # We do the timing ourselves
                properties=event.properties,
                action=event.action,
                keep_shutter_open=event.keep_shutter_open
            )    
            self.engine.setup_event(event)
            output = self.engine.exec_event(event) or ()  # in case output is None
            # We might want to always emit for all channels here, otherwise it gets confusing
            if (img := getattr(output, "image", None)) is not None:
                self.mmc.mda.events.frameReady.emit(img, event)
            if self.full_sequence.sizes.get('t', 1) == self.timepoint + 1:
                self.stop()
        self.timepoint += 1

    def on_new_interpretation(self, new_interval: float):
        """Add a new event to the queue with the new interval."""
        if not self.running:
            return
        print(f"MODE {new_interval}")
        if self.timer and new_interval != self.mode:
            self.mode = new_interval
            if new_interval == 1:
                self.current_iter = self.eda_seq_iter
                self.current_sequence = self.eda_sequence
                interval = self.eda_sequence.time_plan.phases[0].interval.seconds
            else:
                self.current_iter = self.seq_iter
                self.current_sequence = self.sequence
                interval = self.sequence.time_plan.phases[0].interval.seconds
            self.timer.finished.set()
            self.timer.join()
            self.timer = RepeatTimer(interval, self.acquire_event,
                                     immediate=True)
            self.timer.start()

    def _run(self):
        self.running = True
        self.last_sequence = self.sequence
        # Get iterators for the acquisition
        self.seq_iter = self.sequence.iter_events()
        self.eda_seq_iter = self.eda_sequence.iter_events()
        self.current_iter = self.seq_iter
        self.current_sequence = self.sequence
        self.mmc.mda.events.sequenceStarted.emit(self.full_sequence)
        self.acquire_event()
        self.timer.start()
    
    def stop(self):
        self.timer.cancel()
        self.running = False
        self.mmc.mda.cancel()
        self.mmc.mda.events.sequenceFinished.emit(self.full_sequence)


class CoreRunnerGUI(QtWidgets.QWidget):
    def __init__(self, runner: CoreRunner):
        super().__init__()
        self.runner = runner
        self.init_ui()

    def init_ui(self):
        self.start_btn = QtWidgets.QPushButton("Start")
        self.stop_btn = QtWidgets.QPushButton("Stop")

        self.start_btn.clicked.connect(self.run)
        self.stop_btn.clicked.connect(self.runner.stop)

        self.setLayout(QtWidgets.QVBoxLayout())
        self.layout().addWidget(self.start_btn)
        self.layout().addWidget(self.stop_btn)

    def run(self):
        self.runner.setup_sequence()
        self.runner._run()