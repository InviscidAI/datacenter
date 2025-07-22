from simulation.fields.boundary_conditions import BoundaryCondition


class ExternalWallHeatFluxTemperature(BoundaryCondition):
    def __init__(
            self,
            mode='power',
            relaxation=1.0,
            emissivity=0.0,
            qr_relaxation=1.0,
            qr='none',
            kappa_method='fluidThermo',
            power=None,
            flux=None,
            transfer_coeff=None,
            ambient_temperature=None,
            qr_prev=None
    ):
        self.mode = mode
        self.relaxation = relaxation
        self.emissivity = emissivity
        self.qr_relaxation = qr_relaxation
        self.qr = qr
        self.kappa_method = kappa_method
        self.power = power
        self.flux = flux
        self.transfer_coeff = transfer_coeff
        self.ambient_temperature = ambient_temperature
        self.qr_prev = qr_prev

    def get_foam_dict(self):
        res = {
            'type': 'externalWallHeatFluxTemperature',
            'mode': self.mode,
            'relaxation': self.relaxation,
            'emissivity': self.emissivity,
            'qrRelaxation': self.qr_relaxation,
            'qr': self.qr,
            'kappaMethod': self.kappa_method,
            'value': '$internalField'
        }

        if self.qr != 'none':
            res['qrPrev'] = self.qr_prev

        if self.mode == 'power':
            if self.power is None:
                raise ValueError('Power needs to be specified for mode power')
            res['Q'] = self.power

        return res

