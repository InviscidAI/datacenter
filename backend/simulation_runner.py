import os
import shutil
import numpy as np
from stl import mesh
import subprocess
import uuid
import pyvista as pv

# Path to your OpenFOAM sourcing script.
OPENFOAM_BASHRC = "/usr/lib/openfoam/openfoam2412/etc/bashrc"

# Dummy .foam file template for PyVista
CASE_FOAM_TEMPLATE = "FoamFile { version 2.0; format ascii; class dictionary; location \"system\"; object controlDict; }"

def create_face_stl(filepath, v0, v1, v2, v3):
    face_mesh = mesh.Mesh(np.zeros(2, dtype=mesh.Mesh.dtype))
    face_mesh.vectors[0] = np.array([v0, v1, v2])
    face_mesh.vectors[1] = np.array([v0, v2, v3])
    face_mesh.save(filepath)

def generate_stls_by_face(config, stl_dir):
    if os.path.exists(stl_dir): shutil.rmtree(stl_dir)
    os.makedirs(stl_dir)
    w, d, h = config["room"]["dims"]
    v = np.array([[0,0,0],[w,0,0],[w,d,0],[0,d,0],[0,0,h],[w,0,h],[w,d,h],[0,d,h]])
    f = np.array([[0,3,1],[1,3,2],[0,4,7],[0,7,3],[4,5,6],[4,6,7],[5,1,2],[5,2,6],[2,3,7],[2,7,6],[0,1,5],[0,5,4]])
    room_mesh = mesh.Mesh(np.zeros(f.shape[0], dtype=mesh.Mesh.dtype))
    for i, face in enumerate(f):
        for j in range(3): room_mesh.vectors[i][j] = v[face[j],:]
    room_mesh.save(os.path.join(stl_dir, "room_walls.stl"))
    
    for obj_list in [config.get("racks", []), config.get("cracs", [])]:
        for obj in obj_list:
            name, pos, dims = obj["name"], obj["pos"], obj["dims"]
            x,y,z = pos
            w,d,h = dims
            
            # FIX 1: This block is now a direct, correct copy of your original gen.py logic.
            # The typo `[x,y,d,z]` has been corrected to `[x,y+d,z]`.
            v = np.array([
                [x,y,z], [x+w,y,z], [x+w,y+d,z], [x,y+d,z],
                [x,y,z+h], [x+w,y,z+h], [x+w,y+d,z+h], [x,y+d,z+h]
            ])
            
            create_face_stl(os.path.join(stl_dir, f"{name}_bottom.stl"), v[0], v[3], v[2], v[1])
            create_face_stl(os.path.join(stl_dir, f"{name}_top.stl"),    v[4], v[5], v[6], v[7])
            create_face_stl(os.path.join(stl_dir, f"{name}_front.stl"),  v[0], v[1], v[5], v[4])
            create_face_stl(os.path.join(stl_dir, f"{name}_back.stl"),   v[2], v[3], v[7], v[6])
            create_face_stl(os.path.join(stl_dir, f"{name}_left.stl"),   v[0], v[4], v[7], v[3])
            create_face_stl(os.path.join(stl_dir, f"{name}_right.stl"),  v[1], v[2], v[6], v[5])

