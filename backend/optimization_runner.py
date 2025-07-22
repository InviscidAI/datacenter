# optimization_runner.py

import json
from functools import partial
from pathlib import Path
import os
import shutil
from copy import deepcopy
import numpy as np

# --- MODIFIED: Import the main simulation runner, config transformer, and the low-level Simulation class ---
from simulation_runner import transform_config, run_openfoam_simulation
from optimization.binary_search import BinarySearchOptimizer, update_set_temp, check_max_temp
from optimization.ga import GAOptimizer
from simulation import Simulation # For running the baseline simulation

def generate_ga_optim_input(config):
    """
    Dynamically generates the 'optim_input.json' structure based on the room
    layout and existing objects to create a valid grid of possible rack locations.
    """
    # --- FIX: Add more robust checking for the high-level config format ---
    if 'room' not in config or 'points' not in config.get('room', {}):
        raise ValueError("GA Error: The 'config' object from the frontend must have a 'room' key with a 'points' list.")
        
    room_contour = np.array(config['room']['points'])
    room_min = room_contour.min(axis=0)
    room_max = room_contour.max(axis=0)

    # --- 1. Identify movable racks and static obstacles ---
    racks = [obj for obj in config.get('objects', []) if obj.get('category') == 'rack']
    obstacles = [obj for obj in config.get('objects', []) if obj.get('category') != 'rack']
    
    if not racks:
        raise ValueError("No objects with category 'rack' found for GA optimization.")

    movable_rack_names = [rack['name'] for rack in racks]

    # --- 2. Define a standard rack size and layout parameters ---
    avg_width = np.mean([obj['bounding_box']['x_max'] - obj['bounding_box']['x_min'] for obj in racks])
    avg_depth = np.mean([obj['bounding_box']['y_max'] - obj['bounding_box']['y_min'] for obj in racks])
    z_min = 0.0
    z_max = 1.975

    hot_aisle_width = 1.5
    cold_aisle_width = 1.5
    margin = 1.0

    # --- 3. Generate possible positions in a simple hot/cold aisle layout ---
    possible_positions = []
    
    y_row_1 = room_min[1] + margin
    y_row_2 = y_row_1 + avg_depth + hot_aisle_width
    
    for y_start in [y_row_1, y_row_2]:
        x_current = room_min[0] + margin
        while x_current + avg_width < room_max[0] - margin:
            pos = {
                'x_min': x_current, 'y_min': y_start, 'z_min': z_min,
                'x_max': x_current + avg_width, 'y_max': y_start + avg_depth, 'z_max': z_max
            }
            is_valid = True
            for obs in obstacles:
                obs_box = obs['bounding_box']
                if not (pos['x_max'] < obs_box['x_min'] or pos['x_min'] > obs_box['x_max'] or \
                        pos['y_max'] < obs_box['y_min'] or pos['y_min'] > obs_box['y_max']):
                    is_valid = False
                    break
            if is_valid:
                possible_positions.append(pos)
                
            x_current += avg_width + cold_aisle_width

    if len(possible_positions) < len(movable_rack_names):
        raise ValueError(f"Could not generate enough valid positions ({len(possible_positions)}) for the number of racks ({len(movable_rack_names)}). Check room size and obstacle placement.")

    return {
        "objects": movable_rack_names,
        "positions": possible_positions
    }

def create_final_ga_config(original_config, optim_dict, best_position_indices):
    final_config = deepcopy(original_config)
    optimized_object_names = optim_dict['objects']
    new_positions = [optim_dict['positions'][i] for i in best_position_indices]

    objects_to_keep = [obj for obj in final_config.get('objects', []) if obj.get('name') not in optimized_object_names]
    newly_placed_objects = []
    for i, name in enumerate(optimized_object_names):
        original_object = next((obj for obj in original_config.get('objects', []) if obj.get('name') == name), None)
        if original_object:
            newly_placed_objects.append({
                "name": name,
                "category": original_object['category'],
                "bounding_box": new_positions[i]
            })
    final_config['objects'] = objects_to_keep + newly_placed_objects
    return final_config

def run_binary_search_optimization(config, run_id, simulations_db):
    run_path = Path('simulations', run_id)
    run_path.mkdir(parents=True, exist_ok=True)
    iteration_case_dir = run_path / 'bs_temp_case'
    try:
        base_sim_config = transform_config(config)
        target_max_temp = config.get('optimization_params', {}).get('target_max_temp_K', 308.15)
        check_func = partial(check_max_temp, max_temp=target_max_temp)
        optim = BinarySearchOptimizer(
            base=base_sim_config,
            low=288.15, high=target_max_temp,
            update_func=update_set_temp, check_func=check_func,
            foam_case_dir=iteration_case_dir, tol=1.0, max_iters=5
        )
        optimal_temp = optim.run()
        result_data = {'optimal_crac_temp_K': optimal_temp, 'target_max_temp_K': target_max_temp}
        
        print(f"[{run_id}] Binary search found optimal temp: {optimal_temp} K. Running final simulation...")
        final_config = deepcopy(config)
        final_config['physics']['crac_supply_temp_K'] = optimal_temp
        
        run_openfoam_simulation(final_config, run_id, simulations_db, is_optimization_run=True)
        
        with open(run_path / 'optimization_result.json', 'w') as f:
            json.dump(result_data, f)
    except Exception as e:
        print(f"ERROR in Binary Search [{run_id}]: {e}")
        simulations_db[run_id] = "failed"
    finally:
        if iteration_case_dir.exists():
            shutil.rmtree(iteration_case_dir)

def run_ga_optimization(config, run_id, simulations_db):
    run_path = Path('simulations', run_id)
    run_path.mkdir(parents=True, exist_ok=True)
    ga_temp_path = run_path / 'ga_iterations'
    cwd = os.getcwd()
    try:
        optim_dict = generate_ga_optim_input(config)
        
        base_sim_config = transform_config(config)

        ga_temp_path.mkdir(exist_ok=True)
        os.chdir(ga_temp_path)
        
        print(f"[{run_id}] GA: Running baseline simulation to get initial max temperature...")
        initial_sim = Simulation(base_sim_config, f"baseline_{run_id}")
        initial_sim.write_all()
        initial_sim.run_all()
        initial_max_temp_K = initial_sim.get_results().max_temp()
        print(f"[{run_id}] GA: Initial max temperature is {initial_max_temp_K:.2f} K")
        shutil.rmtree(initial_sim.foam_case_dir)
        
        ga = GAOptimizer(
            base=base_sim_config,
            optim_dict=optim_dict,
            mutation_scale=10,
            generations=5,
            num_per_gen=4
        )
        ga.start()

        os.chdir(cwd)

        ga.results.sort(key=lambda x: x[1])
        best_result = ga.results[0]
        best_position_indices, minimized_max_temp = best_result
        
        result_data = {
            'type': 'GA',
            'initial_max_temp_K': initial_max_temp_K,
            'minimized_max_temp_K': minimized_max_temp,
            'best_position_indices': best_position_indices,
            'all_results': ga.results
        }

        print(f"[{run_id}] GA found optimal layout. Running final simulation...")
        final_config = create_final_ga_config(config, optim_dict, best_position_indices)

        run_openfoam_simulation(final_config, run_id, simulations_db, is_optimization_run=True)

        with open(run_path / 'optimization_result.json', 'w') as f:
            json.dump(result_data, f)

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"ERROR in GA Optimization [{run_id}]: {e}")
        simulations_db[run_id] = "failed"
    finally:
        if os.getcwd() != cwd:
            os.chdir(cwd)
        if ga_temp_path.exists():
            shutil.rmtree(ga_temp_path)