from simulation.fields.boundary_conditions import BoundaryCondition


class NutKWallFunction(BoundaryCondition):
    def __init__(self, value='$internalField'):
        self.value = value

    def get_foam_dict(self):
        return {
            'type': 'nutkWallFunction',
            'value': self.value,
        }
