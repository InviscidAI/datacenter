from simulation.fields.boundary_conditions import BoundaryCondition


class EpsilonWallFunction(BoundaryCondition):
    def __init__(self, value='$internalField'):
        self.value = value

    def get_foam_dict(self):
        return {
            'type': 'epsilonWallFunction',
            'value': self.value,
        }


class TurbulentMixingLengthDissipationRateInlet(BoundaryCondition):
    def __init__(self, mixing_length=0.0168, value='$internalField'):
        self.value = value
        self.mixing_length = mixing_length

    def get_foam_dict(self):
        return {
            'type': 'turbulentMixingLengthDissipationRateInlet',
            'mixingLength': self.mixing_length,
            'value': self.value,
        }