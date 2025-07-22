# optimization_runner.py

import json
from functools import partial
from pathlib import Path
import os
import shutil
from copy import deepcopy
import numpy as np

from simulation_runner import transform_config, run_openfoam_simulation
from optimization.binary_search import BinarySearchOptimizer, update_set_temp, check_max_temp
from optimization.ga import GAOptimizer
from simulation import Simulation

def generate_ga_optim_input(config):
    """
    Dynamically generates the 'optim_input.json' structure based on the room
    layout and existing objects to create a valid grid of possible rack locations.
    """
    if 'room' not in config or 'points' not in config.get('room', {}):
        raise ValueError("GA Error: The 'config' object from the frontend must have a 'room' key with a 'points' list.")

    room_contour = np.array(config['room']['points'])
    room_min = room_contour.min(axis=0)
    room_max = room_contour.max(axis=0)

    racks = [obj for obj in config.get('objects', []) if obj.get('category') == 'Data Rack']
    obstacles = [obj for obj in config.get('objects', []) if obj.get('category') != 'Data Rack']

    if not racks:
        raise ValueError("No objects with category 'Data Rack' found for GA optimization.")

    movable_rack_names = [rack['name'] for rack in racks]
    
    if not all('bounding_box' in r for r in racks):
        raise ValueError("One or more racks are missing 'bounding_box' data.")
        
    avg_width = np.mean([r['bounding_box']['x_max'] - r['bounding_box']['x_min'] for r in racks])
    avg_depth = np.mean([r['bounding_box']['y_max'] - r['bounding_box']['y_min'] for r in racks])
    z_min = 0.0
    z_max = 1.975

    hot_aisle_width = 1.5
    cold_aisle_width = 1.5
    margin = 1.0

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
                obs_box = obs.get('bounding_box')
                if obs_box and not (pos['x_max'] < obs_box['x_min'] or pos['x_min'] > obs_box['x_max'] or \
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
    # 'config' is the GA-style config: { "room": {"points":...}, "objects": [...] }
    run_path = Path('simulations', run_id)
    run_path.mkdir(parents=True, exist_ok=True)
    ga_temp_path = run_path / 'ga_iterations'
    cwd = os.getcwd()
    try:
        # Step 1: Generate the GA-specific dictionary of possible rack positions.
        optim_dict = generate_ga_optim_input(config)

        # Step 2: Define a robust helper function to convert the frontend's geometric config
        # into the standard simulation config that `transform_config` expects.
        def convert_ga_to_sim_config(ga_config, px_to_meters=0.05):
            sim_config = {}
            room_contour = np.array(ga_config['room']['points'])
            sim_config['room'] = {'dims': [(room_contour[:, 0].max() - room_contour[:, 0].min()) * px_to_meters, 
                                           (room_contour[:, 1].max() - room_contour[:, 1].min()) * px_to_meters, 4.0]}

            def convert_objects(category_name, default_height):
                converted = []
                for o in ga_config.get('objects', []):
                    if o['category'] == category_name:
                        bbox = o['bounding_box']
                        props = o.get('properties', {})
                        dims = [(bbox['x_max'] - bbox['x_min']) * px_to_meters, 
                                (bbox['y_max'] - bbox['y_min']) * px_to_meters, 
                                props.get('height', default_height)]
                        entry = {'name': o['name'], 'pos': [bbox['x_min'] * px_to_meters, bbox['y_min'] * px_to_meters, 0], 'dims': dims}
                        entry.update(props)
                        converted.append(entry)
                return converted

            sim_config['racks'] = convert_objects('Data Rack', 2.2)
            sim_config['cracs'] = convert_objects('CRAC', 1.8)
            sim_config['tiles'] = convert_objects('Perforated Tile', 0.01)
            sim_config['physics'] = ga_config.get('physics', {})
            return sim_config

        # Step 3: Create the standard config for the INITIAL layout and transform it to regions format.
        # This will be used for the baseline simulation AND to initialize the GA.
        initial_sim_config_standard = convert_ga_to_sim_config(config)
        initial_sim_config_regions = transform_config(initial_sim_config_standard)

        # Step 4: Run the baseline simulation to get the initial temperature.
        ga_temp_path.mkdir(exist_ok=True)
        os.chdir(ga_temp_path)
        
        print(f"[{run_id}] GA: Running baseline simulation...")
        initial_sim = Simulation(deepcopy(initial_sim_config_regions), f"baseline_{run_id}")
        initial_sim.write_all()
        initial_sim.run_all()
        initial_max_temp_K = initial_sim.get_results().max_temp()
        print(f"[{run_id}] GA: Initial max temperature is {initial_max_temp_K:.2f} K")
        shutil.rmtree(initial_sim.foam_case_dir)

        # Step 5: Run the GA using the correct, rack-inclusive base configuration.
        print(f"[{run_id}] GA: Starting optimization...")
        ga = GAOptimizer(
            base=initial_sim_config_regions,
            optim_dict=optim_dict,
            mutation_scale=10,
            generations=5,
            num_per_gen=4 # Increased for better search
        )
        ga.start()
        print(f"[{run_id}] GA: Optimization finished.")
        os.chdir(cwd)

        if not ga.results:
            raise RuntimeError("GA finished with no valid results.")

        # Step 6: Process results and create the final configuration.
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
        final_standard_config = convert_ga_to_sim_config(config) # Start with original layout
        
        new_positions = [optim_dict['positions'][i] for i in best_position_indices]
        new_pos_map = {name: pos for name, pos in zip(optim_dict['objects'], new_positions)}

        # Update rack positions in the standard config to the new optimized locations
        for rack in final_standard_config.get('racks', []):
            if rack['name'] in new_pos_map:
                new_pos = new_pos_map[rack['name']]
                px_to_meters = 0.05
                rack['pos'] = [new_pos['x_min'] * px_to_meters, new_pos['y_min'] * px_to_meters, 0]
                rack['dims'][0] = (new_pos['x_max'] - new_pos['x_min']) * px_to_meters
                rack['dims'][1] = (new_pos['y_max'] - new_pos['y_min']) * px_to_meters
        
        # Step 7: Run the final, optimized simulation.
        run_openfoam_simulation(final_standard_config, run_id, simulations_db, is_optimization_run=True)

        with open(run_path / 'optimization_result.json', 'w') as f:
            json.dump(result_data, f, indent=4)

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