# src/engine/signal/base.py
from abc import ABC, abstractmethod

class SignalStrategy(ABC):
    @abstractmethod
    def evaluate(self, row):
        pass

    @abstractmethod
    def get_signal_type(self):
        pass