def generate_system_files(config, run_path):
    system_dir = os.path.join(run_path, "system")
    stl_dir = os.path.join(run_path, "constant/triSurface")
    rx, ry, rz = config['room']['dims']
    nx,ny,nz = config.get('meshing', {}).get('background_mesh_cells', (24,20,7))
    ref_level = config.get('meshing', {}).get('surface_refinement_level', 2)
    bmd_content = f"""
FoamFile {{ version 2.0; format ascii; class dictionary; object blockMeshDict; }}
convertToMeters 1;
vertices ( (0 0 0) ({rx} 0 0) ({rx} {ry} 0) (0 {ry} 0) (0 0 {rz}) ({rx} 0 {rz}) ({rx} {ry} {rz}) (0 {ry} {rz}) );
blocks ( hex (0 1 2 3 4 5 6 7) ({nx} {ny} {nz}) simpleGrading (1 1 1) );
edges (); boundary (); mergePatchPairs ();
"""
    with open(os.path.join(system_dir, "blockMeshDict"), "w") as f: f.write(bmd_content)

    all_stls = sorted(os.listdir(stl_dir))
    geometry_str = "".join([f'    {stl} {{ type triSurfaceMesh; name {os.path.splitext(stl)[0]}; }}\n' for stl in all_stls])
    ref_surfaces_str = "".join([f'        {os.path.splitext(stl)[0]} {{ level ({ref_level} {ref_level}); }}\n' for stl in all_stls if "room" not in stl])
    sHMd_content = f"""
FoamFile {{ version 2.0; format ascii; class dictionary; object snappyHexMeshDict; }}
castellatedMesh   true; snap true; addLayers false; mergeTolerance 1E-6;
geometry {{
{geometry_str}
}};
castellatedMeshControls {{
    maxLocalCells 1000000; maxGlobalCells 5000000; minRefinementCells 10;
    maxLoadUnbalance 0.10; nCellsBetweenLevels 3; allowFreeStandingZoneFaces true;
    locationInMesh ({rx*0.1} {ry*0.1} {rz*0.1});
    features ();
    refinementSurfaces
    {{
{ref_surfaces_str}
    }}
    refinementRegions {{ }}; resolveFeatureAngle 30;
}};
snapControls {{ nSmoothPatch 3; tolerance 4.0; nSolveIter 30; nRelaxIter 5; }};
addLayersControls {{ relativeSizes true; layers {{ }}; expansionRatio 1.0; }};
meshQualityControls {{
    maxNonOrtho 65; maxBoundarySkewness 20; maxInternalSkewness 4; maxConcave 80;
    minVol 1e-13; minTetQuality -1e30; minArea -1; minTwist 0.02; minDeterminant 0.001;
    minFaceWeight 0.05; minVolRatio 0.01; minTriangleTwist -1; nSmoothScale 4; errorReduction 0.75;
    relaxed {{ maxNonOrtho 75; }}
}};
"""
    with open(os.path.join(system_dir, "snappyHexMeshDict"), "w") as f: f.write(sHMd_content)

