from simulation.fields.boundary_conditions import BoundaryCondition


class AlphatWallFunction(BoundaryCondition):
    def __init__(self, value='$internalField'):
        self.value = value

    def get_foam_dict(self):
        return {
            'type': 'alphatWallFunction',
            'value': self.value,
        }


class AlphatJayatillekeWallFunction(BoundaryCondition):
    def __init__(self, prt=0.85, value='$internalField'):
        self.value = value
        self.prt = prt

    def get_foam_dict(self):
        return {
            'type': 'compressible::alphatJayatillekeWallFunction',
            'Prt': self.prt,
            'value': self.value,
        }