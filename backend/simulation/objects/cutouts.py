from pathlib import Path
from typing import Sequence

import numpy as np

from simulation.objects.face import Face
from simulation.fields.boundary_conditions import BoundaryCondition
from simulation.objects import SimulationObject

import pyvista as pv


class CutoutObject(SimulationObject):
    names = []

    def __init__(
            self,
            name: str,
            mesh: pv.PolyData,
            face_bc_mappings: dict[str, dict[str, BoundaryCondition]],
            sep: str = '_',
            check_name=True
    ):
        # will take in a dict mapping face name -> boundary condition dict
        # mesh will have face names set as cell_data
        super().__init__(name, check_name)

        self.mesh = mesh.triangulate()

        face_names = face_bc_mappings.keys()
        self.faces = []
        for face_name in face_names:
            if sep is not None:
                joined_name = name + sep + face_name
            else:
                joined_name = face_name
            self.faces.append(
                Face(
                    joined_name,
                    face_bc_mappings[face_name],
                    mesh.extract_cells(np.where(mesh.cell_data['face_names'] == face_name)[0]).extract_geometry()
                )
            )

        if sep is not None:
            self.mesh.cell_data['face_names'] = [
                name + sep + face_name
                for face_name in self.mesh.cell_data['face_names']
            ]

    def write_stls(self, directory: str | Path, create_subfolder: bool = False):
        directory = Path(directory)
        if not directory.exists():
            raise ValueError(f'Directory {directory} does not exist')
        if not directory.is_dir():
            raise ValueError(f'Directory {directory} is not a directory')

        if create_subfolder:
            directory = directory / self.name
        directory.mkdir(parents=False, exist_ok=True)
        for face in self.faces:
            face.write_stl(directory)

    def get_shm_geometry_dict(self):
        res = {}
        for face in self.faces:
            res.update(face.get_shm_geometry_dict())

        return res

    def get_shm_refinement_dict(self):
        res = {}
        for face in self.faces:
            res.update(face.get_shm_refinement_dict())
        return res

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

    def add_to_mesh(self, mesh: pv.PolyData):
        mesh = mesh.triangulate()
        self.mesh = self.mesh.triangulate()

        mesh = mesh.clean()
        self.mesh = self.mesh.clean()

        res = mesh.boolean_difference(self.mesh, tolerance=1e-6)
        return res


def cube(bounds: Sequence[float], bc_mappings: dict[str, dict[str, BoundaryCondition]], name: str = 'cube', **kwargs):
    face_names = [
        "x_min",
        "x_max",
        "y_min",
        "y_max",
        "z_min",
        "z_max",
    ]

    for face_name in face_names:
        if face_name not in bc_mappings.keys():
            raise ValueError(f'Boundary condition not defined for face {face_name}')

    mesh = pv.Cube(bounds=bounds)
    mesh.cell_data['face_names'] = face_names

    return CutoutObject(name, mesh, bc_mappings, **kwargs)


def plane(
        bc_dict: dict[str, BoundaryCondition],
        center: Sequence[float],
        direction: Sequence[float],
        i_size: int,
        j_size: int,
        i_resolution: int = 1,
        j_resolution: int = 1,
        name: str = 'plane',
        **kwargs
):
    mesh = pv.Plane(center, direction, i_size, j_size, i_resolution, j_resolution)
    mesh.cell_data['face_names'] = ['plane']
    bc_dict = {'plane': bc_dict}
    return CutoutObject(name, mesh, bc_dict, **kwargs)