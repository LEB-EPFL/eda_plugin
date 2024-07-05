import numpy as np
from useq import MDAEvent, MDASequence


class MIPAnalyser():
    def __init__(self, data, **kwargs):
        self.sizes = None
        self.stack = None

    def frameReady(self, image: np.ndarray, event: MDAEvent, metadata: dict):
        self.stack[event.t, event.z, event.c, :, :] = image
        if event.z == self.sizes['z'] - 1:
            print("Full stack received!")

    def sequenceStarted(self, sequence: MDASequence):
        self.sizes = sequence.sizes
        self.stack = np.zeros((self.sizes['t'], self.sizes['z'], self.sizes['c'],
                               self.sizes['y'], self.sizes['x']), dtype=np.uint16)
