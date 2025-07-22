import os
import shutil
import uuid
from pathlib import Path

# NEW: Import the Simulation class from the new library
from simulation.Simulation import Simulation

def transform_config(config: dict) -> list[dict]:
    """
    Transforms the frontend config dictionary to the list-of-regions format
    required by the new Simulation class. This acts as an adapter layer.
    """
    regions = []

    # 1. Room Definition
    if 'room' in config and 'dims' in config['room']:
        w, d, h = config['room']['dims']
        regions.append({
            'type': 'room', 'name': 'room',
            'x_min': 0, 'y_min': 0, 'z_min': 0,
            'x_max': w, 'y_max': d, 'z_max': h
        })
    else:
        raise ValueError("Configuration must contain room dimensions.")

    # 2. Physics & Common Values
    physics = config.get('physics', {})
    crac_supply_temp_K = physics.get('crac_supply_temp_K', 293.15)  # Default to 20°C

    for rack in config.get('racks', []):
        pos = rack['pos']
        dims = rack['dims']
        regions.append({
            'type': 'rack', 'name': rack['name'],
            'x_min': pos[0], 'x_max': pos[0] + dims[0],
            'y_min': pos[1], 'y_max': pos[1] + dims[1],
            'z_min': pos[2], 'z_max': pos[2] + dims[2],
            'heat_load': rack['power_watts'],
            'flow_rate': rack.get('flow_rate', 0.5 * dims[0] * dims[2]), # Use value from UI or default
            'inlet': rack.get('inlet_face', 'y_min'),
            'outlet': rack.get('outlet_face', 'y_max')
        })

    # 4. CRAC Definitions (add inlet)
    for crac in config.get('cracs', []):
        pos = crac['pos']
        dims = crac['dims']
        regions.append({
            'type': 'cooler', 'name': crac['name'],
            'x_min': pos[0], 'x_max': pos[0] + dims[0],
            'y_min': pos[1], 'y_max': pos[1] + dims[1],
            'z_min': pos[2], 'z_max': pos[2] + dims[2],
            'flow_rate': crac.get('flow_rate', 1.0), # Use value from UI or default
            'set_temp': crac.get('supply_temp_K', 293.15),
            'inlet': crac.get('inlet_face', 'z_max'), # Air return
            'outlet': crac.get('outlet_face', 'y_min'), # Air return
        })
        
    # --- NEW: 5. Perforated Tile Definitions ---
    for tile in config.get('tiles', []):
        pos = tile['pos']
        dims = tile['dims']
        regions.append({
            'type': 'tile', 'name': tile['name'],
            'x_min': pos[0], 'x_max': pos[0] + dims[0],
            'y_min': pos[1], 'y_max': pos[1] + dims[1],
            'z_min': pos[2], 'z_max': pos[2] + dims[2],
            # Note: The backend Simulation class calculates tile flow rate automatically
            # based on total cooler flow rate, so we don't need to pass it here.
        })
        
    return regions


def run_openfoam_simulation(config, run_id, simulations_db, is_optimization_run=False):
    """
    Orchestrates an OpenFOAM simulation using the new modular Simulation class.
    The 'is_optimization_run' flag is not used internally here, but adding it
    to the function signature allows the optimization runner to call this function
    without causing an argument mismatch error.
    """
    run_path = Path(os.path.abspath(os.path.join('simulations', run_id)))
    log_path = run_path / 'simulation_runner.log'

    # Optimization runs should not create their own directory, they use the one already created.
    if not is_optimization_run:
        run_path.mkdir(parents=True, exist_ok=True)

    try:
        # For an optimization run, the status is already 'running_optimization', 
        # so we don't want to overwrite it back to 'running'.
        if not is_optimization_run:
            simulations_db[run_id] = "running" # Set status for normal runs

        with open(log_path, 'w') as log_file:
            log_file.write(f"[{run_id}] Starting simulation setup...\n")
            
            # 1. Transform the input config to the new format
            log_file.write("Transforming configuration...\n")
            sim_config = transform_config(config)

            # 2. Instantiate the main Simulation object
            log_file.write(f"Initializing simulation in: {run_path}\n")
            sim = Simulation(inp=sim_config, foam_case_dir=run_path, overwrite=True)

            # 3. Write all OpenFOAM case files
            log_file.write("Writing OpenFOAM case files...\n")
            log_file.flush()
            sim.write_all()

            # 4. Run the simulation steps (blockMesh, snappyHexMesh, buoyantSimpleFoam)
            log_file.write("Starting OpenFOAM solver execution... See separate log files for details.\n")
            log_file.flush()
            sim.run_all() # This method handles the subprocess calls internally

            # 5. Process and convert results to GLTF
            log_file.write("Simulation finished. Converting results to glTF...\n")
            log_file.flush()
            results = sim.get_results()
            if results.convert_results_to_gltf():
                log_file.write("Result conversion successful.\n")
                simulations_db[run_id] = "completed"
            else:
                log_file.write("Result conversion failed.\n")
                simulations_db[run_id] = "failed"

    except Exception as e:
        # Catch any error during the process and mark the simulation as failed
        error_message = f"[{run_id}] ERROR: An unexpected error occurred: {e}"
        print(error_message)
        import traceback
        traceback.print_exc()
        with open(log_path, 'a') as log_file:
            log_file.write(f"\n{error_message}\n")
            traceback.print_exc(file=log_file)
        simulations_db[run_id] = "failed"