def generate_boundary_conditions(config, run_path):
    zero_dir = os.path.join(run_path, "0")
    if os.path.exists(zero_dir): shutil.rmtree(zero_dir)
    os.makedirs(zero_dir)

    all_patches = ["room_walls"]
    for obj_list in [config.get("racks", []), config.get("cracs", [])]:
        for obj in obj_list:
            all_patches.extend([f'{obj["name"]}_{face}' for face in ["top", "bottom", "left", "right", "front", "back"]])

    def write_field_file(filename, field_class, dimensions, internal_field, boundary_field_dict_str):
        content = f"""/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\\\    /   O peration     | Version:  v2412                                 |
|   \\\\  /    A nd           | Website:  www.openfoam.com                      |
|    \\\\/     M anipulation  |                                                 |
\\*---------------------------------------------------------------------------*/
FoamFile
{{
    version     2.0;
    format      ascii;
    class       {field_class};
    object      {os.path.basename(filename)};
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //
dimensions      {dimensions};
internalField   {internal_field};
boundaryField
{{
{boundary_field_dict_str}
}}
// ************************************************************************* //
"""
        with open(os.path.join(zero_dir, filename), "w") as f: f.write(content)

    bf_U, bf_T, bf_p_rgh, bf_p, bf_k, bf_epsilon, bf_nut, bf_alphat = "", "", "", "", "", "", "", ""
    physics = config.get('physics', {})
    crac_supply_temp_K = physics.get('crac_supply_temp_K', 285.15)
    initial_temp_K = physics.get('initial_temp_K', 295.15)
    initial_k = physics.get('initial_k', 0.08)
    initial_epsilon = physics.get('initial_epsilon', 0.23)

    for patch in all_patches:
        U_bc, T_bc, p_rgh_bc, k_bc, epsilon_bc, nut_bc, alphat_bc = (
            "{ type noSlip; }",
            "{ type zeroGradient; }",
            "{ type fixedFluxPressure; value $internalField; }",
            "{ type kqRWallFunction; value $internalField; }",
            "{ type epsilonWallFunction; value $internalField; }",
            "{ type nutkWallFunction; value $internalField; }",
            "{ type compressible::alphatJayatillekeWallFunction; Prt 0.85; value $internalField; }"
        )
        if "rack" in patch and patch.endswith("_back"):
            power = next(r['power_watts'] for r in config['racks'] if r['name'] in patch)
            T_bc = f"{{ type externalWallHeatFluxTemperature; mode power; Q uniform {power}; kappaMethod fluidThermo; value $internalField; }}"
        elif "crac" in patch and patch.endswith("_front"):
            velocity = next(c['supply_velocity'] for c in config['cracs'] if c['name'] in patch)
            T_bc = f"{{ type fixedValue; value uniform {crac_supply_temp_K}; }}"
            U_bc = f"{{ type fixedValue; value uniform (0 {-velocity} 0); }}"
            k_bc = "{ type turbulentIntensityKineticEnergyInlet; intensity 0.14; value $internalField; }"
            epsilon_bc = "{ type turbulentMixingLengthDissipationRateInlet; mixingLength 0.0168; value $internalField; }"
            nut_bc = "{ type calculated; value $internalField; }"
            alphat_bc = "{ type calculated; value $internalField; }"
        elif "crac" in patch and patch.endswith("_top"):
            U_bc = "{ type pressureInletOutletVelocity; value $internalField; }"
            T_bc = "{ type zeroGradient; }"
            p_rgh_bc = "{ type prghPressure; p $internalField; value $internalField; }"
            k_bc = "{ type inletOutlet; inletValue $internalField; }"
            epsilon_bc = "{ type inletOutlet; inletValue $internalField; }"
            nut_bc = "{ type calculated; value $internalField; }"
            alphat_bc = "{ type calculated; value $internalField; }"
        
        # FIX 2: Using `\n` for a correct newline, not `\\n`.
        bf_U += f"    {patch}\n    {U_bc}\n"
        bf_T += f"    {patch}\n    {T_bc}\n"
        bf_p_rgh += f"    {patch}\n    {p_rgh_bc}\n"
        bf_k += f"    {patch}\n    {k_bc}\n"
        bf_epsilon += f"    {patch}\n    {epsilon_bc}\n"
        bf_p += f"    {patch}\n    {{ type calculated; value $internalField; }}\n"
        bf_nut += f"    {patch}\n    {nut_bc}\n"
        bf_alphat += f"    {patch}\n    {alphat_bc}\n"

    write_field_file("U", "volVectorField", "[0 1 -1 0 0 0 0]", "uniform (0 0 0)", bf_U)
    write_field_file("T", "volScalarField", "[0 0 0 1 0 0 0]", f"uniform {initial_temp_K}", bf_T)
    write_field_file("p_rgh", "volScalarField", "[1 -1 -2 0 0 0 0]", "uniform 101325", bf_p_rgh)
    write_field_file("p", "volScalarField", "[1 -1 -2 0 0 0 0]", "uniform 101325", bf_p)
    write_field_file("k", "volScalarField", "[0 2 -2 0 0 0 0]", f"uniform {initial_k}", bf_k)
    write_field_file("epsilon", "volScalarField", "[0 2 -3 0 0 0 0]", f"uniform {initial_epsilon}", bf_epsilon)
    write_field_file("nut", "volScalarField", "[0 2 -1 0 0 0 0]", "uniform 0", bf_nut)
    write_field_file("alphat", "volScalarField", "[1 -1 -1 0 0 0 0]", "uniform 0", bf_alphat)

# --- (The rest of the file remains the same as the previous correct version) ---

