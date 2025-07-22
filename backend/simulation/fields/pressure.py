from simulation.fields.boundary_conditions import BoundaryCondition


class FixedFluxPressure(BoundaryCondition):
    def __init__(self, value='$internalField'):
        self.value = value

    def get_foam_dict(self):
        return {
            'type': 'fixedFluxPressure',
            'value': self.value,
        }


class PrghPressure(BoundaryCondition):
    def __init__(self, p='$internalField', value='$internalField'):
        self.p = p
        self.value = value

    def get_foam_dict(self):
        return {
            'type': 'prghPressure',
            'p': self.p,
        }