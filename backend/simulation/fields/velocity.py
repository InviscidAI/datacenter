from simulation.fields.boundary_conditions import BoundaryCondition


class PressureInletOutletVelocity(BoundaryCondition):
    def __init__(self, pressure_inlet_value='$internalField'):
        self.pressure_inlet_value = pressure_inlet_value

    def get_foam_dict(self):
        return {
            'type': 'pressureInletOutletVelocity',
            'value': self.pressure_inlet_value,
        }


class NoSlip(BoundaryCondition):
    def get_foam_dict(self):
        return {
            'type': 'noSlip',
        }
