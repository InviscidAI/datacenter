from typing import Sequence

import numpy as np

import pyvista as pv

from simulation.objects.face import Face
from simulation.fields.boundary_conditions import BoundaryCondition
from simulation.objects import SimulationObject


class PatchObject(SimulationObject):
    def __init__(
            self,
            name: str,
            mesh: pv.PolyData,
            bc_dict: dict[str, BoundaryCondition],
            mesh_direction: Sequence[float],
            check_name: bool = True
    ):
        super().__init__(name, check_name)
        self.mesh = mesh
        self.bc_dict = bc_dict
        self.mesh_direction = np.array(mesh_direction)

        self.face = Face(name, bc_dict, mesh)

    def add_to_mesh(self, mesh: pv.PolyData):
        self.mesh = self.mesh.translate(-self.mesh_direction)
        region = self.mesh.extrude(self.mesh_direction * 2, capping=True, inplace=False).triangulate()
        mesh = mesh.triangulate()
        intersection = mesh.boolean_intersection(region)
        difference = mesh.boolean_difference(region)
        intersection.cell_data['face_names'] = self.name

        return difference.boolean_union(intersection)

    def get_bcs_foam_dict(self):
        return self.face.get_bcs_foam_dict()


def plane_patch(
        bc_dict: dict[str, BoundaryCondition],
        center: Sequence[float],
        direction: Sequence[float],
        i_size: int,
        j_size: int,
        i_resolution: int = 1,
        j_resolution: int = 1,
        name: str = 'plane',
        eps: float = 1e-3,
        **kwargs
):
    center = np.array(center)
    direction = np.array(direction)
    mesh = pv.Plane(center, direction, i_size, j_size, i_resolution, j_resolution)
    mesh.cell_data['face_names'] = ['plane']
    return PatchObject(name, mesh, bc_dict, direction * eps, **kwargs)