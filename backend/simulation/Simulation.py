import json
import os
import shutil
import subprocess
from pathlib import Path

from foamlib import FoamCase, FoamFile
import pyvista as pv
from tqdm import tqdm

from simulation.fields.buoyant_simple_foam import *
from simulation.objects import cube


class Results:
    def __init__(self, foam_case):
        self.foam_case: FoamFile = foam_case

    def max_temp(self, t=-1):
        with self.foam_case[t]['T'] as f:
            return f.internal_field.max()

    def convert_results_to_gltf(self):
        """Uses PyVista Plotter to convert the final OpenFOAM timestep to glTF files."""
        try:
            reader = pv.OpenFOAMReader(str(self.foam_case.path / f'{self.foam_case.path.name}.foam'))
            reader.set_active_time_value(reader.time_values[-1])
            mesh_data = reader.read()['internalMesh']
            if mesh_data is None:
                raise Exception("Failed to read internalMesh from OpenFOAM results.")
            min_temp, max_temp = mesh_data.get_data_range('T')

            original_slice = mesh_data.slice('z', origin=(0, 0, 2.5))
            original_slice = original_slice.compute_normals(consistent_normals=True)
            original_slice = original_slice.flip_faces()

            boundary = reader.read()["boundary"]
            surfs = []
            for k in reader.read()["boundary"].keys():
                if k != "defaultFaces":
                    surfs.append(boundary[k].extract_surface().flip_faces())

            plotter_temp = pv.Plotter(off_screen=True, lighting='light_kit')
            plotter_temp.add_mesh(
                mesh_data.outline()
            )
            plotter_temp.add_mesh(
                original_slice,
                scalars='T',
                lighting=False,
                cmap='coolwarm',
                clim=(min_temp, max_temp)
            )
            plotter_temp.add_mesh(
                pv.merge(surfs),
                scalars='T',
                smooth_shading=True,
                split_sharp_edges=True,
                ambient=0.2,
                cmap='coolwarm',
                clim=(min_temp, max_temp)
            )

            mesh_data = reader.read()['internalMesh']
            if mesh_data is None:
                raise Exception("Failed to read internalMesh from OpenFOAM results.")
            min_temp, max_temp = mesh_data.get_data_range('T')

            original_slice = mesh_data.slice('z', origin=(0, 0, 1))
            original_slice = original_slice.compute_normals(consistent_normals=True)
            original_slice = original_slice.flip_faces()

            boundary = reader.read()["boundary"]
            surfs = []
            for k in reader.read()["boundary"].keys():
                if k != "defaultFaces":
                    surfs.append(boundary[k].extract_surface().flip_faces())

            plotter_vel = pv.Plotter(off_screen=True, lighting='light_kit')
            plotter_vel.add_mesh(
                mesh_data.outline()
            )

            # slic = resampled_data.slice('z', origin=(cx,cy,cz))
            # #print(len(slic.points[::10]))
            # streamlines = mesh_data.streamlines_from_source(
            #     slic.points[::10]
            # )
            # plotter_vel.add_mesh(
            #     streamlines.tube(radius=0.01), scalars='U'
            # )

            plotter_vel.add_mesh(
                original_slice,
                scalars='U',
                lighting=False,
            )

            plotter_vel.add_mesh(
                pv.merge(surfs),
                color='w',
                smooth_shading=True,
                split_sharp_edges=True,
                ambient=0.2,
            )

            # 4. Export the scene to GLTF.
            # Per the user's request, use this same volumetric plot for both temperature and velocity views.
            output_path_temp = self.foam_case.path / 'temperature.gltf'
            output_path_vel = self.foam_case.path / 'velocity.gltf'

            plotter_temp.export_gltf(output_path_temp)
            print(f"--> Volumetric temperature result saved to {output_path_temp}")

            # Simply copy the file for the velocity view.
            plotter_vel.export_gltf(output_path_vel)
            print(f"--> Copied volumetric plot for velocity view to {output_path_vel}")

            plotter_temp.close()
            plotter_vel.close()
            pv.close_all()
            # print(f"--> All results converted to glTF in {results_dir}")
            return True
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"--> FAILED to convert results to glTF: {e}")
            return False