def convert_results_to_gltf(run_path):
    """Uses PyVista Plotter to convert the final OpenFOAM timestep to glTF files."""
    results_dir = os.path.join(run_path, 'results')
    if not os.path.exists(results_dir):
        os.makedirs(results_dir)
    case_foam_path = os.path.join(run_path, 'case.foam')
    with open(case_foam_path, 'w') as f:
        f.write(CASE_FOAM_TEMPLATE)

    try:
        reader = pv.OpenFOAMReader(case_foam_path)
        reader.set_active_time_value(reader.time_values[-1])
        mesh_data = reader.read()['internalMesh']
        if mesh_data is None:
            raise Exception("Failed to read internalMesh from OpenFOAM results.")
        
        # Get room dimensions for centering the slice
        bounds = mesh_data.bounds
        center_x = (bounds[0] + bounds[1]) / 2
        center_y = (bounds[2] + bounds[3]) / 2
        center_z = (bounds[4] + bounds[5]) / 2

        # --- Temperature Slice Export ---
        # Create a slice plane through the center of the mesh, normal to the Z-axis (a horizontal slice)
        temp_slice = mesh_data.slice(normal='z', origin=(center_x, center_y, center_z))
        
        # Get the wireframe of the outer room for context
        room_wireframe = mesh_data.extract_surface().extract_feature_edges()

        plotter_temp = pv.Plotter(off_screen=True)
        # Add the colored temperature slice
        plotter_temp.add_mesh(temp_slice, cmap='coolwarm', scalars='T', scalar_bar_args={'title': 'Temperature (K)'})
        # Add the room outline for context
        plotter_temp.add_mesh(room_wireframe, color='white', style='wireframe')
        plotter_temp.export_gltf(os.path.join(results_dir, 'temperature.gltf'))
        plotter_temp.export_gltf(os.path.join(results_dir, 'velocity.gltf'))
        plotter_temp.close()
        print("--> Temperature slice results converted.")

        # # --- Velocity Glyphs (Arrows) Export ---
        # # Create a different slice for velocity to avoid clutter, this one vertical
        # velocity_slice = mesh_data.slice(normal='y', origin=(center_x, center_y, center_z))

        # # We can make the glyphs smaller and more numerous on a 2D slice
        # velocity_glyphs = velocity_slice.glyph(orient='U', factor=0.05, geom=pv.Arrow(), scale="U")

        # plotter_vel = pv.Plotter(off_screen=True)
        # # Add the colored velocity arrows
        # plotter_vel.add_mesh(velocity_glyphs, cmap='viridis', scalars='U', scalar_bar_args={'title': 'Velocity (m/s)'})
        # # Add the room outline for context
        # plotter_vel.add_mesh(room_wireframe, color='white', style='wireframe')
        # plotter_vel.export_gltf(os.path.join(results_dir, 'velocity.gltf'))
        # plotter_vel.close()
        print("--> Velocity glyph results converted.")

        pv.close_all()
        print(f"--> All results converted to glTF in {results_dir}")
        return True
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"--> FAILED to convert results to glTF: {e}")
        return False

def run_openfoam_simulation(config, run_id, simulations_db):
    run_path = os.path.abspath(os.path.join('simulations', run_id))
    os.makedirs(run_path, exist_ok=True)
    log_path = os.path.join(run_path, 'log.txt')
    try:
        print(f"[{run_id}] Setting up case directory...")
        os.makedirs(os.path.join(run_path, 'constant/triSurface'), exist_ok=True)
        os.makedirs(os.path.join(run_path, 'system'), exist_ok=True)
        template_dir = os.path.join(os.path.dirname(__file__), 'template_case')
        # for item in ['fvSchemes', 'fvSolution', 'controlDict']:
        #      shutil.copy(os.path.join(template_dir, 'system', item), os.path.join(run_path, 'system'))
        # shutil.copy(os.path.join(template_dir, 'constant', 'thermophysicalProperties'), os.path.join(run_path, 'constant'))
        shutil.copytree(template_dir, run_path, dirs_exist_ok=True)

        print(f"[{run_id}] Generating files from config...")
        generate_stls_by_face(config, os.path.join(run_path, 'constant/triSurface'))
        generate_system_files(config, run_path)
        generate_boundary_conditions(config, run_path)
        
        commands_to_run = [
            "blockMesh",
            "snappyHexMesh -overwrite",
            "buoyantSimpleFoam"
        ]
        
        with open(log_path, 'w') as log_file:
            for command in commands_to_run:
                print(f"[{run_id}] Running: {command}")
                log_file.write(f"\n\n{'='*20}\n--- Running: {command} ---\n{'='*20}\n\n")
                log_file.flush()
                full_shell_command = f"source {OPENFOAM_BASHRC} && {command}"
                subprocess.run(
                    full_shell_command,
                    shell=True,
                    check=True,
                    cwd=run_path,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    executable='/bin/bash'
                )
        
        print(f"[{run_id}] Simulation successful. Converting results...")
        if convert_results_to_gltf(run_path):
            print("yay")
            simulations_db[run_id] = "completed"
        else:
            print("nay")
            simulations_db[run_id] = "failed"
    except subprocess.CalledProcessError:
        print(f"[{run_id}] ERROR: A command failed. Check log.txt in the run directory.")
        simulations_db[run_id] = "failed"
    except Exception as e:
        print(f"[{run_id}] ERROR: An unexpected Python error occurred: {e}")
        simulations_db[run_id] = "failed"