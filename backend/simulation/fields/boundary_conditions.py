from abc import ABC, abstractmethod
from typing import Sequence


class BoundaryCondition(ABC):
    @abstractmethod
    def get_foam_dict(self):
        return {}


class FixedValue(BoundaryCondition):
    def __init__(self, value: float|Sequence[float]):
        self.value = value

    def get_foam_dict(self):
        return {
            'type': 'fixedValue',
            'value': self.value,
        }


class ZeroGradient(BoundaryCondition):
    def get_foam_dict(self):
        return {
            'type': 'zeroGradient',
        }


class FixedGradient(BoundaryCondition):
    def __init__(self, gradient: float):
        self.gradient = gradient

    def get_foam_dict(self):
        return {
            'type': 'fixedGradient',
            'gradient': self.gradient,
        }


class Calculated(BoundaryCondition):
    def get_foam_dict(self):
        return {
            'type': 'calculated',
            'value': '$internalField'
        }


class InletOutlet(BoundaryCondition):
    def __init__(self, inlet_value='$internalField'):
        self.inlet_value = inlet_value

    def get_foam_dict(self):
        return {
            'type': 'inletOutlet',
            'inletValue': self.inlet_value,
        }
