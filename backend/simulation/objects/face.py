from typing import Sequence

from simulation.fields.boundary_conditions import BoundaryCondition
import pyvista as pv
from pathlib import Path


class Face:
    def __init__(
            self,
            name:str,
            bc_dict: dict[str, BoundaryCondition],
            mesh: pv.PolyData,
            refinement_levels: Sequence[int]=(2,3)
    ):
        self.name = name
        self.bc_dict = bc_dict
        self.mesh = mesh
        self.refinement_levels = list(refinement_levels)

    def update_bcs(self, update: dict[str, BoundaryCondition]) -> None:
        self.bc_dict.update(update)

    def write_stl(self, path: str|Path) -> None:
        if isinstance(path, str):
            path = Path(path)

        if path.is_dir():
            path = path / (self.name + '.stl')

        triangulated_mesh = self.mesh.triangulate()
        triangulated_mesh.save(path)

    def get_bcs_foam_dict(self):
        return {
            field: self.bc_dict[field].get_foam_dict() for field in self.bc_dict.keys()
        }

    def get_shm_geometry_dict(self):
        return {
            f'{self.name}.stl': {
                'type': 'triSurfaceMesh',
                'name': self.name
            }
        }

    def get_shm_refinement_dict(self):
        return {
            self.name: {
                'level': self.refinement_levels,
            }
        }
