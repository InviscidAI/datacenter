from simulation.fields.alpha_t import AlphatJayatillekeWallFunction
from simulation.fields.boundary_conditions import *
from simulation.fields.epsilon import EpsilonWallFunction, TurbulentMixingLengthDissipationRateInlet
from simulation.fields.nu_t import NutKWallFunction
from simulation.fields.pressure import FixedFluxPressure, PrghPressure
from simulation.fields.temperature import ExternalWallHeatFluxTemperature
from simulation.fields.turb_ke import KQRWallFunction, TurbulentIntensityKineticEnergyInlet
from simulation.fields.velocity import NoSlip, PressureInletOutletVelocity


def wall():
    return {
        'alphat': AlphatJayatillekeWallFunction(),
        'epsilon': EpsilonWallFunction(),
        'k': KQRWallFunction(),
        'nut': NutKWallFunction(),
        'p': Calculated(),
        'p_rgh': FixedFluxPressure(),
        'U': NoSlip(),
        'T': ZeroGradient(),
    }


def fixed_temperature_fixed_velocity_inlet(u, t):

    return {
        'U': FixedValue(u),
        'p': Calculated(),
        'p_rgh': FixedFluxPressure(),
        'T': FixedValue(t),
        'k': TurbulentIntensityKineticEnergyInlet(),
        'epsilon': TurbulentMixingLengthDissipationRateInlet(),
        'nut': Calculated(),
        'alphat': Calculated(),
    }


def fixed_heat_flux_fixed_velocity_inlet(u, q):

    return {
        'U': FixedValue(u),
        'p': Calculated(),
        'p_rgh': FixedFluxPressure(),
        'T': ExternalWallHeatFluxTemperature(power=q),
        'k': TurbulentIntensityKineticEnergyInlet(),
        'epsilon': TurbulentMixingLengthDissipationRateInlet(),
        'nut': Calculated(),
        'alphat': Calculated(),
    }


def fixed_velocity_outlet(u):
    return {
        'U': FixedValue(u),
        'p': Calculated(),
        'p_rgh': FixedFluxPressure(),
        'T': ZeroGradient(),
        'k': InletOutlet(),
        'epsilon': InletOutlet(),
        'nut': Calculated(),
        'alphat': Calculated(),
    }


def open_outlet():
    return {
        'U': PressureInletOutletVelocity(),
        'p': Calculated(),
        'p_rgh': PrghPressure(),
        'T': ZeroGradient(),
        'k': InletOutlet(),
        'epsilon': InletOutlet(),
        'nut': Calculated(),
        'alphat': Calculated(),
    }