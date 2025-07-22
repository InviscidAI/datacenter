from simulation.fields.boundary_conditions import BoundaryCondition


class KQRWallFunction(BoundaryCondition):
    def __init__(self, value='$internalField'):
        self.value = value

    def get_foam_dict(self):
        return {
            'type': 'kqRWallFunction',
            'value': self.value,
        }


class TurbulentIntensityKineticEnergyInlet(BoundaryCondition):
    def __init__(self, intensity=0.14, value='$internalField'):
        self.intensity = intensity
        self.value = value

    def get_foam_dict(self):
        return {
            'type': 'turbulentIntensityKineticEnergyInlet',
            'intensity': self.intensity,
            'value': self.value,
        }