class Simulation:
    def __init__(self, inp: str|Path|list[dict], foam_case_dir: str|Path, overwrite=True):
        if isinstance(inp, str) or isinstance(inp, Path):
            with open(inp, "r") as f:
                self.regions = json.load(f)
        else:
            self.regions = inp

        if isinstance(foam_case_dir, str):
            foam_case_dir = Path(foam_case_dir)
        self.foam_case_dir = foam_case_dir
        self.foam_case = None
        self.load_foam_case(overwrite=overwrite)

        self.load_objects()

        self.room_dict = None
        for region in self.regions:
            if region['type'] == 'room':
                self.room_dict = region

        if self.room_dict is None:
            raise ValueError("No room definition found in input.")

    def _run_cmd(self, cmd, log_file=None):
        with open(log_file, "w") as f:
            try:
                subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, cwd=self.foam_case_dir, check=True)
                print(f'{cmd[0]} completed successfully.')
            except subprocess.CalledProcessError as e:
                error_msg = f'Running {cmd[0]} failed with return code {e.returncode}. '
                if log_file is not None:
                    error_msg += f'Logs written to {log_file}'
                raise RuntimeError(error_msg)

    def run_all(self):
        self._run_cmd(['blockMesh'], self.foam_case_dir / 'log.blockMesh')
        self._run_cmd(['surfaceFeatureExtract'], self.foam_case_dir / 'log.surfaceFeatureExtract')
        self._run_cmd(['snappyHexMesh', '-overwrite'], self.foam_case_dir / 'log.snappyHexMesh')
        self._run_cmd(['buoyantSimpleFoam'], self.foam_case_dir / 'log.buoyantBoussinesqSimpleFoam')

    def get_results(self):
        (self.foam_case_dir / f'{self.foam_case_dir.name}.foam').touch()
        return Results(self.foam_case)

    def write_all(self):
        self.write_all_objects((self.foam_case_dir / 'constant' / 'triSurface').absolute().as_posix())
        self.write_control_dict()
        self.write_fv_schemes()
        self.write_fv_solution()
        self.write_block_mesh_dict()
        self.write_snappy_hex_mesh_dict()
        self.write_mesh_quality_dict()
        self.write_field_files()
        self.write_g_dict()
        self.write_turbulence_properties()
        self.write_thermophyiscal_properties()
        self.write_surface_feature_extract_dict()


    def load_foam_case(self, overwrite=True):
        path = Path(self.foam_case_dir)
        if path.exists():
            if overwrite:
                shutil.rmtree(path, ignore_errors=True)
                path.mkdir(parents=True)
            else:
                raise ValueError(f"Path {path} already exists")
        else:
            shutil.rmtree(path, ignore_errors=True)
            path.mkdir(parents=True)

        (path / 'system').mkdir()
        (path / 'constant/triSurface').mkdir(parents=True)
        (path / '0').mkdir()

        self.foam_case = FoamCase(path)

    def load_objects(self):
        total_ac_flow_rate = 0.0
        total_tile_area = 0.0
        ac_set_temp = 0.0
        for region in self.regions:
            if region['type'] == 'cooler':
                total_ac_flow_rate += region['flow_rate']
                ac_set_temp = region['set_temp']
            elif region['type'] == 'tile':
                total_tile_area += (region['x_max'] - region['x_min']) * (region['y_max'] - region['y_min'])
        tile_flow_rate = total_tile_area / total_ac_flow_rate

        for region in self.regions:
            if region['type'] == 'room':
                continue
            else:
                bounds = [
                    region['x_min'], region['x_max'],
                    region['y_min'], region['y_max'],
                    region['z_min'], region['z_max']
                ]
                bc_mappings = {
                    "z_min": wall(),
                    "z_max": wall(),
                    "y_min": wall(),
                    "x_max": wall(),
                    "y_max": wall(),
                    "x_min": wall(),
                }
                if region['type'] == 'rack':
                    bc_mappings.update({
                        region['inlet']: fixed_velocity_outlet([0, region['flow_rate'], 0]),
                        region['outlet']: fixed_heat_flux_fixed_velocity_inlet(
                            [0, region['flow_rate'], 0],
                            region['heat_load'],
                        ),
                    })
                elif region['type'] == 'cooler':
                    bc_mappings.update({
                        region['inlet']: open_outlet(),
                    })
                elif region['type'] == 'tile':
                    bc_mappings.update({
                        'z_max': fixed_temperature_fixed_velocity_inlet(
                            [0, 0, tile_flow_rate],
                            ac_set_temp,
                        )
                    })
                region['object'] = cube(bounds, bc_mappings, name=region['name'], check_name=False)

    def write_all_objects(self, directory: str):
        for region in tqdm(self.regions, desc="Writing object STLs"):
            if region.get('object'):
                region['object'].write_stls(directory)

    def write_block_mesh_dict(self):
        with self.foam_case.block_mesh_dict as f:
            f['scale'] = 1
            f['vertices'] = [
                [self.room_dict['x_min'], self.room_dict['y_min'], self.room_dict['z_min']],
                [self.room_dict['x_max'], self.room_dict['y_min'], self.room_dict['z_min']],
                [self.room_dict['x_max'], self.room_dict['y_max'], self.room_dict['z_min']],
                [self.room_dict['x_min'], self.room_dict['y_max'], self.room_dict['z_min']],
                [self.room_dict['x_min'], self.room_dict['y_min'], self.room_dict['z_max']],
                [self.room_dict['x_max'], self.room_dict['y_min'], self.room_dict['z_max']],
                [self.room_dict['x_max'], self.room_dict['y_max'], self.room_dict['z_max']],
                [self.room_dict['x_min'], self.room_dict['y_max'], self.room_dict['z_max']],
            ]

            x_blocks = int(
                (self.room_dict['x_max'] - self.room_dict['x_min']) //
                (self.room_dict['z_max'] - self.room_dict['z_min'])
            )
            y_blocks = int(
                (self.room_dict['y_max'] - self.room_dict['y_min']) //
                (self.room_dict['z_max'] - self.room_dict['z_min'])
            )

            f['blocks'] = [
                'hex', [0, 1, 2, 3, 4, 5, 6, 7], [x_blocks * 2, y_blocks * 2, 2], 'simpleGrading', [1, 1, 1]
            ]

            f['edges'] = []

            f['boundary'] = [
                ('room_y_max', {'type': 'wall', 'faces': [[3, 7, 6, 2]]}),
                ('room_x_min', {'type': 'wall', 'faces': [[0, 4, 7, 3]]}),
                ('room_x_max', {'type': 'wall', 'faces': [[2, 6, 5, 1]]}),
                ('room_y_min', {'type': 'wall', 'faces': [[1, 5, 4, 0]]}),
                ('room_z_max', {'type': 'wall', 'faces': [[4, 5, 6, 7]]}),
                ('room_z_min', {'type': 'wall', 'faces': [[0, 3, 2, 1]]}),
            ]

            f['mergePatchPairs'] = []

    def write_control_dict(self):
        with self.foam_case.control_dict as f:
            f['application'] = 'buoyantSimpleFoam'
            f['startFrom'] = 'startTime'
            f['startTime'] = 0
            f['stopAt'] = 'endTime'
            f['endTime'] = 10000
            f['deltaT'] = 1
            f['writeControl'] = 'timeStep'
            f['writeInterval'] = 5000
            f['purgeWrite'] = 0
            f['writeFormat'] = 'ascii'
            f['writePrecision'] = 6
            f['writeCompression'] = 'off'
            f['timeFormat'] = 'general'
            f['timePrecision'] = 6
            f['runTimeModifiable'] = 'false'

    def write_snappy_hex_mesh_dict(self):
        with FoamFile(self.foam_case.path / 'system' / 'snappyHexMeshDict') as f:
            f['castellatedMesh'] = 'true'
            f['snap'] = 'true'
            f['addLayers'] = 'false'

            geometry = {}
            for region in self.regions:
                if region.get('object'):
                    geometry.update(region['object'].get_shm_geometry_dict())
            f['geometry'] = geometry

            refinement_surfaces = {}
            for region in self.regions:
                if region.get('object'):
                    refinement_surfaces.update(region['object'].get_shm_refinement_dict())
            f['refinement_surfaces'] = refinement_surfaces

            f['castellatedMeshControls'] = {
                'maxLocalCells': 100000,
                'maxGlobalCells': 2000000,
                'minRefinementCells': 100,
                'nCellsBetweenLevels': 1,
                'features': [{
                    'file': 'allFeatures.eMesh',
                    'level': 2
                }],
                'refinementSurfaces': refinement_surfaces,
                'resolveFeatureAngle': 30,
                'refinementRegions': {},
                'locationInMesh': [22.5, 2.0, 3.0],
                'allowFreeStandingZoneFaces': 'true',
            }

            f['snapControls'] = {
                'nSmoothPatch': 3,
                'tolerance': 1,
                'nSolveIter': 30,
                'nRelaxIter': 5,
                'nFeatureSnapIter': 10,
                'implicitFeatureSnap': 'true',
                'explicitFeatureSnap': 'false'
            }

            f['addLayersControls'] = {}

            f['meshQualityControls'] = {
                '#include': 'meshQualityDict',
                'nSmoothScale': 4,
                'errorReduction': 0.75,
                'maxBoundarySkewness': 4
            }

            f['mergeTolerance'] = 1e-6

    def write_fv_schemes(self):
        with self.foam_case.fv_schemes as f:
            f['ddtSchemes'] = {
                'default': 'steadyState',
            }

            f['gradSchemes'] = {
                'default': 'Gauss linear'
            }

            f['divSchemes'] = {
                'default': 'Gauss linear',   # todo unscam this when foamlib gets fixed

                'div(phi,U)': 'bounded Gauss upwind',
                'div(phi,h)': 'bounded Gauss upwind',

                'div(phi,k)': 'bounded Gauss upwind',
                'div(phi,epsilon)': 'bounded Gauss upwind',
                'div(phi,K)': 'bounded Gauss upwind',

                'div(phi,Ekp)': 'bounded Gauss linear',

                # 'div(((rho*nuEff)*dev2(T(grad(U)))))': 'Gauss linear',

                'div(phi,age)': 'bounded Gauss upwind'

            }

            f['laplacianSchemes'] = {
                'default': 'Gauss linear orthogonal',
            }

            f['interpolationSchemes'] = {
                'default': 'linear'
            }

            f['snGradSchemes'] = {
                'default': 'orthogonal'
            }

    def write_fv_solution(self):
        with (self.foam_case.fv_solution as f):
            f['solvers'] = {
                'p_rgh': {
                    'solver': 'GAMG',
                    'smoother': 'GaussSeidel',
                    'tolerance': 1e-08,
                    'relTol': 0.01
                },
                'U': {
                    'solver': 'PBiCGStab',
                    'preconditioner': 'DILU',
                    'tolerance': 1e-07,
                    'relTol': 0.1
                },
                'h': {
                    'solver': 'PBiCGStab',
                    'preconditioner': 'DILU',
                    'tolerance': 1e-07,
                    'relTol': 0.1
                },
                'k': {
                    'solver': 'PBiCGStab',
                    'preconditioner': 'DILU',
                    'tolerance': 1e-07,
                    'relTol': 0.1
                },
                'epsilon': {
                    'solver': 'PBiCGStab',
                    'preconditioner': 'DILU',
                    'tolerance': 1e-07,
                    'relTol': 0.1
                },
                'age': {
                    'solver': 'PBiCGStab',
                    'preconditioner': 'DILU',
                    'tolerance': 1e-07,
                    'relTol': 0.001
                }
            }

            f['SIMPLE'] = {
                'nNonOrthogonalCorrectors': 0,
                'momentumPredictor': 'false',

                'pRefPoint': [22.5, 2.0, 3.0],
                'pRefValue': 0,
                'residualControl': {
                    'p_rgh': 1e-6,
                    'U': 1e-6,
                    'h': 1e-6,
                    'k': 1e-6,
                    'epsilon': 1e-6,
                }
            }

            f['relaxationFactors'] = {
                'fields': {
                    'p_rgh': 0.7
                },
                'equations': {
                    'U': 0.3,
                    'h': 0.3,
                    'k': 0.7,
                    'age': 1,
                }
            }

    def write_field_files(self):
        room_object = None
        for region in self.regions:
            if region['type'] == 'room':
                room_object = cube(
                    bounds=[
                        region['x_min'], region['x_max'],
                        region['y_min'], region['y_max'],
                        region['z_min'], region['z_max']
                    ],
                    bc_mappings={
                        "z_min": wall(),
                        "z_max": wall(),
                        "y_min": wall(),
                        "x_max": wall(),
                        "y_max": wall(),
                        "x_min": wall(),
                    },
                    name='room',
                    check_name=False
                )

        if room_object is None:
            raise ValueError('Room definition not found in input.')

        bc_dict = room_object.get_bcs_foam_dict()
        for region in self.regions:
            if region.get('object') is not None:
                object_bc = region['object'].get_bcs_foam_dict()
                for field in object_bc.keys():
                    if field not in bc_dict:
                        bc_dict[field] = object_bc[field]
                    else:
                        bc_dict[field].update(object_bc[field])

        with self.foam_case[0]['alphat'] as f:
            f.dimensions = FoamFile.DimensionSet(mass=1, length=-1, time=-1)
            f.internal_field = 0

        with self.foam_case[0]['epsilon'] as f:
            f.dimensions = FoamFile.DimensionSet(length=2, time=-3)
            f.internal_field = 0.23

        with self.foam_case[0]['k'] as f:
            f.dimensions = FoamFile.DimensionSet(length=2, time=-2)
            f.internal_field = 0.08

        with self.foam_case[0]['nut'] as f:
            f.dimensions = FoamFile.DimensionSet(length=2, time=-1)
            f.internal_field = 0

        with self.foam_case[0]['p'] as f:
            f.dimensions = FoamFile.DimensionSet(mass=1, length=-1, time=-2)
            f.internal_field = 101325

        with self.foam_case[0]['p_rgh'] as f:
            f.dimensions = FoamFile.DimensionSet(mass=1, length=-1, time=-2)
            f.internal_field = 101325

        with self.foam_case[0]['T'] as f:
            f.dimensions = FoamFile.DimensionSet(temperature=1)
            f.internal_field = 295.15

        with self.foam_case[0]['U'] as f:
            f.dimensions = FoamFile.DimensionSet(length=1, time=-1)
            f.internal_field = [0, 0, 0]

        for field in bc_dict.keys():
            with self.foam_case[0][field] as f:
                f.boundary_field = bc_dict[field]

    def write_transport_properties(self):
        with self.foam_case.transport_properties as f:
            f['transportModel'] = 'Newtonian'
            f['nu'] = 1e-5
            f['beta'] = 3e-3
            f['TRef'] = 300
            f['Pr'] = 0.7
            f['Prt'] = 0.85

    def write_g_dict(self):
        with self.foam_case['constant']['g'] as f:
            f['dimensions'] = FoamFile.DimensionSet(length=1, time=-2)
            f['value'] = [0, 0, -9.81]

    def write_thermophyiscal_properties(self):
        with self.foam_case['constant']['thermophysicalProperties'] as f:
            f['thermoType'] = {
                'type': 'heRhoThermo',
                'mixture': 'pureMixture',
                'transport': 'const',
                'thermo': 'hConst',
                'equationOfState': 'perfectGas',
                'specie': 'specie',
                'energy': 'sensibleEnthalpy'
            }

            specie = {
                'molWeight': 28.9
            }

            equation_of_state = {
                'rho0': 1.18,
                'T0': 300,
                'beta': 3.33e-3
            }

            thermodynamics = {
                'Cp': 1005,
                'Hf': 0
            }

            transport = {
                'mu': 1.8,
                'Pr': 0.7
            }

            f['mixture'] = {
                'specie': specie,
                'equationOfState': equation_of_state,
                'thermodynamics': thermodynamics,
                'transport': transport,
            }

    def write_turbulence_properties(self):
        with self.foam_case.turbulence_properties as f:
            f['simulationType'] = 'RAS'
            f['RAS'] = {
                'RASModel': 'kEpsilon',
            }

    def write_mesh_quality_dict(self):
        with self.foam_case['system']['meshQualityDict'] as f:
            f['#includeEtc'] = '"caseDicts/meshQualityDict"'

    def write_surface_feature_extract_dict(self):
        surfaces = []
        for region in self.regions:
            if region.get('object') is not None:
                surfaces += region['object'].get_shm_geometry_dict().keys()
        with self.foam_case['system']['surfaceFeatureExtractDict'] as f:
            f['allFeatures'] = {
                'surfaces': surfaces,
                'loadingOption': 'merge',
                'extractionMethod': 'extractFromSurface',
                'includedAngle': 120,
                'geometricTestOnly': 'no'
            }
