import abc
import pyvista as pv


class SimulationObject(abc.ABC):
    names = set()

    def __init__(self, name, check_name=True):
        if check_name:
            if name in SimulationObject.names:
                raise ValueError(f"Name {name} is already in use")

        self.name = name
        SimulationObject.names.add(name)

    @abc.abstractmethod
    def add_to_mesh(self, mesh: pv.PolyData):
        pass

    @abc.abstractmethod
    def get_bcs_foam_dict(self):
        pass
