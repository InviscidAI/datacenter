from typing import Sequence

import numpy as np

from simulation.objects.face import Face
from simulation.fields.boundary_conditions import BoundaryCondition
from simulation.objects import SimulationObject
import pyvista as pv


#------------------------------------------------------------#
#                          NOT USED                          #
#------------------------------------------------------------#
# todo use this class to load the room.


class Room:
    def __init__(
            self,
            mesh: pv.PolyData,
            face_bc_mappings: dict[str, dict[str, BoundaryCondition]],
    ):
        self.mesh = mesh.triangulate()

        face_names = face_bc_mappings.keys()
        self.faces = []
        for face_name in face_names:
            self.faces.append(
                Face(
                    face_name,
                    face_bc_mappings[face_name],
                    mesh.extract_cells(np.where(mesh.cell_data['face_names'] == face_name)[0]).extract_geometry()
                )
            )

    def get_bcs_foam_dict(self):
        res = {}
        for face in self.faces:
            face_bc = face.get_bcs_foam_dict()
            for field in face_bc.keys():
                if res.get(field) is None:
                    res[field] = {face.name: face_bc[field]}
                else:
                    res[field].update({face.name: face_bc[field]})
        return res

    def add_object(self, o: SimulationObject):
        self.mesh = o.add_to_mesh(self.mesh)


def cube_room(
        bounds: Sequence[float],
        bc_mappings: dict[str, dict[str, BoundaryCondition]],
):
    face_names = [
        "z_min",
        "z_max",
        "y_min",
        "x_max",
        "y_max",
        "x_min",
    ]

    for face_name in face_names:
        if face_name not in bc_mappings.keys():
            raise ValueError(f'Boundary condition not defined for face {face_name}')

    mesh = pv.Cube(bounds=bounds)
    mesh.cell_data['face_names'] = face_names

    return Room(mesh, bc_mappings)
